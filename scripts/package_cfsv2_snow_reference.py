"""Package the reviewed March reference and a standalone before/after preview.

No downloads, fitting, operational manifests, or publication. The reviewed
scope is intentionally explicit; this does not reuse March at other leads.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

import numpy as np

import cfsv2_seasonal as cf
from cfsv2_snow_reference import METHOD, load_reference, match_forecast_grid


def main(args):
    study, pilot, out = map(Path, (args.study, args.pilot, args.output))
    report = json.loads((study / 'interpolated-reference.json').read_text())
    forecast_report = json.loads((pilot / 'report.json').read_text())
    init, target = '2026090506', '202703'
    if (report['anchor'] != init or report['target'] != target
            or report['historical_years'] != list(range(1982, 2011))
            or report['historical_cycles'] != 348
            or report['requested_reference_cycles_per_year'] != 24
            or forecast_report['anchor'] != init or forecast_report['target'] != target
            or forecast_report['operational_cycles'] != 24):
        raise ValueError('Inputs are outside the reviewed March/September-5 scope')
    with np.load(study / 'interpolated-reference.npz', allow_pickle=False) as z:
        grids = {k: z[k].copy() for k in z.files}
    with np.load(pilot / 'pilot-grids.npz', allow_pickle=False) as z:
        forecast = cf.Grid(z['lons'].tolist(), z['lats'].tolist(), z['forecast'].tolist())
        old = z['published_method_departure'].copy()
    if not np.array_equal(grids['initialization_years'], np.arange(1982, 2011)):
        raise ValueError('Historical years do not match the reviewed study')
    if not np.array_equal(grids['reference'], grids['annual_reference'].mean(axis=0)):
        raise ValueError('Reference differs from the equal-winter mean')
    if not np.array_equal(old, grids['existing_departure']):
        raise ValueError('Existing-method replay differs from the reviewed study')
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f'snowfall-reference-{init}-{target}'
    np.savez_compressed(stem.with_suffix('.npz'), **{k: grids[k] for k in ('lons', 'lats', 'reference')})
    cycles = cf.rolling_cycle_inits(init, 24)
    meta = dict(schema_version=1, method=METHOD, initialization=init,
                target_month=target, forecast_cycles=cycles, member=1,
                units='inches_water_equivalent', historical_years=list(range(1982, 2011)),
                historical_cycles=348, grid_sha256=hashlib.sha256(stem.with_suffix('.npz').read_bytes()).hexdigest(),
                study_sha256=hashlib.sha256((study / 'interpolated-reference.json').read_bytes()).hexdigest(),
                source_records=report['source_records'])
    stem.with_suffix('.json').write_text(json.dumps(meta, indent=2) + '\n')
    reference, provenance = load_reference(out, init, target, cycles, 1)
    reference = match_forecast_grid(reference, forecast)
    corrected = np.array(cf.subtract_grids(forecast, reference).values)
    if not np.array_equal(corrected, grids['departure']):
        raise ValueError('Production reference loader does not reproduce the reviewed departure')
    result = dict(initialization=init, target_month=target,
                  reference_loader_replay_max_error_inches=float(np.max(np.abs(corrected - grids['departure']))),
                  forecast_changed=False, native_accumulation_changed=False,
                  observation_bias_adjustment=False, points=report['points'], provenance=provenance)
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    preview(out, grids['lons'], grids['lats'], old, corrected, report['points'])
    print(json.dumps({k: v for k, v in result.items() if k not in ('points', 'provenance')}, indent=2))


def preview(out, lons, lats, old, corrected, points):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from cfsv2_reference_review import conus_mask

    with np.load(Path(__file__).with_name('data') / 'cfsv2_cwa_slr_v1.npz') as data:
        borders, offsets = data['states_points'], data['states_offsets']
    mask = conus_mask(lons, lats, borders, offsets)
    fig, axes = plt.subplots(2, 1, figsize=(11, 9), layout='constrained')
    levels = [-2, -1.5, -1, -.75, -.5, -.25, 0, .25, .5, .75, 1, 1.5, 2]
    for ax, values, title in zip(axes, (old, corrected),
            ('Existing reference (reconstructed)', 'Corrected reference calculation')):
        image = ax.contourf(lons, lats, np.ma.masked_where(~mask, values),
                            levels=levels, cmap='RdBu', extend='both')
        for a, b in zip(offsets[:-1], offsets[1:]):
            ax.plot(borders[a:b, 0], borders[a:b, 1], color='#354451', linewidth=.4)
        ax.set(xlim=(-125, -66), ylim=(24, 50), title=title)
        ax.set_aspect(1.25)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(image, ax=axes, orientation='horizontal', shrink=.85, ticks=levels,
                 label='Snowfall departure · inches of water equivalent · blue = above reference')
    fig.suptitle('CFSv2 · March 2027\nSeptember 5, 2026 06Z · 24-cycle mean', weight='bold')
    fig.supxlabel('Preview · Same CFS forecast in both panels; only the historical reference changes.', fontsize=10)
    path = out / 'cfsv2-snowfall-reference-preview.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    rows = ''.join(f'<tr><th>{p["location"]}</th><td>{p["existing"]:+.3f}</td>'
                   f'<td>{p["interpolated_candidate"]:+.3f}</td></tr>' for p in points)
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFSv2 snowfall reference preview</title>
<style>body{margin:24px auto;padding:0 16px;max-width:960px;font:17px/1.5 system-ui;color:#172e41;background:#f7fafc}
img{width:100%;height:auto;background:white}h1{font-size:clamp(24px,5vw,36px)}
table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px;border-bottom:1px solid #d5dfe7;text-align:right}th:first-child{text-align:left}
.tag{color:#466782;font-size:14px}summary{cursor:pointer;font-weight:600}details{margin:24px 0}</style>
<p class="tag">wall.cloud · CFSv2 · Nonproduction preview</p>
<h1>The same CFS snowfall forecast, with a consistent historical reference</h1>
<p>March 2027 · September 5, 2026 06Z · 24-cycle mean.</p>
<p>The correction calculates snowfall for each historical forecast before averaging.
It changes the departure from the model’s historical reference. It does not change CFS snowfall totals.</p>
<img alt="Existing and corrected CFSv2 March 2027 snowfall departure maps, with the same color scale" src="data:image/png;base64,IMAGE">
<p><strong>These values are water equivalent, not inches of snow depth.</strong></p>
<table><thead><tr><th>Location</th><th>Existing</th><th>Corrected</th></tr></thead><tbody>ROWS</tbody></table>
<details><summary>What changed?</summary><p>The previous reference estimated snowfall from average temperatures and precipitation.
Because the snow-phase calculation is nonlinear, that differs from averaging snowfall calculated for individual forecasts.</p>
<p>The new reference uses 348 historical forecasts across 1982–2010. Same-hour interpolation matches the historical reference to the 24 forecast cycle dates. This interpolation estimates the reference; it does not create additional historical forecasts.</p>
<p>The upper map reconstructs the existing calculation. The site does not publish its anomaly grid for a direct numerical comparison.
Monthly-temperature snow phase remains an approximation. This is a model-reference correction, not an observation-based bias correction or a new forecasting model.</p>
<p>This reviewed reference applies only to March 2027 at the displayed initialization. Other months and runs cannot use it. Native snowfall accumulation remains unadjusted.</p></details>
</html>'''.replace('IMAGE', encoded).replace('ROWS', rows)
    (out / 'cfsv2-snowfall-reference-preview.html').write_text(html, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True)
    parser.add_argument('--pilot', required=True)
    parser.add_argument('--output', required=True)
    main(parser.parse_args())
