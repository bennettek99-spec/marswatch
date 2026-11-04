"""End-to-end analysis of one observation pair over one area of interest (AOI).

Outputs (``data/runs/<run_id>/``):

* ``before.jpg``/``after.jpg`` — co-registered, radiometrically matched display images
* ``after_raw.jpg`` — after image with geo-offset only (to inspect registration)
* ``heat.png`` — signed change z-score heatmap (RGBA, transparent where no change)
* ``mask.png`` — detection outlines
* ``*.dzi`` + ``*_files/`` — deep-zoom pyramids for the web viewer
* ``chips/cand_<n>.jpg`` — before | after | z chips for each candidate
* ``run.json`` — full parameters, registration diagnostics, statistics, candidates
* ``report.md`` — human-readable, reproducible analysis report
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .align import AlignedPair, align_pair
from .archive.reference import nearby_references
from .config import settings
from .db import Database, get_db
from .detect import fuse, ml
from .detect.classical import ClassicalParams, detect
from .discovery import make_pair_id, score_pair
from .geometry import angular_diff, footprint, haversine_m
from .imagery import (QC_MIN_SNR, Grid, RemoteImage, cog_url, grid_for_polygon, input_quality, make_grid,
                      pds_jp2_url, uahirise_url)
from .log import get_logger
from .normalize import radiometric_match, to_display

log = get_logger("pipeline")

PIPELINE_VERSION = "0.3.0"


MAX_FALLBACK_RES_M = 4.0


def regrid(grid: Grid, res_m: float) -> Grid:
    """Same footprint, different pixel size."""
    t = list(grid.transform)
    w_m, h_m = grid.width * grid.res, grid.height * grid.res
    return Grid(grid.crs_wkt, (res_m, 0.0, t[2], 0.0, -res_m, t[5]), int(math.ceil(w_m / res_m)), int(math.ceil(h_m / res_m)))


class InputRejected(RuntimeError):
    """An input observation failed quality control (no usable surface signal)."""


def _hash_sources() -> str:
    h = hashlib.sha1()
    for p in sorted(Path(__file__).parent.rglob("*.py")):
        h.update(p.read_bytes())
    return f"{PIPELINE_VERSION}+{h.hexdigest()[:10]}"


# Computed once at import so the recorded version always matches the code actually loaded
_CODE_VERSION = _hash_sources()


def code_version() -> str:
    """Hash of all package sources at import time: identifies the exact algorithm version of a run."""
    return _CODE_VERSION


def _obs(db: Database, pid: str) -> dict:
    o = db.one("SELECT * FROM observations WHERE product_id=?", [pid])
    if not o:
        raise KeyError(f"observation {pid} not in index; run `marswatch index` first")
    return o


def _write_dzi(img: np.ndarray, out_base: Path, fmt: str = "jpg", tile: int = 256, overlap: int = 1) -> None:
    """Minimal Deep Zoom (DZI) pyramid writer (OpenSeadragon compatible)."""
    h, w = img.shape[:2]
    max_level = int(math.ceil(math.log2(max(w, h))))
    files = Path(str(out_base) + "_files")
    files.mkdir(parents=True, exist_ok=True)
    level_img = img
    for level in range(max_level, -1, -1):
        lh, lw = level_img.shape[:2]
        d = files / str(level)
        d.mkdir(exist_ok=True)
        for ty in range(0, max(1, math.ceil(lh / tile))):
            for tx in range(0, max(1, math.ceil(lw / tile))):
                x0 = max(0, tx * tile - overlap)
                y0 = max(0, ty * tile - overlap)
                x1 = min(lw, (tx + 1) * tile + overlap)
                y1 = min(lh, (ty + 1) * tile + overlap)
                t = level_img[y0:y1, x0:x1]
                params = [cv2.IMWRITE_JPEG_QUALITY, 88] if fmt == "jpg" else [cv2.IMWRITE_PNG_COMPRESSION, 6]
                cv2.imwrite(str(d / f"{tx}_{ty}.{fmt}"), t, params)
        nh, nw = max(1, (lh + 1) // 2), max(1, (lw + 1) // 2)
        level_img = cv2.resize(level_img, (nw, nh), interpolation=cv2.INTER_AREA)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" '
           f'Format="{fmt}" Overlap="{overlap}" TileSize="{tile}"><Size Height="{h}" Width="{w}"/></Image>')
    Path(str(out_base) + ".dzi").write_text(xml)


def heat_rgba(z: np.ndarray, mask_valid: np.ndarray, zmax: float = 10.0, zmin_show: float = 2.5) -> np.ndarray:
    """Signed z heatmap: darkening = orange-red, brightening = cyan-blue, transparent below zmin_show."""
    a = np.clip((np.abs(z) - zmin_show) / (zmax - zmin_show), 0, 1)
    rgba = np.zeros(z.shape + (4,), np.uint8)
    dark = z < 0
    # BGR(A) for OpenCV
    rgba[..., 2] = np.where(dark, 255, 40)
    rgba[..., 1] = np.where(dark, (90 + 120 * (1 - a)).astype(np.uint8), (200 * a + 55).astype(np.uint8))
    rgba[..., 0] = np.where(dark, 30, 255)
    rgba[..., 3] = (a * 230 * mask_valid).astype(np.uint8)
    return rgba


def run_pair(before_id: str, after_id: str, aoi: dict | None = None, *, db: Database | None = None,
             job_id: int | None = None, res_m: float | None = None, params: ClassicalParams | None = None,
             use_ml: bool = True, use_cache: bool = True, write_tiles: bool = True,
             progress: Callable[[float, str], None] | None = None, run_kind: str = "survey",
             max_area_km2: float | None = None) -> dict:
    """Analyse one pair. ``aoi`` = {"lat","lon","half_size_m"} for a window, or None for the full overlap."""
    db = db or get_db()
    t_start = time.time()
    prog = progress or (lambda f, s: None)
    res_m = res_m or settings.work_resolution_m
    params = params or ClassicalParams()
    ob, oa = _obs(db, before_id), _obs(db, after_id)
    pinfo = score_pair(ob, oa)
    if pinfo is None:
        raise ValueError(f"{before_id} and {after_id} do not overlap")
    if pinfo.before_id != before_id:
        before_id, after_id, ob, oa = after_id, before_id, oa, ob
    pair_id = make_pair_id(before_id, after_id)
    if not db.one("SELECT 1 FROM pairs WHERE pair_id=?", [pair_id]):
        db.insert("pairs", pinfo.to_row(source=run_kind))
    run_id = f"{pair_id}__{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    out = settings.runs_dir / run_id
    (out / "chips").mkdir(parents=True, exist_ok=True)
    rlog = get_logger("pipeline", run_id=run_id, job_id=job_id, pair_id=pair_id)

    if aoi:
        grid = make_grid(aoi["lat"], aoi["lon"], aoi["half_size_m"], aoi["half_size_m"], res_m)
    else:
        from shapely import wkt as _wkt

        grid = grid_for_polygon(_wkt.loads(pinfo.overlap_wkt), res_m,
                                max_area_km2=max_area_km2 or settings.max_pair_area_km2)
    area_km2 = grid.width * grid.height * res_m * res_m / 1e6
    run_params = {"res_m": res_m, "aoi": aoi, "classical": asdict(params), "use_ml": use_ml,
                  "grid": grid.to_dict(), "max_area_km2": max_area_km2 or settings.max_pair_area_km2}
    db.insert("runs", {"run_id": run_id, "pair_id": pair_id, "job_id": job_id, "kind": run_kind,
                       "params": run_params, "code_version": code_version(), "started_at": t_start,
                       "out_dir": str(out), "status": "running", "area_km2": area_km2})
    rlog.info(f"run {run_id}: grid {grid.width}x{grid.height} @ {res_m} m ({area_km2:.2f} km²)")
    timings: dict[str, float] = {}

    # ---- 0. input quality control --------------------------------------------------
    prog(0.02, "input quality control")
    cx, cy = grid.width / 2, grid.height / 2
    clon, clat = grid.pixel_to_lonlat(cx, cy)
    qc = [input_quality(RemoteImage(pid), clat, clon) for pid in (before_id, after_id)]
    run_params["input_qc"] = qc
    bad = [q for q in qc if not q["usable"]]
    low_snr_reason = "; ".join(f"{q['product_id']} structure SNR {q['structure_snr']} < {QC_MIN_SNR} "
                               f"(atmospheric opacity / haze / dust storm suspected)" for q in bad)

    def reject(reason: str) -> None:
        db.update("runs", "run_id", run_id, {"status": "rejected_input", "finished_at": time.time(),
                                              "params": run_params, "stats": {"rejected": reason, "n_candidates": 0}})
        db.update("pairs", "pair_id", pair_id, {"status": "rejected_input", "suitability_notes": reason})
        rlog.warning(f"input rejected: {reason}")
        raise InputRejected(reason)

    # ---- 1. read + register -------------------------------------------------------
    prog(0.05, "registering")
    t = time.time()
    tiled = grid.width * grid.height > 4096 * 4096
    ap: AlignedPair = align_pair(RemoteImage(before_id, ob["pds_path"]), RemoteImage(after_id, oa["pds_path"]),
                                 grid, use_cache=use_cache, tiled=tiled,
                                 progress=lambda f: prog(0.05 + 0.4 * f, "reading imagery"))
    # Resolution fallback: relief parallax / jitter that cannot be modelled at full resolution is often
    # sub-pixel at coarser scales, where metre-to-decametre changes (slope streaks, blast zones) remain visible.
    res_history = [{"res_m": res_m, "quality": ap.fine.diagnostics.quality, "status": ap.fine.diagnostics.status}]
    while ap.fine.diagnostics.status == "poor" and res_m * 2 <= MAX_FALLBACK_RES_M:
        res_m *= 2
        grid = regrid(grid, res_m)
        rlog.warning(f"registration poor; retrying at {res_m} m/px")
        prog(0.3, f"registration poor: retrying at {res_m} m/px")
        ap = align_pair(RemoteImage(before_id, ob["pds_path"]), RemoteImage(after_id, oa["pds_path"]), grid,
                        use_cache=use_cache, tiled=False)
        res_history.append({"res_m": res_m, "quality": ap.fine.diagnostics.quality, "status": ap.fine.diagnostics.status})
    if len(res_history) > 1:
        ap.fine.diagnostics.warnings.append(
            "resolution fallback: " + " → ".join(f"{h['res_m']} m ({h['status']}, q={h['quality']:.2f})" for h in res_history))
        run_params["res_m_requested"] = run_params["res_m"]
        run_params["res_m"] = res_m
        run_params["grid"] = grid.to_dict()
        run_params["resolution_history"] = res_history
    timings["read_register_s"] = time.time() - t
    diag = ap.fine.diagnostics
    valid = ap.valid
    # Low SNR alone is not fatal: if the images still register, they demonstrably contain surface signal.
    if bad and (diag.quality < 0.2 or not ap.coarse.ok):
        reject(low_snr_reason + f"; registration also failed (quality {diag.quality:.2f})")
    if bad:
        diag.warnings.append("low structure SNR: " + low_snr_reason)
    if valid.mean() < 0.05:
        raise RuntimeError(f"insufficient valid overlap in AOI ({valid.mean() * 100:.1f}%)")

    # ---- 2. normalise + detect -----------------------------------------------------
    prog(0.5, "detecting")
    t = time.time()
    bm, rad_info = radiometric_match(ap.before, ap.after, valid)
    resid = diag.check_rms_px if diag.check_rms_px and np.isfinite(diag.check_rms_px) else 1.0
    cr = detect(bm, ap.after, valid, ap.fine.quality_map, res_m, resid, params)
    timings["detect_A_s"] = time.time() - t
    t = time.time()
    sun_after = fuse.sun_vector_angle(oa["sub_solar_azimuth"], oa["north_azimuth"])
    sun_before = fuse.sun_vector_angle(ob["sub_solar_azimuth"], ob["north_azimuth"])
    ctx = fuse.FusionContext(res_m=res_m, center_lat=pinfo.center_lat, d_incidence=pinfo.d_incidence,
                             d_ls=pinfo.d_ls, d_sun_azimuth=pinfo.d_sun_azimuth, sun_angle_after=sun_after,
                             sun_angle_before=sun_before, reg_quality=diag.quality, reg_rms_px=resid,
                             low_snr=bool(bad))
    cands = fuse.characterise(bm, ap.after, cr, ap.fine.quality_map, ctx)
    timings["detect_B_s"] = time.time() - t
    t = time.time()
    ml_info = {"enabled": False}
    if use_ml and ml.available():
        try:
            ml_info = ml.score_candidates(bm, ap.after, cr.analysis_mask, cands[:150], res_m)
        except Exception as e:  # ML is optional evidence; never fail the run on it
            rlog.warning(f"ML scoring failed: {e}")
            ml_info = {"enabled": False, "error": str(e)}
    timings["detect_C_s"] = time.time() - t
    # recompute scores to include ML agreement
    for c in cands:
        if c["methods"].get("C_deep_features"):
            c["score"] = round(min(1.0, c["score"] * 1.08), 4)

    # ---- 3. georeference candidates, reference matching, status ---------------------
    prog(0.8, "georeferencing & classifying")
    from affine import Affine

    sh_aff = Affine(*grid.transform[:6])
    sh_aff = Affine(sh_aff.a, sh_aff.b, sh_aff.c + diag.coarse_dx_m, sh_aff.d, sh_aff.e, sh_aff.f + diag.coarse_dy_m)
    from pyproj import CRS

    from .geometry import from_local

    tf = from_local(CRS.from_wkt(grid.crs_wkt))
    for c in cands:
        rc = c["features"].get("blob_rc") or c["centroid_rc"]
        r, col = rc
        lon_b, lat_b = grid.pixel_to_lonlat(col + 0.5, r + 0.5)
        ri, ci = int(min(max(r, 0), grid.height - 1)), int(min(max(col, 0), grid.width - 1))
        fx, fy = float(ap.fine.flow_x[ri, ci]), float(ap.fine.flow_y[ri, ci])
        xa, ya = sh_aff * (col + 0.5 + fx, r + 0.5 + fy)
        lon_a, lat_a = tf.transform(xa, ya)
        c["lat"], c["lon"] = lat_b, lon_b % 360
        c["lat_after_frame"], c["lon_after_frame"] = lat_a, lon_a % 360
        assoc = associate_references(db, c, grid, diag, oa, ob, res_m)
        known = [a for a in assoc if a["association"] in ("direct", "cluster")]
        c["reference_associations"] = assoc
        c["known_match"] = known[0]["ref_id"] if known else None
        if known:
            k = known[0]
            how = ("inside detected region" if k["inside_region"] else f"{k['distance_m']:.0f} m away") \
                if k["association"] == "direct" else f"{k['distance_m']:.0f} m away, within dispersion radius of a catalogued cluster impact"
            c["evidence_for"].append(f"coincides with catalogued change {k['ref_id']} ({how}; {k['category']}, D={k['diameter_m']} m; "
                                     f"{k['source'].split(';')[0]})")
        c["classification"] = fuse.classify_status(c, known)

    # ---- 4. outputs ------------------------------------------------------------------
    prog(0.85, "writing outputs")
    t = time.time()
    b8, stretch = to_display(bm, valid)
    a8, _ = to_display(ap.after, valid, ref=stretch)
    araw8, _ = to_display(ap.after_raw, ap.before_valid & (ap.after_raw > 0))
    cv2.imwrite(str(out / "before.jpg"), b8, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(out / "after.jpg"), a8, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(out / "after_raw.jpg"), araw8, [cv2.IMWRITE_JPEG_QUALITY, 85])
    heat = heat_rgba(cr.z, cr.analysis_mask)
    cv2.imwrite(str(out / "heat.png"), heat)
    outl = np.zeros(cr.mask.shape + (4,), np.uint8)
    cnts, _ = cv2.findContours(cr.mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(outl, cnts, -1, (0, 255, 255, 255), max(1, int(round(min(grid.width, grid.height) / 800))))
    cv2.imwrite(str(out / "mask.png"), outl)
    # quality map
    cv2.imwrite(str(out / "regquality.png"), (np.clip(ap.fine.quality_map, 0, 1) * 255).astype(np.uint8))
    if write_tiles:
        _write_dzi(b8, out / "before")
        _write_dzi(a8, out / "after")
        _write_dzi(heat, out / "heat", fmt="png")
        _write_dzi(outl, out / "mask", fmt="png")
    # chips
    zc = np.clip(cr.z / 10, -1, 1)
    for i, c in enumerate(cands[:120]):
        rc = c["centroid_rc"]
        half = int(max(48, min(400, 1.6 * c["major_axis_m"] / res_m)))
        r0, c0 = int(rc[0]), int(rc[1])
        sl = (slice(max(0, r0 - half), r0 + half), slice(max(0, c0 - half), c0 + half))
        zz = zc[sl]
        zrgb = np.dstack([np.clip(zz, 0, 1) * 255, np.zeros_like(zz), np.clip(-zz, 0, 1) * 255]).astype(np.uint8)  # BGR: blue=brighter, red=darker
        tiles = [cv2.cvtColor(b8[sl], cv2.COLOR_GRAY2BGR), cv2.cvtColor(a8[sl], cv2.COLOR_GRAY2BGR), zrgb]
        sz = 256
        tiles = [cv2.resize(x, (sz, sz), interpolation=cv2.INTER_AREA if x.shape[0] > sz else cv2.INTER_NEAREST) for x in tiles]
        sep = np.full((sz, 4, 3), 255, np.uint8)
        name = f"cand_{i:03d}.jpg"
        cv2.imwrite(str(out / "chips" / name), np.hstack([tiles[0], sep, tiles[1], sep, tiles[2]]))
        c["chip"] = f"chips/{name}"
        c["chip_half_px"] = half
    timings["outputs_s"] = time.time() - t
    timings["total_s"] = time.time() - t_start

    stats = {
        "n_candidates": len(cands),
        "by_category": {k: sum(1 for c in cands if c["category"] == k) for k in fuse.CATEGORIES},
        "by_status": {k: sum(1 for c in cands if c["classification"] == k)
                      for k in ("known_documented", "plausible_unverified", "likely_artifact", "insufficient_evidence")},
        "noise_sigma_IF": cr.noise_sigma,
        "valid_fraction": float(valid.mean()),
        "analysed_fraction": float(cr.analysis_mask.mean()),
        "analysed_km2": float(cr.analysis_mask.sum() * res_m * res_m / 1e6),
        "radiometry": rad_info,
        "ml": ml_info,
        "timings": timings,
    }
    sources = {
        k: {"product_id": o["product_id"], "observation_id": o["observation_id"], "start_time": o["start_time"],
            "cog_url": cog_url(o["product_id"]), "pds_jp2_url": pds_jp2_url(o["pds_path"]),
            "uahirise_url": uahirise_url(o["observation_id"]), "incidence": o["incidence"], "emission": o["emission"],
            "solar_longitude": o["solar_longitude"], "map_scale": o["map_scale"], "rationale": o["rationale"],
            "sub_solar_azimuth": o["sub_solar_azimuth"]}
        for k, o in (("before", ob), ("after", oa))
    }
    run_doc = {
        "run_id": run_id, "pair_id": pair_id, "kind": run_kind, "code_version": code_version(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
        "params": run_params, "pair": asdict(pinfo), "sources": sources,
        "registration": diag.to_dict(), "stats": stats,
        "grid_bounds_lonlat": [grid.pixel_to_lonlat(0, 0), grid.pixel_to_lonlat(grid.width, grid.height)],
        "candidates": cands,
    }
    (out / "run.json").write_text(json.dumps(run_doc, indent=1, default=_jd))
    (out / "report.md").write_text(render_report(run_doc))

    # ---- 5. database ---------------------------------------------------------------
    for c in cands:
        db.insert("candidates", {
            "run_id": run_id, "pair_id": pair_id, "lat": c["lat"], "lon": c["lon"],
            "px_x": c["centroid_rc"][1], "px_y": c["centroid_rc"][0], "bbox": c["bbox"],
            "area_m2": c["area_m2"], "eq_diameter_m": c["eq_diameter_m"], "category": c["category"],
            "score": c["score"], "score_kind": "heuristic", "polarity": c["polarity"],
            "registration_quality": c["features"].get("local_reg_quality"), "methods": c["methods"],
            "evidence_for": c["evidence_for"], "evidence_against": c["evidence_against"],
            "classification": c["classification"], "known_match": c["known_match"],
            "chips": {"chip": c.get("chip")}, "features": {**c["features"], "max_abs_z": c["max_abs_z"],
                                                          "mean_ssim": c["mean_ssim"], "elongation": c["elongation"],
                                                          "lat_after_frame": c["lat_after_frame"],
                                                          "lon_after_frame": c["lon_after_frame"],
                                                          "artifact_index": c["artifact_index"]},
            "created_at": time.time(),
        })
    db.update("runs", "run_id", run_id, {"finished_at": time.time(), "registration": diag.to_dict(),
                                          "stats": stats, "status": "done"})
    db.update("pairs", "pair_id", pair_id, {"status": "analysed"})
    prog(1.0, "done")
    rlog.info(f"run complete: {len(cands)} candidates, {stats['by_status']}, {timings['total_s']:.1f}s")
    return run_doc


CLUSTER_RADIUS_M = 500.0


def associate_references(db: Database, c: dict, grid: Grid, diag, oa: dict, ob: dict, res_m: float) -> list[dict]:
    """Relate a candidate to catalogued changes formed within the pair's time window.

    * ``direct``  — the reference point lies inside the candidate's region (bbox + 20 m),
      or within max(100 m, 1.5 D) of its position (either pointing frame);
    * ``cluster`` — the reference is a catalogued *cluster* impact within 500 m
      (fragments of one impactor disperse over hundreds of metres);
    * ``nearby``  — anything else within 600 m (reported, not counted as a match).
    Positions are compared in the after-image pointing frame, where the catalogue
    coordinates were found to agree (RESEARCH_LOG 2026-11-04).
    """
    lat_a, lon_a = c["lat_after_frame"], c["lon_after_frame"]
    refs = nearby_references(db, lat_a, lon_a, 600.0)
    out = []
    r0, c0, r1, c1 = c["bbox"]
    m = 20.0 / res_m
    for k in refs:
        if not ((k["after_date"] or "9999") <= oa["start_time"][:10] and (k["before_date"] or "0000") >= ob["start_time"][:10]):
            continue
        col_a, row_a = grid.lonlat_to_pixel(k["lon"], k["lat"])
        col = col_a - diag.coarse_dx_m / res_m
        row = row_a + diag.coarse_dy_m / res_m
        inside = (r0 - m) <= row <= (r1 + m) and (c0 - m) <= col <= (c1 + m)
        d = min(k["distance_m"], haversine_m(c["lat"], c["lon"], k["lat"], k["lon"]))
        cluster = str((k.get("attrs") or {}).get("single_or_cluster", "")).lower().startswith("cluster")
        if inside or d <= max(100.0, 1.5 * c["eq_diameter_m"]):
            kind = "direct"
        elif (cluster and d <= CLUSTER_RADIUS_M and c["polarity"] in ("darkening", "mixed")
              and c.get("artifact_index", 0) < 0.5):
            kind = "cluster"
        else:
            kind = "nearby"
        out.append({"ref_id": k["ref_id"], "association": kind, "inside_region": bool(inside), "distance_m": float(d),
                    "category": k["category"], "diameter_m": k["diameter_m"], "source": k["source"]})
    order = {"direct": 0, "cluster": 1, "nearby": 2}
    return sorted(out, key=lambda a: (order[a["association"]], a["distance_m"]))


def _jd(o):
    if isinstance(o, (np.generic,)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def render_report(doc: dict) -> str:
    s, reg, st = doc["sources"], doc["registration"], doc["stats"]
    lines = [
        f"# MARSWATCH analysis report — {doc['pair_id']}",
        "",
        f"* Run ID: `{doc['run_id']}`  ",
        f"* Created: {doc['created']}  ",
        f"* Code version: `{doc['code_version']}`  ",
        f"* Kind: {doc['kind']}",
        "",
        "## Source observations (NASA/JPL/University of Arizona HiRISE, via PDS and USGS ARD COGs)",
        "",
        "| role | product | acquired | incidence | emission | Ls | scale (m/px) | rationale |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in ("before", "after"):
        o = s[k]
        lines.append(f"| {k} | [{o['product_id']}]({o['uahirise_url']}) | {o['start_time']} | {o['incidence']:.1f}° | "
                     f"{o['emission']:.1f}° | {o['solar_longitude']:.1f}° | {o['map_scale']} | {o['rationale']} |")
    lines += ["", "Data links:", ""]
    for k in ("before", "after"):
        o = s[k]
        lines.append(f"* {k}: PDS RDR {o['pds_jp2_url']} ; COG {o['cog_url']}")
    p = doc["pair"]
    lines += [
        "",
        "## Pair geometry",
        "",
        f"Δt = {p['dt_days']:.0f} days; Δincidence = {p['d_incidence']:.1f}°; Δsun azimuth = {p['d_sun_azimuth']:.0f}°; "
        f"Δemission = {p['d_emission']:.1f}°; ΔLs = {p['d_ls']:.0f}°; overlap {p['overlap_km2']:.2f} km²; "
        f"suitability (heuristic) {p['suitability']:.2f}.",
        "",
        "## Registration diagnostics",
        "",
        f"* Coarse offset (uncontrolled pointing): dx = {reg['coarse_dx_m']:.1f} m, dy = {reg['coarse_dy_m']:.1f} m",
        f"* Patch matches: {reg['n_matched']}/{reg['n_patches']} (RANSAC inliers {reg['n_inliers']})",
        f"* Held-out checkpoint residual: RMS {reg['check_rms_px']} px, P90 {reg['check_p90_px']} px "
        f"({reg['checkpoints']} checkpoints)",
        f"* High-pass NCC before→after registration: {reg['ncc_before']:.2f} → {reg['ncc_after']:.2f}",
        f"* Overall registration quality: {reg['quality']:.2f} ({reg['status']})",
    ]
    for w in reg.get("warnings", []):
        lines.append(f"* ⚠ {w}")
    lines += [
        "",
        "## Detection summary",
        "",
        f"Analysed area {st['analysed_km2']:.2f} km² at {doc['params']['res_m']} m/px. "
        f"Robust noise σ = {st['noise_sigma_IF']:.4g} I/F. Candidates: {st['n_candidates']}.",
        "",
        "By status: " + ", ".join(f"{k}: {v}" for k, v in st["by_status"].items()),
        "",
        "By category: " + ", ".join(f"{k}: {v}" for k, v in st["by_category"].items() if v),
        "",
        "## Top candidates (heuristic score — not a probability)",
        "",
    ]
    for i, c in enumerate(doc["candidates"][:15]):
        lines += [
            f"### #{i} — {c['category']} — {c['classification']} — score {c['score']:.2f}",
            "",
            f"Location (before-image frame): {c['lat']:.5f}°N, {c['lon']:.5f}°E; (after-image frame): "
            f"{c['lat_after_frame']:.5f}°N, {c['lon_after_frame']:.5f}°E. Area {c['area_m2']:.0f} m², "
            f"equivalent diameter {c['eq_diameter_m']:.1f} m.",
            "",
            f"![chip]({c.get('chip', '')})",
            "",
            "Evidence for: " + "; ".join(c["evidence_for"]),
            "",
            "Evidence against: " + ("; ".join(c["evidence_against"]) or "none recorded"),
            "",
        ]
    lines += [
        "## Reproduce",
        "",
        "```bash",
        f"marswatch analyze {s['before']['product_id']} {s['after']['product_id']}"
        + (f" --lat {doc['params']['aoi']['lat']} --lon {doc['params']['aoi']['lon']} --half {doc['params']['aoi']['half_size_m']}"
           if doc["params"].get("aoi") else "") + f" --res {doc['params']['res_m']}",
        "```",
        "",
        "Caveat: software detections are *candidates*. None is a confirmed discovery without expert review and, "
        "ideally, independent confirmation in further observations.",
    ]
    return "\n".join(lines)
