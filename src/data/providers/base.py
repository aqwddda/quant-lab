"""Small provider contract; unsupported capabilities raise NotImplementedError."""
from typing import Protocol


def check_request(symbol, start, end, frequency='1d'):
    from src.data.manifest import safe_component, iso_date
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
