"""Render a research comparison from computed pilot grids; no network access."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PolygonPath


def main(directory):
    directory=Path(directory)
    with np.load(directory/'pilot-grids.npz') as f:
        z={k:f[k] for k in f.files}
    with np.load(Path(__file__).with_name('data')/'cfsv2_cwa_slr_v1.npz') as f:
        pts=f['states_points'];offsets=f['states_offsets']
    report=json.loads((directory/'report.json').read_text())
    x,y=np.meshgrid(z['lons'],z['lats'])
    mask=np.zeros(x.shape,dtype=bool)
    xy=np.column_stack([x.ravel(),y.ravel()])
    for a,b in zip(offsets[:-1],offsets[1:]):
        mask |= PolygonPath(pts[a:b]).contains_points(xy).reshape(x.shape)
    fig,axs=plt.subplots(3,1,figsize=(11,13),layout='constrained')
    levels=[-2,-1.5,-1,-.75,-.5,-.25,0,.25,.5,.75,1,1.5,2]
    fields=[('published_method_departure','Existing calculation — reconstructed'),
            ('pilot_departure','Historical forecasts calculated individually — pilot'),
            ('change_from_published_method','Pilot minus existing calculation')]
    for ax,(field,title) in zip(axs,fields):
        image=ax.contourf(x,y,np.ma.masked_where(~mask,z[field]),levels=levels,cmap='RdBu',extend='both')
        for a,b in zip(offsets[:-1],offsets[1:]):
            ax.plot(pts[a:b,0],pts[a:b,1],color='#354451',linewidth=.4)
        ax.set(xlim=(-125,-66),ylim=(24,50),title=title)
        ax.set_aspect(1.25);ax.set_xticks([]);ax.set_yticks([])
    fig.colorbar(image,ax=axs,orientation='horizontal',shrink=.8,pad=.025,
                 label='Snowfall water-equivalent departure (inches); blue = positive')
    years=report['historical_years']
    fig.suptitle(f'March 2027 · CFSv2 September 5, 2026 06Z\n'
                 f'Research comparison · {years[0]}–{years[-1]} historical initializations',fontsize=15,weight='bold')
    fig.supxlabel('NOT VALIDATED FOR PUBLICATION · 4 historical vs 24 operational cycles\n'
                  'Includes baseline sampling/smoothing differences; not an observed snowfall bias correction.',fontsize=10)
    fig.savefig(directory/'cfsv2-march-comparison.png',dpi=140)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory')
    main(p.parse_args().directory)
