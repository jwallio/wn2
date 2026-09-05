"""Plot the expanded research screen without suggesting a production correction."""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(source,destination):
    report=json.loads(Path(source).read_text())
    stations=[s for s in report['stations'] if 'walk_forward' in s['scores']]
    if not stations:raise ValueError('No walk-forward validation results')
    fig,axes=plt.subplots(1,2,figsize=(13,8),sharey=True,gridspec_kw={'width_ratios':[1,1]})
    y=np.arange(len(stations))
    ax=axes[0]
    for offset,key,color,label in [(-.23,'raw','#7c8b9c','Raw native snow'),(0,'corrected','#346bb2','Historical ratio correction'),
                                   (.23,'climatology','#d78728','Observed climatology')]:
        values=[s['scores']['walk_forward']['groups']['all'][key]['mae'] for s in stations]
        ax.barh(y+offset,values,height=.22,color=color,label=label)
    ax.set_title('All held-out March cases',fontsize=12)
    ax.set_xlabel('Mean absolute error · snowfall inches')
    ax=axes[1]
    for offset,group,color,label in [(-.16,'all','#346bb2','All cases'),(.16,'measurable_snow','#d78728','Measurable-snow cases')]:
        values=[]
        for station in stations:
            g=station['scores']['walk_forward']['groups'].get(group)
            values.append(g['corrected']['mae']-g['climatology']['mae'] if g else np.nan)
        ax.barh(y+offset,values,height=.30,color=color,label=label)
    ax.axvline(0,color='#333333',linewidth=.9)
    ax.set_title('Does correction beat climatology?',fontsize=12)
    ax.set_xlabel('Corrected error minus climatology error (inches)\nNegative = better · positive = worse')
    ax.legend(loc='upper right',fontsize=8)
    for ax in axes:
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_yticks(y,labels=[s['sid'][1:] for s in stations]);axes[0].invert_yaxis()
    axes[0].legend(loc='lower right',fontsize=8)
    fig.suptitle('CFSv2 March snowfall · 24-cycle historical validation',fontsize=17,y=.97)
    fig.text(.08,.025,'Research only · initialize Aug 30–Sep 5, 2011–2023 · fit earlier winters only, minimum 5\n'
             'Lower error is better. Missing snowy-case bars mean no measurable snow in eligible validation years.\n'
             'Station sample is exploratory; these results do not authorize a CONUS map correction.',fontsize=9)
    fig.tight_layout(rect=(.04,.10,1,.94));fig.savefig(destination,dpi=170);plt.close(fig)


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
