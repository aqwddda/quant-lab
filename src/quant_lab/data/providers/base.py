"""Small provider contract; unsupported capabilities raise NotImplementedError."""
from typing import Protocol


def check_request(symbol, start, end, frequency='1d'):
    from quant_lab.data.manifest import safe_component, iso_date
    safe_component(symbol)
    if frequency != '1d':
        raise ValueError('Only daily frequency 1d is supported')
    first, last = iso_date(start), iso_date(end)
    if first > last:
        raise ValueError('start must not exceed end')
    return first, last


class DataProvider(Protocol):
    name: str

    def fetch_bars(self, symbol: str, start: str, end: str, frequency: str = '1d'): ...
    def fetch_instrument(self, symbol: str): ...
    def fetch_adjustments(self, symbol: str, start: str, end: str): ...
    def fetch_corporate_actions(self, symbol: str, start: str, end: str): ...
    def fetch_calendar(self, start: str, end: str): ...


from dataclasses import dataclass
from quant_lab.market import AssetClass, Timeframe


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
