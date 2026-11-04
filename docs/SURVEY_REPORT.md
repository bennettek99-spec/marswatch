# MARSWATCH survey report

_Generated 2026-11-04 04:13 UTC from the MARSWATCH database. Code version(s): `0.3.0+bb6aa95341`._

## Scope

* Regions: arabia-terra-w, lycus-sulci
  * Lycus Sulci (Olympus Mons aureole), 24–30°N, 218–228°E — primary
  * Arabia Terra W, 5–15°N, 0–10°E — secondary
* Pair selection: best-matched repeat HiRISE pairs (Δt ≥ 200–300 d, Δinc ≤ 10–12°, Δsun az ≤ 25–30°, Δemission ≤ 15°), spatially distinct (≥ 2–4 km apart); ≤ 12 km² of each overlap analysed at 1 m/px (centre crop), with resolution fallback to 2/4 m when registration is poor.
* Image pairs analysed: 17 (+1 rejected by input QC); failed jobs: 1
* Area analysed (after masking invalid / poorly registered areas): **157.2 km²**
* Candidates: 231

## Candidates by status

* insufficient_evidence: 7
* likely_artifact: 81
* plausible_unverified: 143

## Candidates by category (heuristic)

* new_impact_crater: 101
* illumination_or_registration_artifact: 81
* other_change: 25
* slope_streak: 21
* dune_bedform_change: 3

## Analysed pairs

| pair | region | Δt (d) | Δinc | analysed km² | res (m) | registration | checkpoint RMS px | cand. | plausible | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| ESP_017585_2080__ESP_078865_2080 | lycus-sulci | 4775 | 0.0 | 7.34 | 4.0 | marginal (0.23) | 2.02 | 0 | 0 | fallback 1.0→2.0→4.0 |
| ESP_013009_2095__ESP_092868_2095 | lycus-sulci | 6222 | 3.2 | 5.64 | 4.0 | poor (0.18) | 2.59 | 4 | 0 | fallback 1.0→2.0→4.0 |
| ESP_050129_2055__ESP_076478_2055 | lycus-sulci | 2053 | 4.4 | 11.10 | 1.0 | marginal (0.49) | 1.06 | 18 | 7 |  |
| PSP_004175_2060__ESP_057118_2060 | lycus-sulci | 4125 | 1.9 | 11.57 | 1.0 | good (0.62) | 0.72 | 37 | 24 |  |
| PSP_008513_2060__ESP_045435_2055 | lycus-sulci | 2877 | 0.9 | 4.58 | 1.0 | good (0.83) | 0.27 | 5 | 4 |  |
| ESP_069265_2070__ESP_086750_2070 | lycus-sulci | 1362 | 5.7 | 6.84 | 2.0 | marginal (0.23) | 2.19 | 1 | 1 | fallback 1.0→2.0 |
| ESP_027021_1900__ESP_035592_1900 | arabia-terra-w | 668 | 0.6 | 7.78 | 1.0 | marginal (0.22) | 2.25 | 6 | 1 |  |
| ESP_033804_2065__ESP_051197_2065 | lycus-sulci | 1355 | 2.7 | 11.67 | 1.0 | good (0.92) | 0.13 | 54 | 53 |  |
| ESP_048304_1905__ESP_057205_1905 | arabia-terra-w | 694 | 0.7 | 9.38 | 1.0 | marginal (0.37) | 1.48 | 0 | 0 |  |
| PSP_008679_1905__ESP_088815_1910 | arabia-terra-w | 6244 | 1.1 | — | 4.0 | — (—) | — | 0 | 0 | QC-rejected: ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust s; ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust storm suspe |
| ESP_083032_2080__ESP_092776_2080 | lycus-sulci | 759 | 4.4 | 9.47 | 4.0 | marginal (0.39) | 1.40 | 0 | 0 | fallback 1.0→2.0→4.0 |
| PSP_006952_1870__ESP_024542_1870 | arabia-terra-w | 1371 | 2.1 | 11.79 | 1.0 | good (0.86) | 0.22 | 43 | 38 |  |
| ESP_056836_1900__ESP_074996_1900 | arabia-terra-w | 1415 | 0.6 | 11.14 | 1.0 | good (0.59) | 0.80 | 33 | 0 |  |
| ESP_023698_1900__ESP_058959_1900 | arabia-terra-w | 2748 | 1.0 | 11.77 | 1.0 | good (0.77) | 0.40 | 8 | 6 |  |
| ESP_056994_1860__ESP_084121_1860 | arabia-terra-w | 2114 | 2.8 | 8.63 | 1.0 | good (0.57) | 0.83 | 4 | 0 |  |
| ESP_013505_1930__ESP_022498_1930 | arabia-terra-w | 701 | 3.8 | 11.75 | 1.0 | good (0.79) | 0.35 | 2 | 0 |  |
| ESP_028498_1895__ESP_079796_1900 | arabia-terra-w | 3997 | 0.8 | 6.76 | 2.0 | marginal (0.44) | 1.23 | 2 | 0 | fallback 1.0→2.0 |
| ESP_065737_1930__ESP_073664_1930 | arabia-terra-w | 618 | 0.9 | 10.02 | 2.0 | marginal (0.29) | 1.85 | 14 | 9 | fallback 1.0→2.0 |

## Plausible unverified candidates (143; top 25 shown)

These passed the automated artifact tests. They are **not** confirmed discoveries. Follow-up results (third-image persistence, HiRISE targeting history, catalogue) are shown where run. "Triage" notes are a preliminary visual assessment by the operating agent, not expert review.

### Candidate 2115 — new_impact_crater — score 0.95

* Pair `ESP_069265_2070__ESP_086750_2070`; location (before frame) 26.45766°N 227.11822°E; area 6908 m² (≈93.8 m); local registration quality 0.65
* Evidence for: darkening change, peak |z|=16.4, area 6908 m² (≈93.8 m); darkening surrounds centre in 61% of directions (blast-zone-like); angular variation suggests rays (contrast 0.69); local structure changed (mean SSIM 0.30); pretrained CNN embedding change z=15.0 vs background (unvalidated evidence)
* Evidence against: none recorded
* Follow-up: third image none → not run; targeting tags ['slope_streak', 'monitoring']; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): new dark slope streak (heuristic category 'new impact crater' is wrong); HiRISE slope-streak monitoring site, so the HiRISE team is likely aware. Credible change.
* Chip: `data/runs/ESP_069265_2070__ESP_086750_2070__20261104T034502_47f582/chips/cand_000.jpg`

### Candidate 1987 — slope_streak — score 0.81

* Pair `PSP_008513_2060__ESP_045435_2055`; location (before frame) 25.47131°N 220.22420°E; area 6155 m² (≈88.5 m); local registration quality 0.73
* Evidence for: darkening change, peak |z|=17.9, area 6155 m² (≈88.5 m); local structure changed (mean SSIM 0.33); elongated (aspect 8.0, length 262 m); pretrained CNN embedding change z=5.8 vs background (unvalidated evidence)
* Evidence against: local image contrast differs by ×4.7 between images (haze, illumination or resolution difference): shading differences are expected
* Follow-up: third image none → not run; targeting tags none; catalogue within 2 km: none
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): new dark slope streak (~260 m) absent in the before image; morphology (narrow, point origin, downslope extension) typical of dark slope streaks. Credible change.
* Chip: `data/runs/PSP_008513_2060__ESP_045435_2055__20261104T034439_584138/chips/cand_000.jpg`

### Candidate 1792 — new_impact_crater — score 0.72

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.49989°N 221.76550°E; area 2386 m² (≈55.1 m); local registration quality 0.87
* Evidence for: darkening change, peak |z|=14.7, area 2386 m² (≈55.1 m); darkening surrounds centre in 94% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_000.jpg`

### Candidate 1793 — new_impact_crater — score 0.69

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.49478°N 221.76492°E; area 1340 m² (≈41.3 m); local registration quality 0.80
* Evidence for: darkening change, peak |z|=10.3, area 1340 m² (≈41.3 m); darkening surrounds centre in 86% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_001.jpg`

### Candidate 2339 — new_impact_crater — score 0.68

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05520°N 6.72846°E; area 6158 m² (≈88.5 m); local registration quality 0.93
* Evidence for: darkening change, peak |z|=15.7, area 6158 m² (≈88.5 m)
* Evidence against: located on steep/high-contrast relief (relief=5.2×median); crater-like shading appears in after image (template NCC 0.71 vs 0.49 before, r≈1.5 m); shading orientation 139° from solar azimuth (inconsistent with illumination)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_000.jpg`

### Candidate 1794 — new_impact_crater — score 0.68

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.50736°N 221.74010°E; area 6230 m² (≈89.1 m); local registration quality 0.81
* Evidence for: darkening change, peak |z|=10.0, area 6230 m² (≈89.1 m); darkening surrounds centre in 92% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_002.jpg`

### Candidate 2340 — slope_streak — score 0.68

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.09267°N 6.73470°E; area 12865 m² (≈128.0 m); local registration quality 0.77
* Evidence for: darkening change, peak |z|=14.7, area 12865 m² (≈128.0 m); elongated (aspect 3.6, length 287 m)
* Evidence against: local image contrast differs by ×2.9 between images (haze, illumination or resolution difference): shading differences are expected
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_001.jpg`

### Candidate 2341 — slope_streak — score 0.68

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06828°N 6.72844°E; area 16750 m² (≈146.0 m); local registration quality 0.79
* Evidence for: darkening change, peak |z|=15.0, area 16750 m² (≈146.0 m); elongated (aspect 3.2, length 355 m)
* Evidence against: located on steep/high-contrast relief (relief=6.0×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_002.jpg`

### Candidate 2272 — new_impact_crater — score 0.68

* Pair `ESP_033804_2065__ESP_051197_2065`; location (before frame) 26.41401°N 222.51770°E; area 850 m² (≈32.9 m); local registration quality 0.88
* Evidence for: darkening change, peak |z|=12.7, area 850 m² (≈32.9 m); darkening surrounds centre in 92% of directions (blast-zone-like)
* Evidence against: located on steep/high-contrast relief (relief=2.5×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/ESP_033804_2065__ESP_051197_2065__20261104T034701_98d87d/chips/cand_000.jpg`

### Candidate 1795 — new_impact_crater — score 0.67

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.50132°N 221.76377°E; area 578 m² (≈27.1 m); local registration quality 0.86
* Evidence for: darkening change, peak |z|=8.6, area 578 m² (≈27.1 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_003.jpg`

### Candidate 2342 — new_impact_crater — score 0.65

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06936°N 6.75555°E; area 4251 m² (≈73.6 m); local registration quality 0.90
* Evidence for: darkening change, peak |z|=6.7, area 4251 m² (≈73.6 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: none recorded
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_003.jpg`

### Candidate 1796 — new_impact_crater — score 0.65

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.50239°N 221.76388°E; area 431 m² (≈23.4 m); local registration quality 0.85
* Evidence for: darkening change, peak |z|=7.5, area 431 m² (≈23.4 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_004.jpg`

### Candidate 2343 — other_change — score 0.65

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.02742°N 6.73215°E; area 7214 m² (≈95.8 m); local registration quality 0.91
* Evidence for: brightening change, peak |z|=20.3, area 7214 m² (≈95.8 m)
* Evidence against: located on steep/high-contrast relief (relief=4.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_004.jpg`

### Candidate 1797 — new_impact_crater — score 0.65

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.50304°N 221.74949°E; area 380 m² (≈22.0 m); local registration quality 0.70
* Evidence for: darkening change, peak |z|=7.5, area 380 m² (≈22.0 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_005.jpg`

### Candidate 2344 — new_impact_crater — score 0.63

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05259°N 6.74368°E; area 4375 m² (≈74.6 m); local registration quality 0.87
* Evidence for: darkening change, peak |z|=6.1, area 4375 m² (≈74.6 m); darkening surrounds centre in 78% of directions (blast-zone-like)
* Evidence against: none recorded
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_005.jpg`

### Candidate 2345 — other_change — score 0.63

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06323°N 6.72870°E; area 10418 m² (≈115.2 m); local registration quality 0.83
* Evidence for: darkening change, peak |z|=15.8, area 10418 m² (≈115.2 m)
* Evidence against: located on steep/high-contrast relief (relief=5.6×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_006.jpg`

### Candidate 2346 — new_impact_crater — score 0.63

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.07363°N 6.72967°E; area 651 m² (≈28.8 m); local registration quality 0.64
* Evidence for: darkening change, peak |z|=8.9, area 651 m² (≈28.8 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: located on steep/high-contrast relief (relief=5.1×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_007.jpg`

### Candidate 1798 — new_impact_crater — score 0.63

* Pair `PSP_004175_2060__ESP_057118_2060`; location (before frame) 25.49648°N 221.77111°E; area 2008 m² (≈50.6 m); local registration quality 0.36
* Evidence for: darkening change, peak |z|=8.5, area 2008 m² (≈50.6 m); darkening surrounds centre in 69% of directions (blast-zone-like); angular variation suggests rays (contrast 0.56)
* Evidence against: an image was acquired during a global dust storm: haze changes shading contrast non-linearly
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_004175_2060__ESP_057118_2060__20261104T034327_bab07f/chips/cand_006.jpg`

### Candidate 2347 — new_impact_crater — score 0.63

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05512°N 6.73108°E; area 3359 m² (≈65.4 m); local registration quality 0.89
* Evidence for: darkening change, peak |z|=8.9, area 3359 m² (≈65.4 m); darkening surrounds centre in 61% of directions (blast-zone-like); angular variation suggests rays (contrast 0.96)
* Evidence against: located on steep/high-contrast relief (relief=5.2×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_008.jpg`

### Candidate 2348 — other_change — score 0.62

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05218°N 6.72996°E; area 3712 m² (≈68.7 m); local registration quality 0.93
* Evidence for: darkening change, peak |z|=14.2, area 3712 m² (≈68.7 m)
* Evidence against: located on steep/high-contrast relief (relief=7.7×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_009.jpg`

### Candidate 2349 — slope_streak — score 0.62

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06806°N 6.74031°E; area 2079 m² (≈51.4 m); local registration quality 0.79
* Evidence for: darkening change, peak |z|=8.4, area 2079 m² (≈51.4 m); elongated (aspect 3.4, length 113 m); widens toward one end (taper 1.7), fan-like
* Evidence against: located on steep/high-contrast relief (relief=4.4×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_010.jpg`

### Candidate 2350 — slope_streak — score 0.62

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.03104°N 6.73234°E; area 2443 m² (≈55.8 m); local registration quality 0.80
* Evidence for: darkening change, peak |z|=8.2, area 2443 m² (≈55.8 m); elongated (aspect 3.5, length 120 m)
* Evidence against: located on steep/high-contrast relief (relief=7.7×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_011.jpg`

### Candidate 2273 — new_impact_crater — score 0.62

* Pair `ESP_033804_2065__ESP_051197_2065`; location (before frame) 26.39373°N 222.51616°E; area 239 m² (≈17.4 m); local registration quality 0.90
* Evidence for: darkening change, peak |z|=8.0, area 239 m² (≈17.4 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: located on steep/high-contrast relief (relief=3.1×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/ESP_033804_2065__ESP_051197_2065__20261104T034701_98d87d/chips/cand_001.jpg`

### Candidate 2351 — new_impact_crater — score 0.60

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.05529°N 6.73302°E; area 510 m² (≈25.5 m); local registration quality 0.87
* Evidence for: darkening change, peak |z|=7.7, area 510 m² (≈25.5 m); darkening surrounds centre in 100% of directions (blast-zone-like)
* Evidence against: located on steep/high-contrast relief (relief=5.3×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_012.jpg`

### Candidate 2352 — slope_streak — score 0.60

* Pair `PSP_006952_1870__ESP_024542_1870`; location (before frame) 7.06473°N 6.73213°E; area 1668 m² (≈46.1 m); local registration quality 0.79
* Evidence for: darkening change, peak |z|=7.6, area 1668 m² (≈46.1 m); elongated (aspect 3.5, length 97 m)
* Evidence against: located on steep/high-contrast relief (relief=5.5×median)
* Triage: Agent triage (preliminary visual check by the operating AI agent, not expert review): part of a pair-level systematic pattern: darkening concentrated on topographic edges (rims, fractures, pits, dune-field walls) across the scene; most likely photometric/shading or parallax difference, not surface change. Likely artifact.
* Chip: `data/runs/PSP_006952_1870__ESP_024542_1870__20261104T035200_9eb546/chips/cand_013.jpg`

## False positives and uncertainties

* 81 candidates were automatically classified as likely artifacts (shadow dipoles, cast shadows, contrast/haze differences, poor local registration).
* 7 candidates had insufficient evidence (small, weak, or in poorly registered areas).
* From validation, the expected false-positive density in well-registered, non-dust-storm pairs is a few per km² at score 0 and ~1–3 per km² at score ≥ 0.6 (see VALIDATION_RESULTS.md): most plausible candidates in a survey are expected to be false positives or real-but-mundane changes (dust redistribution, fading streaks).
* Pairs including dust-storm-epoch images showed systematic ring artifacts around relief; these are penalised but not eliminated.

## Failed jobs

* job 11 (PSP_008679_1905__ESP_088815_1910): input rejected by QC: ESP_088815_1910_RED structure SNR 0.0 < 2.0 (atmospheric opacity / haze / dust storm suspected); registration also failed (quality 0.00)

## Recommended follow-up

1. Expert visual review of every plausible candidate in the Before/After viewer (blink and slider modes).
2. For impact-like candidates: request/identify CTX coverage to narrow the formation date; search the HiRISE caption archive and the Daubar et al. catalogue updates; check for a crater bowl at full 0.25 m resolution.
3. For slope-streak/albedo candidates: compare with additional HiRISE/CTX epochs to establish formation vs. fading and seasonality.
4. Re-run poorly registered pairs after DEM-based orthorectification (HiRISE/CTX DTMs from USGS STAC) to remove parallax.
