import pytest
from src.data.loader import iter_bars
from src.backtest.engine import BacktestEngine
from src.backtest.execution import EquityCashExecutionModel, EquityBuyAndHoldExecutionModel
from src.backtest.portfolio import EquityPortfolio
from src.backtest.models import BacktestResult
from src.strategies.sma import SmaCrossStrategy


@pytest.fixture
def simulate():
    def run(data, fast, slow, cash, costs):
        observations=tuple(iter_bars(data,'1d'))
        account=BacktestEngine(SmaCrossStrategy(fast,slow),EquityCashExecutionModel(costs),
            EquityPortfolio(cash)).run(observations)
        benchmark=BacktestEngine(SmaCrossStrategy(fast,slow),EquityBuyAndHoldExecutionModel(costs),
            EquityPortfolio(cash)).run(observations)
        return BacktestResult(account.equity,account.trades,benchmark.equity,benchmark.trades)
    return run
