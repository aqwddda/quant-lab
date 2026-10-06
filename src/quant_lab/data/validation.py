"""Validate canonical data without sorting, filling, deduplicating or repairing."""
import numpy as np
import pandas as pd
from quant_lab.data.schema import (BAR_COLUMNS, PRICE_COLUMNS, ADJUSTMENT_COLUMNS,
                             ACTION_COLUMNS, INSTRUMENT_COLUMNS, CALENDAR_COLUMNS,
                             require_columns)


def _dates(dates):
    if not pd.api.types.is_datetime64_ns_dtype(dates.dtype) or dates.dt.tz is not None:
        raise ValueError('date must be timezone-naive datetime64[ns] exchange session dates')
    if dates.isna().any() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Daily dates must be nonmissing with no time-of-day component')


def _strings(values, name):
    if values.isna().any() or not values.map(lambda x: isinstance(x, str) and bool(x.strip()) and x == x.strip()).all():
        raise ValueError(f'{name} must contain nonempty strings')


def _numbers(data, columns):
    if not all(pd.api.types.is_numeric_dtype(data[c]) and not pd.api.types.is_bool_dtype(data[c]) for c in columns):
        raise ValueError(f'{columns} must be numeric')
    if not np.isfinite(data[columns].to_numpy(dtype=float)).all():
        raise ValueError(f'{columns} must be finite and nonmissing')


def _keys(data, keys):
    if data.duplicated(keys).any():
        raise ValueError(f'Duplicate keys: {keys}')
    expected = data.sort_values(keys, kind='stable')[keys].reset_index(drop=True)
    if not data[keys].reset_index(drop=True).equals(expected):
        raise ValueError(f'Data must be ascending by {keys}; loader never sorts dirty files')


def validate_bars(data):
    require_columns(data, BAR_COLUMNS)
    if data.empty:
        raise ValueError('Nonempty bars required')
    _dates(data.date)
    _strings(data.symbol, 'symbol')
    _keys(data, ['date', 'symbol'])
    _numbers(data, PRICE_COLUMNS + ['volume'])
    if (data[PRICE_COLUMNS] <= 0).any().any():
        raise ValueError('OHLC must be positive')
    if (data.volume < 0).any() or (data.volume % 1 != 0).any():
        raise ValueError('Volume must be a nonnegative integer')
    if (data.high < data[['open', 'close', 'low']].max(axis=1)).any():
        raise ValueError('Impossible high')
    if (data.low > data[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError('Impossible low')
    if 'amount' in data:
        _numbers(data, ['amount'])
        if (data.amount < 0).any():
            raise ValueError('amount must be nonnegative')


def validate_daily_bars(data, market, calendar=None):
    validate_bars(data)
    if market not in {'US', 'CN'}:
        raise ValueError(f'Unsupported market: {market}')
    if (data.date.dt.dayofweek >= 5).any():
        raise ValueError('Daily sessions cannot be on weekends')
    if calendar is not None:
        validate_calendar(calendar)
        selected = calendar.loc[calendar.market == market]
        if not data.date.isin(selected.loc[selected.is_open, 'date']).all():
            raise ValueError('Bars include dates not marked open in the calendar')


def validate_us_daily_bars(data, calendar=None):
    validate_daily_bars(data, 'US', calendar)


def validate_cn_daily_bars(data, calendar=None):
    validate_daily_bars(data, 'CN', calendar)


def validate_market_data(data):
    """V1 single-series compatibility check, backed by the canonical validator."""
    require_columns(data, ['date', 'open', 'high', 'low', 'close', 'volume'])
    if not pd.api.types.is_datetime64_any_dtype(data.date) or data.date.dt.tz is not None:
        raise ValueError('date must be timezone-naive datetime64 exchange session dates')
    canonical = data.copy()
    canonical['date'] = canonical.date.astype('datetime64[ns]')
    if 'symbol' not in canonical:
        canonical['symbol'] = '_legacy_'
    validate_daily_bars(canonical, 'US')


def validate_adjustments(data):
    require_columns(data, ADJUSTMENT_COLUMNS)
    if data.empty:
        raise ValueError('Nonempty adjustments required')
    _dates(data.date)
    for column in ['symbol', 'provider', 'factor_semantics']:
        _strings(data[column], column)
    _keys(data, ['date', 'symbol'])
    _numbers(data, ['adj_factor'])
    if (data.adj_factor <= 0).any():
        raise ValueError('Adjustment factors must be positive')
    if not data.factor_semantics.isin(['provider_adjusted_close_ratio', 'cumulative_adjustment_factor']).all():
        raise ValueError('Unknown adjustment factor semantics')
    for _, group in data.groupby('symbol'):
        if group.provider.nunique() != 1 or group.factor_semantics.nunique() != 1:
            raise ValueError('Each symbol needs one provider and factor semantics')


def validate_corporate_actions(data):
    require_columns(data, ACTION_COLUMNS)
    _dates(data.date)
    for column in ['symbol', 'provider']:
        _strings(data[column], column)
    _keys(data, ['date', 'symbol', 'action_type'])
    _numbers(data, ['cash_amount', 'split_ratio'])
    if not data.action_type.isin(['dividend', 'split']).all():
        raise ValueError('Unknown corporate action')
    dividend, split = data.action_type.eq('dividend'), data.action_type.eq('split')
    if (data.loc[dividend, 'cash_amount'] <= 0).any() or (data.loc[dividend, 'split_ratio'] != 0).any():
        raise ValueError('Invalid dividend')
    if (data.loc[split, 'split_ratio'] <= 0).any() or (data.loc[split, 'cash_amount'] != 0).any():
        raise ValueError('Invalid split')


def validate_instruments(data):
    require_columns(data, INSTRUMENT_COLUMNS)
    if data.empty:
        raise ValueError('Nonempty instruments required')
    for column in ['symbol', 'market', 'asset_type', 'provider']:
        _strings(data[column], column)
    if data.symbol.duplicated().any() or not data.market.isin(['US', 'CN']).all():
        raise ValueError('Invalid instrument keys/market')
    for column in ['list_date', 'delist_date']:
        if not pd.api.types.is_datetime64_ns_dtype(data[column].dtype) or data[column].dt.tz is not None:
            raise ValueError(f'{column} must be timezone-naive datetime64[ns]')
        dates = data[column].dropna()
        if not dates.eq(dates.dt.normalize()).all():
            raise ValueError(f'{column} must be a session date')
    known = data.list_date.notna() & data.delist_date.notna()
    if (data.loc[known, 'delist_date'] < data.loc[known, 'list_date']).any():
        raise ValueError('delist_date precedes list_date')


def validate_calendar(data):
    require_columns(data, CALENDAR_COLUMNS)
    if data.empty:
        raise ValueError('Nonempty calendar required')
    _dates(data.date)
    for column in ['market', 'provider']:
        _strings(data[column], column)
    _keys(data, ['date', 'market'])
    if not pd.api.types.is_bool_dtype(data.is_open) or data.is_open.isna().any():
        raise ValueError('is_open must be nonmissing bool')
    if not data.market.isin(['US', 'CN']).all():
        raise ValueError('Invalid calendar market')
