"""Cash and integer-share accounting. Slippage is already inside trade_value."""
from dataclasses import dataclass
import math
from src.backtest.execution import Fill


@dataclass
class EquityPortfolio:
    cash: float
    quantity: int = 0
    cost_basis: float = 0.0  # includes entry commission
    realized_pnl: float = 0.0

    def __post_init__(self):
        if not math.isfinite(self.cash) or self.cash <= 0:
            raise ValueError('Initial cash must be positive and finite')
        if self.quantity != 0 or self.cost_basis != 0 or self.realized_pnl != 0:
            raise ValueError('Initialize a portfolio with cash only')

    def apply_fill(self, fill: Fill):
        if fill.side == 'BUY':
            debit = fill.trade_value + fill.commission
            if self.quantity or debit > self.cash:
                raise ValueError('Buy violates cash-only constraint')
            self.cash -= debit
            self.quantity = fill.quantity
            self.cost_basis = debit
        elif fill.side == 'SELL':
            if fill.quantity != self.quantity or self.quantity <= 0:
                raise ValueError('Sell must liquidate the existing position')
            proceeds = fill.trade_value - fill.commission
            if self.cash + proceeds < 0:
                raise ValueError('Sale costs exceed available funds')
            self.cash += proceeds
            self.realized_pnl += proceeds - self.cost_basis
            self.quantity = 0
            self.cost_basis = 0.0
        else:
            raise ValueError('Invalid fill side')

    def market_value(self, close: float) -> float:
        return self.quantity * close

    def equity(self, close: float) -> float:
        return self.cash + self.market_value(close)

    def unrealized_pnl(self, close: float) -> float:
        return self.market_value(close) - self.cost_basis
