from enum import Enum


class Direction(str, Enum):
    UP = 'up'
    DOWN = 'down'


class FractalType(str, Enum):
    TOP = 'top'
    BOTTOM = 'bottom'


class StrokeStatus(str, Enum):
    TENTATIVE = 'tentative'
    CONFIRMED = 'confirmed'


class InitialDirectionPolicy(str, Enum):
    ERROR = 'error'
    UP = 'up'
    DOWN = 'down'
