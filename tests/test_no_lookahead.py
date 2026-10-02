import pandas as pd
from src.backtest import run_backtest
from src.execution import Costs
from src.validation import future_mutation_test


def test_future_mutation(bars):
    assert future_mutation_test(bars, bars.date.iloc[75], 20, 60)


def test_first_execution_and_benchmark(bars):
    result = run_backtest(bars, 20, 60, 100000, Costs(0.0005, 0.0002), 'SPY')
    trade = result.trades.iloc[0]
    assert trade.signal_date == bars.date.iloc[59]
    assert trade.execution_date == bars.date.iloc[60]
    assert trade.raw_open == bars.open.iloc[60]
    assert (result.equity.position_quantity.iloc[:60] == 0).all()
    assert result.benchmark_trades.execution_date.iloc[0] == bars.date.iloc[60]


def test_future_prices_do_not_change_past_accounts(bars):
    original = run_backtest(bars, 20, 60, 100000, Costs(0.0005, 0.0002), 'SPY')
    changed = bars.copy()
    changed.loc[76:, ['open', 'high', 'low', 'close']] *= 5
    changed.loc[76:, 'volume'] *= 3
    mutated = run_backtest(changed, 20, 60, 100000, Costs(0.0005, 0.0002), 'SPY')
    pd.testing.assert_frame_equal(original.equity.iloc[:76], mutated.equity.iloc[:76])


def test_tomorrow_close_does_not_decide_tomorrow_open(bars):
    changed = bars.copy()
    changed.loc[60, 'close'] = 1
    changed.loc[60, 'low'] = 1
    a = run_backtest(bars, 20, 60, 100000, Costs(0, 0), 'SPY')
    b = run_backtest(changed, 20, 60, 100000, Costs(0, 0), 'SPY')
    pd.testing.assert_series_equal(a.trades.iloc[0], b.trades.iloc[0])


def test_final_close_signal_is_not_executed(bars):
    result = run_backtest(bars.iloc[:60], 20, 60, 100000, Costs(0, 0), 'SPY')
    assert result.trades.empty
    assert result.benchmark_trades.empty
