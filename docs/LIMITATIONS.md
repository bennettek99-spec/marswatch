# MARSWATCH — Scientific limitations

Read this before interpreting any output.

## What a MARSWATCH candidate is — and is not

* A candidate is a **region where two co-registered images differ more than the noise and
  registration model predict**, plus heuristics about what kind of change it might be.
* The **score is a heuristic ranking**, not a probability; it has not been calibrated, and the
  validation set (19 sites) is far too small to calibrate it.
* No candidate is a confirmed discovery. `plausible_unverified` means only that the automated
  artifact tests did not fire. Expert visual review, a literature/catalogue search, and ideally a
  third observation are required before any claim.

## Data limitations

1. **Uncontrolled pointing.** USGS COGs use a-priori SPICE; inter-image offsets of 30–200 m (up to
   several hundred) are corrected by image matching, not by bundle adjustment. Absolute candidate
   coordinates are uncertain by ~100 m; positions are given in both images' pointing frames.
2. **Resampling.** COGs are cubic-resampled re-projections of the PDS RDRs, which are themselves
   map-projected. We resample a third time onto the analysis grid (bilinear). Features of 1–2
   pixels are affected.
3. **Recent observations** appear in the USGS COG bucket with a lag; the PDS JP2 fallback works but
   is ~50× slower, so batch validation skips such pairs (recorded as “skipped”).
4. **Atmosphere.** Dust storms and haze reduce contrast (the 2007 global dust storm image
   PSP_004440_2125 has no usable surface signal). The structure-SNR gate catches the extreme
   cases; moderate haze still changes shading contrast and produces artifacts that are only
   partially caught by the contrast-ratio test.
5. **CTX not integrated.** CTX EDRs need ISIS3 calibration and map projection. Many new impacts in
   the catalogue were found with CTX; without it, our before/after coverage is limited to sites
   with repeat HiRISE imaging (19 documented craters qualify).
6. **No DEMs.** Downslope direction for slope streaks and shadow prediction are not modelled; slope
   streak classification uses morphology only.

## Method limitations

1. **Illumination and viewing geometry.** Different incidence/sun azimuth shift shadows; different
   emission angles produce parallax on relief. Pair selection penalises these, and artifact tests
   (dipole, shadow fraction, contrast ratio, relief) suppress many cases, but shadow-related false
   positives remain the dominant error mode in our audits.
2. **Registration residuals.** The noise model uses one global residual estimate per pair plus a
   coarse local quality map; sharp local misregistration (e.g. on steep slopes with parallax) can
   still yield false positives.
3. **Heuristic categories.** Category rules were written from physical reasoning and adjusted after
   inspecting validation run 1 (documented in RESEARCH_LOG.md). They are not learned or validated
   per category, except new impacts.
4. **Method C** uses ImageNet features with no Mars-specific training. Its AUC is reported, but it
   is supporting evidence only. No Siamese/segmentation model was trained: there is no verified
   labelled HiRISE change dataset of adequate size, and training on the 19 validation sites would
   leak the test set.
5. **Seasonal processes** (frost, polar CO₂ activity, dust devils) are only crudely categorised; high
   latitude pairs with ΔLs > 20° produce many genuine-but-expected changes.
6. **Small craters.** Detection relies mainly on the dark blast zone. Craters without a resolvable
   blast zone and smaller than ~2–3 m (4–6 px at 0.5 m) are rarely detected (see the sensitivity
   results).

## Validation limitations

* 19 documented positive sites only (all catalogued new impacts with HiRISE coverage both before and
  after formation). Precision estimates assume no other real change in each 1 km² window — real
  undocumented changes (e.g. slope streaks, other impacts) would be counted as false positives.
* Rules were revised after validation run 1 on the same sites; the **tuning-set** numbers are
  therefore optimistic. The **held-out** set (alternative image pairs at the same sites, never
  inspected during development) is the fairer estimate, but it shares sites with the tuning set.
* Sensitivity-vs-size is measured with **synthetic injections** into real imagery (labelled as
  such); real blast zones vary in shape, tone and contrast more than the injection model.
* Performance numbers were measured in a cloud Linux container (4 vCPU, network-bound), not on the
  target Apple Silicon Mac mini.
