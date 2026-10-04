"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import numpy as np
import pandas as pd
from src.data.schema import (BAR_COLUMNS, PRICE_COLUMNS, ACTION_COLUMNS, INSTRUMENT_COLUMNS,
                             CALENDAR_COLUMNS, require_columns)
from src.data.validation import validate_bars, validate_adjustments


def canonical_order(frame, keys=('date', 'symbol')):
    return frame.sort_values(list(keys), kind='stable').reset_index(drop=True)


def integer_volume(values):
    values = pd.to_numeric(values, errors='raise').to_numpy(dtype=float)
    nearest = np.rint(values)
    # Only binary floating point arithmetic noise, never fractional shares.
    if not np.isfinite(values).all() or (values < 0).any() or not np.allclose(values, nearest, rtol=0, atol=1e-6):
        raise ValueError('Volume must be finite, nonnegative and integer-valued after explicit unit conversion')
    if (nearest >= np.iinfo(np.int64).max).any():
        raise ValueError('Volume exceeds int64 range')
    return nearest.astype('int64')


def normalize_yahoo(prepared, symbol):
    source = prepared['bars'].copy()
    require_columns(source, ['date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Dividends', 'Stock Splits'])
    # Date conversion has already happened in YahooProvider, before normalization.
    split_history = prepared['adjustments']
    require_columns(split_history, ['date', 'Stock Splits'])
    if split_history.date.duplicated().any():
        raise ValueError('Duplicate Yahoo split events')
    if not np.isfinite(split_history['Stock Splits']).all() or (split_history['Stock Splits'] <= 0).any():
        raise ValueError('Invalid Yahoo split ratios')
    source = source.sort_values('date', kind='stable').reset_index(drop=True)
    split_scale = np.array([split_history.loc[split_history.date > day, 'Stock Splits'].prod()
                            for day in source.date], dtype=float)
    bars = source.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    bars['symbol'] = symbol
    bars = bars[BAR_COLUMNS].copy()
    bars[PRICE_COLUMNS] = bars[PRICE_COLUMNS].mul(split_scale, axis=0)
    bars['volume'] = integer_volume(bars.volume / split_scale)
    validate_bars(bars)
    adjustments = bars[['date', 'symbol']].copy()
    adjustments['adj_factor'] = source['Adj Close'] / bars.close
    adjustments['provider'] = 'yahoo'
    adjustments['factor_semantics'] = 'provider_adjusted_close_ratio'
    validate_adjustments(adjustments)
    events = []
    for i, row in source.iterrows():
        dividend, split = float(row['Dividends']), float(row['Stock Splits'])
        if not np.isfinite([dividend, split]).all() or dividend < 0 or split < 0:
            raise ValueError('Invalid Yahoo corporate action')
        if split:
            found = split_history.loc[split_history.date == row.date, 'Stock Splits']
            if len(found) != 1 or found.iloc[0] != split:
                raise ValueError('Yahoo bar/split-history mismatch')
        if dividend:
            events.append([row.date, symbol, 'dividend', dividend * split_scale[i], 0., 'yahoo'])
        if split:
            events.append([row.date, symbol, 'split', 0., split, 'yahoo'])
    actions = pd.DataFrame(events, columns=ACTION_COLUMNS)
    actions['date'] = pd.to_datetime(actions.date).astype('datetime64[ns]')
    for column in ['cash_amount', 'split_ratio']:
        actions[column] = actions[column].astype(float)
    actions = canonical_order(actions, ['date', 'symbol', 'action_type'])
    info = prepared['instruments']
    if info.get('symbol') != symbol or info.get('quoteType') not in {'ETF', 'EQUITY'}:
        raise ValueError('Yahoo instrument must match symbol and be ETF/EQUITY')
    us_exchanges = {'NMS', 'NGM', 'NCM', 'NYQ', 'PCX', 'ASE', 'BATS', 'PNK', 'OBB', 'OEM', 'OQB', 'OQX'}
    if info.get('exchange') not in us_exchanges or info.get('currency') != 'USD':
        raise ValueError('Yahoo US normalization requires a supported US exchange and USD currency')
    instrument = pd.DataFrame([[symbol, info.get('longName') or info.get('shortName'), 'US',
        info.get('exchange'), info['quoteType'], info.get('currency'), pd.NaT, pd.NaT, 'yahoo']],
        columns=INSTRUMENT_COLUMNS)
    for column in ['list_date', 'delist_date']:
        instrument[column] = pd.to_datetime(instrument[column]).astype('datetime64[ns]')
    return {'bars': bars, 'adjustments': adjustments, 'corporate_actions': actions, 'instruments': instrument}


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
