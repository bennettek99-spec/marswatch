"""Discovery of overlapping, multi-temporal HiRISE observation pairs.

Candidates come from the locally ingested PDS cumulative index (R-tree bbox
pre-filter, then exact footprint intersection on a local equal-area
projection). Each pair receives a transparent *suitability* score built from
observation geometry so that pairs likely to produce illumination or parallax
artifacts are ranked lower (or rejected).
"""
from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .db import Database
from .geometry import angular_diff, footprint, lon360, overlap, point_in_footprint


@dataclass
class PairCriteria:
    min_overlap_km2: float = 1.0
    min_dt_days: float = 30.0          # exclude same-epoch stereo pairs
    max_d_incidence: float = 15.0
    max_d_sun_azimuth: float = 45.0
    max_d_emission: float = 25.0
    max_map_scale: float = 1.0         # m/px; excludes binned 1 m+ products when set lower
    seasonal_ls_tolerance: float | None = None  # if set, require |dLs| <= tol (for frost-free comparisons)


@dataclass
class PairInfo:
    pair_id: str
    before_id: str
    after_id: str
    overlap_km2: float
    center_lat: float
    center_lon: float
    dt_days: float
    d_incidence: float
    d_ls: float
    d_sun_azimuth: float
    d_emission: float
    suitability: float
    notes: list[str] = field(default_factory=list)
    overlap_wkt: str = ""

    def to_row(self, source: str, region: str | None = None) -> dict:
        d = asdict(self)
        d["suitability_notes"] = "; ".join(d.pop("notes"))
        d["source"] = source
        d["region"] = region
        d["created_at"] = time.time()
        return d


# Planet-encircling dust storms (atmospheric opacity high for weeks–months). All images that failed our
# structure-SNR gate during validation fall inside these windows (RESEARCH_LOG). Dates are generous bounds.
GLOBAL_DUST_STORMS = (("MY28", "2007-06-01", "2007-11-15"), ("MY34", "2018-05-25", "2018-10-31"))


def dust_storm_epoch(start_time: str | None) -> str | None:
    d = (start_time or "")[:10]
    for name, a, b in GLOBAL_DUST_STORMS:
        if a <= d <= b:
            return name
    return None


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.strip().replace("Z", "")[:19])


def make_pair_id(before: str, after: str) -> str:
    return f"{before.replace('_RED', '')}__{after.replace('_RED', '')}"


def score_pair(a: dict, b: dict, crit: PairCriteria | None = None) -> PairInfo | None:
    """Order (before, after) by time, compute geometry deltas and a suitability score in [0,1]."""
    crit = crit or PairCriteria()
    if _dt(a["start_time"]) > _dt(b["start_time"]):
        a, b = b, a
    ov = overlap(a, b)
    if ov is None:
        return None
    dt = (_dt(b["start_time"]) - _dt(a["start_time"])).total_seconds() / 86400
    d_inc = abs((a["incidence"] or 0) - (b["incidence"] or 0))
    d_ls = angular_diff(a["solar_longitude"], b["solar_longitude"]) or 0.0
    # sub-solar azimuth is measured in the image frame; correct with north azimuth
    az_a = (a["sub_solar_azimuth"] or 0) - (a["north_azimuth"] or 0)
    az_b = (b["sub_solar_azimuth"] or 0) - (b["north_azimuth"] or 0)
    d_az = angular_diff(az_a, az_b) or 0.0
    d_em = abs((a["emission"] or 0) - (b["emission"] or 0))
    d_ph = abs((a["phase"] or 0) - (b["phase"] or 0))
    notes: list[str] = []
    s = 1.0
    # each term is a soft penalty; documented in docs/METHODS.md
    s *= math.exp(-d_inc / 12.0)
    s *= math.exp(-d_az / 60.0)
    s *= math.exp(-d_em / 20.0)
    # with similar solar geometry, a phase-angle difference means a different viewing azimuth → parallax
    s *= math.exp(-max(0.0, d_ph - d_inc) / 25.0)
    s *= min(1.0, ov.area_km2 / 10.0) ** 0.5
    if abs(a["center_lat"]) > 50:
        s *= math.exp(-d_ls / 40.0)  # seasonal frost dominates at high latitude
        if d_ls > 30:
            notes.append(f"high-latitude pair with dLs={d_ls:.0f}°: seasonal frost differences expected")
    storms = {k: e for k, e in (("before", dust_storm_epoch(a["start_time"])), ("after", dust_storm_epoch(b["start_time"]))) if e}
    if storms:
        s *= 0.3
        notes.append("acquired during a global dust storm (" + ", ".join(f"{k}: {v}" for k, v in storms.items())
                     + "): haze alters shading non-linearly")
    if dt < crit.min_dt_days:
        notes.append(f"dt={dt:.1f} d: probable stereo pair, not a change pair")
        s *= 0.05
    if d_inc > crit.max_d_incidence:
        notes.append(f"incidence differs by {d_inc:.1f}° (shadow-length changes likely)")
    if d_az > crit.max_d_sun_azimuth:
        notes.append(f"sun azimuth differs by {d_az:.0f}° (shadow direction changes)")
    if d_ph - d_inc > 12:
        notes.append(f"phase angle differs by {d_ph:.0f}° (different viewing azimuth: relief parallax)")
    if d_em > crit.max_d_emission:
        notes.append(f"emission differs by {d_em:.1f}° (parallax distortion on relief)")
    return PairInfo(
        pair_id=make_pair_id(a["product_id"], b["product_id"]),
        before_id=a["product_id"],
        after_id=b["product_id"],
        overlap_km2=round(ov.area_km2, 3),
        center_lat=ov.center_lat,
        center_lon=ov.center_lon,
        dt_days=round(dt, 2),
        d_incidence=round(d_inc, 2),
        d_ls=round(d_ls, 2),
        d_sun_azimuth=round(d_az, 2),
        d_emission=round(d_em, 2),
        suitability=round(s, 4),
        notes=notes,
        overlap_wkt=ov.polygon_lonlat.wkt,
    )


def bbox_candidates(db: Database, min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> list[dict]:
    """Observations whose bbox intersects the query bbox (lon 0..360, handles wrap)."""
    out: dict[str, dict] = {}
    for shift in (0.0, 360.0, -360.0):
        rows = db.query(
            "SELECT o.* FROM obs_rtree r JOIN obs_rtree_map m ON r.rid=m.rid "
            "JOIN observations o ON o.product_id=m.product_id "
            "WHERE r.max_lon>=? AND r.min_lon<=? AND r.max_lat>=? AND r.min_lat<=?",
            [min_lon + shift, max_lon + shift, min_lat, max_lat],
        )
        for r in rows:
            out[r["product_id"]] = r
    return list(out.values())


def observations_covering(db: Database, lat: float, lon: float, margin_m: float = 0.0) -> list[dict]:
    lon = lon360(lon)
    d = 0.01
    cands = bbox_candidates(db, lon - d, lon + d, lat - d, lat + d)
    return sorted(
        [o for o in cands if point_in_footprint(o, lat, lon, margin_m)], key=lambda o: o["start_time"]
    )


def overlapping(db: Database, product_id: str) -> list[dict]:
    o = db.one("SELECT * FROM observations WHERE product_id=?", [product_id])
    if not o:
        raise KeyError(product_id)
    return [c for c in bbox_candidates(db, o["min_lon"], o["max_lon"], o["min_lat"], o["max_lat"])
            if c["product_id"] != product_id]


def find_pairs_in_region(
    db: Database,
    min_lat: float, max_lat: float, min_lon: float, max_lon: float,
    crit: PairCriteria | None = None,
    max_obs: int = 2000,
) -> list[PairInfo]:
    crit = crit or PairCriteria()
    obs = [o for o in bbox_candidates(db, min_lon, max_lon, min_lat, max_lat)
           if (o["map_scale"] or 9) <= crit.max_map_scale][:max_obs]
    pairs: list[PairInfo] = []
    polys = {o["product_id"]: footprint(o) for o in obs}
    for i in range(len(obs)):
        for j in range(i + 1, len(obs)):
            a, b = obs[i], obs[j]
            if not polys[a["product_id"]].buffer(0.001).intersects(polys[b["product_id"]]):
                # cheap reject (no wrap handling needed for regional queries)
                continue
            p = score_pair(a, b, crit)
            if p is None or p.overlap_km2 < crit.min_overlap_km2 or p.dt_days < crit.min_dt_days:
                continue
            if crit.seasonal_ls_tolerance is not None and p.d_ls > crit.seasonal_ls_tolerance:
                continue
            pairs.append(p)
    pairs.sort(key=lambda p: -p.suitability)
    return pairs


def save_pairs(db: Database, pairs: list[PairInfo], source: str, region: str | None = None) -> int:
    n = 0
    for p in pairs:
        if db.one("SELECT 1 FROM pairs WHERE pair_id=?", [p.pair_id]):
            continue
        db.insert("pairs", p.to_row(source, region))
        n += 1
    return n


def select_diverse(pairs: list[PairInfo], n: int, min_sep_km: float = 4.0, min_dt_days: float = 300.0,
                   max_d_incidence: float = 10.0, max_d_sun_azimuth: float = 25.0, max_d_emission: float = 15.0) -> list[PairInfo]:
    """Greedy selection of the best-matched pairs with distinct overlap centres (bounded survey budget)."""
    from .geometry import haversine_m

    good = [p for p in pairs if p.dt_days >= min_dt_days and p.d_incidence <= max_d_incidence
            and p.d_sun_azimuth <= max_d_sun_azimuth and p.d_emission <= max_d_emission]
    good.sort(key=lambda p: -p.suitability)
    chosen: list[PairInfo] = []
    for p in good:
        if all(haversine_m(p.center_lat, p.center_lon, q.center_lat, q.center_lon) >= min_sep_km * 1000 for q in chosen):
            chosen.append(p)
        if len(chosen) >= n:
            break
    return chosen
