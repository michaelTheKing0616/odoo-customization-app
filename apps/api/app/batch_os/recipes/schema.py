"""Recipe card schema for API / atlas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.batch_os.types import RiskTier


@dataclass
class RecipeCard:
    id: str
    title: str
    blurb: str
    risk: RiskTier
    status: str  # complete | stub
    atlas_class: str
    models: list[str] = field(default_factory=list)
    phases: list[str] = field(
        default_factory=lambda: ["intake", "map", "validate", "dry_run", "apply"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
