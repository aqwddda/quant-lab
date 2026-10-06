"""Load only frozen local datasets; verify before selection, never repair files."""
import json
from pathlib import Path
import pandas as pd
from quant_lab.data.manifest import file_sha256, safe_component
from quant_lab.data.schema import BAR_COLUMNS, PRICE_BASES
from quant_lab.data.store import DataStore
from quant_lab.data.validation import validate_daily_bars, validate_market_data


def date_range(start, end):
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if (pd.isna(first) or pd.isna(last) or first.tzinfo is not None or last.tzinfo is not None
            or first != first.normalize() or last != last.normalize() or first > last):
        raise ValueError('start_date must not exceed end_date; require timezone-naive session dates')
    return first, last


def _legacy_file(path, symbol, start, end, require_metadata=True):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'Frozen dataset missing: {path}. Run download separately.')
    checksum = file_sha256(path)
    metadata_path = path.with_suffix('.metadata.json')
    if metadata_path.exists():
        with metadata_path.open() as handle:
            metadata = json.load(handle)
        if metadata.get('sha256') != checksum or metadata.get('symbol') != symbol or metadata.get('auto_adjust') is not True:
            raise ValueError('Legacy provenance/checksum/price basis mismatch')
    elif require_metadata:
        raise FileNotFoundError(f'Frozen legacy metadata missing: {metadata_path}')
    else:
        metadata = {'symbol': symbol, 'sha256': checksum,
                    'assumptions': ['Explicit compatibility file has no provider metadata; provenance is not verified.']}
    data = pd.read_parquet(path)
    validate_market_data(data)
    if metadata_path.exists():
        if (metadata.get('rows') != len(data) or metadata.get('actual_start') != str(data.date.iloc[0].date())
                or metadata.get('actual_end') != str(data.date.iloc[-1].date())):
            raise ValueError('Legacy manifest rows/date range mismatch')
    original_dtype = str(data.date.dtype)
    data = data.copy()
    data['date'] = data.date.astype('datetime64[ns]')
    data['symbol'] = symbol
    data = data[BAR_COLUMNS]
    validate_daily_bars(data, 'US')
    selected = data.loc[data.date.between(start, end)].reset_index(drop=True)
    validate_daily_bars(selected, 'US')
    manifest = {'schema_version': 1, 'dataset_id': f'legacy_{symbol}_{checksum[:16]}',
                'provider': metadata.get('provider', 'unverified'), 'market': 'US', 'symbols': [symbol],
                'price_basis': 'legacy_provider_adjusted', 'normalized_sha256': checksum,
                'frequency': '1d', 'rows': len(data),
                'actual_start': str(data.date.min().date()), 'actual_end': str(data.date.max().date()),
                'requested_start': metadata.get('requested_start', str(data.date.min().date())),
                'requested_end_inclusive': metadata.get('requested_end_inclusive', str(data.date.max().date())),
                'normalized_files': {'bars': {'path': str(path), 'sha256': checksum}},
                'legacy_metadata': metadata, 'assumptions': metadata.get('assumptions', [])}
    if metadata_path.exists():
        manifest['metadata_file'] = {'path': str(metadata_path), 'sha256': file_sha256(metadata_path)}
    selected.attrs.update({'manifests': [manifest], 'price_basis': 'legacy_provider_adjusted',
                           '_legacy_date_dtype': original_dtype})
    return selected


def load_bars(market, symbols, start, end, frequency='1d', price_basis='raw', *,
              store=None, dataset_id=None, legacy_path=None, require_legacy_metadata=True):
    store = store or DataStore()
    first, last = date_range(start, end)
    if market not in {'US', 'CN'} or frequency != '1d':
        raise ValueError('Only US/CN daily bars supported')
    if not isinstance(symbols, (list, tuple)) or not symbols or len(symbols) != len(set(symbols)):
        raise ValueError('symbols must be a nonempty unique list')
    for symbol in symbols:
        safe_component(symbol)
    if price_basis not in PRICE_BASES:
        raise ValueError(f'Unknown price basis: {price_basis}')
    if price_basis == 'legacy_provider_adjusted':
        if market != 'US' or len(symbols) != 1:
            raise ValueError('Legacy compatibility supports one US symbol')
        if dataset_id is not None:
            raise ValueError('V2 dataset_id cannot select a legacy adjusted file; use legacy_path')
        path = legacy_path or store.root / 'data' / 'raw' / f'{symbols[0].lower()}_daily.parquet'
        return _legacy_file(path, symbols[0], first, last, require_legacy_metadata)
    if legacy_path is not None:
        raise ValueError('legacy_path requires legacy_provider_adjusted')
    manifests = store.locate(market, symbols, str(first.date()), str(last.date()), dataset_id)
    pieces = []
    for manifest in manifests:
        frames = store.verify(manifest)
        bars = frames['bars']
        selected = bars.loc[bars.symbol.isin(symbols) & bars.date.between(first, last)].copy()
        if price_basis != 'raw':
            from quant_lab.data.adjustment import adjust_bars
            selected = adjust_bars(selected, frames.get('adjustments'), method=price_basis, anchor_end=last)
        pieces.append(selected)
    # Frozen components were validated before ordering the constructed result.
    data = pd.concat(pieces, ignore_index=True).sort_values(['date', 'symbol'], kind='stable').reset_index(drop=True)
    validate_daily_bars(data, market)
    if set(data.symbol) != set(symbols):
        raise ValueError('Requested symbols have no observations in selected range')
    data.attrs.update({'manifests': manifests, 'price_basis': price_basis})
    return data


def verify_dataset(*, dataset_id=None, manifest_path=None, legacy_path=None, store=None):
    """Independent local verification for inspection tools, including the V1 adapter."""
    store = store or DataStore()
    if sum(value is not None for value in [dataset_id, manifest_path, legacy_path]) != 1:
        raise ValueError('Specify exactly one dataset_id, manifest_path, or legacy_path')
    if legacy_path is not None:
        path = Path(legacy_path)
        with path.with_suffix('.metadata.json').open() as handle:
            metadata = json.load(handle)
        data = load_bars('US', [metadata['symbol']], metadata['requested_start'], metadata['requested_end_inclusive'],
                         price_basis='legacy_provider_adjusted', legacy_path=path, store=store)
        return data.attrs['manifests'][0], {'bars': data}
    if manifest_path is None:
        manifest = store.load_manifest(dataset_id)
    else:
        from quant_lab.data.manifest import read_manifest
        manifest = read_manifest(manifest_path)
    return manifest, store.verify(manifest)
