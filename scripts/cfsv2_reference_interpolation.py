"""Research March reference interpolated to each operational date and hour.

Derive snowfall independently first; interpolate its historical reference in
initialization time. This never creates or labels synthetic model forecasts.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import re
import requests
import numpy as np
import cfsv2_march_pilot as p
from cfsv2_native_bias_screen import cycle_window
from cfsv2_reference_review import conus_mask,cell_weights,summarize


def brackets(year,cache,august,september):
    prefix=f'high-priority-subset/monthly-means-9-month/{year}/{year}09/'
    url=requests.Request('GET',p.ARCHIVE,params={'list-type':2,'delimiter':'/','prefix':prefix}).prepare().url
    data,_=p.fetch(url,cache);root=ET.fromstring(data)
    if any(x.text=='true' for x in root.iter() if x.tag.endswith('IsTruncated')):raise ValueError('Truncated listing')
    dates=sorted({x.text.rstrip('/').split('/')[-1] for x in root.iter()
                  if x.tag.endswith('Prefix') and x.text and re.search(r'/\d{8}/$',x.text)})
    after=[d for d in dates if d>f'{year}0905']
    if not after or (datetime.strptime(after[0],'%Y%m%d')-datetime(year,9,5)).days>5:raise ValueError('No nearby upper bracket')
    return [august,september,after[0]]


def interpolation_weights(requested,available):
    """Same-hour interpolation only, with no extrapolation or absent brackets."""
    time=datetime.strptime(requested,'%Y%m%d%H')
    candidates=sorted(i for i in available if i[-2:]==requested[-2:])
    before=[i for i in candidates if i<=requested];after=[i for i in candidates if i>=requested]
    if not before or not after:raise ValueError('Unbracketed requested initialization')
    lo,hi=before[-1],after[0]
    if lo==hi:return {lo:1.}
    a,b=datetime.strptime(lo,'%Y%m%d%H'),datetime.strptime(hi,'%Y%m%d%H')
    if (b-a).days>5:raise ValueError('Historical initialization gap exceeds five days')
    fraction=(time-a).total_seconds()/(b-a).total_seconds()
    return {lo:1-fraction,hi:fraction}


def annual_reference(samples,requested):
    by_init={s['init']:s for s in samples}
    if len(by_init)!=len(samples):raise ValueError('Duplicate historical samples')
    weights={i:0. for i in by_init}
    for init in requested:
        for source,weight in interpolation_weights(init,by_init).items():weights[source]+=weight/len(requested)
    if not np.isclose(sum(weights.values()),1):raise ValueError('Reference weights do not sum to one')
    return sum(by_init[i]['snow']*weight for i,weight in weights.items()),weights



def plot(directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory=Path(directory)
    with np.load(directory/'interpolated-reference.npz') as z:g={k:z[k] for k in z.files}
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as z:points=z['states_points'];offsets=z['states_offsets']
    mask=conus_mask(g['lons'],g['lats'],points,offsets);x,y=np.meshgrid(g['lons'],g['lats'])
    fig,axes=plt.subplots(3,1,figsize=(11,13),layout='constrained')
    levels=[-2,-1.5,-1,-.75,-.5,-.25,0,.25,.5,.75,1,1.5,2]
    for ax,key,title in zip(axes,['existing_departure','departure','change'],
            ['Existing reference — reconstructed','Candidate: reference interpolated to each cycle date','Candidate minus existing calculation']):
        im=ax.contourf(x,y,np.ma.masked_where(~mask,g[key]),levels=levels,cmap='RdBu',extend='both')
        for a,b in zip(offsets[:-1],offsets[1:]):ax.plot(points[a:b,0],points[a:b,1],color='#354451',linewidth=.4)
        ax.set(xlim=(-125,-66),ylim=(24,50),title=title);ax.set_aspect(1.25);ax.set_xticks([]);ax.set_yticks([])
    fig.colorbar(im,ax=axes,orientation='horizontal',shrink=.8,pad=.025,label='Snowfall water-equivalent departure (inches) · blue = positive')
    fig.suptitle('March 2027 · September 5, 2026 06Z\nResearch candidate · 1982–2010 reference',fontsize=15,weight='bold')
    fig.supxlabel('RESEARCH ONLY · 12 historical cycles/year interpolated to the 24 requested cycle dates\n'
                  'Snowfall derived before interpolation and averaging. Native snowfall totals are unchanged.',fontsize=10)
    fig.savefig(directory/'cfsv2-interpolated-reference.png',dpi=140);plt.close(fig)

def main(args):
    directory=Path(args.pilot);out=Path(args.output);out.mkdir(parents=True,exist_ok=True);cache=Path(args.cache)
    pilot=json.loads((directory/'report.json').read_text());mix=json.loads((directory/'lead-mix-report.json').read_text())
    years=[int(y) for y in pilot['historical_years']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        dates=list(pool.map(lambda t:brackets(t[0],cache,t[1],t[2]),zip(years,mix['august_dates'],pilot['historical_dates'])))
        samples=list(pool.map(lambda init:p.cycle(init,str(int(init[:4])+1)+'03',cache,True),
                              [d+h for group in dates for d in group for h in ('00','06','12','18')]))
    with np.load(directory/'pilot-grids.npz') as z:grids={k:z[k] for k in z.files}
    with np.load(directory/'lead-mix-grids.npz') as z:weighted=z['departure'].copy()
    for sample in samples:
        if not(np.array_equal(sample['lons'],grids['lons']) and np.array_equal(sample['lats'],grids['lats'])):raise ValueError('Historical grid mismatch')
    annual=[];all_weights=[]
    for year in years:
        reference,weights=annual_reference([s for s in samples if s['init'].startswith(str(year))],cycle_window(year))
        annual.append(reference);all_weights.append(dict(initialization_year=year,weights=weights))
    annual=np.array(annual);reference=annual.mean(axis=0);departure=grids['forecast']-reference
    omitted=(annual.sum(axis=0)-annual)/(len(annual)-1)
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as z:points=z['states_points'];offsets=z['states_offsets']
    mask=conus_mask(grids['lons'],grids['lats'],points,offsets);area=cell_weights(grids['lats'],len(grids['lons']))
    point_results=[]
    for name,y,x in p.POINTS:
        j=np.abs(grids['lats']-y).argmin();i=np.abs(grids['lons']-x).argmin()
        point_results.append(dict(location=name,existing=float(grids['published_method_departure'][j,i]),
            weighted_candidate=float(weighted[j,i]),interpolated_candidate=float(departure[j,i]),
            omitted_winter_min=float((grids['forecast'][j,i]-omitted[:,j,i]).min()),omitted_winter_max=float((grids['forecast'][j,i]-omitted[:,j,i]).max())))
    np.savez_compressed(out/'interpolated-reference.npz',lons=grids['lons'],lats=grids['lats'],reference=reference,departure=departure,
                        annual_reference=annual,initialization_years=np.array(years),
                        existing_departure=grids['published_method_departure'],change=departure-grids['published_method_departure'])
    result=dict(status='RESEARCH_INTERPOLATED_REFERENCE_NOT_PUBLISHED',anchor='2026090506',target='202703',
        historical_years=years,historical_cycles=len(samples),requested_reference_cycles_per_year=24,
        method='Snowfall derived per historical forecast, then same-hour linear interpolation to each requested date, then cycle/winter averaging.',
        date_groups=dates,annual_weights=all_weights,points=point_results,
        comparison_with_existing=summarize(grids['published_method_departure'],departure,mask,area),
        comparison_with_weighted_candidate=summarize(weighted,departure,mask,area),
        source_records=[dict(init=s['init'],sources=s['sources']) for s in samples],
        limitations=['Interpolation is an estimated reference, not 24 observed historical forecast cycles.',
                     'No extrapolation beyond the five-day historical brackets; only the same initialization hour is used.',
                     'Monthly phase estimation remains approximate; native accumulation is unchanged.',
                     'Only March at this September anchor has been reviewed; other anchors and periods require their own references.'])
    (out/'interpolated-reference.json').write_text(json.dumps(result,indent=2)+'\n')
    plot(out)
    print(json.dumps(dict(points=point_results,comparison=result['comparison_with_weighted_candidate']),indent=2))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--cache',required=True);a.add_argument('--pilot',required=True);a.add_argument('--output',required=True)
    main(a.parse_args())
