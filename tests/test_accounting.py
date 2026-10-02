import pytest
from src.execution import Costs, execute_order
from src.portfolio import Portfolio


def test_manual_round_trip():
    account = Portfolio(10000)
    account.apply_fill(execute_order('BUY', 100, account.cash, 0, Costs(0.001, 0.01)))
    assert account.quantity == 98
    assert account.cash == pytest.approx(92.102)
    assert account.equity(105) == pytest.approx(10382.102)
    assert account.unrealized_pnl(105) == pytest.approx(382.102)
    account.apply_fill(execute_order('SELL', 110, account.cash, 98, Costs(0.001, 0.01)))
    assert account.cash == pytest.approx(10753.6298)
    assert account.quantity == 0
    assert account.realized_pnl == pytest.approx(753.6298)
    assert account.unrealized_pnl(110) == 0


def test_overdraft_is_rejected_without_mutation():
    account = Portfolio(50)
    fill = execute_order('BUY', 100, 10000, 0, Costs(0, 0))
    with pytest.raises(ValueError):
        account.apply_fill(fill)
    assert account.cash == 50
    assert account.quantity == 0


def test_sell_without_position_is_rejected():
    account = Portfolio(10000)
    fill = execute_order('SELL', 100, 0, 10, Costs(0, 0))
    with pytest.raises(ValueError):
        account.apply_fill(fill)
