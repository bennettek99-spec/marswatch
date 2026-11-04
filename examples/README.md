# Reproducible example analyses (authentic NASA HiRISE observations)

Each command re-downloads only the needed pixels from the USGS COGs, re-runs the full pipeline and
writes a new run directory under `data/runs/` with `run.json`, `report.md`, images and chips.
Results should match the values below to within small differences from nondeterministic
floating-point order; registration offsets depend on the archive's a-priori pointing, which does
not change.

## 1. Documented new impact crater D22-0887 (Daubar et al. 2022), 9.1 m, Olympus Mons south flank

```bash
marswatch analyze PSP_007023_1980_RED ESP_056155_1980_RED --lat 17.762 --lon 226.942 --half 500 --res 0.5
```

Expected: pointing offset ≈ 60 m E / 14 m N corrected; registration *good* (checkpoint RMS ≈ 0.45 px);
top candidate `new_impact_crater`, `known_documented` (D22-0887), dark radial blast zone ≈ 250 m,
plus 1–2 small `likely_artifact` components on an old crater rim (shadow dipole, Δinc ≈ 20°).

## 2. Documented cluster impact D22-0514 (dual-toned blast zone), Elysium Planitia

```bash
marswatch analyze ESP_039913_1845_RED ESP_043605_1845_RED --lat 4.5105 --lon 135.8219 --half 500 --res 0.5
```

Expected: a ≈ 220 m dark blast zone (`known_documented`, score ≈ 1.0) and several further darkening
spots 100–250 m away associated with the same catalogued cluster event.

## 3. Input QC: an image acquired during the 2007 global dust storm

```bash
marswatch analyze PSP_004440_2125_RED ESP_027555_2125_RED --lat 32.2279 --lon 186.824 --half 500 --res 0.5
```

Expected: `InputRejected` — PSP_004440_2125 structure SNR ≈ 0.9 (< 2) and registration fails; no
candidates are produced. (ESP_027555_2125 alone shows the D22-0230 crater clearly.)

## 4. Survey candidate 1987 — new dark slope streak, Lycus Sulci (plausible, unverified)

```bash
marswatch analyze PSP_008513_2060_RED ESP_045435_2055_RED --lat 25.4713 --lon 220.2242 --half 400 --res 1.0
```

Expected: an elongated (aspect ≈ 8, ≈ 260 m) darkening candidate absent in 2008 and present in 2016.
Follow-up (`marswatch followup <id>`): no later HiRISE image, not a HiRISE slope-streak monitoring
target, not in the Daubar catalogue (which lists impacts only).

## 5. Validation and synthetic tests

```bash
marswatch validate --set holdout && marswatch validate --skip-craters --registration --injection && marswatch validate
```

Writes `docs/VALIDATION_RESULTS.md`. Takes roughly 1 hour on 4 cores with network access.
