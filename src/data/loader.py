"""Read current frozen datasets by explicit ID; never download or repair."""
import pandas as pd
from src.data.manifest import read_manifest
from src.data.schema import PRICE_BASES
from src.data.store import DataStore


def verify_dataset(*, dataset_id=None, manifest_path=None, store=None):
    store = store or DataStore()
    if (dataset_id is None) == (manifest_path is None):
        raise ValueError('Specify exactly one dataset_id or manifest_path')
    manifest = store.load_manifest(dataset_id) if manifest_path is None else read_manifest(manifest_path)
    return manifest, store.verify(manifest)


def load_dataset(dataset_id, *, store=None, symbols=None, start=None, end=None,
                 timeframe=None, price_basis='raw'):
    """Read verified UTC observations, then select symbols and bar-start bounds."""
    from src.market import Timeframe
    store = store or DataStore()
    manifest = store.load_manifest(dataset_id)
    frames = store.verify(manifest)
    actual_timeframe = Timeframe.parse(manifest['timeframe'])
    if timeframe is not None and Timeframe.parse(timeframe) != actual_timeframe:
        raise ValueError('Dataset timeframe mismatch')
    bars = frames['bars'].copy(deep=True)
    if symbols is not None:
        if not symbols or len(symbols) != len(set(symbols)) or not set(symbols).issubset(manifest['symbols']):
            raise ValueError('Requested symbol mismatch')
        bars = bars.loc[bars.symbol.isin(symbols)].copy()
    for boundary in (start, end):
        if boundary is not None:
            stamp = pd.Timestamp(boundary)
            if stamp.tzinfo is None:
                raise ValueError('Range boundaries require timezone')
    if start is not None and end is not None and pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError('start must not exceed end')
    if start is not None:
        bars = bars.loc[bars.timestamp >= pd.Timestamp(start)]
    if end is not None:
        bars = bars.loc[bars.timestamp <= pd.Timestamp(end)]
    if price_basis not in PRICE_BASES:
        raise ValueError(f'Unknown price basis: {price_basis}')
    if price_basis != 'raw':
        if 'date' not in bars:
            raise ValueError('Adjustment data unavailable for this dataset')
        from src.data.adjustment import adjust_bars
        zone = manifest.get('session_timezone') or 'UTC'
        anchor_end = (pd.Timestamp(end).tz_convert(zone).tz_localize(None).normalize()
            if end is not None else bars.date.max())
        bars = adjust_bars(bars, frames.get('adjustments'), method=price_basis, anchor_end=anchor_end)
    from src.data.validation import validate_bars
    bars = bars.reset_index(drop=True)
    validate_bars(bars, actual_timeframe)
    bars.attrs.update({'manifests': [manifest], 'price_basis': price_basis,
        'timeframe': actual_timeframe.value, 'timestamp_semantics': 'bar_start'})
    return bars


def iter_bars(frame, timeframe=None):
    """DataFrame adapter outside Chan; never fabricates unknown volume."""
    from src.market import Bar, Timeframe
    from src.data.schema import OPTIONAL_BAR_COLUMNS
    from src.data.validation import validate_bars
    timeframe = Timeframe.parse(timeframe or frame.attrs.get('timeframe', '1d'))
    validate_bars(frame, timeframe)
    for row in frame.to_dict('records'):
        yield Bar(timestamp=row['timestamp'].to_pydatetime(), symbol=row['symbol'],
            open=row['open'], high=row['high'], low=row['low'], close=row['close'],
            timeframe=timeframe, **{key: row[key] for key in OPTIONAL_BAR_COLUMNS if key in row})
