"""One download's supplier snapshots and its explicitly prepared session labels."""
from dataclasses import dataclass, field


@dataclass
class ProviderSnapshot:
    source_frames: dict
    prepared: dict
    provider_version: str
    assumptions: list[str] = field(default_factory=list)
