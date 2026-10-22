"""Dynamic tool targets resolve through the existing schema client.

A model, field, or method the client rejects is not offered as a tool target.
This module does not register write tools and does not edit agent_runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

TargetKind = Literal["model", "field", "method"]


@dataclass(frozen=True, slots=True)
class ToolTarget:
    """One model, field, or method a dynamic tool may point at.

    Inputs: kind, the model technical name, and the field or method name.
    ``name`` is required for field and method targets and unused for model.
    """

    kind: TargetKind
    model: str
    name: str | None = None


def accept_tool_target(client: Any, target: ToolTarget) -> bool:
    """True only when ``schema_client`` admits this target.

    Inputs: a schema client and one candidate.
    Side effects: none. Unknown names fail closed.
    """
    model = str(target.model or "").strip()
    if not model:
        return False
    try:
        if not client.model_exists(model):
            return False
    except Exception:  # noqa: BLE001
        return False
    if target.kind == "model":
        return True
    name = str(target.name or "").strip()
    if not name:
        return False
    if target.kind == "field":
        try:
            fields = client.fields_get(model) or {}
        except Exception:  # noqa: BLE001
            return False
        return name in fields
    if target.kind == "method":
        try:
            return bool(client.method_exists(model, name))
        except Exception:  # noqa: BLE001
            return False
    return False


def offer_tool_targets(
    client: Any, candidates: Iterable[ToolTarget]
) -> tuple[ToolTarget, ...]:
    """Return the subset of ``candidates`` the schema client admits.

    A rejected target is dropped. It never becomes a tool.
    """
    return tuple(target for target in candidates if accept_tool_target(client, target))


__all__ = [
    "ToolTarget",
    "accept_tool_target",
    "offer_tool_targets",
]
