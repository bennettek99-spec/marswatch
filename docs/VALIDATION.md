# MARSWATCH — Validation methodology

Measured numbers are generated into `docs/VALIDATION_RESULTS.md` by `marswatch validate`. This
page explains what is measured and how to read it.

## 1. Ground truth: documented new impact craters

Source: Daubar et al. (2022), *New Craters on Mars: An Updated Catalog*, JGR Planets 127,
e2021JE007145, Table S1 (Zenodo 6604912). Each of the 1,203 impacts has a location, an effective
diameter and a formation window [before-image date, after-image date] (mostly from CTX/THEMIS/MOC).

A site is usable when HiRISE RED products (≤ 0.5 m/px) exist **before the window** and **after the
window**, both covering the crater (150 m margin for pointing error). 19 sites qualify. For each:

* **positive pair** — the best-suited (pre, post) combination, preferring the catalogue's own HiRISE
  image as the "after" (its pointing frame matches the catalogue coordinates);
* **pre-pre controls** — two images, both before formation: *any* detection is a false positive
  (barring other undocumented changes);
* **post-post controls** — both after formation: the crater exists in both; changes near it
  (blast-zone fading) are real processes, changes elsewhere are counted separately.

Each run analyses a 1 km × 1 km window centred on the catalogue position at 0.5 m/px.

### Matching criterion
A positive is **detected** if a non-artifact candidate (status ≠ likely_artifact, category ≠
artifact) contains the catalogue point within its region (bbox + 20 m), or lies within 60 m of it
(150 m if the after image is not the catalogue's). Run 1 used only the centroid distance; it was
revised because large blast zones have centroids offset from the crater (RESEARCH_LOG). Both
criteria are recorded per run.

### Metrics
* **recall** at score thresholds; also with QC-rejected positives counted as misses;
* **recall as new impact** (correct category as well);
* **FP / km²** in positive windows (excluding candidates associated with the catalogued event,
  e.g. other craters of a cluster) and in pre-pre controls;
* **precision\*** = TP / (TP + FP), assuming the catalogued crater is the only real change in each
  window — pessimistic if other undocumented changes exist (we observed at least one fading
  dark streak in an audit);
* **rank** of the documented change among all candidates in its window;
* **illumination breakdown** of FP/km² by Δincidence;
* **Method C ablation**: AUC of the CNN-feature z-score separating documented changes from other
  non-artifact candidates.

## 2. Held-out pairs

Rules were revised after validation run 1 on the same 19 sites (see RESEARCH_LOG.md), so
tuning-set results are optimistic. The held-out set uses **image pairs never inspected during
development** at the same sites (alternative pre/post combinations and lower-ranked controls).
Because the sites are shared, it is not fully independent, but it tests whether the rules
generalise across different images, illumination and viewing geometry.

## 3. Sensitivity vs size (synthetic injection — labelled)

Artificial blast zones (Gaussian darkening of radius ≈ 8 × D) plus a shaded bowl of diameter D,
with halo contrasts of 5, 10 and 20 %, are injected into the *after* image of real, registered,
unchanged pre-pre pairs at random positions ≥ 40 px from existing detections. Detection = a
non-artifact candidate within max(10 m, 4 D). This measures detectability only; real blast zones
are irregular and rayed.

## 4. Registration accuracy

* **Real pairs**: displacement re-measured on a held-out checkpoint grid after warping (RMS, P90).
  Registration status and the corrected pointing offsets are reported for every run.
* **Synthetic known warps (labelled)**: real 600 m × 600 m HiRISE windows warped with random
  translation (±8 px), rotation (±0.5°), scale (±0.5 %), sinusoidal along-track jitter (≤ 1.5 px),
  gain (0.5–1.5) and noise; the estimated dense field is compared with the true field.

## 5. Input quality control

Structure-to-noise ratio < 2 flags an image; a pair is rejected only if registration also fails.
All images that failed the threshold during validation were acquired during the MY28 (2007) and
MY34 (2018) global dust storms.

## 6. What is *not* validated

* Slope-streak, dune, rockfall and frost categories have no labelled ground truth in this version;
  their outputs are heuristic categorisations reviewed visually only.
* The heuristic score is not calibrated as a probability.
* Performance was measured in a 4-vCPU Linux container with a concurrent survey worker (timings are
  conservative); not on the target Mac mini.
