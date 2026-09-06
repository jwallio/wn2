"""Plot month-specific chronological skill differences for the research screen."""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(source,destination):
    report=json.loads(Path(source).read_text());labels=['December','January','February','DJF']
    fig,axes=plt.subplots(1,4,figsize=(15,8),sharey=True,layout='constrained')
    y=np.arange(len(report['stations']))
    for ax,label in zip(axes,labels):
        for offset,group,color,name in [(-.16,'all','#346bb2','All cases'),(.16,'measurable_snow','#d78728','Snowy cases')]:
            values=[]
            for station in report['stations']:
                scores=station['products'][label]['scores']
                g=scores.get('walk_forward',{}).get('groups',{}).get(group)
                values.append(g['corrected']['mae']-g['climatology']['mae'] if g else np.nan)
            ax.barh(y+offset,values,height=.3,color=color,label=name)
        ax.axvline(0,color='#333333',linewidth=1);ax.set_title(label)
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);ax.set_xlabel('MAE difference (snow inches)')
    axes[0].set_yticks(y,labels=[s['sid'][1:] for s in report['stations']]);axes[0].invert_yaxis()
    handles,legend_labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='outside upper right',ncol=2)
    fig.suptitle('Does historical bias correction improve CFSv2 winter snowfall?\n'
                 'Chronological validation · correction error minus climatology error',fontsize=16)
    fig.supxlabel('Negative = better than climatology · Positive = worse\n'
                 'Research only · September 5 06Z anchors, 2011–2023 · complete 24-cycle monthly ensembles\n'
                 'DJF requires all three months and is fitted separately. Snowy = observed total ≥0.1 inch.\n'
                 'Panels use different horizontal scales. Missing bars indicate insufficient data or no snowy cases.',fontsize=10)
    fig.savefig(destination,dpi=160);plt.close(fig)


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
