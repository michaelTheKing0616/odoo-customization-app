"""Risk ladder and environment policy for change-set ops."""

from __future__ import annotations

from typing import Any

from app.changeset.ops import op_base_risk
from app.changeset.protected_registry import protection_level

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")


def _bump(risk: str, steps: int) -> str:
    idx = _RISK_ORDER.index(risk)
    return _RISK_ORDER[min(idx + steps, len(_RISK_ORDER) - 1)]


def risk_of(
    op: dict[str, Any],
    *,
    rows: int = 0,
    users: int = 0,
    outbound: bool = False,
    mode_c: bool = False,
    protected: bool = False,
    tenant: dict[str, Any] | None = None,
    document: list[dict[str, Any]] | None = None,
) -> str:
    op_type = str(op.get("type", ""))
    params = op.get("params")
    if not isinstance(params, dict):
        params = {}
    base = op_base_risk(op_type, params)
    if base == "R4":
        return "R4"
    level = protection_level(op, tenant=tenant, document=document)
    if level == "deny":
        return "R4"
    bumps = 0
    if protected:
        bumps += 1
    if level == "elevate":
        bumps += 1
    if rows > 1000:
        bumps += 1
    if users > 10:
        bumps += 1
    if outbound:
        bumps += 1
    if mode_c:
        bumps += 1
    return _bump(base, bumps)


def policy_decision(
    risk: str,
    environment: str,
    *,
    autonomy: str = "L2",
) -> dict[str, bool | int]:
    env = environment.lower()
    deny = risk == "R4"
    if deny:
        return {"allow": False, "approvers": 0, "needs_simulation": False, "deny": True}

    if env == "staging":
        if risk == "R0":
            return {"allow": True, "approvers": 0, "needs_simulation": False, "deny": False}
        if risk == "R1":
            approvers = 0 if autonomy in {"L3", "L4"} else 1
            return {"allow": True, "approvers": approvers, "needs_simulation": False, "deny": False}
        if risk in {"R2", "R3"}:
            return {"allow": True, "approvers": 1, "needs_simulation": False, "deny": False}
        return {"allow": False, "approvers": 0, "needs_simulation": False, "deny": True}

    # production (default)
    if risk == "R0":
        return {"allow": True, "approvers": 0, "needs_simulation": False, "deny": False}
    if risk in {"R1", "R2"}:
        return {"allow": True, "approvers": 1, "needs_simulation": True, "deny": False}
    if risk == "R3":
        return {"allow": True, "approvers": 2, "needs_simulation": True, "deny": False}
    return {"allow": False, "approvers": 0, "needs_simulation": False, "deny": True}


def self_approval_allowed(risk: str) -> bool:
    return risk not in {"R3", "R4"}
