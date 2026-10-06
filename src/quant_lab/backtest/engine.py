"""Chronological driver: prior close target -> today's open fill -> close valuation."""
from dataclasses import dataclass, asdict
import pandas as pd
from quant_lab.backtest.execution import Costs, execute_order, next_open_target
from quant_lab.backtest.portfolio import Portfolio
from quant_lab.strategies.sma import calculate_signals
from quant_lab.validation import validate_market_data


TRADE_COLUMNS = ['signal_date', 'execution_date', 'symbol', 'side', 'signal_close',
                 'fast_ma', 'slow_ma', 'raw_open', 'execution_price', 'quantity',
                 'trade_value', 'commission', 'slippage_cost', 'cash_before', 'cash_after',
                 'position_before', 'position_after', 'realized_pnl']


@dataclass
class BacktestResult:
    equity: pd.DataFrame
    trades: pd.DataFrame
    benchmark_equity: pd.DataFrame
    benchmark_trades: pd.DataFrame


def _simulate(data, indicators, initial_cash, costs, symbol, benchmark=False):
    account = Portfolio(initial_cash)
    targets = indicators.target.tolist()
    trades, states = [], []
    previous_equity = peak = float(initial_cash)
    benchmark_entered = False
    for i, bar in enumerate(data.itertuples(index=False)):
        target = next_open_target(targets, i)
        side = None
        if benchmark:
            if target != -1 and not benchmark_entered:
                side = 'BUY'
        elif target != -1:
            if target == 1 and account.quantity == 0:
                side = 'BUY'
            elif target == 0 and account.quantity > 0:
                side = 'SELL'
        if side:
            fill = execute_order(side, float(bar.open), account.cash, account.quantity, costs)
            if fill is not None:
                cash_before, position_before, realized_before = account.cash, account.quantity, account.realized_pnl
                account.apply_fill(fill)
                prior = data.iloc[i - 1]
                trades.append({
                    'signal_date': prior.date, 'execution_date': bar.date, 'symbol': symbol,
                    'signal_close': prior.close, 'fast_ma': indicators.fast_ma.iloc[i - 1],
                    'slow_ma': indicators.slow_ma.iloc[i - 1], **asdict(fill),
                    'cash_before': cash_before, 'cash_after': account.cash,
                    'position_before': position_before, 'position_after': account.quantity,
                    'realized_pnl': account.realized_pnl - realized_before,
                })
            if benchmark:
                benchmark_entered = True  # one attempt on the first eligible open
        equity = account.equity(bar.close)
        peak = max(peak, equity)
        current_target = targets[i]
        signal = 'HOLD'
        if benchmark:
            if current_target == -1:
                signal = 'WAIT'
            elif not benchmark_entered:
                signal = 'BUY'
        elif current_target == -1:
            signal = 'WAIT'
        elif current_target == 1 and account.quantity == 0:
            signal = 'BUY'
        elif current_target == 0 and account.quantity > 0:
            signal = 'SELL'
        states.append({
            'date': bar.date, 'open': bar.open, 'close': bar.close,
            'fast_ma': indicators.fast_ma.iloc[i], 'slow_ma': indicators.slow_ma.iloc[i],
            'target': current_target, 'signal': signal, 'cash': account.cash,
            'position_quantity': account.quantity, 'position_market_value': account.market_value(bar.close),
            'equity': equity, 'daily_return': equity / previous_equity - 1,
            'drawdown': equity / peak - 1, 'realized_pnl': account.realized_pnl,
            'unrealized_pnl': account.unrealized_pnl(bar.close),
        })
        previous_equity = equity
    return pd.DataFrame(states), pd.DataFrame(trades, columns=TRADE_COLUMNS)


def run_backtest(data, fast_window: int, slow_window: int, initial_cash: float,
                 costs: Costs, symbol: str = 'SPY') -> BacktestResult:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError('A nonempty symbol is required')
    if 'symbol' in data:
        if data.symbol.nunique(dropna=False) != 1:
            raise ValueError('Current backtest engine supports one symbol; Data Layer supports multi-symbol datasets.')
        if not data.symbol.eq(symbol).all():
            raise ValueError('Backtest symbol does not match bars')
    validate_market_data(data)
    data = data.reset_index(drop=True)
    indicators = calculate_signals(data, fast_window, slow_window)
    equity, trades = _simulate(data, indicators, initial_cash, costs, symbol)
    benchmark_equity, benchmark_trades = _simulate(data, indicators, initial_cash, costs, symbol, True)
    return BacktestResult(equity, trades, benchmark_equity, benchmark_trades)
