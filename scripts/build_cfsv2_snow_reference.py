"""Cached model-only snowfall reference builder for routine CFSv2 runs."""
import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

import numpy as np
import requests
import cfsv2_seasonal as cf
import cfsv2_march_pilot as source
from cfsv2_snow_reference import NORMALIZED_METHOD, load_reference, reference_years


def historical_time(cycle, year, anchor_year):
    moment = datetime.strptime(cycle, '%Y%m%d%H')
    mapped_year = year + moment.year - anchor_year
    try:
        return moment.replace(year=mapped_year)
    except ValueError:
        # Feb29 maps halfway between Feb28 and Mar1 in nonleap years.
        # Source interpolation still selects the original cycle hour.
        return moment.replace(year=mapped_year, day=28) + timedelta(hours=12)


def available_dates(month, cache):
    prefix = f'high-priority-subset/monthly-means-9-month/{month[:4]}/{month}/'
    url = requests.Request('GET', source.ARCHIVE, params={
        'list-type': 2, 'delimiter': '/', 'prefix': prefix}).prepare().url
    data, _ = source.fetch(url, cache)
    root = ET.fromstring(data)
    if any(x.text == 'true' for x in root.iter() if x.tag.endswith('IsTruncated')):
        raise ValueError(f'Truncated historical listing: {month}')
    return sorted({x.text.rstrip('/').split('/')[-1] for x in root.iter()
                   if x.tag.endswith('Prefix') and x.text and re.search(r'/\d{8}/$', x.text)})


def weights_for_time(moment, hour, dates):
    candidates = sorted(datetime.strptime(d + hour, '%Y%m%d%H') for d in dates)
    before, after = [d for d in candidates if d <= moment], [d for d in candidates if d >= moment]
    if not before or not after:
        raise ValueError(f'No historical bracket for {moment} at {hour}Z')
    lo, hi = before[-1], after[0]
    if lo == hi:
        return {lo.strftime('%Y%m%d%H'): 1.}
    leap_gap = (hi - lo == timedelta(days=6) and calendar.isleap(lo.year)
                and lo.month == 2 and hi.month == 3)
    if hi - lo > timedelta(days=5) and not leap_gap:
        raise ValueError('Historical bracket exceeds five days')
    fraction = (moment - lo).total_seconds() / (hi - lo).total_seconds()
    return {lo.strftime('%Y%m%d%H'): 1 - fraction, hi.strftime('%Y%m%d%H'): fraction}


def plan_year(year, init, cycles, cache):
    moments = [historical_time(c, year, int(init[:4])) for c in cycles]
    day, end = min(moments) - timedelta(days=5), max(moments) + timedelta(days=5)
    months = set()
    while day <= end + timedelta(days=1):
        months.add(day.strftime('%Y%m'))
        day += timedelta(days=1)
    dates = sorted({d for month in sorted(months) for d in available_dates(month, cache)})
    weights = {}
    for cycle, moment in zip(cycles, moments):
        for init, weight in weights_for_time(moment, cycle[-2:], dates).items():
            weights[init] = weights.get(init, 0.) + weight / len(cycles)
    if not np.isclose(sum(weights.values()), 1.):
        raise ValueError('Reference weights do not sum to one')
    return year, weights


class MissingHistoricalCycle(ValueError):
    """An explicit HTTP 404 from the historical NOAA archive."""


def cached_sample(init, target, cache):
    directory = cache / 'derived-v2'
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / f'{init}-{target}'
    path, sidecar = stem.with_suffix('.npz'), stem.with_suffix('.json')
    missing = stem.with_suffix('.missing.json')
    if missing.exists() and time.time() - missing.stat().st_mtime < 86400:
        record = json.loads(missing.read_text())
        if record.get('init') == init and record.get('target') == target and record.get('status') == 404:
            raise MissingHistoricalCycle(record['url'])
    if path.exists() and sidecar.exists():
        meta = json.loads(sidecar.read_text())
        if (meta.get('method') != NORMALIZED_METHOD or meta.get('init') != init
                or meta.get('target') != target
                or hashlib.sha256(path.read_bytes()).hexdigest() != meta.get('sha256')):
            raise ValueError(f'Invalid derived cache: {stem.name}')
        with np.load(path, allow_pickle=False) as data:
            result = {k: data[k].copy() for k in ('lons', 'lats', 'snow_per_day')}
        result['sources'] = meta['sources']
        return result
    try:
        sample = source.cycle(init, target, cache / 'sources', historical=True, allow_lead_zero=True)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        source.atomic_write(missing, json.dumps(dict(init=init, target=target, status=404, url=exc.response.url)).encode())
        raise MissingHistoricalCycle(exc.response.url) from exc

    days = calendar.monthrange(int(target[:4]), int(target[4:]))[1]
    result = dict(lons=sample['lons'], lats=sample['lats'], snow_per_day=sample['snow'] / days)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **result)
    source.atomic_write(path, buffer.getvalue())
    source.atomic_write(sidecar, (json.dumps(dict(method=NORMALIZED_METHOD, init=init, target=target,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), sources=sample['sources'])) + '\n').encode())
    result['sources'] = sample['sources']
    return result


def build_target(init, target, cycles, plans, cache, output, workers):
    try:
        load_reference(output, init, target, cycles, 1)
        print(f'Using complete reference: {init} -> {target}', flush=True)
        return
    except cf.CFSv2Error:
        pass  # Rebuild from verified historical inputs; never substitute a reference.
    offset = int(target[:4]) - int(init[:4])
    days = calendar.monthrange(int(target[:4]), int(target[4:]))[1]
    annual, records, axes = [], [], None
    complete_plans, excluded = [], []
    pool = ThreadPoolExecutor(max_workers=workers)
    pending = {year: [pool.submit(cached_sample, i, f'{year + offset:04d}{target[4:]}', cache)
                      for i in sorted(weights)] for year, weights in plans}
    try:
        for year, weights in plans:
            historical_target = f'{year + offset:04d}{target[4:]}'
            inits = sorted(weights)
            samples, missing = [], []
            for future in pending.pop(year):
                try:
                    samples.append(future.result())
                except MissingHistoricalCycle as exc:
                    missing.append(str(exc))
            if missing:
                excluded.append(dict(year=year, reason='source_http_404', urls=missing))
                print(f'Reference {target}: excluding incomplete historical year {year}', flush=True)
                continue
            complete_plans.append((year, weights))
            for s in samples:
                if axes is None:
                    axes = s['lons'], s['lats']
                if (not np.array_equal(s['lons'], axes[0]) or not np.array_equal(s['lats'], axes[1])
                        or s['snow_per_day'].shape != (len(axes[1]), len(axes[0]))
                        or not np.isfinite(s['snow_per_day']).all() or s['snow_per_day'].min() < 0):
                    raise ValueError('Incomplete or incompatible historical snowfall grid')
            annual.append(sum(s['snow_per_day'] * weights[i] * days for i, s in zip(inits, samples)))
            records.extend(dict(init=i, target=historical_target, sources=s['sources']) for i, s in zip(inits, samples))
            print(f'Reference {target}: historical year {year} complete', flush=True)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    if len(complete_plans) < 25:
        raise ValueError(f'Only {len(complete_plans)} complete historical years for {target}; need at least 25')
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f'snowfall-reference-{init}-{target}'
    buffer = io.BytesIO()
    np.savez_compressed(buffer, lons=axes[0], lats=axes[1], reference=np.mean(annual, axis=0))
    source.atomic_write(stem.with_suffix('.npz'), buffer.getvalue())
    meta = dict(schema_version=1, method=NORMALIZED_METHOD, initialization=init,
        target_month=target, forecast_cycles=cycles, member=1, units='inches_water_equivalent',
        historical_years=[y for y, _ in complete_plans], historical_cycles=len(records),
        candidate_years=[y for y, _ in plans], excluded_years=excluded,
        grid_sha256=hashlib.sha256(stem.with_suffix('.npz').read_bytes()).hexdigest(),
        target_calendar_days=days, annual_weights=[dict(year=y, weights=w) for y, w in complete_plans],
        source_records=records, leap_day_policy='nonleap Feb29 interpolated between Feb28 and Mar1',
        accumulation_policy='historical daily snowfall multiplied by operational target calendar days')
    source.atomic_write(stem.with_suffix('.json'), (json.dumps(meta, indent=2) + '\n').encode())
    load_reference(output, init, target, cycles, 1)
    print(f'Built reference: {init} -> {target} ({len(records)} historical forecasts)', flush=True)


def main(args):
    init = cf.parse_init(args.init)
    if not 1 <= args.rolling_days <= 6 or not 1 <= args.workers <= 4:
        raise ValueError('Use 1-6 rolling days and 1-4 workers')
    cycles = cf.rolling_cycle_inits(init, args.rolling_days * 4)
    leads = set(cf.parse_int_list(args.lead_months, 'lead months', 1, 9))
    for window in cf.parse_seasonal_windows(args.seasonal_window):
        leads.update(window)
    cache, output = Path(args.cache), Path(args.output)
    # A rolling window only needs nearby initialization dates. Bound cache
    # growth while retaining enough history for repairs and repeated runs.
    now = time.time()
    for directory, days in ((cache / 'sources', 45), (cache / 'derived-v2', 45), (output, 14)):
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and now - path.stat().st_mtime > days * 86400:
                    path.unlink()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        plans = list(pool.map(lambda y: plan_year(y, init, cycles, cache / 'sources'), reference_years(cycles)))
    for lead in sorted(leads):
        build_target(init, cf.target_month(init, lead), cycles, plans, cache, output, args.workers)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init', required=True)
    parser.add_argument('--lead-months', required=True)
    parser.add_argument('--seasonal-window', default='')
    parser.add_argument('--rolling-days', type=int, default=6)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--output', required=True)
    main(parser.parse_args())
