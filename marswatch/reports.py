"""Generation of the validation document and the survey report from the database."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .config import REPO_ROOT
from .db import Database


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def latest_validation(db: Database, kind: str) -> dict | None:
    return db.one("SELECT * FROM validation_runs WHERE kind=? ORDER BY id DESC LIMIT 1", [kind])


def write_validation_doc(db: Database, path: Path | None = None) -> Path:
    path = path or REPO_ROOT / "docs" / "VALIDATION_RESULTS.md"
    L = ["# MARSWATCH — measured validation results", "",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from the `validation_runs` table. "
         "Every number below was produced by `marswatch validate`; nothing is hand-entered._", ""]
    cv = latest_validation(db, "crater_validation")
    if cv:
        m = cv["metrics"]
        L += [f"## 1. Documented new impact craters (Daubar et al. 2022) — validation run #{cv['id']}, code `{cv['code_version']}`", "",
              f"* Sites: {m['n_cases']}; positive runs: {m['n_positive_runs']}; pre-pre controls: {m['n_prepre_runs']}; "
              f"post-post controls: {m['n_postpost_runs']}; failed runs: {m['n_failed_runs']}",
              f"* Median rank of the documented change among candidates in its 1 km² window: {_fmt(m.get('match_rank_median'), 1)}; "
              f"ranked #1 in {_fmt((m.get('match_rank_top1_frac') or 0) * 100, 0)}% of detected cases", "",
              "### Operating points (heuristic score threshold)", "",
              "| threshold | recall (any category) | recall (as new impact) | TP | FP in positive windows | FP in pre-pre controls | FP/km² (pos. windows) | FP/km² (pre-pre) | precision* |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in m["operating_points"]:
            L.append(f"| {r['threshold']:.1f} | {_fmt(r['recall_any_category'])} | {_fmt(r['recall_as_new_impact'])} | {r['tp']} | "
                     f"{r['fp_in_positive_windows']} | {r['fp_in_prepre_controls']} | {_fmt(r['fp_per_km2_positive_windows'])} | "
                     f"{_fmt(r['fp_per_km2_prepre'])} | {_fmt(r['precision_window_assumption'])} |")
        L += ["", "\\* Precision assumes the only real change inside each window is the catalogued crater; any other "
              "non-artifact candidate counts as a false positive. Real undocumented changes would make this pessimistic; "
              "see the per-case review in `docs/VALIDATION.md`.", "",
              "### Sensitivity vs crater diameter (real cases)", "", "| diameter (m) | n | detected | rate |", "|---|---|---|---|"]
        for s in m["sensitivity_by_diameter_real"]:
            L.append(f"| {s['diameter_m']} | {s['n']} | {s['detected']} | {_fmt(s['rate'])} |")
        L += ["", "### Illumination breakdown (false positives per km² at score ≥ 0.4)", "", "| group | runs | FP/km² |", "|---|---|---|"]
        for s in m["illumination_breakdown"]:
            L.append(f"| {s['group']} | {s['runs']} | {_fmt(s['fp_per_km2_at_0.4'])} |")
        rg = m["registration_real"]
        L += ["", "### Registration on real pairs", "",
              f"* Runs: {rg['runs']}; held-out checkpoint RMS median {_fmt(rg['checkpoint_rms_px_median'])} px, "
              f"P90 {_fmt(rg['checkpoint_rms_px_p90'])} px; status counts {rg['status_counts']}; "
              f"median uncontrolled-pointing offset corrected {_fmt(rg['coarse_offset_m_median'], 0)} m", "",
              "### Method C (pretrained CNN features) — ablation", "",
              f"* deep-feature z of documented changes (median): {_fmt(m['ml_deep_z']['documented_median'])}; "
              f"of other non-artifact candidates: {_fmt(m['ml_deep_z']['other_candidates_median'])}; "
              f"AUC separating them: {_fmt(m['ml_deep_z']['auc'])}", "",
              "### Post-post controls (crater present in both images)", "",
              f"* Non-artifact detections within 100 m of the crater: {m['postpost_detections_near_crater']} "
              "(blast-zone fading/brightening is a real, documented process — Daubar et al. 2016 — so these are not counted as false positives)",
              f"* Non-artifact detections elsewhere, score ≥ 0.4, per km²: {_fmt(m['postpost_nonartifact_elsewhere_per_km2'])}", "",
              "### Performance", "",
              f"* Median wall time per 1 km² validation run (0.5 m/px, incl. remote reads): {_fmt(m['performance']['median_seconds_per_run'], 1)} s; "
              f"{_fmt(m['performance']['seconds_per_km2'], 1)} s/km²; peak RSS {_fmt(m.get('peak_rss_mb'), 0)} MB", ""]
        if m.get("failures"):
            L += ["### Failed runs (recorded, not hidden)", ""]
            for f in m["failures"]:
                L.append(f"* {f['kind']} {f['before']} → {f['after']}: {f['error'][:200]}")
            L.append("")
        # per-case table
        L += ["### Per-case results (positive pairs)", "",
              "| ref | D (m) | before → after | Δinc | reg RMS px | matched | score | category | status | rank | dist (m) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for e in cv["details"]["cases"]:
            for r in e["runs"]:
                if r["kind"] != "positive":
                    continue
                if "error" in r:
                    L.append(f"| {e['ref_id']} | {e['diameter_m']} | {r['before_id']} → {r['after_id']} | — | — | ERROR | | | | | |")
                    continue
                mm = r.get("match") or {}
                L.append(f"| {e['ref_id']} | {e['diameter_m']} | {r['before_id'].replace('_RED','')} → {r['after_id'].replace('_RED','')} | "
                         f"{r['d_incidence']:.0f}° | {_fmt(r['registration']['check_rms_px'])} | {'yes' if mm else 'no'} | "
                         f"{_fmt(mm.get('score'))} | {mm.get('category', '—')} | {mm.get('status', '—')} | {mm.get('rank', '—')} | "
                         f"{_fmt(r['nearest_dist_m'], 0)} |")
        L.append("")
    inj = latest_validation(db, "injection_sensitivity")
    if inj:
        L += [f"## 2. Detection sensitivity vs size — SYNTHETIC INJECTION (run #{inj['id']})", "",
              "Synthetic dark blast-zone + shaded-bowl signatures injected into *real*, registered, unchanged "
              "(pre-pre) HiRISE imagery. These are not real changes; they measure detectability only.", "",
              "| crater D (m) | halo contrast | n | detection rate |", "|---|---|---|---|"]
        for r in inj["details"]["table"]:
            L.append(f"| {r['diameter_m']} | {r['halo_contrast']} | {r['n']} | {_fmt(r['detection_rate'])} |")
        L.append("")
    rs = latest_validation(db, "registration_synthetic")
    if rs:
        d = rs["details"]
        L += [f"## 3. Registration accuracy — SYNTHETIC known warps (run #{rs['id']})", "",
              f"Median true-field RMS error {_fmt(d['err_rms_px_median'], 3)} px, max {_fmt(d['err_rms_px_max'], 3)} px over "
              f"{len(d['trials'])} trials (shift ±8 px, rotation ±0.5°, scale ±0.5%, sinusoidal jitter ≤1.5 px, gain 0.5–1.5, noise).", "",
              "| site | true shift (px) | jitter amp (px) | true RMS err (px) | P90 err (px) | checkpoint RMS estimate (px) |", "|---|---|---|---|---|---|"]
        for t in d["trials"]:
            L.append(f"| {t['site']} | {t['true_shift_px'][0]:.1f}, {t['true_shift_px'][1]:.1f} | {t['jitter_amp_px']:.2f} | "
                     f"{t['err_rms_px']:.3f} | {t['err_p90_px']:.3f} | {_fmt(t['checkpoint_rms_px'], 3)} |")
        L.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))
    return path


def write_survey_report(db: Database, region: str | None = None, path: Path | None = None) -> Path:
    path = path or REPO_ROOT / "docs" / "SURVEY_REPORT.md"
    runs = db.query("SELECT * FROM runs WHERE kind='survey' AND status='done' ORDER BY started_at")
    if region:
        pids = {p["pair_id"] for p in db.query("SELECT pair_id FROM pairs WHERE region=?", [region])}
        runs = [r for r in runs if r["pair_id"] in pids]
    run_ids = [r["run_id"] for r in runs]
    cands = []
    if run_ids:
        q = ",".join("?" * len(run_ids))
        cands = db.query(f"SELECT * FROM candidates WHERE run_id IN ({q}) ORDER BY score DESC", run_ids)
    failed = db.query("SELECT * FROM jobs WHERE status='failed'")
    area = sum((r["stats"] or {}).get("analysed_km2", 0) for r in runs)
    L = [f"# MARSWATCH survey report{f' — {region}' if region else ''}", "",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from the MARSWATCH database._", "",
         "## Scope", "",
         f"* Image pairs analysed: {len(runs)}", f"* Area analysed: {area:.1f} km²",
         f"* Candidates: {len(cands)}", f"* Failed jobs: {len(failed)}", ""]
    by = {}
    for c in cands:
        by.setdefault(c["classification"], 0)
        by[c["classification"]] += 1
    L += ["## Candidates by status", ""] + [f"* {k}: {v}" for k, v in sorted(by.items())] + [""]
    byc = {}
    for c in cands:
        byc.setdefault(c["category"], 0)
        byc[c["category"]] += 1
    L += ["## Candidates by category (heuristic)", ""] + [f"* {k}: {v}" for k, v in sorted(byc.items(), key=lambda x: -x[1])] + [""]
    L += ["## Analysed pairs", "", "| pair | area km² | registration | checkpoint RMS px | candidates | plausible |", "|---|---|---|---|---|---|"]
    for r in runs:
        reg = r["registration"] or {}
        n = sum(1 for c in cands if c["run_id"] == r["run_id"])
        npl = sum(1 for c in cands if c["run_id"] == r["run_id"] and c["classification"] == "plausible_unverified")
        L.append(f"| {r['pair_id']} | {_fmt((r['stats'] or {}).get('analysed_km2'))} | {reg.get('status')} ({_fmt(reg.get('quality'))}) | "
                 f"{_fmt(reg.get('check_rms_px'))} | {n} | {npl} |")
    L += ["", "## Top plausible unverified candidates", "",
          "These passed the automated artifact tests. They are **not** confirmed discoveries.", ""]
    for c in [c for c in cands if c["classification"] == "plausible_unverified"][:25]:
        L += [f"### Candidate {c['id']} — {c['category']} — score {c['score']:.2f}", "",
              f"* Pair `{c['pair_id']}`, run `{c['run_id']}`",
              f"* Location (before-image frame) {c['lat']:.5f}°N {c['lon']:.5f}°E; area {c['area_m2']:.0f} m² (≈{c['eq_diameter_m']:.1f} m)",
              f"* Registration quality (local) {_fmt(c['registration_quality'])}",
              f"* Evidence for: {'; '.join(c['evidence_for'] or [])}",
              f"* Evidence against: {'; '.join(c['evidence_against'] or []) or 'none recorded'}",
              f"* Chip: `data/runs/{c['run_id']}/{(c['chips'] or {}).get('chip')}`", ""]
    if failed:
        L += ["## Failed jobs", ""] + [f"* job {f['id']} ({f['pair_id']}): {(f['error'] or '').splitlines()[0][:200]}" for f in failed] + [""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))
    return path
