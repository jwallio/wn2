"""Reference application and rejection checks; no NOAA downloads needed."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cfsv2_seasonal as cf
import cfsv2_snow_reference as ref


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.init, self.target = '2026090506', '202703'
        self.cycles = cf.rolling_cycle_inits(self.init, 24)
        self.stem = self.directory / f'snowfall-reference-{self.init}-{self.target}'
        self.grid = dict(lons=np.array([-100., -99.]), lats=np.array([30., 31.]),
                         reference=np.array([[.1, .2], [.3, .4]]))
        self.meta = dict(schema_version=1, method=ref.METHOD, initialization=self.init,
                         target_month=self.target, forecast_cycles=self.cycles, member=1,
                         units='inches_water_equivalent', historical_years=list(range(1982, 2011)),
                         historical_cycles=348)
        self.save()

    def save(self):
        np.savez_compressed(self.stem.with_suffix('.npz'), **self.grid)
        self.meta['grid_sha256'] = hashlib.sha256(self.stem.with_suffix('.npz').read_bytes()).hexdigest()
        self.stem.with_suffix('.json').write_text(json.dumps(self.meta))

    def load(self):
        return ref.load_reference(self.directory, self.init, self.target, self.cycles, 1)

    def args(self):
        return cf.build_parser().parse_args(['--product', 'snowfall_anomaly', '--init', self.init,
            '--lead-months', '6', '--rolling-days', '6', '--snowfall-reference-dir', str(self.directory)])

    def test_adapter_applies_reference_without_changing_forecast(self):
        args = self.args()
        with patch.object(cf, 'load_ncei_calibration', side_effect=AssertionError('No fallback download')):
            grid, info, last_request = cf.load_snowfall_baseline(
                args, self.init, self.target, 6, self.directory, self.directory, '', 123.)
        forecast = cf.Grid(grid.lons[:], grid.lats[:], [[1., 2.], [3., 4.]])
        difference = cf.subtract_grids(forecast, grid)
        np.testing.assert_allclose(difference.values, [[.9, 1.8], [2.7, 3.6]])
        self.assertEqual(forecast.values, [[1., 2.], [3., 4.]])
        self.assertEqual(last_request, 123.)
        self.assertFalse(info['observation_bias_adjustment'])

    def test_metadata_mismatches_rejected(self):
        for key, value in [('initialization', '2026090512'), ('target_month', '202702'),
                           ('units', 'inches_snow_depth'), ('member', 2), ('method', 'other'),
                           ('historical_years', [2010]), ('forecast_cycles', self.cycles[:-1])]:
            with self.subTest(key=key):
                original = self.meta[key]
                self.meta[key] = value
                self.save()
                with self.assertRaises(cf.CFSv2Error):
                    self.load()
                self.meta[key] = original

    def test_corrupt_grid_rejected(self):
        self.stem.with_suffix('.npz').write_bytes(b'bad')
        with self.assertRaises(cf.CFSv2Error):
            self.load()

    def test_invalid_values_rejected(self):
        for value in (-1., float('nan'), float('inf')):
            self.grid['reference'][0, 0] = value
            self.save()
            with self.assertRaises(cf.CFSv2Error):
                self.load()

    def test_decoder_rounding_allowed_but_different_grid_rejected(self):
        grid, _ = self.load()
        forecast = cf.Grid([-100.000001, -99.], grid.lats, [[1., 2.], [3., 4.]])
        aligned = ref.match_forecast_grid(grid, forecast)
        self.assertEqual(aligned.values, grid.values)
        self.assertEqual(aligned.lons, forecast.lons)
        forecast.lons[0] += .1
        with self.assertRaises(cf.CFSv2Error):
            ref.match_forecast_grid(grid, forecast)

    def test_real_wgrib2_csv_coordinates_match_eccodes_reference(self):
        # Actual 2026090512 -> 202703 reference coordinates and the site's
        # wgrib2-decoded 2026090506 March native LWE grid (same global grid).
        reference = cf.Grid(
            [-179.06275195822496, -178.12525326370803],
            [-89.27671287810583, -88.33975425118209],
            [[0.25, 0.5], [0.75, 1.0]])
        forecast = cf.Grid([-179.063, -178.125], [-89.2767, -88.3398],
                           [[1., 2.], [3., 4.]])
        aligned = ref.match_forecast_grid(reference, forecast)
        self.assertIs(aligned.values, reference.values)
        self.assertEqual(cf.subtract_grids(forecast, aligned).values,
                         [[0.75, 1.5], [2.25, 3.]])
        for axis, offset in [('lons', 0.001), ('lats', 0.0001)]:
            shifted = cf.Grid(forecast.lons[:], forecast.lats[:], forecast.values)
            getattr(shifted, axis)[0] += offset
            with self.subTest(axis=axis), self.assertRaises(cf.CFSv2Error):
                ref.match_forecast_grid(reference, shifted)
        with self.assertRaises(cf.CFSv2Error):
            ref.match_forecast_grid(reference, cf.Grid([0.], forecast.lats, [[0.], [0.]]))

    def test_missing_month_preflight_before_decoder(self):
        args = self.args()
        args.lead_months = '5,6'
        with patch.object(cf, 'find_wgrib2', side_effect=AssertionError('Decoder must not run')):
            with self.assertRaises(cf.CFSv2Error):
                cf._run_single_window(args)

    def test_unsafe_options_rejected(self):
        for key, value in [('product', 'snowfall_accumulation'), ('rolling_days', 5),
                           ('rolling_member', 2), ('allow_partial_rolling', True),
                           ('allow_stale_calibration', True), ('absolute', True),
                           ('baseline_label', 'Misleading label')]:
            with self.subTest(key=key):
                args = self.args()
                setattr(args, key, value)
                with self.assertRaises(cf.CFSv2Error):
                    ref.validate_options(args, args.product, self.init, [self.target], self.directory)

    def test_no_mixed_baselines(self):
        args = self.args()
        args.ncei_calibration = True
        with self.assertRaises(cf.CFSv2Error):
            cf._run_single_window(args)

    def test_seasonal_provenance_preserved(self):
        _, info = self.load()
        result = cf.seasonal_baseline_manifest([info], ref.LABEL, None, rolling_init=self.init)
        self.assertEqual(result['years'], '1982-2010')
        self.assertEqual(result['rolling_policy'], info['rolling_policy'])
        self.assertEqual(result['monthly_references'][0]['grid_sha256'], self.meta['grid_sha256'])

    def test_default_is_opt_in(self):
        self.assertIsNone(cf.build_parser().parse_args([]).snowfall_reference_dir)


if __name__ == '__main__':
    unittest.main()
