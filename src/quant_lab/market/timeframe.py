"""Fixed elapsed-time bars. Calendar/session aggregation requires a separate rule."""
from datetime import timedelta
from enum import Enum
from functools import total_ordering


@total_ordering
class Timeframe(Enum):
    M1 = '1m'
    M5 = '5m'
    M15 = '15m'
    M30 = '30m'
    H1 = '1h'
    H4 = '4h'
    D1 = '1d'

    @classmethod
    def parse(cls, value):
        return value if isinstance(value, cls) else cls(value)

    @property
    def duration(self):
        return timedelta(minutes={'1m': 1, '5m': 5, '15m': 15, '30m': 30,
                                  '1h': 60, '4h': 240, '1d': 1440}[self.value])

    def __lt__(self, other):
        if not isinstance(other, Timeframe):
            return NotImplemented
        return self.duration < other.duration

    def can_resample_to(self, target):
        target = self.parse(target)
        return target > self and target.duration % self.duration == timedelta(0)
