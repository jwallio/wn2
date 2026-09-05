"""Winter source, calendar, seasonal-completeness and validation contracts."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import cfsv2_winter_validation as w
from cfsv2_reference_interpolation import interpolation_weights,annual_reference


class WinterTests(unittest.TestCase):
    def test_leap_february_and_cross_year_targets(self):
        self.assertEqual(w.targets(2019),['201912','202001','202002'])
        self.assertEqual(w.month_seconds('202002'),29*86400)
        self.assertEqual(w.month_seconds('202102'),28*86400)
        rows=[(f'2020-02-{d:02d}','1') for d in range(1,30)]
        self.assertEqual(w.month_total(rows,'202002'),29)
        with self.assertRaises(ValueError):w.month_total(rows[:-1],'202002')
        with self.assertRaises(ValueError):w.month_total(rows+[rows[0]],'202002')
        rows[0]=(rows[0][0],'M')
        with self.assertRaises(ValueError):w.month_total(rows,'202002')

    def test_duplicate_cycles_cannot_stand_in_for_missing_cycle(self):
        cycles=[dict(init='a',status='available',values={'S':2}),dict(init='a',status='available',values={'S':4})]
        self.assertIsNone(w.complete_mean(cycles,['a','b']))

    def test_missing_month_excludes_season_but_preserves_other_months(self):
        observed=[dict(sid='S',meta={},monthly={'201112':1,'201201':2,'201202':3},sources=[],excluded=[])]
        cycles=[dict(init=init,target=target,status='available',values={'S':4})
                for target in ['201112','201201'] for init in w.march.cycle_window(2011)]
        products=w.build_report(cycles,observed)['stations'][0]['products']
        self.assertEqual(len(products['December']['rows']),1)
        self.assertEqual(len(products['January']['rows']),1)
        self.assertEqual(products['DJF']['rows'],[])
        self.assertIn(2011,products['DJF']['excluded_initialization_years'])
        self.assertEqual(products['DJF']['unmatched_observations'][0]['observed'],6)

    def test_djf_sums_months_before_fitting(self):
        obs=[dict(sid='S',meta={},monthly={'201112':1,'201201':2,'201202':3},sources=[],excluded=[])]
        cycles=[dict(init=init,target=target,status='available',values={'S':value})
                for target,value in zip(w.targets(2011),[4,5,6]) for init in w.march.cycle_window(2011)]
        row=w.build_report(cycles,obs)['stations'][0]['products']['DJF']['rows'][0]
        self.assertEqual((row['raw'],row['observed']),(15,6))

    def test_short_fixed_split_does_not_discard_valid_walk_forward_scores(self):
        years=[y for y in range(2011,2024) if y not in (2014,2019,2020,2022)]
        obs=[dict(sid='S',meta={},monthly={t:1. for y in years for t in w.targets(y)},sources=[],excluded=[])]
        cycles=[dict(init=init,target=target,status='available',values={'S':2.})
                for year in years for target in w.targets(year) for init in w.march.cycle_window(year)]
        scores=w.build_report(cycles,obs)['stations'][0]['products']['January']['scores']
        self.assertEqual(scores['walk_forward']['groups']['all']['count'],4)
        self.assertEqual(scores['fixed_split']['status'],'insufficient_data')

    def test_compact_cache_corruption_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as d:
            cache=Path(d);stem=cache/'native-2011090506-201112'
            stem.with_suffix('.grb2').write_bytes(b'corrupt')
            stem.with_suffix('.json').write_text('{"record_sha256":"wrong","source":{"url":"wrong"}}')
            with patch.object(w.p,'fetch',side_effect=AssertionError('Should not use network')):
                with self.assertRaises(ValueError):w.native_record('2011090506','201112',cache)

    def test_offline_missing_inputs_never_request_network(self):
        with tempfile.TemporaryDirectory() as d, patch.object(w.p,'fetch',side_effect=AssertionError('Network')):
            with self.assertRaises(ValueError):w.native_record('2011090506','201112',Path(d),offline=True)
        with tempfile.TemporaryDirectory() as d, patch.object(w.requests,'post',side_effect=AssertionError('Network')):
            with self.assertRaises(ValueError):w.daily_response('S','2011-12-01','2011-12-31',Path(d),offline=True)

    def test_influence_detects_single_validation_winter_dependence(self):
        years=list(range(2011,2024));raw=np.arange(1,14,dtype=float);obs=raw*.3
        result=w.influence(years,raw,obs)
        self.assertEqual(len(result['drop_one_validation_case_differences']),8)
        self.assertEqual(len(result['drop_one_training_winter']),13)
        for item in result['drop_one_training_winter']:
            self.assertLess(item['corrected_mae'],1e-12)

    def test_reference_interpolation_matches_date_and_hour_without_extrapolating(self):
        available=['2000082900','2000090300','2000090800','2000090806']
        self.assertEqual(interpolation_weights('2000090300',available),{'2000090300':1.})
        self.assertEqual(interpolation_weights('2000090500',available),{'2000090300':.6,'2000090800':.4})
        with self.assertRaises(ValueError):interpolation_weights('2000090900',available)
        with self.assertRaises(ValueError):interpolation_weights('2000090506',available)
        with self.assertRaises(ValueError):interpolation_weights('2000090500',['2000082900','2000090800'])

    def test_interpolation_preserves_constant_reference(self):
        samples=[dict(init=d+h,snow=np.array([[2.]])) for d in ['20000829','20000903','20000908'] for h in ['00','06','12','18']]
        reference,weights=annual_reference(samples,w.march.cycle_window(2000))
        self.assertAlmostEqual(float(reference[0,0]),2.)
        self.assertAlmostEqual(sum(weights.values()),1.)
        self.assertTrue(all(v>=0 for v in weights.values()))


if __name__=='__main__':unittest.main()
