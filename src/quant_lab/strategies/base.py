"""A strategy sees one completed bar and emits one target-position model."""
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Protocol


@dataclass(frozen=True)
class StrategyContext:
    index: int
    available_at: datetime


@dataclass(frozen=True)
class TargetPosition:
    target: int | None  # None = unavailable; 0 = cash; 1 = long
    diagnostics: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.target is not None and (type(self.target) is not int or self.target not in (0, 1)):
            raise ValueError('Target must be None, 0 or 1')
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))


class Strategy(Protocol):
    def reset(self): ...
    def on_bar(self, context: StrategyContext, bar) -> TargetPosition: ...
