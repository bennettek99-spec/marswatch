# MARSWATCH — Methods

This document describes exactly what the pipeline does. Parameter defaults live in code
(`marswatch/detect/classical.py:ClassicalParams`, `marswatch/config.py`); every run records the
parameters it used and a hash of the code (`run.json → code_version`).

## 1. Data sources

| Source | What we use | Access |
|---|---|---|
| HiRISE PDS archive (U. Arizona) | `INDEX/RDRCUMINDEX.TAB` + `.LBL`: metadata for every RDR (dates, corner coordinates, incidence/emission/phase, sub-solar azimuth, Ls, map scale, targeting rationale). RED RDR JPEG2000 originals as fallback imagery. | `https://hirise-pds.lpl.arizona.edu/PDS/` (HTTP, range requests) |
| USGS Astrogeology analysis-ready HiRISE (doi:10.5066/P944DLP8) | Cloud-Optimized GeoTIFFs of the same RED RDRs, re-projected (cubic) to IAU 2015 Mars equirectangular / polar stereographic, uint16 with DN→I/F scale/offset; provenance file per product links back to the PDS JP2. | STAC API `https://stac.astrogeology.usgs.gov/api`, collection `mro_hirise_uncontrolled_observations`; files on `astrogeo-ard.s3-us-west-2.amazonaws.com` |
| Daubar et al. (2022) JGR Planets 127, e2021JE007145 | Table S1: 1,203 dated new impacts (location, diameter, bracketing before/after images). Ground truth for validation and for “known documented” labelling. | Zenodo record 6604912 |
| NASA Mars Trek | Global Viking MDIM 2.1 / MOLA basemap tiles for the map view only (never used for detection). | `trek.nasa.gov/tiles` |

CTX: the PDS imaging node hosts CTX EDRs, but they are raw, unprojected, uncalibrated
products that require ISIS3 (`mroctx2isis`, `spiceinit`, `ctxcal`, `cam2map`) to be compared
reliably. ISIS3 is not installable in our target environment without conda and multi-GB SPICE
kernels, so CTX is **not** integrated in this version (see LIMITATIONS.md).

## 2. Discovery of multi-temporal pairs

1. The cumulative index (~170 MB) is parsed into SQLite (`observations`, 103,933 RED products as
   of 2026-11-04) with an R-tree over footprint bounding boxes. Column names are read from the
   PDS label, not hard-coded.
2. Candidate pairs: R-tree bbox query → exact intersection of the four-corner footprints,
   computed in a local Lambert azimuthal equal-area projection on the Mars sphere (R = 3,396,190 m).
3. Each pair gets geometry deltas and a **suitability** score (heuristic, 0–1):
   `exp(-Δinc/12°) · exp(-Δsun_az/60°) · exp(-Δemission/20°) · min(1, overlap/10 km²)^0.5`,
   ×`exp(-ΔLs/40°)` above 50° latitude (seasonal frost), ×0.05 if Δt < 30 days (stereo pair, not a
   change pair). Warnings are attached for Δinc > 15°, Δaz > 45°, Δemission > 25°.
4. Bounded surveys select the best-matched pairs with distinct overlap centres
   (`select_diverse`: Δt ≥ 300 d, Δinc ≤ 10°, Δaz ≤ 25°, Δemission ≤ 15°, ≥ 4 km apart).

## 3. Reading and resampling

Both images are resampled onto one **analysis grid**: north-up local LAEA centred on the area of
interest, square pixels at the working resolution (default 1 m for surveys, 0.5 m for validation).
For each grid (or tile of it) the reader computes the source window, reads it decimated to ≈1.5×
the grid resolution through GDAL `/vsicurl/` (COG overviews are used automatically), converts
DN → I/F with the embedded scale/offset, and warps bilinearly. Reads are rate limited (token
bucket, default 4 req/s) and cached as compressed float16 `.npz` under a size budget (LRU eviction).

## 4. Input quality control

Before registration, both images are tested with a **structure-to-noise ratio**: std of a
difference-of-Gaussians band (σ = 2–20 px) divided by Immerkær's Laplacian noise estimate, on a
400 m window at 0.5 m/px. Usable HiRISE terrain measured 4.6–7.7; an image taken through the 2007
global dust storm measured 1.0. Pairs with SNR < 2 are rejected with a recorded reason.

## 5. Registration

HiRISE COGs carry a-priori (uncontrolled) SPICE pointing; our measured offsets between
observations are typically 30–200 m.

* **Coarse**: NCC (`cv2.matchTemplate`, `TM_CCOEFF_NORMED`) of high-pass-filtered images
  (σ = 4 px), template = after-image interior, search margin 600 m at 4 m/px; fallback 1500 m at
  8 m/px; refined at 2 m/px. Accepted if peak > 0.15 and peak − second peak > 0.02.
  The after image is then **re-read** with the grid shifted by the offset, so no data is lost at
  the edges.
* **Fine**: 96-px patches every 64 px, NCC search ±24 px with parabolic sub-pixel refinement;
  textureless patches (σ < 0.3 in normalised high-pass units) are skipped. RANSAC affine
  (threshold 2 px), then the inlier residuals are interpolated (linear + nearest fill, Gaussian
  smoothing) into a dense residual field to absorb jitter and relief parallax. The after image is
  warped with `cv2.remap`.
* **Diagnostics**: displacement is re-measured after warping on a **held-out checkpoint grid**
  offset by half a step (never used for fitting). We report checkpoint RMS / P90, matched fraction,
  high-pass NCC before/after, and a per-pixel quality map
  `exp(-|residual|/1 px) · clip(peak/0.6)`. Overall quality
  `exp(-RMS/1.5) · coverage · clip((NCC+0.1)/0.5)`; status good ≥ 0.5, marginal ≥ 0.2, else poor.
  Detection is suppressed where local quality < 0.15.

## 6. Radiometric normalisation

`A ≈ g(x)·B + o(x)`: gain/offset fitted by iteratively trimmed least squares (4 iterations, reject
|r| > 2.5 MAD) in ~1024-px blocks on lightly smoothed, subsampled pixels; block parameters are
bilinearly interpolated. Changes occupying a minority of a block are rejected as outliers rather
than absorbed.

## 7. Detection

### Method A — classical differencing
* Difference `D = A − B̂`. Robust noise σₙ = 1.4826·MAD of D over the 40 % lowest-gradient pixels.
* **Registration-aware noise model**: σ²(x) = σₙ,s² + (r·max(|∇B|,|∇A|)/s)², with r = measured
  checkpoint RMS (floored at 0.5 px) and s the smoothing scale.
* Multi-scale z: Gaussian smoothing s ∈ {1, 2, 4, 8} px, per-scale empirical noise, keep the
  scale with max |z|.
* SSIM map (Gaussian σ = 2) as structural evidence.
* Adaptive thresholding: hysteresis on |z| (low 3.5, high 6.0), separately for darkening and
  brightening; 2×2 opening, closing, hole filling.
* Connected components grouped by a 4-px dilation (fragmented blast zones/rays become one
  candidate); components < 6 px dropped; regionprops shape statistics.

### Method B — feature-based characterisation (per component)
* Crater template NCC (bowl shading model: wall toward the sun dark, far wall bright, lit rim),
  radii 1.5–20 px × 8 orientations, after vs before; orientation compared with the solar azimuth
  (PDS convention: clockwise from 3 o'clock, NORTH_AZIMUTH = 270 → north up).
* LoG blobs on the darkening z-map (crater centres, 1–20 m).
* Radial structure: fraction of 36 angular bins with mean darkening z > 1.5 (blast zone), ray
  contrast.
* Slope-streak morphology: elongation (major/minor), length, taper (end-width ratio).
* Texture: Laplacian energy ratio, LBP (P = 8, R = 1, uniform) χ²; new-edge fraction (Canny edges
  in A not within 2 px of edges in B).
* Artifact indicators: relief index (median |∇B| in region / scene median); **dipole** (adjacent
  opposite-polarity component); **shadow fraction** (pixels on/next to cast shadows, defined as
  < median − 2.5 MAD and < 0.7·median in either image); **context contrast ratio** (albedo-normalised
  Laplacian CV in a 60-px padded window, sensitive to haze/illumination differences but not to
  multiplicative albedo changes); local registration quality; proximity to the overlap edge.
* Residual displacement (32-px patches) inside large low-SSIM regions → bedform migration.

### Method C — pretrained deep features (evaluated, not assumed)
Frozen ImageNet ResNet-18 (torchvision) up to layer 3; 64-px chips (before vs after) → pooled
embeddings → cosine distance, expressed as a robust z-score against 64 random background chips of
the same pair. Apple `mps` / CUDA / CPU. No Mars training data was used (see LIMITATIONS.md).

### Fusion and categories
Heuristic score in [0,1]:
`(0.35·strength + 0.15·size + 0.15·(1−SSIM) + 0.2·method agreement + 0.15·local registration) · (1 − artifact index)`
with strength `1−exp(−(|z|−3)/4)`, size `1−exp(−px/40)`. The artifact index accumulates the
penalties listed in `detect/fuse.py` (dipole on relief, shadows, contrast ratio, illumination
differences on relief, poor local registration, edge proximity).

Categories (heuristic, first match wins): artifact (index ≥ 0.5) → seasonal frost/albedo
(|lat| > 45°, ΔLs > 20°, > 2 ha) → dune/bedform (coherent residual displacement) → **new impact**
if radial darkening with elongation < 4 → slope streak (elongation ≥ 3, length ≥ 15 m) → new impact
(darkening + crater template appearing, or compact LoG blob) → rockfall/boulder (< 30 m², on relief)
→ other change.

Status: `known_documented` (associated with a catalogued change formed inside the pair's time
window: reference point inside the region, within max(100 m, 1.5 D), or within 500 m for a
catalogued *cluster* impact), `likely_artifact` (artifact category or index ≥ 0.5),
`insufficient_evidence` (< 12 px, |z| < 5, local registration < 0.3, or score < 0.3), else
`plausible_unverified`.

## 8. Georeferencing of candidates

Positions are reported in both pointing frames: the before image's (grid frame) and the after
image's (grid + coarse offset + local flow). Catalogue coordinates of Daubar et al. (2022) agreed
with the after-image frame to ~10 m for D22-0887, so matching uses the after frame first.

## 9. Reproducibility

Every run writes `data/runs/<run_id>/run.json` (sources with PDS/COG/uahirise URLs, parameters,
analysis grid, registration diagnostics, statistics, candidates with evidence) and `report.md`
(with the exact CLI command to reproduce). The code hash is computed at import time.
