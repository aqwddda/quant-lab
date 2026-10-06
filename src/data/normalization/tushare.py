"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import pandas as pd
from src.data.schema import CALENDAR_COLUMNS, require_columns
from src.market import Instrument, AssetClass
from src.data.validation import _validate_daily_prices, validate_adjustments


from src.data.normalization import (canonical_order, integer_volume,
    DAILY_PRICE_COLUMNS, normalize_session_bars)

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
    bars = canonical_order(bars[DAILY_PRICE_COLUMNS + ['amount']])
    _validate_daily_prices(bars)
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
    require_columns(reference, ['ts_code', 'exchange'])
    if len(reference) != 1 or reference.ts_code.iloc[0] != symbol:
        raise ValueError('Tushare instrument symbol mismatch')
    item = reference.iloc[0]
    # Tushare codes coincide with canonical venue names, through an explicit mapping.
    venues = {'SZSE': 'SZSE', 'SSE': 'SSE', 'BSE': 'BSE'}
    if item.exchange not in venues:
        raise ValueError('Unsupported Tushare exchange')
    instrument = Instrument(symbol=symbol, provider_symbol=item.ts_code,
        asset_class=AssetClass.EQUITY, venue=venues[item.exchange], quote_currency='CNY')
    source_calendar = prepared['calendar']
    require_columns(source_calendar, ['cal_date', 'is_open'])
    if not source_calendar.is_open.isin([0, 1]).all():
        raise ValueError('Invalid Tushare calendar is_open')
    calendar = pd.DataFrame({'date': pd.to_datetime(source_calendar.cal_date, format='%Y%m%d').astype('datetime64[ns]'),
                            'market': 'CN', 'is_open': source_calendar.is_open.astype(bool), 'provider': 'tushare'})
    calendar = canonical_order(calendar, ['date', 'market'])[CALENDAR_COLUMNS]
    bars = normalize_session_bars(bars, 'Asia/Shanghai')
    return {'bars': bars, 'adjustments': adjustments, 'instruments': [instrument], 'calendar': calendar}
