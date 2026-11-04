"""Reference catalogs of documented Martian surface changes.

Currently ingested:

* Daubar, I.J., et al. (2022) "New Craters on Mars: An Updated Catalog",
  JGR Planets 127, e2021JE007145, doi:10.1029/2021JE007145.
  Table S1 from Zenodo record 6604912 (https://zenodo.org/record/6604912).
  1,203 dated impacts with coordinates, effective diameter and the
  before/after images that bracket the formation time.

Note: the Table S1 header labels latitude as "deg E" and longitude as "deg N";
the values are planetocentric latitude (deg N) and east longitude (0-360).
"""
from __future__ import annotations

import math
from pathlib import Path

import httpx

from ..config import settings
from ..db import Database
from ..log import get_logger

log = get_logger("reference")

DAUBAR_URL = "https://zenodo.org/api/records/6604912/files/Daubar_2022_catalog_tableS1.xlsx/content"
DAUBAR_FILE = "Daubar_2022_catalog_tableS1.xlsx"
DAUBAR_CITATION = "Daubar et al. (2022) JGR Planets 127, e2021JE007145, doi:10.1029/2021JE007145; data: zenodo.org/record/6604912"


def download_daubar(dest: Path | None = None) -> Path:
    dest = dest or settings.reference_dir / DAUBAR_FILE
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading Daubar 2022 catalog from Zenodo")
        r = httpx.get(DAUBAR_URL, follow_redirects=True, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def _date(v) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return str(v)[:10]
    except Exception:
        return None


def load_daubar(db: Database, path: Path | None = None) -> int:
    import pandas as pd

    path = path or download_daubar()
    df = pd.read_excel(path)
    cols = list(df.columns)
    n = 0
    for i, r in df.iterrows():
        hid = str(r[cols[0]]).strip()
        lat, lon = float(r[cols[1]]), float(r[cols[2]])
        diam = r[cols[12]]
        try:
            diam = float(diam)
        except (TypeError, ValueError):
            diam = None
        ref_id = f"D22-{i + 1:04d}"
        db.insert(
            "reference_changes",
            {
                "ref_id": ref_id,
                "source": DAUBAR_CITATION,
                "category": "new_impact_crater",
                "lat": lat,
                "lon": lon % 360,
                "diameter_m": diam,
                "hirise_id": hid,
                "before_date": _date(r[cols[15]]),
                "after_date": _date(r[cols[18]]),
                "before_image": f"{r[cols[13]]}:{r[cols[14]]}",
                "after_image": f"{r[cols[16]]}:{r[cols[17]]}",
                "attrs": {
                    "single_or_cluster": r[cols[6]],
                    "ice_exposing": r[cols[7]],
                    "halo": r[cols[8]],
                    "linear_rays": r[cols[9]],
                    "arcuate_rays": r[cols[10]],
                    "blast_zone_tone": r[cols[11]],
                    "image_ls": r[cols[3]],
                    "image_date": _date(r[cols[4]]),
                    "mars_year": r[cols[5]],
                },
            },
            replace=True,
        )
        n += 1
    log.info(f"loaded {n} Daubar 2022 craters")
    return n


def nearby_references(db: Database, lat: float, lon: float, radius_m: float) -> list[dict]:
    from ..geometry import haversine_m

    d = radius_m / 59000.0 + 0.01  # ~59 km per degree on Mars
    rows = db.query(
        "SELECT * FROM reference_changes WHERE lat BETWEEN ? AND ?",
        [lat - d, lat + d],
    )
    out = []
    for r in rows:
        dist = haversine_m(lat, lon, r["lat"], r["lon"])
        if dist <= radius_m:
            r["distance_m"] = dist
            out.append(r)
    return sorted(out, key=lambda r: r["distance_m"])
