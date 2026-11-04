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
         "Every number below was produced by `marswatch validate`, except the run-1 baseline line, which is "
         "transcribed from that run's log (the run was aborted before saving metrics)._", ""]
    L += ["## Summary", "",
          "| set | code | positive runs | recall (usable pairs) | recall, actionable status | recall (QC-rejected = miss) | recall as new impact | FP/km² pre-pre | precision* | @ threshold |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for kind, label in (("crater_validation", "tuning (rules developed on these sites)"), ("crater_validation_holdout", "held-out image pairs")):
        v = latest_validation(db, kind)
        if not v:
            continue
        for th in (0.0, 0.6):
            o = next((x for x in v["metrics"]["operating_points"] if abs(x["threshold"] - th) < 1e-9), None)
            if o:
                L.append(f"| {label} | `{v['code_version']}` | {v['metrics']['n_positive_runs']} | {_fmt(o['recall_any_category'])} | "
                         f"{_fmt(o.get('recall_actionable'))} | "
                         f"{_fmt(o.get('recall_counting_rejected_inputs_as_misses'))} | {_fmt(o['recall_as_new_impact'])} | "
                         f"{_fmt(o['fp_per_km2_prepre'])} | {_fmt(o['precision_window_assumption'])} | {th} |")
    L += ["", "Baseline (validation run 1, before any rule revision, centroid criterion): 12/16 completed positives "
          "matched; see `data/validation/run1_baseline_log.txt` and RESEARCH_LOG.md.", ""]
    for kind, title in (("crater_validation", "Tuning set"), ("crater_validation_holdout", "Held-out image pairs")):
        cv = latest_validation(db, kind)
        if cv:
            L += _crater_section(cv, title)
    inj = latest_validation(db, "injection_sensitivity")
    if inj:
        L += _injection_section(inj)
        L += ["_Note: this easy variant (halo radius 8 × D, contrast ≥ 5 %) saturates at 100 % — every injected "
              "signature is a large smooth darkening. It shows only that such halos are reliably detected; see the "
              "harder variant below._", ""]
    hard = latest_validation(db, "injection_sensitivity_hard")
    if hard:
        L += ["## Detection sensitivity — SYNTHETIC INJECTION, hard variant", "",
              f"Shaded crater bowl only (contrast 0) or bowl + faint compact halo (radius {hard['details'].get('halo_factor')} × D, "
              "contrast 2–3 %), injected into real unchanged HiRISE imagery (run #" + str(hard["id"]) + ").", "",
              "| crater D (m) | halo contrast | n | detection rate |", "|---|---|---|---|"]
        for r in hard["details"]["table"]:
            L.append(f"| {r['diameter_m']} | {r['halo_contrast']} | {r['n']} | {_fmt(r['detection_rate'])} |")
        L.append("")
    rs = latest_validation(db, "registration_synthetic")
    if rs:
        L += _registration_section(rs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))
    return path


def _crater_section(cv: dict, title: str) -> list[str]:
    L: list[str] = []
    if cv:
        m = cv["metrics"]
        L += [f"## {title}: documented new impact craters (Daubar et al. 2022) — validation run #{cv['id']}, code `{cv['code_version']}`", "",
              f"* Sites: {m['n_cases']}; positive runs: {m['n_positive_runs']}; pre-pre controls: {m['n_prepre_runs']}; "
              f"post-post controls: {m['n_postpost_runs']}; failed/rejected runs: {m['n_failed_runs']}; "
              f"skipped (no COG yet): {m.get('n_skipped_runs', 0)}",
              f"* Median rank of the documented change among candidates in its 1 km² window: {_fmt(m.get('match_rank_median'), 1)}; "
              f"ranked #1 in {_fmt((m.get('match_rank_top1_frac') or 0) * 100, 0)}% of detected cases", "",
              "### Operating points (heuristic score threshold)", "",
              "| threshold | recall (usable pairs) | recall (rejected = miss) | recall (as new impact) | TP | FP in positive windows | FP in pre-pre controls | FP/km² (pos. windows) | FP/km² (pre-pre) | precision* |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in m["operating_points"]:
            L.append(f"| {r['threshold']:.1f} | {_fmt(r['recall_any_category'])} | {_fmt(r.get('recall_counting_rejected_inputs_as_misses'))} | {_fmt(r['recall_as_new_impact'])} | {r['tp']} | "
                     f"{r['fp_in_positive_windows']} | {r['fp_in_prepre_controls']} | {_fmt(r['fp_per_km2_positive_windows'])} | "
                     f"{_fmt(r['fp_per_km2_prepre'])} | {_fmt(r['precision_window_assumption'])} |")
        L += ["", "\\* Precision assumes the only real change inside each window is the catalogued crater; any other "
              "non-artifact candidate counts as a false positive. Real undocumented changes would make this pessimistic; "
              "see the per-case review in `docs/VALIDATION.md`.", "",
              "### Sensitivity vs crater diameter (real cases)", "", "| diameter (m) | n | detected | rate |", "|---|---|---|---|"]
        for s in m["sensitivity_by_diameter_real"]:
            L.append(f"| {s['diameter_m']} | {s['n']} | {s['detected']} | {_fmt(s['rate'])} |")
        if m.get("recall_by_illumination"):
            L += ["", "### Recall vs illumination difference (positive pairs)", "",
                  "| Δincidence | n | detected | matched but labelled artifact | recall |", "|---|---|---|---|---|"]
            for g in m["recall_by_illumination"]:
                L.append(f"| {g['group']} | {g['n']} | {g['detected']} | {g['matched_but_labelled_artifact']} | {_fmt(g['recall'])} |")
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
                if "error" in r or "skipped" in r:
                    why = "QC-REJECTED" if r.get("input_rejected") else ("SKIPPED" if "skipped" in r else "ERROR")
                    L.append(f"| {e['ref_id']} | {e['diameter_m']} | {r['before_id'].replace('_RED','')} → {r['after_id'].replace('_RED','')} | — | — | {why} | | | {(r.get('error') or r.get('skipped'))[:70]} | | |")
                    continue
                mm = r.get("match") or {}
                L.append(f"| {e['ref_id']} | {e['diameter_m']} | {r['before_id'].replace('_RED','')} → {r['after_id'].replace('_RED','')} | "
                         f"{r['d_incidence']:.0f}° | {_fmt(r['registration']['check_rms_px'])} | {'yes' if mm else 'no'} | "
                         f"{_fmt(mm.get('score'))} | {mm.get('category', '—')} | {mm.get('status', '—')} | {mm.get('rank', '—')} | "
                         f"{_fmt(r['nearest_dist_m'], 0)} |")
        L.append("")
    return L


def _injection_section(inj: dict) -> list[str]:
    L: list[str] = []
    if inj:
        L += [f"## Detection sensitivity vs size — SYNTHETIC INJECTION (run #{inj['id']})", "",
              "Synthetic dark blast-zone + shaded-bowl signatures injected into *real*, registered, unchanged "
              "(pre-pre) HiRISE imagery. These are not real changes; they measure detectability only.", "",
              "| crater D (m) | halo contrast | n | detection rate |", "|---|---|---|---|"]
        for r in inj["details"]["table"]:
            L.append(f"| {r['diameter_m']} | {r['halo_contrast']} | {r['n']} | {_fmt(r['detection_rate'])} |")
        L.append("")
    return L


def _registration_section(rs: dict) -> list[str]:
    L: list[str] = []
    if rs:
        d = rs["details"]
        L += [f"## Registration accuracy — SYNTHETIC known warps (run #{rs['id']})", "",
              f"Median true-field RMS error {_fmt(d['err_rms_px_median'], 3)} px, max {_fmt(d['err_rms_px_max'], 3)} px over "
              f"{len(d['trials'])} trials (shift ±8 px, rotation ±0.5°, scale ±0.5%, sinusoidal jitter ≤1.5 px, gain 0.5–1.5, noise).", "",
              "| site | true shift (px) | jitter amp (px) | true RMS err (px) | P90 err (px) | checkpoint RMS estimate (px) |", "|---|---|---|---|---|---|"]
        for t in d["trials"]:
            L.append(f"| {t['site']} | {t['true_shift_px'][0]:.1f}, {t['true_shift_px'][1]:.1f} | {t['jitter_amp_px']:.2f} | "
                     f"{t['err_rms_px']:.3f} | {t['err_p90_px']:.3f} | {_fmt(t['checkpoint_rms_px'], 3)} |")
        L.append("")
    return L


def write_survey_report(db: Database, region: str | None = None, path: Path | None = None) -> Path:
    path = path or REPO_ROOT / "docs" / "SURVEY_REPORT.md"
    runs = db.query("SELECT * FROM runs WHERE kind='survey' AND status IN ('done','rejected_input') ORDER BY started_at")
    pairs = {p["pair_id"]: p for p in db.query("SELECT * FROM pairs")}
    if region:
        runs = [r for r in runs if (pairs.get(r["pair_id"]) or {}).get("region") == region]
    done = [r for r in runs if r["status"] == "done"]
    run_ids = [r["run_id"] for r in done]
    cands = []
    if run_ids:
        q = ",".join("?" * len(run_ids))
        cands = db.query(f"SELECT * FROM candidates WHERE run_id IN ({q}) ORDER BY score DESC", run_ids)
    failed = db.query("SELECT * FROM jobs WHERE status='failed' AND kind='analyze_pair'")
    area = sum((r["stats"] or {}).get("analysed_km2", 0) for r in done)
    versions = sorted({r["code_version"] for r in runs})
    regions = sorted({(pairs.get(r["pair_id"]) or {}).get("region") or "?" for r in runs})
    L = [f"# MARSWATCH survey report{f' — {region}' if region else ''}", "",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from the MARSWATCH database. "
         f"Code version(s): {', '.join(f'`{v}`' for v in versions)}._", "",
         "## Scope", "",
         f"* Regions: {', '.join(regions)}",
         "  * Lycus Sulci (Olympus Mons aureole), 24–30°N, 218–228°E — primary",
         "  * Arabia Terra W, 5–15°N, 0–10°E — secondary",
         "* Pair selection: best-matched repeat HiRISE pairs (Δt ≥ 200–300 d, Δinc ≤ 10–12°, Δsun az ≤ 25–30°, "
         "Δemission ≤ 15°), spatially distinct (≥ 2–4 km apart); ≤ 12 km² of each overlap analysed at 1 m/px "
         "(centre crop), with resolution fallback to 2/4 m when registration is poor.",
         f"* Image pairs analysed: {len(done)} (+{len(runs) - len(done)} rejected by input QC); failed jobs: {len(failed)}",
         f"* Area analysed (after masking invalid / poorly registered areas): **{area:.1f} km²**",
         f"* Candidates: {len(cands)}", ""]
    by: dict = {}
    for c in cands:
        by[c["classification"]] = by.get(c["classification"], 0) + 1
    L += ["## Candidates by status", ""] + [f"* {k}: {v}" for k, v in sorted(by.items())] + [""]
    byc: dict = {}
    for c in cands:
        byc[c["category"]] = byc.get(c["category"], 0) + 1
    L += ["## Candidates by category (heuristic)", ""] + [f"* {k}: {v}" for k, v in sorted(byc.items(), key=lambda x: -x[1])] + [""]
    L += ["## Analysed pairs", "",
          "| pair | region | Δt (d) | Δinc | analysed km² | res (m) | registration | checkpoint RMS px | cand. | plausible | notes |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        reg = r["registration"] or {}
        pr = pairs.get(r["pair_id"]) or {}
        prm = r["params"] or {}
        n = sum(1 for c in cands if c["run_id"] == r["run_id"])
        npl = sum(1 for c in cands if c["run_id"] == r["run_id"] and c["classification"] == "plausible_unverified")
        res = prm.get("res_m")
        try:
            doc = json.loads((Path(r["out_dir"]) / "run.json").read_text())
            res = doc["params"]["res_m"]
            hist = doc["params"].get("resolution_history")
        except Exception:
            hist = None
        note = "QC-rejected: " + ((r["stats"] or {}).get("rejected") or "")[:80] if r["status"] == "rejected_input" else (
            "fallback " + "→".join(str(h["res_m"]) for h in hist) if hist else "")
        if pr.get("suitability_notes"):
            note = (note + "; " if note else "") + pr["suitability_notes"][:90]
        L.append(f"| {r['pair_id']} | {pr.get('region', '')} | {_fmt(pr.get('dt_days'), 0)} | {_fmt(pr.get('d_incidence'), 1)} | "
                 f"{_fmt((r['stats'] or {}).get('analysed_km2'))} | {res} | {reg.get('status', '—')} ({_fmt(reg.get('quality'))}) | "
                 f"{_fmt(reg.get('check_rms_px'))} | {n} | {npl} | {note} |")
    pl = [c for c in cands if c["classification"] == "plausible_unverified"]
    L += ["", f"## Plausible unverified candidates ({len(pl)}; top 25 shown)", "",
          "These passed the automated artifact tests. They are **not** confirmed discoveries. Follow-up results "
          "(third-image persistence, HiRISE targeting history, catalogue) are shown where run. "
          "\"Triage\" notes are a preliminary visual assessment by the operating agent, not expert review.", ""]
    for c in pl[:25]:
        fu = (c["features"] or {}).get("followup") or {}
        t = fu.get("third_image") or {}
        L += [f"### Candidate {c['id']} — {c['category']} — score {c['score']:.2f}", "",
              f"* Pair `{c['pair_id']}`; location (before frame) {c['lat']:.5f}°N {c['lon']:.5f}°E; "
              f"area {c['area_m2']:.0f} m² (≈{c['eq_diameter_m']:.1f} m); local registration quality {_fmt(c['registration_quality'])}",
              f"* Evidence for: {'; '.join(c['evidence_for'] or [])}",
              f"* Evidence against: {'; '.join(c['evidence_against'] or []) or 'none recorded'}"]
        if fu:
            L.append(f"* Follow-up: third image {t.get('product_id', 'none')} → "
                     f"{'reappears' if t.get('reappears') else ('no matching change' if 'reappears' in t else t.get('error', 'not run'))}; "
                     f"targeting tags {list((fu.get('targeting') or {}).keys()) or 'none'}; catalogue within 2 km: "
                     f"{[x['ref_id'] for x in fu.get('catalogue_within_2km', [])] or 'none'}")
        if c.get("notes"):
            L.append(f"* Triage: {c['notes'].strip()}")
        L += [f"* Chip: `data/runs/{c['run_id']}/{(c['chips'] or {}).get('chip')}`", ""]
    arts = [c for c in cands if c["classification"] == "likely_artifact"]
    flagged = [r for r in done if ((r["stats"] or {}).get("scene_test") or {}).get("flagged")]
    if flagged:
        L += ["## Scene-level artifact test", "",
              "| pair | candidates | on steep relief | demoted | kept as strength outliers |", "|---|---|---|---|---|"]
        for r in flagged:
            st = r["stats"]["scene_test"]
            L.append(f"| {r['pair_id']} | {st['n_candidates']} | {st['frac_on_relief'] * 100:.0f}% | {st['demoted']} | {st['survived_as_outliers']} |")
        L.append("")
    L += ["## False positives and uncertainties", "",
          f"* {len(arts)} candidates were automatically classified as likely artifacts (shadow dipoles, cast shadows, "
          "contrast/haze differences, poor local registration).",
          f"* {by.get('insufficient_evidence', 0)} candidates had insufficient evidence (small, weak, or in poorly registered areas).",
          "* From validation, the expected false-positive density in well-registered, non-dust-storm pairs is a few per km² "
          "at score 0 and ~1–3 per km² at score ≥ 0.6 (see VALIDATION_RESULTS.md): most plausible candidates in a survey "
          "are expected to be false positives or real-but-mundane changes (dust redistribution, fading streaks).",
          "* Pairs including dust-storm-epoch images showed systematic ring artifacts around relief; these are penalised but not eliminated.", ""]
    if failed:
        L += ["## Failed jobs", ""] + [f"* job {f['id']} ({f['pair_id']}): {(f['error'] or '').splitlines()[0][:200]}" for f in failed] + [""]
    L += ["## Recommended follow-up", "",
          "1. Expert visual review of every plausible candidate in the Before/After viewer (blink and slider modes).",
          "2. For impact-like candidates: request/identify CTX coverage to narrow the formation date; search the HiRISE "
          "caption archive and the Daubar et al. catalogue updates; check for a crater bowl at full 0.25 m resolution.",
          "3. For slope-streak/albedo candidates: compare with additional HiRISE/CTX epochs to establish formation vs. fading "
          "and seasonality.",
          "4. Re-run poorly registered pairs after DEM-based orthorectification (HiRISE/CTX DTMs from USGS STAC) to remove parallax.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))
    return path
