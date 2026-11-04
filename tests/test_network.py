"""Integration tests against the real NASA/USGS archives. Run with: pytest -m network"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.network


def test_cog_windowed_read_real_hirise():
    from marswatch.imagery import RemoteImage, make_grid

    g = make_grid(17.762, 226.942, 100, 100, 1.0)
    a, v = RemoteImage("ESP_056155_1980_RED").read_to_grid(g)
    assert a.shape == (200, 200) and v.mean() > 0.95 and 0.01 < float(np.median(a[v])) < 0.6


def test_documented_crater_detected_end_to_end(tmp_path, monkeypatch):
    """D22-0887 (Daubar et al. 2022): 9 m crater formed between PSP_007023 and ESP_056155."""
    from marswatch.db import get_db
    from marswatch.pipeline import run_pair

    db = get_db()
    if not db.one("SELECT 1 FROM observations WHERE product_id='ESP_056155_1980_RED'"):
        pytest.skip("index not ingested; run `marswatch init`")
    doc = run_pair("PSP_007168_1980_RED", "ESP_056155_1980_RED", {"lat": 17.762, "lon": 226.942, "half_size_m": 300},
                   res_m=1.0, use_ml=False, write_tiles=False, run_kind="test")
    try:
        assert doc["registration"]["status"] in ("good", "marginal")
        assert any(c.get("known_match") == "D22-0887" for c in doc["candidates"])
    finally:  # keep test runs out of the research database
        import shutil
        from marswatch.config import settings

        db.execute("DELETE FROM candidates WHERE run_id=?", [doc["run_id"]])
        db.execute("DELETE FROM runs WHERE run_id=?", [doc["run_id"]])
        shutil.rmtree(settings.runs_dir / doc["run_id"], ignore_errors=True)
