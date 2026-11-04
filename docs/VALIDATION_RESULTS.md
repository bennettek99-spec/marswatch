# MARSWATCH — measured validation results

_Generated 2026-11-04 03:32 UTC from the `validation_runs` table. Every number below was produced by `marswatch validate`; nothing is hand-entered._

## 1. Documented new impact craters (Daubar et al. 2022) — validation run #1, code `0.3.0+54b06d405e`

* Sites: 19; positive runs: 16; pre-pre controls: 3; post-post controls: 12; failed runs: 5
* Median rank of the documented change among candidates in its 1 km² window: 1.0; ranked #1 in 60% of detected cases

### Operating points (heuristic score threshold)

| threshold | recall (any category) | recall (as new impact) | TP | FP in positive windows | FP in pre-pre controls | FP/km² (pos. windows) | FP/km² (pre-pre) | precision* |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.94 | 0.69 | 15 | 53 | 13 | 3.76 | 6.74 | 0.19 |
| 0.2 | 0.94 | 0.69 | 15 | 53 | 13 | 3.76 | 6.74 | 0.19 |
| 0.3 | 0.94 | 0.69 | 15 | 53 | 13 | 3.76 | 6.74 | 0.19 |
| 0.4 | 0.94 | 0.69 | 15 | 47 | 11 | 3.33 | 5.70 | 0.21 |
| 0.5 | 0.94 | 0.69 | 15 | 31 | 9 | 2.20 | 4.67 | 0.27 |
| 0.6 | 0.94 | 0.69 | 15 | 13 | 5 | 0.92 | 2.59 | 0.45 |
| 0.7 | 0.75 | 0.56 | 12 | 5 | 2 | 0.35 | 1.04 | 0.63 |

\* Precision assumes the only real change inside each window is the catalogued crater; any other non-artifact candidate counts as a false positive. Real undocumented changes would make this pessimistic; see the per-case review in `docs/VALIDATION.md`.

### Sensitivity vs crater diameter (real cases)

| diameter (m) | n | detected | rate |
|---|---|---|---|
| 0-3 | 1 | 1 | 1.00 |
| 3-5 | 9 | 8 | 0.89 |
| 5-8 | 4 | 4 | 1.00 |
| 8-100 | 2 | 2 | 1.00 |

### Illumination breakdown (false positives per km² at score ≥ 0.4)

| group | runs | FP/km² |
|---|---|---|
| d_incidence<=10 | 14 | 4.63 |
| d_incidence>10 | 5 | 1.09 |

### Registration on real pairs

* Runs: 31; held-out checkpoint RMS median 0.46 px, P90 1.81 px; status counts {'good': 26, 'marginal': 4, 'poor': 1}; median uncontrolled-pointing offset corrected 42 m

### Method C (pretrained CNN features) — ablation

* deep-feature z of documented changes (median): 3.03; of other non-artifact candidates: -0.24; AUC separating them: 0.78

### Post-post controls (crater present in both images)

* Non-artifact detections within 100 m of the crater: 5 (blast-zone fading/brightening is a real, documented process — Daubar et al. 2016 — so these are not counted as false positives)
* Non-artifact detections elsewhere, score ≥ 0.4, per km²: 4.99

### Performance

* Median wall time per 1 km² validation run (0.5 m/px, incl. remote reads): 19.2 s; 23.1 s/km²; peak RSS 837 MB

### Failed runs (recorded, not hidden)

* positive PSP_004440_2125_RED → ESP_027555_2125_RED: PSP_004440_2125_RED structure SNR 0.97 < 2.0 (likely atmospheric opacity / dust storm or no surface signal)
* positive PSP_004952_2035_RED → ESP_048572_2035_RED: PSP_004952_2035_RED structure SNR 0.89 < 2.0 (likely atmospheric opacity / dust storm or no surface signal)
* neg:post-post ESP_055943_1890_RED → ESP_056708_1890_RED: ESP_055943_1890_RED structure SNR 0.71 < 2.0 (likely atmospheric opacity / dust storm or no surface signal)
* positive ESP_055702_1775_RED → ESP_065843_1775_RED: ESP_055702_1775_RED structure SNR 0.76 < 2.0 (likely atmospheric opacity / dust storm or no surface signal)
* neg:pre-pre ESP_022670_1775_RED → ESP_055702_1775_RED: ESP_055702_1775_RED structure SNR 0.74 < 2.0 (likely atmospheric opacity / dust storm or no surface signal)

### Per-case results (positive pairs)

| ref | D (m) | before → after | Δinc | reg RMS px | matched | score | category | status | rank | dist (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| D22-0230 | 1.84 | PSP_004440_2125_RED → ESP_027555_2125_RED | — | — | ERROR | | | | | |
| D22-0233 | 4.28 | ESP_016108_2305 → ESP_026802_2305 | 6° | 0.42 | yes | 0.88 | seasonal_frost_or_albedo | known_documented | 3 | 43 |
| D22-0343 | 4.62 | ESP_018784_2050 → ESP_034357_2050 | 6° | 0.43 | no | — | — | — | — | 367 |
| D22-0412 | 2.4 | ESP_024665_2360 → ESP_036269_2360 | 3° | 0.26 | yes | 0.62 | seasonal_frost_or_albedo | known_documented | 2 | 56 |
| D22-0514 | 5.5 | ESP_039913_1845 → ESP_043605_1845 | 2° | 0.36 | yes | 1.00 | new_impact_crater | known_documented | 1 | 141 |
| D22-0537 | 8.14 | ESP_034897_2080 → ESP_045473_2080 | 1° | 0.72 | yes | 0.69 | new_impact_crater | known_documented | 3 | 161 |
| D22-0542 | 6.38 | PSP_007378_1860 → ESP_045236_1865 | 7° | 1.26 | yes | 0.92 | new_impact_crater | known_documented | 1 | 38 |
| D22-0546 | 4.32 | ESP_028344_2085 → ESP_045447_2085 | 9° | 0.47 | yes | 0.96 | slope_streak | known_documented | 2 | 63 |
| D22-0673 | 6.63 | PSP_004952_2035_RED → ESP_048572_2035_RED | — | — | ERROR | | | | | |
| D22-0761 | 3.94 | ESP_017280_2070 → ESP_050958_2070 | 4° | 0.81 | yes | 0.66 | new_impact_crater | known_documented | 21 | 19 |
| D22-0786 | 3.42 | ESP_026632_2015 → ESP_051884_2015 | 7° | 0.19 | yes | 0.95 | new_impact_crater | known_documented | 1 | 39 |
| D22-0884 | 6.24 | PSP_006165_1890 → ESP_056708_1890 | 18° | 0.60 | yes | 0.93 | new_impact_crater | known_documented | 1 | 24 |
| D22-0887 | 9.12 | PSP_007023_1980 → ESP_056155_1980 | 20° | 0.45 | yes | 0.83 | new_impact_crater | known_documented | 1 | 47 |
| D22-0971 | 3.83 | ESP_037324_1990 → ESP_059491_1990 | 18° | 0.46 | yes | 0.83 | other_change | known_documented | 1 | 10 |
| D22-1001 | 3.32 | ESP_027372_1850 → ESP_060444_1850 | 10° | 1.97 | yes | 0.88 | new_impact_crater | known_documented | 1 | 27 |
| D22-1020 | 4.6 | ESP_037020_2075 → ESP_063433_2075 | 2° | 1.83 | yes | 0.91 | new_impact_crater | known_documented | 1 | 25 |
| D22-1128 | 20.84 | ESP_055702_1775_RED → ESP_065843_1775_RED | — | — | ERROR | | | | | |
| D22-1148 | 3.37 | ESP_047376_1865 → ESP_067051_1865 | 9° | 0.73 | yes | 0.80 | new_impact_crater | known_documented | 3 | 85 |
| D22-1157 | 5.5388 | PSP_006660_2190 → ESP_067173_2190 | 17° | 0.46 | yes | 0.83 | new_impact_crater | known_documented | 1 | 16 |
