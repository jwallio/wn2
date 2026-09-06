"""Apply documented owner assumptions without modifying measured CIPS ratios."""
import json
from pathlib import Path
import numpy as np


def apply(data, meta):
    path=Path(__file__).with_name('data')/'cfsv2_slr_assumptions_v1.json'
    fill=json.loads(path.read_text())
    if fill['schema_version']!=1 or fill['base_lookup_sha256']!=meta['lookup_sha256']:
        raise ValueError('SLR assumption geometry does not match the measured lookup')
    if set(fill['ratios']) & set(meta['supported_cwas']):
        raise ValueError('Assumptions cannot replace measured CIPS ratios')
    for name in ('native','display'):
        flat=data[name+'_ratios'].reshape(-1)
        for code,spans in fill[name+'_spans'].items():
            value=fill['ratios'][code]
            if not 0 < value <= 25:raise ValueError('Invalid assumed SLR')
            for start,end in spans:
                if not 0 <= start < end <= flat.size or not np.isnan(flat[start:end]).all():
                    raise ValueError('Assumed SLR fill overlaps measured data or invalid geometry')
                flat[start:end]=value
    rings=[]
    for i in fill['retained_missing_rings']:
        a,b=data['missing_offsets'][i:i+2]
        rings.append(data['missing_points'][a:b])
    data['missing_points']=np.concatenate(rings) if rings else np.empty((0,2))
    data['missing_offsets']=np.cumsum([0]+[len(r) for r in rings])
    data['florida_display_rings']=[np.asarray(r) for r in fill['florida_display_rings']]
    meta['florida_display_policy']=fill['florida_display_policy']
    meta['measured_supported_cwas']=meta['supported_cwas'][:]
    meta['assumed_ratios']=fill['ratios']
    meta['assumption_status']=fill['status']
    meta['assumption_reasons']=fill['reasons']
    meta['supported_cwas']=sorted(set(meta['supported_cwas'])|set(fill['ratios']))
    meta['unsupported_cwas']=fill['unsupported_cwas']
    meta['description']='Measured CIPS CWA ratios with explicit owner-assumed fills; no ratio smoothing.'
    return data,meta
