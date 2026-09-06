"""Regression checks for native forecast/reference pairing and calendars."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cfsv2_native_reference as native
import cfsv2_seasonal as cf


class NativeReferenceTests(unittest.TestCase):
    def test_calendar_mapping_preserves_cycle_hour_and_year_crossing(self):
        self.assertEqual(native.historical_cycle('2025123118', 2015, '2026010106'), [('2014123118', 1.)])
        self.assertEqual(native.historical_cycle('2024022918', 2015, '2024030106'), [('2015022818', .5), ('2015030118', .5)])

    def test_native_departure_decoder_never_uses_temperature_phase(self):
        lwe = cf.Grid([0, 1], [0, 1], [[.1, .2], [.3, .4]])
        depth = cf.Grid([0, 1], [0, 1], [[1, 2], [3, 4]])
        args = argparse.Namespace(native_snowfall_departure=True)
        with patch('cfsv2_native_snow.decode', return_value=(depth, [], 24, 24, '24 cycles', 0., {'_native_lwe': lwe})), patch.object(cf, 'derive_snowfall_lwe_grid', side_effect=AssertionError('Phase estimator called')):
            result = cf._decode_snowfall_target_ensemble(args, '2026090606', '202701', [1], [], Path('.'), Path('.'), '', Path('.'), 0.)
        self.assertIs(result[0], lwe)
        self.assertEqual(result[6]['method'], 'native_SRWEQ_departure_v1')

    def test_native_reference_rejects_mixed_seasonal_years(self):
        a = dict(method=native.METHOD, historical_years=[2011, 2012], years='2011-2012', label='native')
        b = dict(a, historical_years=[2012, 2013])
        with self.assertRaises(cf.CFSv2Error):
            cf.seasonal_baseline_manifest([a, b], 'native', None)

    def test_loader_rejects_derived_method_and_wrong_target(self):
        with tempfile.TemporaryDirectory() as d:
            stem = Path(d) / 'snowfall-reference-2026090606-202701'
            stem.with_suffix('.json').write_text(json.dumps({'schema_version': 1, 'method': 'derive_each_forecast_daily_rate_then_same_hour_interpolate_v2'}))
            with self.assertRaises(cf.CFSv2Error):
                native.load_reference(d, '2026090606', '202701', ['2026090606'], 1)


if __name__ == '__main__':
    unittest.main()
