"""CONUS research preview and historical-winter influence for March reference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import numpy as np
from matplotlib.path import Path as PolygonPath
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cfsv2_march_pilot as p


def conus_mask(lons,lats,points,offsets):
    x,y=np.meshgrid(lons,lats);xy=np.column_stack([x.ravel(),y.ravel()]);mask=np.zeros(x.shape,bool)
    for a,b in zip(offsets[:-1],offsets[1:]):mask|=PolygonPath(points[a:b]).contains_points(xy).reshape(x.shape)
    return mask&(x>=-125)&(x<=-66)&(y>=24)&(y<=50)


def cell_weights(lats,nlon):
    edges=np.r_[-90,(lats[:-1]+lats[1:])/2,90]
    return np.broadcast_to(np.diff(np.sin(np.deg2rad(edges)))[:,None],(len(lats),nlon))


def summarize(old,new,mask,weights):
    a=old[mask];b=new[mask];w=weights[mask];w=w/w.sum();d=b-a
    return dict(area_weighted_mean_change=float(np.sum(w*d)),area_weighted_mean_absolute_change=float(np.sum(w*np.abs(d))),
        area_weighted_rms_change=float(np.sqrt(np.sum(w*d*d))),max_absolute_change=float(np.max(np.abs(d))),
        area_fraction_change_at_least_005=float(np.sum(w*(np.abs(d)>=.05))),
        area_fraction_sign_flip_away_from_zero=float(np.sum(w*((a*b<0)&(np.maximum(np.abs(a),np.abs(b))>=.05)))))


def main(args):
    directory=Path(args.pilot);out=Path(args.output);out.mkdir(parents=True,exist_ok=True);cache=Path(args.cache)
    report=json.loads((directory/'report.json').read_text());mix=json.loads((directory/'lead-mix-report.json').read_text())
    with np.load(directory/'pilot-grids.npz') as z:old={k:z[k] for k in z.files}
    with np.load(directory/'lead-mix-grids.npz') as z:new={k:z[k] for k in z.files}
    dates=[d for pair in zip(mix['august_dates'],report['historical_dates']) for d in pair]
    with ThreadPoolExecutor(max_workers=4) as pool:
        samples=list(pool.map(lambda init:p.cycle(init,str(int(init[:4])+1)+'03',cache,True),[d+h for d in dates for h in ('00','06','12','18')]))
    annual=[]
    for year in report['historical_years']:
        months=[]
        for month in ('08','09'):
            subset=[s for s in samples if s['init'].startswith(year+month)]
            if len(subset)!=4 or len({s['init'] for s in subset})!=4:raise ValueError('Incomplete historical sampling')
            for s in subset:
                if not(np.array_equal(s['lons'],old['lons']) and np.array_equal(s['lats'],old['lats'])):raise ValueError('Historical grid mismatch')
            months.append(np.mean([s['snow'] for s in subset],axis=0))
        annual.append(.25*months[0]+.75*months[1])
    annual=np.array(annual)
    if not np.allclose(annual.mean(axis=0),new['mixed_reference'],rtol=0,atol=1e-12):raise ValueError('Reference reconstruction differs')
    omitted=(annual.sum(axis=0)-annual)/(len(annual)-1)
    influence=np.max(np.abs(omitted-new['mixed_reference']),axis=0)
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as z:points=z['states_points'];offsets=z['states_offsets']
    mask=conus_mask(old['lons'],old['lats'],points,offsets);weights=cell_weights(old['lats'],len(old['lons']))
    south=mask&(old['lats'][:,None]<=37)
    stats={region:{'candidate_vs_existing':summarize(old['published_method_departure'],new['departure'],m,weights),
                   'lead_mix_vs_september_only':summarize(old['pilot_departure'],new['departure'],m,weights),
                   'max_single_winter_reference_influence':float(influence[m].max())}
           for region,m in [('CONUS',mask),('CONUS_south_of_37N',south)]}
    point_results=[]
    for name,y,x in p.POINTS:
        j=np.abs(old['lats']-y).argmin();i=np.abs(old['lons']-x).argmin()
        point_results.append(dict(location=name,existing=float(old['published_method_departure'][j,i]),candidate=float(new['departure'][j,i]),
            omitted_winter_departure_min=float((old['forecast'][j,i]-omitted[:,j,i]).min()),
            omitted_winter_departure_max=float((old['forecast'][j,i]-omitted[:,j,i]).max())))
    np.savez_compressed(out/'reference-candidate.npz',lons=old['lons'],lats=old['lats'],reference=new['mixed_reference'],
                        annual_reference=annual,initialization_years=np.array(report['historical_years'],dtype=int),
                        departure=new['departure'],max_single_winter_influence=influence)
    result=dict(status='RESEARCH_REFERENCE_NOT_APPROVED_FOR_PRODUCTION',anchor='2026090506',target='202703',
        units='inches snowfall water equivalent',historical_years=report['historical_years'],historical_cycles=232,
        weighting='Equal winter weights; 25% August 29 and 75% September 3, four cycles each.',
        conus_cell_count=int(mask.sum()),statistics=stats,points=point_results,
        source_grid_hashes={f:p.sha((directory/f).read_bytes()) for f in ('pilot-grids.npz','lead-mix-grids.npz')},
        candidate_sha256=p.sha((out/'reference-candidate.npz').read_bytes()),
        limitations=['Approximate initialization-date matching; correct lead proportions do not create exact 24-cycle hindcasts.',
                     'Change from published-method reconstruction includes sampling, smoothing, transformation-order and lead effects.',
                     'Single-winter omission is a sensitivity diagnostic, not predictive validation or a confidence interval.',
                     'Native accumulation is separate and unchanged. No spatially calibrated snowfall totals are produced.'])
    (out/'reference-review.json').write_text(json.dumps(result,indent=2)+'\n')
    x,y=np.meshgrid(old['lons'],old['lats']);fig,axes=plt.subplots(3,1,figsize=(11,13),layout='constrained')
    levels=[-2,-1.5,-1,-.75,-.5,-.25,0,.25,.5,.75,1,1.5,2]
    panels=[(old['published_method_departure'],'Existing reference — reconstructed'),(new['departure'],'Candidate: individual forecasts, weighted August/September'),
            (new['departure']-old['published_method_departure'],'Candidate minus existing calculation')]
    for ax,(values,title) in zip(axes,panels):
        im=ax.contourf(x,y,np.ma.masked_where(~mask,values),levels=levels,cmap='RdBu',extend='both')
        for a,b in zip(offsets[:-1],offsets[1:]):ax.plot(points[a:b,0],points[a:b,1],color='#354451',linewidth=.4)
        ax.set(xlim=(-125,-66),ylim=(24,50),title=title);ax.set_aspect(1.25);ax.set_xticks([]);ax.set_yticks([])
    fig.colorbar(im,ax=axes,orientation='horizontal',shrink=.8,pad=.025,label='Snowfall water-equivalent departure (inches) · blue = positive')
    fig.suptitle('March 2027 · September 5, 2026 06Z\nResearch candidate · 1982–2010 reference',fontsize=15,weight='bold')
    fig.supxlabel('NOT APPROVED FOR PRODUCTION · 8 weighted historical cycles versus 24 operational cycles\n'
                  'Different historical dates; not an observed snowfall-total correction.',fontsize=10)
    fig.savefig(out/'cfsv2-reference-candidate.png',dpi=140);plt.close(fig)
    print(json.dumps(dict(statistics=stats,points=point_results),indent=2))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--cache',required=True);a.add_argument('--pilot',required=True);a.add_argument('--output',required=True)
    main(a.parse_args())
