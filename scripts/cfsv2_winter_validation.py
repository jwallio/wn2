"""Research-only DJF validation at a fixed September 5 06Z ensemble anchor.

Exact 24-cycle means; native GRIB records retained with verified source hashes.
No correction is applied to operational maps. Missing months exclude DJF.
"""
import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import numpy as np
import requests
import eccodes as ec
import cfsv2_march_pilot as p
import cfsv2_native_bias_screen as march

STATIONS='KRDU,KAVL,KOKC,KORD,KBOS,KDFW,KDEN,KMSP,KDTW,KCLE,KBUF,KALB,KBTV,KPIT,KSTL'


def month_seconds(target):
    return calendar.monthrange(int(target[:4]),int(target[4:]))[1]*86400


def targets(year):
    return [f'{year}12',f'{year+1}01',f'{year+1}02']


def native_record(init,target,cache):
    """Retain one exact native message, plus full upstream source provenance."""
    url=march.ROOT+f'monthly-means/{init[:4]}/{init[:6]}/{init[:8]}/{init}/flxf.01.{init}.{target}.avrg.grib.grb2'
    stem=cache/f'native-{init}-{target}'
    record=stem.with_suffix('.grb2');sidecar=stem.with_suffix('.json')
    cache_hit=record.exists() and sidecar.exists()
    if cache_hit:
        message=record.read_bytes();meta=json.loads(sidecar.read_text())
        if meta['record_sha256']!=p.sha(message) or meta['source']['url']!=url:
            raise ValueError('Native record cache identity/hash mismatch')
    else:
        # Reuse a full-file cache if one exists; new full files are temporary.
        key=p.sha(f'{url}|None|None'.encode())
        with tempfile.TemporaryDirectory() as temp:
            source_cache=cache if (cache/key).exists() else Path(temp)
            data,source=p.fetch(url,source_cache,limit=10_000_000)
        found=[]
        with tempfile.TemporaryFile() as stream:
            stream.write(data);stream.seek(0)
            while (h:=ec.codes_grib_new_from_file(stream)) is not None:
                try:
                    if (ec.codes_get(h,'discipline'),ec.codes_get(h,'parameterCategory'),
                        ec.codes_get(h,'parameterNumber'),ec.codes_get(h,'typeOfLevel'))==(0,1,12,'surface'):
                        found.append(ec.codes_get_message(h))
                finally:ec.codes_release(h)
        if len(found)!=1:raise ValueError('Expected exactly one surface native snowfall record')
        message=found[0];meta=dict(source=source,record_sha256=p.sha(message),init=init,target=target)
    h=ec.codes_new_from_message(message)
    try:
        if ec.codes_get(h,'indicatorOfUnitOfTimeRange')!=3 or ec.codes_get(h,'forecastTime')!=p.cf.lead_for_target(init,target):
            raise ValueError('Wrong native calendar lead')
    finally:ec.codes_release(h)
    xs,ys,rate=p.decode(message,'native',init)
    if not cache_hit:
        record.write_bytes(message);sidecar.write_text(json.dumps(meta,indent=2)+'\n')
    return xs,ys,rate*month_seconds(target)/25.4,meta


def point_cycle(task,cache,observed,lookup):
    init,target=task
    try:
        xs,ys,lwe,source=native_record(init,target,cache)
        if not (np.allclose(xs,lookup['lons'],atol=.001,rtol=0) and np.allclose(ys,lookup['lats'],atol=.001,rtol=0)):
            raise ValueError('Grid differs from fixed CIPS lookup')
        values={};grid={}
        for obs in observed:
            x,y=obs['meta']['ll'];i=np.abs(xs-x).argmin();j=np.abs(ys-y).argmin()
            value=float(lwe[j,i]*lookup['native_ratios'][j,i])
            if not np.isfinite(value):raise ValueError(f'Unsupported ratio at {obs["sid"]}')
            values[obs['sid']]=value;grid[obs['sid']]=[float(xs[i]),float(ys[j])]
        return dict(init=init,target=target,status='available',values=values,grid=grid,source=source)
    except (requests.RequestException,ValueError) as exc:
        print('Unavailable',init,target,str(exc),flush=True)
        return dict(init=init,target=target,status='unavailable',error=str(exc))


def daily_response(sid,start,end,cache):
    payload=dict(sid=sid,sdate=start,edate=end,
                 elems=[{'name':'snow','interval':'dly','duration':'dly'}],meta='name,state,ll,sids')
    path=cache/('acis-'+p.sha(json.dumps(payload,sort_keys=True).encode())+'.json')
    if not path.exists():
        r=requests.post('https://data.rcc-acis.org/StnData',json=payload,timeout=(10,40));r.raise_for_status()
        raw=r.content
    else:raw=path.read_bytes()
    result=json.loads(raw)
    if 'data' not in result or 'meta' not in result or sid not in [s.split()[0] for s in result['meta']['sids']]:
        raise ValueError('ACIS response identity/data mismatch')
    if not path.exists():path.write_bytes(raw)
    return result,dict(url='https://data.rcc-acis.org/StnData',request=payload,sha256=p.sha(raw))


def month_total(rows,target):
    prefix=target[:4]+'-'+target[4:]+'-'
    subset=[(date,value) for date,value in rows if date.startswith(prefix)]
    expected={prefix+f'{day:02d}' for day in range(1,calendar.monthrange(int(target[:4]),int(target[4:]))[1]+1)}
    if len(subset)!=len(expected) or {d for d,v in subset}!=expected:raise ValueError('Missing or duplicate daily observations')
    vals=np.array([0. if v=='T' else float(v) for d,v in subset])
    if not np.isfinite(vals).all() or np.any(vals<0):raise ValueError('Invalid daily snow observation')
    return float(vals.sum())


def winter_observations(sid,cache):
    # Most observations are already in the March pilot's cached daily response.
    main,source=daily_response(sid,'2012-01-01','2024-04-01',cache)
    early,early_source=daily_response(sid,'2011-12-01','2011-12-31',cache)
    if not np.allclose(main['meta']['ll'],early['meta']['ll'],atol=1e-6,rtol=0):
        raise ValueError('Station coordinates changed between responses')
    rows=early['data']+main['data'];monthly={};excluded=[]
    for year in range(2011,2024):
        for target in targets(year):
            try:monthly[target]=month_total(rows,target)
            except ValueError:excluded.append(target)
    return dict(sid=sid,meta=main['meta'],monthly=monthly,excluded=excluded,sources=[early_source,source])


def complete_mean(cycles,expected):
    if len(cycles)!=len(expected) or {c['init'] for c in cycles}!=set(expected):return None
    if any(c['status']!='available' for c in cycles):return None
    return {sid:float(np.mean([c['values'][sid] for c in cycles])) for sid in cycles[0]['values']}


def influence(years,raw,obs):
    base=march.walk_forward(years,raw,obs);cases=base['cases']
    errors=np.array([abs(c['corrected']-c['observed'])-abs(c['climatology']-c['observed']) for c in cases])
    omitted=[]
    for excluded in years:
        corrected=[];clim=[];observed=[]
        for case in cases:
            train=np.array([(y<case['initialization_year'] and y!=excluded) for y in years])
            if train.sum()<4:raise ValueError('Too few sensitivity training winters')
            denominator=np.mean(np.asarray(raw)[train])
            if denominator<=0:raise ValueError('Undefined sensitivity correction')
            factor=np.mean(np.asarray(obs)[train])/denominator
            corrected.append(case['raw']*factor);clim.append(np.mean(np.asarray(obs)[train]));observed.append(case['observed'])
        a=march.error_metrics(corrected,observed)['mae'];b=march.error_metrics(clim,observed)['mae']
        omitted.append(dict(omitted_training_initialization_year=excluded,corrected_mae=a,climatology_mae=b,difference=a-b))
    return dict(baseline_mae_difference=float(errors.mean()),
                drop_one_validation_case_differences=[dict(initialization_year=c['initialization_year'],difference=float(np.delete(errors,i).mean())) for i,c in enumerate(cases)],
                drop_one_training_winter=omitted)


def build_report(cycles,observed):
    means={}
    for year in range(2011,2024):
        for target in targets(year):
            means[target]=complete_mean([c for c in cycles if c['init'][:4]==str(year) and c['target']==target],march.cycle_window(year))
    stations=[]
    for obs in observed:
        products={}
        for label,indexes in [('December',[0]),('January',[1]),('February',[2]),('DJF',[0,1,2])]:
            rows=[];excluded=[]
            for year in range(2011,2024):
                months=[targets(year)[i] for i in indexes]
                if any(means[t] is None or t not in obs['monthly'] for t in months):excluded.append(year);continue
                rows.append(dict(initialization_year=year,targets=months,
                    raw=sum(means[t][obs['sid']] for t in months),observed=sum(obs['monthly'][t] for t in months)))
            years=[r['initialization_year'] for r in rows];raw=[r['raw'] for r in rows];actual=[r['observed'] for r in rows]
            try:
                scores=dict(walk_forward=march.walk_forward(years,raw,actual),
                            sensitivity=influence(years,raw,actual),fixed_split=march.evaluate(years,raw,actual))
            except ValueError as exc:scores=dict(status='insufficient_data',reason=str(exc))
            products[label]=dict(rows=rows,excluded_initialization_years=excluded,scores=scores)
        stations.append(dict(sid=obs['sid'],station=obs['meta'],products=products,observations_sources=obs['sources'],excluded_observation_months=obs['excluded']))
    return dict(status='RESEARCH_ONLY_NO_PRODUCTION_CORRECTION',anchor='September 5 06Z',ensemble_cycles=24,
                source_cycles=cycles,stations=stations,
                complete_model_months=[t for t,m in means.items() if m is not None],
                limitations=['Selected 15-station sample; no CONUS interpolation or promotion.',
                             'A September initialization only; results cannot be transferred to other leads.',
                             'Chronological expanding training with minimum five earlier winters; DJF fit to complete seasonal sums.',
                             'Exploratory historical validation; no new independent holdout is claimed.'])


def main(args):
    cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        observed=list(pool.map(lambda sid:winter_observations(sid,cache),args.stations.split(',')))
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as z:lookup={k:z[k] for k in ('lons','lats','native_ratios')}
    tasks=[(init,target) for year in range(2011,2024) for target in targets(year) for init in march.cycle_window(year)]
    cycles=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for c in pool.map(lambda task:point_cycle(task,cache,observed,lookup),tasks):
            cycles.append(c)
            if len(cycles)%24==0:
                print('Completed',len(cycles),'of',len(tasks),c['target'],flush=True)
                (out/'winter-cycles-checkpoint.json').write_text(json.dumps(cycles)+'\n')
    report=build_report(cycles,observed)
    (out/'winter-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Finished:',len(report['complete_model_months']),'complete model months',flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cache',required=True);a.add_argument('--output',required=True)
    a.add_argument('--stations',default=STATIONS);a.add_argument('--workers',type=int,choices=range(1,9),default=4)
    main(a.parse_args())
