import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cfsv2_seasonal as cf
import refresh_cfsv2_native_departures as repair

class RetainedNativeTest(unittest.TestCase):
    def test_retained_run_uses_its_own_native_total_and_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cache=root/'cache'; init='2026090606'; period='202701'
            image=f'public/seasonal/cfsv2/{init}/cfsv2_snowfalla_{period}.jpg'
            native_path=f'cfsv2/{init}/cfsv2_snowfall_lwe_{period}.csv.gz'
            cf.write_grid_state(cf.Grid([0,1],[0,1],[[1.5]*2]*2),cache/'retained-inputs'/native_path)
            base=dict(init_utc='2026-09-06T06:00:00Z',ensemble_members=24)
            anomaly=dict(base,id='old',product='snowfall_anomaly',raw_field='derived',targets=[dict(target_month=period,image=image,lead_month=4)])
            total=dict(base,product='snowfall_accumulation',targets=[dict(target_month=period,native_lwe_grid='public/seasonal/'+native_path,source_files=[{'decoded_field':'SRWEQ:surface'}])])
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'runs':[anomaly,total]}))
            info=dict(method=repair.reference.METHOD,label='native',years='2011-2025',historical_years=list(range(2011,2026)))
            with patch.object(repair.reference,'build') as builder,patch.object(repair.reference,'load_reference',return_value=(cf.Grid([0,1],[0,1],[[.5]*2]*2),info)),patch.object(cf,'render_map') as renderer,patch.object(repair.requests,'get',side_effect=AssertionError('Unexpected download')):
                repair.refresh(manifest,'https://example.com/',cache,root/'bundles',[],output_root=root)
            self.assertEqual(builder.call_args.args[0],init)
            self.assertEqual(renderer.call_args.args[0].values,[[1.]*2]*2)
            updated=json.loads(manifest.read_text())['runs'][0]
            self.assertEqual(updated['raw_field'],'SRWEQ:surface')
            self.assertEqual(updated['targets'][0]['baseline']['method'],repair.reference.METHOD)
            self.assertEqual(updated['targets'][0]['source_files'],total['targets'][0]['source_files'])

if __name__=='__main__':unittest.main()
