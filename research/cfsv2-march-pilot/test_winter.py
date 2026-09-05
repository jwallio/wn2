"""Winter source, calendar, seasonal-completeness and validation contracts."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import cfsv2_winter_validation as w


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

    def test_djf_sums_months_before_fitting(self):
        obs=[dict(sid='S',meta={},monthly={'201112':1,'201201':2,'201202':3},sources=[],excluded=[])]
        cycles=[dict(init=init,target=target,status='available',values={'S':value})
                for target,value in zip(w.targets(2011),[4,5,6]) for init in w.march.cycle_window(2011)]
        row=w.build_report(cycles,obs)['stations'][0]['products']['DJF']['rows'][0]
        self.assertEqual((row['raw'],row['observed']),(15,6))

    def test_compact_cache_corruption_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as d:
            cache=Path(d);stem=cache/'native-2011090506-201112'
            stem.with_suffix('.grb2').write_bytes(b'corrupt')
            stem.with_suffix('.json').write_text('{"record_sha256":"wrong","source":{"url":"wrong"}}')
            with patch.object(w.p,'fetch',side_effect=AssertionError('Should not use network')):
                with self.assertRaises(ValueError):w.native_record('2011090506','201112',cache)

    def test_influence_detects_single_validation_winter_dependence(self):
        years=list(range(2011,2024));raw=np.arange(1,14,dtype=float);obs=raw*.3
        result=w.influence(years,raw,obs)
        self.assertEqual(len(result['drop_one_validation_case_differences']),8)
        self.assertEqual(len(result['drop_one_training_winter']),13)
        for item in result['drop_one_training_winter']:
            self.assertLess(item['corrected_mae'],1e-12)


if __name__=='__main__':unittest.main()
