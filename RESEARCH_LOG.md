# MARSWATCH research log

Chronological record of decisions, experiments, failures and findings. Times are UTC, 2026-11-04.
Numbers quoted here come from logs in `data/logs/` and the `validation_runs` table; the final
measured metrics are in `docs/VALIDATION_RESULTS.md`.

---

## Phase 1 — data access (02:32–02:45)

**Archive reconnaissance (all verified with real requests):**

| Endpoint | Result |
|---|---|
| `hirise-pds.lpl.arizona.edu/PDS/` | 200 — PDS3 volume with `INDEX/RDRCUMINDEX.TAB` (168.7 MB, 205,302 rows, 60 columns incl. 4 corner lat/lon, incidence, emission, phase, sub-solar azimuth, Ls, rationale) |
| `stac.astrogeology.usgs.gov/api` | 200 — collection `mro_hirise_uncontrolled_observations`, 202,882 items, COG assets on `astrogeo-ard` S3 |
| `oderest.rsl.wustl.edu` (PDS Geosciences ODE) | timed out from our network — not used |
| `planetarydata.jpl.nasa.gov` (PDS imaging, CTX EDRs) | 200 — but CTX EDRs need ISIS3; deferred (see below) |
| `murray-lab.caltech.edu` (global CTX mosaic) | timed out — not used |
| `trek.nasa.gov/tiles` | 200 — used only for map basemaps (level-0 tile matrix 2×1, matches Leaflet EPSG:4326) |

**Decision: COGs as the primary imagery source.** Test read of ESP_093796_2260_RED: open 0.9 s,
1/32 overview 0.34 s, full-resolution 1024² window 0.93 s. The same 512² window from the PDS JP2
via `/vsicurl/` took **52 s** — kept only as an automatic fallback. COGs embed DN→I/F scale/offset
and USGS `provenance.txt` traces each COG to its PDS JP2 (`gdalwarp -r cubic -t_srs IAU_2015:49910`).

**Decision: PDS index for discovery, not STAC search.** The index has rationale strings, incidence,
phase, Ls, sub-solar/north azimuths that STAC lacks; parsed into SQLite with an R-tree in 6.5 s
(103,933 RED products). Useful rationale counts: "Candidate recent impact site" 1,775, "Monitoring
new impact site" 652, "Slope streak monitoring" 392, "Dune monitoring in crater" 353.

**Ground truth found:** Daubar et al. (2022) Table S1 (Zenodo 6604912), 1,203 dated new impacts.
Header quirk recorded: latitude column labelled "deg E", longitude labelled "deg N". Of 1,203,
**19** have a ≤0.5 m HiRISE image before the catalogue's "before" date and one after its "after"
date covering the crater (150 m margin). Relaxing to 1 m binned products or 60 m margin adds none.

**CTX decision:** CTX EDRs are raw (companded 8-bit, unprojected, uncalibrated). Comparing two
CTX EDRs meaningfully needs ISIS3 + SPICE kernels (multi-GB, conda) — out of scope for a Mac-mini
deployment without ISIS. Not integrated; recorded as a limitation rather than faked with a
homography on raw frames.

## Phase 2 — first real pair (02:44–02:50)

Pair: PSP_007168_1980 (2008) → ESP_056155_1980 (2018), Daubar crater D22-0887 (D = 9.1 m).

* Raw georeferenced overlay showed ~160 m misalignment (uncontrolled SPICE pointing).
* Coarse NCC (4 m, ±600 m) found dx = 157 m, dy = 35 m; refined at 2 m → 159 m / 35 m.
* Fine field: 461/576 patches matched, 395 RANSAC inliers; **held-out checkpoint RMS 0.73 px
  (0.37 m)** on 529 independent points; high-pass NCC 0.05 → 0.72.
* I/F differed by ×0.45 between dates (atmosphere/season) → blockwise trimmed gain/offset fit.
* Method A found the blast zone (187 m, |z| up to 12.9) plus two small components on an old crater
  rim forming a bright/dark pair — a shadow dipole (Δincidence 21°).
* **Finding:** the blast-zone centre lies ~155 m from the catalogue position in the *before*
  frame but within ~10 m in the *after* frame → catalogue coordinates follow the after image's
  pointing. Matching therefore uses the after-image frame.

## Phase 3 — detection and validation

### Validation run 1 (baseline; 02:54–03:17, aborted)
* Settings: centroid-distance criterion (≤ 60 m, or 150 m when the after image isn't the
  catalogue's), Methods A+B+C, 1 km² windows at 0.5 m.
* Result over completed runs: **12/16 positives matched**, 2 pre-pre and 13 post-post controls.
* **Failure (process):** a post-post control used ESP_093882_2075 (acquired 2026), not yet in the
  USGS COG bucket. JP2 fallback worked but took > 20 min; because results were only saved at the
  end, I aborted the run and kept the per-run log (`data/validation/run1_baseline_log.txt`).
  Fixes: per-site checkpointing; batch validation skips pairs without COGs and records them.
* **Failure (provenance):** `code_version()` hashed source files at call time, so runs after I
  edited files recorded the wrong hash. Fixed: hash computed once at import.

### Error analysis after run 1
1. **D22-0230 miss** — before image PSP_004440_2125 is pure noise with CCD striping. Acquired
   2007-07-08, Ls 272° — inside the **MY28 planet-encircling dust storm**. → Added a structure-SNR
   QC metric (DoG band std / Immerkær noise σ at 0.5 m). Usable images 4.6–7.7; this one 1.0.
   Lag-3 autocorrelation of the high-pass image was tried first and did **not** separate the cases
   (values −0.2…+0.2 for both) — abandoned.
2. **D22-0514 "miss"** — the top-ranked candidate (score 1.0) *was* the crater's 220 m blast zone,
   but its centroid lay 76 m from the catalogue point. → Validation criterion revised to "reference
   point inside the detected region (bbox + 20 m) or within tolerance"; the centroid criterion is
   still computed and reported.
3. **Cluster members** — candidates 94–99 lie 100–250 m from D22-0514, a catalogued *cluster*
   impact; they are other craters of the same event. → `known_documented` association extended to
   500 m for catalogued clusters (darkening/mixed, non-artifact candidates only).
4. **Category order** — D22-0761's elongated, rayed blast zone was labelled "slope streak". →
   Radial-darkening test now precedes the elongation rule.
5. **Audit of 54 "plausible" candidates > 600 m from any catalogued crater** (contact sheet):
   * one genuine-looking change (a dark streak that faded);
   * ~15 from a single pair with a hazy, nearly shadowless before image (PSP_004952_2035,
     2007-08-17, Ls 297° — again the MY28 dust storm) → shading differences;
   * several on cast-shadow edges where only one polarity crossed threshold (dipole test missed).
   → Added **shadow-fraction** and **albedo-normalised context-contrast ratio** tests. A first
   version of the contrast test used raw Laplacian variance; I realised a real dark blast zone
   (multiplicative albedo change) would trip it, and switched to coefficient of variation in a
   wider context window before running it.
6. **D22-0343 miss (unresolved)** — no change visible within ±500 m of the catalogue point in
   ESP_018784 → ESP_034357; the strongest darkening 443 m away is a shadow-length change on a mesa.
   Possible causes: subtle halo of a 4.6 m cluster impact at 0.5 m, or a larger catalogue-to-HiRISE
   offset. Kept as a miss.

**Overfitting guard:** because these rules were revised after looking at run-1 results on the
same 19 sites, I built a **held-out set**: alternative image pairs at the same sites never
inspected during development (18 positive pairs, 9 extra controls), run with the final code.

### Validation run 2 (tuning set, code with hard SNR gate)
* The SNR gate rejected PSP_004952_2035 (SNR 0.89) — the hazy image in which run 1 *had* found
  D22-0673 — and ESP_055943_1890 (0.71) and ESP_055702_1775 (0.76).
* **Finding:** all four images that fail the gate were acquired during the two global dust storms
  (MY28: 2007-07-08 Ls 272°, 2007-08-17 Ls 297°; MY34: 2018-06-14 Ls 193°, 2018-07-03 Ls 204°).
  The metric knows nothing about dates — this is independent physical confirmation.
* **Revision:** a hard gate discards marginal but usable data. New rule: low SNR rejects a pair only
  if registration also fails; otherwise the run proceeds and every candidate carries a haze penalty
  (+0.2 artifact index) and explicit evidence-against.
* Also fixed: a shadow change near a catalogued crater was labelled `known_documented` because
  "known" took precedence over "artifact". Artifact status now takes precedence.

### Held-out run — final code `0.3.0+bb6aa95341` (the key generalisation result)
* 17 held-out positive pairs (alternative before/after images at the same 19 sites), 2 pre-pre and
  5 post-post controls, 1 QC-rejected, 1 skipped (no COG yet).
* **Recall 9/17 = 0.53** (0.50 counting the QC rejection as a miss), versus 0.94 on the tuning pairs.
  False positives were low: 0.6 /km² in pre-pre controls, 1.3 /km² in positive windows (score ≥ 0);
  precision* 0.33 at score ≥ 0 and 0.53 at ≥ 0.6. Median rank of the documented crater: 1.
* Why the drop (per-pair inspection):
  - **Illumination geometry**: held-out pairs are each site's *next-best* pairs, often with
    Δinc 14–21°. Recall: 0.56 (Δinc ≤ 5°, n = 9), 1.0 (5–10°, n = 2), 0.33 (> 10°, n = 6).
  - **Artifact rules cost recall**: D22-0887's blast zone (cleanly found in the tuning pair) is
    labelled an illumination artifact at Δinc = 21°; D22-0673's crater in a dust-storm-epoch pair
    is pushed to artifact by the haze penalties. The rules trade recall for precision.
  - **Genuine misses**: D22-0343 (never found in any pair), D22-0412 (2.4 m; found only in the
    tuning pair), D22-0971 (marginal registration), D22-1128 second pair (registration failed).
* Conclusion recorded in LIMITATIONS.md: expect roughly half of catalogue-class new impacts to be
  recovered from an arbitrary well-registered HiRISE pair; the 0.94 tuning figure is optimistic.

### Validation run 3 (tuning set, final detection code)
* Recorded code hash `0.3.0+174dbb81d7` differs from the held-out run's `bb6aa95341` only because
  reporting/validation/API files were edited between the runs; `git diff` against the freeze commit
  confirms the detection path (`detect/`, `pipeline`, `registration`, `align`, `normalize`,
  `imagery`, `discovery`, `geometry`, `archive/`) is byte-identical.
* 17 positive pairs (3 QC-rejected/failed, 1 skipped): **recall 0.88** on usable pairs (0.79 counting
  rejections as misses; 0.71 as new-impact category). Score ≥ 0.6: recall 0.71, FP 0.9 /km² in
  positive windows, 0.5 /km² in pre-pre controls, precision* 0.46.
* Compared with run 2 (0.94), the final rules lose one tuning-set crater (the haze/low-SNR penalties
  now allow D22-0673's hazy pair to run, and its crater ends up labelled artifact).
* Registration: 33 runs, median checkpoint RMS 0.46 px, 28 good / 5 marginal / 0 poor; median
  corrected pointing offset 42 m. Method C AUC 0.79 (held-out 0.75). ~22 s per km² at 0.5 m/px
  (4 vCPU, network-bound, concurrent survey), peak RSS ≈ 1 GB.

### Synthetic tests (labelled)
* **Registration, known warps** (8 trials, real imagery, QC-passing images only): true-field RMS
  error median 0.20 px, max 0.50 px; the checkpoint estimate tracks it but reads 10–35 % low.
* **Injection, easy variant** (halo radius 8 × D, contrast 5–20 %): 100 % everywhere — saturated,
  uninformative (recorded, not hidden).
* **Injection, hard variant** (bowl only, or faint 2–3 % halo of radius 3 × D; one smooth site,
  D22-1020, 0.5 m/px): bowl-only craters of 1–2 m (2–4 px) are never detected; ≥ 3 m (6 px) always;
  a faint halo lifts 2 m craters to 86–100 %. Real-scene recall (held-out ≈ 0.5) is far lower than
  this, so the practical limit is scene complexity (relief, illumination, haze), not raw sensitivity.

## Phase 5–6 — autonomous survey

**Region choice.** Counted well-matched repeat pairs (Δinc ≤ 10°, Δaz ≤ 25°, Δt ≥ 300 d,
Δemission ≤ 15°): Elysium/InSight 206, Arabia Terra W 126, **Lycus Sulci 106**, Tharsis W 32,
Amazonis 21. Chose **Lycus Sulci (Olympus Mons aureole, 24–30°N, 218–228°E)**: dusty (blast zones
and slope streaks visible), not dominated by one monitoring target. Only 8 spatially distinct
sites qualify, so **Arabia Terra W (5–15°N, 0–10°E)** was added as a secondary region (10 pairs).

**Survey failure 1 — registration on dust-mantled terrain.** The best-scoring Lycus pair
(ESP_017585_2080 → ESP_078865_2080, Δinc 0.04°) failed registration (quality 0.07, checkpoint RMS
3.2 px). Visual inspection: obvious slope-streak changes, alignment trivial by eye at coarse scale.
Causes: (a) the coarse/fine band-pass (σ = 4/6 px) removes the large-scale relief that carries the
signal on dust-mantled terrain; (b) phase angles 34° vs 52° at equal incidence → different viewing
azimuth → several metres of relief parallax on rugged terrain, not modelled without a DEM.
Fixes: coarse search over two band-pass scales (σ = 4, 12 px, best distinctness); adaptive fine
registration (second configuration with larger patches / σ = 12, keep the better checkpoint
quality); **resolution fallback** (re-analyse at 2 m, then 4 m, when registration is poor — slope
streaks remain resolvable); Δphase penalty added to pair suitability. Larger patches alone did not
fix it at 1 m (quality 0.06) — the fallback is what makes such pairs usable.

**Resume test (real):** killing the worker mid-job left job 3 in `running`; on restart the worker
logged "re-queued 1 interrupted jobs" and continued.

**Survey failure 2 — attitude shear on long strips.** Even at 4 m the same pair stayed poor. The
fitted affine had shear −0.03 (x-offset drifting ~160 m over the 5.4 km strip): uncontrolled
attitude error, not translation. Added **block-affine initialisation** (coarse offsets in ~1.2 km
blocks → trimmed affine → fine search centred on the prediction; active only for areas > 1.2 km).
On that pair the block fit then showed a 6 % x-scale, which is not physical: the terrain is
dominated by parallel aeolian ridges (aperture problem) and has viewing-azimuth parallax. It remains
unregistrable without DEM orthorectification; the pipeline reports it as poor and refuses detections.
On a normal pair the block affine is near identity ([[1.0004, 0.0025], [−0.0003, 0.9953]]).

**Survey audit — first candidates (before freeze).** Contact sheet of the top 24 "plausible":
* PSP_004175_2060 → ESP_057118_2060: dark rings around every crater/mound. Before image 2007-06-17
  (Ls 259°, onset of the MY28 storm), after 2018-10-03 (MY34 storm decay): **differential haze**
  fills shaded slopes non-linearly. Added PSF matching (first version used Laplacian energy, which
  is dominated by pixel noise and chose σ = 0.5 px; switched to DoG band energy → σ = 1 px), but the
  rings persisted (27 plausible in 4 km²). Did *not* switch to quantile tone mapping this late
  (risk of absorbing real blast zones). Instead: global-dust-storm epochs (MY28 2007-06-01…11-15,
  MY34 2018-05-25…10-31) now cut pair suitability ×0.3 and add evidence-against.
* ESP_050129 → ESP_076478: ~3 % brightening patches on very smooth dusty terrain. Checked the
  shadow test on candidate 1129 — region minimum I/F 0.137 vs shadow threshold 0.107, so not a
  shadow; plausibly real dust redistribution (wind streaks / dust-devil tracks).
* Candidate 1346: a dark, rayed, blast-zone-like spot that **faded** between 2007 and 2018 —
  consistent with documented blast-zone fading (followed up below).
* Candidates from a pair with *poor* overall registration still scored 0.8 → global registration
  status `poor` now caps candidates at `insufficient_evidence`.

**Code freeze (03:40): `0.3.0+bb6aa95341`.** All final validation (held-out, tuning re-run) and
the survey were re-run from scratch on this version; earlier survey runs are kept as `survey_dev`.

**Test bug found (synthetic registration):** the known-warp test compared the estimated field with
+f, but the registration estimates the inverse field g = −f(p+g). Initial "true error" 12–20 px vs
checkpoint estimates 0.03–0.26 px exposed it. After fixed-point inversion, true RMS error
0.29 px and 0.024 px vs checkpoint estimates 0.26 and 0.03 px — **the held-out checkpoint RMS is a
faithful estimate of true registration error.** The test also initially drew a dust-storm image as
its source; it now skips images below the QC threshold.

### Survey findings (frozen code)

* **Candidate 1987 — new dark slope streak, Lycus Sulci (≈25.471°N, 220.224°E, before-image frame).**
  ~260 m long, absent in PSP_008513_2060 (2008-05), present in ESP_045435_2055 (2016-04); |z| = 17.9,
  aspect 8, CNN z = 5.8. Follow-up: only two HiRISE observations cover it (no third image);
  neither targets slope streaks (after-image rationale "Layers in Trough Wall Northwest of
  Olympus Rupes"); nothing in the Daubar catalogue (impacts only). Population-level slope-streak
  formation in the Olympus Mons aureole is documented (Heyer et al. 2019, Icarus, CTX survey), so
  this individual streak may be included in such counts. Status: **plausible unverified**.
* **Candidate 2115 — new dark slope streak (heuristically mis-labelled "new impact crater").**
  Formed between ESP_069265_2070 (2021-05-06) and ESP_086750_2070 (2025-01-27) at ≈26.458°N,
  227.118°E; |z| = 16.4, CNN z = 15.0. Follow-up: the location is a **HiRISE slope-streak
  monitoring site** (all three covering observations; caption "Dark Slope Streak Monitoring Site in
  Lycus Sulci") — the HiRISE team is very likely aware. The impact label came from the radial-
  darkening rule (61 % angular coverage on a curved, compact streak); recorded as a category error
  rather than patched after the freeze.

### Final survey (frozen code)
* 18 pairs queued (8 Lycus Sulci, 10 Arabia Terra W); 17 analysed, 1 rejected. The rejection of
  PSP_008679_1905/ESP_088815_1910 reports "structure SNR 0.0": that means *no valid pixels* in the
  QC window (recent product not covering it / not yet in the COG bucket), not haze — the rejection
  message wording is misleading in this case (known issue).
* 157 km² analysed; 7 pairs needed the resolution fallback (2–4 m). 231 candidates: 143 plausible,
  81 likely artifact, 7 insufficient evidence; no catalogued impacts fall in the analysed areas.
* **Agent triage of all 143 plausible** (labelled as preliminary, not expert review; automated status
  unchanged): **4 credible new dark slope streaks** — 1987, 1988, 1989 (one pair,
  PSP_008513_2060 → ESP_045435_2055, 2008-05 → 2016-04, ~25.47–25.49°N, 220.21–220.23°E; not a
  monitoring target, no later image, not catalogued) and 2115 (HiRISE slope-streak monitoring site,
  2021-05 → 2025-01). 3 uncertain diffuse albedo changes (2415–2417). The rest — dominated by three
  pairs with 24–53 candidates each — are pair-level systematic shading/parallax responses on relief.
* **Lesson / top improvement:** the artifact tests are per-candidate; a pair whose photometry differs
  produces dozens of individually unremarkable detections on relief. A scene-level test (fraction of
  detections co-located with high relief, or detection density vs relief) is the most valuable next
  step, followed by DEM orthorectification.
