"""Method B — feature-based change characterisation.

For each Method-A component (and for independent small-blob detections) we
compute interpretable morphological / textural measurements:

* **crater template response** — correlation with a bowl-crater shading model
  (shadowed wall toward the sun, lit wall away), searched over 8 orientations,
  in the after vs before image; plus whether the best orientation agrees with
  the predicted solar azimuth.
* **radial structure** — angular coverage and ray contrast of darkening
  around the centroid (blast zones are radially symmetric / rayed).
* **elongation & taper** — slope-streak morphology (long, narrow, widening
  downslope).
* **texture change** — gradient-energy ratio and LBP histogram distance.
* **new edges** — fraction of after-image edges absent in the before image.
* **relief & dipole tests** — illumination/parallax artifact indicators: a
  change located on high-relief terrain that is paired with an adjacent
  opposite-polarity change is the signature of shifted shadows, not a surface
  change.
* **residual displacement** — small-patch NCC shift after registration;
  coherent sub-metre motion over rippled terrain indicates bedform migration.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from skimage.feature import blob_log, local_binary_pattern

from ..registration import highpass, match_template


def crater_template(radius_px: float, angle_rad: float) -> np.ndarray:
    r = max(1.5, radius_px)
    n = int(math.ceil(r * 2.6)) | 1
    c = n // 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) - c
    rr = np.sqrt(xx ** 2 + yy ** 2)
    ux, uy = math.cos(angle_rad), math.sin(angle_rad)
    proj = (xx * ux + yy * uy) / r
    t = np.zeros((n, n), np.float32)
    inside = rr <= r
    t[inside] = -proj[inside]           # toward the sun (proj>0): dark; away: bright
    rim = (rr > r) & (rr <= r * 1.25)
    t[rim] = 0.3 * proj[rim]            # raised rim lit on the sun side
    t -= t.mean()
    return t


def sun_vector_angle(sub_solar_azimuth: float | None, north_azimuth: float | None) -> float | None:
    """Image-plane angle (radians, x right / y down) pointing toward the sun.

    PDS HiRISE azimuths are measured clockwise from the 3 o'clock direction of a
    north-up map-projected image (NORTH_AZIMUTH=270 means north is up), which
    matches an angle in a y-down pixel frame directly. We resample to north-up
    grids, so only the sub-solar azimuth relative to north matters.
    """
    if sub_solar_azimuth is None:
        return None
    na = north_azimuth if north_azimuth is not None else 270.0
    return math.radians((sub_solar_azimuth - na + 270.0) % 360.0)


def crater_response(img_hp: np.ndarray, rc: tuple[float, float], radii: list[float], search: int = 4,
                    n_orient: int = 8) -> tuple[float, float, float]:
    """Best NCC of crater templates near rc. Returns (score, radius_px, angle_rad)."""
    best = (-1.0, 0.0, 0.0)
    r0, c0 = int(round(rc[0])), int(round(rc[1]))
    h, w = img_hp.shape
    for rad in radii:
        for k in range(n_orient):
            ang = 2 * math.pi * k / n_orient
            t = crater_template(rad, ang)
            n = t.shape[0]
            y0, x0 = r0 - n // 2 - search, c0 - n // 2 - search
            y1, x1 = y0 + n + 2 * search, x0 + n + 2 * search
            if y0 < 0 or x0 < 0 or y1 > h or x1 > w:
                continue
            s = img_hp[y0:y1, x0:x1]
            if s.std() < 1e-6:
                continue
            res = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
            v = float(res.max())
            if v > best[0]:
                best = (v, rad, ang)
    return best


def radial_structure(z: np.ndarray, rc: tuple[float, float], radius_px: float, n_bins: int = 36) -> dict:
    h, w = z.shape
    R = int(max(6, radius_px))
    r0, c0 = int(rc[0]), int(rc[1])
    y0, y1, x0, x1 = max(0, r0 - R), min(h, r0 + R + 1), max(0, c0 - R), min(w, c0 + R + 1)
    sub = z[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dy, dx = yy - rc[0], xx - rc[1]
    rr = np.sqrt(dx ** 2 + dy ** 2)
    ann = (rr > 0.15 * R) & (rr <= R)
    if ann.sum() < n_bins:
        return {"angular_coverage": 0.0, "ray_contrast": 0.0, "center_dark_ratio": 0.0}
    ang = ((np.arctan2(dy, dx) + math.pi) / (2 * math.pi) * n_bins).astype(int) % n_bins
    vals = -sub  # darkening positive
    means = np.array([vals[ann & (ang == b)].mean() if (ann & (ang == b)).any() else 0 for b in range(n_bins)])
    coverage = float((means > 1.5).mean())
    ray_contrast = float(means.std() / (abs(means.mean()) + 1e-6))
    inner = rr <= 0.35 * R
    outer = ann & (rr > 0.6 * R)
    cdr = float(vals[inner].mean() / (vals[outer].mean() + 1e-6)) if inner.any() and outer.any() else 0.0
    return {"angular_coverage": coverage, "ray_contrast": ray_contrast, "center_dark_ratio": cdr}


def taper(mask_comp: np.ndarray, orientation_rad: float) -> float:
    """Ratio of width in the widest end-third to the narrowest end-third along the major axis (>=1)."""
    ys, xs = np.nonzero(mask_comp)
    if len(xs) < 15:
        return 1.0
    # skimage orientation: angle between row axis and major axis
    ux, uy = math.sin(orientation_rad), math.cos(orientation_rad)
    cx, cy = xs.mean(), ys.mean()
    along = (xs - cx) * ux + (ys - cy) * uy
    across = -(xs - cx) * uy + (ys - cy) * ux
    lo, hi = np.percentile(along, [33, 67])
    w1 = np.ptp(across[along <= lo]) + 1 if (along <= lo).sum() > 2 else 1
    w2 = np.ptp(across[along >= hi]) + 1 if (along >= hi).sum() > 2 else 1
    return float(max(w1, w2) / max(1, min(w1, w2)))


def texture_change(b: np.ndarray, a: np.ndarray, sl: tuple[slice, slice]) -> dict:
    bb, aa = b[sl], a[sl]
    if bb.size < 64:
        return {"grad_energy_log_ratio": 0.0, "lbp_chi2": 0.0}
    gb = cv2.Laplacian(bb, cv2.CV_32F).var()
    ga = cv2.Laplacian(aa, cv2.CV_32F).var()

    def lbp_hist(x: np.ndarray) -> np.ndarray:
        x8 = cv2.normalize(x, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        l = local_binary_pattern(x8, 8, 1, method="uniform")
        h, _ = np.histogram(l, bins=10, range=(0, 10))
        return h / max(1, h.sum())

    hb, ha = lbp_hist(bb), lbp_hist(aa)
    chi2 = float(0.5 * np.sum((hb - ha) ** 2 / (hb + ha + 1e-9)))
    return {"grad_energy_log_ratio": float(np.log((ga + 1e-12) / (gb + 1e-12))), "lbp_chi2": chi2}


def context_contrast_log_ratio(b: np.ndarray, a: np.ndarray, sl: tuple[slice, slice]) -> float:
    """log ratio of albedo-normalised fine-scale contrast (after vs before) in a context window.

    Uses the coefficient of variation of the Laplacian (std / local mean) so that a
    multiplicative albedo change (e.g. a dark blast zone) does not register, while
    haze, illumination or resolution differences (which change shading contrast) do.
    """
    bb, aa = b[sl], a[sl]
    if bb.size < 256:
        return 0.0
    cb = float(cv2.Laplacian(bb, cv2.CV_32F).std() / (abs(float(bb.mean())) + 1e-9))
    ca = float(cv2.Laplacian(aa, cv2.CV_32F).std() / (abs(float(aa.mean())) + 1e-9))
    return float(np.log((ca + 1e-12) / (cb + 1e-12)))


def new_edge_fraction(b_hp: np.ndarray, a_hp: np.ndarray, sl: tuple[slice, slice], tol_px: int = 2) -> float:
    bb, aa = b_hp[sl], a_hp[sl]
    if bb.size < 64:
        return 0.0
    to8 = lambda x: np.clip((x + 3) / 6 * 255, 0, 255).astype(np.uint8)
    eb = cv2.Canny(to8(bb), 60, 140) > 0
    ea = cv2.Canny(to8(aa), 60, 140) > 0
    if ea.sum() == 0:
        return 0.0
    ebd = cv2.dilate(eb.astype(np.uint8), np.ones((2 * tol_px + 1, 2 * tol_px + 1), np.uint8)) > 0
    return float((ea & ~ebd).sum() / ea.sum())


def relief_index(grad_b: np.ndarray, comp_mask: np.ndarray, global_median: float) -> float:
    v = grad_b[comp_mask]
    return float(np.median(v) / (global_median + 1e-12)) if v.size else 0.0


def dipole_score(comp: dict, comps: list[dict], res_m: float) -> float:
    """Strength of an adjacent opposite-polarity component (0 = none, 1 = equally strong & adjacent)."""
    if comp["polarity"] == "mixed":
        return 0.6
    r0, c0 = comp["centroid_rc"]
    size = max(comp["eq_diameter_m"] / res_m, 4)
    best = 0.0
    for o in comps:
        if o is comp or o["polarity"] == comp["polarity"] or o["polarity"] == "mixed":
            continue
        r1, c1 = o["centroid_rc"]
        d = math.hypot(r1 - r0, c1 - c0)
        reach = 1.5 * (size + max(o["eq_diameter_m"] / res_m, 4)) / 2 + 6
        if d <= reach:
            ratio = min(o["area_px"], comp["area_px"]) / max(o["area_px"], comp["area_px"])
            best = max(best, 0.4 + 0.6 * ratio)
    return best


def residual_displacement(b_hp: np.ndarray, a_hp: np.ndarray, sl: tuple[slice, slice], patch: int = 32,
                          search: int = 6) -> dict:
    """Median local shift (px) of small patches inside a region after registration."""
    bb, aa = b_hp[sl], a_hp[sl]
    h, w = bb.shape
    shifts = []
    for y in range(search, h - patch - search, patch):
        for x in range(search, w - patch - search, patch):
            t = bb[y:y + patch, x:x + patch]
            if t.std() < 0.5:
                continue
            s = aa[y - search:y + patch + search, x - search:x + patch + search]
            mx, my, peak, dist = match_template(s, t)
            if peak > 0.4:
                shifts.append((mx - search, my - search, peak))
    if not shifts:
        return {"disp_median_px": 0.0, "disp_coherence": 0.0, "disp_n": 0}
    s = np.array(shifts)
    mag = np.hypot(s[:, 0], s[:, 1])
    mean_vec = np.hypot(s[:, 0].mean(), s[:, 1].mean())
    return {"disp_median_px": float(np.median(mag)), "disp_coherence": float(mean_vec / (mag.mean() + 1e-9)),
            "disp_n": int(len(s))}


def small_blobs(z: np.ndarray, mask: np.ndarray, res_m: float, min_d_m: float = 1.0, max_d_m: float = 20.0,
                thresh: float = 0.25) -> list[tuple[float, float, float]]:
    """LoG blobs on the darkening z-map: candidate crater centres. Returns (row, col, diameter_m)."""
    img = np.clip(-z / 10.0, 0, 1) * mask
    smin = max(1.0, min_d_m / res_m / 2.83)
    smax = max(smin + 1, max_d_m / res_m / 2.83)
    blobs = blob_log(img, min_sigma=smin, max_sigma=smax, num_sigma=6, threshold=thresh)
    return [(float(r), float(c), float(s * 2.83 * res_m)) for r, c, s in blobs]
