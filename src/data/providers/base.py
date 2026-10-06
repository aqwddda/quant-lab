"""Small provider contract; unsupported capabilities raise NotImplementedError."""
from dataclasses import dataclass
from typing import Protocol
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
