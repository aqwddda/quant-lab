"""JSON manifests and content hashes; no provider imports or network calls."""
import hashlib
import json
from pathlib import Path
import re

def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_component(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_^=.-]+', value) or value in {'.', '..'}:
        raise ValueError(f'Invalid path component: {value!r}')
    return value


def write_manifest(path, manifest):
    validate_manifest(manifest)
    path = Path(path)
    checksum_path = path.with_suffix(path.suffix + '.sha256')
    if path.exists() or checksum_path.exists():
        raise FileExistsError(f'Refusing to overwrite frozen manifest: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
    with checksum_path.open('x') as handle:
        handle.write(file_sha256(path) + '\n')


def read_manifest(path):
    path = Path(path)
    expected = path.with_suffix(path.suffix + '.sha256').read_text().strip()
    if expected != file_sha256(path):
        raise ValueError(f'Manifest checksum mismatch: {path}')
    with path.open() as handle:
        manifest = json.load(handle)
    validate_manifest(manifest)
    return manifest


IDENTITY_KEYS = ['dataset_id', 'provider', 'provider_version', 'instruments', 'timeframe',
    'timestamp_semantics', 'source_timezone', 'aggregation_timezone', 'anchor', 'lineage',
    'price_data', 'session_timezone', 'assumptions', 'normalizer_version']


def validate_manifest(manifest):
    from zoneinfo import ZoneInfo
    import pandas as pd
    from src.market import Instrument, Timeframe
    required = set(IDENTITY_KEYS) | {'schema_version', 'symbols', 'rows', 'actual_start',
        'actual_end', 'downloaded_at_utc', 'source_files', 'normalized_files',
        'source_sha256', 'normalized_sha256'}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise ValueError('Manifest schema mismatch')
    if manifest['schema_version'] != 3 or manifest['normalizer_version'] != 3:
        raise ValueError('Only current schema version 3 is supported')
    for key in ('dataset_id', 'provider'):
        safe_component(manifest[key])
    Timeframe.parse(manifest['timeframe'])
    if manifest['timestamp_semantics'] != 'bar_start':
        raise ValueError('Canonical timestamp_semantics must be bar_start')
    for name in ('source_timezone', 'session_timezone', 'aggregation_timezone'):
        if manifest[name] is not None:
            ZoneInfo(manifest[name])
    if manifest['source_timezone'] is None:
        raise ValueError('Explicit source_timezone is required')
    instruments = manifest['instruments']
    if not isinstance(instruments, list) or not instruments:
        raise ValueError('Manifest instruments required')
    objects = [Instrument(**item) for item in instruments]
    if sorted(x.symbol for x in objects) != manifest['symbols'] or len(set(manifest['symbols'])) != len(objects):
        raise ValueError('Manifest instrument/symbol mismatch')
    for obj in objects:
        safe_component(obj.symbol)
        safe_component(obj.venue)
    if type(manifest['rows']) is not int or manifest['rows'] <= 0:
        raise ValueError('Invalid manifest rows')
    for name in ('actual_start', 'actual_end', 'downloaded_at_utc'):
        stamp = pd.Timestamp(manifest[name])
        if pd.isna(stamp) or stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('Manifest timestamps must be UTC')
    if pd.Timestamp(manifest['actual_start']) > pd.Timestamp(manifest['actual_end']):
        raise ValueError('Manifest timestamp range mismatch')
    if not isinstance(manifest['provider_version'], str) or not manifest['provider_version']:
        raise ValueError('Provider version required')
    if not isinstance(manifest['assumptions'], list) or not all(isinstance(x, str) for x in manifest['assumptions']):
        raise ValueError('Manifest assumptions must be strings')
    prices = manifest['price_data']
    if not isinstance(prices, dict) or prices.get('raw_ohlc') is not True:
        raise ValueError('Datasets must retain explicit raw OHLC')
    for key in ('source_files', 'normalized_files'):
        entries = manifest[key]
        if not isinstance(entries, dict) or 'bars' not in entries:
            raise ValueError('Manifest bars file required')
        for entry in entries.values():
            if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
                raise ValueError('Invalid manifest file entry')
            path = Path(entry['path'])
            if path.is_absolute() or '..' in path.parts or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
                raise ValueError('Invalid manifest path/checksum')
    if manifest['source_sha256'] != manifest['source_files']['bars']['sha256'] or manifest['normalized_sha256'] != manifest['normalized_files']['bars']['sha256']:
        raise ValueError('Manifest primary checksum mismatch')
    lineage = manifest['lineage']
    if lineage is not None:
        required_lineage = {'source_dataset_id','source_timeframe','target_timeframe',
            'aggregation_timezone','anchor','source_normalized_sha256','aggregation_rule'}
        if not isinstance(lineage,dict) or not required_lineage.issubset(lineage):
            raise ValueError('Resampling lineage schema mismatch')
        safe_component(lineage['source_dataset_id'])
        if (lineage['target_timeframe'] != manifest['timeframe']
                or lineage['aggregation_timezone'] != manifest['aggregation_timezone']
                or lineage['anchor'] != manifest['anchor']):
            raise ValueError('Resampling lineage metadata mismatch')
        if not Timeframe.parse(lineage['source_timeframe']).can_resample_to(manifest['timeframe']):
            raise ValueError('Resampling lineage timeframe mismatch')
        if not isinstance(lineage['aggregation_rule'],str) or not lineage['aggregation_rule']:
            raise ValueError('Aggregation rule required')
        if not re.fullmatch('[0-9a-f]{64}',lineage['source_normalized_sha256']):
            raise ValueError('Invalid parent checksum')
    json.dumps(manifest, allow_nan=False)
