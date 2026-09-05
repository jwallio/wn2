# Limited snowfall reference correction

This describes the original March preview. Routine monthly/seasonal integration
is documented in [RUN_INTEGRATION.md](RUN_INTEGRATION.md).

The product remains a CFS model viewer. The completed implementation corrects
the historical reference calculation for the reviewed March departure map.
It does not fit a new forecast model or adjust native snowfall-depth totals.
The broader station/regional calibration expansion is stopped.

## What is corrected

The existing snowfall departure derives the historical reference from averaged
temperature and precipitation fields. The new reference derives snowfall for
each historical forecast first, matching the order used for the forecast.
It uses 348 historical forecasts, equal weighting of 29 winters, and same-hour
interpolation to the requested 24 cycle dates. Forecast values are unchanged.
This is a model-reference correction, not an observation-based bias adjustment;
the UI must not label it "historical bias adjusted snowfall totals."

The packaged reference covers **2026090506 / March 2027 only**, the original
reported monthly map. No DJF bundle or automatic rolling reference catalog is
provided. The loader rejects unsupported runs/months before downloads begin.
The scheduled production configuration remains unchanged. This is the agreed
nonproduction preview stage, not a claim of a live-site fix.

## Reproduce without new research or downloads

With the retained study and pilot outputs recovered:

```bash
python scripts/package_cfsv2_snow_reference.py \
  --study /path/to/winter-study/results \
  --pilot /path/to/winter-study/inputs/pilot \
  --output /path/to/reference-preview
```

This writes an exact-run JSON/NPZ reference bundle, a self-contained HTML
before/after preview, a PNG, and verification results. The generator's actual
loader and subtraction must reproduce the reviewed departure with zero error.
The numerical forecast remains unchanged. The existing-method map is a
reconstruction because the published anomaly has no downloadable numerical grid.

To use the bundle in a separately located generator preview (requires the
normal decoder and retained forecast cache):

```bash
python scripts/cfsv2_seasonal.py --product snowfall_anomaly \
  --init 2026090506 --lead-months 6 --rolling-days 6 --rolling-member 1 \
  --snowfall-reference-dir /path/to/reference-preview \
  --output-dir /path/to/private-render \
  --manifest /path/to/private-render/manifest.json
```

Do not add `--ncei-calibration`, a seasonal window, partial rolling, or stale
fallback to this command. References are exclusive and must cover every requested
month. The loader verifies checksum, units, cycle list, target, initialization,
method, years, and grid compatibility. Decoder coordinate rounding up to 1e-5
degrees is accepted without regridding or changing reference values.

The manual research workflow packages the preview as an artifact. It does not
publish to Pages. Its dated forecast inputs still require retained cache after
NOMADS rotates them out.

## Why snowfall totals are left alone

Native snowfall accumulation and phase-derived snowfall departure are distinct
products. The historical phase reference cannot calibrate native accumulation.
The 15-station observational study mostly improved raw errors, but cannot supply
a defensible nationwide factor. No city-specific fitting, national multiplier,
new station expansion, or climatology skill gate is added. Native totals remain
labeled as unadjusted estimates using the existing CIPS snow-to-liquid ratios.

## Validation

- The packaged March reference reproduces the reviewed departure exactly
  (maximum absolute error 0.0 inches water equivalent).
- Ten new tests exercise application, input rejection, checksum, grid alignment,
  preflight ordering, baseline exclusivity, default behavior, and provenance.
- Twenty existing research tests and all 28 repository contract scripts pass.
- The actual generator, quality control, renderer, and manifest path pass with
  the previously verified cached forecast grid injected at the decoder boundary.
  This rendering check does not claim a fresh NOMADS download/decoder run.
- The before/after preview uses the same scale and labels water-equivalent units.

Later live adoption needs an explicit decision about coverage: this one reviewed
reference must not silently become a default for other months or runs. That
limitation is visible in the preview and enforced by the loader.
