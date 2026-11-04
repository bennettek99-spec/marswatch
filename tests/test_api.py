"""API tests against a temporary database (no network)."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_db, tmp_path, monkeypatch):
    from marswatch.api import app as appmod

    tmp_db.insert("runs", {"run_id": "R1", "pair_id": "A__B", "kind": "survey", "status": "done", "started_at": time.time(),
                           "finished_at": time.time(), "stats": {"analysed_km2": 1.5, "n_candidates": 1}, "area_km2": 1.5,
                           "registration": {"quality": 0.8, "status": "good", "check_rms_px": 0.5}})
    tmp_db.insert("candidates", {"run_id": "R1", "pair_id": "A__B", "lat": 1.0, "lon": 2.0, "area_m2": 50.0, "eq_diameter_m": 8.0,
                                 "category": "new_impact_crater", "score": 0.7, "classification": "plausible_unverified",
                                 "methods": {"A_classical": True}, "evidence_for": ["x"], "evidence_against": [], "features": {}})
    return TestClient(appmod.app)


def test_overview_and_candidates(client):
    ov = client.get("/api/overview").json()
    assert ov["runs_done"] == 1 and ov["candidates"] == 1 and abs(ov["area_km2"] - 1.5) < 1e-9
    r = client.get("/api/candidates", params={"status": "plausible_unverified", "min_score": 0.5}).json()
    assert r["total"] == 1 and r["items"][0]["category"] == "new_impact_crater"
    assert client.get("/api/candidates", params={"min_score": 0.9}).json()["total"] == 0
    csv = client.get("/api/export/candidates.csv").text
    assert csv.splitlines()[0].startswith("id,run_id")


def test_review_and_worker_controls(client, tmp_db):
    cid = client.get("/api/candidates").json()["items"][0]["id"]
    assert client.patch(f"/api/candidates/{cid}", json={"classification": "likely_artifact", "notes": "shadow"}).json()["ok"]
    row = tmp_db.one("SELECT classification, notes FROM candidates WHERE id=?", [cid])
    assert row["classification"] == "likely_artifact" and "shadow" in row["notes"]
    assert client.post("/api/worker/pause").json()["paused"] is True
    assert client.get("/api/overview").json()["worker"]["paused"] is True
    assert client.post("/api/discover", json={"min_lat": 0, "max_lat": 50, "min_lon": 0, "max_lon": 50}).status_code == 400
