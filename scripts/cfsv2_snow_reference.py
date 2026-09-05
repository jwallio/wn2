"""Load an explicitly supplied, model-only snowfall departure reference.

This adjusts the reference calculation, never native snowfall accumulation.
There is deliberately no nearest-date or alternate-month fallback.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

METHOD = "derive_each_forecast_then_same_hour_interpolate_v1"
LABEL = "1982–2010 CFS reforecasts · snowfall derived before averaging"


def match_forecast_grid(reference, forecast):
    """Allow decoder coordinate rounding, never spatial interpolation."""
    from cfsv2_seasonal import CFSv2Error, Grid
    if (np.shape(reference.values) != np.shape(forecast.values)
            or not np.allclose(reference.lons, forecast.lons, rtol=0, atol=1e-5)
            or not np.allclose(reference.lats, forecast.lats, rtol=0, atol=1e-5)):
        raise CFSv2Error('Snowfall reference grid does not match the forecast grid')
    return Grid(forecast.lons[:], forecast.lats[:], reference.values)


def load_reference(directory, init, target, cycles, member):
    from cfsv2_seasonal import CFSv2Error, Grid

    stem = Path(directory) / f"snowfall-reference-{init}-{target}"
    try:
        meta = json.loads(stem.with_suffix('.json').read_text(encoding='utf-8'))
        expected = dict(schema_version=1, method=METHOD, initialization=init,
                        target_month=target, forecast_cycles=list(cycles),
                        member=member, units='inches_water_equivalent',
                        historical_years=list(range(1982, 2011)), historical_cycles=348)
        for key, value in expected.items():
            if meta.get(key) != value:
                raise ValueError(f"Reference {key} does not match the requested forecast")
        if not cycles or len(set(cycles)) != len(cycles):
            raise ValueError('Reference requires an explicit, unique cycle window')
        path = stem.with_suffix('.npz')
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['grid_sha256']:
            raise ValueError('Reference grid checksum mismatch')
        with np.load(path, allow_pickle=False) as data:
            lons, lats, values = (data[k].copy() for k in ('lons', 'lats', 'reference'))
        if (lons.ndim != 1 or lats.ndim != 1 or min(len(lons), len(lats)) < 2
                or values.shape != (len(lats), len(lons))
                or not all(np.isfinite(a).all() for a in (lons, lats, values))
                or not (np.diff(lons) > 0).all() or not (np.diff(lats) > 0).all()
                or lons.min() < -180 or lons.max() > 180
                or lats.min() < -90 or lats.max() > 90 or values.min() < 0):
            raise ValueError('Invalid snowfall reference grid')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CFSv2Error(f'Cannot use snowfall reference {stem.name}: {exc}') from exc
    return Grid(lons.tolist(), lats.tolist(), values.tolist()), {
        'source': 'NCEI CFS reforecasts; model-only snowfall reference',
        'label': LABEL, 'years': '1982-2010', 'required': True, 'status': 'applied',
        'file': str(path), 'grid_sha256': meta['grid_sha256'],
        'method': METHOD, 'rolling_policy': 'reference_matched_to_each_forecast_cycle',
        'anchor_init': init, 'target_month': target, 'forecast_cycles': list(cycles),
        'historical_cycles': meta['historical_cycles'],
        'reference_interpolation': 'same hour; bracket gap at most five days; no extrapolation',
        'observation_bias_adjustment': False,
    }


def validate_options(args, product, init, targets, repo_root):
    """Preflight every requested month before any downloads or rendering."""
    from cfsv2_seasonal import CFSv2Error, rolling_cycle_inits, resolve_repo_path

    directory = getattr(args, 'snowfall_reference_dir', None)
    if not directory:
        return
    if (product != 'snowfall_anomaly' or args.absolute or args.decode_only
            or args.rolling_days != 6 or args.rolling_member != 1
            or args.allow_partial_rolling or args.allow_stale_calibration
            or args.baseline_label or args.baseline_years):
        raise CFSv2Error('An explicit snowfall reference requires snowfall_anomaly, '
                         'the complete six-day member-1 window, and its own reference labels')
    directory = resolve_repo_path(directory, repo_root)
    for target in targets:
        load_reference(directory, init, target, rolling_cycle_inits(init, 24), 1)
