"""Offline, read-only snapshot of the dashboard (``marswatch export-static OUT``).

Produces a folder that opens by double-clicking ``index.html`` — no Python, no server:

* the static frontend bundle (``frontend/dist-static``, built with ``MW_STATIC=1``);
* ``data.js`` — every API response the dashboard needs, computed in-process by the API's own
  functions so the snapshot shows exactly what the live server would;
* ``runs/<run_id>/`` — display images (large ones re-encoded to ≤ ``max_side`` px; candidate boxes are
  rescaled via ``display_scale``), heatmaps, outlines, evidence chips and per-run reports;
* ``data/candidates.csv|json`` and ``reports/*.md`` (README, research log, methods, limitations,
  validation results, survey report).

Included runs: the latest survey runs and the positive (documented-crater) runs of the latest
tuning and held-out validations. Other runs stay in the database and are reachable from the live server.
"""
from __future__ import annotations

import csv
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from .config import REPO_ROOT, settings
from .db import get_db
from .log import get_logger

log = get_logger("export")


def _included_runs(db) -> list[str]:
    runs = [r["run_id"] for r in db.query("SELECT run_id FROM runs WHERE kind='survey' AND status='done' ORDER BY started_at")]
    for kind in ("crater_validation", "crater_validation_holdout"):
        v = db.one("SELECT details FROM validation_runs WHERE kind=? ORDER BY id DESC LIMIT 1", [kind])
        if v:
            for e in v["details"]["cases"]:
                runs += [r["run_id"] for r in e["runs"] if r["kind"] == "positive" and r.get("run_id")]
    seen, out = set(), []
    for r in runs:
        if r not in seen and (settings.runs_dir / r / "run.json").exists():
            seen.add(r)
            out.append(r)
    return out


def _copy_images(src: Path, dst: Path, max_side: int, quality: int) -> float:
    dst.mkdir(parents=True, exist_ok=True)
    b = cv2.imread(str(src / "before.jpg"), cv2.IMREAD_GRAYSCALE)
    h, w = b.shape
    k = min(1.0, max_side / max(h, w))
    size = (max(1, round(w * k)), max(1, round(h * k)))
    for name in ("before.jpg", "after.jpg"):  # after_raw.jpg (registration diagnostic) is not used by the viewer
        p = src / name
        if p.exists():
            im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if k < 1:
                im = cv2.resize(im, size, interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(dst / name), im, [cv2.IMWRITE_JPEG_QUALITY, quality])
    for name in ("heat.png", "mask.png"):
        p = src / name
        if p.exists():
            im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            kk = min(k, 1500 / max(h, w)) if name == "heat.png" else k  # heat is a smooth field
            if kk < 1:
                im = cv2.resize(im, (max(1, round(w * kk)), max(1, round(h * kk))), interpolation=cv2.INTER_AREA)
                if name == "mask.png" and im.ndim == 3 and im.shape[2] == 4 and k < 1:  # keep thin outlines visible
                    im[..., 3] = np.clip(im[..., 3].astype(np.int32) * 3, 0, 255).astype(np.uint8)
            cv2.imwrite(str(dst / name), im, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if (src / "chips").exists():
        (dst / "chips").mkdir(exist_ok=True)
        for c in (src / "chips").glob("*.jpg"):
            cv2.imwrite(str(dst / "chips" / c.name), cv2.imread(str(c)), [cv2.IMWRITE_JPEG_QUALITY, 72])
    if (src / "report.md").exists():
        shutil.copy2(src / "report.md", dst / "report.md")
    return k


def export_static(out_dir: Path, max_side: int = 2400, quality: int = 78) -> dict:
    from .api import app as A  # API functions are plain callables

    db = get_db()
    dist = REPO_ROOT / "frontend" / "dist-static"
    if not (dist / "index.html").exists():
        raise FileNotFoundError("build the snapshot bundle first: cd frontend && MW_STATIC=1 npx vite build")
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(dist, out_dir)
    run_ids = _included_runs(db)
    S: dict = {"exported_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "runDocs": {}, "runReports": {},
               "candidateDetails": {}, "candidateReports": {}}
    for i, rid in enumerate(run_ids):
        k = _copy_images(settings.runs_dir / rid, out_dir / "runs" / rid, max_side, quality)
        doc = A.get_run(rid)
        doc["dzi"] = {}  # deep-zoom tiles are not shipped; the viewer uses the (re-encoded) full images
        doc["display_scale"] = k
        S["runDocs"][rid] = doc
        S["runReports"][rid] = A.run_report(rid)
        log.info(f"export run {i + 1}/{len(run_ids)} {rid} (scale {k:.2f})")
    S["runs"] = [r for r in A.list_runs(limit=5000) if r["run_id"] in S["runDocs"]]
    q = ",".join("?" * len(run_ids))
    cands = db.query(f"SELECT c.id, c.run_id, c.pair_id, c.lat, c.lon, c.area_m2, c.eq_diameter_m, c.category, c.score, "
                     f"c.polarity, c.registration_quality, c.classification, c.known_match, c.chips, c.methods, c.notes, "
                     f"c.created_at, r.kind AS run_kind FROM candidates c JOIN runs r ON r.run_id=c.run_id "
                     f"WHERE c.run_id IN ({q}) ORDER BY c.score DESC", run_ids)
    S["candidates"] = cands
    for c in cands:
        S["candidateDetails"][str(c["id"])] = A.get_candidate(c["id"])
        S["candidateReports"][str(c["id"])] = A.candidate_report(c["id"])
    m = A.map_layers()
    keep = set(run_ids)
    ids = {c["id"] for c in cands}
    m["areas"] = [a for a in m["areas"] if a["run_id"] in keep]
    m["candidates"] = [c for c in m["candidates"] if c["id"] in ids]
    S["map"] = m
    S["overview"] = A.overview()
    S["validation"] = A.validation()
    S["docs"] = {}
    for name in ("VALIDATION", "VALIDATION_RESULTS", "SURVEY_REPORT", "LIMITATIONS", "METHODS"):
        try:
            S["docs"][name] = A.docs(name)
        except Exception:
            pass
    S["jobs"] = A.jobs()
    S["system"] = A.system()
    S["logs"] = A.logs(limit=300)
    (out_dir / "data.js").write_text("window.__MW_STATIC__ = " + json.dumps(S, default=str) + ";\n")
    # classic script tags so the bundle runs from file:// (module scripts are blocked there)
    html = (out_dir / "index.html").read_text()
    html = html.replace(' type="module"', "").replace(" crossorigin", "")
    html = html.replace("<head>", '<head>\n    <script src="./data.js"></script>', 1)
    # IIFE bundle must run after #root exists
    html = html.replace("<script src=\"./assets/", "<script defer src=\"./assets/")
    (out_dir / "index.html").write_text(html)
    (out_dir / "data").mkdir(exist_ok=True)
    (out_dir / "data" / "candidates.json").write_text(json.dumps(cands, indent=1, default=str))
    cols = ["id", "run_id", "pair_id", "lat", "lon", "area_m2", "eq_diameter_m", "category", "score", "polarity",
            "registration_quality", "classification", "known_match", "run_kind", "notes"]
    with open(out_dir / "data" / "candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in cands:
            w.writerow(c)
    rep = out_dir / "reports"
    rep.mkdir(exist_ok=True)
    for p in [REPO_ROOT / "README.md", REPO_ROOT / "RESEARCH_LOG.md", *sorted((REPO_ROOT / "docs").glob("*.md")),
              REPO_ROOT / "examples" / "README.md"]:
        if p.exists():
            shutil.copy2(p, rep / (("EXAMPLES" if p.parent.name == "examples" else p.stem) + ".md"))
    (out_dir / "OPEN_ME.txt").write_text(
        "MARSWATCH offline snapshot\n\n"
        "1. Unzip this folder anywhere (e.g. your Desktop).\n"
        "2. Double-click index.html (Chrome, Edge, Firefox or Safari).\n"
        "   The Mars Explorer basemap tiles load from NASA Trek and need internet; everything else is local.\n"
        "3. Written reports are in reports/ (start with SURVEY_REPORT.md and VALIDATION_RESULTS.md).\n\n"
        "The snapshot is read-only: queueing new analyses, retries and reviewer edits need the live server\n"
        "(see reports/README.md).\n")
    size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    return {"runs": len(run_ids), "candidates": len(cands), "bytes": size, "out": str(out_dir)}
