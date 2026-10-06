"""Historical single-asset SMA API and exact report layout."""
import pandas as pd
from quant_lab.market import Bar, Timeframe
from quant_lab.strategies.sma import SmaCrossStrategy
from quant_lab.backtest.engine import BacktestEngine
from quant_lab.backtest.execution import Costs, EquityCashExecutionModel, EquityBuyAndHoldExecutionModel
from quant_lab.backtest.portfolio import EquityPortfolio
from quant_lab.backtest.models import BacktestResult
from quant_lab.data.validation import validate_market_data

TRADE_COLUMNS = ['signal_date','execution_date','symbol','side','signal_close','fast_ma','slow_ma',
    'raw_open','execution_price','quantity','trade_value','commission','slippage_cost',
    'cash_before','cash_after','position_before','position_after','realized_pnl']
EQUITY_COLUMNS = ['date','open','close','fast_ma','slow_ma','target','signal','cash','position_quantity',
    'position_market_value','equity','daily_return','drawdown','realized_pnl','unrealized_pnl']


def run_backtest(data, fast_window, slow_window, initial_cash, costs, symbol='SPY'):
    if not isinstance(symbol,str) or not symbol.strip():
        raise ValueError('A nonempty symbol is required')
    if 'symbol' in data:
        if data.symbol.nunique(dropna=False)!=1:
            raise ValueError('Current backtest engine supports one symbol')
        if not data.symbol.eq(symbol).all():
            raise ValueError('Backtest symbol does not match bars')
    validate_market_data(data)
    data=data.reset_index(drop=True)
    # Historical session labels stay unchanged in reports. UTC midnight here is
    # solely an ordering coordinate; it does not infer an exchange session open.
    raw=[Bar(pd.Timestamp(row.date).tz_localize('UTC').to_pydatetime(),symbol,
        row.open,row.high,row.low,row.close,timeframe=Timeframe.D1,volume=row.volume)
        for row in data.itertuples()]
    strategy=BacktestEngine(SmaCrossStrategy(fast_window,slow_window),
        EquityCashExecutionModel(costs),EquityPortfolio(initial_cash)).run(raw,labels=data.date)
    benchmark=BacktestEngine(SmaCrossStrategy(fast_window,slow_window),
        EquityBuyAndHoldExecutionModel(costs),EquityPortfolio(initial_cash)).run(raw,labels=data.date)
    return BacktestResult(strategy.equity.rename(columns={'bar_return':'daily_return'})[EQUITY_COLUMNS],strategy.trades[TRADE_COLUMNS],
        benchmark.equity.rename(columns={'bar_return':'daily_return'})[EQUITY_COLUMNS],benchmark.trades[TRADE_COLUMNS])
