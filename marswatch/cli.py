"""MARSWATCH command-line interface.

    marswatch init                       # download + ingest HiRISE index, Daubar catalog
    marswatch covering LAT LON           # list HiRISE RED observations covering a point
    marswatch discover --region NAME --lat0 .. --lat1 .. --lon0 .. --lon1 .. [--enqueue N]
    marswatch analyze BEFORE AFTER [--lat --lon --half] [--res]
    marswatch validate [--limit N] [--no-negatives] [--injection] [--registration]
    marswatch worker [--until-empty]
    marswatch pause | resume
    marswatch serve [--port 8000]
    marswatch report                     # regenerate docs/SURVEY_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import sys


def _db():
    from .db import get_db

    return get_db()


def cmd_init(a) -> None:
    from .archive.pds_index import download_index, ingest_index
    from .archive.reference import load_daubar

    db = _db()
    download_index(force=a.refresh)
    print(f"observations: {ingest_index(db)}")
    print(f"reference craters: {load_daubar(db)}")


def cmd_covering(a) -> None:
    from .discovery import observations_covering

    for o in observations_covering(_db(), a.lat, a.lon):
        print(f"{o['product_id']:22s} {o['start_time']}  inc={o['incidence']:5.1f} Ls={o['solar_longitude']:6.1f} "
              f"scale={o['map_scale']}  {o['rationale']}")


def cmd_discover(a) -> None:
    from .worker import execute

    params = {"region": a.region, "min_lat": a.lat0, "max_lat": a.lat1, "min_lon": a.lon0, "max_lon": a.lon1,
              "enqueue_top": a.enqueue, "res_m": a.res, "max_area_km2": a.max_area,
              "criteria": {"min_overlap_km2": a.min_overlap, "max_map_scale": a.max_scale}}
    res = execute(_db(), {"id": None, "kind": "discover_region", "params": params})
    print(json.dumps(res, indent=1))


def cmd_analyze(a) -> None:
    from .pipeline import run_pair

    aoi = {"lat": a.lat, "lon": a.lon, "half_size_m": a.half} if a.lat is not None else None
    doc = run_pair(a.before, a.after, aoi, res_m=a.res, use_ml=not a.no_ml, run_kind=a.kind)
    print(f"run: {doc['run_id']}\nregistration: {doc['registration']['status']} "
          f"(checkpoint RMS {doc['registration']['check_rms_px']} px)\nstatus counts: {doc['stats']['by_status']}")
    for c in doc["candidates"][:10]:
        print(f"  {c['score']:.2f} {c['category']:38s} {c['classification']:22s} {c['lat']:.5f},{c['lon']:.5f} "
              f"D≈{c['eq_diameter_m']:.1f} m {c['known_match'] or ''}")


def cmd_validate(a) -> None:
    from .validation import (injection_sensitivity, registration_synthetic, run_crater_validation,
                             save_validation)
    from .reports import write_validation_doc

    db = _db()
    if a.registration:
        r = registration_synthetic(db, n_trials=a.trials)
        save_validation(db, "registration_synthetic", r)
        print(json.dumps({k: v for k, v in r.items() if k != "trials"}, indent=1))
    if a.injection:
        r = injection_sensitivity(db)
        save_validation(db, "injection_sensitivity", r)
        print(json.dumps(r["table"], indent=1))
    if not a.skip_craters:
        r = run_crater_validation(db, limit=a.limit, include_negatives=not a.no_negatives, use_ml=not a.no_ml,
                                  case_set=a.set)
        save_validation(db, "crater_validation" if a.set == "tuning" else "crater_validation_holdout", r,
                        {"limit": a.limit, "case_set": a.set, "criterion": "region"})
        print(json.dumps(r["metrics"], indent=1, default=str))
    write_validation_doc(db)


def cmd_worker(a) -> None:
    from .worker import Worker

    w = Worker(_db(), a.threads)
    if a.until_empty:
        w.run_until_empty()
    else:
        w.start()
        import time

        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            w.stop()


def cmd_pause(a) -> None:
    from .worker import set_paused

    set_paused(_db(), a.cmd == "pause")


def cmd_serve(a) -> None:
    import uvicorn

    uvicorn.run("marswatch.api.app:app", host=a.host, port=a.port, log_level="info")


def cmd_report(a) -> None:
    from .reports import write_survey_report, write_validation_doc

    db = _db()
    write_validation_doc(db)
    print(write_survey_report(db, region=a.region))


def main(argv: list[str] | None = None) -> None:
    from .log import configure

    configure()
    p = argparse.ArgumentParser(prog="marswatch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("init"); s.add_argument("--refresh", action="store_true"); s.set_defaults(f=cmd_init)
    s = sp.add_parser("covering"); s.add_argument("lat", type=float); s.add_argument("lon", type=float); s.set_defaults(f=cmd_covering)
    s = sp.add_parser("discover")
    s.add_argument("--region", default="custom")
    for k in ("lat0", "lat1", "lon0", "lon1"):
        s.add_argument(f"--{k}", type=float, required=True)
    s.add_argument("--enqueue", type=int, default=0, help="queue analysis jobs for the top-N pairs")
    s.add_argument("--res", type=float, default=1.0)
    s.add_argument("--max-area", type=float, default=None)
    s.add_argument("--min-overlap", type=float, default=1.0)
    s.add_argument("--max-scale", type=float, default=0.5)
    s.set_defaults(f=cmd_discover)
    s = sp.add_parser("analyze")
    s.add_argument("before"); s.add_argument("after")
    s.add_argument("--lat", type=float); s.add_argument("--lon", type=float); s.add_argument("--half", type=float, default=500)
    s.add_argument("--res", type=float, default=None); s.add_argument("--no-ml", action="store_true")
    s.add_argument("--kind", default="manual")
    s.set_defaults(f=cmd_analyze)
    s = sp.add_parser("validate")
    s.add_argument("--limit", type=int); s.add_argument("--no-negatives", action="store_true")
    s.add_argument("--injection", action="store_true"); s.add_argument("--registration", action="store_true")
    s.add_argument("--trials", type=int, default=8); s.add_argument("--skip-craters", action="store_true")
    s.add_argument("--no-ml", action="store_true")
    s.add_argument("--set", choices=["tuning", "holdout"], default="tuning")
    s.set_defaults(f=cmd_validate)
    s = sp.add_parser("worker"); s.add_argument("--threads", type=int); s.add_argument("--until-empty", action="store_true"); s.set_defaults(f=cmd_worker)
    for name in ("pause", "resume"):
        s = sp.add_parser(name); s.set_defaults(f=cmd_pause)
    s = sp.add_parser("serve"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000); s.set_defaults(f=cmd_serve)
    s = sp.add_parser("report"); s.add_argument("--region"); s.set_defaults(f=cmd_report)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main(sys.argv[1:])
