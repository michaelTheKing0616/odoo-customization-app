"""Bot Grant. Prose does not grant permission. Effective rights are an intersection."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass

from app.changeset.handlers import handler_for
from app.changeset.ops import op_base_risk

_ORDER = ("R0", "R1", "R2", "R3", "R4")


def _at_most(risk: str, ceiling: str) -> bool:
    return _ORDER.index(risk) <= _ORDER.index(ceiling)


def _matches(op_type: str, patterns: frozenset[str]) -> bool:
    return any(fnmatch.fnmatch(op_type, pattern) for pattern in patterns)


@dataclass(frozen=True, slots=True)
class BotGrant:
    bot_id: str
    ops_allowed: frozenset[str]
    risk_ceiling: str
    autonomy_cap: str = "L2"
    apps_allowed: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.risk_ceiling not in _ORDER:
            raise ValueError(f"invalid risk ceiling {self.risk_ceiling!r}")
        if self.risk_ceiling == "R4":
            raise ValueError("a grant cannot allow R4")


def decide(
    grant: BotGrant,
    op: dict,
    *,
    requester_ops: frozenset[str] | None = None,
) -> str | None:
    """Return a deny reason, or None when the op is allowed.

    Description text is not an input. A template's requested grant is not this object
    until a human has already approved it.
    """
    op_type = str(op.get("type") or "")
    params = op.get("params") if isinstance(op.get("params"), dict) else {}
    try:
        handler = handler_for(op_type)
    except KeyError:
        return "unknown_op"
    reason = handler.refuse_reason(params)
    if reason:
        return "prohibited"
    if handler.issues(params):
        return "invalid_params"
    if not _matches(op_type, grant.ops_allowed):
        return "grant"
    if requester_ops is not None and not _matches(op_type, requester_ops):
        return "requester"
    risk = op_base_risk(op_type, params)
    if not _at_most(risk, grant.risk_ceiling):
        return "ceiling"
    return None


def install_template_grant(requested: BotGrant, *, human_approved: bool) -> BotGrant | None:
    """Templates never install a grant by themselves."""
    if not human_approved:
        return None
    return requested
