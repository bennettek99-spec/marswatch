# MARSWATCH survey report

_Generated 2026-11-04 22:58 UTC from the MARSWATCH database. Code version(s): `0.4.0+0e782630d9`._

## Scope

* Regions: arabia-terra-w, lycus-sulci
  * Lycus Sulci (Olympus Mons aureole), 24–30°N, 218–228°E — primary
  * Arabia Terra W, 5–15°N, 0–10°E — secondary
* Pair selection: best-matched repeat HiRISE pairs (Δt ≥ 200–300 d, Δinc ≤ 10–12°, Δsun az ≤ 25–30°, Δemission ≤ 15°), spatially distinct (≥ 2–4 km apart); ≤ 12 km² of each overlap analysed at 1 m/px (centre crop), with resolution fallback to 2/4 m when registration is poor.
* Image pairs analysed: 17 (+1 rejected by input QC); failed jobs: 1
* Area analysed (after masking invalid / poorly registered areas): **155.9 km²**
* Candidates: 277

## Candidates by status

* insufficient_evidence: 10
* likely_artifact: 242
* plausible_unverified: 25

## Candidates by category (heuristic)

* illumination_or_registration_artifact: 125
* new_impact_crater: 102
* other_change: 26
* slope_streak: 21
* dune_bedform_change: 3

## Analysed pairs

| pair | region | Δt (d) | Δinc | analysed km² | res (m) | registration | checkpoint RMS px | cand. | plausible | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| ESP_017585_2080__ESP_078865_2080 | lycus-sulci | 4775 | 0.0 | 7.34 | 4.0 | marginal (0.23) | 2.02 | 0 | 0 | fallback 1.0→2.0→4.0 |
| ESP_013009_2095__ESP_092868_2095 | lycus-sulci | 6222 | 3.2 | 5.64 | 4.0 | poor (0.18) | 2.59 | 4 | 0 | fallback 1.0→2.0→4.0 |
| ESP_050129_2055__ESP_076478_2055 | lycus-sulci | 2053 | 4.4 | 11.10 | 1.0 | marginal (0.49) | 1.06 | 18 | 2 |  |
| PSP_004175_2060__ESP_057118_2060 | lycus-sulci | 4125 | 1.9 | 11.57 | 1.0 | good (0.62) | 0.72 | 37 | 2 |  |
| PSP_008513_2060__ESP_045435_2055 | lycus-sulci | 2877 | 0.9 | 4.58 | 1.0 | good (0.84) | 0.27 | 5 | 4 |  |
| ESP_069265_2070__ESP_086750_2070 | lycus-sulci | 1362 | 5.7 | 6.84 | 2.0 | marginal (0.23) | 2.19 | 1 | 1 | fallback 1.0→2.0 |
| ESP_027021_1900__ESP_035592_1900 | arabia-terra-w | 668 | 0.6 | 7.78 | 1.0 | marginal (0.22) | 2.25 | 6 | 1 |  |
| ESP_033804_2065__ESP_051197_2065 | lycus-sulci | 1355 | 2.7 | 11.67 | 1.0 | good (0.92) | 0.13 | 55 | 3 |  |
| ESP_048304_1905__ESP_057205_1905 | arabia-terra-w | 694 | 0.7 | 8.30 | 1.0 | marginal (0.32) | 1.70 | 0 | 0 |  |
| PSP_008679_1905__ESP_088815_1910 | arabia-terra-w | 6244 | 1.1 | — | 4.0 | — (—) | — | 0 | 0 | QC-rejected: ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust s; ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust storm suspe |
| ESP_083032_2080__ESP_092776_2080 | lycus-sulci | 759 | 4.4 | 9.47 | 4.0 | marginal (0.39) | 1.40 | 0 | 0 | fallback 1.0→2.0→4.0 |
| PSP_006952_1870__ESP_024542_1870 | arabia-terra-w | 1371 | 2.1 | 11.80 | 1.0 | good (0.87) | 0.21 | 45 | 4 |  |
| ESP_056836_1900__ESP_074996_1900 | arabia-terra-w | 1415 | 0.6 | 11.56 | 1.0 | good (0.63) | 0.70 | 66 | 0 |  |
| ESP_023698_1900__ESP_058959_1900 | arabia-terra-w | 2748 | 1.0 | 11.80 | 1.0 | good (0.84) | 0.26 | 8 | 7 |  |
| ESP_056994_1860__ESP_084121_1860 | arabia-terra-w | 2114 | 2.8 | 9.17 | 1.0 | good (0.73) | 0.46 | 11 | 0 |  |
| ESP_013505_1930__ESP_022498_1930 | arabia-terra-w | 701 | 3.8 | 11.81 | 1.0 | good (0.81) | 0.31 | 3 | 0 |  |
| ESP_028498_1895__ESP_079796_1900 | arabia-terra-w | 3997 | 0.8 | 5.42 | 1.0 | marginal (0.21) | 1.89 | 4 | 0 |  |
| ESP_065737_1930__ESP_073664_1930 | arabia-terra-w | 618 | 0.9 | 10.02 | 2.0 | marginal (0.29) | 1.86 | 14 | 1 | fallback 1.0→2.0 |

## Plausible unverified candidates (25; top 25 shown)

These passed the automated artifact tests. They are **not** confirmed discoveries. Follow-up results (third-image persistence, HiRISE targeting history, catalogue) are shown where run. "Triage" notes are a preliminary visual assessment by the operating agent, not expert review.

### Candidate 3442 — new_impact_crater — score 0.95

* Pair `ESP_069265_2070__ESP_086750_2070`; location (before frame) 26.45766°N 227.11822°E; area 6908 m² (≈93.8 m); local registration quality 0.65
* Evidence for: darkening change, peak |z|=16.4, area 6908 m² (≈93.8 m); darkening surrounds centre in 61% of directions (blast-zone-like); angular variation suggests rays (contrast 0.69); local structure changed (mean SSIM 0.30); pretrained CNN embedding change z=14.1 vs background (unvalidated evidence)
* Evidence against: none recorded
* Follow-up: third image none → not run; targeting tags ['slope_streak', 'monitoring']; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): new dark slope streak (heuristic category 'new impact crater' is wrong); HiRISE slope-streak monitoring site, so the HiRISE team is likely aware. Credible change.
* Chip: `data/runs/ESP_069265_2070__ESP_086750_2070__20261104T224340_bef770/chips/cand_000.jpg`

### Candidate 3314 — slope_streak — score 0.81

* Pair `PSP_008513_2060__ESP_045435_2055`; location (before frame) 25.47131°N 220.22420°E; area 6154 m² (≈88.5 m); local registration quality 0.73
* Evidence for: darkening change, peak |z|=17.9, area 6154 m² (≈88.5 m); local structure changed (mean SSIM 0.33); elongated (aspect 8.0, length 262 m); pretrained CNN embedding change z=5.6 vs background (unvalidated evidence)
* Evidence against: local image contrast differs by ×4.7 between images (haze, illumination or resolution difference): shading differences are expected
* Follow-up: third image none → not run; targeting tags none; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): new dark slope streak (~260 m) absent in the before image; narrow, point origin, downslope extension. Credible change.
* Chip: `data/runs/PSP_008513_2060__ESP_045435_2055__20261104T224323_8f6884/chips/cand_000.jpg`

### Candidate 3132 — new_impact_crater — score 0.72

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.49989°N 221.76550°E; area 2392 m² (≈55.2 m); local registration quality 0.87
* Evidence for: darkening change, peak |z|=14.7, area 2392 m² (≈55.2 m); darkening surrounds centre in 94% of directions (blast-zone-like); scene-level: stands out from this pair's systematic relief-bound population (|z| 14.7 vs scene median 7.3)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T224235_df0f90/chips/cand_000.jpg`

### Candidate 3745 — new_impact_crater — score 0.68

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05520°N 6.72846°E; area 6037 m² (≈87.7 m); local registration quality 0.93
* Evidence for: darkening change, peak |z|=15.7, area 6037 m² (≈87.7 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 15.7 vs scene median 8.2)
* Evidence against: located on steep/high-contrast relief (relief=5.3×median); crater-like shading appears in after image (template NCC 0.71 vs 0.49 before, r≈1.5 m); shading orientation 139° from solar azimuth (inconsistent with illumination)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T224824_4d62eb/chips/cand_001.jpg`

### Candidate 3600 — new_impact_crater — score 0.68

* Pair `ESP_033804_2065__ESP_051197_2065`; location (before frame) 26.41401°N 222.51770°E; area 849 m² (≈32.9 m); local registration quality 0.88
* Evidence for: darkening change, peak |z|=12.7, area 849 m² (≈32.9 m); darkening surrounds centre in 92% of directions (blast-zone-like); scene-level: stands out from this pair's systematic relief-bound population (|z| 12.7 vs scene median 7.2)
* Evidence against: located on steep/high-contrast relief (relief=2.5×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/ESP_033804_2065__ESP_051197_2065__20261104T224522_3c89e3/chips/cand_000.jpg`

### Candidate 3749 — other_change — score 0.65

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.02742°N 6.73215°E; area 7199 m² (≈95.7 m); local registration quality 0.91
* Evidence for: brightening change, peak |z|=20.3, area 7199 m² (≈95.7 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 20.3 vs scene median 8.2)
* Evidence against: located on steep/high-contrast relief (relief=4.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T224824_4d62eb/chips/cand_005.jpg`

### Candidate 3751 — other_change — score 0.63

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06323°N 6.72870°E; area 10413 m² (≈115.1 m); local registration quality 0.83
* Evidence for: darkening change, peak |z|=15.8, area 10413 m² (≈115.1 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 15.8 vs scene median 8.2)
* Evidence against: located on steep/high-contrast relief (relief=5.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T224824_4d62eb/chips/cand_007.jpg`

### Candidate 3315 — slope_streak — score 0.59

* Pair `PSP_008513_2060__ESP_045435_2055`; location (before frame) 25.49095°N 220.23282°E; area 22515 m² (≈169.3 m); local registration quality 0.54
* Evidence for: darkening change, peak |z|=17.2, area 22515 m² (≈169.3 m); local structure changed (mean SSIM 0.48); elongated (aspect 13.6, length 702 m)
* Evidence against: local image contrast differs by ×6.0 between images (haze, illumination or resolution difference): shading differences are expected
* Follow-up: third image none → not run; targeting tags none; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): dark slope streak (~190 m) much darker/longer in the after image; faint precursor visible before, so new or renewed. Credible change.
* Chip: `data/runs/PSP_008513_2060__ESP_045435_2055__20261104T224323_8f6884/chips/cand_001.jpg`

### Candidate 3316 — slope_streak — score 0.58

* Pair `PSP_008513_2060__ESP_045435_2055`; location (before frame) 25.46482°N 220.21411°E; area 4550 m² (≈76.1 m); local registration quality 0.50
* Evidence for: darkening change, peak |z|=16.5, area 4550 m² (≈76.1 m); local structure changed (mean SSIM 0.48); elongated (aspect 4.5, length 176 m); widens toward one end (taper 1.7), fan-like
* Evidence against: local image contrast differs by ×5.7 between images (haze, illumination or resolution difference): shading differences are expected
* Follow-up: third image none → not run; targeting tags none; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): fan-shaped dark slope streak present only in the after image; an image seam crosses it but does not explain it. Credible change.
* Chip: `data/runs/PSP_008513_2060__ESP_045435_2055__20261104T224323_8f6884/chips/cand_002.jpg`

### Candidate 4091 — new_impact_crater — score 0.58

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.70296°N 8.22530°E; area 1942 m² (≈49.7 m); local registration quality 0.90
* Evidence for: darkening change, peak |z|=6.0, area 1942 m² (≈49.7 m); darkening surrounds centre in 100% of directions (blast-zone-like); pretrained CNN embedding change z=6.8 vs background (unvalidated evidence)
* Evidence against: local image contrast differs by ×7.5 between images (haze, illumination or resolution difference): shading differences are expected; crater-like shading appears in after image (template NCC 0.49 vs 0.28 before, r≈6.0 m); shading orientation 65° from solar azimuth (inconsistent with illumination)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_000.jpg`

### Candidate 3604 — new_impact_crater — score 0.57

* Pair `ESP_033804_2065__ESP_051197_2065`; location (before frame) 26.39638°N 222.53098°E; area 15030 m² (≈138.3 m); local registration quality 0.66
* Evidence for: darkening change, peak |z|=19.1, area 15030 m² (≈138.3 m); darkening surrounds centre in 78% of directions (blast-zone-like); angular variation suggests rays (contrast 0.69); scene-level: stands out from this pair's systematic relief-bound population (|z| 19.1 vs scene median 7.2)
* Evidence against: local image contrast differs by ×8.4 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/ESP_033804_2065__ESP_051197_2065__20261104T224522_3c89e3/chips/cand_004.jpg`

### Candidate 3606 — slope_streak — score 0.50

* Pair `ESP_033804_2065__ESP_051197_2065`; location (before frame) 26.39365°N 222.51512°E; area 1055 m² (≈36.7 m); local registration quality 0.89
* Evidence for: darkening change, peak |z|=11.5, area 1055 m² (≈36.7 m); elongated (aspect 3.0, length 73 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 11.5 vs scene median 7.2)
* Evidence against: local image contrast differs by ×2.9 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=2.7×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/ESP_033804_2065__ESP_051197_2065__20261104T224522_3c89e3/chips/cand_006.jpg`

### Candidate 4092 — slope_streak — score 0.50

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.71922°N 8.22507°E; area 39402 m² (≈224.0 m); local registration quality 0.86
* Evidence for: darkening change, peak |z|=7.9, area 39402 m² (≈224.0 m); darkening surrounds centre in 67% of directions (blast-zone-like); elongated (aspect 4.9, length 571 m)
* Evidence against: local image contrast differs by ×5.8 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_001.jpg`

### Candidate 3144 — other_change — score 0.50

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.50191°N 221.76020°E; area 186518 m² (≈487.3 m); local registration quality 0.83
* Evidence for: brightening change, peak |z|=10.7, area 186518 m² (≈487.3 m)
* Evidence against: local image contrast differs by ×4.3 between images (haze, illumination or resolution difference): shading differences are expected; an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Follow-up: third image none → not run; targeting tags ['impact']; catalogue within 2 km: ['D22-0041']
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): dark rayed blast zone that FADED between 2007 and 2018. Follow-up: after-image caption 'Recent Impact Crater' and catalogued crater D22-0041 (6.5 m, formed 2002-05…2004-02) lies 241 m away — this is very likely D22-0041's blast zone fading (a documented process, Daubar et al. 2016). Real change of a known feature. Not auto-associated because MARSWATCH only links impacts that formed inside the pair's time window.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T224235_df0f90/chips/cand_012.jpg`

### Candidate 3107 — other_change — score 0.48

* Pair `ESP_050129_2055__ESP_076478_2055`; location (before frame) 25.45150°N 222.47350°E; area 4839 m² (≈78.5 m); local registration quality 0.67
* Evidence for: brightening change, peak |z|=12.2, area 4839 m² (≈78.5 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 12.2 vs scene median 7.0)
* Evidence against: local image contrast differs by ×19.1 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/ESP_050129_2055__ESP_076478_2055__20261104T224144_9c961c/chips/cand_000.jpg`

### Candidate 3580 — other_change — score 0.47

* Pair `ESP_027021_1900__ESP_035592_1900`; location (before frame) 9.79499°N 8.01708°E; area 69493 m² (≈297.5 m); local registration quality 0.48
* Evidence for: brightening change, peak |z|=7.4, area 69493 m² (≈297.5 m)
* Evidence against: local image contrast differs by ×4.1 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_027021_1900__ESP_035592_1900__20261104T224409_ee3e2e/chips/cand_000.jpg`

### Candidate 4093 — other_change — score 0.45

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.74993°N 8.17865°E; area 3967 m² (≈71.1 m); local registration quality 0.44
* Evidence for: brightening change, peak |z|=6.3, area 3967 m² (≈71.1 m)
* Evidence against: located on steep/high-contrast relief (relief=2.5×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_002.jpg`

### Candidate 3777 — other_change — score 0.42

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.09546°N 6.75712°E; area 121473 m² (≈393.3 m); local registration quality 0.48
* Evidence for: brightening change, peak |z|=16.9, area 121473 m² (≈393.3 m); scene-level: stands out from this pair's systematic relief-bound population (|z| 16.9 vs scene median 8.2)
* Evidence against: local image contrast differs by ×3.3 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=3.0×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): kept only as a strength outlier in a scene flagged as relief-bound; visually a ring/arc of darkening around existing relief (crater rim, mesa, dune-field wall). Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T224824_4d62eb/chips/cand_033.jpg`

### Candidate 4094 — new_impact_crater — score 0.42

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.77120°N 8.22065°E; area 41382 m² (≈229.5 m); local registration quality 0.66
* Evidence for: darkening change, peak |z|=7.4, area 41382 m² (≈229.5 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: local image contrast differs by ×4.9 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=2.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_003.jpg`

### Candidate 4386 — other_change — score 0.41

* Pair `ESP_065737_1930__ESP_073664_1930`; location (before frame) 12.67421°N 6.67540°E; area 8668 m² (≈105.1 m); local registration quality 0.77
* Evidence for: brightening change, peak |z|=7.3, area 8668 m² (≈105.1 m)
* Evidence against: local image contrast differs by ×16.7 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_065737_1930__ESP_073664_1930__20261104T225609_adc699/chips/cand_006.jpg`

### Candidate 4095 — slope_streak — score 0.40

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.70882°N 8.19696°E; area 828 m² (≈32.5 m); local registration quality 0.86
* Evidence for: brightening change, peak |z|=6.5, area 828 m² (≈32.5 m); elongated (aspect 3.3, length 62 m)
* Evidence against: local image contrast differs by ×4.8 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=3.9×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_004.jpg`

### Candidate 4096 — new_impact_crater — score 0.40

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.74349°N 8.18930°E; area 309 m² (≈19.8 m); local registration quality 0.85
* Evidence for: darkening change, peak |z|=6.3, area 309 m² (≈19.8 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: local image contrast differs by ×4.9 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=3.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_005.jpg`

### Candidate 4097 — other_change — score 0.40

* Pair `ESP_023698_1900__ESP_058959_1900`; location (before frame) 9.70502°N 8.18177°E; area 5535 m² (≈83.9 m); local registration quality 0.82
* Evidence for: brightening change, peak |z|=6.9, area 5535 m² (≈83.9 m)
* Evidence against: local image contrast differs by ×5.9 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_023698_1900__ESP_058959_1900__20261104T225107_860041/chips/cand_006.jpg`

### Candidate 3113 — other_change — score 0.37

* Pair `ESP_050129_2055__ESP_076478_2055`; location (before frame) 25.46227°N 222.45020°E; area 1148 m² (≈38.2 m); local registration quality 0.33
* Evidence for: brightening change, peak |z|=6.9, area 1148 m² (≈38.2 m)
* Evidence against: local image contrast differs by ×8.7 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/ESP_050129_2055__ESP_076478_2055__20261104T224144_9c961c/chips/cand_006.jpg`

### Candidate 3317 — other_change — score 0.35

* Pair `PSP_008513_2060__ESP_045435_2055`; location (before frame) 25.47218°N 220.23622°E; area 2704 m² (≈58.7 m); local registration quality 0.89
* Evidence for: brightening change, peak |z|=6.0, area 2704 m² (≈58.7 m)
* Evidence against: local image contrast differs by ×4.8 between images (haze, illumination or resolution difference): shading differences are expected; located on steep/high-contrast relief (relief=3.8×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): diffuse albedo or shading change without clear morphology. Uncertain.
* Chip: `data/runs/PSP_008513_2060__ESP_045435_2055__20261104T224323_8f6884/chips/cand_003.jpg`

## Scene-level artifact test

| pair | candidates | on steep relief | demoted | kept as strength outliers |
|---|---|---|---|---|
| ESP_050129_2055__ESP_076478_2055 | 18 | 72% | 5 | 2 |
| PSP_004175_2060__ESP_057118_2060 | 37 | 95% | 22 | 4 |
| ESP_033804_2065__ESP_051197_2065 | 55 | 100% | 51 | 3 |
| PSP_006952_1870__ESP_024542_1870 | 45 | 100% | 34 | 6 |
| ESP_056836_1900__ESP_074996_1900 | 66 | 71% | 0 | 2 |
| ESP_065737_1930__ESP_073664_1930 | 14 | 71% | 8 | 0 |

## False positives and uncertainties

* 242 candidates were automatically classified as likely artifacts (shadow dipoles, cast shadows, contrast/haze differences, poor local registration).
* 10 candidates had insufficient evidence (small, weak, or in poorly registered areas).
* From validation, the expected false-positive density in well-registered, non-dust-storm pairs is a few per km² at score 0 and ~1–3 per km² at score ≥ 0.6 (see VALIDATION_RESULTS.md): most plausible candidates in a survey are expected to be false positives or real-but-mundane changes (dust redistribution, fading streaks).
* Pairs including dust-storm-epoch images showed systematic ring artifacts around relief; these are penalised but not eliminated.

## Failed jobs

* job 11 (PSP_008679_1905__ESP_088815_1910): input rejected by QC: ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)

## Recommended follow-up

1. Expert visual review of every plausible candidate in the Before/After viewer (blink and slider modes).
2. For impact-like candidates: request/identify CTX coverage to narrow the formation date; search the HiRISE caption archive and the Daubar et al. catalogue updates; check for a crater bowl at full 0.25 m resolution.
3. For slope-streak/albedo candidates: compare with additional HiRISE/CTX epochs to establish formation vs. fading and seasonality.
4. Re-run poorly registered pairs after DEM-based orthorectification (HiRISE/CTX DTMs from USGS STAC) to remove parallax.
