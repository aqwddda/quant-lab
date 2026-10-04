"""Reject invalid inputs; never silently sort, deduplicate, fill or repair bars."""
import numpy as np
import pandas as pd
from src.strategy import calculate_signals
from src.data.validation import validate_market_data


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
