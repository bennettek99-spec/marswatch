"""Pair alignment orchestration: coarse geo-offset search, re-read, dense fine registration."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from affine import Affine

from .imagery import Grid, RemoteImage, read_cached, read_tiled
from .log import get_logger
from .registration import CoarseResult, FineResult, coarse_offset, fine_register

log = get_logger("align")


def expand_grid(grid: Grid, margin_m: float, res_m: float) -> Grid:
    a = grid.affine
    left, top = a.c - margin_m, a.f + margin_m
    width_m = grid.width * grid.res + 2 * margin_m
    height_m = grid.height * grid.res + 2 * margin_m
    w, h = int(np.ceil(width_m / res_m)), int(np.ceil(height_m / res_m))
    return Grid(grid.crs_wkt, (res_m, 0.0, left, 0.0, -res_m, top), w, h)


def shift_grid(grid: Grid, dx_m: float, dy_m: float) -> Grid:
    t = list(grid.transform)
    t[2] += dx_m
    t[5] += dy_m
    return Grid(grid.crs_wkt, tuple(t), grid.width, grid.height)


@dataclass
class AlignedPair:
    grid: Grid
    before: np.ndarray
    before_valid: np.ndarray
    after: np.ndarray          # registered onto ``before``
    after_valid: np.ndarray
    after_raw: np.ndarray      # geo-shifted only (before fine registration) - for diagnostics
    coarse: CoarseResult
    fine: FineResult

    @property
    def valid(self) -> np.ndarray:
        return self.before_valid & self.after_valid


def find_coarse_offset(before: RemoteImage, after: RemoteImage, grid: Grid,
                       use_cache: bool = True) -> CoarseResult:
    """Multi-resolution search for the global translation between the two products."""
    best: CoarseResult | None = None
    for res_m, margin_m in ((4.0, 600.0), (8.0, 1500.0)):
        g = expand_grid(grid, margin_m, res_m)
        b, bv = read_cached(before, g, use_cache)
        a, av = read_cached(after, g, use_cache)
        c = coarse_offset(b, bv, a, av, res_m, margin_m)
        log.info(f"coarse @{res_m} m: dx={c.dx_m:.1f} dy={c.dy_m:.1f} peak={c.peak:.2f} distinct={c.distinct:.2f}")
        if best is None or c.peak > best.peak:
            best = c
        if c.ok:
            break
    assert best is not None
    if best.ok:
        # refine at 2 m/px in a small window around the coarse solution
        g = expand_grid(grid, 40.0, 2.0)
        b, bv = read_cached(before, g, use_cache)
        a, av = read_cached(after, shift_grid(g, best.dx_m, best.dy_m), use_cache)
        r = coarse_offset(b, bv, a, av, 2.0, 30.0)
        if r.ok:
            best = CoarseResult(best.dx_m + r.dx_m, best.dy_m + r.dy_m, r.peak, r.distinct, 2.0, True)
            log.info(f"refined @2 m: dx={best.dx_m:.1f} dy={best.dy_m:.1f} peak={r.peak:.2f}")
    return best


def block_affine(before: RemoteImage, after: RemoteImage, grid: Grid, coarse: CoarseResult, use_cache: bool = True,
                 block_m: float = 1200.0, res_m: float = 4.0, margin_m: float = 250.0) -> np.ndarray | None:
    """Initial affine (grid px -> grid px of the geo-shifted after image) from blockwise coarse offsets.

    Uncontrolled attitude errors produce rotation/shear across multi-km strips (we measured a 3 % shear,
    i.e. 160 m drift over 5.4 km, on ESP_017585_2080/ESP_078865_2080) that a single translation cannot
    absorb. Returns None for small areas or when fewer than 3 blocks give a reliable offset.
    """
    W, H = grid.width * grid.res, grid.height * grid.res
    nx, ny = max(1, int(round(W / block_m))), max(1, int(round(H / block_m)))
    if nx * ny < 3:
        return None
    pts, offs = [], []
    for j in range(ny):
        for i in range(nx):
            x0, y0 = int(i * grid.width / nx), int(j * grid.height / ny)
            x1, y1 = int((i + 1) * grid.width / nx), int((j + 1) * grid.height / ny)
            sub = grid.subgrid(x0, y0, x1 - x0, y1 - y0)
            g = expand_grid(sub, margin_m, res_m)
            b, bv = read_cached(before, g, use_cache)
            a, av = read_cached(after, shift_grid(g, coarse.dx_m, coarse.dy_m), use_cache)
            if bv.mean() < 0.5 or av.mean() < 0.5:
                continue
            c = coarse_offset(b, bv, a, av, res_m, margin_m * 0.8)
            if c.ok and c.distinct > 0.04:
                pts.append(((x0 + x1) / 2, (y0 + y1) / 2))
                offs.append((c.dx_m / grid.res, -c.dy_m / grid.res))
    if len(pts) < 3:
        return None
    P = np.array(pts, np.float64)
    D = np.array(offs, np.float64)
    X = np.column_stack([P, np.ones(len(P))])
    keep = np.ones(len(P), bool)
    for _ in range(3):  # trimmed least squares
        cx, *_ = np.linalg.lstsq(X[keep], D[keep, 0], rcond=None)
        cy, *_ = np.linalg.lstsq(X[keep], D[keep, 1], rcond=None)
        r = np.hypot(X @ cx - D[:, 0], X @ cy - D[:, 1])
        thr = max(3.0, 2.5 * np.median(r[keep]) * 1.4826)
        keep = r <= thr
        if keep.sum() < 3:
            return None
    A = np.array([[1 + cx[0], cx[1], cx[2]], [cy[0], 1 + cy[1], cy[2]]], np.float64)
    log.info(f"block affine from {int(keep.sum())}/{len(P)} blocks: {np.round(A, 4).tolist()}")
    return A


def align_pair(before: RemoteImage, after: RemoteImage, grid: Grid, use_cache: bool = True,
               tiled: bool = False, progress=None) -> AlignedPair:
    coarse = find_coarse_offset(before, after, grid, use_cache)
    init = block_affine(before, after, grid, coarse, use_cache) if coarse.ok else None
    if not coarse.ok:
        log.warning("coarse registration unreliable; continuing with best guess (will be flagged)")
    reader = read_tiled if tiled else (lambda img, g, uc: read_cached(img, g, uc))
    b, bv = reader(before, grid, use_cache)
    if progress:
        progress(0.5)
    a, av = reader(after, shift_grid(grid, coarse.dx_m, coarse.dy_m), use_cache)
    fine = fine_register(b, bv, a, av, grid.res, init=init)
    if init is not None:
        fine.diagnostics.warnings.append(f"initialised with block affine {np.round(init, 4).tolist()}")
    d = fine.diagnostics
    d.coarse_dx_m, d.coarse_dy_m, d.coarse_peak = coarse.dx_m, coarse.dy_m, coarse.peak
    if not coarse.ok:
        d.warnings.append("coarse offset search did not find a distinct correlation peak")
        d.quality *= 0.5
    log.info(f"fine registration: matched {d.n_matched}/{d.n_patches}, inliers {d.n_inliers}, "
             f"checkpoint RMS {d.check_rms_px:.2f}px ({d.checkpoints} pts), NCC {d.ncc_before:.2f}->{d.ncc_after:.2f}, "
             f"quality {d.quality:.2f} [{d.status}]")
    return AlignedPair(grid, b, bv, fine.warped, fine.warped_valid, a, coarse, fine)
