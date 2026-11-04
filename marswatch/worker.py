"""Persistent job queue and autonomous worker.

* Jobs live in SQLite (``jobs`` table) so the queue survives restarts.
* ``dedupe_key`` (UNIQUE) prevents duplicate processing of the same pair/AOI/params.
* Pausing is a DB flag (``state.worker_paused``) honoured between jobs; the
  dashboard and CLI can toggle it. Running jobs finish their current stage.
* Failures are retried with exponential backoff up to ``max_attempts``; the
  error text is stored on the job and in the log.
* On start-up, jobs left in ``running`` by a crash are re-queued (resume).
* A memory guard waits while process RSS exceeds the configured limit.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from typing import Any

import psutil

from .config import settings
from .db import Database, get_db
from .log import get_logger

log = get_logger("worker")

JOB_KINDS = ("analyze_pair", "discover_region")


def enqueue(db: Database, kind: str, params: dict, pair_id: str | None = None, priority: int = 0,
            dedupe_key: str | None = None, max_attempts: int = 3) -> int | None:
    if kind not in JOB_KINDS:
        raise ValueError(kind)
    dedupe_key = dedupe_key or f"{kind}:{json.dumps(params, sort_keys=True)}"
    existing = db.one("SELECT id, status FROM jobs WHERE dedupe_key=?", [dedupe_key])
    if existing:
        return None
    return db.insert("jobs", {"kind": kind, "dedupe_key": dedupe_key, "pair_id": pair_id, "params": params,
                              "priority": priority, "status": "queued", "max_attempts": max_attempts,
                              "created_at": time.time()})


def analyze_key(before_id: str, after_id: str, aoi: dict | None, res_m: float) -> str:
    return f"analyze_pair:{before_id}:{after_id}:{json.dumps(aoi, sort_keys=True)}:{res_m}"


def is_paused(db: Database) -> bool:
    return bool(db.get_state("worker_paused", False))


def set_paused(db: Database, paused: bool) -> None:
    db.set_state("worker_paused", paused)
    log.info("worker paused" if paused else "worker resumed")


def recover_stale(db: Database) -> int:
    rows = db.query("SELECT id FROM jobs WHERE status='running'")
    for r in rows:
        db.execute("UPDATE jobs SET status='queued', stage='re-queued after interruption', "
                   "attempts=MAX(0, attempts-1), started_at=NULL WHERE id=?", [r["id"]])  # interruption ≠ failure
    # run records orphaned by the interruption are kept (provenance) but marked as such
    db.execute("UPDATE runs SET status='interrupted' WHERE status='running' AND kind IN ('survey','manual')")
    if rows:
        log.warning(f"re-queued {len(rows)} interrupted jobs")
    return len(rows)


_claim_lock = threading.Lock()


def claim(db: Database) -> dict | None:
    with _claim_lock:
        now = time.time()
        r = db.one("SELECT * FROM jobs WHERE status='queued' AND (started_at IS NULL OR started_at <= ?) "
                   "ORDER BY priority DESC, id ASC LIMIT 1", [now])
        if not r:
            return None
        db.update("jobs", "id", r["id"], {"status": "running", "started_at": now, "attempts": (r["attempts"] or 0) + 1,
                                          "progress": 0.0, "stage": "starting", "error": None})
        r["attempts"] = (r["attempts"] or 0) + 1
        return r


def execute(db: Database, job: dict) -> Any:
    p = job["params"] or {}
    jid = job["id"]

    def progress(f: float, stage: str) -> None:
        db.update("jobs", "id", jid, {"progress": round(f, 3), "stage": stage})

    if job["kind"] == "analyze_pair":
        from .pipeline import run_pair

        doc = run_pair(p["before_id"], p["after_id"], p.get("aoi"), db=db, job_id=jid, res_m=p.get("res_m"),
                       use_ml=p.get("use_ml", True), progress=progress, run_kind=p.get("run_kind", "survey"),
                       max_area_km2=p.get("max_area_km2"))
        return {"run_id": doc["run_id"], "n_candidates": len(doc["candidates"]), "by_status": doc["stats"]["by_status"]}
    if job["kind"] == "discover_region":
        from .discovery import PairCriteria, find_pairs_in_region, save_pairs, select_diverse

        crit = PairCriteria(**p.get("criteria", {}))
        pairs = find_pairs_in_region(db, p["min_lat"], p["max_lat"], p["min_lon"], p["max_lon"], crit)
        n = save_pairs(db, pairs, source="discovery", region=p.get("region"))
        queued = 0
        to_queue = (select_diverse(pairs, p.get("enqueue_top", 0), p.get("min_sep_km", 4.0))
                    if p.get("diverse", True) else pairs[: p.get("enqueue_top", 0)])
        for pr in to_queue:
            aoi = None
            k = analyze_key(pr.before_id, pr.after_id, aoi, p.get("res_m", settings.work_resolution_m))
            if enqueue(db, "analyze_pair", {"before_id": pr.before_id, "after_id": pr.after_id, "aoi": aoi,
                                            "res_m": p.get("res_m", settings.work_resolution_m),
                                            "max_area_km2": p.get("max_area_km2"), "run_kind": "survey"},
                       pair_id=pr.pair_id, priority=int(pr.suitability * 100), dedupe_key=k):
                queued += 1
        return {"pairs_found": len(pairs), "pairs_new": n, "jobs_queued": queued}
    raise ValueError(f"unknown job kind {job['kind']}")


def publish_read_stats(db: Database) -> None:
    """Share this process's remote-read counters with the API (dashboard console)."""
    import os

    from .imagery import ReadStats

    db.set_state(f"read_stats_{os.getpid()}", ReadStats.snapshot() | {"updated": time.time()})


def run_one(db: Database, job: dict) -> None:
    jlog = get_logger("worker", job_id=job["id"])
    try:
        _run_one(db, job, jlog)
    finally:
        publish_read_stats(db)


def _run_one(db: Database, job: dict, jlog) -> None:
    try:
        res = execute(db, job)
        db.update("jobs", "id", job["id"], {"status": "done", "finished_at": time.time(), "progress": 1.0,
                                            "stage": "done", "result": res})
        jlog.info(f"job {job['id']} ({job['kind']}) done: {res}")
    except Exception as e:
        from .pipeline import InputRejected

        tb = traceback.format_exc(limit=6)
        attempts = job["attempts"]
        if isinstance(e, InputRejected):  # data problem, retrying cannot help
            db.update("jobs", "id", job["id"], {"status": "failed", "error": f"input rejected by QC: {e}",
                                                "finished_at": time.time(), "stage": "rejected_input"})
            jlog.warning(f"job {job['id']} input rejected: {e}")
            return
        if attempts < (job["max_attempts"] or 3):
            backoff = 30 * 2 ** (attempts - 1)
            db.update("jobs", "id", job["id"], {"status": "queued", "error": f"{e}\n{tb}", "stage": f"retry in {backoff}s",
                                                "started_at": time.time() + backoff})
            jlog.warning(f"job {job['id']} failed (attempt {attempts}); retrying in {backoff}s: {e}")
        else:
            db.update("jobs", "id", job["id"], {"status": "failed", "error": f"{e}\n{tb}", "finished_at": time.time(),
                                                "stage": "failed"})
            jlog.error(f"job {job['id']} failed permanently: {e}")


class Worker:
    def __init__(self, db: Database | None = None, n_threads: int | None = None):
        self.db = db or get_db()
        self.n = n_threads or settings.max_workers
        self.stop_evt = threading.Event()
        self.threads: list[threading.Thread] = []

    def _loop(self) -> None:
        proc = psutil.Process()
        while not self.stop_evt.is_set():
            if is_paused(self.db):
                time.sleep(2)
                continue
            if proc.memory_info().rss / 1e6 > settings.memory_limit_mb:
                log.warning("memory limit reached; waiting before claiming new jobs")
                time.sleep(10)
                continue
            job = claim(self.db)
            if job is None:
                time.sleep(3)
                continue
            run_one(self.db, job)

    def start(self) -> None:
        recover_stale(self.db)
        self.db.set_state("worker_started_at", time.time())
        for i in range(self.n):
            t = threading.Thread(target=self._loop, name=f"mw-worker-{i}", daemon=True)
            t.start()
            self.threads.append(t)
        log.info(f"worker started with {self.n} threads")

    def stop(self) -> None:
        self.stop_evt.set()

    def run_until_empty(self, poll: float = 3.0) -> None:
        self.start()
        try:
            while True:
                q = self.db.one("SELECT COUNT(*) n FROM jobs WHERE status IN ('queued','running')")["n"]
                if q == 0:
                    break
                time.sleep(poll)
        finally:
            self.stop()
