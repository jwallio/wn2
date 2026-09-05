# Routine CFSv2 snowfall reference correction

The snowfall workflow now builds a matching model-only reference for every
requested target month before rendering departure maps. DJF and JFM use sums
of the corrected monthly fields. Native snowfall accumulation is unchanged.
There is no station fitting, forecast blending, or new forecasting model.

## Calculation

For each operational cycle date, use nearby same-hour historical forecasts.
Derive snowfall independently from each historical forecast's precipitation
and monthly temperatures before interpolation and averaging. Linear
interpolation uses brackets no more than five days apart, without extrapolation.
Average cycles within each historical year, then weight complete years equally.
Integrate historical daily snowfall using the operational target month's day
count, including leap February. This removes a calendar-length artifact when
historical February months contain a mixture of 28 and 29 days.

The candidate initialization years are 1982–2010. Around the archive's year
boundaries, require brackets entirely inside that archive, giving 28 candidate
years. A February 29 cycle maps halfway between February 28 and March 1 in
nonleap historical years, while retaining the original source cycle hour.
An upper bracket in the target month can use its explicitly verified 0–1 month
forecast mean; it contributes a daily reference rate, not a partial-month total.
Operational forecast decoding still requires its normal 1–9 month targets.

An explicit NOAA 404 excludes that entire historical year for the affected
target. At least 25 complete years are required. The bundle and published
target metadata record the exact included years and missing-source URLs.
Timeouts, changed fields, corrupt cache entries, missing brackets, and invalid
units stop the build; they never silently remove years or select another
reference. Monthly coverage can differ, and seasonal labels report the range
of complete years per month rather than implying complete historical winters.

## Workflow and cache

`build_cfsv2_snow_reference.py` accepts the actual selected anchor, rolling
window, monthly leads, and all seasonal windows. The same resolved targets
are passed to the generator. Both the scheduled suite and manual snowfall
entry points use this path. Other products retain their existing references.

The reference cache is separate from rolling forecast state and is saved after
every attempt. It retains checked NOAA source ranges, derived daily snowfall,
and exact-run bundles. Four workers reuse HTTP connections. Warm runs reuse
derived fields; they do not repeat the historical GRIB downloads/decoding.
Cold starts must populate the historical cache and take longer than normal
rolling updates. Missing-source responses are cached for one day; input caches
expire after 45 days and run bundles after 14 days to bound cache growth.

```bash
python scripts/build_cfsv2_snow_reference.py \
  --init 2026090506 --lead-months 3,4,5,6 \
  --seasonal-window '3,4,5;4,5,6' --rolling-days 6 \
  --cache .cache/cfsv2-snow-reference \
  --output .cache/cfsv2-snow-reference/bundles
```

The generator receives `--snowfall-reference-dir` instead of
`--ncei-calibration --allow-stale-calibration` for snowfall departures only.
If the builder fails, the workflow does not publish a substitute or relabel the
old calculation as corrected. Its previous successful publication remains.

## Verification

Tests cover calendar/year boundaries, leap February, allowed historical lead
zero, equal-year weighting, missing-year disclosure, fatal network failures,
cache reuse, correct workflow routing, and monthly/seasonal provenance.
The original reviewed March bundle remains readable for reproduction.
This adjustment fixes reference consistency; it does not establish forecast
skill or reduce the native snow-depth totals shown by the separate product.
