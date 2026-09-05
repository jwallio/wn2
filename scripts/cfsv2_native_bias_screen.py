"""Research screen: single-cycle historical native snow vs daily ACIS observations.

This deliberately does not publish a correction: one historical cycle is not
the operational 24-cycle product, and five stations cannot calibrate CONUS.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import numpy as np
import requests
import eccodes as ec
import cfsv2_march_pilot as p

ROOT='https://www.ncei.noaa.gov/oa/prod-cfs-operational-forecast/'
STATIONS=['KRDU','KAVL','KOKC','KORD','KBOS']


def error_metrics(pred,observed):
    error=np.asarray(pred)-np.asarray(observed)
    return dict(mae=float(np.mean(np.abs(error))),rmse=float(np.sqrt(np.mean(error**2))),
                mean_error=float(np.mean(error)))


def leave_one_winter_out(raw,observed):
    """Diagnostic including snowy winters omitted by the dry late-period split."""
    raw=np.asarray(raw);observed=np.asarray(observed)
    if len(raw)<8:raise ValueError('Insufficient winters for the diagnostic')
    corrected=[];climatology=[];factors=[]
    for i in range(len(raw)):
        train=np.arange(len(raw))!=i
        if raw[train].mean()<=0:raise ValueError('Undefined leave-one-out factor')
        factor=float(observed[train].mean()/raw[train].mean())
        corrected.append(raw[i]*factor);climatology.append(observed[train].mean());factors.append(factor)
    corrected=np.asarray(corrected);climatology=np.asarray(climatology)
    groups={}
    for label,mask in [('all',np.ones(len(raw),bool)),('measurable_snow',observed>=.1),('zero_or_trace',observed<.1)]:
        if mask.any():groups[label]=dict(count=int(mask.sum()),raw=error_metrics(raw[mask],observed[mask]),
            corrected=error_metrics(corrected[mask],observed[mask]),
            observed_climatology=error_metrics(climatology[mask],observed[mask]))
    return dict(groups=groups,factors=factors,
                limitation='Leave-one-out uses other earlier and later winters; diagnostic, not a chronological forecast simulation.')


def evaluate(years,raw,observed,train_end=2018):
    """Fixed chronological split, with fitting restricted to the training set."""
    years=np.asarray(years);raw=np.asarray(raw);observed=np.asarray(observed)
    train=years<=train_end;test=years>train_end
    if train.sum()<5 or test.sum()<3 or not np.isfinite(raw).all() or not np.isfinite(observed).all():
        raise ValueError('Insufficient complete training/validation data')
    if raw[train].mean()<=0:raise ValueError('Undefined multiplicative correction')
    factor=float(observed[train].mean()/raw[train].mean())
    corrected=raw[test]*factor
    climatology=np.full(test.sum(),observed[train].mean())
    return dict(factor=factor,training_initialization_years=years[train].tolist(),
                validation_initialization_years=years[test].tolist(),raw=error_metrics(raw[test],observed[test]),
                corrected=error_metrics(corrected,observed[test]),
                training_observed_climatology=error_metrics(climatology,observed[test]),
                validation_measurable_snow_winters=int(np.sum(observed[test]>=.1)))


def native_year(year,cache):
    init=f'{year}090506';target=f'{year+1}03'
    url=ROOT+f'monthly-means/{year}/{year}09/{year}0905/{init}/flxf.01.{init}.{target}.avrg.grib.grb2'
    try:
        data,meta=p.fetch(url,cache,limit=10_000_000)
        file=cache/(p.sha(data)+'.grb2');file.write_bytes(data)
        found=[]
        with file.open('rb') as stream:
            while (h:=ec.codes_grib_new_from_file(stream)) is not None:
                try:
                    if (ec.codes_get(h,'discipline')==0 and ec.codes_get(h,'parameterCategory')==1
                        and ec.codes_get(h,'parameterNumber')==12 and ec.codes_get(h,'typeOfLevel')=='surface'):
                        # CFS encodes lead in calendar months; its uncorrected
                        # end-of-interval date is not the valid month.
                        if ec.codes_get(h,'indicatorOfUnitOfTimeRange')!=3 or ec.codes_get(h,'forecastTime')!=6:
                            raise ValueError('Historical native record has wrong lead')
                        found.append(p.decode(ec.codes_get_message(h),'native',init))
                finally:ec.codes_release(h)
        if len(found)!=1:raise ValueError(f'Expected one native snowfall field; found {len(found)}')
        xs,ys,rate=found[0]
        with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as lookup:
            if not(np.allclose(xs,lookup['lons'],atol=.001,rtol=0) and np.allclose(ys,lookup['lats'],atol=.001,rtol=0)):
                raise ValueError('Historical axes differ from ratio lookup')
            values=rate*31*86400/25.4*lookup['native_ratios']
        print('Native history',year,'available',flush=True)
        return dict(year=year,status='available',lons=xs,lats=ys,depth=values,source=meta)
    except (requests.RequestException,ValueError) as exc:
        print('Native history',year,str(exc)[:120],flush=True)
        return dict(year=year,status='unavailable',url=url,error=str(exc))


def observations(sid,cache):
    payload=dict(sid=sid,sdate='2012-01-01',edate='2024-04-01',
                 elems=[{'name':'snow','interval':'dly','duration':'dly'}],meta='name,state,ll,sids')
    key=p.sha(json.dumps(payload,sort_keys=True).encode())
    path=cache/('acis-'+key+'.json')
    if not path.exists():
        r=requests.post('https://data.rcc-acis.org/StnData',json=payload,timeout=(10,40))
        r.raise_for_status();path.write_text(r.text)
    raw=path.read_bytes();result=json.loads(raw)
    if 'error' in result or 'data' not in result or 'meta' not in result:
        raise ValueError(f'Invalid ACIS response for {sid}')
    if sid not in [s.split()[0] for s in result['meta']['sids']]:
        raise ValueError('ACIS station identity differs')
    # Require all 31 distinct March days; traces count as zero inches, missing
    # days exclude the entire month. Never convert missing observations to zero.
    monthly={};excluded=[]
    for year in range(2012,2025):
        rows={date:value for date,value in result['data'] if date.startswith(f'{year}-03-')}
        expected={f'{year}-03-{day:02d}' for day in range(1,32)}
        if set(rows)!=expected:
            excluded.append(year);continue
        try:
            vals=[0. if value=='T' else float(value) for value in rows.values()]
            if not np.isfinite(vals).all() or min(vals)<0:raise ValueError('Invalid snow observation')
            monthly[year]=sum(vals)
        except ValueError:excluded.append(year)
    return dict(sid=sid,meta=result['meta'],monthly=monthly,excluded=excluded,
                source=dict(url='https://data.rcc-acis.org/StnData',request=payload,sha256=p.sha(raw)))


def main(args):
    cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        historical=list(pool.map(lambda y:native_year(y,cache),range(2011,2024)))
    with ThreadPoolExecutor(max_workers=3) as pool:
        observed=list(pool.map(lambda sid:observations(sid,cache),STATIONS))
    stations=[]
    for obs in observed:
        x,y=obs['meta']['ll'];rows=[]
        for h in historical:
            if h['status']!='available' or h['year']+1 not in obs['monthly']:continue
            i=np.abs(h['lons']-x).argmin();j=np.abs(h['lats']-y).argmin()
            value=float(h['depth'][j,i])
            if not np.isfinite(value):continue
            rows.append(dict(initialization_year=h['year'],valid_march=h['year']+1,
                             raw_snow_inches=value,observed_snow_inches=obs['monthly'][h['year']+1],
                             grid_lon=float(h['lons'][i]),grid_lat=float(h['lats'][j])))
        try:
            scores=evaluate([r['initialization_year'] for r in rows],[r['raw_snow_inches'] for r in rows],
                            [r['observed_snow_inches'] for r in rows])
            scores['leave_one_winter_out']=leave_one_winter_out([r['raw_snow_inches'] for r in rows],
                                                               [r['observed_snow_inches'] for r in rows])
        except ValueError as exc:scores={'status':'insufficient_data','reason':str(exc)}
        stations.append(dict(station=obs['meta'],sid=obs['sid'],observations_source=obs['source'],
                             excluded_observation_years=obs['excluded'],rows=rows,scores=scores))
    report=dict(status='RESEARCH_SCREEN_ONLY_NO_CORRECTION_PUBLISHED',
        method='Native SRWEQ integrated for March, times existing CIPS ratio at nearest station grid cell.',
        split='Fit initialization years 2011–2018; evaluate 2019–2023, excluding unavailable data.',
        limitations=['One September 5 06Z cycle per year, not the operational 24-cycle rolling mean.',
                     'Five station points do not represent a calibrated CONUS grid.',
                     'Station snowfall and coarse grid estimates have spatial representativeness differences.',
                     'This exploratory fixed split is not a production promotion test.'],
        historical_sources=[{k:v for k,v in h.items() if k not in ['lons','lats','depth']} for h in historical],stations=stations)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({s['sid']:s['scores'] for s in stations},indent=2))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cache',required=True);a.add_argument('--output',required=True)
    main(a.parse_args())
