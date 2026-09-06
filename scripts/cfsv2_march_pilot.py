"""Research-only March calibration audit. Never writes operational manifests.

Use research/cfsv2-march-pilot/README.md for scope and reproduction.
ecCodes is an isolated research dependency, not a production decoder change.
"""
import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import threading
import tempfile
import xml.etree.ElementTree as ET

import eccodes as ec
import numpy as np
import requests
import cfsv2_seasonal as cf

ARCHIVE = 'https://www.ncei.noaa.gov/oa/prod-cfs-reforecast/'
NOMADS = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/cfs/prod/'
FIELDS = {'t2m': ('TMP:2 m above ground', 0, 0, 'heightAboveGround', 2, 'K'),
          't850': ('TMP:850 mb', 0, 0, 'isobaricInhPa', 850, 'K'),
          'precip': ('PRATE:surface', 1, 7, 'surface', 0, 'kg m**-2 s**-1'),
          'native': ('SRWEQ:surface', 1, 12, 'surface', 0, 'kg m**-2 s**-1')}
POINTS = [('Raleigh', 35.78, -78.64), ('Asheville', 35.60, -82.55),
          ('Oklahoma City', 35.47, -97.52), ('Denton TX', 33.21, -97.13),
          ('Chicago', 41.88, -87.63), ('Boston', 42.36, -71.06)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


_http_state = threading.local()


def http_session():
    # Reuse NOAA connections within each worker across inventories and ranges.
    if not hasattr(_http_state, 'session'):
        _http_state.session = requests.Session()
    return _http_state.session


def atomic_write(path, data):
    """Publish complete cache files even when a workflow is interrupted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch(url, cache, start=None, end=None, limit=2_000_000):
    """Bounded range reads, with URL/range/content-hash checked caching."""
    key = sha(f'{url}|{start}|{end}'.encode())
    path = cache / key
    sidecar = cache / (key + '.json')
    if path.exists() and sidecar.exists():
        data = path.read_bytes()
        meta = json.loads(sidecar.read_text())
        if (meta['sha256'] != sha(data) or len(data) > limit or meta['url'] != url or
            meta['start'] != start or meta['end'] != end or meta['bytes'] != len(data)):
            raise ValueError('Invalid cached source')
        return data, meta
    headers = {} if start is None else {'Range': f'bytes={start}-{end if end is not None else ""}'}
    for attempt in range(3):
        try:
            with http_session().get(url, headers=headers, stream=True, timeout=(10, 30)) as r:
                r.raise_for_status()
                chunks = bytearray()
                for chunk in r.iter_content(65536):
                    chunks.extend(chunk)
                    if len(chunks) > limit:
                        raise ValueError('Source exceeds bounded download limit')
                data = bytes(chunks)
                if start is not None:
                    m = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', r.headers.get('Content-Range', ''))
                    if (r.status_code != 206 or not m or int(m[1]) != start or
                        int(m[2]) - start + 1 != len(data) or
                        (end is not None and int(m[2]) != end)):
                        raise ValueError('Server did not return the exact requested range')
                meta = dict(url=url, start=start, end=end, sha256=sha(data), bytes=len(data),
                            retrieved_utc=datetime.now(timezone.utc).isoformat())
                cache.mkdir(parents=True, exist_ok=True)
                atomic_write(path, data)
                atomic_write(sidecar, json.dumps(meta, indent=2).encode())
                return data, meta
        except requests.RequestException as exc:
            if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 404:
                raise
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def record_range(index, token, init, target, allow_lead_zero=False):
    lines = index.splitlines()
    matches = [i for i, line in enumerate(lines) if f':{token}:' in line]
    if len(matches) != 1:
        raise ValueError(f'Expected one {token} record, found {len(matches)}')
    i = matches[0]
    lead = (int(target[:4]) - int(init[:4])) * 12 + int(target[4:]) - int(init[4:6])
    if not (0 if allow_lead_zero else 1) <= lead <= 9:
        raise ValueError('Requested historical monthly lead is outside the archive range')
    if f':d={init}:' not in lines[i] or f':{lead}-{lead+1} month ave fcst:' not in lines[i]:
        raise ValueError('Wrong initialization, target month, or averaging interval')
    return int(lines[i].split(':')[1]), int(lines[i+1].split(':')[1])-1 if i+1 < len(lines) else None


def decode(data, field, init):
    if (not data.startswith(b'GRIB') or data[7] != 2 or not data.endswith(b'7777') or
        int.from_bytes(data[8:16], 'big') != len(data)):
        raise ValueError('Expected exactly one complete GRIB2 message')
    h = ec.codes_new_from_message(data)
    try:
        token, category, number, level_type, level, units = FIELDS[field]
        checks = {'discipline': 0, 'parameterCategory': category, 'parameterNumber': number,
                  'typeOfLevel': level_type, 'level': level, 'units': units,
                  'dataDate': int(init[:8]), 'dataTime': int(init[8:])*100, 'stepType': 'avg'}
        for key, expected in checks.items():
            if ec.codes_get(h, key) != expected:
                raise ValueError(f'{field}: unexpected {key}={ec.codes_get(h,key)}')
        # ecCodes interprets legacy CFS month intervals as 30-day units. The
        # provider inventory above verifies the calendar lead; month integration
        # below deliberately uses the target's actual calendar days.
        vals = ec.codes_get_values(h)
        lat = ec.codes_get_array(h, 'latitudes')
        lon = (ec.codes_get_array(h, 'longitudes') + 180) % 360 - 180
        xs, ys = np.unique(lon), np.unique(lat)
        if len(vals) != len(xs)*len(ys) or not np.isfinite(vals).all():
            raise ValueError('Incomplete or nonrectangular grid')
        if ec.codes_get(h, 'numberOfMissing') != 0:
            raise ValueError('Missing GRIB values')
        if field in ('precip', 'native') and np.min(vals) < 0:
            raise ValueError('Negative precipitation/snowfall rate')
        grid = np.empty((len(ys), len(xs)))
        grid[np.searchsorted(ys,lat), np.searchsorted(xs,lon)] = vals
        return xs, ys, grid
    finally:
        ec.codes_release(h)


def phase_snow(t2m, t850, precip, target):
    """Use the production phase function, with inches of precipitation."""
    temp = np.maximum(t2m, t850) - 273.15
    a, b, c, d = cf.SNOWFALL_DAI_LAND_PARAMS_BY_SEASON[cf.snowfall_phase_season(target)]
    return np.maximum(precip, 0) * np.clip(a*(np.tanh(b*(temp-c))-d)/100, 0, 1)


def historical_reference(samples):
    """Equal weight per winter, then per cycle within each complete winter."""
    if not samples or len({s['init'] for s in samples}) != len(samples):
        raise ValueError('Historical samples must be nonempty and unique')
    years = sorted({s['init'][:4] for s in samples})
    annual = []
    for year in years:
        subset = [s for s in samples if s['init'][:4] == year]
        if {s['init'][8:] for s in subset} != {'00','06','12','18'} or len(subset) != 4:
            raise ValueError(f'Incomplete four-cycle historical year {year}')
        annual.append({k: np.mean([s[k] for s in subset], axis=0)
                       for k in ('snow','t2m','t850','precip')})
    correct = np.mean([a['snow'] for a in annual],axis=0)
    wrong_order = phase_snow(*(np.mean([a[k] for a in annual],axis=0)
                              for k in ('t2m','t850','precip')), '202703')
    return correct, wrong_order, years


def cycle(init, target, cache, historical=False, allow_lead_zero=False):
    if historical:
        root = ARCHIVE + f'high-priority-subset/monthly-means-9-month/{init[:4]}/{init[:6]}/{init[:8]}/'
        urls = {k: root+f'{k}{init}.01.{target}.avrg.grb2' for k in ('flxf','pgbf')}
        inv_urls = {k: u.removesuffix('.grb2')+'.inv' for k,u in urls.items()}
    else:
        urls = {k: cf.cfs_file_url(init,1,target,k) for k in ('flxf','pgbf')}
        inv_urls = {k: u+'.idx' for k,u in urls.items()}
    indexes = {k: fetch(u,cache,limit=100000)[0].decode('ascii') for k,u in inv_urls.items()}
    fields = ['t2m','t850','precip'] + ([] if historical else ['native'])
    result = dict(init=init, target=target, sources=[], native_in_inventory=':SRWEQ:surface:' in indexes['flxf'])
    axes = None
    for field in fields:
        kind = 'pgbf' if field == 't850' else 'flxf'
        start,end = record_range(indexes[kind],FIELDS[field][0],init,target, allow_lead_zero=historical and allow_lead_zero)
        data,meta = fetch(urls[kind],cache,start,end,limit=200000)
        xs,ys,values = decode(data,field,init)
        if axes is None:
            axes = xs,ys
        elif field == 't850':
            xi = np.abs(xs[None,:]-axes[0][:,None]).argmin(axis=1)
            yi = np.abs(ys[None,:]-axes[1][:,None]).argmin(axis=1)
            values = values[np.ix_(yi,xi)]
        elif not (np.allclose(xs,axes[0],rtol=0,atol=1e-6) and np.allclose(ys,axes[1],rtol=0,atol=1e-6)):
            raise ValueError('Dependency axes differ')
        if field in ('precip','native'):
            values = values*calendar.monthrange(int(target[:4]),int(target[4:]))[1]*86400/25.4
        result[field] = values
        result['sources'].append({**meta,'field':field})
    result['lons'],result['lats'] = axes
    result['snow'] = phase_snow(result['t2m'],result['t850'],result['precip'],target)
    print(f'Loaded {init} -> {target}',flush=True)
    return result


def available_init(year, cache):
    """Discover actual reforecast date within the operational Aug30–Sep05 window."""
    prefix = f'high-priority-subset/monthly-means-9-month/{year}/{year}09/'
    url = requests.Request('GET',ARCHIVE,params={'list-type':2,'delimiter':'/','prefix':prefix}).prepare().url
    data,_ = fetch(url,cache)
    root = ET.fromstring(data)
    if any(x.text == 'true' for x in root.iter() if x.tag.endswith('IsTruncated')):
        raise ValueError('Unexpected truncated month-directory listing')
    dates = sorted({x.text.rstrip('/').split('/')[-1] for x in root.iter()
                    if x.tag.endswith('Prefix') and x.text and re.search(r'/\d{8}/$',x.text)})
    candidates = [d for d in dates if 1 <= int(d[-2:]) <= 5]
    if len(candidates) != 1:
        raise ValueError(f'{year}: expected one September reforecast date in pilot window; got {candidates}')
    return candidates[0]


def run(args):
    out,cache = Path(args.output),Path(args.cache)
    out.mkdir(parents=True,exist_ok=True)
    years = list(range(args.first_year,args.last_year+1))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        dates = list(pool.map(lambda y:available_init(y,cache),years))
    tasks = [(d+h,str(int(d[:4])+1)+'03',True) for d in dates for h in ['00','06','12','18']]
    tasks += [(i,'202703',False) for i in cf.rolling_cycle_inits('2026090506',24)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        samples = list(pool.map(lambda t:cycle(t[0],t[1],cache,t[2]),tasks))
    hist,live = samples[:len(dates)*4],samples[len(dates)*4:]
    for s in samples[1:]:
        if not (np.allclose(s['lons'],samples[0]['lons'],rtol=0,atol=.001) and
                np.allclose(s['lats'],samples[0]['lats'],rtol=0,atol=.001)):
            raise ValueError('Historical and operational grids are incompatible')
    baseline,wrong,used_years = historical_reference(hist)
    forecast = np.mean([s['snow'] for s in live],axis=0)
    native = np.mean([s['native'] for s in live],axis=0)
    precip = np.mean([s['precip'] for s in live],axis=0)
    lon,lat = samples[0]['lons'],samples[0]['lats']
    new = forecast-baseline
    control = forecast-wrong
    # Isolate transformation-order effect using identical historical samples.
    # This control is NOT the existing smoothed NCEI operational reference.
    np.savez_compressed(out/'pilot-grids.npz',lons=lon,lats=lat,forecast=forecast,
                        historical_reference=baseline,mean_input_reference=wrong,
                        pilot_departure=new,mean_input_departure=control,
                        native_lwe=native,precipitation=precip)
    points=[]
    for name,y,x in POINTS:
        j,i=np.abs(lat-y).argmin(),np.abs(lon-x).argmin()
        points.append(dict(location=name,grid_lat=float(lat[j]),grid_lon=float(lon[i]),
            forecast_derived_lwe=float(forecast[j,i]),native_lwe=float(native[j,i]),
            precipitation=float(precip[j,i]),historical_reference=float(baseline[j,i]),
            mean_input_reference=float(wrong[j,i]),pilot_departure=float(new[j,i]),
            mean_input_departure=float(control[j,i]),order_effect=float(new[j,i]-control[j,i])))
    report=dict(status='RESEARCH_ONLY_NOT_VALIDATED_FOR_PUBLICATION',
        target='202703',anchor='2026090506',historical_years=used_years,
        historical_dates=dates,historical_cycles=len(hist),operational_cycles=len(live),
        method='mean individual historical phase-derived snowfall; equal winter weights',
        control='same historical sample; derive snowfall from averaged inputs',
        limitations=['Four historical initializations within the six-day window versus 24 operational cycles.',
                     'Operational window includes six August (lead 7) and eighteen September (lead 6) cycles; the available in-window historical samples are September lead 6 only.',
                     'Mean-input control isolates operation order; it is not the published smoothed NCEI reference.',
                     'Monthly temperature phase estimation remains an approximation.',
                     'No observational bias correction or independent predictive validation.',
                     'Native accumulation remains uncorrected.'],
        historical_native_field_present=sum(s['native_in_inventory'] for s in hist),
        sample_points=points,
        sources=[dict(init=s['init'],target=s['target'],records=s['sources']) for s in samples],
        grids_sha256=sha((out/'pilot-grids.npz').read_bytes()))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--first-year',type=int,default=1982)
    p.add_argument('--last-year',type=int,default=2010)
    p.add_argument('--workers',type=int,choices=range(1,5),default=3)
    a=p.parse_args()
    if not 1982 <= a.first_year <= a.last_year <= 2010:
        p.error('Pilot historical initialization years must be within 1982–2010')
    run(a)
