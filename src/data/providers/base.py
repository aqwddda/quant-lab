"""Small provider contract; unsupported capabilities raise NotImplementedError."""
from typing import Protocol


def check_request(symbol, start, end, frequency='1d'):
    from datetime import date
    from src.data.manifest import safe_component
    safe_component(symbol)
    if frequency != '1d':
        raise ValueError('Only daily frequency 1d is supported')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first.isoformat() != start or last.isoformat() != end:
        raise ValueError('Dates must use YYYY-MM-DD format')
    if first > last:
        raise ValueError('start must not exceed end')
    return first, last


from dataclasses import dataclass
from src.market import AssetClass, Timeframe


@dataclass(frozen=True)
class ProviderCapabilities:
    asset_classes: frozenset[AssetClass]
    timeframes: frozenset[Timeframe]
    supports_adjustments: bool = False
    supports_corporate_actions: bool = False
    supports_calendar: bool = False

    def require(self, asset_class, timeframe):
        if AssetClass(asset_class) not in self.asset_classes or Timeframe.parse(timeframe) not in self.timeframes:
            raise NotImplementedError('Provider does not support requested asset class/timeframe')


class BarProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def fetch_snapshot(self, *args, **kwargs): ...
