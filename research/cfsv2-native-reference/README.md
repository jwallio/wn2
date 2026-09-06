# Native CFSv2 snowfall departures

The operational departure now pairs native SRWEQ forecasts with native SRWEQ
from archived operational seasonal forecasts. It no longer partitions monthly
precipitation using monthly mean temperature.

## Source verification

Native GRIB2 discipline 0/category 1/parameter 12, surface, kg m-2 s-1 was
verified in operational archives from 2011 onward. Sampled full reforecast
and calibration files lacked this field. Snowpack depth and SWE are not used
as snowfall substitutes.

Archive roots:
- https://www.ncei.noaa.gov/oa/prod-cfs-operational-forecast/monthly-means/
- https://noaa-cfs-pds.s3.amazonaws.com/

The explicit reference is 2011-2025 archived operational forecasts. It is a
15-year model reference, not a 30-year observed normal or the 1982-2010
reforecast reference. Operational model/assimilation changes and the short
reference period remain limitations. No observation-based bias adjustment is
applied, and large native model departures can remain after this repair.

For each current cycle, historical inputs match calendar date and cycle hour.
Each complete year receives equal weight, and all requested valid months use
the same complete years. Leap-day mapping uses same-hour February 28/March 1
brackets. The native monthly mean rate is normalized to inches LWE per day,
then integrated using the current target month's calendar length. Subtract
forecast minus reference in LWE; multiply by 10 once at display/export.

## September 6 2026 06Z replay

All 15 historical years were complete for Dec-Mar: 1,440 source grids,
360 forecasts per target month. Reference checksums, source identities,
calendar leads, grids and equal-year averaging are validated by the loader.
JFM equals the sum of Jan-Mar departures and cannot exceed its native
forecast total because its reference is nonnegative. Point values at nearest
model grid cells are in `verification.json`.

The native repair changes the spatial pattern; it does not guarantee smaller
values. At Oklahoma City, the JFM native forecast is approximately 48.71 inches,
the native model reference 25.89 inches, and the departure +22.82 inches.
These are model estimates at fixed 10:1, not an observed snowfall prediction
with demonstrated local skill.

Rebuild a reference:

```sh
python scripts/cfsv2_native_reference.py --init 2026090606 \
  --lead-months 3,4,5,6 --seasonal-window '3,4,5;4,5,6' \
  --cache .cache/cfsv2-snow-reference \
  --output .cache/cfsv2-snow-reference/bundles
```

The routine workflow supplies `--native-snowfall-departure` and the exact
reference directory to the renderer. Legacy derived reference code remains
available for reproduction of older outputs, but the production workflow
uses the native branch. Existing products remain visible until replaced.
