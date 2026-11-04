"""SQLite persistence for observations, pairs, jobs, runs, candidates, validation and logs.

A single file database (WAL mode) keeps the system portable and dependency-free.
Every candidate references the run that produced it, and every run references
its source pair and the exact parameters / code version used, so any result can
be re-derived.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    product_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    instrument TEXT NOT NULL DEFAULT 'HIRISE',
    start_time TEXT,
    orbit INTEGER,
    mission_phase TEXT,
    rationale TEXT,
    image_lines INTEGER,
    line_samples INTEGER,
    emission REAL, incidence REAL, phase REAL,
    north_azimuth REAL, sub_solar_azimuth REAL,
    solar_longitude REAL, local_time REAL,
    min_lat REAL, max_lat REAL, min_lon REAL, max_lon REAL,
    map_scale REAL, projection TEXT,
    c1_lat REAL, c1_lon REAL, c2_lat REAL, c2_lon REAL,
    c3_lat REAL, c3_lon REAL, c4_lat REAL, c4_lon REAL,
    center_lat REAL, center_lon REAL,
    pds_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_obsid ON observations(observation_id);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(start_time);
CREATE VIRTUAL TABLE IF NOT EXISTS obs_rtree USING rtree(
    rid, min_lon, max_lon, min_lat, max_lat
);
CREATE TABLE IF NOT EXISTS obs_rtree_map (rid INTEGER PRIMARY KEY, product_id TEXT UNIQUE);

CREATE TABLE IF NOT EXISTS pairs (
    pair_id TEXT PRIMARY KEY,
    before_id TEXT NOT NULL,
    after_id TEXT NOT NULL,
    overlap_km2 REAL,
    overlap_wkt TEXT,
    center_lat REAL, center_lon REAL,
    dt_days REAL,
    d_incidence REAL, d_ls REAL, d_sun_azimuth REAL, d_emission REAL,
    suitability REAL,
    suitability_notes TEXT,
    source TEXT,
    region TEXT,
    status TEXT DEFAULT 'discovered',
    created_at REAL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    dedupe_key TEXT UNIQUE,
    pair_id TEXT,
    params TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    progress REAL DEFAULT 0,
    stage TEXT,
    error TEXT,
    result TEXT,
    created_at REAL, started_at REAL, finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, priority);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    pair_id TEXT,
    job_id INTEGER,
    kind TEXT,
    params TEXT,
    code_version TEXT,
    started_at REAL, finished_at REAL,
    out_dir TEXT,
    registration TEXT,
    stats TEXT,
    area_km2 REAL,
    status TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    pair_id TEXT,
    lat REAL, lon REAL,
    px_x REAL, px_y REAL,
    bbox TEXT,
    area_m2 REAL,
    eq_diameter_m REAL,
    category TEXT,
    score REAL,
    score_kind TEXT DEFAULT 'heuristic',
    polarity TEXT,
    registration_quality REAL,
    methods TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    classification TEXT,
    known_match TEXT,
    chips TEXT,
    features TEXT,
    notes TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_cand_run ON candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_cand_score ON candidates(score);

CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,
    created_at REAL,
    code_version TEXT,
    params TEXT,
    metrics TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS reference_changes (
    ref_id TEXT PRIMARY KEY,
    source TEXT,
    category TEXT,
    lat REAL, lon REAL,
    diameter_m REAL,
    hirise_id TEXT,
    before_date TEXT, after_date TEXT,
    before_image TEXT, after_image TEXT,
    attrs TEXT
);
CREATE INDEX IF NOT EXISTS idx_ref_latlon ON reference_changes(lat, lon);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL, level TEXT, logger TEXT, message TEXT, job_id INTEGER, context TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);

CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
"""

JSON_COLS = {
    "params", "result", "registration", "stats", "methods", "evidence_for",
    "evidence_against", "chips", "features", "bbox", "metrics", "details", "attrs", "context",
}


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if k in JSON_COLS and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                pass
    return d


def _enc(v: Any) -> Any:
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, default=_json_default)
    return v


def _json_default(o: Any) -> Any:
    try:
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self.conn() as c:
            c.executescript(SCHEMA)

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return c

    # -- generic helpers -------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        c = self.conn()
        cur = c.execute(sql, [_enc(p) for p in params])
        c.commit()
        return cur

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return [_decode(r) for r in self.conn().execute(sql, list(params)).fetchall()]  # type: ignore[misc]

    def one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        return _decode(self.conn().execute(sql, list(params)).fetchone())

    def insert(self, table: str, row: dict[str, Any], replace: bool = False) -> int:
        cols = ",".join(row)
        qs = ",".join("?" * len(row))
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        cur = self.execute(f"{verb} INTO {table} ({cols}) VALUES ({qs})", list(row.values()))
        return int(cur.lastrowid or 0)

    def update(self, table: str, key: str, key_val: Any, fields: dict[str, Any]) -> None:
        sets = ",".join(f"{k}=?" for k in fields)
        self.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", [*fields.values(), key_val])

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        c = self.conn()
        c.executemany(sql, rows)
        c.commit()

    # -- state -----------------------------------------------------------
    def get_state(self, key: str, default: Any = None) -> Any:
        r = self.one("SELECT value FROM state WHERE key=?", [key])
        return json.loads(r["value"]) if r else default

    def set_state(self, key: str, value: Any) -> None:
        self.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", [key, json.dumps(value)])

    # -- logs ------------------------------------------------------------
    def add_log(self, level: str, logger: str, message: str, job_id: int | None, context: dict) -> None:
        self.execute(
            "INSERT INTO logs(ts,level,logger,message,job_id,context) VALUES(?,?,?,?,?,?)",
            [time.time(), level, logger, message, job_id, context],
        )


_db: Database | None = None
_db_lock = threading.Lock()


def get_db(path: Path | str | None = None) -> Database:
    global _db
    with _db_lock:
        if path is not None:
            return Database(path)
        if _db is None:
            settings.ensure_dirs()
            _db = Database(settings.db_path)
        return _db


def set_db(db: Database) -> None:
    global _db
    _db = db
