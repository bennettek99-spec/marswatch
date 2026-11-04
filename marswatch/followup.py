"""Follow-up verification of promising candidates.

For a candidate, gather independent evidence:

1. **Catalogue** — catalogued changes within 2 km (Daubar et al. 2022).
2. **HiRISE targeting** — rationales of all HiRISE observations covering the point. A rationale such
   as "Candidate recent impact site" or "Slope streak monitoring" shows the HiRISE team already
   targeted a suspected change/process there (prior knowledge, though not necessarily published).
3. **Caption** — the uahirise.org caption title of the after observation (public release text).
4. **Third-image persistence** — if another HiRISE observation exists *after* the pair's after image,
   the before image is compared with it over a small window. A real, persistent surface change
   (new crater, new streak) must reappear at the same place; an artifact of one particular image
   generally will not. (Fading features such as slope streaks or blast zones can legitimately weaken.)

Results are stored in the candidate's ``features.followup`` and summarised in evidence lists.
"""
from __future__ import annotations

import re
import time

import httpx

from .db import Database, get_db
from .discovery import observations_covering
from .geometry import haversine_m
from .imagery import cog_available, uahirise_url
from .log import get_logger

log = get_logger("followup")

TARGETING_PATTERNS = {
    "impact": re.compile(r"(new|recent|fresh|candidate).*(impact|crater)|impact site|dated impact", re.I),
    "slope_streak": re.compile(r"slope streak", re.I),
    "dune": re.compile(r"dune|ripple|bedform", re.I),
    "gully": re.compile(r"gull", re.I),
    "rsl": re.compile(r"\bRSL\b|recurring slope lineae", re.I),
    "monitoring": re.compile(r"monitor|change detection|repeat", re.I),
}


def caption_title(observation_id: str) -> str | None:
    try:
        r = httpx.get(uahirise_url(observation_id), timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return None
        m = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    except Exception:
        return None


def followup_candidate(cid: int, db: Database | None = None, window_m: float = 250.0, run_third: bool = True) -> dict:
    from .pipeline import run_pair

    db = db or get_db()
    c = db.one("SELECT * FROM candidates WHERE id=?", [cid])
    if not c:
        raise KeyError(cid)
    run = db.one("SELECT * FROM runs WHERE run_id=?", [c["run_id"]])
    pair = db.one("SELECT * FROM pairs WHERE pair_id=?", [c["pair_id"]])
    before_id, after_id = pair["before_id"], pair["after_id"]
    after = db.one("SELECT * FROM observations WHERE product_id=?", [after_id])
    res = {"candidate": cid, "checked_at": time.time()}

    # 1. catalogue
    from .archive.reference import nearby_references

    refs = nearby_references(db, c["features"].get("lat_after_frame", c["lat"]), c["features"].get("lon_after_frame", c["lon"]), 2000)
    res["catalogue_within_2km"] = [{"ref_id": r["ref_id"], "distance_m": round(r["distance_m"]), "diameter_m": r["diameter_m"],
                                    "formed": f"{r['before_date']}…{r['after_date']}"} for r in refs]
    # 2. targeting rationales of all coverage
    cov = observations_covering(db, c["lat"], c["lon"])
    tags = {}
    for o in cov:
        for k, rx in TARGETING_PATTERNS.items():
            if o["rationale"] and rx.search(o["rationale"]):
                tags.setdefault(k, []).append(f"{o['product_id'].replace('_RED', '')} ({o['start_time'][:10]}): {o['rationale']}")
    res["targeting"] = tags
    res["n_coverage"] = len(cov)
    # 3. caption of after observation
    res["after_caption_title"] = caption_title(after["observation_id"])
    # 4. third-image persistence
    later = [o for o in cov if o["start_time"] > after["start_time"] and (o["map_scale"] or 9) <= 0.5
             and o["product_id"] != after_id and cog_available(o["product_id"])]
    res["third_image"] = None
    if run_third and later:
        third = later[-1]
        try:
            doc = run_pair(before_id, third["product_id"], {"lat": c["lat"], "lon": c["lon"], "half_size_m": window_m},
                           db=db, res_m=run["params"].get("res_m", 1.0) if isinstance(run["params"], dict) else 1.0,
                           run_kind="followup", write_tiles=False, use_ml=False)
            near = [k for k in doc["candidates"] if haversine_m(k["lat"], k["lon"], c["lat"], c["lon"]) <= max(30.0, c["eq_diameter_m"])
                    and k["polarity"] == c["polarity"] and k["classification"] != "likely_artifact"]
            res["third_image"] = {
                "product_id": third["product_id"], "date": third["start_time"][:10], "run_id": doc["run_id"],
                "registration": doc["registration"]["status"],
                "reappears": bool(near), "match_score": max((k["score"] for k in near), default=None),
            }
        except Exception as e:
            res["third_image"] = {"product_id": third["product_id"], "error": str(e)[:200]}
    # evidence summary
    ev_for, ev_against = list(c["evidence_for"] or []), list(c["evidence_against"] or [])
    t = res["third_image"]
    if t and "reappears" in t:
        if t["reappears"]:
            ev_for.append(f"FOLLOW-UP: same-polarity change reappears comparing before with independent later image "
                          f"{t['product_id']} ({t['date']})")
        else:
            ev_against.append(f"FOLLOW-UP: no matching change when comparing before with later image {t['product_id']} "
                              f"({t['date']}, registration {t['registration']}) — artifact or transient/fading feature")
    if tags.get("impact") and c["category"] == "new_impact_crater":
        ev_for.append("FOLLOW-UP: HiRISE team targeted this location as a candidate/new impact site — prior knowledge exists")
    if tags.get("slope_streak") and c["category"] == "slope_streak":
        ev_for.append("FOLLOW-UP: location is a HiRISE slope-streak monitoring target")
    feats = dict(c["features"] or {})
    feats["followup"] = res
    db.update("candidates", "id", cid, {"features": feats, "evidence_for": ev_for, "evidence_against": ev_against})
    log.info(f"follow-up candidate {cid}: third image {t}, targeting {list(tags)}")
    return res
