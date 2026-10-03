"""Rollback tiers: snapshot restore (named only), compensating plan, changelog.

Tier 1 is a /web/database restore where that service exists. This card does not
implement a live restore and does not rely on it for Odoo Online, Odoo.sh, or
Odoo 20. Tier 2 builds a compensating change-set from audit ``change`` rows and
runs it through validate / policy / apply. Tier 3 is the manual changelog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.changeset.executor import apply
from app.changeset.policy import policy_decision, risk_of
from app.changeset.validate import validate
from app.rpc_classify import classify_rpc

NOT_REVERSIBLE_BY_THIS_TIER = "not reversible by this tier"

_POSTED_MODELS = frozenset(
    {
        "account.move",
        "account.move.line",
        "account.payment",
        "account.bank.statement",
        "account.bank.statement.line",
    }
)
_ACCOUNTING_REVERSIBLE_STATES = frozenset({"draft", "cancel"})
_MODULE_INSTALL_STATES = frozenset({"installed", "to install", "to_install"})
_MODULE_INSTALL_ACTIONS = frozenset(
    {
        "install",
        "installed",
        "button_install",
        "button_immediate_install",
        "module.install",
    }
)
_POSTED_ACTIONS = frozenset({"posted", "action_post", "post"})
_CREATED = frozenset({"created", "create"})
_UPDATED = frozenset({"updated", "update", "write"})

ROLLBACK_TIERS: tuple[dict[str, Any], ...] = (
    {
        "tier": 1,
        "id": "database_snapshot",
        "name": "Database snapshot restore",
        "requires": "/web/database",
        "not_for": ("odoo_online", "odoo_sh", "odoo_20"),
        "live_restore": False,
    },
    {
        "tier": 2,
        "id": "compensating",
        "name": "Compensating plan from change rows",
        "rule": "created → unlink, updated → write old values",
        "pipeline": ("validate", "policy", "apply"),
    },
    {
        "tier": 3,
        "id": "manual",
        "name": "Manual changelog",
    },
)


class CompensatingRefused(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class CompensatingPlan:
    tiers: tuple[dict[str, Any], ...]
    changeset: list[dict[str, Any]]
    not_reversible_by_this_tier: list[dict[str, Any]]
    refused: bool = False
    reason: str = ""


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    if isinstance(payload, dict) and ("model" in payload or "action" in payload):
        return payload
    return row


def _res_ids(payload: dict[str, Any]) -> list[int]:
    raw = payload.get("res_id", payload.get("ids"))
    if raw is None:
        return []
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, list):
        return [int(item) for item in raw if isinstance(item, int) or str(item).isdigit()]
    if isinstance(raw, str) and raw.isdigit():
        return [int(raw)]
    return []


def _changes_map(payload: dict[str, Any]) -> dict[str, Any]:
    changes = payload.get("changes")
    return changes if isinstance(changes, dict) else {}


def _old_values(changes: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, delta in changes.items():
        if isinstance(delta, dict) and "old" in delta:
            values[str(name)] = delta["old"]
    return values


def _new_state(changes: dict[str, Any]) -> str:
    state = changes.get("state")
    if isinstance(state, dict):
        return str(state.get("new") or "").strip().lower()
    if isinstance(state, str):
        return state.strip().lower()
    return ""


def _changes_state_new(changes: dict[str, Any]) -> str | None:
    """Return ``changes.state.new`` when that key is present; else None."""
    state = changes.get("state")
    if not isinstance(state, dict) or "new" not in state:
        return None
    return str(state.get("new") or "").strip().lower()


def _action_token(payload: dict[str, Any]) -> str:
    for key in ("action", "method", "type", "op_type"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.strip().lower()
    return ""


def _is_module_install(payload: dict[str, Any]) -> bool:
    model = str(payload.get("model") or "")
    token = _action_token(payload)
    if token in _MODULE_INSTALL_ACTIONS or token == "module.install":
        return True
    if model != "ir.module.module":
        return False
    if token in _MODULE_INSTALL_ACTIONS:
        return True
    return _new_state(_changes_map(payload)) in _MODULE_INSTALL_STATES


def _is_posted_entry(payload: dict[str, Any]) -> bool:
    """Accounting rows are not reversible unless state.new is draft/cancel.

    Missing ``changes.state.new`` fails closed — a posted move whose audit
    row omitted state must not be treated as unlinkable.
    """
    model = str(payload.get("model") or "")
    if model not in _POSTED_MODELS:
        return False
    token = _action_token(payload)
    if token in _POSTED_ACTIONS:
        return True
    if token in _CREATED or token in _UPDATED:
        new_state = _changes_state_new(_changes_map(payload))
        if new_state is None:
            return True
        return new_state not in _ACCOUNTING_REVERSIBLE_STATES
    return _new_state(_changes_map(payload)) == "posted"


def _not_reversible(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "reason": NOT_REVERSIBLE_BY_THIS_TIER,
        "kind": kind,
        "model": payload.get("model"),
        "res_id": payload.get("res_id"),
        "key": payload.get("key"),
        "xmlid": payload.get("xmlid"),
    }


def _never_allowed_unlink(model: str, ids: list[int]) -> bool:
    classification = classify_rpc(model, "unlink", ids=ids or None)
    return bool(classification.forbidden and classification.reason == "never_allowed")


def _op_params(op: dict[str, Any]) -> dict[str, Any]:
    raw = op.get("params")
    return raw if isinstance(raw, dict) else {}


def _id_list(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    return [int(item) for item in raw if isinstance(item, int)]


def build_compensating_plan(change_rows: list[dict[str, Any]]) -> CompensatingPlan:
    """Build a compensating change-set from audit ``change`` rows.

    created → data.unlink; updated → data.update_batch of old values.
    Module installs and posted/unknown-state accounting entries are listed,
    not inverted. Draft/cancel on those models may compensate; missing
    ``changes.state.new`` is not reversible.
    A plan that would unlink a never-allowed model is refused.
    """
    changeset: list[dict[str, Any]] = []
    not_reversible: list[dict[str, Any]] = []
    refused = False

    for row in reversed(list(change_rows)):
        if not isinstance(row, dict):
            continue
        payload = _payload(row)
        if _is_module_install(payload):
            not_reversible.append(_not_reversible("module_install", payload))
            continue
        if _is_posted_entry(payload):
            not_reversible.append(_not_reversible("posted_entry", payload))
            continue

        model = payload.get("model")
        if not isinstance(model, str) or not model:
            continue
        action = _action_token(payload)
        ids = _res_ids(payload)

        if action in _CREATED:
            if _never_allowed_unlink(model, ids):
                refused = True
                continue
            if not ids:
                continue
            changeset.append({"type": "data.unlink", "params": {"model": model, "ids": ids}})
            continue

        if action in _UPDATED:
            values = _old_values(_changes_map(payload))
            if not ids or not values:
                continue
            changeset.append(
                {
                    "type": "data.update_batch",
                    "params": {
                        "model": model,
                        "domain": [["id", "in", ids]] if len(ids) > 1 else [["id", "=", ids[0]]],
                        "values": values,
                    },
                }
            )

    return CompensatingPlan(
        tiers=ROLLBACK_TIERS,
        changeset=changeset,
        not_reversible_by_this_tier=not_reversible,
        refused=refused,
        reason="never_allowed" if refused else "",
    )


def run_compensating_pipeline(
    plan: CompensatingPlan,
    *,
    known_models: set[str] | frozenset[str] | None = None,
    environment: str = "staging",
    mode: str = "T",
) -> dict[str, Any]:
    """Send the compensating change-set through validate / policy / apply."""
    if plan.refused:
        raise CompensatingRefused(plan.reason or "never_allowed")
    for op in plan.changeset:
        params = _op_params(op)
        if op.get("type") != "data.unlink":
            continue
        model = str(params.get("model") or "")
        if _never_allowed_unlink(model, _id_list(params.get("ids"))):
            raise CompensatingRefused("never_allowed")

    models = set(known_models or ())
    if not models:
        for op in plan.changeset:
            hinted = _op_params(op).get("model")
            if isinstance(hinted, str):
                models.add(hinted)

    validation = validate(plan.changeset, known_models=models)
    if not validation["valid"]:
        return {
            "ok": False,
            "stage": "validate",
            "validation": validation,
            "policy": None,
            "apply": None,
        }

    decisions: list[dict[str, Any]] = []
    for op in plan.changeset:
        risk = risk_of(op, document=plan.changeset)
        decision = policy_decision(risk, environment)
        decisions.append({"op": op.get("type"), "risk": risk, **decision})
        if decision["deny"]:
            return {
                "ok": False,
                "stage": "policy",
                "validation": validation,
                "policy": decisions,
                "apply": None,
            }

    applied = apply(plan.changeset, mode=mode)
    return {
        "ok": True,
        "stage": "apply",
        "validation": validation,
        "policy": decisions,
        "apply": applied,
    }
