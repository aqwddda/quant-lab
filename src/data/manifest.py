"""JSON manifests and content hashes; no provider imports or network calls."""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re

REQUIRED = {'schema_version', 'dataset_id', 'provider', 'provider_version', 'market',
            'asset_type', 'symbols', 'frequency', 'requested_start', 'requested_end_inclusive',
            'actual_start', 'actual_end', 'price_data', 'rows', 'date_semantics',
            'downloaded_at_utc', 'source_sha256', 'normalized_sha256', 'normalizer_version',
            'assumptions', 'source_files', 'normalized_files'}


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


def iso_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Dates must use YYYY-MM-DD format')
    return parsed


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or not REQUIRED.issubset(manifest):
        raise ValueError('Manifest schema mismatch')
    if manifest['schema_version'] != 2 or manifest['normalizer_version'] != 2:
        raise ValueError('Unsupported manifest/normalizer version')
    for field in ['provider_version', 'asset_type', 'date_semantics']:
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f'Invalid manifest {field}')
    for name in ['dataset_id', 'provider']:
        safe_component(manifest[name])
    symbols = manifest['symbols']
    if not isinstance(symbols, list) or not symbols or len(symbols) != len(set(symbols)):
        raise ValueError('Manifest symbols must be a nonempty unique list')
    for symbol in symbols:
        safe_component(symbol)
    if manifest['market'] not in {'US', 'CN'} or manifest['frequency'] != '1d':
        raise ValueError('Unsupported market/frequency')
    if type(manifest['rows']) is not int or manifest['rows'] <= 0:
        raise ValueError('Invalid manifest rows')
    start, end, actual_start, actual_end = [iso_date(manifest[k]) for k in
        ['requested_start', 'requested_end_inclusive', 'actual_start', 'actual_end']]
    if not start <= actual_start <= actual_end <= end:
        raise ValueError('Manifest date range mismatch')
    timestamp = datetime.fromisoformat(manifest['downloaded_at_utc'])
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError('downloaded_at_utc must have UTC timezone')
    if not isinstance(manifest['assumptions'], list) or not all(isinstance(x, str) for x in manifest['assumptions']):
        raise ValueError('Manifest assumptions must be strings')
    prices = manifest['price_data']
    if not isinstance(prices, dict) or not all(type(prices.get(k)) is bool for k in
        ['raw_ohlc', 'adjustment_available', 'provider_adjusted_available']):
        raise ValueError('Manifest price semantics missing')
    if not prices['raw_ohlc']:
        raise ValueError('V2 datasets must retain raw OHLC')
    for key in ['source_files', 'normalized_files']:
        files = manifest[key]
        if not isinstance(files, dict) or 'bars' not in files:
            raise ValueError(f'Manifest missing {key} bars')
        for entry in files.values():
            if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
                raise ValueError('Invalid manifest file entry')
            path = Path(entry['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Manifest paths must be relative and contained in the store')
            if not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
                raise ValueError('Invalid SHA-256')
    if manifest['source_sha256'] != manifest['source_files']['bars']['sha256'] or manifest['normalized_sha256'] != manifest['normalized_files']['bars']['sha256']:
        raise ValueError('Manifest primary checksum mismatch')
    if prices['adjustment_available'] != ('adjustments' in manifest['normalized_files']):
        raise ValueError('Manifest adjustment availability mismatch')
    json.dumps(manifest, allow_nan=False)


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
