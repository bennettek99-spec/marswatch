"""Offline unit tests. Imagery fixtures are a real HiRISE crop; synthetic perturbations are labelled."""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import FIX, shift_image


# ---------------------------------------------------------------- PDS index
def test_parse_label_and_rows():
    from marswatch.archive.pds_index import parse_index_bytes, parse_label_columns

    lbl = (FIX / "RDRCUMINDEX.LBL").read_text(encoding="latin-1")
    cols = parse_label_columns(lbl)
    assert cols[0] == "VOLUME_ID" and "CORNER4_LONGITUDE" in cols and "SOLAR_LONGITUDE" in cols
    rows = parse_index_bytes(lbl, (FIX / "rdrcumindex_sample.tab").read_bytes())
    ids = {r["product_id"] for r in rows}
    assert "ESP_056155_1980_RED" in ids
    r = next(r for r in rows if r["product_id"] == "ESP_056155_1980_RED")
    assert 17 < r["center_lat"] < 18.5 and 226 < r["center_lon"] < 228
    assert r["pds_path"].endswith("ESP_056155_1980_RED.JP2")


# ---------------------------------------------------------------- geometry
def _obs(lat0, lat1, lon0, lon1, pid="X_RED"):
    return {"product_id": pid, "c1_lat": lat0, "c1_lon": lon0, "c2_lat": lat0, "c2_lon": lon1,
            "c3_lat": lat1, "c3_lon": lon1, "c4_lat": lat1, "c4_lon": lon0}


def test_overlap_area_and_disjoint():
    from marswatch.geometry import MARS_RADIUS_M, overlap

    a = _obs(0.0, 0.1, 10.0, 10.1)
    ov = overlap(a, a)
    expected = (MARS_RADIUS_M * math.radians(0.1)) ** 2 / 1e6  # ~35 km² near the equator
    assert ov is not None and abs(ov.area_km2 - expected) / expected < 0.01
    assert overlap(a, _obs(1.0, 1.1, 10.0, 10.1)) is None
    half = overlap(a, _obs(0.05, 0.15, 10.0, 10.1))
    assert half is not None and abs(half.frac_a - 0.5) < 0.02


def test_overlap_across_meridian():
    from marswatch.geometry import overlap

    a = _obs(0.0, 0.1, 359.95, 360.05)
    b = _obs(0.0, 0.1, 0.0, 0.1)
    b2 = {**b, "c1_lon": 0.0, "c2_lon": 0.1, "c3_lon": 0.1, "c4_lon": 0.0}
    assert overlap(a, b2) is not None


# ---------------------------------------------------------------- registration
def test_coarse_offset_recovers_translation(hirise_crop):
    from marswatch.registration import coarse_offset

    v = np.ones_like(hirise_crop, bool)
    mov = shift_image(hirise_crop, 13, -7)  # SYNTHETIC known shift of real imagery
    c = coarse_offset(hirise_crop, v, mov, v, res_m=1.0, max_shift_m=40)
    assert c.ok
    assert abs(c.dx_m - 13) < 1.0 and abs(c.dy_m - 7) < 1.0  # y north-positive


def test_fine_register_subpixel(hirise_crop):
    from marswatch.registration import fine_register

    v = np.ones_like(hirise_crop, bool)
    mov = shift_image(hirise_crop, 2.4, -1.7) * 0.6 + 0.01  # SYNTHETIC shift + gain/offset change
    fr = fine_register(hirise_crop, v, mov.astype(np.float32), v, res_m=0.5, patch=64, step=48, search=10)
    inner = (slice(60, -60), slice(60, -60))
    assert abs(float(np.median(fr.flow_x[inner])) - 2.4) < 0.25
    assert abs(float(np.median(fr.flow_y[inner])) + 1.7) < 0.25
    assert fr.diagnostics.check_rms_px < 0.5
    assert fr.diagnostics.status in ("good", "marginal")


def test_registration_flags_unrelated_images(hirise_crop):
    from marswatch.registration import fine_register

    rng = np.random.default_rng(0)
    noise = rng.normal(0.2, 0.02, hirise_crop.shape).astype(np.float32)
    v = np.ones_like(hirise_crop, bool)
    fr = fine_register(hirise_crop, v, noise, v, res_m=0.5)
    assert fr.diagnostics.status == "poor"


# ---------------------------------------------------------------- radiometry
def test_radiometric_match_robust_to_changes(hirise_crop):
    from marswatch.normalize import radiometric_match

    after = hirise_crop * 0.45 + 0.02
    after[200:260, 200:260] *= 0.5  # SYNTHETIC localized darkening (a "change")
    v = np.ones_like(after, bool)
    bm, info = radiometric_match(hirise_crop, after, v, block_px=1024)
    assert abs(info["global_gain"] - 0.45) < 0.03
    resid = (after - bm)[v]
    assert np.median(np.abs(resid)) < 0.002


# ---------------------------------------------------------------- detection
def test_injected_blast_zone_detected_and_noise_not(hirise_crop):
    from marswatch.detect.classical import detect
    from marswatch.validation import _inject

    rng = np.random.default_rng(1)
    v = np.ones_like(hirise_crop, bool)
    before = hirise_crop + rng.normal(0, 0.001, hirise_crop.shape).astype(np.float32)
    after = hirise_crop + rng.normal(0, 0.001, hirise_crop.shape).astype(np.float32)
    q = np.ones_like(hirise_crop)
    clean = detect(before, after, v, q, 0.5, 0.3)
    assert sum(1 for c in clean.components if c["max_abs_z"] > 8) == 0
    inj = _inject(after, (256, 256), diameter_px=8, contrast=0.2, sun_angle=0.0)  # SYNTHETIC injection
    r = detect(before, inj, v, q, 0.5, 0.3)
    hits = [c for c in r.components if abs(c["centroid_rc"][0] - 256) < 30 and abs(c["centroid_rc"][1] - 256) < 30]
    assert hits and hits[0]["polarity"] == "darkening"


def test_fusion_labels_shadow_dipole_as_artifact():
    from marswatch.detect.fuse import FusionContext, fuse_one

    comp = {"label": 1, "area_px": 200, "area_m2": 50.0, "eq_diameter_m": 8.0, "centroid_rc": [10.0, 10.0],
            "bbox": [0, 0, 20, 20], "polarity": "darkening", "frac_dark": 1.0, "mean_abs_z": 6.0, "max_abs_z": 9.0,
            "mean_diff": -0.01, "mean_ssim": 0.5, "eccentricity": 0.5, "elongation": 1.4, "major_axis_m": 9.0,
            "minor_axis_m": 6.0, "orientation_deg": 0.0, "solidity": 0.9, "extent": 0.7}
    f = {"crater_resp_after": 0.3, "crater_resp_before": 0.3, "crater_resp_gain": 0.0, "crater_radius_m": 2.0,
         "angular_coverage": 0.2, "ray_contrast": 0.1, "center_dark_ratio": 1.0, "taper": 1.0,
         "grad_energy_log_ratio": 0.0, "lbp_chi2": 0.0, "new_edge_frac": 0.1, "relief_index": 2.0, "dipole": 0.9,
         "local_reg_quality": 0.8, "near_mask_edge": False, "shadow_frac": 0.0, "contrast_log_ratio": 0.0}
    ctx = FusionContext(0.5, 10.0, 15.0, 5.0, 10.0, 0.0, 0.0, 0.8, 0.5)
    c = fuse_one(comp, f, ctx)
    assert c["category"] == "illumination_or_registration_artifact"
    from marswatch.detect.fuse import classify_status

    assert classify_status(c, []) == "likely_artifact"


def test_structure_snr_separates_noise(hirise_crop):
    from marswatch.imagery import structure_snr

    v = np.ones_like(hirise_crop, bool)
    noise = np.random.default_rng(3).normal(0.2, 0.02, hirise_crop.shape).astype(np.float32)
    assert structure_snr(hirise_crop, v) > 3.0
    assert structure_snr(noise, v) < 1.5


def test_sun_vector_convention():
    from marswatch.detect.features import sun_vector_angle

    # PDS: azimuth clockwise from 3 o'clock; NORTH_AZIMUTH=270 => north up. Sun due west => 180.
    a = sun_vector_angle(180.0, 270.0)
    assert abs(math.cos(a) + 1) < 1e-9  # points toward -x (west) in a north-up y-down frame
    a = sun_vector_angle(90.0, 270.0)
    assert abs(math.sin(a) - 1) < 1e-9  # toward +y (south)


# ---------------------------------------------------------------- worker / queue
def test_queue_dedupe_retry_and_pause(tmp_db, monkeypatch):
    from marswatch import worker

    jid = worker.enqueue(tmp_db, "analyze_pair", {"before_id": "A", "after_id": "B"}, dedupe_key="k1")
    assert jid and worker.enqueue(tmp_db, "analyze_pair", {"before_id": "A", "after_id": "B"}, dedupe_key="k1") is None
    calls = {"n": 0}

    def boom(db, job):
        calls["n"] += 1
        raise RuntimeError("network down")

    monkeypatch.setattr(worker, "execute", boom)
    j = worker.claim(tmp_db)
    worker.run_one(tmp_db, j)
    row = tmp_db.one("SELECT * FROM jobs WHERE id=?", [jid])
    assert row["status"] == "queued" and row["attempts"] == 1 and "retry" in row["stage"]
    assert worker.claim(tmp_db) is None  # backoff not elapsed
    tmp_db.update("jobs", "id", jid, {"started_at": 0, "attempts": 3})
    j = worker.claim(tmp_db)
    worker.run_one(tmp_db, j)
    assert tmp_db.one("SELECT status FROM jobs WHERE id=?", [jid])["status"] == "failed"
    worker.set_paused(tmp_db, True)
    assert worker.is_paused(tmp_db)
    tmp_db.insert("jobs", {"kind": "analyze_pair", "dedupe_key": "k2", "status": "running", "params": {}})
    assert worker.recover_stale(tmp_db) == 1


def test_input_rejection_not_retried(tmp_db, monkeypatch):
    from marswatch import worker
    from marswatch.pipeline import InputRejected

    jid = worker.enqueue(tmp_db, "analyze_pair", {"x": 1})

    def rej(db, job):
        raise InputRejected("structure SNR 1.0")

    monkeypatch.setattr(worker, "execute", rej)
    worker.run_one(tmp_db, worker.claim(tmp_db))
    row = tmp_db.one("SELECT * FROM jobs WHERE id=?", [jid])
    assert row["status"] == "failed" and row["stage"] == "rejected_input"


# ---------------------------------------------------------------- validation summary
def test_summarize_counts():
    from marswatch.validation import summarize

    def run(kind, match=None, cands=(), d_inc=3.0):
        return {"kind": kind, "d_incidence": d_inc, "d_sun_azimuth": 5.0, "dt_days": 400, "area_km2": 1.0,
                "seconds": 10.0, "registration": {"quality": 0.8, "check_rms_px": 0.5, "check_p90_px": 0.8, "checkpoints": 50,
                                                 "ncc_after": 0.7, "coarse_dx_m": 30.0, "coarse_dy_m": 40.0, "status": "good"},
                "candidates": list(cands), "match": match, "nearest_dist_m": 10.0}

    tp = {"score": 0.9, "category": "new_impact_crater", "status": "known_documented", "rank": 1, "dist_m": 5.0,
          "eq_diameter_m": 30.0, "max_abs_z": 10.0, "deep_z": 4.0, "methods": {}}
    fp = {"score": 0.5, "category": "other_change", "status": "plausible_unverified", "eq_diameter_m": 5.0, "max_abs_z": 6.0,
          "dist_to_ref_m": 400.0, "deep_z": 1.0, "methods": {}, "known_match": None}
    res = [{"ref_id": "R1", "diameter_m": 6.0, "runs": [run("positive", tp, [dict(tp, dist_to_ref_m=5.0, known_match="R1"), fp]),
                                                       run("neg:pre-pre", None, [fp])]},
           {"ref_id": "R2", "diameter_m": 2.0, "runs": [run("positive", None, [])]}]
    m = summarize(res)
    op0 = m["operating_points"][0]
    assert op0["recall_any_category"] == 0.5 and op0["tp"] == 1
    assert op0["fp_in_positive_windows"] == 1 and op0["fp_in_prepre_controls"] == 1
    assert m["ml_deep_z"]["auc"] == 1.0


def test_psf_match_reduces_blur_rings(hirise_crop):
    from marswatch.normalize import psf_match

    import cv2

    v = np.ones_like(hirise_crop, bool)
    blurry = cv2.GaussianBlur(hirise_crop, (0, 0), 1.5)  # SYNTHETIC blur of real imagery
    raw = np.abs(blurry - hirise_crop)[20:-20, 20:-20].mean()
    b2, a2, info = psf_match(hirise_crop, blurry, v)
    assert info["applied"] and info["blurred"] == "before" and 1.0 <= info["sigma_px"] <= 2.0
    assert np.abs(a2 - b2)[20:-20, 20:-20].mean() < 0.5 * raw
