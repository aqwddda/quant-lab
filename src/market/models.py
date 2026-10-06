"""Immutable bars contain only a completed observation, never future data."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from .enums import AssetClass
from .timeframe import Timeframe


def utc_datetime(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Require timezone-aware UTC timestamp')
    if value.utcoffset().total_seconds() != 0:
        raise ValueError('Require UTC timestamp')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Instrument:
    symbol: str
    provider_symbol: str
    asset_class: AssetClass
    venue: str
    base_currency: str | None = None
    quote_currency: str | None = None
    tick_size: float | None = None
    lot_size: float | None = None
    contract_multiplier: float | None = None
    expiry: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'asset_class', AssetClass(self.asset_class))
        for name in ('symbol', 'provider_symbol', 'venue'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f'Instrument requires {name}')
        for name in ('tick_size', 'lot_size', 'contract_multiplier'):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f'Invalid {name}')


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    timeframe: Timeframe = Timeframe.D1
    volume: float | None = None
    tick_volume: float | None = None
    amount: float | None = None
    open_interest: float | None = None

    def __post_init__(self):
        object.__setattr__(self, 'timestamp', utc_datetime(self.timestamp))
        object.__setattr__(self, 'timeframe', Timeframe.parse(self.timeframe))
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError('Bar requires symbol')
        prices = [self.open, self.high, self.low, self.close]
        if any(isinstance(x, bool) or not math.isfinite(x) or x <= 0 for x in prices):
            raise ValueError('OHLC must be finite and positive')
        if self.high < max(prices) or self.low > min(prices):
            raise ValueError('Impossible OHLC')
        for name in ('volume', 'tick_volume', 'amount', 'open_interest'):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not math.isfinite(value) or value < 0):
                raise ValueError(f'Invalid {name}')
        if self.tick_volume is not None and self.tick_volume % 1:
            raise ValueError('tick_volume must be integer')

    @property
    def available_at(self):
        return self.timestamp + self.timeframe.duration
