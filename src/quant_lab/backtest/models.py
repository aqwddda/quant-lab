from dataclasses import dataclass
import pandas as pd


TRADE_COLUMNS = ['signal_date', 'execution_date', 'symbol', 'side', 'signal_close',
    'raw_open', 'execution_price', 'quantity', 'trade_value', 'commission', 'slippage_cost',
    'cash_before', 'cash_after', 'position_before', 'position_after', 'realized_pnl']


@dataclass
class SimulationResult:
    equity: pd.DataFrame
    trades: pd.DataFrame


@dataclass
class BacktestResult:
    equity: pd.DataFrame
    trades: pd.DataFrame
    benchmark_equity: pd.DataFrame
    benchmark_trades: pd.DataFrame
