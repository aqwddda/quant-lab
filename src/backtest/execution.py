"""Orders use only the prior close's target and the current open."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Costs:
    commission_rate: float
    slippage_rate: float

    def __post_init__(self):
        if (not math.isfinite(self.commission_rate) or self.commission_rate < 0
                or not math.isfinite(self.slippage_rate) or not 0 <= self.slippage_rate < 1):
            raise ValueError('Costs must be finite; commission >= 0 and 0 <= slippage < 1')


@dataclass(frozen=True)
class Fill:
    side: str
    raw_open: float
    execution_price: float
    quantity: int
    trade_value: float
    commission: float
    slippage_cost: float

    def __post_init__(self):
        if self.side not in ('BUY', 'SELL') or type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError('Fill requires a valid side and positive integer quantity')
        for value in [self.raw_open, self.execution_price, self.trade_value, self.commission, self.slippage_cost]:
            if not math.isfinite(value) or value < 0:
                raise ValueError('Fill amounts must be finite and nonnegative')
        if self.raw_open <= 0 or self.execution_price <= 0:
            raise ValueError('Fill prices must be positive')
        if not math.isclose(self.trade_value, self.quantity * self.execution_price, rel_tol=1e-12):
            raise ValueError('Fill trade value must equal quantity times execution price')
        if not math.isclose(self.slippage_cost, self.quantity * abs(self.execution_price - self.raw_open),
                            rel_tol=1e-12, abs_tol=1e-10):
            raise ValueError('Fill slippage cost is inconsistent with prices')


def execute_order(side: str, raw_open: float, cash: float, position: int, costs: Costs):
    if side not in ('BUY', 'SELL'):
        raise ValueError('Unknown side')
    if not math.isfinite(raw_open) or raw_open <= 0 or not math.isfinite(cash) or cash < 0:
        raise ValueError('Invalid price or cash')
    if type(position) is not int or position < 0:
        raise ValueError('Position must be a nonnegative integer')
    price = raw_open * (1 + costs.slippage_rate if side == 'BUY' else 1 - costs.slippage_rate)
    if side == 'BUY':
        if position:
            raise ValueError('This strategy cannot add to an existing position')
        quantity = math.floor(cash / (price * (1 + costs.commission_rate)))
        # Guard floating-point boundary rounding; never overdraw cash.
        while quantity and quantity * price * (1 + costs.commission_rate) > cash:
            quantity -= 1
    else:
        quantity = position
    if quantity == 0:
        return None
    value = quantity * price
    return Fill(side, float(raw_open), price, quantity, value,
                value * costs.commission_rate, quantity * abs(price - raw_open))


from typing import Protocol


class ExecutionModel(Protocol):
    def reset(self): ...
    def execute(self, target, raw_open, account): ...
    def signal(self, target, account): ...


class EquityCashExecutionModel:
    def __init__(self, costs):
        self.costs = costs

    def reset(self):
        pass

    def execute(self, target, raw_open, account):
        if target is None:
            return None
        if target == 1 and account.quantity == 0:
            side = 'BUY'
        elif target == 0 and account.quantity > 0:
            side = 'SELL'
        else:
            return None
        return execute_order(side, raw_open, account.cash, account.quantity, self.costs)

    def signal(self, target, account):
        if target is None:
            return 'WAIT'
        if target == 1 and account.quantity == 0:
            return 'BUY'
        if target == 0 and account.quantity > 0:
            return 'SELL'
        return 'HOLD'


class EquityBuyAndHoldExecutionModel(EquityCashExecutionModel):
    """One attempt on the first open eligible after the strategy warmup."""
    def reset(self):
        self.entered = False

    def execute(self, target, raw_open, account):
        if target is None or self.entered:
            return None
        self.entered = True
        return execute_order('BUY', raw_open, account.cash, account.quantity, self.costs)

    def signal(self, target, account):
        if target is None:
            return 'WAIT'
        return 'HOLD' if self.entered else 'BUY'


class FxExecutionModel:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Forex execution requires confirmed spread, lot, leverage, margin, swap and short rules')
