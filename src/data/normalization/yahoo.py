"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import numpy as np
import pandas as pd
from src.market import Instrument, AssetClass
from src.data.schema import (PRICE_COLUMNS, ACTION_COLUMNS,
                             require_columns)
from src.data.validation import _validate_daily_prices, validate_adjustments


from src.data.normalization import (canonical_order, integer_volume,
    DAILY_PRICE_COLUMNS, normalize_session_bars)

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
    bars = bars[DAILY_PRICE_COLUMNS].copy()
    bars[PRICE_COLUMNS] = bars[PRICE_COLUMNS].mul(split_scale, axis=0)
    bars['volume'] = integer_volume(bars.volume / split_scale)
    _validate_daily_prices(bars)
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
    # Canonical venues group listing tiers; supplier codes remain in Source Snapshot.
    venues = {'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ',
              'NYQ': 'NYSE', 'PCX': 'NYSE_ARCA', 'ASE': 'NYSE_AMERICAN',
              'BATS': 'CBOE_BZX', 'PNK': 'OTC', 'OBB': 'OTC', 'OEM': 'OTC',
              'OQB': 'OTC', 'OQX': 'OTC'}
    if info.get('exchange') not in venues or info.get('currency') != 'USD':
        raise ValueError('Yahoo US normalization requires a supported US exchange and USD currency')
    instrument = Instrument(symbol=symbol, provider_symbol=info['symbol'],
        asset_class=AssetClass.EQUITY, venue=venues[info['exchange']], quote_currency=info['currency'])
    bars = normalize_session_bars(bars, prepared['source_timezone'])
    return {'bars': bars, 'adjustments': adjustments, 'corporate_actions': actions, 'instruments': [instrument]}


