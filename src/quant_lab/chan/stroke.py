"""Alternating endpoints, minimum merged distance and immutable confirmations."""
from dataclasses import replace
from .enums import Direction, FractalType, StrokeStatus
from .models import Stroke


def more_extreme(candidate, previous):
    if candidate.type != previous.type:
        raise ValueError('Extremum comparison requires same-type fractals')
    # Provisional equality behavior: strict replacement only; ties keep first.
    return (candidate.price > previous.price if candidate.type == FractalType.TOP
        else candidate.price < previous.price)


def assert_stroke_extremes(stroke, merged_bars):
    interval = merged_bars[stroke.start.center.index:stroke.end.center.index + 1]
    if not interval:
        raise ValueError('Stroke interval is empty')
    low, high = min(x.low for x in interval), max(x.high for x in interval)
    if stroke.direction == Direction.UP:
        valid = stroke.start.price == low and stroke.end.price == high
    else:
        valid = stroke.start.price == high and stroke.end.price == low
    if not valid:
        raise ValueError('Stroke endpoint extreme invariant violated')


class StrokeBuilder:
    def __init__(self):
        self._anchor = None
        self._current = None
        self._confirmed = []
        self._last_fractal = None

    @property
    def confirmed_strokes(self):
        return tuple(self._confirmed)

    @property
    def current_stroke(self):
        return self._current

    @property
    def strokes(self):
        return (*self._confirmed, *((self._current,) if self._current else ()))

    def _propose(self, start, end, merged_bars):
        if end.center.index - start.center.index < 4:
            return None
        direction = Direction.UP if start.type == FractalType.BOTTOM else Direction.DOWN
        stroke = Stroke(start, end, direction)
        # Explicit interval assertion. No extra fractal price-separation rule;
        # gaps do not add synthetic merged bars to the required distance.
        assert_stroke_extremes(stroke, merged_bars)
        return stroke

    def update(self, fractal, merged_bars):
        if self._last_fractal is not None and (fractal.center.index <= self._last_fractal.center.index
                or fractal.confirmed_at < self._last_fractal.confirmed_at):
            raise ValueError('Fractals must arrive in confirmation order')
        if self._current is None:
            if self._anchor is None:
                self._anchor = fractal
            elif fractal.type == self._anchor.type:
                if more_extreme(fractal, self._anchor):
                    self._anchor = fractal
            else:
                proposal = self._propose(self._anchor, fractal, merged_bars)
                if proposal is not None:
                    self._current = proposal
        elif fractal.type == self._current.end.type:
            if more_extreme(fractal, self._current.end):
                proposal = self._propose(self._current.start, fractal, merged_bars)
                if proposal is not None:
                    self._current = proposal
        else:
            proposal = self._propose(self._current.end, fractal, merged_bars)
            if proposal is not None:
                self._confirmed.append(replace(self._current, status=StrokeStatus.CONFIRMED,
                    confirmed_at=fractal.confirmed_at))
                self._current = proposal
        self._last_fractal = fractal
