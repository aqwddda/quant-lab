"""Generic completed-bar strategy -> next open execution -> close valuation."""
from dataclasses import asdict
import pandas as pd
from src.market import Bar
from src.strategies.base import StrategyContext, TargetPosition
from src.backtest.models import SimulationResult, TRADE_COLUMNS


class BacktestEngine:
    def __init__(self, strategy, execution_model, portfolio):
        self.strategy = strategy
        self.execution_model = execution_model
        self.portfolio = portfolio
        self._used = False

    def run(self, bars):
        if self._used:
            raise ValueError('Use a fresh account and engine for each simulation')
        self._used = True
        self.strategy.reset()
        self.execution_model.reset()
        account = self.portfolio
        previous_equity = peak = float(account.cash)
        trades, states, diagnostic_names = [], [], []
        pending = previous_bar = previous_label = None
        for i, bar in enumerate(bars):
            if not isinstance(bar, Bar):
                raise ValueError('Engine requires canonical Bar objects')
            if previous_bar is not None:
                if bar.symbol != previous_bar.symbol or bar.timeframe != previous_bar.timeframe:
                    raise ValueError('Current backtest engine supports one symbol and timeframe')
                if bar.timestamp < previous_bar.available_at:
                    raise ValueError('Bars must be chronological; prior close must be known before execution open')
            label = bar.timestamp
            fill = self.execution_model.execute(pending.target if pending is not None else None, bar.open, account)
            if fill is not None:
                cash_before, quantity_before, realized_before = account.cash, account.quantity, account.realized_pnl
                account.apply_fill(fill)
                trades.append({'signal_date': previous_label, 'execution_date': label,
                    'symbol': bar.symbol, 'signal_close': previous_bar.close, **dict(pending.diagnostics),
                    **asdict(fill), 'cash_before': cash_before, 'cash_after': account.cash,
                    'position_before': quantity_before, 'position_after': account.quantity,
                    'realized_pnl': account.realized_pnl - realized_before})
            decision = self.strategy.on_bar(StrategyContext(i, bar.available_at), bar)
            if not isinstance(decision, TargetPosition):
                raise ValueError('Strategy must return TargetPosition')
            equity = account.equity(bar.close)
            peak = max(peak, equity)
            state = {'date': label, 'valuation_time': bar.available_at, 'open': bar.open, 'close': bar.close,
                'target': -1 if decision.target is None else decision.target,
                'signal': self.execution_model.signal(decision.target, account), 'cash': account.cash,
                'position_quantity': account.quantity, 'position_market_value': account.market_value(bar.close),
                'equity': equity, 'bar_return': equity / previous_equity - 1,
                'drawdown': equity / peak - 1, 'realized_pnl': account.realized_pnl,
                'unrealized_pnl': account.unrealized_pnl(bar.close)}
            if set(decision.diagnostics).intersection(set(state) | set(TRADE_COLUMNS)):
                raise ValueError('Strategy diagnostics cannot overwrite account or execution fields')
            for name in decision.diagnostics:
                if name not in diagnostic_names:
                    diagnostic_names.append(name)
            states.append({**state, **dict(decision.diagnostics)})
            previous_equity = equity
            previous_bar, previous_label, pending = bar, label, decision
        if not states:
            raise ValueError('Nonempty bars required')
        return SimulationResult(pd.DataFrame(states), pd.DataFrame(trades, columns=TRADE_COLUMNS + diagnostic_names))
