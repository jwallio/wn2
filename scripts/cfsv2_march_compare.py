"""Compare the pilot with the existing smoothed reference; no publication."""
import argparse
import json
from pathlib import Path
import numpy as np
import eccodes as ec
import cfsv2_march_pilot as p


def calibration(cache):
    result={}
    sources=[]
    inventory=[]
    for kind,directory in [('flxf','flux'),('pgbf','by-pressure-level')]:
        url=p.ARCHIVE+f'calibration-climatologies/{directory}-1982-2010/09/{kind}.09.05.06.l06.fclm.1982.2010.grb2'
        data,meta=p.fetch(url,cache,limit=40_000_000)
        sources.append(meta)
        # codes_grib_new_from_file requires a real file descriptor.
        temp=cache/(p.sha(data)+'.grb2')
        temp.write_bytes(data)
        with temp.open('rb') as stream:
            while (h:=ec.codes_grib_new_from_file(stream)) is not None:
                try:
                    inventory.append(dict(kind=kind,name=ec.codes_get(h,'name'),
                                          units=ec.codes_get(h,'units')))
                    for field in (['t2m','precip'] if kind=='flxf' else ['t850']):
                        token,cat,num,levtype,lev,unit=p.FIELDS[field]
                        if (ec.codes_get(h,'parameterCategory')==cat and ec.codes_get(h,'parameterNumber')==num
                            and ec.codes_get(h,'typeOfLevel')==levtype and ec.codes_get(h,'level')==lev):
                            if field in result:raise ValueError('Duplicate calibration field')
                            init=str(ec.codes_get(h,'dataDate'))+f'{ec.codes_get(h,"dataTime")//100:02d}'
                            if init[4:]!='090506':raise ValueError('Calibration anchor mismatch')
                            result[field]=p.decode(ec.codes_get_message(h),field,init)
                finally:ec.codes_release(h)
    if set(result)!= {'t2m','t850','precip'}:raise ValueError('Incomplete calibration')
    xs,ys,t=result['t2m']
    xp,yp,r=result['precip']
    if not (np.array_equal(xs,xp) and np.array_equal(ys,yp)):raise ValueError('Flux axes differ')
    x8,y8,t8=result['t850']
    xi=np.abs(x8[None,:]-xs[:,None]).argmin(axis=1)
    yi=np.abs(y8[None,:]-ys[:,None]).argmin(axis=1)
    return xs,ys,p.phase_snow(t,t8[np.ix_(yi,xi)],r*31*86400/25.4,'202703'),sources,inventory


def main(args):
    directory=Path(args.pilot)
    with np.load(directory/'pilot-grids.npz') as z:
        grids={k:z[k] for k in z.files}
    xs,ys,reference,sources,inventory=calibration(Path(args.cache))
    if not(np.allclose(xs,grids['lons'],atol=.001,rtol=0) and np.allclose(ys,grids['lats'],atol=.001,rtol=0)):
        raise ValueError('Calibration axes differ')
    grids['published_method_reference']=reference
    grids['published_method_departure']=grids['forecast']-reference
    grids['change_from_published_method']=grids['pilot_departure']-grids['published_method_departure']
    report=json.loads((directory/'report.json').read_text())
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as f:
        if not(np.allclose(xs,f['lons'],atol=.001,rtol=0) and np.allclose(ys,f['lats'],atol=.001,rtol=0)):
            raise ValueError('Snow ratio lookup axes differ')
        ratios=f['native_ratios'].copy()
    for point in report['sample_points']:
        i=np.abs(xs-point['grid_lon']).argmin();j=np.abs(ys-point['grid_lat']).argmin()
        for k in ['published_method_reference','published_method_departure','change_from_published_method']:
            point[k]=float(grids[k][j,i])
        point['native_snow_fraction']=float(grids['native_lwe'][j,i]/grids['precipitation'][j,i]) if grids['precipitation'][j,i]>0 else None
        point['snow_to_liquid_ratio']=float(ratios[j,i]) if np.isfinite(ratios[j,i]) else None
        point['uncorrected_native_snow_depth']=float(grids['native_lwe'][j,i]*ratios[j,i]) if np.isfinite(ratios[j,i]) else None
    # Cross-check the independent decoder against the already published native
    # numeric output for precisely the same anchor and 24-cycle window.
    url='https://jwallio.github.io/seasonal/cfsv2/2026090506/cfsv2_snowfall_lwe_202703.csv.gz'
    data,meta=p.fetch(url,Path(args.cache),limit=3_000_000)
    temp=Path(args.cache)/'published-native.csv.gz';temp.write_bytes(data)
    published=p.cf.read_grid_state(temp)
    if not (np.allclose(published.lons,xs,atol=.001,rtol=0) and np.allclose(published.lats,ys,atol=.001,rtol=0)):
        raise ValueError('Published numeric axes differ')
    error=float(np.max(np.abs(np.asarray(published.values)-grids['native_lwe'])))
    report['native_published_replay_max_error_inches']=error
    # wgrib2 CSV output rounds the underlying rate. Allow that quantization only.
    if error>.0001:raise ValueError(f'Independent native replay differs by {error} inches')
    report['published_native_grid_source']=meta
    report['calibration_sources']=sources
    report['calibration_inventory']=inventory
    np.savez_compressed(directory/'pilot-grids.npz',**grids)
    report['grids_sha256']=p.sha((directory/'pilot-grids.npz').read_bytes())
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['sample_points'],indent=2))
    print('Native replay max error',error)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--pilot',required=True)
    a.add_argument('--cache',required=True)
    main(a.parse_args())
