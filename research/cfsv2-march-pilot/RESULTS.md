# March pilot results — September 5, 2026

**Decision: research pilot complete; do not promote a numerical correction yet.**

The experiment used 116 complete historical forecasts (four cycles for each of 29 initialization years, 1982–2010) and all 24 operational cycles for March 2027. The retained-input replay reproduced the pilot grid archive SHA-256 exactly before comparison fields were added. Independent native decoding matched the published 24-cycle grid with maximum error 4.44e-15 inches of water equivalent.

## Departure reference

The corrected operation order changes the spatial pattern in both directions. It reduces the positive departures at Raleigh, Asheville and Oklahoma City, while reducing the negative departures around Chicago and Boston. It does not remove the underlying positive southern snowfall signal.

Values below are inches of snowfall **water equivalent**, not snow depth. They are nearest coarse grid cells to city coordinates; the observed verification below uses airport coordinates instead.

| Location | Existing-method departure | Pilot departure | Change | Isolated operation-order effect |
|---|---:|---:|---:|---:|
| Raleigh | +0.157 | +0.101 | -0.056 | -0.058 |
| Asheville | +1.722 | +1.367 | -0.355 | -0.341 |
| Oklahoma City | +0.724 | +0.595 | -0.129 | -0.133 |
| Denton TX | +0.117 | +0.086 | -0.031 | -0.037 |
| Chicago | -1.727 | -0.886 | +0.841 | +0.668 |
| Boston | -0.825 | +0.045 | +0.870 | +1.024 |

The existing-method comparison uses the original smoothed NCEI calibration. The isolated operation-order column uses identical unsmoothed historical samples on both sides. Consequently, differences in the first comparison cannot all be attributed to nonlinearity.

The six-day operational window spans six August lead-7 and eighteen September lead-6 initializations. Available historical initializations inside that window supply only four September lead-6 cycles per year. Matching/sensitivity-testing this mix is an outstanding promotion requirement.

## Native snowfall totals

All thirteen sampled September 5 06Z operational forecasts (2011–2023) were available with the exact native SRWEQ field. All five airports had complete daily March snowfall observations for the corresponding 2012–2024 months. Native rate integration and the existing snow-to-liquid ratios were applied unchanged.

A simple station-specific ratio was fitted only on initialization years 2011–2018. On the later 2019–2023 initialization years it reduced mean absolute error at all five stations. However, that test period is disproportionately low-snow (Raleigh has no measurable March snowfall in those five validation years). It cannot establish performance in snowy winters.

The following leave-one-winter-out diagnostic includes all thirteen winters. Each target winter is excluded from its fitted ratio and observed-mean comparison. This uses earlier and later years in training, so it is a diagnostic rather than a historical real-time simulation.

| Airport | Raw MAE (snow inches) | Adjusted MAE | Observed-average MAE | Adjusted beats observed average? |
|---|---:|---:|---:|---|
| KRDU | 2.37 | 0.25 | 0.27 | Yes |
| KAVL | 5.69 | 0.57 | 0.45 | No |
| KOKC | 8.29 | 1.09 | 0.96 | No |
| KORD | 14.45 | 4.05 | 3.45 | No |
| KBOS | 13.17 | 5.44 | 7.16 | Yes |

The adjustment loses to the observed-average comparator at three of five airports. Even at Raleigh, its measurable-snow subgroup MAE is worse than observed climatology (0.71 versus 0.58 inches). This demonstrates bias reduction, not dependable snow-event skill. No station factors have been applied to March 2027, extrapolated across CONUS, or published.

## What was fixed in the research implementation

- Recovered NOAA's migrated archive paths instead of relying on timed-out legacy THREDDS paths.
- Implemented per-forecast historical snowfall before averaging, with equal winter weights.
- Added exact-field/range/date checks, complete-cycle checks, source hashes, and retained-input reproduction.
- Added chronological and leave-one-winter-out native bias screens with observations and a climatology comparator.
- Added an isolated manual GitHub workflow and a comparison renderer.

## Remaining gates after the initial pilot (updated below)

1. Historical sampling sensitivity for the August/September lead mixture and the full 24-cycle native product.
2. Broader spatial verification and an observed correction that adds value beyond climatology, including snowy cases.
3. Only after those gates: production reference integration, expansion to other months/seasons, and site publication.

Production source, maps, schedules and publication remain unchanged. The added research workflow is not included in the Pages publisher allowlist.

## Validation performed

- Six targeted tests passed: historical operation order, incomplete/duplicate cycles, record identity, production phase-function equivalence, chronological leakage protection, and leave-one-out leakage protection.
- Existing Seasonal Actions contract passed; new workflow parsed with read-only contents permission.
- All three-panel comparison maps were rendered and visually inspected.
- Full 29-year computation rerun from retained inputs reproduced the exact pre-comparison grid archive hash.

## Sources and reproducibility

- [NOAA reforecast archive](https://www.ncei.noaa.gov/oa/prod-cfs-reforecast/index.html)
- [NOAA operational forecast archive](https://www.ncei.noaa.gov/oa/prod-cfs-operational-forecast/index.html)
- [ACIS daily station data API](https://data.rcc-acis.org/StnData)
- [Reproduction and method](README.md)

The saved data package contains all requested source-byte ranges and their URL/hash provenance, observation responses, full numerical grids, and both result reports. Research code is retained on this GitHub branch.


## Expanded experiment — exact native ensemble and 15 stations

**Decision: bias reduction is demonstrated; nationwide forecast improvement is not established.**

Twelve of thirteen historical 24-cycle windows were complete (288 native forecasts). The September 4, 2019 18Z March-2020 archive file returned HTTP 404; the entire 2019 initialization window was excluded. All 15 requested stations had complete daily March observations in all 13 years, and supported CIPS ratios at their sampled cells. Therefore each station uses the same 12 model/observation pairs.

The walk-forward test begins with five earlier winters and scores seven later Marches: 2017–2019 and 2021–2024. Each correction and climatology comparator uses only the winters available before that initialization. These are exploratory re-used historical cases, not a new independent promotion set.

| Station | Raw MAE | Corrected MAE | Climatology MAE | Snowy cases | Corrected snowy MAE | Climatology snowy MAE |
|---|---:|---:|---:|---:|---:|---:|
| KRDU | 2.114 | 0.379 | 0.425 | 2 | 0.905 | 0.888 |
| KAVL | 4.765 | 0.670 | 0.676 | 3 | 0.959 | 0.946 |
| KOKC | 7.164 | 0.933 | 0.955 | 2 | 1.735 | 1.541 |
| KORD | 18.585 | 3.199 | 3.262 | 7 | 3.199 | 3.262 |
| KBOS | 12.551 | 7.885 | 7.844 | 6 | 7.867 | 7.847 |
| KDFW | 2.544 | 0.306 | 0.482 | 0 | — | — |
| KDEN | 26.647 | 8.222 | 7.738 | 6 | 7.803 | 7.334 |
| KMSP | 17.779 | 4.601 | 4.259 | 7 | 4.601 | 4.259 |
| KDTW | 11.456 | 3.738 | 3.909 | 6 | 3.427 | 3.698 |
| KCLE | 19.578 | 3.362 | 3.667 | 6 | 2.358 | 2.880 |
| KBUF | 24.298 | 6.596 | 6.862 | 7 | 6.596 | 6.862 |
| KALB | 21.270 | 10.657 | 10.583 | 7 | 10.657 | 10.583 |
| KBTV | 21.816 | 10.388 | 10.453 | 7 | 10.388 | 10.453 |
| KPIT | 18.759 | 5.578 | 5.735 | 7 | 5.578 | 5.735 |
| KSTL | 10.880 | 1.882 | 1.830 | 4 | 1.719 | 1.426 |

All errors are snow-depth inches. Correction improves raw MAE at all 15 stations and beats climatology at 10/15 overall, but only 6/14 with measurable-snow validation cases. Most margins against climatology are small and no significance claim is made. DFW has zero measurable-snow validation Marches; its improvement cannot establish rare-event skill. Raleigh, Asheville and Oklahoma City all lose to climatology on their snowy subgroup. The leave-one-winter-out diagnostic beats climatology at only 7/15 stations. No fitted factors were applied to March 2027 or interpolated across CONUS.

The exact native 24-cycle sampling gap is now addressed for the 12 available winters. Spatial coverage remains a selected station sample, and a useful independently validated correction remains an open production gate.

Ten research tests passed, including exact month-boundary cycle selection, rejection of partial/misaligned ensembles, and prevention of present/future observation leakage. The full native experiment was replayed from retained source downloads with the final chronological validation implementation.

## August/September lead sensitivity

All 29 initialization years supplied August 29 reforecasts, four cycles each. A 25% August / 75% September blend matches the modern lead proportions, while still using eight historical cycles per winter rather than 24 exact dates. August 29 lies outside the modern window. This explicitly labeled approximation does not replace a matched hindcast reference.

| Location | Original pilot departure | Lead-mix departure | Change |
|---|---:|---:|---:|
| Raleigh | +0.1015 | +0.1137 | +0.0123 |
| Asheville | +1.3672 | +1.4063 | +0.0391 |
| Oklahoma City | +0.5950 | +0.5966 | +0.0017 |
| Denton TX | +0.0861 | +0.0848 | -0.0013 |
| Chicago | -0.8858 | -0.8055 | +0.0802 |
| Boston | +0.0451 | +0.0704 | +0.0254 |

Values are snowfall **water-equivalent inches**, not snow depth. The sensitivity is small at Denton and Oklahoma City and does not explain the excessive southern totals. Asheville and Chicago show larger sensitivity. No observed native-snow correction is implied by changing this separate phase-derived departure reference.

The final reference-grid replay reproduced the exact SHA-256 of the initial lead-mix result. Source URLs and hashes, station cases, fitted factors, and numerical reference grids are retained in the expanded result package. The large historical native source files are reproducible from the permanent NOAA URLs; they are not duplicated in that compact result package. The original saved pilot package retains the dated operational inputs.

## Live-cycle recheck

At approximately 21:12 UTC September 5, the 12Z March monthly inventory returned HTTP 404 from NOMADS. The successful scheduled job selected 06Z after finding its eight required monthly files; the live manifest was rebuilt at 19:53:59 UTC. The scheduled next check is 23:45 UTC, subject to GitHub scheduling delay. The shared URL also explicitly pins the 06Z run.

- [Successful scheduled job](https://github.com/jwallio/seasonal/actions/runs/33987436356)
- [Live manifest](https://jwallio.github.io/seasonal/cfsv2_manifest.json)
