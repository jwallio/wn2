"""Derived-cache and rendering-only regressions, using tiny deterministic grids."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cansips_seasonal as c
import cansips_cache as cache


class CacheTests(unittest.TestCase):
    def test_checksums_and_climatology_reuse(self):
        calls = []
        @cache.cached_climatology
        def baseline(init,lead,climo_start,climo_end,cache_dir,last_request,force=False):
            calls.append(lead)
            return c.Grid([0.,1.],[0.,1.],[[1.,2.],[3.,4.]]), [{'source':'test'}],last_request+1
        with tempfile.TemporaryDirectory() as tmp:
            args=('2026090100',3,1991,2020,Path(tmp),0.)
            a=baseline(*args);b=baseline(*args)
            self.assertEqual(a[0].values,b[0].values)
            self.assertEqual(calls,[3])
            baseline(*args,force=True)
            self.assertEqual(calls,[3,3])
            next(Path(tmp).rglob('climatology.csv.gz')).write_bytes(b'corrupt')
            baseline(*args)
            self.assertEqual(calls,[3,3,3])

    def test_two_workers_match_serial_grib_decode(self):
        import eccodes as ec
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            inputs=[]
            for field in range(3):
                path=Path(tmp)/f'field{field}.grib'
                with path.open('wb') as stream:
                    for member in range(1,41):
                        h=ec.codes_grib_new_from_samples('regular_ll_sfc_grib2')
                        for key,value in {'Ni':2,'Nj':2,'latitudeOfFirstGridPointInDegrees':1.,
                            'latitudeOfLastGridPointInDegrees':0.,'longitudeOfFirstGridPointInDegrees':0.,
                            'longitudeOfLastGridPointInDegrees':1.,'iDirectionIncrementInDegrees':1.,
                            'jDirectionIncrementInDegrees':1.,'productDefinitionTemplateNumber':1,
                            'perturbationNumber':member,'numberOfForecastsInEnsemble':40}.items():
                            ec.codes_set(h,key,value)
                        ec.codes_set_values(h,np.full(4,field*100+member,dtype=float))
                        ec.codes_write(h,stream);ec.codes_release(h)
                inputs.append((path,('t','t2m','2t'),'test'))
            with patch.object(c,'CANSIPS_GRID_SHAPE',(2,2)):
                c._DECODE_WORKERS=1
                serial=c.decode_snow_inputs(inputs)
                c._DECODE_WORKERS=2
                try:
                    parallel=c.decode_snow_inputs(inputs)
                    for a,b in zip(serial,parallel):
                        self.assertEqual(a[:2],b[:2])
                        np.testing.assert_array_equal(a[2],b[2])
                        self.assertEqual(a[3],b[3])
                finally:
                    if c._DECODE_POOL is not None: c._DECODE_POOL.shutdown()
                    c._DECODE_POOL=None;c._DECODE_WORKERS=1

    def test_render_only_matches_normal_without_loading_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=c.build_parser().parse_args(['--product','precipitation_anomaly','--no-borders'])
            grid=lambda v:c.Grid([0.,1.],[0.,1.],[[v,v],[v,v]])
            forecast=(grid(1.5),{'source_files':[{'url':'test'}]},0.)
            baseline=(grid(1.),[{'url':'hindcast'}],0.)
            callargs=(args,c.PRODUCT_SPECS['precipitation_anomaly'],'2026090100',[3,4,5],[3,4,5],'',root,root/'out',[],None)
            with patch.object(c,'load_ensemble_mean',return_value=forecast), patch.object(c,'hindcast_climatology',return_value=baseline), patch.object(c,'render_standalone') as render:
                entry, failures=c.render_product_run(*callargs)
                expected=[call.args[0].values for call in render.call_args_list]
                self.assertEqual(failures,0)
            args.render_only=True
            with patch.object(c,'load_ensemble_mean',side_effect=AssertionError('model loading forbidden')), patch.object(c,'hindcast_climatology',side_effect=AssertionError('baseline loading forbidden')), patch.object(c,'render_standalone') as render:
                entry,failures=c.render_product_run(*callargs)
                self.assertEqual(failures,0)
                self.assertEqual([call.args[0].values for call in render.call_args_list],expected)
                self.assertEqual(expected[-1],[[1.5,1.5],[1.5,1.5]])
                for p in root.rglob('anomaly.csv.gz'): p.unlink()
                entry,failures=c.render_product_run(*callargs)
                self.assertGreater(failures,0)
                self.assertIn('Render-only cache missing',entry['targets'][0]['error'])

if __name__=='__main__': unittest.main()
