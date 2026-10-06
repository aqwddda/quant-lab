"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import numpy as np
import pandas as pd
from quant_lab.data.schema import (BAR_COLUMNS, PRICE_COLUMNS, ACTION_COLUMNS, INSTRUMENT_COLUMNS,
                             CALENDAR_COLUMNS, require_columns)
from quant_lab.data.validation import validate_bars, validate_adjustments


from quant_lab.data.normalization import canonical_order, integer_volume

def normalize_tushare(prepared, symbol):
    source = prepared['bars']
    require_columns(source, ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount'])
    if not source.ts_code.eq(symbol).all():
        raise ValueError('Tushare symbol mismatch')
    bars = source.rename(columns={'ts_code': 'symbol', 'vol': 'volume'}).copy()
    bars['date'] = pd.to_datetime(bars.trade_date, format='%Y%m%d', errors='raise').astype('datetime64[ns]')
    # daily: volume in lots of 100 shares; amount in thousands of CNY.
    bars['volume'] = integer_volume(bars.volume * 100)
    bars['amount'] = bars.amount * 1000
    bars = canonical_order(bars[BAR_COLUMNS + ['amount']])
    validate_bars(bars)
    source_adj = prepared['adjustments']
    require_columns(source_adj, ['ts_code', 'trade_date', 'adj_factor'])
    if not source_adj.ts_code.eq(symbol).all():
        raise ValueError('Tushare adjustment symbol mismatch')
    adjustments = source_adj.rename(columns={'ts_code': 'symbol'}).copy()
    adjustments['date'] = pd.to_datetime(adjustments.trade_date, format='%Y%m%d').astype('datetime64[ns]')
    adjustments['provider'] = 'tushare'
    adjustments['factor_semantics'] = 'cumulative_adjustment_factor'
    adjustments = canonical_order(adjustments[['date', 'symbol', 'adj_factor', 'provider', 'factor_semantics']])
    validate_adjustments(adjustments)
    # Preserve factors on suspended sessions; they can define the qfq end anchor.
    matching = bars[['date', 'symbol']].merge(adjustments, on=['date', 'symbol'], how='left', validate='one_to_one')
    if matching.adj_factor.isna().any():
        raise ValueError('Missing adjustment factor for bar date')
    reference = prepared['instruments']
    require_columns(reference, ['ts_code', 'name', 'exchange', 'list_date', 'delist_date'])
    if len(reference) != 1 or reference.ts_code.iloc[0] != symbol:
        raise ValueError('Tushare instrument symbol mismatch')
    item = reference.iloc[0]
    instrument = pd.DataFrame([[symbol, item['name'], 'CN', item.exchange, 'EQUITY', 'CNY',
        item.list_date, item.delist_date, 'tushare']], columns=INSTRUMENT_COLUMNS)
    for column in ['list_date', 'delist_date']:
        instrument[column] = pd.to_datetime(instrument[column].replace('', None), format='%Y%m%d').astype('datetime64[ns]')
    source_calendar = prepared['calendar']
    require_columns(source_calendar, ['cal_date', 'is_open'])
    if not source_calendar.is_open.isin([0, 1]).all():
        raise ValueError('Invalid Tushare calendar is_open')
    calendar = pd.DataFrame({'date': pd.to_datetime(source_calendar.cal_date, format='%Y%m%d').astype('datetime64[ns]'),
                            'market': 'CN', 'is_open': source_calendar.is_open.astype(bool), 'provider': 'tushare'})
    calendar = canonical_order(calendar, ['date', 'market'])[CALENDAR_COLUMNS]
    return {'bars': bars, 'adjustments': adjustments, 'instruments': instrument, 'calendar': calendar}
