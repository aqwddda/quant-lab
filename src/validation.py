"""Reject invalid inputs; never silently sort, deduplicate, fill or repair bars."""
import numpy as np
import pandas as pd
from src.strategy import calculate_signals


def validate_market_data(data: pd.DataFrame):
    required = ['date', 'open', 'high', 'low', 'close', 'volume']
    if data.empty or not set(required).issubset(data.columns):
        raise ValueError('Nonempty date/OHLCV data required')
    dates = data['date']
    if not pd.api.types.is_datetime64_any_dtype(dates):
        raise ValueError('date must be datetime64 exchange session dates')
    if dates.dt.tz is not None:
        raise ValueError('Use timezone-naive New York exchange session dates, not UTC timestamps')
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError('Dates must be nonmissing, unique, and ascending')
    if not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Daily dates must have no time-of-day component')
    if (dates.dt.dayofweek >= 5).any():
        raise ValueError('SPY daily sessions cannot be on weekends')
    numbers = data[required[1:]]
    if not all(pd.api.types.is_numeric_dtype(numbers[c]) for c in numbers):
        raise ValueError('OHLCV must be numeric')
    if not np.isfinite(numbers.to_numpy(dtype=float)).all():
        raise ValueError('OHLCV must be finite and nonmissing')
    if (data[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise ValueError('OHLC must be positive')
    if (data['volume'] < 0).any() or (data['volume'] % 1 != 0).any():
        raise ValueError('Volume must be a nonnegative integer')
    if (data.high < data[['open', 'close', 'low']].max(axis=1)).any():
        raise ValueError('Impossible high')
    if (data.low > data[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError('Impossible low')


def future_mutation_test(data: pd.DataFrame, cutoff, fast_window: int, slow_window: int) -> bool:
    cutoff = pd.Timestamp(cutoff)
    past = data.date <= cutoff
    if not past.any() or past.all():
        raise ValueError('Cutoff must leave both past and future observations')
    before = calculate_signals(data, fast_window, slow_window)
    mutated = data.copy(deep=True)
    rng = np.random.default_rng(42)
    future = ~past
    for column in ['open', 'high', 'low', 'close', 'volume']:
        mutated[column] = mutated[column].astype(float)
        mutated.loc[future, column] = rng.uniform(1, 10000, int(future.sum()))
    # Deliberately extreme future bars need not be coherent; no validation/repair is applied.
    after = calculate_signals(mutated, fast_window, slow_window)
    pd.testing.assert_frame_equal(before.loc[past], after.loc[past], check_exact=True)
    pd.testing.assert_frame_equal(before.loc[past], calculate_signals(data.loc[past], fast_window, slow_window),
                                  check_exact=True)
    return True
