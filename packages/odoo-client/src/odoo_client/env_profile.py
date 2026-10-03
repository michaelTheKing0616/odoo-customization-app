"""Environment profile. An unknown capability is treated as unavailable."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EnvProfile:
    major: int
    capabilities: dict[str, str] = field(default_factory=dict)

    def allows(self, name: str) -> bool:
        return self.capabilities.get(name) == "yes"
