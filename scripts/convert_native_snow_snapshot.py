"""Re-render the retained September 4 native snowfall inputs at fixed 10:1."""
import hashlib
import json
from pathlib import Path
import shutil
import cfsv2_seasonal as cf
import cfsv2_native_snow as native

OLD = '20260904T1200Z-style-a'
NEW = '20260904T1200Z-10-to-1'
PERIODS = {'202701': 'Jan 2027', '202702': 'Feb 2027',
           '202703': 'Mar 2027', 'JFM': 'Jan–Mar 2027'}


def build(root):
    source, output = root / OLD, root / NEW
    output.mkdir(exist_ok=True)
    old = json.loads((source / 'provenance.json').read_text())
    hashes = {}
    for period, label in PERIODS.items():
        lwe_path = source / f'{period}-lwe.csv.gz'
        lwe = cf.read_grid_state(lwe_path)
        depth = native.depth_grid(lwe)
        total_path = output / f'{period}-total.csv.gz'
        cf.write_grid_state(depth, total_path)
        shutil.copyfile(lwe_path, output / lwe_path.name)
        native.render(lwe, '2026090412', '202701' if period == 'JFM' else period,
                      '4–6' if period == 'JFM' else {'202701':4,'202702':5,'202703':6}[period],
                      output / f'{period}-total.png', period == 'JFM', label,
                      '24-cycle mean • Frozen September 4 run')
        for suffix in ('total.csv.gz', 'lwe.csv.gz', 'total.png'):
            path = output / f'{period}-{suffix}'
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {
        'schema_version': 2, 'method': 'native_SRWEQ_times_fixed_10_to_1_v1',
        'snow_to_liquid_ratio': 10, 'status': 'experimental_frozen_snapshot',
        'init_utc': old['init_utc'], 'native_provenance': old['native_provenance'],
        'automatic_refresh': False, 'native_reference_status': 'unavailable',
        'departure_status': 'unavailable', 'periods': list(PERIODS),
        'units': old['units'], 'files_sha256': hashes,
        'presentation': {'white_below_inches': 1, 'saturation_inches': 200},
        'display_method': 'Bilinear native snowfall water equivalent multiplied by 10',
        'numerical_download_method': 'Native grid snowfall water equivalent multiplied by 10, CONUS mask',
        'limitations': ['Unadjusted model forecast; fixed 10:1 is an estimate.',
                       'No matching native snowfall climatology; departures unavailable.',
                       'Display sampling does not increase model resolution.'],
    }
    (output / 'provenance.json').write_text(json.dumps(record, indent=2))
    print(f'Converted four retained native snowfall maps: {output}')


if __name__ == '__main__':
    build(Path(__file__).resolve().parents[1] / 'public/seasonal/cfsv2/native-snowfall')
