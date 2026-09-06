"""Versioned, checksummed derived caches. No network or decoding fallbacks."""
import functools
import hashlib
import inspect
import json
from pathlib import Path
from cfsv2_seasonal import read_grid_state, write_grid_state

VERSION = 'science-v1-dai-t850'


def location(root, kind, identity):
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return Path(root) / 'derived' / VERSION / kind / digest


def save(path, grids, metadata):
    path.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, grid in grids.items():
        target = path / (name + '.csv.gz')
        temporary = path / (name + '.tmp.csv.gz')
        write_grid_state(grid, temporary)
        temporary.replace(target)
        checksums[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    tmp = path / 'metadata.tmp'
    tmp.write_text(json.dumps({'checksums': checksums, 'metadata': metadata}))
    tmp.replace(path / 'metadata.json')


def load(path):
    info = json.loads((path / 'metadata.json').read_text())
    grids = {}
    for name, expected in info['checksums'].items():
        target = path / (name + '.csv.gz')
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError('derived cache checksum mismatch')
        grids[name] = read_grid_state(target)
    return grids, info['metadata']


def cached_climatology(function):
    signature = inspect.signature(function)
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        a = bound.arguments
        # Include init year to preserve existing target-calendar behavior exactly.
        identity = {k: a.get(k) for k in ('init','lead','climo_start','climo_end','product_spec')}
        path = location(a['cache_dir'], function.__name__, identity)
        if not a['force']:
            try:
                grids, sources = load(path)
                return grids['climatology'], sources, a['last_request']
            except (OSError, ValueError, KeyError):
                pass
        grid, sources, last = function(*args, **kwargs)
        save(path, {'climatology':grid}, sources)
        return grid, sources, last
    return wrapped
