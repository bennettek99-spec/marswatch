# MARSWATCH — measured validation results

_Generated 2026-11-04 04:13 UTC from the `validation_runs` table. Every number below was produced by `marswatch validate`, except the run-1 baseline line, which is transcribed from that run's log (the run was aborted before saving metrics)._

## Summary

| set | code | positive runs | recall (usable pairs) | recall (QC-rejected = miss) | recall as new impact | FP/km² pre-pre | precision* | @ threshold |
|---|---|---|---|---|---|---|---|---|
| tuning (rules developed on these sites) | `0.3.0+174dbb81d7` | 17 | 0.88 | 0.79 | 0.71 | 8.75 | 0.12 | 0.0 |
| tuning (rules developed on these sites) | `0.3.0+174dbb81d7` | 17 | 0.71 | 0.63 | 0.53 | 0.51 | 0.46 | 0.6 |
| held-out image pairs | `0.3.0+bb6aa95341` | 17 | 0.53 | 0.50 | 0.47 | 0.61 | 0.33 | 0.0 |
| held-out image pairs | `0.3.0+bb6aa95341` | 17 | 0.47 | 0.44 | 0.47 | 0.61 | 0.53 | 0.6 |

Baseline (validation run 1, before any rule revision, centroid criterion): 12/16 completed positives matched; see `data/validation/run1_baseline_log.txt` and RESEARCH_LOG.md.

## Tuning set: documented new impact craters (Daubar et al. 2022) — validation run #5, code `0.3.0+174dbb81d7`

* Sites: 19; positive runs: 17; pre-pre controls: 3; post-post controls: 13; failed/rejected runs: 3; skipped (no COG yet): 1
* Median rank of the documented change among candidates in its 1 km² window: 1.0; ranked #1 in 56% of detected cases

### Operating points (heuristic score threshold)

| threshold | recall (usable pairs) | recall (rejected = miss) | recall (as new impact) | TP | FP in positive windows | FP in pre-pre controls | FP/km² (pos. windows) | FP/km² (pre-pre) | precision* |
|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.88 | 0.79 | 0.71 | 15 | 93 | 17 | 6.28 | 8.75 | 0.12 |
| 0.2 | 0.88 | 0.79 | 0.71 | 15 | 93 | 17 | 6.28 | 8.75 | 0.12 |
| 0.3 | 0.88 | 0.79 | 0.71 | 15 | 91 | 17 | 6.14 | 8.75 | 0.12 |
| 0.4 | 0.88 | 0.79 | 0.71 | 15 | 67 | 13 | 4.52 | 6.69 | 0.16 |
| 0.5 | 0.82 | 0.74 | 0.65 | 14 | 37 | 2 | 2.50 | 1.03 | 0.26 |
| 0.6 | 0.71 | 0.63 | 0.53 | 12 | 13 | 1 | 0.88 | 0.51 | 0.46 |
| 0.7 | 0.53 | 0.47 | 0.47 | 9 | 2 | 0 | 0.14 | 0.00 | 0.82 |

\* Precision assumes the only real change inside each window is the catalogued crater; any other non-artifact candidate counts as a false positive. Real undocumented changes would make this pessimistic; see the per-case review in `docs/VALIDATION.md`.

### Sensitivity vs crater diameter (real cases)

| diameter (m) | n | detected | rate |
|---|---|---|---|
| 0-3 | 1 | 1 | 1.00 |
| 3-5 | 9 | 8 | 0.89 |
| 5-8 | 5 | 4 | 0.80 |
| 8-100 | 2 | 2 | 1.00 |

### Recall vs illumination difference (positive pairs)

| Δincidence | n | detected | matched but labelled artifact | recall |
|---|---|---|---|---|
| Δinc ≤ 5° | 6 | 5 | 1 | 0.83 |
| 5° < Δinc ≤ 10° | 6 | 5 | 0 | 0.83 |
| Δinc > 10° | 5 | 5 | 0 | 1.00 |

### Illumination breakdown (false positives per km² at score ≥ 0.4)

| group | runs | FP/km² |
|---|---|---|
| d_incidence<=10 | 15 | 4.46 |
| d_incidence>10 | 5 | 5.60 |

### Registration on real pairs

* Runs: 33; held-out checkpoint RMS median 0.46 px, P90 1.22 px; status counts {'good': 28, 'marginal': 5, 'poor': 0}; median uncontrolled-pointing offset corrected 42 m

### Method C (pretrained CNN features) — ablation

* deep-feature z of documented changes (median): 2.06; of other non-artifact candidates: -0.46; AUC separating them: 0.79

### Post-post controls (crater present in both images)

* Non-artifact detections within 100 m of the crater: 5 (blast-zone fading/brightening is a real, documented process — Daubar et al. 2016 — so these are not counted as false positives)
* Non-artifact detections elsewhere, score ≥ 0.4, per km²: 3.91

### Performance

* Median wall time per 1 km² validation run (0.5 m/px, incl. remote reads): 19.3 s; 22.6 s/km²; peak RSS 983 MB

### Failed runs (recorded, not hidden)

* positive PSP_004440_2125_RED → ESP_027555_2125_RED: PSP_004440_2125_RED structure SNR 0.93 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)
* positive ESP_055702_1775_RED → ESP_065843_1775_RED: ESP_055702_1775_RED structure SNR 0.74 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)
* neg:pre-pre ESP_022670_1775_RED → ESP_055702_1775_RED: ESP_055702_1775_RED structure SNR 0.74 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)

### Per-case results (positive pairs)

| ref | D (m) | before → after | Δinc | reg RMS px | matched | score | category | status | rank | dist (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| D22-0230 | 1.84 | PSP_004440_2125 → ESP_027555_2125 | — | — | QC-REJECTED | | | PSP_004440_2125_RED structure SNR 0.93 < 2.0 (atmospheric opacity / ha | | |
| D22-0233 | 4.28 | ESP_016108_2305 → ESP_026802_2305 | 6° | 0.42 | yes | 0.64 | seasonal_frost_or_albedo | known_documented | 6 | 43 |
| D22-0343 | 4.62 | ESP_018784_2050 → ESP_034357_2050 | 6° | 0.43 | no | — | — | — | — | 367 |
| D22-0412 | 2.4 | ESP_024665_2360 → ESP_036269_2360 | 3° | 0.26 | yes | 0.64 | seasonal_frost_or_albedo | known_documented | 6 | 56 |
| D22-0514 | 5.5 | ESP_039913_1845 → ESP_043605_1845 | 2° | 0.36 | yes | 0.52 | new_impact_crater | known_documented | 8 | 58 |
| D22-0537 | 8.14 | ESP_034897_2080 → ESP_045473_2080 | 1° | 0.72 | yes | 0.87 | new_impact_crater | known_documented | 1 | 161 |
| D22-0542 | 6.38 | PSP_007378_1860 → ESP_045236_1865 | 7° | 1.26 | yes | 0.74 | new_impact_crater | known_documented | 1 | 38 |
| D22-0546 | 4.32 | ESP_028344_2085 → ESP_045447_2085 | 9° | 0.47 | yes | 0.77 | slope_streak | known_documented | 2 | 63 |
| D22-0673 | 6.63 | PSP_004952_2035 → ESP_048572_2035 | 3° | 0.92 | yes | 0.08 | illumination_or_registration_artifact | likely_artifact | 60 | 29 |
| D22-0761 | 3.94 | ESP_017280_2070 → ESP_050958_2070 | 4° | 0.81 | yes | 0.47 | new_impact_crater | known_documented | 9 | 18 |
| D22-0786 | 3.42 | ESP_026632_2015 → ESP_051884_2015 | 7° | 0.19 | yes | 0.88 | new_impact_crater | known_documented | 1 | 38 |
| D22-0884 | 6.24 | PSP_006165_1890 → ESP_056708_1890 | 18° | 0.60 | yes | 0.66 | new_impact_crater | known_documented | 1 | 24 |
| D22-0887 | 9.12 | PSP_007023_1980 → ESP_056155_1980 | 20° | 0.45 | yes | 0.55 | new_impact_crater | known_documented | 1 | 47 |
| D22-0971 | 3.83 | ESP_037324_1990 → ESP_059491_1990 | 18° | 0.46 | yes | 0.83 | new_impact_crater | known_documented | 1 | 17 |
| D22-1001 | 3.32 | ESP_027372_1850 → ESP_060444_1850 | 10° | 1.37 | yes | 0.72 | new_impact_crater | known_documented | 1 | 27 |
| D22-1020 | 4.6 | ESP_037020_2075 → ESP_063433_2075 | 2° | 1.73 | yes | 0.91 | new_impact_crater | known_documented | 1 | 25 |
| D22-1128 | 20.84 | ESP_055702_1775 → ESP_065843_1775 | — | — | QC-REJECTED | | | ESP_055702_1775_RED structure SNR 0.74 < 2.0 (atmospheric opacity / ha | | |
| D22-1148 | 3.37 | ESP_047376_1865 → ESP_067051_1865 | 9° | 0.73 | yes | 0.80 | new_impact_crater | known_documented | 3 | 85 |
| D22-1157 | 5.5388 | PSP_006660_2190 → ESP_067173_2190 | 17° | 0.46 | yes | 0.76 | new_impact_crater | known_documented | 1 | 16 |

## Held-out image pairs: documented new impact craters (Daubar et al. 2022) — validation run #2, code `0.3.0+bb6aa95341`

* Sites: 18; positive runs: 17; pre-pre controls: 2; post-post controls: 5; failed/rejected runs: 2; skipped (no COG yet): 1
* Median rank of the documented change among candidates in its 1 km² window: 1.0; ranked #1 in 55% of detected cases

### Operating points (heuristic score threshold)

| threshold | recall (usable pairs) | recall (rejected = miss) | recall (as new impact) | TP | FP in positive windows | FP in pre-pre controls | FP/km² (pos. windows) | FP/km² (pre-pre) | precision* |
|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.53 | 0.50 | 0.47 | 9 | 17 | 1 | 1.27 | 0.61 | 0.33 |
| 0.2 | 0.53 | 0.50 | 0.47 | 9 | 17 | 1 | 1.27 | 0.61 | 0.33 |
| 0.3 | 0.53 | 0.50 | 0.47 | 9 | 17 | 1 | 1.27 | 0.61 | 0.33 |
| 0.4 | 0.53 | 0.50 | 0.47 | 9 | 17 | 1 | 1.27 | 0.61 | 0.33 |
| 0.5 | 0.47 | 0.44 | 0.47 | 8 | 10 | 1 | 0.75 | 0.61 | 0.42 |
| 0.6 | 0.47 | 0.44 | 0.47 | 8 | 6 | 1 | 0.45 | 0.61 | 0.53 |
| 0.7 | 0.29 | 0.28 | 0.29 | 5 | 3 | 0 | 0.22 | 0.00 | 0.62 |

\* Precision assumes the only real change inside each window is the catalogued crater; any other non-artifact candidate counts as a false positive. Real undocumented changes would make this pessimistic; see the per-case review in `docs/VALIDATION.md`.

### Sensitivity vs crater diameter (real cases)

| diameter (m) | n | detected | rate |
|---|---|---|---|
| 0-3 | 1 | 0 | 0.00 |
| 3-5 | 8 | 5 | 0.62 |
| 5-8 | 4 | 2 | 0.50 |
| 8-100 | 4 | 2 | 0.50 |

### Recall vs illumination difference (positive pairs)

| Δincidence | n | detected | matched but labelled artifact | recall |
|---|---|---|---|---|
| Δinc ≤ 5° | 9 | 5 | 1 | 0.56 |
| 5° < Δinc ≤ 10° | 2 | 2 | 0 | 1.00 |
| Δinc > 10° | 6 | 2 | 1 | 0.33 |

### Illumination breakdown (false positives per km² at score ≥ 0.4)

| group | runs | FP/km² |
|---|---|---|
| d_incidence<=10 | 13 | 1.32 |
| d_incidence>10 | 6 | 0.83 |

### Registration on real pairs

* Runs: 24; held-out checkpoint RMS median 0.56 px, P90 1.15 px; status counts {'good': 19, 'marginal': 4, 'poor': 1}; median uncontrolled-pointing offset corrected 53 m

### Method C (pretrained CNN features) — ablation

* deep-feature z of documented changes (median): 3.09; of other non-artifact candidates: 0.66; AUC separating them: 0.75

### Post-post controls (crater present in both images)

* Non-artifact detections within 100 m of the crater: 4 (blast-zone fading/brightening is a real, documented process — Daubar et al. 2016 — so these are not counted as false positives)
* Non-artifact detections elsewhere, score ≥ 0.4, per km²: 4.39

### Performance

* Median wall time per 1 km² validation run (0.5 m/px, incl. remote reads): 17.2 s; 21.2 s/km²; peak RSS 884 MB

### Failed runs (recorded, not hidden)

* positive PSP_004440_2125_RED → ESP_026355_2125_RED: PSP_004440_2125_RED structure SNR 0.93 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)
* neg:pre-pre ESP_023092_1775_RED → ESP_055702_1775_RED: ESP_055702_1775_RED structure SNR 0.74 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)

### Per-case results (positive pairs)

| ref | D (m) | before → after | Δinc | reg RMS px | matched | score | category | status | rank | dist (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| D22-0230 | 1.84 | PSP_004440_2125 → ESP_026355_2125 | — | — | QC-REJECTED | | | PSP_004440_2125_RED structure SNR 0.93 < 2.0 (atmospheric opacity / ha | | |
| D22-0233 | 4.28 | ESP_016108_2305 → ESP_033659_2305 | 2° | 0.72 | yes | 0.91 | new_impact_crater | known_documented | 1 | 129 |
| D22-0233 | 4.28 | ESP_016108_2305 → ESP_035228_2305 | 5° | 0.35 | yes | 0.72 | new_impact_crater | known_documented | 2 | 102 |
| D22-0343 | 4.62 | ESP_018784_2050 → ESP_062748_2050 | 1° | 0.17 | no | — | — | — | — | inf |
| D22-0343 | 4.62 | ESP_018784_2050 → ESP_045012_2050 | 5° | 0.22 | no | — | — | — | — | 423 |
| D22-0412 | 2.4 | ESP_024665_2360 → ESP_071717_2360 | 1° | 0.64 | no | — | — | — | — | 571 |
| D22-0514 | 5.5 | ESP_039913_1845 → ESP_044937_1845 | 1° | 0.62 | yes | 0.61 | new_impact_crater | known_documented | 5 | 76 |
| D22-0514 | 5.5 | ESP_039913_1845 → ESP_044027_1845 | 0° | 0.72 | yes | 0.66 | new_impact_crater | known_documented | 2 | 141 |
| D22-0537 | 8.14 | ESP_034897_2080 → ESP_071690_2080 | 6° | 0.58 | yes | 0.66 | new_impact_crater | known_documented | 1 | 41 |
| D22-0673 | 6.63 | PSP_004952_2035 → ESP_057394_2035 | 3° | 0.48 | yes | 0.32 | illumination_or_registration_artifact | likely_artifact | 14 | 127 |
| D22-0884 | 6.24 | PSP_006165_1890 → ESP_055943_1890 | 18° | 0.52 | no | — | — | — | — | 355 |
| D22-0887 | 9.12 | PSP_007168_1980 → ESP_056155_1980 | 21° | 0.84 | yes | 0.42 | illumination_or_registration_artifact | likely_artifact | 1 | 39 |
| D22-0971 | 3.83 | ESP_037324_1990 → ESP_085787_1990 | 14° | 1.94 | no | — | — | — | — | 339 |
| D22-1001 | 3.32 | ESP_027649_1850 → ESP_060444_1850 | 12° | 1.14 | yes | 0.74 | new_impact_crater | known_documented | 1 | 27 |
| D22-1020 | 4.6 | ESP_036453_2075 → ESP_089254_2075 | 0° | 0.21 | yes | 0.98 | new_impact_crater | known_documented | 1 | 33 |
| D22-1020 | 4.6 | ESP_016700_2075 → ESP_087052_2075 | 1° | 0.57 | yes | 0.78 | new_impact_crater | known_documented | 1 | 14 |
| D22-1128 | 20.84 | ESP_022670_1775 → ESP_065843_1775 | 14° | 0.56 | yes | 0.49 | other_change | known_documented | 3 | 144 |
| D22-1128 | 20.84 | ESP_023092_1775 → ESP_065843_1775 | 17° | — | no | — | — | — | — | inf |

## Detection sensitivity vs size — SYNTHETIC INJECTION (run #4)

Synthetic dark blast-zone + shaded-bowl signatures injected into *real*, registered, unchanged (pre-pre) HiRISE imagery. These are not real changes; they measure detectability only.

| crater D (m) | halo contrast | n | detection rate |
|---|---|---|---|
| 1.0 | 0.05 | 7 | 1.00 |
| 1.0 | 0.1 | 7 | 1.00 |
| 1.0 | 0.2 | 7 | 1.00 |
| 2.0 | 0.05 | 7 | 1.00 |
| 2.0 | 0.1 | 7 | 1.00 |
| 2.0 | 0.2 | 7 | 1.00 |
| 3.0 | 0.05 | 7 | 1.00 |
| 3.0 | 0.1 | 7 | 1.00 |
| 3.0 | 0.2 | 7 | 1.00 |
| 5.0 | 0.05 | 7 | 1.00 |
| 5.0 | 0.1 | 7 | 1.00 |
| 5.0 | 0.2 | 7 | 1.00 |
| 8.0 | 0.05 | 7 | 1.00 |
| 8.0 | 0.1 | 7 | 1.00 |
| 8.0 | 0.2 | 7 | 1.00 |
| 12.0 | 0.05 | 7 | 1.00 |
| 12.0 | 0.1 | 7 | 1.00 |
| 12.0 | 0.2 | 7 | 1.00 |

_Note: this easy variant (halo radius 8 × D, contrast ≥ 5 %) saturates at 100 % — every injected signature is a large smooth darkening. It shows only that such halos are reliably detected; see the harder variant below._

## Detection sensitivity — SYNTHETIC INJECTION, hard variant

Shaded crater bowl only (contrast 0) or bowl + faint compact halo (radius 3.0 × D, contrast 2–3 %), injected into real unchanged HiRISE imagery (run #6).

| crater D (m) | halo contrast | n | detection rate |
|---|---|---|---|
| 1.0 | 0.0 | 7 | 0.00 |
| 1.0 | 0.02 | 7 | 0.00 |
| 1.0 | 0.03 | 7 | 0.00 |
| 2.0 | 0.0 | 7 | 0.00 |
| 2.0 | 0.02 | 7 | 0.86 |
| 2.0 | 0.03 | 7 | 1.00 |
| 3.0 | 0.0 | 7 | 1.00 |
| 3.0 | 0.02 | 7 | 1.00 |
| 3.0 | 0.03 | 7 | 1.00 |
| 5.0 | 0.0 | 7 | 1.00 |
| 5.0 | 0.02 | 7 | 1.00 |
| 5.0 | 0.03 | 7 | 1.00 |
| 8.0 | 0.0 | 7 | 1.00 |
| 8.0 | 0.02 | 7 | 1.00 |
| 8.0 | 0.03 | 7 | 1.00 |

## Registration accuracy — SYNTHETIC known warps (run #3)

Median true-field RMS error 0.200 px, max 0.496 px over 8 trials (shift ±8 px, rotation ±0.5°, scale ±0.5%, sinusoidal jitter ≤1.5 px, gain 0.5–1.5, noise).

| site | true shift (px) | jitter amp (px) | true RMS err (px) | P90 err (px) | checkpoint RMS estimate (px) |
|---|---|---|---|---|---|
| D22-0233 | -3.8, -3.2 | 0.90 | 0.292 | 0.380 | 0.255 |
| D22-0343 | -6.3, 7.2 | 0.06 | 0.024 | 0.036 | 0.029 |
| D22-0412 | 2.0, -2.4 | 0.44 | 0.221 | 0.285 | 0.176 |
| D22-0514 | 7.3, 2.0 | 0.66 | 0.154 | 0.227 | 0.118 |
| D22-0542 | -2.2, -6.0 | 0.10 | 0.164 | 0.192 | 0.101 |
| D22-0546 | 1.1, -7.9 | 0.86 | 0.462 | 0.618 | 0.425 |
| D22-0761 | 5.2, -6.1 | 0.97 | 0.496 | 0.692 | 0.414 |
| D22-0786 | 5.2, 5.6 | 0.31 | 0.179 | 0.253 | 0.155 |
