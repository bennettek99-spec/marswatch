"""HiRISE PDS3 cumulative RDR index (RDRCUMINDEX.TAB) ingestion.

Source: https://hirise-pds.lpl.arizona.edu/PDS/INDEX/RDRCUMINDEX.TAB (+ .LBL)
The label defines ~60 columns; we parse the column names from the label so the
ingester does not rely on hard-coded byte offsets. Only ``*_RED`` RDR products
(the full-swath panchromatic products) are kept: they are what change detection
needs and what USGS republishes as Cloud-Optimized GeoTIFFs.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Iterator

import httpx

from ..config import settings
from ..db import Database
from ..log import get_logger

log = get_logger("pds_index")

INDEX_NAME = "RDRCUMINDEX"


def parse_label_columns(lbl_text: str) -> list[str]:
    """Return COLUMN NAMEs in order from a PDS3 TABLE label."""
    names: list[str] = []
    in_col = False
    for line in lbl_text.splitlines():
        s = line.strip()
        if s.startswith("OBJECT") and s.endswith("COLUMN"):
            in_col = True
            continue
        if s.startswith("END_OBJECT") and in_col:
            in_col = False
            continue
        if in_col:
            m = re.match(r"NAME\s*=\s*\"?([A-Z0-9_:]+)\"?", s)
            if m:
                names.append(m.group(1))
    return names


def download_index(dest_dir: Path | None = None, force: bool = False) -> tuple[Path, Path]:
    """Stream-download the cumulative index (~170 MB) and its label."""
    dest_dir = dest_dir or settings.index_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("LBL", "TAB"):
        p = dest_dir / f"{INDEX_NAME}.{ext}"
        if p.exists() and not force:
            out.append(p)
            continue
        url = f"{settings.pds_base}/INDEX/{INDEX_NAME}.{ext}"
        log.info(f"downloading {url}")
        tmp = p.with_suffix(p.suffix + ".part")
        with httpx.stream("GET", url, timeout=600, follow_redirects=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        tmp.rename(p)
        out.append(p)
    return out[1], out[0]


def _f(v: str) -> float | None:
    v = v.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def iter_rows(tab_path: Path, columns: list[str]) -> Iterator[dict[str, str]]:
    with open(tab_path, "r", encoding="latin-1", newline="") as fh:
        for rec in csv.reader(fh, skipinitialspace=True):
            if len(rec) != len(columns):
                continue
            yield {c: v.strip() for c, v in zip(columns, rec)}


def row_to_observation(r: dict[str, str]) -> dict | None:
    pid = r.get("PRODUCT_ID", "")
    if not pid.endswith("_RED"):
        return None
    corners = [(_f(r[f"CORNER{i}_LATITUDE"]), _f(r[f"CORNER{i}_LONGITUDE"])) for i in range(1, 5)]
    if any(a is None or b is None for a, b in corners):
        return None
    lons = [c[1] for c in corners]
    # unwrap footprints that straddle the 0/360 meridian
    if max(lons) - min(lons) > 180:  # type: ignore[operator]
        corners = [(la, lo + 360 if lo < 180 else lo) for la, lo in corners]  # type: ignore[operator]
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    obs = {
        "product_id": pid,
        "observation_id": r["OBSERVATION_ID"],
        "start_time": r.get("START_TIME") or r.get("OBSERVATION_START_TIME"),
        "orbit": int(r["ORBIT_NUMBER"]) if r.get("ORBIT_NUMBER", "").strip().isdigit() else None,
        "mission_phase": r.get("MISSION_PHASE_NAME"),
        "rationale": r.get("RATIONALE_DESC"),
        "image_lines": int(_f(r["IMAGE_LINES"]) or 0),
        "line_samples": int(_f(r["LINE_SAMPLES"]) or 0),
        "emission": _f(r["EMISSION_ANGLE"]),
        "incidence": _f(r["INCIDENCE_ANGLE"]),
        "phase": _f(r["PHASE_ANGLE"]),
        "north_azimuth": _f(r["NORTH_AZIMUTH"]),
        "sub_solar_azimuth": _f(r["SUB_SOLAR_AZIMUTH"]),
        "solar_longitude": _f(r["SOLAR_LONGITUDE"]),
        "local_time": _f(r["LOCAL_TIME"]),
        "min_lat": min(lats), "max_lat": max(lats),  # type: ignore[type-var]
        "min_lon": min(lons), "max_lon": max(lons),  # type: ignore[type-var]
        "map_scale": _f(r["MAP_SCALE"]),
        "projection": r.get("MAP_PROJECTION_TYPE"),
        "c1_lat": corners[0][0], "c1_lon": corners[0][1],
        "c2_lat": corners[1][0], "c2_lon": corners[1][1],
        "c3_lat": corners[2][0], "c3_lon": corners[2][1],
        "c4_lat": corners[3][0], "c4_lon": corners[3][1],
        "center_lat": sum(lats) / 4,  # type: ignore[arg-type]
        "center_lon": (sum(lons) / 4) % 360,  # type: ignore[arg-type]
        "pds_path": r.get("FILE_NAME_SPECIFICATION"),
    }
    return obs


def ingest_index(db: Database, tab_path: Path | None = None, lbl_path: Path | None = None) -> int:
    """Parse the cumulative index into the ``observations`` table + R-tree. Idempotent."""
    tab_path = tab_path or settings.index_dir / f"{INDEX_NAME}.TAB"
    lbl_path = lbl_path or settings.index_dir / f"{INDEX_NAME}.LBL"
    if not tab_path.exists():
        tab_path, lbl_path = download_index()
    columns = parse_label_columns(lbl_path.read_text(encoding="latin-1"))
    log.info(f"index label has {len(columns)} columns")
    obs_rows: list[dict] = []
    seen: dict[str, dict] = {}
    for r in iter_rows(tab_path, columns):
        o = row_to_observation(r)
        if o is None:
            continue
        # the cumulative index can list re-released versions; keep the last one
        seen[o["product_id"]] = o
    obs_rows = list(seen.values())
    if not obs_rows:
        raise RuntimeError("no RED observations parsed from index")
    cols = list(obs_rows[0])
    c = db.conn()
    c.execute("DELETE FROM obs_rtree")
    c.execute("DELETE FROM obs_rtree_map")
    c.executemany(
        f"INSERT OR REPLACE INTO observations ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [[o[k] for k in cols] for o in obs_rows],
    )
    c.executemany(
        "INSERT INTO obs_rtree_map(rid, product_id) VALUES(?,?)",
        [(i + 1, o["product_id"]) for i, o in enumerate(obs_rows)],
    )
    c.executemany(
        "INSERT INTO obs_rtree(rid,min_lon,max_lon,min_lat,max_lat) VALUES(?,?,?,?,?)",
        [(i + 1, o["min_lon"], o["max_lon"], o["min_lat"], o["max_lat"]) for i, o in enumerate(obs_rows)],
    )
    c.commit()
    log.info(f"ingested {len(obs_rows)} RED RDR observations")
    return len(obs_rows)


def parse_index_bytes(lbl_text: str, tab_bytes: bytes) -> list[dict]:
    """Helper for tests: parse an in-memory snippet of the index."""
    columns = parse_label_columns(lbl_text)
    out = []
    for rec in csv.reader(io.StringIO(tab_bytes.decode("latin-1")), skipinitialspace=True):
        if len(rec) == len(columns):
            o = row_to_observation({c: v.strip() for c, v in zip(columns, rec)})
            if o:
                out.append(o)
    return out
