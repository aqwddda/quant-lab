"""Reject invalid inputs; never silently sort, deduplicate, fill or repair bars."""
import numpy as np
import pandas as pd
from quant_lab.strategies.sma import calculate_signals
from quant_lab.data.validation import validate_market_data


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


def strategy_future_mutation_test(bars, cutoff, strategy_factory):
    """Compare known outputs by close availability, including a truncated prefix."""
    from dataclasses import replace
    from quant_lab.strategies.base import StrategyContext
    bars = tuple(bars)
    cutoff = pd.Timestamp(cutoff)
    past = [bar.available_at <= cutoff for bar in bars]
    if not any(past) or all(past):
        raise ValueError('Cutoff must leave both past and future observations')
    mutated = [bar if known else replace(bar, open=bar.open*7, high=bar.high*7,
        low=bar.low*7, close=bar.close*7) for bar, known in zip(bars, past)]
    def outputs(history):
        strategy = strategy_factory()
        strategy.reset()
        rows = []
        for i, bar in enumerate(history):
            decision = strategy.on_bar(StrategyContext(i, bar.available_at), bar)
            rows.append({'target': decision.target, **decision.diagnostics})
        return pd.DataFrame(rows)
    before, after = outputs(bars), outputs(mutated)
    mask = np.array(past)
    pd.testing.assert_frame_equal(before.loc[mask], after.loc[mask], check_exact=True)
    pd.testing.assert_frame_equal(before.loc[mask].reset_index(drop=True),
        outputs([bar for bar, known in zip(bars, past) if known]), check_exact=True)
    return True


def chan_future_mutation_test(bars, cutoff, config=None):
    from dataclasses import replace
    from quant_lab.chan import ChanAnalyzer
    bars = tuple(bars)
    cutoff = pd.Timestamp(cutoff)
    if not any(b.available_at <= cutoff for b in bars) or all(b.available_at <= cutoff for b in bars):
        raise ValueError('Cutoff must leave both past and future observations')
    before = ChanAnalyzer(config).extend(bars)
    altered = [b if b.available_at <= cutoff else replace(b,open=b.open*7,high=b.high*7,
        low=b.low*7,close=b.close*7) for b in bars]
    after = ChanAnalyzer(config).extend(altered)
    assert tuple(f for f in before.fractals if f.confirmed_at <= cutoff) == tuple(f for f in after.fractals if f.confirmed_at <= cutoff)
    assert tuple(s for s in before.confirmed_strokes if s.confirmed_at <= cutoff) == tuple(s for s in after.confirmed_strokes if s.confirmed_at <= cutoff)
    return True
