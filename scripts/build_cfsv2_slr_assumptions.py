"""Build explicit owner-selected SLR fills on the verified CWA geometry.

Usage: python scripts/build_cfsv2_slr_assumptions.py /path/to/w_16ap26.zip
The original measured lookup remains unchanged. Runtime needs only NumPy/JSON.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile
import numpy as np
import render_cfsv2_cwa_snapshot as cwa

RATIOS = {'PSR':10., 'BMX':8., 'CAE':8., 'CHS':8., 'ILM':8., 'JAN':8.,
          'LCH':7., 'LIX':7., 'MOB':7., 'TAE':7., 'JAX':7., 'KEY':7.,
          'MFL':7., 'MLB':7., 'TBW':7.}


def spans(mask):
    indices=np.flatnonzero(mask)
    if not len(indices):return []
    breaks=np.flatnonzero(np.diff(indices)>1)+1
    return [[int(a[0]),int(a[-1])+1] for a in np.split(indices,breaks)]


def build(archive_path):
    root=Path(__file__).with_name('data')
    meta=json.loads((root/'cfsv2_cwa_slr_v1.json').read_text())
    if hashlib.sha256(archive_path.read_bytes()).hexdigest()!=meta['boundary_sha256']:
        raise ValueError('Unexpected CWA boundary release')
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive_path) as z:z.extractall(tmp)
        geometry=cwa.read_cwas(next(Path(tmp).glob('*.shp')))
    with np.load(root/'cfsv2_cwa_slr_v1.npz') as z:data={k:z[k] for k in z.files}
    assert not set(RATIOS)&set(meta['supported_cwas'])
    result={'schema_version':1,'status':'owner_assumed_not_measured_CIPS',
            'base_lookup_sha256':meta['lookup_sha256'],
            'boundary_sha256':meta['boundary_sha256'],'ratios':RATIOS,
            'reasons':{'PSR':'Use neighboring TWC measured mean (10:1), per owner.',
                       '8':'Owner-selected Southeast assumption.',
                       '7':'Owner-selected Gulf Coast / Florida assumption.'},
            'unsupported_cwas':sorted(set(meta['unsupported_cwas'])-set(RATIOS))}
    for name,x,y in [('native','lons','lats'),('display','display_lons','display_lats')]:
        xx,yy=np.meshgrid(data[x],data[y]);_,codes=cwa.ratio_grid(xx,yy,geometry,RATIOS)
        result[name+'_spans']={code:spans((codes==code)&np.isnan(data[name+'_ratios'])) for code in RATIOS}
    # The baseline builder writes missing polygon rings in geometry order.
    # Verify each ring exactly before assigning a code to its hatching.
    ring_codes=[]
    for code,geo in geometry.items():
        if code in meta['supported_cwas']:continue
        for poly in (list(geo.geoms) if geo.geom_type=='MultiPolygon' else [geo]):
            i=len(ring_codes);a,b=data['missing_offsets'][i:i+2]
            np.testing.assert_array_equal(data['missing_points'][a:b],np.asarray(poly.exterior.coords))
            ring_codes.append(code)
    assert len(ring_codes)==len(data['missing_offsets'])-1
    result['retained_missing_rings']=[i for i,c in enumerate(ring_codes) if c not in RATIOS]
    path=root/'cfsv2_slr_assumptions_v1.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(path, result['unsupported_cwas'])

if __name__=='__main__':build(Path(sys.argv[1]))
