import pytest
from src.backtest.execution import Costs, Fill, execute_order


def test_buy_integer_quantity_costs():
    fill = execute_order('BUY', 100.0, 10000.0, 0, Costs(0.001, 0.01))
    assert fill.quantity == 98
    assert fill.raw_open == 100
    assert fill.execution_price == 101
    assert fill.trade_value == 9898
    assert fill.commission == pytest.approx(9.898)
    assert fill.slippage_cost == 98
    assert fill.trade_value + fill.commission <= 10000


def test_sell_price_and_costs():
    fill = execute_order('SELL', 110.0, 92.102, 98, Costs(0.001, 0.01))
    assert fill.execution_price == 108.9
    assert fill.trade_value == pytest.approx(10672.2)
    assert fill.commission == pytest.approx(10.6722)
    assert fill.slippage_cost == pytest.approx(107.8)


def test_no_affordable_shares():
    assert execute_order('BUY', 100, 50, 0, Costs(0, 0)) is None


@pytest.mark.parametrize('commission,slippage', [(-0.1, 0), (0, 1), (float('nan'), 0)])
def test_invalid_costs(commission, slippage):
    with pytest.raises(ValueError):
        Costs(commission, slippage)


def test_reject_invalid_fill():
    with pytest.raises(ValueError):
        Fill('BUY', 100, 100, -1, -100, 0, 0)
    with pytest.raises(ValueError):
        Fill('BUY', 100, 100, 1, 99, 0, 0)
