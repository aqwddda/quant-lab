"""Incremental containment processing using the latest merged range."""
from dataclasses import replace
from .config import ChanConfig
from .enums import Direction, InitialDirectionPolicy
from .models import MergedBar


def includes(first, second):
    return ((first.high >= second.high and first.low <= second.low)
        or (second.high >= first.high and second.low <= first.low))


def direction_between(first, second):
    if second.high > first.high and second.low > first.low:
        return Direction.UP
    if second.high < first.high and second.low < first.low:
        return Direction.DOWN
    raise ValueError('Direction requires two non-containing ranges')


class InclusionProcessor:
    def __init__(self, config=None):
        self.config = config or ChanConfig()
        self._bars = []
        self._direction = None
        self._raw_count = 0
        self._last_bar = None

    @property
    def merged_bars(self):
        return tuple(self._bars)

    @property
    def tail(self):
        return tuple(self._bars[-3:])

    def update(self, bar):
        if self._last_bar is not None:
            if bar.symbol != self._last_bar.symbol or bar.timeframe != self._last_bar.timeframe:
                raise ValueError('Chan requires one symbol and timeframe')
            if bar.timestamp < self._last_bar.available_at:
                raise ValueError('Chan bars must be chronological and non-overlapping')
        raw_index = self._raw_count
        if self._bars and includes(self._bars[-1], bar):
            direction = self._direction
            if direction is None:
                policy = self.config.initial_direction_policy
                if policy == InitialDirectionPolicy.ERROR:
                    raise ValueError('Initial inclusion has no established direction; choose an explicit initial policy')
                # Provisional user-selected policy, never inferred from candle color.
                direction = Direction(policy.value)
            previous = self._bars[-1]
            merge = max if direction == Direction.UP else min
            self._bars[-1] = replace(previous, high=merge(previous.high, bar.high),
                low=merge(previous.low, bar.low), end_timestamp=bar.timestamp,
                available_at=bar.available_at, raw_bars=previous.raw_bars + (bar,),
                raw_indices=previous.raw_indices + (raw_index,), direction=direction)
            self._direction = direction
            appended = False
        else:
            if self._bars:
                self._direction = direction_between(self._bars[-1], bar)
            self._bars.append(MergedBar(len(self._bars), bar.high, bar.low, bar.timestamp,
                bar.timestamp, bar.available_at, (bar,), (raw_index,), self._direction))
            appended = True
        self._raw_count += 1
        self._last_bar = bar
        return appended
