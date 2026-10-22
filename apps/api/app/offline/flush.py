"""Apply a queued offline item once. Does not write Odoo."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

QUEUED_KINDS = ("mutation", "promote")

# In-process effect log for exactly-once tests. Not an Odoo write.
_EFFECTS: list[dict[str, Any]] = []


class FlushBody(BaseModel):
    kind: Literal["mutation", "promote"]
    method: Literal["POST", "PUT", "PATCH", "DELETE"] = "POST"
    path: str = Field(min_length=1, max_length=512)
    body: dict[str, Any] = Field(default_factory=dict)
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


def reset_flush_effects() -> None:
    _EFFECTS.clear()


def recorded_flush_effects() -> list[dict[str, Any]]:
    return list(_EFFECTS)


def apply_queued_flush(body: FlushBody) -> dict[str, Any]:
    """Record one server effect. Caller must already have claimed the key."""
    effect = {
        "kind": body.kind,
        "method": body.method,
        "path": body.path,
    }
    _EFFECTS.append(effect)
    return {
        "applied": True,
        "kind": body.kind,
        "method": body.method,
        "path": body.path,
        "effect_seq": len(_EFFECTS),
    }
