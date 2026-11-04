"""Image registration for multi-temporal HiRISE pairs, with diagnostics.

USGS HiRISE COGs use a-priori (uncontrolled) SPICE pointing; absolute errors of
~100 m (sometimes several hundred) are expected, plus spacecraft jitter and
parallax from differing emission angles over relief. Registration therefore runs
in three stages:

1. **Coarse** — normalised cross-correlation (NCC) of high-pass filtered images
   at a coarse resolution over a large search window -> global translation (m).
   The caller re-reads the moving image with the grid shifted by that offset.
2. **Fine** — dense grid of local patch matches (NCC with sub-pixel peak fit);
   RANSAC affine fit; robust smooth residual field -> dense displacement map
   applied with ``cv2.remap``.
3. **Diagnostics** — displacement re-measured on *held-out* check patches
   (offset grid, never used for fitting) after warping; RMS / P90 residuals,
   match fraction, NCC gain, and a per-pixel local quality map used to veto
   detections in poorly registered areas.

A detection is never trusted where local registration is poor; see
``detect.fuse`` for how this map is used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import cv2
import numpy as np
from scipy import ndimage as ndi


def highpass(img: np.ndarray, valid: np.ndarray | None = None, sigma: float = 6.0) -> np.ndarray:
    """Zero-mean, unit-variance high-pass image (removes albedo/illumination gradients)."""
    a = img.astype(np.float32)
    if valid is not None:
        fill = float(np.median(a[valid])) if valid.any() else 0.0
        a = np.where(valid, a, fill)
    lp = cv2.GaussianBlur(a, (0, 0), sigma)
    hp = a - lp
    m = valid if valid is not None else np.ones_like(hp, bool)
    s = float(hp[m].std()) if m.any() else 1.0
    hp = hp / (s + 1e-9)
    hp[~m] = 0
    return np.clip(hp, -5, 5).astype(np.float32)


def _subpixel_peak(res: np.ndarray, loc: tuple[int, int]) -> tuple[float, float]:
    x, y = loc
    dx = dy = 0.0
    if 0 < x < res.shape[1] - 1:
        l, c, r = res[y, x - 1], res[y, x], res[y, x + 1]
        den = l - 2 * c + r
        dx = 0.5 * (l - r) / den if abs(den) > 1e-9 else 0.0
    if 0 < y < res.shape[0] - 1:
        u, c, d = res[y - 1, x], res[y, x], res[y + 1, x]
        den = u - 2 * c + d
        dy = 0.5 * (u - d) / den if abs(den) > 1e-9 else 0.0
    return x + float(np.clip(dx, -1, 1)), y + float(np.clip(dy, -1, 1))


def match_template(search: np.ndarray, templ: np.ndarray, excl: int = 3) -> tuple[float, float, float, float]:
    """NCC match. Returns (x, y, peak, distinctiveness) where x,y is the top-left of the match."""
    res = cv2.matchTemplate(search, templ, cv2.TM_CCOEFF_NORMED)
    _, peak, _, loc = cv2.minMaxLoc(res)
    x, y = _subpixel_peak(res, loc)
    r2 = res.copy()
    x0, y0 = loc
    r2[max(0, y0 - excl):y0 + excl + 1, max(0, x0 - excl):x0 + excl + 1] = -1
    second = float(r2.max()) if r2.size > (2 * excl + 1) ** 2 else -1.0
    return x, y, float(peak), float(peak - second)


@dataclass
class CoarseResult:
    dx_m: float
    dy_m: float
    peak: float
    distinct: float
    res_m: float
    ok: bool


def coarse_offset(ref: np.ndarray, ref_valid: np.ndarray, mov: np.ndarray, mov_valid: np.ndarray,
                  res_m: float, max_shift_m: float, sigmas: tuple[float, ...] = (4.0, 12.0)) -> CoarseResult:
    """Best of several band-pass scales (fine texture vs. broad dust-mantled relief), by peak distinctness."""
    best: CoarseResult | None = None
    for sg in sigmas:
        c = _coarse_offset_sigma(ref, ref_valid, mov, mov_valid, res_m, max_shift_m, sg)
        if best is None or (c.ok, c.distinct) > (best.ok, best.distinct):
            best = c
    assert best is not None
    return best


def _coarse_offset_sigma(ref: np.ndarray, ref_valid: np.ndarray, mov: np.ndarray, mov_valid: np.ndarray,
                         res_m: float, max_shift_m: float, sigma: float) -> CoarseResult:
    """Translation of ``mov`` relative to ``ref`` (both on the same grid, same size).

    Returns the offset (dx_m, dy_m) in map metres (x east, y north) such that the
    ground point at ref pixel p appears in mov at p + (dx, -dy)/res.
    """
    h, w = ref.shape
    m = int(round(max_shift_m / res_m))
    m = min(m, h // 3, w // 3)
    rh = highpass(ref, ref_valid, sigma=sigma)
    mh = highpass(mov, mov_valid, sigma=sigma)
    templ = rh[m:h - m, m:w - m]
    if templ.size == 0 or float(np.abs(templ).sum()) == 0:
        return CoarseResult(0, 0, 0, 0, res_m, False)
    x, y, peak, distinct = match_template(mh, templ)
    sx, sy = x - m, y - m  # pixel shift of the ref-centre content inside mov
    return CoarseResult(dx_m=sx * res_m, dy_m=-sy * res_m, peak=peak, distinct=distinct, res_m=res_m,
                        ok=bool(peak > 0.15 and distinct > 0.02))


@dataclass
class RegistrationDiagnostics:
    coarse_dx_m: float = 0.0
    coarse_dy_m: float = 0.0
    coarse_peak: float = 0.0
    n_patches: int = 0
    n_matched: int = 0
    n_inliers: int = 0
    match_fraction: float = 0.0
    affine: list[list[float]] = field(default_factory=list)
    fit_rms_px: float = 0.0
    checkpoints: int = 0
    check_rms_px: float = float("nan")
    check_p90_px: float = float("nan")
    check_rms_m: float = float("nan")
    ncc_before: float = 0.0
    ncc_after: float = 0.0
    quality: float = 0.0
    status: str = "unknown"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float) and not np.isfinite(v):
                d[k] = None
        return d


def _patch_grid(h: int, w: int, patch: int, step: int, offset: int = 0) -> list[tuple[int, int]]:
    half = patch // 2
    ys = range(half + offset, h - half, step)
    xs = range(half + offset, w - half, step)
    return [(x, y) for y in ys for x in xs]


def measure_shifts(ref_hp: np.ndarray, mov_hp: np.ndarray, valid: np.ndarray, centers: list[tuple[int, int]],
                   patch: int, search: int, min_peak: float = 0.35,
                   min_texture: float = 0.3, init: np.ndarray | None = None) -> np.ndarray:
    """For each centre: (x, y, ux, uy, peak, distinct, ok). u = where ref content lies in mov minus centre.

    ``init`` (2x3 affine, ref px -> mov px) centres each search window on a predicted position, so
    large attitude-induced rotations/shears over long strips stay within the search range.
    """
    out = []
    half = patch // 2
    h, w = ref_hp.shape
    for (cx, cy) in centers:
        if init is not None:
            px = init[0, 0] * cx + init[0, 1] * cy + init[0, 2]
            py = init[1, 0] * cx + init[1, 1] * cy + init[1, 2]
            d0x, d0y = int(round(px - cx)), int(round(py - cy))
        else:
            d0x = d0y = 0
        y0, y1, x0, x1 = cy - half, cy + half, cx - half, cx + half
        if not valid[y0:y1, x0:x1].mean() > 0.95:
            out.append((cx, cy, 0, 0, 0, 0, 0))
            continue
        t = ref_hp[y0:y1, x0:x1]
        if t.std() < min_texture:  # featureless patch: matching unreliable
            out.append((cx, cy, 0, 0, 0, 0, 0))
            continue
        sy0, sy1 = max(0, y0 + d0y - search), min(h, y1 + d0y + search)
        sx0, sx1 = max(0, x0 + d0x - search), min(w, x1 + d0x + search)
        s = mov_hp[sy0:sy1, sx0:sx1] if sy1 > sy0 and sx1 > sx0 else np.zeros((0, 0), np.float32)
        if s.shape[0] < t.shape[0] or s.shape[1] < t.shape[1]:
            out.append((cx, cy, 0, 0, 0, 0, 0))
            continue
        x, y, peak, distinct = match_template(s, t)
        ux = sx0 + x - x0
        uy = sy0 + y - y0
        ok = (peak >= min_peak and distinct > 0.03 and abs(ux - d0x) < search - 1 and abs(uy - d0y) < search - 1)
        out.append((cx, cy, ux, uy, peak, distinct, float(ok)))
    return np.array(out, dtype=np.float64).reshape(-1, 7)


def _smooth_field(pts: np.ndarray, vals: np.ndarray, shape: tuple[int, int], step: int) -> np.ndarray:
    """Interpolate scattered residual displacements onto a dense grid (coarse grid + bilinear upsample)."""
    from scipy.interpolate import griddata

    h, w = shape
    gy = np.arange(0, h + step, step)
    gx = np.arange(0, w + step, step)
    GX, GY = np.meshgrid(gx, gy)
    if len(pts) < 4:
        return np.zeros(shape, np.float32)
    lin = griddata(pts, vals, (GX, GY), method="linear")
    near = griddata(pts, vals, (GX, GY), method="nearest")
    f = np.where(np.isfinite(lin), lin, near)
    f = ndi.gaussian_filter(f, 1.0)
    # grid node k sits at pixel k*step; cv2.resize places node k at output index (k+0.5)*step-0.5,
    # so the value for pixel p is found at output index p + step/2.
    up = cv2.resize(f.astype(np.float32), (len(gx) * step, len(gy) * step), interpolation=cv2.INTER_LINEAR)
    sh = step // 2
    return up[sh:sh + h, sh:sh + w]


def _ncc(a: np.ndarray, b: np.ndarray, m: np.ndarray) -> float:
    if m.sum() < 100:
        return 0.0
    x, y = a[m], b[m]
    x = x - x.mean()
    y = y - y.mean()
    return float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-9))


@dataclass
class FineResult:
    warped: np.ndarray
    warped_valid: np.ndarray
    flow_x: np.ndarray
    flow_y: np.ndarray
    quality_map: np.ndarray
    diagnostics: RegistrationDiagnostics
    matches: np.ndarray
    checks: np.ndarray


def fine_register(ref: np.ndarray, ref_valid: np.ndarray, mov: np.ndarray, mov_valid: np.ndarray,
                  res_m: float, patch: int = 96, step: int = 64, search: int = 24, hp_sigma: float = 6.0,
                  adaptive: bool = True, init: np.ndarray | None = None) -> FineResult:
    """Dense local registration of mov onto ref (same grid). See module docstring.

    With ``adaptive``, a second configuration (larger patches, coarser band-pass) is tried when the
    first is not 'good' — smooth dust-mantled terrain carries most of its signal at larger scales —
    and the result with the better held-out checkpoint quality is kept.
    """
    r1 = _fine_register(ref, ref_valid, mov, mov_valid, res_m, patch, step, search, hp_sigma, init)
    if not adaptive or r1.diagnostics.status == "good":
        return r1
    r2 = _fine_register(ref, ref_valid, mov, mov_valid, res_m, int(patch * 5 / 3), int(step * 1.5), search, hp_sigma * 2, init)
    best = r2 if r2.diagnostics.quality > r1.diagnostics.quality else r1
    best.diagnostics.warnings.append(
        f"adaptive registration: config A quality {r1.diagnostics.quality:.2f}, config B (larger patches, "
        f"σ={hp_sigma * 2:.0f}) quality {r2.diagnostics.quality:.2f}; kept {'B' if best is r2 else 'A'}")
    return best


def _fine_register(ref: np.ndarray, ref_valid: np.ndarray, mov: np.ndarray, mov_valid: np.ndarray,
                   res_m: float, patch: int, step: int, search: int, hp_sigma: float,
                   init: np.ndarray | None = None) -> FineResult:
    h, w = ref.shape
    diag = RegistrationDiagnostics()
    valid = ref_valid & mov_valid
    rh = highpass(ref, ref_valid, hp_sigma)
    mh = highpass(mov, mov_valid, hp_sigma)
    vmask = ndi.binary_erosion(valid, iterations=2)
    diag.ncc_before = _ncc(rh, mh, vmask)

    centers = _patch_grid(h, w, patch, step)
    m = measure_shifts(rh, mh, valid, centers, patch, search, init=init)
    diag.n_patches = len(centers)
    good = m[m[:, 6] > 0] if len(m) else m
    diag.n_matched = len(good)
    diag.match_fraction = len(good) / max(1, int((m[:, 4] != 0).sum() + (m[:, 6] == 0).sum()))
    flow_x = np.zeros((h, w), np.float32)
    flow_y = np.zeros((h, w), np.float32)
    if len(good) >= 6:
        src = good[:, :2].astype(np.float32)
        dst = (good[:, :2] + good[:, 2:4]).astype(np.float32)
        A, inl = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0,
                                      maxIters=4000, confidence=0.995)
        if A is not None:
            inl = inl.ravel().astype(bool)
            diag.n_inliers = int(inl.sum())
            diag.affine = A.tolist()
            pred = (A[:, :2] @ src.T).T + A[:, 2]
            resid = dst - pred
            diag.fit_rms_px = float(np.sqrt((resid[inl] ** 2).sum(1).mean()))
            # dense affine displacement
            YY, XX = np.mgrid[0:h, 0:w].astype(np.float32)
            ax = A[0, 0] * XX + A[0, 1] * YY + A[0, 2] - XX
            ay = A[1, 0] * XX + A[1, 1] * YY + A[1, 2] - YY
            # smooth residual field from inliers (jitter / parallax)
            if inl.sum() >= 8:
                rx = _smooth_field(src[inl], resid[inl, 0], (h, w), step)
                ry = _smooth_field(src[inl], resid[inl, 1], (h, w), step)
            else:
                rx = ry = np.zeros((h, w), np.float32)
            flow_x = (ax + rx).astype(np.float32)
            flow_y = (ay + ry).astype(np.float32)
        else:
            diag.warnings.append("affine RANSAC failed")
    else:
        diag.warnings.append(f"only {len(good)} reliable patch matches; using coarse alignment only")

    YY, XX = np.mgrid[0:h, 0:w].astype(np.float32)
    warped = cv2.remap(mov.astype(np.float32), XX + flow_x, YY + flow_y, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    wv = cv2.remap(mov_valid.astype(np.uint8), XX + flow_x, YY + flow_y, cv2.INTER_NEAREST,
                   borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)

    # --- held-out checkpoints: offset grid, never used in fitting -----------------
    wh = highpass(warped, wv, hp_sigma)
    checks_c = _patch_grid(h, w, patch, step, offset=step // 2)
    cm = measure_shifts(rh, wh, ref_valid & wv, checks_c, patch, max(6, search // 3))
    cgood = cm[cm[:, 6] > 0] if len(cm) else cm
    diag.checkpoints = len(cgood)
    if len(cgood):
        r = np.sqrt(cgood[:, 2] ** 2 + cgood[:, 3] ** 2)
        diag.check_rms_px = float(np.sqrt((r ** 2).mean()))
        diag.check_p90_px = float(np.percentile(r, 90))
        diag.check_rms_m = diag.check_rms_px * res_m
    vm2 = ndi.binary_erosion(ref_valid & wv, iterations=2)
    diag.ncc_after = _ncc(rh, wh, vm2)

    # --- local quality map: residual & match confidence at checkpoints ------------
    qmap = np.zeros((h, w), np.float32)
    if len(cm):
        qual = np.where(cm[:, 6] > 0, np.exp(-np.sqrt(cm[:, 2] ** 2 + cm[:, 3] ** 2) / 1.0) * np.clip(cm[:, 4] / 0.6, 0, 1), 0.0)
        qmap = _smooth_field(cm[:, :2], qual, (h, w), step)
        qmap = np.clip(qmap, 0, 1)
    qmap[~(ref_valid & wv)] = 0

    # --- overall quality ----------------------------------------------------------
    if diag.checkpoints >= 3 and np.isfinite(diag.check_rms_px):
        q = np.exp(-diag.check_rms_px / 1.5) * min(1.0, diag.checkpoints / max(4, 0.3 * len(checks_c)))
        q *= float(np.clip((diag.ncc_after + 0.1) / 0.5, 0, 1))
        diag.quality = float(np.clip(q, 0, 1))
    else:
        diag.quality = 0.0
        diag.warnings.append("too few checkpoints to verify registration")
    diag.status = "good" if diag.quality >= 0.5 else ("marginal" if diag.quality >= 0.2 else "poor")
    if diag.check_rms_px > 1.5:
        diag.warnings.append(f"checkpoint RMS {diag.check_rms_px:.2f} px exceeds 1.5 px")
    return FineResult(warped, wv, flow_x, flow_y, qmap, diag, m, cm)
