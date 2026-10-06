"""Immutable structure snapshots. Managers own all transitions."""
from dataclasses import dataclass
from datetime import datetime
from quant_lab.market import Bar
from .enums import Direction, FractalType, StrokeStatus


@dataclass(frozen=True)
class MergedBar:
    index: int
    high: float
    low: float
    start_timestamp: datetime
    end_timestamp: datetime
    available_at: datetime
    raw_bars: tuple[Bar, ...]
    raw_indices: tuple[int, ...]
    direction: Direction | None


@dataclass(frozen=True)
class Fractal:
    type: FractalType
    left: MergedBar
    center: MergedBar
    right: MergedBar
    pivot_time: datetime
    confirmed_at: datetime
    price: float


@dataclass(frozen=True)
class Stroke:
    start: Fractal
    end: Fractal
    direction: Direction
    status: StrokeStatus = StrokeStatus.TENTATIVE
    confirmed_at: datetime | None = None
