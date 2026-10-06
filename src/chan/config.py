from dataclasses import dataclass
from .enums import InitialDirectionPolicy


@dataclass(frozen=True)
class ChanConfig:
    initial_direction_policy: InitialDirectionPolicy = InitialDirectionPolicy.ERROR

    def __post_init__(self):
        object.__setattr__(self, 'initial_direction_policy', InitialDirectionPolicy(self.initial_direction_policy))
