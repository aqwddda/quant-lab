"""Canonical columns and explicit price coordinates."""
SCHEMA_VERSION = NORMALIZER_VERSION = 2
BAR_COLUMNS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']
PRICE_COLUMNS = ['open', 'high', 'low', 'close']
ADJUSTMENT_COLUMNS = ['date', 'symbol', 'adj_factor', 'provider', 'factor_semantics']
ACTION_COLUMNS = ['date', 'symbol', 'action_type', 'cash_amount', 'split_ratio', 'provider']
INSTRUMENT_COLUMNS = ['symbol', 'name', 'market', 'exchange', 'asset_type', 'currency',
                      'list_date', 'delist_date', 'provider']
CALENDAR_COLUMNS = ['market', 'date', 'is_open', 'provider']
PRICE_BASES = {'raw', 'provider_adjusted', 'qfq', 'hfq', 'legacy_provider_adjusted'}
DATE_SEMANTICS = 'timezone-naive exchange session date; local date label, not UTC'


def require_columns(data, columns):
    missing = set(columns) - set(data.columns)
    if missing or data.columns.duplicated().any():
        raise ValueError(f'Schema mismatch: missing {sorted(missing)} or duplicate columns')

V3_SCHEMA_VERSION = 3
V3_BAR_COLUMNS = ['timestamp', 'symbol', 'open', 'high', 'low', 'close']
V3_OPTIONAL_COLUMNS = ['volume', 'tick_volume', 'amount', 'open_interest']
