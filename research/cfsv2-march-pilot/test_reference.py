"""Research-only checks; require the pilot's isolated ecCodes environment."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import cfsv2_march_pilot as pilot
from cfsv2_native_bias_screen import evaluate, leave_one_winter_out, walk_forward, cycle_window, ensemble_year


class MarchPilotTests(unittest.TestCase):
    def samples(self):
        rows=[]
        for year,temp,precip in [(2000,270.,2.),(2001,280.,6.)]:
            for hour in ['00','06','12','18']:
                a=np.array([[temp]])
                p=np.array([[precip]])
                rows.append(dict(init=f'{year}0903{hour}',t2m=a,t850=a,precip=p,
                                 snow=pilot.phase_snow(a,a,p,'202703')))
        return rows

    def test_transform_before_averaging_preserves_historical_mean(self):
        rows=self.samples()
        reference,wrong,years=pilot.historical_reference(rows)
        np.testing.assert_allclose(reference,np.mean([r['snow'] for r in rows],axis=0))
        self.assertGreater(abs(float((reference-wrong)[0,0])),.1)
        # In-sample zero-mean anomaly is algebraic consistency, NOT skill validation.
        self.assertAlmostEqual(float(np.mean([r['snow']-reference for r in rows])),0.)
        self.assertEqual(years,['2000','2001'])

    def test_incomplete_or_duplicate_cycles_are_rejected(self):
        rows=self.samples()
        with self.assertRaises(ValueError):pilot.historical_reference(rows[:-1])
        with self.assertRaises(ValueError):pilot.historical_reference(rows+[rows[0]])

    def test_record_identity_calendar_rollover_and_final_record(self):
        index='1:0:d=2009090300:PRATE:surface:6-7 month ave fcst:\n2:40:d=2009090300:SRWEQ:surface:6-7 month ave fcst:'
        self.assertEqual(pilot.record_range(index,'PRATE:surface','2009090300','201003'),(0,39))
        self.assertEqual(pilot.record_range(index,'SRWEQ:surface','2009090300','201003'),(40,None))
        with self.assertRaises(ValueError):pilot.record_range(index,'PRATE:surface','2009090300','201004')
        with self.assertRaises(ValueError):pilot.record_range(index,'TMP:850 mb','2009090300','201003')

    def test_phase_matches_production(self):
        for temp in [-15.,-1.,0.,2.,8.]:
            got=pilot.phase_snow(np.array([temp+273.15]),np.array([temp+273.15]),np.array([4.]),'202703')
            self.assertAlmostEqual(float(got[0]),4*pilot.cf.snowfall_fraction_from_temperature_c(temp,'MAM'))

    def test_validation_observations_do_not_change_fitted_correction(self):
        years=list(range(2011,2024))
        raw=np.arange(1,14,dtype=float)
        observed=raw*.3
        first=evaluate(years,raw,observed)
        observed[8:]+=100
        second=evaluate(years,raw,observed)
        self.assertAlmostEqual(first['factor'],.3)
        self.assertEqual(first['factor'],second['factor'])
        self.assertGreater(second['corrected']['mae'],first['corrected']['mae'])
        with self.assertRaises(ValueError):evaluate(years[:5],raw[:5],observed[:5])

    def test_leave_one_out_factor_excludes_target_observation(self):
        raw=np.arange(1,14,dtype=float)
        obs=raw*.3
        first=leave_one_winter_out(raw,obs)
        obs[0]=1000
        second=leave_one_winter_out(raw,obs)
        self.assertEqual(first['factors'][0],second['factors'][0])
        self.assertNotEqual(first['factors'][1],second['factors'][1])

    def test_window_matches_production_across_month_boundary(self):
        window=cycle_window(2026)
        self.assertEqual(set(window),set(pilot.cf.rolling_cycle_inits('2026090506',24)))
        self.assertEqual(len(window),24)
        self.assertEqual(sum(i[4:6]=='08' for i in window),6)
        self.assertEqual(window[0],'2026083012')
        self.assertEqual(window[-1],'2026090506')

    def test_partial_ensemble_is_not_averaged(self):
        def fake(init,cache):
            return dict(init=init,status='unavailable' if init.endswith('06') else 'available',
                        lons=np.array([0]),lats=np.array([0]),depth=np.array([[10.]]))
        with patch('cfsv2_native_bias_screen.native_cycle',side_effect=fake):
            result=ensemble_year(2011,Path('/unused'))
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('depth',result)
        self.assertEqual(len(result['cycles']),24)

    def test_walk_forward_cannot_see_present_or_future_observations(self):
        years=list(range(2011,2024));raw=np.arange(1,14,dtype=float);obs=raw*.3
        first=walk_forward(years,raw,obs)
        obs[5:]+=1000
        second=walk_forward(years,raw,obs)
        self.assertEqual(first['cases'][0]['factor'],second['cases'][0]['factor'])
        self.assertEqual(first['cases'][0]['climatology'],second['cases'][0]['climatology'])
        self.assertNotEqual(first['cases'][1]['factor'],second['cases'][1]['factor'])


if __name__=='__main__':unittest.main()
