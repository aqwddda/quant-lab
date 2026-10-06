import pandas as pd
import pytest
from src.backtest.execution import Costs


def test_chronological_manual_round_trip(simulate):
    data = pd.DataFrame({
        'date': pd.bdate_range('2020-01-01', periods=6),
        'open': [100., 100., 100., 100., 100., 110.],
        'close': [100., 100., 103., 104., 80., 110.],
        'high': [101., 101., 104., 105., 101., 111.],
        'low': [99., 99., 99., 99., 79., 109.], 'volume': [1000] * 6,
    })
    data['timestamp']=data.date.dt.tz_localize('UTC')
    data['symbol']='AAPL'
    result = simulate(data, 2, 3, 10000, Costs(0.001, 0.01))
    assert result.trades.side.tolist() == ['BUY', 'SELL']
    buy, sell = result.trades.iloc[0], result.trades.iloc[1]
    assert buy.signal_date == data.timestamp.iloc[2]
    assert buy.execution_date == data.timestamp.iloc[3]
    assert buy.quantity == 98
    assert buy.cash_after == pytest.approx(92.102)
    assert sell.signal_date == data.timestamp.iloc[4]
    assert sell.execution_date == data.timestamp.iloc[5]
    assert sell.cash_after == pytest.approx(10753.6298)
    assert result.equity.equity.iloc[-1] == pytest.approx(10753.6298)
    assert result.equity.realized_pnl.iloc[-1] == pytest.approx(753.6298)
    assert result.benchmark_trades.execution_date.iloc[0] == data.timestamp.iloc[3]


def test_benchmark_buys_even_if_first_target_is_cash(bars, simulate):
    bars['close'] = 100.
    bars['open'] = 100.
    bars['high'] = 101.
    bars['low'] = 99.
    result = simulate(bars, 20, 60, 100000, Costs(0, 0))
    assert result.trades.empty
    assert len(result.benchmark_trades) == 1
    assert result.benchmark_trades.execution_date.iloc[0] == bars.timestamp.iloc[60]
    assert 'SELL' not in result.benchmark_equity.signal.tolist()


def test_accounts_reconcile_every_day(bars, simulate):
    result = simulate(bars, 20, 60, 100000, Costs(0.0005, 0.0002))
    for account in [result.equity, result.benchmark_equity]:
        assert (account.cash >= 0).all()
        assert (account.position_quantity >= 0).all()
        assert (account.position_quantity % 1 == 0).all()
        assert (account.equity == account.cash + account.position_market_value).all()
        assert (account.equity - 100000).to_numpy() == pytest.approx(
            (account.realized_pnl + account.unrealized_pnl).to_numpy())


def test_generic_aapl_symbol(bars, simulate):
    bars['symbol'] = 'AAPL'
    result = simulate(bars, 20, 60, 100000, Costs(0.0005, 0.0002))
    assert not result.trades.empty
    assert result.trades.symbol.eq('AAPL').all()


def test_reject_multi_symbol(bars, simulate):
    bars.loc[0,'symbol']='MSFT'
    with pytest.raises(ValueError,match='one symbol'):
        simulate(bars,20,60,100000,Costs(0,0))
