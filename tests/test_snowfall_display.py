"""Cross-provider display contract, separate from canonical blending units."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cfsv2_seasonal as cf
import c3s_seasonal as c3s
import cansips_seasonal as can
import seas5_seasonal as seas
import superensemble_seasonal as superensemble
from snowfall_display import depth_departure


class SnowfallDisplay(unittest.TestCase):
    def test_all_providers_use_depth_once_and_common_scale(self):
        from matplotlib.colors import BoundaryNorm, ListedColormap
        original = cf.Grid([0, 1, 2, 3, 4], [0], [[-.2, -.05, 0, .05, .2]])
        specs = [cf.get_product_spec('snowfall_anomaly'),
                 c3s.product_spec('snowfall_anomaly', 'UK Met Office'),
                 can.PRODUCT_SPECS['snowfall_anomaly'],
                 seas.PRODUCT_SPECS['snowfall_anomaly'],
                 superensemble.product_spec('snowfall_anomaly')]
        for spec in specs:
            with self.subTest(title=spec.get('title')):
                grid, display = depth_departure(original, spec, cf.SNOWFALL_ANOMALY_PALETTE)
                self.assertEqual(grid.values, [[-2, -.5, 0, .5, 2]])
                self.assertEqual(original.values, [[-.2, -.05, 0, .05, .2]])
                self.assertIs(depth_departure(grid, display, cf.SNOWFALL_ANOMALY_PALETTE)[0], grid)
                for seasonal in (False, True):
                    low, high, ticks, colors = cf.anomaly_style(display, seasonal)
                    self.assertEqual((low, high), (-10, 10))
                    self.assertEqual(ticks, list(range(-10, 11)))
                    cmap = ListedColormap(colors)
                    norm = BoundaryNorm(ticks, cmap.N)
                    for value in (-.99, 0, .99):
                        self.assertEqual(cmap(norm(value)), (1, 1, 1, 1))
                    for value in (-1.01, 1):
                        self.assertNotEqual(cmap(norm(value)), (1, 1, 1, 1))
                self.assertIn('10:1', display['header_detail'])

    def test_conversion_commutes_with_monthly_sum(self):
        months = [cf.Grid([0, 1], [0], [[v, -v]]) for v in (.2, .3, .5)]
        spec = cf.get_product_spec('snowfall_anomaly')
        combined = depth_departure(cf.sum_grids(months), spec, cf.SNOWFALL_ANOMALY_PALETTE)[0]
        separately = cf.sum_grids([depth_departure(g, spec, cf.SNOWFALL_ANOMALY_PALETTE)[0] for g in months])
        self.assertEqual(combined.values, separately.values)
        self.assertEqual(combined.values, [[10, -10]])

    def test_catalog_holds_unverified_images(self):
        import json
        import tempfile
        import build_seasonal_catalog as catalog
        from snowfall_display import DISPLAY
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'cfsv2' / 'snow.jpg'
            image.parent.mkdir()
            image.write_bytes(b'image fixture')
            target = {'id': 'snow', 'target_month': '202701', 'status': 'rendered',
                      'field': 'snowfall_lwe', 'units': 'in',
                      'valid_start_utc': '2027-01-01T00:00:00Z',
                      'valid_end_utc': '2027-02-01T00:00:00Z',
                      'image': 'public/seasonal/cfsv2/snow.jpg'}
            def normalize():
                return catalog._target_catalog_state('snowfall_anomaly', target,
                    site_root=root, check_assets=True, collector=catalog.IssueCollector(), path='test')[0]
            self.assertNotIn('image', normalize())
            self.assertEqual(normalize()['status'], 'pending')
            image.with_suffix('.snow.json').write_text(json.dumps(DISPLAY))
            verified = normalize()
            self.assertIn('image', verified)
            self.assertEqual(verified['display']['snow_to_liquid_ratio'], 10)
            self.assertTrue(verified['numeric_grid'].endswith('.snow.csv.gz'))


if __name__ == '__main__':
    unittest.main()
