"""Repair retained CFSv2 departures using their paired, published native totals."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urljoin
import requests
import cfsv2_seasonal as cf
import cfsv2_native_reference as reference
from cfsv2_snow_reference import match_forecast_grid


def refresh(manifest, site_url, cache, bundles, border_paths, output_root=None):
    document = json.loads(manifest.read_text())
    totals = {r['init_utc']: r for r in document['runs'] if r['product'] == 'snowfall_accumulation'}
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[1]
    count = 0
    for run in document['runs']:
        if run['product'] != 'snowfall_anomaly' or run.get('raw_field') == 'SRWEQ:surface':
            continue
        pair = totals.get(run['init_utc'])
        if pair is None:
            print(f"Retained {run['id']}: no paired native total; preserving original", flush=True)
            continue
        init = run['init_utc'].replace('-', '').replace(':', '').replace('T', '')[:10]
        native_targets = {t['target_month']: t for t in pair['targets'] if t.get('native_lwe_grid')}
        months = sorted(t['target_month'] for t in run['targets'] if '-' not in t['target_month'] and t.get('image'))
        if not months or any(m not in native_targets for m in months):
            raise ValueError(f'Retained native inputs incomplete for {init}')
        cycles = cf.rolling_cycle_inits(init, run['ensemble_members'])
        reference.build(init, months, cycles, cache, bundles, workers=8)
        forecasts, baselines, anomalies, metadata = {}, {}, {}, {}
        for month in months:
            target = native_targets[month]
            path = str(target['native_lwe_grid']).removeprefix('public/seasonal/')
            local = cache / 'retained-inputs' / path
            local.parent.mkdir(parents=True, exist_ok=True)
            if not local.exists():
                response = requests.get(urljoin(site_url.rstrip('/')+'/', path), timeout=(10, 60))
                response.raise_for_status()
                local.write_bytes(response.content)
            forecast = cf.read_grid_state(local)
            baseline, info = reference.load_reference(bundles, init, month, cycles, 1)
            baseline = match_forecast_grid(baseline, forecast)
            forecasts[month], baselines[month], metadata[month] = forecast, baseline, info
            anomalies[month] = cf.subtract_grids(forecast, baseline)
        for target in run['targets']:
            if not target.get('image'):
                continue
            period = target['target_month']
            selected = [m for m in months if period.split('-')[0] <= m <= period.split('-')[-1]]
            if not selected:
                raise ValueError('Retained snowfall target has no matching native months')
            anomaly = cf.sum_grids([anomalies[m] for m in selected])
            info = metadata[selected[0]] if len(selected) == 1 else cf.seasonal_baseline_manifest([metadata[m] for m in selected], '', None, rolling_init=init)
            spec = dict(cf.get_product_spec('snowfall_anomaly'), raw_field='SRWEQ:surface', raw_units='kg m-2 s-1',
                        snowfall_input_kind='Native snowfall · 2011–2025 operational reference')
            out = root / target['image']
            out.parent.mkdir(parents=True, exist_ok=True)
            cf.render_map(anomaly, init, selected[0], target['lead_month'], [1], out, True, info['label'], border_paths,
                          period_label=target.get('label', ''), seasonal=len(selected)>1,
                          ensemble_label=f"{len(cycles)}/{len(cycles)}-cycle rolling mean", product_spec=spec)
            numerical = out.with_suffix('.csv.gz')
            cf.write_grid_state(anomaly, numerical)
            target.update(raw_field='SRWEQ:surface', raw_units='kg m-2 s-1', baseline=info,
                          derivation={'method':'native_SRWEQ_departure_v1','native_departure_status':'available'},
                          numeric_grid=str(numerical.relative_to(root)), numeric_grid_format='csv.gz',
                          source_files=[deepcopy(s) for m in selected for s in native_targets[m].get('source_files', [])],
                          quality_control=cf.grid_quality_control('snowfall_anomaly', anomaly.values, units='in', field='snowfall_lwe', seasonal=len(selected)>1))
            cf.require_quality_control(target['quality_control'], ValueError)
            count += 1
        run.update(raw_field='SRWEQ:surface', raw_units='kg m-2 s-1', source_kind='FLXF',
                   baseline=cf.seasonal_baseline_manifest(list(metadata.values()), '', None, rolling_init=init))
        print(f"Repaired retained native departures: {init}", flush=True)
    manifest.write_text(json.dumps(document, indent=2))
    print(f'Repaired {count} retained snowfall departure maps', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--site-url', required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--reference-dir', type=Path, required=True)
    a = p.parse_args()
    args = argparse.Namespace(border_geojson=[], no_borders=False)
    borders = cf.ensure_border_files(args, a.cache, Path(__file__).resolve().parents[1])
    refresh(a.manifest, a.site_url, a.cache, a.reference_dir, borders)
