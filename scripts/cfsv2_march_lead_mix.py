"""Research sensitivity: 25% August lead 7 + 75% September lead 6.

The five-day reforecast schedule cannot reproduce the exact operational window.
Use the last August date and in-window September date; label this approximation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import numpy as np
import requests
import cfsv2_march_pilot as p


def august_date(year,cache):
    prefix=f'high-priority-subset/monthly-means-9-month/{year}/{year}08/'
    url=requests.Request('GET',p.ARCHIVE,params={'list-type':2,'delimiter':'/','prefix':prefix}).prepare().url
    data,_=p.fetch(url,cache)
    root=ET.fromstring(data)
    if any(x.text=='true' for x in root.iter() if x.tag.endswith('IsTruncated')):
        raise ValueError('Truncated August directory listing')
    dates=sorted({x.text.rstrip('/').split('/')[-1] for x in root.iter()
        if x.tag.endswith('Prefix') and x.text and re.search(r'/\d{8}/$',x.text)})
    if not dates or not 26<=int(dates[-1][-2:])<=31:
        raise ValueError(f'No nearby August reference date for {year}')
    return dates[-1]


def main(args):
    cache=Path(args.cache);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    original=json.loads((Path(args.pilot)/'report.json').read_text())
    years=[int(y) for y in original['historical_years']]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        dates=list(pool.map(lambda year:august_date(year,cache),years))
        samples=list(pool.map(lambda init:p.cycle(init,str(int(init[:4])+1)+'03',cache,True),
                              [d+h for d in dates for h in ('00','06','12','18')]))
    for sample in samples[1:]:
        if not (np.array_equal(sample['lons'],samples[0]['lons']) and
                np.array_equal(sample['lats'],samples[0]['lats'])):
            raise ValueError('August cycle grids differ')
    august,_,used=p.historical_reference(samples)
    if used!=original['historical_years']:raise ValueError('Historical years do not match')
    with np.load(Path(args.pilot)/'pilot-grids.npz') as old:
        if not(np.allclose(samples[0]['lons'],old['lons'],atol=.001,rtol=0) and
               np.allclose(samples[0]['lats'],old['lats'],atol=.001,rtol=0)):
            raise ValueError('Reference grids differ')
        mixed=.25*august+.75*old['historical_reference']
        departure=old['forecast']-mixed
        difference=departure-old['pilot_departure']
        points=[]
        for name,y,x in p.POINTS:
            j=np.abs(old['lats']-y).argmin();i=np.abs(old['lons']-x).argmin()
            points.append(dict(location=name,original_pilot_lwe=float(old['pilot_departure'][j,i]),
                               lead_mix_departure_lwe=float(departure[j,i]),change_lwe=float(difference[j,i])))
        np.savez_compressed(out/'lead-mix-grids.npz',lons=old['lons'],lats=old['lats'],
                            august_reference=august,mixed_reference=mixed,departure=departure,change=difference)
    report=dict(status='RESEARCH_SENSITIVITY_ONLY',august_dates=dates,weights={'august':.25,'september':.75},
        points=points,limitations=['Matches lead proportions, not exact initialization dates or 24 individual cycles.',
        'August date may lie outside the six-day operational window. This is a sensitivity test, not a matched hindcast.',
        'No observational correction or independent predictive validation.'],
        sources=[{'init':s['init'],'sources':s['sources']} for s in samples])
    (out/'lead-mix-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(points,indent=2))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cache',required=True);a.add_argument('--pilot',required=True);a.add_argument('--output',required=True)
    a.add_argument('--workers',type=int,choices=range(1,9),default=4)
    main(a.parse_args())
