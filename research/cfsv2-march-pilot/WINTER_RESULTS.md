# Winter validation and reference review — September 5, 2026

## Release decisions

| Product | Decision | Evidence and remaining requirement |
|---|---|---|
| March snowfall departure reference | Advance the interpolated candidate for implementation review; keep this preview outside production | Transformation order is consistent with the forecast calculation, and historical references can be interpolated to each cycle date. This experiment covers one September anchor and March only. Other run dates/months and operational reference integration remain unverified. |
| December native totals | Do not apply a universal mean-ratio correction | Corrected error beats climatology at 6/15 stations overall and 5/14 with snowy validation cases. |
| January native totals | Do not apply a universal mean-ratio correction | Only 3–4 chronological validation cases per station; correction worsens raw error at two stations. |
| February native totals | Reject the universal correction as tested | Only 3/14 stations beat climatology on snowy cases; correction increases raw error at Boston and Detroit. |
| DJF native totals | Retain station-level exploratory results; do not interpolate factors across CONUS | Only 3–4 validation seasons per station, and incomplete model windows exclude the snowiest observed season at six stations. |

No live map, forecast value, production schedule, or publication path changed.
These are product-specific decisions, not a claim that an anomaly-reference
change calibrates native snowfall totals.

## Final March reference comparison

The final candidate uses 348 historical forecasts: August 29, September 3, and
September 8, four initialization hours each, across 29 years. Snowfall is derived
before same-hour linear interpolation to each of the 24 requested dates. The
result is a date-matched reference estimate, not 24 actual historical forecasts
per year. No current September 8 forecast is used.

Compared with the prior 25%/75% reference, CONUS area-weighted mean absolute
change is 0.00589 inches of water equivalent; the largest grid-cell change is
0.04045 inches. Against the reconstructed existing method, mean absolute change
is 0.23146 inches and 64.3% of CONUS area changes by at least 0.05 inches.
These differences include historical sampling/smoothing and transformation
order, not just temporal interpolation. Weights use spherical grid-cell areas
with midpoint latitude bounds and a state-polygon grid-center CONUS mask.

| Location | Existing method | Interpolated candidate | Omit-one-historical-winter range |
|---|---:|---:|---:|
| Raleigh | +0.157 | +0.117 | +0.114 to +0.130 |
| Asheville | +1.722 | +1.409 | +1.397 to +1.452 |
| Oklahoma City | +0.724 | +0.606 | +0.601 to +0.637 |
| Denton TX | +0.117 | +0.090 | +0.088 to +0.108 |
| Chicago | -1.727 | -0.815 | -0.853 to -0.770 |
| Boston | -0.825 | +0.080 | +0.005 to +0.144 |

All values in this table are water-equivalent inches, not snow-depth inches.
The interpolation refinement leaves the southern positive signal intact. Boston
remains close to zero; its final omission range is slightly positive, unlike
the earlier weighted candidate's range. Omission ranges are sensitivity tests,
not confidence intervals or forecast probabilities.

The final interpolated grid archive reproduced its SHA-256 exactly on a complete
retained-input replay. The live March baseline metadata was also checked: it
uses the September 5 06Z calibration without a prior-cycle fallback, consistent
with the reference reconstructed for this comparison. The live product exposes
no numeric snowfall-anomaly grid for an independent pixel-for-pixel replay.

## Data coverage and method

The experiment requested 936 native SRWEQ monthly forecasts: 13 initialization
years (2011–2023), three target months, and the exact 24-cycle August 30 12Z to
September 5 06Z window. It recovered 930 records. Seven initial connection
timeouts were recovered in a second pass with fewer concurrent downloads.
Six files still returned HTTP 404, leaving 33 complete model months: 12 December,
9 January, and 12 February windows. Nine complete model DJF seasons remain.
Missing cycles exclude the entire monthly ensemble; DJF requires all three
complete model and observation months.

| Missing initialization | Target month |
|---|---|
| 2014-08-30 12Z | January 2015 |
| 2019-09-04 18Z | December 2019 |
| 2019-09-04 18Z | January 2020 |
| 2019-09-04 18Z | February 2020 |
| 2020-08-31 18Z | January 2021 |
| 2022-08-31 06Z | January 2023 |

Daily ACIS observations were reused from the March pilot, with December 2011
added. Incomplete observed months were excluded at Denver (December 2013),
Burlington (February 2013 and December 2020), and Pittsburgh (January 2013).
Traces count as zero; missing values never do. Monthly rate integration uses
actual month lengths, including leap February. DJF is a sum, with its correction
fitted to seasonal sums rather than adding separately corrected months.

For each held-out case, the mean observed/model ratio and the observed-mean
comparator use at least five complete earlier winters. The original fixed split
has insufficient later January/DJF cases and reports that separately. It does
not suppress valid expanding-training scores. The same observations and cases
are used for raw, corrected, and climatology comparisons within each test.

## Chronological results

Counts below describe this selected station sample, not independent regional
replications. Lower mean absolute error (MAE) is better. Snowy cases have at
least 0.1 inch observed in the target month or season.

| Period | Held-out cases per station | Correction beats raw MAE | Beats climatology, all cases | Beats climatology, snowy cases |
|---|---:|---:|---:|---:|
| December | 6–7 | 15/15 | 6/15 | 5/14 |
| January | 3–4 | 13/15 | 7/15 | 5/15 |
| February | 6–7 | 13/15 | 6/15 | 3/14 |
| DJF | 3–4 | 15/15 | 8/15 | 8/15 |

The naive correction is not uniformly beneficial even relative to raw totals.
Boston February MAE rises from 9.586 to 13.717 snow inches. Omitting the 2014
initialization winter from training reduces corrected MAE to 7.584, but the
corresponding climatology comparator is still better at 6.870 inches. This is a
large dependence on a single training winter, not a reliable universal fix.
Buffalo January MAE rises from 10.546 to 22.133 inches after correction. Raleigh
January and Detroit February also lose to their raw forecasts.

## Single-winter influence and omitted extremes

We separately omit each earlier training winter while preserving the validation
cases, and omit each validation case when assessing the reported advantage.
We repeat the comparison on snowy cases. Requiring a negative MAE difference
against climatology in all those omission checks, plus at least three snowy
validation cases, leaves these **exploratory** station/period results:

- December: Boston, Detroit, St. Louis.
- January: Denver, Minneapolis, Cleveland, Pittsburgh.
- February: none.
- DJF: Denver, Minneapolis, Detroit, Cleveland.

This is a stability description, not significance testing, a new independent
holdout result, or authority to transfer a station factor to neighboring cells.
The narrow DJF sample is especially consequential: the snowiest observed DJF
within the 13-year observation period is excluded from model verification at
Oklahoma City, Boston, DFW, Denver, Minneapolis, and Pittsburgh. For example,
Boston's observed 2014/15 DJF total is 99.4 inches, but its January model window
is incomplete. February can still be evaluated separately where complete.
Unmatched observations remain in the JSON audit rather than disappearing.

## Reproduction and scope

All 930 retained native records were re-decoded in offline mode. Every sampled
station value matched the online calculation exactly (maximum difference 0.0
inches). Compact caches retain exact native GRIB records, checksums, and the
original full-file URL/hash provenance. Missing records remain unavailable
without making network requests. The saved package includes case-level CSVs,
full scores, source provenance, observation responses, and numerical references.

Twenty targeted research tests passed, including calendar rollover, leap
February, missing/duplicate observations, complete seasonal membership, cache
integrity, offline behavior, interpolation brackets/hours, and separation of
short fixed-split and expanding-training results. Research code and the manual
workflow remain isolated from the Pages publisher. The expanded manual workflow
has not been executed on GitHub in this session; its numerical jobs ran in the
cloud workspace, and GitHub runs the repository contract checks.

Sources: [NOAA operational archive](https://www.ncei.noaa.gov/oa/prod-cfs-operational-forecast/index.html),
[NOAA reforecast archive](https://www.ncei.noaa.gov/oa/prod-cfs-reforecast/index.html),
[ACIS daily observations](https://data.rcc-acis.org/StnData).
Reproduction commands and definitions are in [README.md](README.md).
