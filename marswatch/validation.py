"""Scientific validation framework.

Test sets (all built from real HiRISE observations; see docs/VALIDATION.md):

1. **Documented positives** — new impacts from Daubar et al. (2022) for which a
   HiRISE image exists *before* the catalogue's "before" date and another *after*
   its "after" date, both covering the crater. Success = a candidate within a
   tolerance of the catalogued position (in the after-image pointing frame).
2. **Same-site negative controls** — pairs at the same sites in which both
   images precede formation ("pre-pre") or both follow it ("post-post", which
   may legitimately contain blast-zone fading). Detections there are counted as
   false positives (pre-pre) or as non-impact changes (post-post).
3. **Illumination stress** — the above, broken down by Δincidence / Δsun-azimuth.
4. **Sensitivity vs size** (SYNTHETIC INJECTION, labelled as such) — artificial
   dark blast-zone + crater-bowl signatures injected into real, registered,
   unchanged pre-pre imagery at known positions and diameters. Used only to
   measure detectability vs size/contrast, never presented as real data.
5. **Registration accuracy** — (a) held-out checkpoint residuals on every real
   pair; (b) SYNTHETIC known warps (translation + affine + jitter) of real
   imagery, comparing estimated vs true displacement fields.
6. **Computational performance** — wall time per km², peak RSS.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
import psutil

from .align import align_pair
from .config import REPO_ROOT, settings
from .db import Database, get_db
from .detect import fuse
from .detect.classical import ClassicalParams, detect
from .discovery import observations_covering, score_pair
from .geometry import haversine_m
from .imagery import RemoteImage, cog_available, make_grid
from .log import get_logger
from .normalize import psf_match, radiometric_match
from .pipeline import code_version, run_pair
from .registration import fine_register

log = get_logger("validation")

CASES_FILE = "validation_cases.json"
STATUSES = ("known_documented", "plausible_unverified", "likely_artifact", "insufficient_evidence")


# ---------------------------------------------------------------------------
# case construction
# ---------------------------------------------------------------------------

def build_crater_cases(db: Database, max_scale: float = 0.5, margin_m: float = 150.0,
                       max_negatives_per_case: int = 2) -> list[dict]:
    refs = db.query("SELECT * FROM reference_changes WHERE category='new_impact_crater' AND before_date IS NOT NULL")
    cases = []
    for r in refs:
        cov = [o for o in observations_covering(db, r["lat"], r["lon"], margin_m) if (o["map_scale"] or 9) <= max_scale]
        pre = [o for o in cov if o["start_time"][:10] < r["before_date"]]
        post = [o for o in cov if o["start_time"][:10] >= (r["after_date"] or "9999")]
        if not pre or not post:
            continue
        best = None
        for b in pre:
            for a in post:
                p = score_pair(b, a)
                if p is None:
                    continue
                key = (a["observation_id"] == r["hirise_id"], p.suitability)
                if best is None or key > best[0]:
                    best = (key, p)
        if best is None:
            continue
        p = best[1]
        negs = []
        for group, label in ((pre, "pre-pre"), (post, "post-post")):
            opts = []
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    q = score_pair(group[i], group[j])
                    if q and q.dt_days >= 30:
                        opts.append(q)
            opts.sort(key=lambda q: -q.suitability)
            negs += [{"kind": label, "before_id": q.before_id, "after_id": q.after_id, "suitability": q.suitability,
                      "d_incidence": q.d_incidence, "d_sun_azimuth": q.d_sun_azimuth, "dt_days": q.dt_days}
                     for q in opts[:max_negatives_per_case]]
        cases.append({
            "ref_id": r["ref_id"], "lat": r["lat"], "lon": r["lon"], "diameter_m": r["diameter_m"],
            "hirise_id": r["hirise_id"], "before_date": r["before_date"], "after_date": r["after_date"],
            "blast_zone_tone": (r["attrs"] or {}).get("blast_zone_tone"),
            "positive": {"before_id": p.before_id, "after_id": p.after_id, "suitability": p.suitability,
                         "d_incidence": p.d_incidence, "d_sun_azimuth": p.d_sun_azimuth, "dt_days": p.dt_days,
                         "after_is_catalog_image": p.after_id.replace("_RED", "") == r["hirise_id"]},
            "negatives": negs,
        })
    cases.sort(key=lambda c: c["ref_id"])
    return cases


def build_holdout_cases(db: Database, tuning: list[dict], max_scale: float = 0.5, margin_m: float = 150.0,
                        max_alt: int = 2, max_neg: int = 2) -> list[dict]:
    """Held-out set: same documented sites, but image pairs NOT used while developing the rules.

    Positive alternatives use a different before image or a different after image than the tuning pair;
    negative controls are pre-pre / post-post combinations ranked below those used in tuning.
    """
    used = {(c["positive"]["before_id"], c["positive"]["after_id"]) for c in tuning}
    used |= {(n["before_id"], n["after_id"]) for c in tuning for n in c["negatives"]}
    out = []
    for c in tuning:
        r = db.one("SELECT * FROM reference_changes WHERE ref_id=?", [c["ref_id"]])
        cov = [o for o in observations_covering(db, r["lat"], r["lon"], margin_m) if (o["map_scale"] or 9) <= max_scale]
        pre = [o for o in cov if o["start_time"][:10] < r["before_date"]]
        post = [o for o in cov if o["start_time"][:10] >= (r["after_date"] or "9999")]
        alts = []
        for b in pre:
            for a in post:
                if (b["product_id"], a["product_id"]) in used:
                    continue
                q = score_pair(b, a)
                if q:
                    alts.append(q)
        alts.sort(key=lambda q: -q.suitability)
        negs = []
        for group, label in ((pre, "pre-pre"), (post, "post-post")):
            opts = []
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    q = score_pair(group[i], group[j])
                    if q and q.dt_days >= 30 and (q.before_id, q.after_id) not in used:
                        opts.append(q)
            opts.sort(key=lambda q: -q.suitability)
            negs += [{"kind": label, "before_id": q.before_id, "after_id": q.after_id, "suitability": q.suitability,
                      "d_incidence": q.d_incidence, "d_sun_azimuth": q.d_sun_azimuth, "dt_days": q.dt_days}
                     for q in opts[:max_neg]]
        for k, q in enumerate(alts[:max_alt] or [None]):
            if q is None and not negs:
                continue
            e = {key: c[key] for key in ("ref_id", "lat", "lon", "diameter_m", "hirise_id", "before_date", "after_date", "blast_zone_tone")}
            e["positive"] = None if q is None else {
                "before_id": q.before_id, "after_id": q.after_id, "suitability": q.suitability, "d_incidence": q.d_incidence,
                "d_sun_azimuth": q.d_sun_azimuth, "dt_days": q.dt_days,
                "after_is_catalog_image": q.after_id.replace("_RED", "") == r["hirise_id"]}
            e["negatives"] = negs if k == 0 else []
            out.append(e)
    return out


def load_or_build_holdout(db: Database, rebuild: bool = False) -> list[dict]:
    path = settings.reference_dir / "validation_cases_holdout.json"
    if path.exists() and not rebuild:
        cases = json.loads(path.read_text())
        if cases:
            return cases
    cases = build_holdout_cases(db, load_or_build_cases(db))
    path.write_text(json.dumps(cases, indent=1))
    return cases


def load_or_build_cases(db: Database, rebuild: bool = False) -> list[dict]:
    path = settings.reference_dir / CASES_FILE
    if path.exists() and not rebuild:
        return json.loads(path.read_text())
    cases = build_crater_cases(db)
    path.write_text(json.dumps(cases, indent=1))
    return cases


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------

def match_reference(cands: list[dict], lat: float, lon: float, tol_m: float, ref_id: str | None = None,
                    criterion: str = "region") -> tuple[dict | None, float]:
    """Find the candidate corresponding to a documented change.

    ``criterion="centroid"``: nearest candidate position within ``tol_m`` (validation run 1).
    ``criterion="region"`` (default since run 2): additionally accept a candidate whose detected
    region contains the reference point (bbox + 20 m), preferring the highest-scoring such candidate.
    """
    best, bd = None, float("inf")
    for c in cands:
        d = min(haversine_m(lat, lon, c["lat_after_frame"], c["lon_after_frame"]),
                haversine_m(lat, lon, c["lat"], c["lon"]))
        if d < bd:
            best, bd = c, d
    if best is not None and bd <= tol_m:
        if criterion == "centroid":
            return best, bd
    if criterion == "region" and ref_id:
        hits = [c for c in cands if any(a["ref_id"] == ref_id and a["inside_region"] for a in c.get("reference_associations", []))]
        near = [c for c in cands if min(haversine_m(lat, lon, c["lat_after_frame"], c["lon_after_frame"]),
                                        haversine_m(lat, lon, c["lat"], c["lon"])) <= tol_m]
        pool = hits + near
        if pool:
            m = max(pool, key=lambda c: c["score"])
            return m, min(haversine_m(lat, lon, m["lat_after_frame"], m["lon_after_frame"]), haversine_m(lat, lon, m["lat"], m["lon"]))
    return (best, bd) if best is not None and bd <= tol_m else (None, bd)


def _window_area_km2(doc: dict) -> float:
    return doc["stats"]["analysed_km2"]


def run_crater_validation(db: Database | None = None, half_size_m: float = 500.0, res_m: float = 0.5,
                          limit: int | None = None, include_negatives: bool = True, use_ml: bool = True,
                          case_set: str = "tuning", criterion: str = "region", skip_missing_cog: bool = True) -> dict:
    db = db or get_db()
    cases = (load_or_build_cases(db) if case_set == "tuning" else load_or_build_holdout(db))[: limit or None]
    proc = psutil.Process()
    peak_rss = proc.memory_info().rss
    results = []
    for ci, case in enumerate(cases):
        aoi = {"lat": case["lat"], "lon": case["lon"], "half_size_m": half_size_m}
        tol = 60.0 if (case.get("positive") or {}).get("after_is_catalog_image", True) else 150.0
        entry = {"ref_id": case["ref_id"], "diameter_m": case["diameter_m"], "tol_m": tol, "runs": []}
        jobs = ([("positive", case["positive"])] if case.get("positive") else []) + (
            [("neg:" + n["kind"], n) for n in case["negatives"]] if include_negatives else [])
        for kind, pr in jobs:
            t0 = time.time()
            missing = [pid for pid in (pr["before_id"], pr["after_id"]) if not cog_available(pid)]
            if missing and skip_missing_cog:
                entry["runs"].append({"kind": kind, "skipped": f"USGS COG not yet published for {', '.join(missing)} "
                                      "(PDS JP2 fallback too slow for batch validation)",
                                      "before_id": pr["before_id"], "after_id": pr["after_id"]})
                log.info(f"{case['ref_id']} {kind}: skipped (no COG for {missing})")
                continue
            try:
                doc = run_pair(pr["before_id"], pr["after_id"], aoi, db=db, res_m=res_m, use_ml=use_ml,
                               run_kind="validation", write_tiles=False)
            except Exception as e:  # record failures rather than hiding them
                from .pipeline import InputRejected

                log.error(f"{case['ref_id']} {kind} failed: {e}")
                entry["runs"].append({"kind": kind, "error": str(e), "input_rejected": isinstance(e, InputRejected),
                                      "before_id": pr["before_id"], "after_id": pr["after_id"]})
                continue
            peak_rss = max(peak_rss, proc.memory_info().rss)
            cands = doc["candidates"]
            m, dist = match_reference(cands, case["lat"], case["lon"], tol, case["ref_id"], criterion)
            m_c, _ = match_reference(cands, case["lat"], case["lon"], tol, case["ref_id"], "centroid")
            r = {
                "kind": kind, "run_id": doc["run_id"], "before_id": pr["before_id"], "after_id": pr["after_id"],
                "d_incidence": pr["d_incidence"], "d_sun_azimuth": pr["d_sun_azimuth"], "dt_days": pr["dt_days"],
                "registration": {k: doc["registration"][k] for k in ("quality", "check_rms_px", "check_p90_px", "checkpoints",
                                                                     "ncc_after", "coarse_dx_m", "coarse_dy_m", "status")},
                "area_km2": _window_area_km2(doc), "seconds": time.time() - t0,
                "timings": doc["stats"]["timings"],
                "n_candidates": len(cands),
                "candidates": [{"score": c["score"], "known_match": c.get("known_match"), "category": c["category"], "status": c["classification"],
                                "eq_diameter_m": c["eq_diameter_m"], "max_abs_z": c["max_abs_z"],
                                "dist_to_ref_m": min(haversine_m(case["lat"], case["lon"], c["lat_after_frame"], c["lon_after_frame"]),
                                                     haversine_m(case["lat"], case["lon"], c["lat"], c["lon"])),
                                "deep_z": c["features"].get("deep_z"), "methods": c["methods"]} for c in cands],
                "nearest_dist_m": dist,
                "match_centroid_criterion": bool(m_c is not None),
            }
            if m is not None:
                r["match"] = {"score": m["score"], "category": m["category"], "status": m["classification"],
                              "rank": sorted([c["score"] for c in cands], reverse=True).index(m["score"]) + 1,
                              "eq_diameter_m": m["eq_diameter_m"], "max_abs_z": m["max_abs_z"], "dist_m": dist,
                              "deep_z": m["features"].get("deep_z"), "methods": m["methods"]}
            entry["runs"].append(r)
            log.info(f"[{ci + 1}/{len(cases)}] {case['ref_id']} {kind}: {len(cands)} cands, "
                     f"match={'yes' if m else 'no'} (nearest {dist:.0f} m), reg q={doc['registration']['quality']:.2f}")
        results.append(entry)
        # checkpoint after every site so an interrupted validation keeps its results
        (settings.data_dir / "validation").mkdir(exist_ok=True)
        (settings.data_dir / "validation" / f"partial_{case_set}.json").write_text(json.dumps(results, default=str))
    metrics = summarize(results)
    metrics["peak_rss_mb"] = peak_rss / 1e6
    return {"cases": results, "metrics": metrics}


def _real_match(m: dict) -> bool:
    """A matched candidate only counts if it was not itself judged an artifact."""
    return m["status"] != "likely_artifact" and m["category"] != "illumination_or_registration_artifact"


def summarize(results: list[dict], thresholds=(0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)) -> dict:
    ok = lambda r: "error" not in r and "skipped" not in r
    pos = [r for e in results for r in e["runs"] if r["kind"] == "positive" and ok(r)]
    pre = [r for e in results for r in e["runs"] if r["kind"] == "neg:pre-pre" and ok(r)]
    post = [r for e in results for r in e["runs"] if r["kind"] == "neg:post-post" and ok(r)]
    skipped = [r for e in results for r in e["runs"] if "skipped" in r]
    errors = [r for e in results for r in e["runs"] if "error" in r]
    diam = {e["ref_id"]: e["diameter_m"] for e in results}
    out: dict = {"n_cases": len(results), "n_positive_runs": len(pos), "n_prepre_runs": len(pre),
                 "n_postpost_runs": len(post), "n_failed_runs": len(errors), "n_skipped_runs": len(skipped),
                 "skipped": [{"kind": r["kind"], "before": r["before_id"], "after": r["after_id"], "reason": r["skipped"]} for r in skipped],
                 "failures": [{"kind": r["kind"], "before": r["before_id"], "after": r["after_id"], "error": r["error"]} for r in errors]}
    nonart = lambda c: c["status"] != "likely_artifact"

    def recall(th: float, need_cat: bool = False) -> float:
        if not pos:
            return float("nan")
        ok = 0
        for r in pos:
            m = r.get("match")
            if m and m["score"] >= th and _real_match(m) and (not need_cat or m["category"] == "new_impact_crater"):
                ok += 1
        return ok / len(pos)

    def fp_count(runs: list[dict], th: float, exclude_match: bool) -> tuple[int, float]:
        n, area = 0, 0.0
        for r in runs:
            area += r["area_km2"]
            for c in r["candidates"]:
                if c["score"] < th or not nonart(c):
                    continue
                if c.get("known_match"):
                    continue  # associated with a catalogued change (e.g. other craters of the same cluster impact)
                if exclude_match and r.get("match") and c["dist_to_ref_m"] <= max(r.get("match", {}).get("dist_m", 0), 0) + 1e-6:
                    continue
                if exclude_match and c["dist_to_ref_m"] <= 60:
                    continue  # part of the documented change (e.g. fragmented blast zone)
                n += 1
        return n, area

    table = []
    for th in thresholds:
        tp = sum(1 for r in pos if r.get("match") and r["match"]["score"] >= th and _real_match(r["match"]))
        fp_pos, a_pos = fp_count(pos, th, True)
        fp_pre, a_pre = fp_count(pre, th, False)
        prec = tp / (tp + fp_pos + fp_pre) if (tp + fp_pos + fp_pre) else float("nan")
        n_rej = sum(1 for e in results for r in e["runs"] if r["kind"] == "positive" and r.get("input_rejected"))
        table.append({
            "threshold": th, "recall_any_category": recall(th), "recall_as_new_impact": recall(th, True),
            "tp": tp, "fp_in_positive_windows": fp_pos, "fp_in_prepre_controls": fp_pre,
            "fp_per_km2_positive_windows": fp_pos / a_pos if a_pos else float("nan"),
            "fp_per_km2_prepre": fp_pre / a_pre if a_pre else float("nan"),
            "precision_window_assumption": prec,
            "recall_counting_rejected_inputs_as_misses": tp / (len(pos) + n_rej) if (len(pos) + n_rej) else float("nan"),
            # matched AND left in an actionable status (not demoted to insufficient evidence by e.g. the scene test)
            "recall_actionable": (sum(1 for r in pos if r.get("match") and r["match"]["score"] >= th and _real_match(r["match"])
                                      and r["match"]["status"] in ("known_documented", "plausible_unverified")) / len(pos))
                                 if pos else float("nan"),
        })
    out["operating_points"] = table
    # matched-candidate rank (how high the documented change ranks within its window)
    ranks = [r["match"]["rank"] for r in pos if r.get("match")]
    out["match_rank_median"] = float(np.median(ranks)) if ranks else None
    out["match_rank_top1_frac"] = float(np.mean([k == 1 for k in ranks])) if ranks else None
    # sensitivity vs diameter (real cases)
    bins = [(0, 3), (3, 5), (5, 8), (8, 100)]
    sens = []
    for lo, hi in bins:
        sel = [r for e in results for r in e["runs"] if r["kind"] == "positive" and ok(r)
               and lo <= (diam[e["ref_id"]] or 0) < hi]
        det = sum(1 for r in sel if r.get("match") and _real_match(r["match"]))
        sens.append({"diameter_m": f"{lo}-{hi}", "n": len(sel), "detected": det, "rate": det / len(sel) if sel else None})
    out["sensitivity_by_diameter_real"] = sens
    # illumination breakdown
    ill = []
    for name, sel in (("d_incidence<=10", [r for r in pos + pre if r["d_incidence"] <= 10]),
                      ("d_incidence>10", [r for r in pos + pre if r["d_incidence"] > 10])):
        fp, area = fp_count([r for r in sel if r["kind"] != "positive"], 0.4, False)
        fpp, areap = fp_count([r for r in sel if r["kind"] == "positive"], 0.4, True)
        ill.append({"group": name, "runs": len(sel), "fp_per_km2_at_0.4": (fp + fpp) / (area + areap) if (area + areap) else None})
    out["illumination_breakdown"] = ill
    rb = []
    for name, lo, hi in (("Δinc ≤ 5°", -1, 5), ("5° < Δinc ≤ 10°", 5, 10), ("Δinc > 10°", 10, 999)):
        sel = [r for r in pos if lo < r["d_incidence"] <= hi]
        det = sum(1 for r in sel if r.get("match") and _real_match(r["match"]))
        art = sum(1 for r in sel if r.get("match") and not _real_match(r["match"]))
        rb.append({"group": name, "n": len(sel), "detected": det, "matched_but_labelled_artifact": art,
                   "recall": det / len(sel) if sel else None})
    out["recall_by_illumination"] = rb
    # post-post: what is detected near the crater (blast-zone evolution) and elsewhere
    out["postpost_detections_near_crater"] = sum(1 for r in post for c in r["candidates"] if c["dist_to_ref_m"] <= 100 and nonart(c))
    out["postpost_nonartifact_elsewhere_per_km2"] = (
        sum(1 for r in post for c in r["candidates"] if c["dist_to_ref_m"] > 100 and nonart(c) and c["score"] >= 0.4)
        / max(1e-9, sum(r["area_km2"] for r in post)) if post else None)
    # registration over all real runs
    allruns = pos + pre + post
    rms = [r["registration"]["check_rms_px"] for r in allruns if r["registration"]["check_rms_px"] is not None]
    out["registration_real"] = {
        "runs": len(allruns), "checkpoint_rms_px_median": float(np.median(rms)) if rms else None,
        "checkpoint_rms_px_p90": float(np.percentile(rms, 90)) if rms else None,
        "status_counts": {s: sum(1 for r in allruns if r["registration"]["status"] == s) for s in ("good", "marginal", "poor")},
        "coarse_offset_m_median": float(np.median([math.hypot(r["registration"]["coarse_dx_m"], r["registration"]["coarse_dy_m"]) for r in allruns])) if allruns else None,
    }
    # ML ablation: does deep_z separate the documented change from other non-artifact candidates?
    dz_pos = [r["match"]["deep_z"] for r in pos if r.get("match") and r["match"].get("deep_z") is not None]
    dz_neg = [c["deep_z"] for r in pos + pre for c in r["candidates"]
              if c.get("deep_z") is not None and c["dist_to_ref_m"] > 60 and nonart(c)]
    out["ml_deep_z"] = {"documented_median": float(np.median(dz_pos)) if dz_pos else None,
                        "other_candidates_median": float(np.median(dz_neg)) if dz_neg else None,
                        "auc": _auc(dz_pos, dz_neg)}
    sec = [r["seconds"] for r in allruns]
    km2 = [r["area_km2"] for r in allruns]
    out["performance"] = {"median_seconds_per_run": float(np.median(sec)) if sec else None,
                          "seconds_per_km2": float(sum(sec) / sum(km2)) if km2 and sum(km2) else None}
    return out


def _auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    p, n = np.asarray(pos), np.asarray(neg)
    return float(((p[:, None] > n[None, :]).sum() + 0.5 * (p[:, None] == n[None, :]).sum()) / (len(p) * len(n)))


# ---------------------------------------------------------------------------
# synthetic tests on real imagery (clearly labelled)
# ---------------------------------------------------------------------------

def _inject(after: np.ndarray, rc: tuple[int, int], diameter_px: float, contrast: float, sun_angle: float,
            halo_factor: float = 8.0) -> np.ndarray:
    """SYNTHETIC: dark blast-zone halo (Gaussian, ~halo_factor × crater D) + shaded bowl crater."""
    out = after.copy()
    h, w = after.shape
    r0, c0 = rc
    R = int(max(6, diameter_px * halo_factor))
    y0, y1, x0, x1 = max(0, r0 - R), min(h, r0 + R + 1), max(0, c0 - R), min(w, c0 + R + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dy, dx = yy - r0, xx - c0
    rr = np.sqrt(dx * dx + dy * dy)
    sig = R / 2.5
    halo = np.exp(-(rr ** 2) / (2 * sig ** 2))
    local = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = local * (1 - contrast * halo)
    rad = diameter_px / 2
    bowl = rr <= rad
    if rad >= 1:
        proj = (dx * math.cos(sun_angle) + dy * math.sin(sun_angle)) / max(rad, 1)
        shade = np.where(bowl, 1 - 0.5 * np.clip(proj + 0.3, 0, 1.3), 1.0)
        out[y0:y1, x0:x1] *= shade
    return out


def injection_sensitivity(db: Database | None = None, n_per_bin: int = 12, seed: int = 1,
                          diameters_m=(1.0, 2.0, 3.0, 5.0, 8.0, 12.0), contrasts=(0.05, 0.10, 0.20),
                          res_m: float = 0.5, half_size_m: float = 500.0, halo_factor: float = 8.0) -> dict:
    """SYNTHETIC INJECTION into real unchanged (pre-pre) registered imagery.

    ``halo_factor`` = halo radius / crater diameter; contrast 0 injects the shaded bowl only (no halo).
    """
    db = db or get_db()
    cases = [c for c in load_or_build_cases(db) if any(n["kind"] == "pre-pre" for n in c["negatives"])]
    rng = np.random.default_rng(seed)
    rows = []
    for case in cases[:4]:
        neg = next(n for n in case["negatives"] if n["kind"] == "pre-pre")
        ob = db.one("SELECT * FROM observations WHERE product_id=?", [neg["before_id"]])
        oa = db.one("SELECT * FROM observations WHERE product_id=?", [neg["after_id"]])
        grid = make_grid(case["lat"], case["lon"], half_size_m, half_size_m, res_m)
        ap = align_pair(RemoteImage(neg["before_id"]), RemoteImage(neg["after_id"]), grid)
        if ap.fine.diagnostics.quality < 0.2:
            continue
        valid = ap.valid
        b_psf, a_psf, _ = psf_match(ap.before, ap.after, valid)
        bm, _ = radiometric_match(b_psf, a_psf, valid)
        ap.after = a_psf
        resid = ap.fine.diagnostics.check_rms_px or 1.0
        sun = fuse.sun_vector_angle(oa["sub_solar_azimuth"], oa["north_azimuth"]) or 0.0
        ctx = fuse.FusionContext(res_m, case["lat"], neg["d_incidence"], 0.0, neg["d_sun_azimuth"], sun, sun,
                                 ap.fine.diagnostics.quality, resid)
        base = detect(bm, ap.after, valid, ap.fine.quality_map, res_m, resid)
        safe = base.analysis_mask & ~cv2.dilate(base.mask.astype(np.uint8), np.ones((81, 81), np.uint8)).astype(bool)
        ys, xs = np.nonzero(safe[100:-100, 100:-100])
        if len(ys) == 0:
            continue
        for D in diameters_m:
            for con in contrasts:
                hits = 0
                n = 0
                for k in range(n_per_bin // len(cases[:4]) + 1):
                    i = rng.integers(len(ys))
                    rc = (int(ys[i]) + 100, int(xs[i]) + 100)
                    inj = _inject(ap.after, rc, D / res_m, con, sun, halo_factor=halo_factor)
                    cr = detect(bm, inj, valid, ap.fine.quality_map, res_m, resid)
                    cands = fuse.characterise(bm, inj, cr, ap.fine.quality_map, ctx, max_candidates=50)
                    tol = max(10.0, D * 4) / res_m
                    hit = any(math.hypot(c["centroid_rc"][0] - rc[0], c["centroid_rc"][1] - rc[1]) <= tol
                              and c["artifact_index"] < 0.5 for c in cands)
                    hits += hit
                    n += 1
                rows.append({"site": case["ref_id"], "diameter_m": D, "halo_contrast": con, "n": n, "hits": hits})
                log.info(f"injection {case['ref_id']} D={D} c={con}: {hits}/{n}")
    agg: dict = {}
    for r in rows:
        k = (r["diameter_m"], r["halo_contrast"])
        a = agg.setdefault(k, [0, 0])
        a[0] += r["hits"]
        a[1] += r["n"]
    table = [{"diameter_m": k[0], "halo_contrast": k[1], "n": v[1], "detection_rate": v[0] / v[1] if v[1] else None}
             for k, v in sorted(agg.items())]
    return {"label": "SYNTHETIC INJECTION into real HiRISE imagery (not real changes)", "halo_factor": halo_factor,
            "rows": rows, "table": table}


def registration_synthetic(db: Database | None = None, n_trials: int = 8, seed: int = 2, res_m: float = 0.5) -> dict:
    """SYNTHETIC known warps applied to real imagery; measures fine-registration error vs truth."""
    db = db or get_db()
    cases = load_or_build_cases(db)
    rng = np.random.default_rng(seed)
    trials = []
    from .imagery import QC_MIN_SNR, structure_snr

    for t in range(len(cases) * 2):
        if len(trials) >= n_trials:
            break
        case = cases[t % len(cases)]
        pid = case["positive"]["after_id"] if t >= len(cases) else case["positive"]["before_id"]
        grid = make_grid(case["lat"], case["lon"], 300, 300, res_m)
        img, valid = RemoteImage(pid).read_to_grid(grid)
        if valid.mean() < 0.9 or structure_snr(img, valid) < QC_MIN_SNR:
            log.info(f"registration synthetic: skipping {pid} (coverage or structure SNR below QC threshold)")
            continue
        h, w = img.shape
        tx, ty = rng.uniform(-8, 8, 2)
        rot = math.radians(rng.uniform(-0.5, 0.5))
        sc = 1 + rng.uniform(-0.005, 0.005)
        amp, per = rng.uniform(0, 1.5), rng.uniform(200, 600)
        YY, XX = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2, h / 2
        fx = (sc * math.cos(rot) - 1) * (XX - cx) - sc * math.sin(rot) * (YY - cy) + tx + amp * np.sin(2 * math.pi * YY / per)
        fy = sc * math.sin(rot) * (XX - cx) + (sc * math.cos(rot) - 1) * (YY - cy) + ty
        mov = cv2.remap(img, XX + fx.astype(np.float32), YY + fy.astype(np.float32), cv2.INTER_CUBIC)
        gain = rng.uniform(0.5, 1.5)
        mov = mov * gain + rng.normal(0, img[valid].std() * 0.08, mov.shape).astype(np.float32)
        mv = cv2.remap(valid.astype(np.uint8), XX + fx.astype(np.float32), YY + fy.astype(np.float32), cv2.INTER_NEAREST) > 0
        fr = fine_register(img, valid, mov.astype(np.float32), mv, res_m)
        m = valid & mv
        m[:40], m[-40:], m[:, :40], m[:, -40:] = False, False, False, False
        # mov(p) = img(p + f(p)); registration estimates g with mov(p + g(p)) = img(p), i.e. g(p) = -f(p + g(p)).
        gx, gy = -fx.astype(np.float32), -fy.astype(np.float32)
        for _ in range(5):  # fixed-point inversion of the known field
            gx = -cv2.remap(fx.astype(np.float32), XX + gx, YY + gy, cv2.INTER_LINEAR)
            gy = -cv2.remap(fy.astype(np.float32), XX + gx, YY + gy, cv2.INTER_LINEAR)
        err = np.sqrt((fr.flow_x - gx) ** 2 + (fr.flow_y - gy) ** 2)[m]
        trials.append({"site": case["ref_id"], "product_id": pid, "true_shift_px": [float(tx), float(ty)], "rot_deg": math.degrees(rot),
                       "jitter_amp_px": amp, "err_rms_px": float(np.sqrt((err ** 2).mean())),
                       "err_p90_px": float(np.percentile(err, 90)),
                       "checkpoint_rms_px": fr.diagnostics.check_rms_px, "quality": fr.diagnostics.quality})
        log.info(f"registration synthetic trial {len(trials)}: true-field RMS error {trials[-1]['err_rms_px']:.3f}px "
                 f"(checkpoint estimate {fr.diagnostics.check_rms_px:.3f}px)")
    errs = [t["err_rms_px"] for t in trials]
    return {"label": "SYNTHETIC known warps of real HiRISE imagery", "trials": trials,
            "err_rms_px_median": float(np.median(errs)) if errs else None,
            "err_rms_px_max": float(np.max(errs)) if errs else None}


def save_validation(db: Database, kind: str, result: dict, params: dict | None = None) -> int:
    metrics = result.get("metrics") or {k: v for k, v in result.items() if k not in ("cases", "rows", "trials")}
    vid = db.insert("validation_runs", {"kind": kind, "created_at": time.time(), "code_version": code_version(),
                                        "params": params or {}, "metrics": metrics, "details": result})
    out = settings.data_dir / "validation"
    out.mkdir(exist_ok=True)
    (out / f"{kind}_{vid}.json").write_text(json.dumps(result, indent=1, default=str))
    return vid
