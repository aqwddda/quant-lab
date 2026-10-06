"""Canonical columns and explicit price coordinates."""
SCHEMA_VERSION = NORMALIZER_VERSION = 3
BAR_COLUMNS = ['timestamp', 'symbol', 'open', 'high', 'low', 'close']
OPTIONAL_BAR_COLUMNS = ['volume', 'tick_volume', 'amount', 'open_interest']
PRICE_COLUMNS = ['open', 'high', 'low', 'close']
ADJUSTMENT_COLUMNS = ['date', 'symbol', 'adj_factor', 'provider', 'factor_semantics']
ACTION_COLUMNS = ['date', 'symbol', 'action_type', 'cash_amount', 'split_ratio', 'provider']
CALENDAR_COLUMNS = ['market', 'date', 'is_open', 'provider']
PRICE_BASES = {'raw', 'provider_adjusted', 'qfq', 'hfq'}


def require_columns(data, columns):
    missing = set(columns) - set(data.columns)
    if missing or data.columns.duplicated().any():
        raise ValueError(f'Schema mismatch: missing {sorted(missing)} or duplicate columns')
