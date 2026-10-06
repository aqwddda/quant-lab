from enum import Enum


class AssetClass(str, Enum):
    EQUITY = 'equity'
    FOREX = 'forex'
    FUTURES = 'futures'


class TimestampSemantics(str, Enum):
    BAR_START = 'bar_start'
    BAR_END = 'bar_end'
