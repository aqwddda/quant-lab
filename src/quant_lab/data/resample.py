"""Explicit anchored aggregation. Incomplete windows fail; no synthetic bars."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import pandas as pd
from quant_lab.market import Timeframe
from quant_lab.data.validation import validate_bars_v3


def resample_bars(bars, *, source_timeframe, target_timeframe, aggregation_timezone, anchor):
    source = Timeframe.parse(source_timeframe)
    target = Timeframe.parse(target_timeframe)
    if not source.can_resample_to(target):
        raise ValueError('Incompatible source/target timeframes')
    ZoneInfo(aggregation_timezone)
    if not isinstance(anchor, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', anchor):
        raise ValueError('anchor must be explicit HH:MM')
    validate_bars_v3(bars, source)
    hour, minute = map(int, anchor.split(':'))
    offset = pd.Timedelta(hours=hour, minutes=minute)
    # Bucket in local wall-clock coordinates. DST ambiguous/nonexistent edges
    # raise, rather than silently changing 4H anchoring or producing partial bars.
    local = bars.timestamp.dt.tz_convert(aggregation_timezone).dt.tz_localize(None)
    origin = pd.Timestamp('1970-01-01') + offset
    elapsed = local - origin
    buckets = origin + (elapsed // pd.Timedelta(target.duration)) * pd.Timedelta(target.duration)
    starts = buckets.dt.tz_localize(aggregation_timezone, ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    ends = (buckets + target.duration).dt.tz_localize(aggregation_timezone,
        ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    if not (ends - starts).eq(pd.Timedelta(target.duration)).all():
        raise ValueError('DST changes elapsed window duration; use UTC or another explicit aggregation rule')
    work = bars.copy()
    work['_bucket'] = starts
    work['_end'] = ends
    rows = []
    expected_count = int(target.duration / source.duration)
    for (start, symbol), group in work.groupby(['_bucket', 'symbol'], sort=True):
        expected = pd.date_range(start, periods=expected_count, freq=pd.Timedelta(source.duration))
        if len(group) != expected_count or not pd.DatetimeIndex(group.timestamp).equals(expected):
            raise ValueError(f'Incomplete or misaligned resampling window: {symbol}/{start}; no filling')
        end = group['_end'].iloc[0]
        if 'available_at' in group and (group.available_at > end).any():
            raise ValueError('Source observation is unavailable at target close')
        row = {'timestamp': start, 'symbol': symbol, 'open': group.open.iloc[0],
            'high': group.high.max(), 'low': group.low.min(), 'close': group.close.iloc[-1],
            'available_at': end}
        for column in ('volume', 'tick_volume', 'amount'):
            if column in group:
                row[column] = group[column].sum()
        if 'open_interest' in group:
            row['open_interest'] = group.open_interest.iloc[-1]
        rows.append(row)
    result = pd.DataFrame(rows)
    validate_bars_v3(result, target)
    result.attrs.update({'timeframe': target.value, 'aggregation_timezone': aggregation_timezone,
        'anchor': anchor, 'timestamp_semantics': 'bar_start'})
    return result


def resample_dataset(source_dataset_id, *, target_timeframe, aggregation_timezone, anchor,
                     dataset_id, store=None):
    from quant_lab.data.store import DataStore
    from quant_lab.data.loader import load_dataset
    store = store or DataStore()
    parent = store.load_manifest(source_dataset_id)
    if parent['schema_version'] != 3:
        raise ValueError('Resampling requires V3; legacy session labels are not intraday observations')
    bars = load_dataset(source_dataset_id, store=store)
    target = Timeframe.parse(target_timeframe)
    result = resample_bars(bars, source_timeframe=parent['timeframe'], target_timeframe=target,
        aggregation_timezone=aggregation_timezone, anchor=anchor)
    lineage = {'source_dataset_id': source_dataset_id, 'source_timeframe': parent['timeframe'],
        'target_timeframe': target.value, 'aggregation_timezone': aggregation_timezone,
        'anchor': anchor, 'source_normalized_sha256': parent['normalized_sha256'],
        'aggregation_rule': 'left-closed/right-open; OHLC first/max/min/last; volume,tick_volume,amount sum; open_interest last; complete windows only'}
    return store.save_bars_v3(result, dataset_id=dataset_id, provider='resample', provider_version='1',
        instruments=parent['instruments'], timeframe=target, source_timezone='UTC',
        source_frames={'bars': bars, 'parent_manifest': parent,
            'parent_bars_original': store.resolve(parent['normalized_files']['bars']['path']).read_bytes()},
        assumptions=[*parent['assumptions'], 'Incomplete or ambiguous DST windows are rejected, never filled.',
            'Each aggregated observation is known only after its target window closes.'],
        aggregation_timezone=aggregation_timezone, anchor=anchor, lineage=lineage)
