"""Method A — classical change detection.

Pipeline: radiometrically matched difference -> registration-aware noise model
-> multi-scale z-score -> SSIM -> hysteresis (adaptive) thresholding ->
morphological filtering -> connected components with shape statistics.

Registration-aware noise model
------------------------------
A residual misregistration of ``r`` pixels produces a difference of roughly
``|∇I|·r`` wherever the image has gradient ``∇I``. The expected difference
standard deviation per pixel is therefore modelled as

    σ²(x) = σ_n² + (r · max(|∇B|, |∇A|))²

where σ_n is the robust noise level (MAD of the difference in low-gradient
terrain) and ``r`` the measured checkpoint residual (floored at 0.5 px).
Bright crater rims or boulder edges with small residual misalignment therefore
do not produce high z-scores, while albedo changes on smooth terrain do.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.filters import apply_hysteresis_threshold
from skimage.measure import label, regionprops
from skimage.metrics import structural_similarity


@dataclass
class ClassicalParams:
    scales_px: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)
    z_low: float = 3.5
    z_high: float = 6.0
    min_area_px: int = 6
    group_dilate_px: int = 4
    min_reg_quality: float = 0.15
    edge_margin_px: int = 12
    residual_floor_px: float = 0.5


@dataclass
class ClassicalResult:
    diff: np.ndarray
    z: np.ndarray
    ssim: np.ndarray
    mask: np.ndarray
    labels: np.ndarray
    components: list[dict]
    noise_sigma: float
    analysis_mask: np.ndarray
    params: dict = field(default_factory=dict)


def gradient_mag(img: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return np.sqrt(gx * gx + gy * gy)


def robust_sigma(x: np.ndarray) -> float:
    if x.size == 0:
        return 1.0
    return float(np.median(np.abs(x - np.median(x))) * 1.4826 + 1e-12)


def analysis_mask(valid: np.ndarray, qmap: np.ndarray | None, p: ClassicalParams) -> np.ndarray:
    m = ndi.binary_erosion(valid, iterations=p.edge_margin_px, border_value=0)
    if qmap is not None:
        m &= qmap >= p.min_reg_quality
    return m


def compute_z(before_m: np.ndarray, after: np.ndarray, mask: np.ndarray, residual_px: float,
              p: ClassicalParams) -> tuple[np.ndarray, np.ndarray, float]:
    diff = np.where(mask, after - before_m, 0).astype(np.float32)
    grad = np.maximum(gradient_mag(before_m), gradient_mag(after))
    low_grad = mask & (grad < np.percentile(grad[mask], 40)) if mask.any() else mask
    sn = robust_sigma(diff[low_grad]) if low_grad.sum() > 100 else robust_sigma(diff[mask])
    r = max(residual_px, p.residual_floor_px)
    zs = []
    for s in p.scales_px:
        d = cv2.GaussianBlur(diff, (0, 0), s) if s > 0 else diff
        g = cv2.GaussianBlur(grad, (0, 0), s) if s > 0 else grad
        # empirical noise of the smoothed difference (accounts for spatially correlated noise)
        sn_s = robust_sigma(d[low_grad]) if low_grad.sum() > 100 else sn
        sig = np.sqrt(sn_s ** 2 + (r * g / max(1.0, s)) ** 2)
        zs.append(d / (sig + 1e-12))
    zstack = np.stack(zs)
    idx = np.argmax(np.abs(zstack), axis=0)
    z = np.take_along_axis(zstack, idx[None], 0)[0]
    z[~mask] = 0
    return diff, z.astype(np.float32), sn


def ssim_map(before_m: np.ndarray, after: np.ndarray, mask: np.ndarray) -> np.ndarray:
    v = np.concatenate([before_m[mask], after[mask]]) if mask.any() else np.array([0.0, 1.0])
    rng = float(np.percentile(v, 99.5) - np.percentile(v, 0.5)) or 1.0
    _, S = structural_similarity(before_m, after, data_range=rng, gaussian_weights=True, sigma=2.0,
                                 use_sample_covariance=False, full=True)
    S = S.astype(np.float32)
    S[~mask] = 1.0
    return S


def component_stats(lbl: np.ndarray, z: np.ndarray, ssim: np.ndarray, diff: np.ndarray, res_m: float) -> list[dict]:
    comps = []
    for rp in regionprops(lbl, intensity_image=z):
        coords = rp.coords
        zz = z[coords[:, 0], coords[:, 1]]
        ss = ssim[coords[:, 0], coords[:, 1]]
        dd = diff[coords[:, 0], coords[:, 1]]
        neg = (zz < 0).mean()
        maj = max(rp.axis_major_length, 1.0)
        mnr = max(rp.axis_minor_length, 1.0)
        comps.append({
            "label": int(rp.label),
            "area_px": int(rp.area),
            "area_m2": float(rp.area * res_m * res_m),
            "eq_diameter_m": float(rp.equivalent_diameter_area * res_m),
            "centroid_rc": [float(rp.centroid[0]), float(rp.centroid[1])],
            "bbox": [int(b) for b in rp.bbox],  # minr, minc, maxr, maxc
            "polarity": "darkening" if neg >= 0.6 else ("brightening" if neg <= 0.4 else "mixed"),
            "frac_dark": float(neg),
            "mean_abs_z": float(np.abs(zz).mean()),
            "max_abs_z": float(np.abs(zz).max()),
            "mean_diff": float(dd.mean()),
            "mean_ssim": float(ss.mean()),
            "eccentricity": float(rp.eccentricity),
            "elongation": float(maj / mnr),
            "major_axis_m": float(maj * res_m),
            "minor_axis_m": float(mnr * res_m),
            "orientation_deg": float(np.degrees(rp.orientation)),
            "solidity": float(rp.solidity),
            "extent": float(rp.extent),
        })
    return comps


def detect(before_m: np.ndarray, after: np.ndarray, valid: np.ndarray, qmap: np.ndarray | None,
           res_m: float, residual_px: float, p: ClassicalParams | None = None) -> ClassicalResult:
    p = p or ClassicalParams()
    am = analysis_mask(valid, qmap, p)
    diff, z, sn = compute_z(before_m, after, am, residual_px, p)
    S = ssim_map(before_m, after, am)
    absz = np.abs(z)
    dark = apply_hysteresis_threshold(np.where(z < 0, absz, 0), p.z_low, p.z_high)
    bright = apply_hysteresis_threshold(np.where(z > 0, absz, 0), p.z_low, p.z_high)
    mask = (dark | bright) & am
    mask = ndi.binary_opening(mask, structure=np.ones((2, 2)))
    mask = ndi.binary_fill_holes(ndi.binary_closing(mask, iterations=1)) & am
    # group nearby fragments (e.g. a blast zone broken into rays) into one candidate
    grouped = label(ndi.binary_dilation(mask, iterations=p.group_dilate_px))
    lbl = np.where(mask, grouped, 0)
    sizes = np.bincount(lbl.ravel())
    small = sizes < p.min_area_px
    small[0] = False
    lbl[small[lbl]] = 0
    comps = component_stats(lbl, z, S, diff, res_m)
    return ClassicalResult(diff, z, S, lbl > 0, lbl, comps, sn, am, p.__dict__.copy())
