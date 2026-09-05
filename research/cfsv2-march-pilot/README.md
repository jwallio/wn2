# March 2027 calibration pilot

Research only. This branch does not change a production generator, model
manifest, published numerical grid, or Pages deployment. The added manual
workflow is not on the publisher's workflow allowlist and has read-only
repository permissions. Its definition must be available on the default
branch before GitHub exposes its manual dispatch control.

## Scope

Source baseline: `0ce7f14827885cb33f44e4ec1636a12feacba311`.
Operational target: March 2027, anchored September 5, 2026 06Z, with the exact
24 initializations from August 30 12Z through September 5 06Z.

There are two different products:

- Departure: precipitation times a nonlinear monthly-temperature snow-phase
  approximation, less the same approximation applied to smoothed NCEI mean
  temperature/precipitation fields. Units are inches of water equivalent.
- Accumulation: native SRWEQ rate integrated over the calendar month, times
  the existing CIPS regional snow-to-liquid ratio. Units are snow-depth inches.
  The departure product is not a compatible reference for this native product.

## Archive recovery

The old NCEI HTTPS directories now contain migration notices, while old THREDDS
requests timed out during this audit. Following NOAA's notice recovered:

- https://www.ncei.noaa.gov/oa/prod-cfs-reforecast/index.html
- https://www.ncei.noaa.gov/oa/prod-cfs-operational-forecast/index.html

The pilot uses the official object listing API at those same origins. It reads
the provider's `.inv`/`.idx` inventories and verifies exact HTTP byte ranges,
GRIB variable identifiers, units, surface/pressure levels, initialization and
calendar lead. Source bytes are cached with SHA-256 and retrieval provenance.
It never substitutes standing snowpack or snow phase-change heat flux for
falling snow. The inspected smoothed flux calibration contains 96 fields but
no native snowfall-rate record. The newer operational archive supplies SRWEQ.

## Departure experiment

`cfsv2_march_pilot.py` discovers the available September initialization date
inside the operational window for each year 1982–2010, uses all four cycles,
and verifies complete temperature/precipitation dependencies. Historical valid
March months therefore run from 1983 through 2011.

1. Compute each historical forecast's phase-derived snowfall.
2. Average cycles within each winter, then average winters with equal weight.
3. Subtract that reference from the operational phase-derived forecast.
4. Separately derive a reference from the mean inputs of **the identical
   historical samples**, isolating the nonlinear operation-order effect.

`cfsv2_march_compare.py` reconstructs the existing smoothed-NCEI method for a
separate comparison. Differences from that method include historical sampling
and smoothing as well as operation order. The control must not be called the
published baseline. The independent native replay is also checked against the
published numeric grid for the exact same cycle window.

The historical window contains four September cycles; the operational window
contains six August lead-7 cycles and eighteen September lead-6 cycles. This
sampling/lead mixture still needs a sensitivity experiment before promotion.
The experiment fixes calculation order, not the limitations of inferring snow
from monthly mean temperatures, nor observational bias or predictive skill.

## Native totals screen

`cfsv2_native_bias_screen.py` independently decodes September 5 06Z operational
forecasts initialized in 2011–2023, targeting March 2012–2024. It uses the same
native field, calendar integration, and existing regional ratio as production.
Daily ACIS snowfall for KRDU, KAVL, KOKC, KORD and KBOS is matched using each
station's returned coordinates. A March total requires all 31 days; traces
count as zero, and missing days exclude the month.

A simple multiplicative correction is fitted on initialization years
2011–2018 and evaluated on 2019–2023. A training-observation-mean forecast is
the comparison baseline. Because the late-period split is disproportionately
low-snow, a separate leave-one-winter-out diagnostic includes snowy winters and
reports measurable-snow and zero/trace groups. It uses other earlier and later
winters, so is not a chronological forecasting simulation.

This is a five-station, single-cycle screen. Its coefficients are not suitable
for the 24-cycle CONUS product and are never applied to the live maps.

## Reproduce without a personal computer

Use a cloud Python 3.11 environment, or the isolated manual GitHub workflow
after its definition is merged. The workflow writes research artifacts only.

```bash
python -m pip install -r research/cfsv2-march-pilot/requirements.txt
python -m unittest discover -s research/cfsv2-march-pilot -p test_reference.py
python scripts/cfsv2_march_pilot.py --cache .cache/cfsv2-march-pilot --output research-output
python scripts/cfsv2_march_compare.py --cache .cache/cfsv2-march-pilot --pilot research-output
python scripts/plot_cfsv2_march_pilot.py research-output
python scripts/cfsv2_native_bias_screen.py --cache .cache/cfsv2-march-pilot --output research-output/native-bias-screen.json
```

The dated NOMADS files rotate after seven days. Preserve the supplied cache
bundle for later reproduction; missing files must stop the replay rather than
silently selecting a newer initialization. The workflow preserves its own
source cache after failed attempts, but a fresh runner needs the retained
dated input cache once NOMADS rotates.

## Publication requirements still outstanding

- Match/sensitivity-test the August/September initialization mixture and full
  operational rolling ensemble before adopting a replacement reference.
- Expand observed snowfall coverage and fit/test the **24-cycle** native
  product, including snowy and low-snow winters and spatial uncertainty.
- Require usefulness relative to observed climatology, not merely smaller
  errors than the unadjusted model or a zero-mean in-sample anomaly.
- Only then create a new versioned reference, integrate production lookup and
  missing-reference handling, and validate all monthly/seasonal products.

No all-CONUS numerical correction, production deployment, or full scientific
validation is claimed by this pilot.
