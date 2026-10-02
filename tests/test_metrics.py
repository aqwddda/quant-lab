import json
import pandas as pd
import pytest
from src.backtest import TRADE_COLUMNS, run_backtest
from src.execution import Costs
from src.metrics import calculate_metrics


def test_hand_calculated_metrics():
    equity = pd.DataFrame({
        'date': pd.to_datetime(['2020-01-01', '2020-01-02', '2021-01-01']),
        'equity': [100., 120., 90.], 'daily_return': [0., 0.2, -0.25],
        'drawdown': [0., 0., -0.25], 'position_quantity': [0, 0, 0],
    })
    trades = pd.DataFrame(columns=TRADE_COLUMNS)
    result = calculate_metrics(equity, trades, 100, 252, 0)
    assert result['total_return'] == pytest.approx(-0.1)
    assert result['maximum_drawdown'] == -0.25
    assert result['cagr'] == pytest.approx(0.9 ** (365.25 / 366) - 1)
    assert result['annualized_volatility'] == pytest.approx(0.2254624876411447 * 252 ** 0.5)
    assert result['win_rate'] is None
    assert result['sharpe_ratio'] == pytest.approx((-0.05 / 3) / 0.2254624876411447 * 252 ** 0.5)
    json.dumps(result, allow_nan=False)


def test_trade_statistics_net_of_entry_and_exit_costs():
    equity = pd.DataFrame({
        'date': pd.bdate_range('2020-01-01', periods=5),
        'equity': [10000.] * 5, 'daily_return': [0.] * 5,
        'drawdown': [0.] * 5, 'position_quantity': [0] * 5,
    })
    trades = pd.DataFrame({
        'side': ['BUY', 'SELL', 'BUY', 'SELL'],
        'execution_date': pd.to_datetime(['2020-01-01', '2020-01-02', '2020-01-03', '2020-01-06']),
        'realized_pnl': [0, 50, 0, -25], 'trade_value': [1000.] * 4,
        'commission': [1.] * 4, 'slippage_cost': [2.] * 4,
    })
    metrics = calculate_metrics(equity, trades, 10000, 252, 0)
    assert metrics['trade_count'] == 4
    assert metrics['closed_trade_count'] == 2
    assert metrics['win_rate'] == 0.5
    assert metrics['profit_factor'] == 2
    assert metrics['average_profit_per_trade'] == 50
    assert metrics['average_loss_per_trade'] == -25
    assert metrics['average_holding_period_days'] == 2
    assert metrics['total_commission'] == 4
    assert metrics['total_slippage_cost'] == 8
    assert metrics['turnover'] == 0.4
    assert metrics['sharpe_ratio'] is None
    assert metrics['sortino_ratio'] is None


def test_open_trades_are_not_classified_as_wins(bars):
    result = run_backtest(bars, 20, 60, 100000, Costs(0, 0))
    metrics = calculate_metrics(result.equity, result.trades, 100000, 252, 0)
    assert metrics['trade_count'] == 1
    assert metrics['closed_trade_count'] == 0
    assert metrics['win_rate'] is None
