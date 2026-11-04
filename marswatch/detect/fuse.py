"""Candidate fusion, categorisation, heuristic scoring and status classification.

IMPORTANT: the score produced here is an explicitly *heuristic* ranking value
in [0, 1]. It is not a calibrated probability. Its behaviour on documented
changes and controls is measured by ``marswatch.validation``; see
docs/VALIDATION.md for the measured precision/recall at various cut-offs.

Status classes (never "confirmed discovery"):

* ``known_documented``    — coincides with a catalogued change (e.g. Daubar et al. 2022)
* ``plausible_unverified`` — passes artifact tests with adequate evidence
* ``likely_artifact``     — artifact indicators dominate
* ``insufficient_evidence`` — too small/weak/poorly registered to judge
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .classical import ClassicalResult, gradient_mag
from .features import (
    context_contrast_log_ratio,
    crater_response,
    dipole_score,
    new_edge_fraction,
    radial_structure,
    relief_index,
    residual_displacement,
    small_blobs,
    sun_vector_angle,
    taper,
    texture_change,
)
from ..registration import highpass

CATEGORIES = [
    "new_impact_crater",
    "slope_streak",
    "dune_bedform_change",
    "rockfall_or_boulder_track",
    "seasonal_frost_or_albedo",
    "illumination_or_registration_artifact",
    "other_change",
]


@dataclass
class FusionContext:
    res_m: float
    center_lat: float
    d_incidence: float
    d_ls: float
    d_sun_azimuth: float
    sun_angle_after: float | None
    sun_angle_before: float | None
    reg_quality: float
    reg_rms_px: float
    low_snr: bool = False
    dust_storm: bool = False


def shadow_mask(img: np.ndarray, valid: np.ndarray, k: float = 2.5) -> np.ndarray:
    """Cast-shadow pixels: much darker than the robust scene level (after radiometric matching)."""
    v = img[valid]
    if v.size < 100:
        return np.zeros_like(valid)
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med))) * 1.4826 + 1e-12
    return valid & (img < med - k * mad) & (img < 0.7 * med)


def _sl(bbox: list[int], pad: int, shape: tuple[int, int]) -> tuple[slice, slice]:
    r0, c0, r1, c1 = bbox
    return (slice(max(0, r0 - pad), min(shape[0], r1 + pad)), slice(max(0, c0 - pad), min(shape[1], c1 + pad)))


def _ang_diff(a: float, b: float) -> float:
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def characterise(before_m: np.ndarray, after: np.ndarray, cr: ClassicalResult, qmap: np.ndarray,
                 ctx: FusionContext, max_candidates: int = 300) -> list[dict]:
    """Compute Method-B features for each component and fuse into scored candidates."""
    res = ctx.res_m
    shape = after.shape
    b_hp = highpass(before_m, cr.analysis_mask, sigma=4)
    a_hp = highpass(after, cr.analysis_mask, sigma=4)
    grad_b = gradient_mag(before_m)
    gmed = float(np.median(grad_b[cr.analysis_mask])) if cr.analysis_mask.any() else 1.0
    shadow = shadow_mask(before_m, cr.analysis_mask) | shadow_mask(after, cr.analysis_mask)
    shadow_d = ndi.binary_dilation(shadow, iterations=3)
    comps = sorted(cr.components, key=lambda c: -c["max_abs_z"] * math.sqrt(c["area_px"]))[:max_candidates]
    blobs = small_blobs(cr.z, cr.analysis_mask, res)
    cands = []
    for comp in comps:
        sl = _sl(comp["bbox"], 6, shape)
        cmask = cr.labels[sl] == comp["label"]
        f: dict = {}
        rc = tuple(comp["centroid_rc"])
        # crater blob inside the component (strongest LoG darkening blob)
        r0, c0, r1, c1 = comp["bbox"]
        inside = [b for b in blobs if r0 - 2 <= b[0] <= r1 + 2 and c0 - 2 <= b[1] <= c1 + 2]
        if inside:
            bz = max(inside, key=lambda b: abs(cr.z[int(b[0]), int(b[1])]))
            f["blob_rc"] = [bz[0], bz[1]]
            f["blob_diameter_m"] = bz[2]
            center = (bz[0], bz[1])
        else:
            center = rc
        rad_px = max(1.5, min(30.0, comp["eq_diameter_m"] / res / 2))
        radii = sorted({max(1.5, r) for r in (1.5, 2.5, 4.0, 6.0, 9.0, 14.0, 20.0) if r <= max(3.0, rad_px * 1.2)})
        ca = crater_response(a_hp, center, radii)
        cb = crater_response(b_hp, center, [ca[1]] if ca[1] else radii)
        f["crater_resp_after"], f["crater_radius_m"] = ca[0], ca[1] * res
        f["crater_resp_before"] = cb[0]
        f["crater_resp_gain"] = ca[0] - cb[0]
        if ctx.sun_angle_after is not None and ca[0] > 0:
            f["crater_sun_misfit_deg"] = math.degrees(_ang_diff(ca[2], ctx.sun_angle_after))
        f.update(radial_structure(cr.z, center, max(comp["major_axis_m"] / res / 2, 8)))
        f["taper"] = taper(cmask, math.radians(comp["orientation_deg"]))
        f.update(texture_change(before_m, after, sl))
        f["new_edge_frac"] = new_edge_fraction(b_hp, a_hp, sl)
        f["relief_index"] = relief_index(grad_b[sl], cmask, gmed)
        f["dipole"] = dipole_score(comp, comps, res)
        f["shadow_frac"] = float(shadow_d[sl][cmask].mean()) if cmask.any() else 0.0
        f["contrast_log_ratio"] = context_contrast_log_ratio(before_m, after, _sl(comp["bbox"], 60, shape))
        f["local_reg_quality"] = float(qmap[int(rc[0]), int(rc[1])]) if qmap is not None else ctx.reg_quality
        f["near_mask_edge"] = bool(ndi.binary_erosion(cr.analysis_mask, iterations=20)[int(rc[0]), int(rc[1])] == 0)
        if comp["area_m2"] > 400 and comp["mean_ssim"] < 0.6:
            f.update(residual_displacement(b_hp, a_hp, sl))
        cands.append(fuse_one(comp, f, ctx))
    cands.sort(key=lambda c: -c["score"])
    return cands


def fuse_one(comp: dict, f: dict, ctx: FusionContext) -> dict:
    res = ctx.res_m
    ev_for: list[str] = []
    ev_against: list[str] = []
    methods = {"A_classical": True}
    z = comp["max_abs_z"]
    area = comp["area_m2"]
    elong = comp["elongation"]
    dark = comp["polarity"] == "darkening"
    bright = comp["polarity"] == "brightening"

    # ---- artifact indicators ---------------------------------------------------------
    art = 0.0
    illum_differs = ctx.d_incidence > 10 or ctx.d_sun_azimuth > 20
    if f["dipole"] > 0.5 and (f["relief_index"] > 1.5 or (illum_differs and f["relief_index"] > 1.0)):
        art += 0.5
        ev_against.append(f"adjacent opposite-polarity change on relief (dipole={f['dipole']:.2f}, "
                          f"relief={f['relief_index']:.1f}×median"
                          + (", illumination differs" if illum_differs else "")
                          + "): typical of shifted shadows or parallax")
    elif f["dipole"] > 0.5:
        art += 0.2
        ev_against.append(f"adjacent opposite-polarity change (dipole={f['dipole']:.2f})")
    if f.get("shadow_frac", 0) > 0.3:
        art += 0.4 if illum_differs or f["shadow_frac"] > 0.6 else 0.25
        ev_against.append(f"{f['shadow_frac'] * 100:.0f}% of the region lies on/next to cast shadows: "
                          "shadow length/position changes mimic surface change")
    gl = abs(f.get("contrast_log_ratio", 0.0))
    if gl > 1.0:
        art += 0.35 if gl > 1.6 else 0.2
        ev_against.append(f"local image contrast differs by ×{math.exp(gl):.1f} between images "
                          "(haze, illumination or resolution difference): shading differences are expected")
    if f["relief_index"] > 2.5:
        art += 0.2
        ev_against.append(f"located on steep/high-contrast relief (relief={f['relief_index']:.1f}×median)")
    if ctx.d_incidence > 10 and f["relief_index"] > 1.5:
        art += 0.15
        ev_against.append(f"incidence angles differ by {ctx.d_incidence:.0f}°: shadow lengths differ")
    if ctx.d_sun_azimuth > 30 and f["relief_index"] > 1.2:
        art += 0.15
        ev_against.append(f"sun azimuth differs by {ctx.d_sun_azimuth:.0f}°")
    if f["local_reg_quality"] < 0.3:
        art += 0.25
        ev_against.append(f"poor local registration quality ({f['local_reg_quality']:.2f})")
    if ctx.low_snr:
        art += 0.2
        ev_against.append("one image has low structure SNR (haze/dust): shading and noise differences are likely")
    if ctx.dust_storm and not ctx.low_snr:
        art += 0.15
        ev_against.append("an image was acquired during a global dust storm: haze changes shading contrast non-linearly")
    if f["near_mask_edge"]:
        art += 0.1
        ev_against.append("within 20 px of the valid-overlap boundary")
    if comp["polarity"] == "mixed":
        ev_against.append("mixed polarity (both brightening and darkening)")

    # ---- positive indicators ----------------------------------------------------------
    crater_new = f["crater_resp_after"] > 0.45 and f["crater_resp_gain"] > 0.2
    if crater_new:
        methods["B_crater_template"] = True
        msg = (f"crater-like shading appears in after image (template NCC {f['crater_resp_after']:.2f} vs "
               f"{f['crater_resp_before']:.2f} before, r≈{f['crater_radius_m']:.1f} m)")
        if "crater_sun_misfit_deg" in f:
            msg += f"; shading orientation {f['crater_sun_misfit_deg']:.0f}° from solar azimuth"
            if f["crater_sun_misfit_deg"] <= 50:
                ev_for.append(msg + " (consistent)")
            else:
                ev_against.append(msg + " (inconsistent with illumination)")
        else:
            ev_for.append(msg)
    radial = f["angular_coverage"] >= 0.6 and dark
    if radial:
        methods["B_radial"] = True
        ev_for.append(f"darkening surrounds centre in {f['angular_coverage'] * 100:.0f}% of directions (blast-zone-like)")
    if f.get("ray_contrast", 0) > 0.5 and radial:
        ev_for.append(f"angular variation suggests rays (contrast {f['ray_contrast']:.2f})")
    if "blob_rc" in f:
        methods["B_log_blob"] = True
    if f["new_edge_frac"] > 0.5:
        ev_for.append(f"{f['new_edge_frac'] * 100:.0f}% of edges in after image are new")
    if comp["mean_ssim"] < 0.5:
        ev_for.append(f"local structure changed (mean SSIM {comp['mean_ssim']:.2f})")
    ev_for.insert(0, f"{comp['polarity']} change, peak |z|={z:.1f}, area {area:.0f} m² (≈{comp['eq_diameter_m']:.1f} m)")

    # ---- category -------------------------------------------------------------------
    high_lat = abs(ctx.center_lat) > 45
    if art >= 0.5:
        cat = "illumination_or_registration_artifact"
    elif high_lat and ctx.d_ls > 20 and area > 20000:
        cat = "seasonal_frost_or_albedo"
        ev_against.append(f"high latitude with ΔLs={ctx.d_ls:.0f}°: seasonal frost/albedo change expected")
    elif (f.get("disp_median_px", 0) > 0.8 and f.get("disp_coherence", 0) > 0.6 and comp["mean_ssim"] < 0.6
          and f["dipole"] <= 0.5):
        cat = "dune_bedform_change"
        methods["B_displacement"] = True
        ev_for.append(f"coherent residual displacement {f['disp_median_px'] * res:.2f} m over textured terrain")
    elif (dark or comp["polarity"] == "mixed") and radial and elong < 4.0:
        cat = "new_impact_crater"
    elif elong >= 3.0 and comp["major_axis_m"] >= 15 and (dark or bright):
        cat = "slope_streak"
        methods["B_streak_morphology"] = True
        ev_for.append(f"elongated (aspect {elong:.1f}, length {comp['major_axis_m']:.0f} m)")
        if f["taper"] > 1.5:
            ev_for.append(f"widens toward one end (taper {f['taper']:.1f}), fan-like")
    elif (dark or comp["polarity"] == "mixed") and (radial or crater_new or (elong < 2.5 and "blob_rc" in f)):
        cat = "new_impact_crater"
    elif area < 30 and f["relief_index"] > 1.0:
        cat = "rockfall_or_boulder_track"
    else:
        cat = "other_change"

    # ---- heuristic score ------------------------------------------------------------
    s_strength = 1 - math.exp(-max(0.0, z - 3.0) / 4.0)
    s_size = 1 - math.exp(-comp["area_px"] / 40.0)
    s_reg = min(1.0, f["local_reg_quality"] / 0.6)
    s_struct = float(np.clip(1.0 - comp["mean_ssim"], 0, 1))
    n_methods = sum(1 for v in methods.values() if v)
    s_agree = min(1.0, n_methods / 3.0)
    score = (0.35 * s_strength + 0.15 * s_size + 0.15 * s_struct + 0.2 * s_agree + 0.15 * s_reg) * (1 - min(0.9, art))
    if cat == "new_impact_crater" and radial and crater_new:
        score = min(1.0, score * 1.15)

    return {
        **comp,
        "category": cat,
        "score": round(float(score), 4),
        "score_kind": "heuristic",
        "artifact_index": round(art, 3),
        "methods": methods,
        "evidence_for": ev_for,
        "evidence_against": ev_against,
        "features": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in f.items()},
    }


def classify_status(c: dict, known: list[dict] | None) -> str:
    # artifact evidence takes precedence: a shadow change next to a catalogued crater is still a shadow change
    if c["category"] == "illumination_or_registration_artifact" or c["artifact_index"] >= 0.5:
        return "likely_artifact"
    if known:
        return "known_documented"
    if c["area_px"] < 12 or c["max_abs_z"] < 5 or c["features"].get("local_reg_quality", 1) < 0.3 or c["score"] < 0.3:
        return "insufficient_evidence"
    return "plausible_unverified"
