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

## Remaining gates

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
