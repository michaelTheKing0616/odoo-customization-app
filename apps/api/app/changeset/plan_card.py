"""Human-facing plan card from a validated change-set."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from odoo_client.schema_fingerprint import schema_fingerprint

from app.changeset.handlers import handler_for
from app.changeset.ops import OP_CATALOG
from app.changeset.policy import approval_expiry_hours, changeset_r4_posture, policy_decision, risk_of
from app.changeset.setting_ops import billable_warning

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
PLAN_CARD_COPY_SECTIONS = (
    "goal and assumptions",
    "each change",
    "impact",
    "risk and why",
    "what is not changing",
    "how it will be checked",
    "how to undo",
    "environment",
    "plan fingerprint and expiry",
)
_OUT_OF_SCOPE = ("data.delete", "module.uninstall", "rpc.write")


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def compute_plan_hash(changeset: list[dict[str, Any]], *, assumptions: list[str] | tuple[str, ...]) -> str:
    return _canonical_hash({"changeset": changeset, "assumptions": list(assumptions)})


def changeset_ops_fingerprint(changeset: list[dict[str, Any]]) -> str:
    """Identity of the ops only. Assumptions are excluded.

    Inputs: the change-set list.
    Output: a 16-hex fingerprint of type+params per op.
    Side effects: none.
    """
    ops: list[dict[str, Any]] = []
    for op in changeset:
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        ops.append({"type": op.get("type"), "params": params})
    return _canonical_hash(ops)


def ops_from_card_changes(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Recover the submitted ops from a rendered card.

    Inputs: a plan card with a `changes` list.
    Output: type+params only, in order. Description is dropped.
    Side effects: none.
    """
    ops: list[dict[str, Any]] = []
    for change in card.get("changes") or []:
        if not isinstance(change, dict):
            continue
        params = change.get("params") if isinstance(change.get("params"), dict) else {}
        ops.append({"type": change.get("type"), "params": params})
    return ops


def _change_line(change: dict[str, Any]) -> str:
    line = str(change.get("description") or change.get("type") or "")
    warning = change.get("billable_warning")
    if warning:
        return f"{line}. {warning}"
    return line


def _copy_sections(
    *,
    goal: str,
    assumptions: list[str],
    changes: list[dict[str, Any]],
    impact: dict[str, Any],
    risk: dict[str, Any],
    not_changing: list[str],
    verification: list[str],
    rollback: list[dict[str, Any]],
    environment: str,
    plan_hash: str,
    expires_at: str,
) -> list[dict[str, str]]:
    """Nine human sections. Titles and bodies are engine strings.

    Inputs: the structured fields already on the card.
    Output: nine `{title, body}` objects in PLAN_CARD_COPY_SECTIONS order.
    Side effects: none. The web page must render these strings as sent.
    """
    assumption_lines = list(assumptions) or ["none"]
    change_lines = [_change_line(item) for item in changes] or ["none"]
    policy = risk.get("policy") if isinstance(risk.get("policy"), dict) else {}
    risk_lines = [f"max {risk.get('max')}"]
    per_op = risk.get("per_op") if isinstance(risk.get("per_op"), list) else []
    if per_op:
        risk_lines.append("per_op " + ", ".join(str(item) for item in per_op))
    if policy.get("deny"):
        risk_lines.append("denied")
    else:
        risk_lines.append(f"approvers {policy.get('approvers')}")
        if policy.get("needs_simulation"):
            risk_lines.append("needs simulation")
        if policy.get("domain_owner"):
            risk_lines.append("needs domain owner")
        if policy.get("needs_backup"):
            risk_lines.append("needs backup")
        if policy.get("needs_window"):
            risk_lines.append("needs window")
    undo_lines: list[str] = []
    for item in rollback:
        op_type = str(item.get("op") or "")
        if item.get("irreversible") or item.get("inverse") is None:
            undo_lines.append(f"{op_type} irreversible")
        else:
            undo_lines.append(f"{op_type} inverse {item.get('inverse')}")
    bodies = (
        "\n".join([goal, *assumption_lines]),
        "\n".join(change_lines),
        f"op_count {impact.get('op_count')}",
        "\n".join(risk_lines),
        "\n".join(not_changing) if not_changing else "none",
        "\n".join(verification),
        "\n".join(undo_lines) if undo_lines else "none",
        environment,
        f"{plan_hash}\n{expires_at}",
    )
    return [
        {"title": title, "body": body}
        for title, body in zip(PLAN_CARD_COPY_SECTIONS, bodies, strict=True)
    ]


def copy_sections_for_card(card: dict[str, Any]) -> list[dict[str, str]]:
    """Nine engine copy sections from a stored card's structured fields.

    Inputs: a plan card, including one stored before `sections` existed.
    Output: nine `{title, body}` objects in PLAN_CARD_COPY_SECTIONS order.
    Side effects: none. Does not recompute `plan_hash` or call Odoo.
    """
    assumptions = card.get("assumptions") if isinstance(card.get("assumptions"), list) else []
    changes = card.get("changes") if isinstance(card.get("changes"), list) else []
    not_changing = card.get("not_changing") if isinstance(card.get("not_changing"), list) else []
    verification = card.get("verification") if isinstance(card.get("verification"), list) else []
    rollback = card.get("rollback") if isinstance(card.get("rollback"), list) else []
    return _copy_sections(
        goal=str(card.get("goal") or ""),
        assumptions=[str(item) for item in assumptions],
        changes=[item for item in changes if isinstance(item, dict)],
        impact=card.get("impact") if isinstance(card.get("impact"), dict) else {},
        risk=card.get("risk") if isinstance(card.get("risk"), dict) else {},
        not_changing=[str(item) for item in not_changing],
        verification=[str(item) for item in verification],
        rollback=[item for item in rollback if isinstance(item, dict)],
        environment=str(card.get("environment") or ""),
        plan_hash=str(card.get("plan_hash") or ""),
        expires_at=str(card.get("expires_at") or ""),
    )


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
        change = {**dict(op), "description": description}
        warning = billable_warning(op_type, params)
        if warning:
            change["billable"] = True
            change["billable_warning"] = warning
        changes.append(change)
        rollback.append(
            {"op": op_type, "inverse": None if inverse is None else inverse["type"], "irreversible": inverse is None}
        )
    risks = [risk_of(op, document=changeset) for op in changeset]
    order = ("R0", "R1", "R2", "R3", "R4")
    max_risk = max(risks, key=lambda r: order.index(r)) if risks else "R0"
    decision = policy_decision(
        max_risk,
        environment,
        heavy=changeset_r4_posture(changeset) == "heavy" and max_risk == "R4",
    )

    env = environment.lower()
    expires = datetime.now(timezone.utc) + timedelta(
        hours=approval_expiry_hours(max_risk, env)
    )

    impact = {"op_count": len(changes)}
    risk = {"per_op": risks, "max": max_risk, "policy": decision}
    not_changing = [name for name in _OUT_OF_SCOPE if name not in {str(op.get("type") or "") for op in changeset}]
    verification = [f"postcondition:{op.get('type')}" for op in changeset] or ["no_ops"]
    plan_hash = compute_plan_hash(changeset, assumptions=assumptions)
    expires_at = expires.isoformat()
    return {
        "goal": goal,
        "assumptions": list(assumptions),
        "changes": changes,
        "impact": impact,
        "risk": risk,
        "not_changing": not_changing,
        "verification": verification,
        "rollback": rollback,
        "environment": environment,
        "plan_hash": plan_hash,
        "expires_at": expires_at,
        "sections": _copy_sections(
            goal=goal,
            assumptions=list(assumptions),
            changes=changes,
            impact=impact,
            risk=risk,
            not_changing=not_changing,
            verification=verification,
            rollback=rollback,
            environment=environment,
            plan_hash=plan_hash,
            expires_at=expires_at,
        ),
    }


def bound_schema_fp(
    changeset: list[dict[str, Any]],
    *,
    environment: str,
    schema_slice: dict[str, Any] | None = None,
) -> str:
    """Schema fingerprint bound to a plan card at submit.

    Inputs: the change-set, its environment, and an optional schema slice.
    A slice is hashed as given. Without one, the fingerprint covers the
    environment and the model names on the ops.
    Output: the schema fingerprint string.
    Side effects: none. Does not call Odoo.
    """
    if schema_slice is not None:
        return schema_fingerprint(schema_slice)
    models: list[str] = []
    for op in changeset:
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        models.append(str(params.get("model") or ""))
    return schema_fingerprint(
        {"environment": environment.lower(), "models": sorted(set(models))}
    )


def fingerprints_match(card: dict[str, Any], *, plan_hash: str, schema_fp: str) -> bool:
    """Whether a decide body names this card's plan hash and schema fingerprint.

    Inputs: the stored card, plus the plan hash and schema fingerprint from the body.
    Output: True only when both equal the values stored on the card.
    A missing or blank schema fingerprint does not match.
    Side effects: none.
    """
    bound = card.get("schema_fp")
    return (
        isinstance(bound, str)
        and bound != ""
        and card.get("plan_hash") == plan_hash
        and bound == schema_fp
    )


def approval_is_expired(card: dict[str, Any], now: datetime) -> bool:
    """Whether `now` is at or after the card's expires_at.

    Inputs: the stored card and the clock at apply time.
    Output: True when the timestamp is missing, unparseable, or not in the future.
    The window itself is the one written at render: 24 hours on production for
    R2 and above, and 7 days on staging.
    Side effects: none.
    """
    raw = card.get("expires_at")
    if not isinstance(raw, str) or raw.strip() == "":
        return True
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return current >= expires
