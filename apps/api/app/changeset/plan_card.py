"""Human-facing plan card from a validated change-set."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.changeset.handlers import handler_for
from app.changeset.ops import OP_CATALOG
from app.changeset.policy import approval_expiry_hours, policy_decision, risk_of

PLAN_CARD_SECTIONS = (
    "goal",
    "assumptions",
    "changes",
    "impact",
    "risk",
    "not_changing",
    "verification",
    "rollback",
    "environment",
    "plan_hash",
    "expires_at",
)
_OUT_OF_SCOPE = ("data.delete", "module.uninstall", "rpc.write")


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def compute_plan_hash(changeset: list[dict[str, Any]], *, assumptions: list[str] | tuple[str, ...]) -> str:
    return _canonical_hash({"changeset": changeset, "assumptions": list(assumptions)})


def render_plan_card(
    changeset: list[dict[str, Any]],
    *,
    goal: str,
    assumptions: list[str] | tuple[str, ...],
    environment: str,
) -> dict[str, Any]:
    changes = []
    rollback = []
    for op in changeset:
        op_type = str(op.get("type") or "")
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if op_type in OP_CATALOG:
            handler = handler_for(op_type)
            description = handler.describe(params)
            inverse = handler.inverse(params, document=changeset)
        else:
            description = f"{op_type} is not in the catalog"
            inverse = None
        changes.append({**dict(op), "description": description})
        rollback.append(
            {"op": op_type, "inverse": None if inverse is None else inverse["type"], "irreversible": inverse is None}
        )
    risks = [risk_of(op, document=changeset) for op in changeset]
    order = ("R0", "R1", "R2", "R3", "R4")
    max_risk = max(risks, key=lambda r: order.index(r)) if risks else "R0"
    decision = policy_decision(max_risk, environment)

    env = environment.lower()
    expires = datetime.now(timezone.utc) + timedelta(
        hours=approval_expiry_hours(max_risk, env)
    )

    return {
        "goal": goal,
        "assumptions": list(assumptions),
        "changes": changes,
        "impact": {"op_count": len(changes)},
        "risk": {"per_op": risks, "max": max_risk, "policy": decision},
        "not_changing": [name for name in _OUT_OF_SCOPE if name not in {str(op.get("type") or "") for op in changeset}],
        "verification": [f"postcondition:{op.get('type')}" for op in changeset] or ["no_ops"],
        "rollback": rollback,
        "environment": environment,
        "plan_hash": compute_plan_hash(changeset, assumptions=assumptions),
        "expires_at": expires.isoformat(),
    }
