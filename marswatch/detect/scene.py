"""Scene-level (pair-level) artifact tests.

Per-candidate artifact tests look at one region at a time. When the two images of a pair differ
*photometrically* (phase angle, haze, viewing azimuth / parallax, resolution), every slope in the
scene changes brightness a little and the detector returns dozens of individually unremarkable
candidates along rims, fractures and dune walls (RESEARCH_LOG, survey 2026-11-04). Two scene
statistics expose this:

1. **Relief coupling** ``R`` — fraction of detected change pixels lying on the steepest 20 % of the
   scene (gradient magnitude of the before image), divided by 0.20. Surface changes (blast zones,
   slope streaks, dust redistribution) are not preferentially located on brightness edges, so
   ``R ≈ 1``; shading/parallax artifacts give ``R ≫ 1``.
2. **Shading model** — the difference image ``D = A − B̂`` is regressed (iteratively trimmed least
   squares, on a pixel subsample) on terrain-shading terms derived from the before image only:
   band-pass images at three scales and directional derivatives. ``R²`` is the fraction of scene
   difference variance explained by shading. Because a genuinely new feature is absent from the
   before image, it cannot be predicted from the before image's shading and is trimmed out of the fit.

Per candidate, ``shading_explained`` = 1 − var(D − P) / var(D) inside the region (P = model
prediction): the fraction of that candidate's own difference that the scene shading model accounts for.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass
class SceneStats:
    relief_coupling: float = 1.0
    detected_px: int = 0
    shading_r2: float = 0.0
    shading_inlier_frac: float = 0.0
    n_candidates: int = 0
    photometric_mismatch: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RELIEF_TOP_FRAC = 0.20
# thresholds (set from survey development pairs; see RESEARCH_LOG "scene-level test")
R_COUPLING_FLAG = 2.0
SHADING_R2_FLAG = 0.15
MIN_DETECTED_PX = 200


def shading_features(b: np.ndarray) -> list[np.ndarray]:
    b = b.astype(np.float32)
    feats = []
    for s_lo, s_hi in ((0.0, 2.0), (2.0, 6.0), (6.0, 16.0)):
        lo = b if s_lo == 0 else cv2.GaussianBlur(b, (0, 0), s_lo)
        feats.append(lo - cv2.GaussianBlur(b, (0, 0), s_hi))
    sm = cv2.GaussianBlur(b, (0, 0), 2.0)
    feats.append(cv2.Sobel(sm, cv2.CV_32F, 1, 0, ksize=3) / 8.0)
    feats.append(cv2.Sobel(sm, cv2.CV_32F, 0, 1, ksize=3) / 8.0)
    return feats


def shading_model(before_m: np.ndarray, after: np.ndarray, mask: np.ndarray, sample: int = 60000,
                  seed: int = 0) -> tuple[np.ndarray, float, float]:
    """Return (predicted difference map, R², inlier fraction)."""
    d = (after - before_m).astype(np.float32)
    feats = shading_features(before_m)
    idx = np.flatnonzero(mask.ravel())
    if idx.size < 1000:
        return np.zeros_like(d), 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.choice(idx, size=min(sample, idx.size), replace=False)
    X = np.column_stack([f.ravel()[idx] for f in feats] + [np.ones(idx.size, np.float32)]).astype(np.float64)
    y = d.ravel()[idx].astype(np.float64)
    keep = np.ones(y.size, bool)
    coef = np.zeros(X.shape[1])
    for _ in range(4):
        coef, *_ = np.linalg.lstsq(X[keep], y[keep], rcond=None)
        r = y - X @ coef
        mad = np.median(np.abs(r[keep] - np.median(r[keep]))) * 1.4826 + 1e-12
        keep = np.abs(r) < 2.5 * mad
    yk = y[keep]
    res = yk - X[keep] @ coef
    r2 = float(1.0 - res.var() / (yk.var() + 1e-20)) if keep.sum() > 100 else 0.0
    pred = sum(c * f for c, f in zip(coef[:-1], feats)) + coef[-1]
    return pred.astype(np.float32), max(0.0, r2), float(keep.mean())


def relief_coupling(det_mask: np.ndarray, grad: np.ndarray, analysis_mask: np.ndarray) -> tuple[float, int]:
    n = int((det_mask & analysis_mask).sum())
    if n < MIN_DETECTED_PX:
        return 1.0, n
    thr = float(np.percentile(grad[analysis_mask], 100 * (1 - RELIEF_TOP_FRAC)))
    frac = float((grad[det_mask & analysis_mask] >= thr).mean())
    return frac / RELIEF_TOP_FRAC, n


def scene_stats(before_m: np.ndarray, after: np.ndarray, det_mask: np.ndarray, analysis_mask: np.ndarray,
                grad: np.ndarray, n_candidates: int) -> tuple[SceneStats, np.ndarray]:
    st = SceneStats(n_candidates=n_candidates)
    st.relief_coupling, st.detected_px = relief_coupling(det_mask, grad, analysis_mask)
    pred, st.shading_r2, st.shading_inlier_frac = shading_model(before_m, after, analysis_mask)
    why = []
    if st.relief_coupling >= R_COUPLING_FLAG:
        why.append(f"{st.relief_coupling:.1f}× more change pixels on steep terrain than expected")
    if st.shading_r2 >= SHADING_R2_FLAG:
        why.append(f"{st.shading_r2 * 100:.0f}% of scene difference variance is explained by terrain shading")
    st.photometric_mismatch = bool(why)
    st.reason = "; ".join(why)
    return st, pred


def shading_explained(diff: np.ndarray, pred: np.ndarray, region: np.ndarray) -> float:
    if region.sum() < 6:
        return 0.0
    d = diff[region].astype(np.float64)
    if (d ** 2).mean() < 1e-14:  # no difference at all: nothing to explain
        return 0.0
    r = d - pred[region]
    # compare energy about zero (a uniform albedo step is *not* shading-explained)
    return float(max(0.0, 1.0 - (r ** 2).mean() / ((d ** 2).mean() + 1e-20)))


# ---------------------------------------------------------------------------------------------
# Scene-level test applied to the candidate population of one pair
# ---------------------------------------------------------------------------------------------
SCENE_MIN_CANDIDATES = 12
SCENE_RELIEF_INDEX = 1.5
SCENE_RELIEF_FRAC_FLAG = 0.6
SHADING_EXPLAINED_FLAG = 0.4
OUTLIER_MADS = 3.0


def apply_scene_test(cands: list[dict], labels: np.ndarray, diff: np.ndarray, pred: np.ndarray,
                     stats: SceneStats) -> dict:
    """Flag pairs whose candidate population is dominated by relief-bound responses and demote the
    candidates that share that signature unless they are strength outliers within the scene.

    Mutates candidates (features, evidence_against, classification, artifact_index) and returns a summary.
    """
    for c in cands:
        m = labels == c["label"]
        c["features"]["shading_explained"] = round(shading_explained(diff, pred, m), 3)
    n = len(cands)
    rel = np.array([c["features"].get("relief_index", 0.0) for c in cands]) if n else np.zeros(0)
    z = np.array([c["max_abs_z"] for c in cands]) if n else np.zeros(0)
    frac_relief = float((rel > SCENE_RELIEF_INDEX).mean()) if n else 0.0
    zmed = float(np.median(z)) if n else 0.0
    zmad = max(0.5, float(np.median(np.abs(z - zmed)) * 1.4826)) if n else 0.5
    flagged = n >= SCENE_MIN_CANDIDATES and frac_relief >= SCENE_RELIEF_FRAC_FLAG
    summary = {"n_candidates": n, "frac_on_relief": round(frac_relief, 3), "z_median": round(zmed, 2),
               "z_mad": round(zmad, 2), "flagged": flagged, "relief_coupling_px": round(stats.relief_coupling, 2),
               "shading_r2": round(stats.shading_r2, 3), "demoted": 0, "survived_as_outliers": 0}
    for c in cands:
        f = c["features"]
        shares = f.get("relief_index", 0) > SCENE_RELIEF_INDEX or f["shading_explained"] > SHADING_EXPLAINED_FLAG
        outlier = c["max_abs_z"] >= zmed + OUTLIER_MADS * zmad
        f["scene_flagged"] = flagged
        f["scene_shares_signature"] = bool(shares)
        f["scene_outlier"] = bool(outlier)
        if not flagged or not shares:
            continue
        if outlier:
            summary["survived_as_outliers"] += 1
            c["evidence_for"].append(f"scene-level: stands out from this pair's systematic relief-bound population "
                                     f"(|z| {c['max_abs_z']:.1f} vs scene median {zmed:.1f})")
            continue
        c["evidence_against"].append(
            f"scene-level: {frac_relief * 100:.0f}% of this pair's {n} candidates sit on steep relief — a systematic "
            f"photometric/parallax difference between the images; this candidate shares that signature "
            f"(relief {f.get('relief_index', 0):.1f}×, shading-explained {f['shading_explained']:.2f}) and is not a "
            f"strength outlier (|z| {c['max_abs_z']:.1f} vs median {zmed:.1f})")
        c["artifact_index"] = round(c["artifact_index"] + 0.35, 3)
        if c["classification"] in ("plausible_unverified", "known_documented"):
            c["classification"] = "likely_artifact" if c["artifact_index"] >= 0.5 else "insufficient_evidence"
            summary["demoted"] += 1
    return summary
