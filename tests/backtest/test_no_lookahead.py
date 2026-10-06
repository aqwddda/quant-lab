import pandas as pd
from src.backtest.execution import Costs
from src.validation import strategy_future_mutation_test
from src.strategies.sma import SmaCrossStrategy
from src.data.loader import iter_bars


def test_future_mutation(bars, simulate):
    observations=tuple(iter_bars(bars,'1d'))
    assert strategy_future_mutation_test(observations,observations[75].available_at,lambda:SmaCrossStrategy(20,60))


def test_first_execution_and_benchmark(bars, simulate):
    result = simulate(bars, 20, 60, 100000, Costs(0.0005, 0.0002))
    trade = result.trades.iloc[0]
    assert trade.signal_date == bars.timestamp.iloc[59]
    assert trade.execution_date == bars.timestamp.iloc[60]
    assert trade.raw_open == bars.open.iloc[60]
    assert (result.equity.position_quantity.iloc[:60] == 0).all()
    assert result.benchmark_trades.execution_date.iloc[0] == bars.timestamp.iloc[60]


def test_future_prices_do_not_change_past_accounts(bars, simulate):
    original = simulate(bars, 20, 60, 100000, Costs(0.0005, 0.0002))
    changed = bars.copy()
    changed.loc[76:, ['open', 'high', 'low', 'close']] *= 5
    changed.loc[76:, 'volume'] *= 3
    mutated = simulate(changed, 20, 60, 100000, Costs(0.0005, 0.0002))
    pd.testing.assert_frame_equal(original.equity.iloc[:76], mutated.equity.iloc[:76])


def test_tomorrow_close_does_not_decide_tomorrow_open(bars, simulate):
    changed = bars.copy()
    changed.loc[60, 'close'] = 1
    changed.loc[60, 'low'] = 1
    a = simulate(bars, 20, 60, 100000, Costs(0, 0))
    b = simulate(changed, 20, 60, 100000, Costs(0, 0))
    pd.testing.assert_series_equal(a.trades.iloc[0], b.trades.iloc[0])


def test_final_close_signal_is_not_executed(bars, simulate):
    result = simulate(bars.iloc[:60], 20, 60, 100000, Costs(0, 0))
    assert result.trades.empty
    assert result.benchmark_trades.empty
