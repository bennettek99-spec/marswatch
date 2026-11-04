"""Radiometric normalisation between two registered observations.

Atmospheric opacity, season, photometric angles and calibration differ between
observations: I/F of the same terrain can differ by a factor of two (e.g.
0.21 vs 0.11 in our first test pair). We model the after image as a smoothly
varying linear function of the before image, ``A ≈ g(x)·B + o(x)``, fitted by
iteratively trimmed least squares in large blocks so that genuine changes
(which occupy a small fraction of each block) are rejected as outliers instead
of being absorbed by the fit.
"""
from __future__ import annotations

import cv2
import numpy as np


def _trimmed_fit(b: np.ndarray, a: np.ndarray, iters: int = 4, k: float = 2.5) -> tuple[float, float, float]:
    keep = np.ones(b.size, bool)
    g, o = 1.0, 0.0
    for _ in range(iters):
        if keep.sum() < 20:
            break
        bb, aa = b[keep], a[keep]
        vb = bb.var()
        if vb < 1e-12:
            g, o = 1.0, float(np.median(aa - bb))
        else:
            g = float(((bb - bb.mean()) * (aa - aa.mean())).mean() / vb)
            g = float(np.clip(g, 0.2, 5.0))
            o = float(aa.mean() - g * bb.mean())
        r = a - (g * b + o)
        mad = float(np.median(np.abs(r[keep] - np.median(r[keep])))) * 1.4826 + 1e-9
        keep = np.abs(r) < k * mad
    return g, o, float(keep.mean())


def radiometric_match(before: np.ndarray, after: np.ndarray, valid: np.ndarray,
                      block_px: int = 1024, sample_step: int = 4, smooth_px: float = 8.0) -> tuple[np.ndarray, dict]:
    """Return ``before`` mapped into the radiometry of ``after`` and fit diagnostics.

    Pixels are first lightly smoothed and subsampled to make the fit robust to
    noise and residual misregistration.
    """
    h, w = before.shape
    bs = cv2.GaussianBlur(before, (0, 0), 1.5)
    as_ = cv2.GaussianBlur(after, (0, 0), 1.5)
    ny = max(1, int(round(h / block_px)))
    nx = max(1, int(round(w / block_px)))
    G = np.ones((ny, nx), np.float32)
    O = np.zeros((ny, nx), np.float32)
    inl = np.zeros((ny, nx), np.float32)
    gg, go, gi = _trimmed_fit(bs[valid][::sample_step * sample_step], as_[valid][::sample_step * sample_step])
    for j in range(ny):
        for i in range(nx):
            y0, y1 = j * h // ny, (j + 1) * h // ny
            x0, x1 = i * w // nx, (i + 1) * w // nx
            v = valid[y0:y1:sample_step, x0:x1:sample_step]
            if v.sum() < 200:
                G[j, i], O[j, i], inl[j, i] = gg, go, 0
                continue
            b = bs[y0:y1:sample_step, x0:x1:sample_step][v]
            a = as_[y0:y1:sample_step, x0:x1:sample_step][v]
            G[j, i], O[j, i], inl[j, i] = _trimmed_fit(b, a)
    if ny * nx > 1:
        Gm = cv2.resize(G, (w, h), interpolation=cv2.INTER_LINEAR)
        Om = cv2.resize(O, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        Gm = np.full((h, w), G[0, 0], np.float32)
        Om = np.full((h, w), O[0, 0], np.float32)
    matched = np.where(valid, Gm * before + Om, 0).astype(np.float32)
    info = {
        "global_gain": gg, "global_offset": go, "global_inlier_frac": gi,
        "blocks": [ny, nx], "gain_range": [float(G.min()), float(G.max())],
        "offset_range": [float(O.min()), float(O.max())], "mean_inlier_frac": float(inl.mean()),
    }
    return matched, info


def to_display(img: np.ndarray, valid: np.ndarray, lo_p: float = 0.5, hi_p: float = 99.5,
               ref: tuple[float, float] | None = None) -> tuple[np.ndarray, tuple[float, float]]:
    """8-bit display stretch; pass ``ref`` to apply the same stretch to a second image."""
    if ref is None:
        vals = img[valid] if valid.any() else img.ravel()
        lo, hi = (float(np.percentile(vals, lo_p)), float(np.percentile(vals, hi_p))) if vals.size else (0.0, 1.0)
    else:
        lo, hi = ref
    out = np.clip((img - lo) / max(hi - lo, 1e-9) * 255, 0, 255).astype(np.uint8)
    out[~valid] = 0
    return out, (lo, hi)
