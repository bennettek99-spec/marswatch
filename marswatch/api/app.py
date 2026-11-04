"""MARSWATCH FastAPI backend.

Serves the JSON API under ``/api``, run outputs under ``/runs`` and the built
React dashboard (``frontend/dist``) at ``/``. Set ``MARSWATCH_EMBED_WORKER=1``
to run the autonomous worker inside the API process so the dashboard's
pause/resume/retry controls act on a live worker.
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Literal

import psutil
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..archive.reference import nearby_references
from ..config import REPO_ROOT, settings
from ..db import get_db
from ..discovery import observations_covering, score_pair
from ..imagery import ReadStats, cache_size_bytes, cog_thumbnail_url, cog_url, pds_jp2_url, uahirise_url
from ..log import configure
from ..worker import Worker, analyze_key, enqueue, is_paused, set_paused

configure()
app = FastAPI(title="MARSWATCH", version="0.3.0", description="Mars surface change detection with public HiRISE data")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
settings.ensure_dirs()
app.mount("/runs", StaticFiles(directory=str(settings.runs_dir)), name="runs")
_worker: Worker | None = None
STARTED = time.time()


@app.on_event("startup")
def _startup() -> None:
    global _worker
    if os.environ.get("MARSWATCH_EMBED_WORKER") == "1":
        _worker = Worker(get_db())
        _worker.start()


# ---------------------------------------------------------------------------
# overview
# ---------------------------------------------------------------------------

@app.get("/api/overview")
def overview() -> dict:
    db = get_db()
    runs = db.query("SELECT kind, status, stats, area_km2 FROM runs")
    done = [r for r in runs if r["status"] == "done"]
    area = sum((r["stats"] or {}).get("analysed_km2", 0) for r in done)
    by_status = {r["classification"]: r["n"] for r in db.query(
        "SELECT classification, COUNT(*) n FROM candidates c JOIN runs r ON r.run_id=c.run_id GROUP BY classification")}
    by_cat = {r["category"]: r["n"] for r in db.query("SELECT category, COUNT(*) n FROM candidates GROUP BY category")}
    jobs = {r["status"]: r["n"] for r in db.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
    val = db.one("SELECT id, created_at, metrics, code_version FROM validation_runs WHERE kind='crater_validation' ORDER BY id DESC LIMIT 1")
    vsum = None
    if val:
        m = val["metrics"]
        op = {o["threshold"]: o for o in m.get("operating_points", [])}
        vsum = {"id": val["id"], "created_at": val["created_at"], "code_version": val["code_version"],
                "n_cases": m.get("n_cases"), "operating_points": m.get("operating_points"),
                "recall_at_0": op.get(0.0, {}).get("recall_any_category"),
                "registration": m.get("registration_real"), "ml": m.get("ml_deep_z")}
    ho = db.one("SELECT id, metrics, code_version FROM validation_runs WHERE kind='crater_validation_holdout' ORDER BY id DESC LIMIT 1")
    holdout = None
    if ho:
        hm = ho["metrics"]
        hop = {o["threshold"]: o for o in hm.get("operating_points", [])}
        holdout = {"id": ho["id"], "code_version": ho["code_version"], "n_positive_runs": hm.get("n_positive_runs"),
                   "recall_at_0": hop.get(0.0, {}).get("recall_any_category"),
                   "fp_per_km2_prepre_at_0": hop.get(0.0, {}).get("fp_per_km2_prepre"),
                   "operating_points": hm.get("operating_points")}
    timeline = db.query("SELECT started_at, finished_at, kind, area_km2 FROM runs WHERE status='done' ORDER BY started_at")
    return {
        "pairs_discovered": db.one("SELECT COUNT(*) n FROM pairs")["n"],
        "pairs_analysed": db.one("SELECT COUNT(DISTINCT pair_id) n FROM runs WHERE status='done'")["n"],
        "runs_done": len(done),
        "runs_by_kind": {k: sum(1 for r in done if r["kind"] == k) for k in {r["kind"] for r in done}},
        "area_km2": area,
        "candidates": sum(by_status.values()),
        "candidates_by_status": by_status,
        "candidates_by_category": by_cat,
        "observations_indexed": db.one("SELECT COUNT(*) n FROM observations")["n"],
        "reference_changes": db.one("SELECT COUNT(*) n FROM reference_changes")["n"],
        "jobs": jobs,
        "worker": {"paused": is_paused(db), "embedded": _worker is not None},
        "validation": vsum,
        "validation_holdout": holdout,
        "timeline": timeline,
    }


# ---------------------------------------------------------------------------
# runs & candidates
# ---------------------------------------------------------------------------

@app.get("/api/runs")
def list_runs(kind: str | None = None, limit: int = 200) -> list[dict]:
    db = get_db()
    sql = "SELECT run_id, pair_id, kind, status, started_at, finished_at, area_km2, registration, stats, code_version FROM runs"
    args: list[Any] = []
    if kind:
        sql += " WHERE kind=?"
        args.append(kind)
    sql += " ORDER BY started_at DESC LIMIT ?"
    args.append(limit)
    out = db.query(sql, args)
    for r in out:
        st = r.pop("stats") or {}
        r["n_candidates"] = st.get("n_candidates")
        r["by_status"] = st.get("by_status")
        r["analysed_km2"] = st.get("analysed_km2")
        reg = r.pop("registration") or {}
        r["registration"] = {k: reg.get(k) for k in ("quality", "status", "check_rms_px")}
    return out


def _run_doc(run_id: str) -> dict:
    p = settings.runs_dir / run_id / "run.json"
    if not p.exists():
        raise HTTPException(404, "run not found")
    return json.loads(p.read_text())


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    doc = _run_doc(run_id)
    db = get_db()
    ids = {(c["px_x"], c["px_y"]): c["id"] for c in db.query("SELECT id, px_x, px_y FROM candidates WHERE run_id=?", [run_id])}
    for c in doc["candidates"]:
        c["id"] = ids.get((c["centroid_rc"][1], c["centroid_rc"][0]))
    d = settings.runs_dir / run_id
    doc["assets"] = {k: f"/runs/{run_id}/{k}" for k in ("before.jpg", "after.jpg", "after_raw.jpg", "heat.png", "mask.png", "regquality.png")}
    doc["dzi"] = {k: f"/runs/{run_id}/{k}.dzi" for k in ("before", "after", "heat", "mask") if (d / f"{k}.dzi").exists()}
    return doc


@app.get("/api/runs/{run_id}/report", response_class=PlainTextResponse)
def run_report(run_id: str) -> str:
    p = settings.runs_dir / run_id / "report.md"
    if not p.exists():
        raise HTTPException(404)
    return p.read_text()


SORTABLE = {"score", "area_m2", "eq_diameter_m", "created_at", "lat", "lon", "registration_quality", "id"}


@app.get("/api/candidates")
def list_candidates(q: str | None = None, status: str | None = None, category: str | None = None,
                    kind: str | None = None, min_score: float = 0.0, sort: str = "score",
                    order: Literal["asc", "desc"] = "desc", limit: int = Query(100, le=2000), offset: int = 0) -> dict:
    db = get_db()
    where = ["c.score >= ?"]
    args: list[Any] = [min_score]
    if status:
        where.append("c.classification IN (%s)" % ",".join("?" * len(status.split(","))))
        args += status.split(",")
    if category:
        where.append("c.category IN (%s)" % ",".join("?" * len(category.split(","))))
        args += category.split(",")
    if kind:
        where.append("r.kind = ?")
        args.append(kind)
    if q:
        where.append("(c.pair_id LIKE ? OR c.known_match LIKE ? OR c.notes LIKE ? OR CAST(c.id AS TEXT) = ?)")
        args += [f"%{q}%", f"%{q}%", f"%{q}%", q]
    sort = sort if sort in SORTABLE else "score"
    w = " AND ".join(where)
    total = db.one(f"SELECT COUNT(*) n FROM candidates c JOIN runs r ON r.run_id=c.run_id WHERE {w}", args)["n"]
    rows = db.query(f"SELECT c.id, c.run_id, c.pair_id, c.lat, c.lon, c.area_m2, c.eq_diameter_m, c.category, c.score, "
                    f"c.polarity, c.registration_quality, c.classification, c.known_match, c.chips, c.methods, c.notes, "
                    f"c.created_at, r.kind AS run_kind FROM candidates c JOIN runs r ON r.run_id=c.run_id WHERE {w} "
                    f"ORDER BY c.{sort} {order.upper()} LIMIT ? OFFSET ?", args + [limit, offset])
    return {"total": total, "items": rows}


@app.get("/api/candidates/{cid}")
def get_candidate(cid: int) -> dict:
    db = get_db()
    c = db.one("SELECT * FROM candidates WHERE id=?", [cid])
    if not c:
        raise HTTPException(404)
    run = db.one("SELECT * FROM runs WHERE run_id=?", [c["run_id"]])
    pair = db.one("SELECT * FROM pairs WHERE pair_id=?", [c["pair_id"]])
    doc = _run_doc(c["run_id"])
    c["sources"] = doc["sources"]
    c["registration"] = doc["registration"]
    c["run_params"] = doc["params"]
    c["code_version"] = doc["code_version"]
    c["pair"] = pair
    c["run"] = {k: run[k] for k in ("run_id", "kind", "started_at", "finished_at", "status", "out_dir")}
    c["grid"] = doc["params"]["grid"]
    c["references_nearby"] = nearby_references(db, c["features"].get("lat_after_frame", c["lat"]),
                                               c["features"].get("lon_after_frame", c["lon"]), 2000)
    c["other_observations"] = [
        {"product_id": o["product_id"], "start_time": o["start_time"], "incidence": o["incidence"],
         "solar_longitude": o["solar_longitude"], "map_scale": o["map_scale"],
         "uahirise_url": uahirise_url(o["observation_id"]), "thumbnail": cog_thumbnail_url(o["product_id"])}
        for o in observations_covering(db, c["lat"], c["lon"])]
    c["processing_history"] = [
        {"stage": "discovery", "detail": f"pair {c['pair_id']} (source: {pair['source'] if pair else '?'})"},
        {"stage": "read", "detail": "USGS ARD COG windowed reads via HTTP range requests, resampled to local LAEA grid "
                                   f"@ {doc['params']['res_m']} m/px"},
        {"stage": "registration", "detail": f"coarse offset ({doc['registration']['coarse_dx_m']:.1f}, "
                                           f"{doc['registration']['coarse_dy_m']:.1f}) m; fine field from "
                                           f"{doc['registration']['n_inliers']} inliers; checkpoint RMS "
                                           f"{doc['registration']['check_rms_px']} px"},
        {"stage": "radiometry", "detail": f"blockwise trimmed linear fit, global gain "
                                         f"{doc['stats']['radiometry']['global_gain']:.3f}"},
        {"stage": "detection", "detail": "Method A (multi-scale registration-aware z + SSIM + hysteresis) → "
                                        "Method B features → Method C deep-feature distance → fusion"},
        {"stage": "classification", "detail": f"{c['classification']} (heuristic score {c['score']:.2f})"},
    ]
    return c


class Review(BaseModel):
    notes: str | None = None
    classification: Literal["known_documented", "plausible_unverified", "likely_artifact", "insufficient_evidence"] | None = None


@app.patch("/api/candidates/{cid}")
def review_candidate(cid: int, body: Review) -> dict:
    db = get_db()
    c = db.one("SELECT id, notes FROM candidates WHERE id=?", [cid])
    if not c:
        raise HTTPException(404)
    upd: dict[str, Any] = {}
    if body.notes is not None:
        upd["notes"] = body.notes
    if body.classification is not None:
        upd["classification"] = body.classification
        upd["notes"] = (upd.get("notes", c["notes"]) or "") + f"\n[{time.strftime('%Y-%m-%d %H:%M')}] status set to {body.classification} by reviewer"
    if upd:
        db.update("candidates", "id", cid, upd)
    return {"ok": True}


@app.get("/api/candidates/{cid}/report", response_class=PlainTextResponse)
def candidate_report(cid: int) -> str:
    c = get_candidate(cid)
    s = c["sources"]
    lines = [f"# MARSWATCH candidate {cid}", "",
             f"**Status:** {c['classification']}  ", f"**Category (heuristic):** {c['category']}  ",
             f"**Heuristic score:** {c['score']:.3f} (not a probability)  ",
             f"**Location (before frame):** {c['lat']:.5f}°N, {c['lon']:.5f}°E  ",
             f"**Location (after frame):** {c['features'].get('lat_after_frame', 0):.5f}°N, {c['features'].get('lon_after_frame', 0):.5f}°E  ",
             f"**Area:** {c['area_m2']:.0f} m² (equivalent diameter {c['eq_diameter_m']:.1f} m)  ",
             f"**Local registration quality:** {c['registration_quality']}  ", "",
             "## Observations", ""]
    for k in ("before", "after"):
        o = s[k]
        lines.append(f"* {k}: {o['product_id']} acquired {o['start_time']} (i={o['incidence']:.1f}°, Ls={o['solar_longitude']:.1f}°) — "
                     f"{o['uahirise_url']} — PDS: {o['pds_jp2_url']}")
    lines += ["", "## Evidence supporting", ""] + [f"* {e}" for e in c["evidence_for"]]
    lines += ["", "## Evidence against", ""] + ([f"* {e}" for e in c["evidence_against"]] or ["* none recorded"])
    lines += ["", "## Registration", "", "```json", json.dumps(c["registration"], indent=1), "```", "",
              "## Features", "", "```json", json.dumps(c["features"], indent=1), "```", "",
              "## Reproduce", "", "```bash",
              f"marswatch analyze {s['before']['product_id']} {s['after']['product_id']} --res {c['run_params']['res_m']}"
              + (f" --lat {c['run_params']['aoi']['lat']} --lon {c['run_params']['aoi']['lon']} --half {c['run_params']['aoi']['half_size_m']}"
                 if c["run_params"].get("aoi") else ""), "```", "",
              f"Code version `{c['code_version']}`; run `{c['run_id']}`.", "",
              "This is a software-generated candidate, not a confirmed discovery."]
    if c.get("notes"):
        lines += ["", "## Reviewer notes", "", c["notes"]]
    return "\n".join(lines)


@app.get("/api/export/candidates.{fmt}")
def export_candidates(fmt: Literal["csv", "json"], status: str | None = None, kind: str | None = None) -> Response:
    data = list_candidates(status=status, kind=kind, limit=2000)["items"]
    if fmt == "json":
        return JSONResponse(data)
    buf = io.StringIO()
    cols = ["id", "run_id", "pair_id", "lat", "lon", "area_m2", "eq_diameter_m", "category", "score", "polarity",
            "registration_quality", "classification", "known_match", "run_kind"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in data:
        w.writerow(r)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=marswatch_candidates.csv"})


# ---------------------------------------------------------------------------
# map
# ---------------------------------------------------------------------------

@app.get("/api/map")
def map_layers() -> dict:
    db = get_db()
    runs = db.query("SELECT run_id, pair_id, kind, params, stats FROM runs WHERE status='done'")
    areas = []
    for r in runs:
        try:
            doc = json.loads((settings.runs_dir / r["run_id"] / "run.json").read_text())
        except FileNotFoundError:
            continue
        (lon0, lat0), (lon1, lat1) = doc["grid_bounds_lonlat"]
        areas.append({"run_id": r["run_id"], "pair_id": r["pair_id"], "kind": r["kind"],
                      "bounds": [[min(lat0, lat1), min(lon0, lon1)], [max(lat0, lat1), max(lon0, lon1)]],
                      "n_candidates": (r["stats"] or {}).get("n_candidates")})
    cands = db.query("SELECT c.id, c.lat, c.lon, c.category, c.classification, c.score, c.eq_diameter_m, r.kind AS run_kind "
                     "FROM candidates c JOIN runs r ON r.run_id=c.run_id WHERE c.score >= 0.2")
    refs = db.query("SELECT ref_id, lat, lon, diameter_m, category FROM reference_changes")
    return {"areas": areas, "candidates": cands, "references": refs}


@app.get("/api/observations/covering")
def covering(lat: float, lon: float) -> list[dict]:
    db = get_db()
    return [{k: o[k] for k in ("product_id", "start_time", "incidence", "emission", "solar_longitude", "map_scale", "rationale")}
            | {"uahirise_url": uahirise_url(o["observation_id"]), "thumbnail": cog_thumbnail_url(o["product_id"])}
            for o in observations_covering(db, lat, lon)]


@app.get("/api/observations/{pid}")
def observation(pid: str) -> dict:
    o = get_db().one("SELECT * FROM observations WHERE product_id=?", [pid])
    if not o:
        raise HTTPException(404)
    return o | {"cog_url": cog_url(pid), "pds_jp2_url": pds_jp2_url(o["pds_path"]),
                "uahirise_url": uahirise_url(o["observation_id"]), "thumbnail": cog_thumbnail_url(pid)}


@app.get("/api/pairs")
def pairs(region: str | None = None, status: str | None = None, limit: int = 500) -> list[dict]:
    sql, args = "SELECT * FROM pairs WHERE 1=1", []
    if region:
        sql += " AND region=?"
        args.append(region)
    if status:
        sql += " AND status=?"
        args.append(status)
    return get_db().query(sql + " ORDER BY suitability DESC LIMIT ?", args + [limit])


# ---------------------------------------------------------------------------
# jobs / worker / system
# ---------------------------------------------------------------------------

class DiscoverReq(BaseModel):
    region: str = "custom"
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    enqueue_top: int = Field(5, ge=0, le=200)
    res_m: float = 1.0
    max_area_km2: float | None = 20.0
    min_overlap_km2: float = 1.0
    max_map_scale: float = 0.5


@app.post("/api/discover")
def discover(req: DiscoverReq) -> dict:
    if (req.max_lat - req.min_lat) * (req.max_lon - req.min_lon) > 400:
        raise HTTPException(400, "region too large (max 400 deg²): keep surveys bounded")
    params = req.model_dump()
    params["criteria"] = {"min_overlap_km2": params.pop("min_overlap_km2"), "max_map_scale": params.pop("max_map_scale")}
    jid = enqueue(get_db(), "discover_region", params, priority=100)
    return {"job_id": jid, "deduplicated": jid is None}


class AnalyzeReq(BaseModel):
    before_id: str
    after_id: str
    lat: float | None = None
    lon: float | None = None
    half_size_m: float = 500
    res_m: float = 1.0


@app.post("/api/analyze")
def analyze(req: AnalyzeReq) -> dict:
    db = get_db()
    for pid in (req.before_id, req.after_id):
        if not db.one("SELECT 1 FROM observations WHERE product_id=?", [pid]):
            raise HTTPException(404, f"{pid} not in index")
    aoi = {"lat": req.lat, "lon": req.lon, "half_size_m": req.half_size_m} if req.lat is not None else None
    jid = enqueue(db, "analyze_pair", {"before_id": req.before_id, "after_id": req.after_id, "aoi": aoi, "res_m": req.res_m,
                                       "run_kind": "manual"},
                  priority=90, dedupe_key=analyze_key(req.before_id, req.after_id, aoi, req.res_m))
    return {"job_id": jid, "deduplicated": jid is None}


@app.get("/api/jobs")
def jobs(status: str | None = None, limit: int = 200) -> list[dict]:
    sql, args = "SELECT * FROM jobs", []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    return get_db().query(sql + " ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END, id DESC LIMIT ?", args + [limit])


@app.post("/api/jobs/{jid}/retry")
def retry(jid: int) -> dict:
    db = get_db()
    j = db.one("SELECT status FROM jobs WHERE id=?", [jid])
    if not j:
        raise HTTPException(404)
    if j["status"] not in ("failed", "cancelled"):
        raise HTTPException(400, f"job is {j['status']}")
    db.update("jobs", "id", jid, {"status": "queued", "attempts": 0, "error": None, "started_at": None, "stage": "retry requested"})
    return {"ok": True}


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: int) -> dict:
    db = get_db()
    db.execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=? AND status='queued'", [time.time(), jid])
    return {"ok": True}


@app.post("/api/worker/{action}")
def worker_action(action: Literal["pause", "resume"]) -> dict:
    set_paused(get_db(), action == "pause")
    return {"paused": action == "pause"}


@app.get("/api/logs")
def logs(since_id: int = 0, level: str | None = None, limit: int = 300) -> list[dict]:
    sql, args = "SELECT * FROM logs WHERE id > ?", [since_id]
    if level:
        sql += " AND level=?"
        args.append(level)
    rows = get_db().query(sql + " ORDER BY id DESC LIMIT ?", args + [limit])
    return rows[::-1]


def _all_read_stats() -> dict:
    """Remote-read counters summed over this API process and all worker processes."""
    tot = ReadStats.snapshot()
    for r in get_db().query("SELECT value FROM state WHERE key LIKE 'read_stats_%'"):
        v = json.loads(r["value"])
        for k in ("reads", "pixels", "seconds", "cache_hits", "failures"):
            tot[k] = tot.get(k, 0) + v.get(k, 0)
    tot["seconds"] = round(tot["seconds"], 1)
    return tot


@app.get("/api/system")
def system() -> dict:
    vm = psutil.virtual_memory()
    du = shutil.disk_usage(settings.data_dir)
    proc = psutil.Process()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2), "cpu_count": psutil.cpu_count(),
        "mem_total_mb": vm.total / 1e6, "mem_used_percent": vm.percent, "process_rss_mb": proc.memory_info().rss / 1e6,
        "disk_free_gb": du.free / 1e9, "disk_total_gb": du.total / 1e9,
        "cache_mb": cache_size_bytes() / 1e6, "cache_budget_mb": settings.cache_budget_mb,
        "remote_reads": _all_read_stats(), "uptime_s": time.time() - STARTED,
        "settings": {"max_workers": settings.max_workers, "memory_limit_mb": settings.memory_limit_mb,
                     "requests_per_second": settings.requests_per_second, "work_resolution_m": settings.work_resolution_m},
    }


@app.get("/api/validation")
def validation() -> dict:
    db = get_db()
    out = {}
    for kind in ("crater_validation", "crater_validation_holdout", "injection_sensitivity", "injection_sensitivity_hard",
                 "registration_synthetic"):
        v = db.one("SELECT id, created_at, code_version, metrics FROM validation_runs WHERE kind=? ORDER BY id DESC LIMIT 1", [kind])
        if v and kind in ("injection_sensitivity", "injection_sensitivity_hard"):
            d = db.one("SELECT details FROM validation_runs WHERE id=?", [v["id"]])["details"]
            v["table"] = d.get("table")
        if v and kind == "registration_synthetic":
            d = db.one("SELECT details FROM validation_runs WHERE id=?", [v["id"]])["details"]
            v["trials"] = d.get("trials")
        if v and kind in ("crater_validation", "crater_validation_holdout"):
            d = db.one("SELECT details FROM validation_runs WHERE id=?", [v["id"]])["details"]
            v["cases"] = [{"ref_id": e["ref_id"], "diameter_m": e["diameter_m"],
                           "runs": [{k: r.get(k) for k in ("kind", "run_id", "before_id", "after_id", "d_incidence", "match",
                                                           "nearest_dist_m", "n_candidates", "registration", "error",
                                                           "skipped", "input_rejected")}
                                    for r in e["runs"]]} for e in d["cases"]]
        out[kind] = v
    return out


@app.get("/api/docs/{name}", response_class=PlainTextResponse)
def docs(name: str) -> str:
    allowed = {"VALIDATION_RESULTS", "SURVEY_REPORT", "LIMITATIONS", "METHODS", "VALIDATION"}
    if name not in allowed:
        raise HTTPException(404)
    p = REPO_ROOT / "docs" / f"{name}.md"
    if not p.exists():
        raise HTTPException(404)
    return p.read_text()


# ---------------------------------------------------------------------------
# frontend
# ---------------------------------------------------------------------------
DIST = REPO_ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
