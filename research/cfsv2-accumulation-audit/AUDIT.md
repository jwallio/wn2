# CFSv2 snowfall accumulation audit — 6 September 2026

**Decision: no nationwide bias factor is ready to ship.** The audited arithmetic
is consistent with the source field and published grids. Large totals are already
present in native snowfall water equivalent and amplified by a fixed ratio.
Historical station results support a simple adjustment at sampled locations;
they do not define a validated spatial correction for JFM. Production unchanged.

Code baseline: `4ec1e67985f4267c66cd7b9921a2473d316b7c19`.
Run: `cfsv2-2026090512-snowfall_accumulation`, January–March 2027.
Detailed numbers, source URLs and hashes: [evidence.json](evidence.json).
Live provenance: [manifest](https://jwallio.github.io/seasonal/cfsv2_manifest.json).

## Verification scope

- Retrieved published January, February, March and JFM LWE and depth grids.
- Downloaded the actual anchor SRWEQ messages for all three months, verified
  hashes against published provenance, and independently decoded with ecCodes.
  This is a three-message source spot check, not independent reconstruction of
  all 72 contributing monthly forecasts.
- Reviewed calendar integration, 24-cycle means, seasonal sums, cache handling,
  ratio lookup and display interpolation.
- Re-ran the existing 15-station study offline: 936 requested native records,
  930 available, 33 complete model months. Station rows and scores exactly match
  the retained report. This is reproduction, not new validation.

## Calculation findings

Monthly depth = mean(SRWEQ across 24 cycles) × calendar days × 86400 / 25.4 × CWA SLR.

| Check | Finding |
|---|---|
| Field | Surface snowfall water-equivalent rate, parameter 0/1/12; not snowpack |
| Units | Independently decoded as kg m−2 s−1, average |
| Lead | Actual anchor records identify leads 4, 5, 6 for Jan, Feb, Mar |
| Calendar | 31, 28, 31 days; code handles leap February |
| Ensemble | Mean of 24 cycles, not sum; native path requires complete inputs |
| Seasonal total | Published JFM LWE equals Jan + Feb + Mar exactly across the grid |
| Depth conversion | Monthly depth equals LWE × lookup exactly; seasonal error ≤2.85e−14 in |
| Display | Bilinear native LWE, then local ratio; no bicubic overshoot or double multiplication |
| Missing ratios | 19 CWAs masked/hatched, not treated as zero |

NOAA documents [incorrect monthly time metadata and its repair](https://www.cpc.ncep.noaa.gov/products/tools/wgrib2/fix_CFSv2_fcst.html).
Production invokes the documented daily repair and checks month start/end.
Full calendar-month seconds are appropriate for the monthly mean rate; the last
18Z sample does not justify removing six hours. No factor-of-four, factor-of-24,
repeated-month or double-conversion error was found in this path.

## Denton example

Approximate renderer-method values at 33.2148°N, 97.1331°W, using FWD's 13.8:1 ratio:

| Period | Native LWE | Current depth | 10:1 sensitivity only |
|---|---:|---:|---:|
| January | 1.154 in | 15.93 in | 11.54 in |
| February | 1.222 in | 16.86 in | 12.22 in |
| March | 1.217 in | 16.80 in | 12.17 in |
| JFM | 3.593 in | **49.58 in** | **35.93 in** |

The 10:1 column is a conversion sensitivity, not a calibrated forecast. It cuts
depth by 27.5% but retains a large native snowfall-water signal. These are
approximate map values, not Denton observations; the native grid is roughly 1°.

## Ratio assumption

The [CIPS methodology](https://www.eas.slu.edu/CIPS/slr.html) uses a 30-year
cooperative-observer sample of events with snowfall over 2 inches and liquid
equivalent over 0.11 inches, subject to observation/station screening. Its
[CWA charts](https://www.eas.slu.edu/CIPS/SLR/slrmap.htm) provide pooled event
ratios, not monthly forecast ratios or a calibration of CFSv2.

A seasonal total's effective ratio would be snowfall-water-weighted across
events. Applying a pooled event mean is an approximation, not a demonstrated
universal error in one direction. This audit establishes no superior replacement
ratio. CWA boundaries introduce steps unrelated to the CFS field; a 0.05° display
does not add detail to the coarse native forecast.

## Historical evidence

The retained study compares native SRWEQ with ACIS snowfall at 15 selected
stations, using September 5 06Z rolling windows for initialization years
2011–2023. NOAA's [operational archive](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC00878/html)
starts in 2011. This differs from the 1982–2010 phase-derived anomaly reference,
which cannot be used directly as a native snowfall bias reference. The project
has no usable native reforecast bundle; this is not proof none exists elsewhere.

The tested correction is mean(observed) / mean(modeled depth), fitted only on
earlier winters. It preserves relative model amounts and absorbs model and ratio
bias together.

| Target | Stations with lower later-case MAE than raw | Later cases per station |
|---|---:|---:|
| December | 15/15 | 6–7 |
| January | 13/15 | 3–4 |
| February | 13/15 | 6–7 |
| DJF | 15/15 | 3–4 |

DFW DJF raw MAE was **14.26 inches**, adjusted **0.90 inches**, across four later
cases. That is substantial bias reduction. Beating a climatology-only forecast
is not a prerequisite for this model-viewer correction and is not the reason
for withholding a nationwide adjustment.

The constraints are coverage and sample composition: DFW has nine complete DJF
seasons. Four were excluded for incomplete model ensembles, including 2020–21
(5.0 inches observed). Fitted later-case DFW DJF factors were 0.029–0.039; these
are neither Denton nor JFM factors. The research samples nearest grid cells,
not the exact bilinear display at every city. Buffalo January MAE worsened from
10.55 to 22.13 inches; Boston February from 9.59 to 13.72 inches. No national
interpolation method, JFM seasonal factor or complete month/lead table was tested.

## Recommendation

1. Do not silently reduce the national depth map. No arithmetic repair found here
   justifies it, and station factors cannot be spread nationwide without testing.
2. Native snowfall water equivalent is the cleanest direct model quantity for
   this viewer. If depth maps remain, retain estimated/unadjusted wording and
   disclose the fixed event-ratio assumption. Standard 10:1 would be a labeled
   display convention, not a historical correction.
3. A simple empirical adjustment remains reasonable with matching native data,
   month/lead and geographic support. The station research motivates that work
   but does not supply a deployable national table. No AnalogWx-style predictors
   or broad forecast-skill research are needed for this decision.

Audit complete. No production changes; no nationwide correction certified.
