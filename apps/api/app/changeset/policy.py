"""Risk ladder and environment policy for change-set ops."""

from __future__ import annotations

from typing import Any

from app.changeset.ops import op_base_risk
from app.changeset.protected_registry import protection_level, requires_domain_owner

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
    no_simulation_on_production: bool = False,
    tenant: dict[str, Any] | None = None,
    document: list[dict[str, Any]] | None = None,
) -> str:
    """Catalog risk plus escalations. Each escalation adds one. The result stays in R0–R4.

    Inputs: one op and optional impact flags. A `risk` key on the op is ignored, so a
    caller cannot talk the catalog class down. `no_simulation_on_production` is a
    production apply with no recorded simulation. Defaults leave existing callers unchanged.
    Output: R0–R4.
    Side effects: none.
    """
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
    if no_simulation_on_production:
        bumps += 1
    if mode_c:
        bumps += 1
    return _bump(base, bumps)


def policy_decision(
    risk: str,
    environment: str,
    *,
    autonomy: str = "L2",
    elevated: bool = False,
) -> dict[str, bool | int]:
    """Who must approve.

    Inputs: risk class, environment, autonomy, and whether the target is protected:elevate.
    Output: allow, approvers, needs_simulation, deny, and domain_owner.
    Side effects: none. An elevated target that is still allowed needs a domain-owner
    approver. R4 stays denied, so a domain owner cannot unlock it.
    """

    def finish(allow: bool, approvers: int, needs_simulation: bool, deny: bool) -> dict[str, bool | int]:
        return {
            "allow": allow,
            "approvers": approvers,
            "needs_simulation": needs_simulation,
            "deny": deny,
            "domain_owner": bool(elevated) and not deny,
        }

    env = environment.lower()
    deny = risk == "R4"
    if deny:
        return finish(False, 0, False, True)

    if env == "staging":
        if risk == "R0":
            return finish(True, 0, False, False)
        if risk == "R1":
            approvers = 0 if autonomy in {"L3", "L4"} else 1
            return finish(True, approvers, False, False)
        if risk in {"R2", "R3"}:
            return finish(True, 1, False, False)
        return finish(False, 0, False, True)

    # production (default)
    if risk == "R0":
        return finish(True, 0, False, False)
    if risk in {"R1", "R2"}:
        return finish(True, 1, True, False)
    if risk == "R3":
        return finish(True, 2, True, False)
    return finish(False, 0, False, True)


def policy_for_op(
    op: dict[str, Any],
    environment: str,
    *,
    autonomy: str = "L2",
    tenant: dict[str, Any] | None = None,
    document: list[dict[str, Any]] | None = None,
    rows: int = 0,
    users: int = 0,
    outbound: bool = False,
    mode_c: bool = False,
    no_simulation_on_production: bool = False,
) -> dict[str, bool | int]:
    """Policy for one op, including the protected:elevate domain-owner requirement.

    Inputs: the op, environment, and the same risk bumps `risk_of` accepts.
    Output: the policy decision. `domain_owner` is true only for an allowed elevate.
    Side effects: none.
    """
    risk = risk_of(
        op,
        rows=rows,
        users=users,
        outbound=outbound,
        mode_c=mode_c,
        no_simulation_on_production=no_simulation_on_production,
        tenant=tenant,
        document=document,
    )
    elevated = requires_domain_owner(op, document=document, tenant=tenant)
    return policy_decision(risk, environment, autonomy=autonomy, elevated=elevated)


def self_approval_allowed(risk: str) -> bool:
    return risk not in {"R3", "R4"}
