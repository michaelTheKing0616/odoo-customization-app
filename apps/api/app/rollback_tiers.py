"""Rollback tiers: named snapshot restore, compensating plan, changelog.

Tier 1 is a ``/web/database`` restore where that service exists. This module
does not implement a live restore and does not rely on it for Odoo Online,
Odoo.sh, or Odoo 20. It calls ``request_database_backup``, which never opens
those endpoints.

Tier 2 builds a compensating change-set from audit ``change`` rows
(created → unlink, updated → write old values) and submits it through the
existing change-set pipeline (``approve_field_data_deletion``:
validate / policy / approval). It does not raw-RPC the undo.

Tier 3 is the manual changelog. Module installs and posted accounting
entries are listed as not reversible by this tier and are not inverted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.changeset.inbox import Inbox
from app.changeset.rollback import PIPELINE, approve_field_data_deletion
from app.database_backup import request_database_backup
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
_CHANGE_KINDS = frozenset({None, "", "change"})

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
        "pipeline": PIPELINE,
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

    @property
    def changelog(self) -> list[dict[str, Any]]:
        """Tier 3 listing: rows this compensating tier will not invert."""
        return list(self.not_reversible_by_this_tier)


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
    if token in _MODULE_INSTALL_ACTIONS:
        return True
    if model != "ir.module.module":
        return False
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


def _known_models(
    plan: CompensatingPlan,
    known_models: set[str] | frozenset[str] | None,
) -> set[str]:
    models = set(known_models or ())
    if models:
        return models
    for op in plan.changeset:
        hinted = _op_params(op).get("model")
        if isinstance(hinted, str) and hinted:
            models.add(hinted)
    return models


def describe_database_snapshot_tier(
    *,
    odoo_major: int | None = None,
    hosting_hint: str | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """Name tier 1 and refuse a live ``/web/database`` restore.

    Inputs: optional major, hosting hint, and a client that must not be
    dispatched. Outputs: the tier-1 record plus the backup refusal.
    ``live_restore`` stays False. Side effects: none. Does not call Odoo.
    """
    backup = request_database_backup(
        odoo_major=odoo_major,
        hosting_hint=hosting_hint,
        client=client,
    )
    return {
        **ROLLBACK_TIERS[0],
        "backup": backup,
        "live_restore": False,
        "called_db_service": bool(backup.get("called_db_service")),
    }


def build_compensating_plan(change_rows: list[dict[str, Any]]) -> CompensatingPlan:
    """Build a compensating change-set from audit ``change`` rows.

    Inputs: audit rows. ``kind`` other than ``change`` (or omitted) is not
    inverted unless it is a module install, which is listed instead.
    created → ``data.unlink``; updated → ``data.update_batch`` of old values.
    Module installs and posted/unknown-state accounting entries are listed,
    not inverted. Draft/cancel on those models may compensate.
    A plan that would unlink a never-allowed model is refused.
    Outputs: the plan. Side effects: none. Does not call Odoo.
    """
    changeset: list[dict[str, Any]] = []
    not_reversible: list[dict[str, Any]] = []
    refused = False

    for row in reversed(list(change_rows)):
        if not isinstance(row, dict):
            continue
        payload = _payload(row)
        kind = row.get("kind")
        if _is_module_install(payload) or kind == "module":
            not_reversible.append(_not_reversible("module_install", payload))
            continue
        if _is_posted_entry(payload):
            not_reversible.append(_not_reversible("posted_entry", payload))
            continue
        if kind not in _CHANGE_KINDS:
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
    requester_id: str = "rollback-tiers",
    connection_id: str = "rollback-tiers",
    approvals: list[dict[str, str]] | None = None,
    inbox: Inbox | None = None,
) -> dict[str, Any]:
    """Submit the compensating change-set through validate / policy / approval.

    Inputs: the plan from ``build_compensating_plan``, known models, environment,
    requester, connection, optional approvals, and optional inbox.
    Outputs: the change-set pipeline result. ``applied`` stays False.
    Side effects: ``Inbox.submit`` (and ``Inbox.decide`` when approvals are
    supplied). Does not call Odoo and does not write a customer database.
    """
    if plan.refused:
        raise CompensatingRefused(plan.reason or "never_allowed")
    for op in plan.changeset:
        params = _op_params(op)
        if op.get("type") != "data.unlink":
            continue
        model = str(params.get("model") or "")
        if _never_allowed_unlink(model, _id_list(params.get("ids"))):
            raise CompensatingRefused("never_allowed")

    return approve_field_data_deletion(
        plan.changeset,
        known_models=_known_models(plan, known_models),
        environment=environment,
        requester_id=requester_id,
        connection_id=connection_id,
        approvals=approvals,
        inbox=inbox,
        goal="Compensate audit change rows",
        assumptions=["The inverse was computed from audit change rows."],
    )
