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

### Validation run 3 (tuning set) and held-out run — final code
See `docs/VALIDATION_RESULTS.md` (generated). Both use the same code version.

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

(Survey outcomes are appended below once the queue drains.)
