"""Risk ladder and environment policy for change-set ops."""

from __future__ import annotations

from typing import Any

from app.changeset.ops import op_base_risk
from app.changeset.protected_registry import protection_level, requires_domain_owner

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
# Staging R1 needs no human approval at L3 and L4. Production does not use this set.
_STAGING_R1_OPEN_AUTONOMY = frozenset({"L3", "L4"})
STAGING_APPROVAL_EXPIRY_HOURS = 7 * 24
PRODUCTION_R2_APPROVAL_EXPIRY_HOURS = 24


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


def approval_expiry_hours(risk: str, environment: str) -> int:
    """How long an approval stays valid.

    Inputs: risk class R0–R4 and environment. Any environment other than staging
    follows the production rule.
    Output: 24 hours on production when risk is R2 or higher. 168 hours (7 days)
    on staging, and on production for R0 and R1, where the 24-hour rule does not apply.
    Side effects: none. Raises ValueError for an unknown risk class.
    """
    if risk not in _RISK_ORDER:
        raise ValueError(f"unknown risk class: {risk}")
    high = _RISK_ORDER.index(risk) >= _RISK_ORDER.index("R2")
    if environment.lower() != "staging" and high:
        return PRODUCTION_R2_APPROVAL_EXPIRY_HOURS
    return STAGING_APPROVAL_EXPIRY_HOURS


def approval_count_met(received: int, required: int) -> bool:
    """Whether distinct approvers satisfy the required count.

    Inputs: distinct approvers already recorded, and the count from the matrix.
    Output: True when received >= required. An equal count is enough.
    Side effects: none.
    """
    return received >= required


def apply_blocked(decision: dict[str, bool | int], *, frozen: bool) -> bool:
    """Whether apply must stop.

    Inputs: a policy decision and whether a freeze window is active.
    Output: True when a freeze is on, or the decision denies or does not allow.
    A freeze blocks every apply, including a cell the matrix would otherwise allow.
    Side effects: none.
    """
    if frozen:
        return True
    return bool(decision["deny"]) or not bool(decision["allow"])


def policy_decision(
    risk: str,
    environment: str,
    *,
    autonomy: str = "L2",
    elevated: bool = False,
) -> dict[str, bool | int]:
    """Who must approve.

    Inputs: risk class, environment, autonomy, and whether the target is protected:elevate.
    Output: allow, approvers, needs_simulation, deny, domain_owner, needs_backup,
    needs_window, and expiry_hours. L4 does not reduce a production approval.
    Side effects: none. An elevated target that is still allowed needs a domain-owner
    approver. R4 stays denied, so a domain owner cannot unlock it. Production R3 also
    needs a passed simulation, a backup, and an allowed window.
    """

    def finish(
        allow: bool,
        approvers: int,
        needs_simulation: bool,
        deny: bool,
        *,
        needs_backup: bool = False,
        needs_window: bool = False,
    ) -> dict[str, bool | int]:
        known = risk if risk in _RISK_ORDER else "R4"
        return {
            "allow": allow,
            "approvers": approvers,
            "needs_simulation": needs_simulation,
            "deny": deny,
            "domain_owner": bool(elevated) and not deny,
            "needs_backup": needs_backup,
            "needs_window": needs_window,
            "expiry_hours": approval_expiry_hours(known, env),
        }

    env = environment.lower()
    deny = risk == "R4"
    if deny:
        return finish(False, 0, False, True)

    if env == "staging":
        if risk == "R0":
            return finish(True, 0, False, False)
        if risk == "R1":
            approvers = 0 if autonomy in _STAGING_R1_OPEN_AUTONOMY else 1
            return finish(True, approvers, False, False)
        if risk in {"R2", "R3"}:
            return finish(True, 1, False, False)
        return finish(False, 0, False, True)

    # production (default). L4 stays off: no production auto-approve path.
    if risk == "R0":
        return finish(True, 0, False, False)
    if risk in {"R1", "R2"}:
        return finish(True, 1, True, False)
    if risk == "R3":
        return finish(True, 2, True, False, needs_backup=True, needs_window=True)
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
