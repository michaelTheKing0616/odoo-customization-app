"""Undo as a change-set.

Undo uses the same validate, policy, and approval path as any other
change-set. After an approved undo, the caller-supplied MetaSnapshots are
compared. A mismatch is NEEDS_HUMAN.

When a new field already holds rows, the undo hides that field and reports
the remaining row count. Deleting those rows is a separate change-set with
a higher risk. The hide step does not delete them.

This module does not call Odoo. ``compensate_memory`` is used only for an
exact inverse and is not modified.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from app.changeset.handlers import apply_memory, compensate_memory, handler_for
from app.changeset.inbox import Inbox, InboxError
from app.changeset.ops import op_base_risk
from app.changeset.policy import changeset_r4_posture, policy_decision
from app.changeset.validate import validate

STATUS_INVALID = "INVALID"
STATUS_PENDING = "PENDING_APPROVAL"
STATUS_REJECTED = "REJECTED"
STATUS_APPROVED = "APPROVED"
STATUS_ROLLED_BACK = "ROLLED_BACK"
STATUS_NEEDS_HUMAN = "NEEDS_HUMAN"

PIPELINE = ("validate", "policy", "approval")
_DELETE_TYPES = frozenset({"field.delete", "data.delete", "data.unlink"})
_APPROVAL_DECISIONS = frozenset({"approve", "deny", "deny_and_stop"})
_EVIDENCE_KEYS = (
    "user_id",
    "session_id",
    "provider",
    "domain_owner",
    "role",
    "simulation_passed",
    "backup_id",
    "allowed_window",
    "now",
)
_SAFE_FIELD_NAME = re.compile(r"^x_[A-Za-z0-9_]+$")
_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")


def snapshots_match(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> bool:
    """Whether two MetaSnapshots describe the same metadata.

    Inputs: the snapshot taken as the undo target, and the snapshot observed
    after the undo. List order is ignored. Key order is ignored.
    Outputs: True when the normalized snapshots are equal.
    Side effects: none. Does not call Odoo. A non-JSON value is a mismatch.
    """
    try:
        return _normalize(expected) == _normalize(observed)
    except (TypeError, ValueError):
        return False


def undo(
    changeset: list[dict[str, Any]],
    *,
    known_models: set[str] | frozenset[str],
    environment: str,
    requester_id: str,
    connection_id: str,
    store: dict[str, dict[str, Any]] | None = None,
    field_rows: Mapping[str, int] | None = None,
    approvals: list[dict[str, str]] | None = None,
    inbox: Inbox | None = None,
    expected_snapshot: Mapping[str, Any] | None = None,
    observed_snapshot: Mapping[str, Any] | None = None,
    goal: str = "Undo the change-set",
    assumptions: list[str] | None = None,
) -> dict[str, Any]:
    """Validate, check policy, and approve an inverse change-set, then compare snapshots.

    Inputs: the applied change-set, known models, environment, requester,
    connection, optional memory store, optional ``model:name`` row counts,
    approval decisions, inbox, and the two MetaSnapshots to compare.
    Outputs: status, pipeline steps that ran, validation, policy, approval,
    the inverse change-set, remaining row count, and a separate deletion
    change-set when a hide was planned. ``applied`` is True only after the
    inverse is written to ``store``.
    Side effects: after approval, an exact inverse calls ``compensate_memory``.
    A soft inverse calls ``apply_memory`` for the hide and sets ``hidden`` on
    the existing field entry. Row lists already stored on that entry are left
    in place. ``field_rows`` is not mutated. No Odoo call.
    """
    planned, plan_error = _plan_inverse(changeset, field_rows=field_rows)
    deletion = _deletion_plan(planned)
    if plan_error is not None:
        return _outcome(
            status=STATUS_NEEDS_HUMAN,
            reason=plan_error,
            data_deletion=deletion,
            remaining_rows=_remaining_total(planned),
            remaining_by_field=_remaining_by_field(planned),
        )
    undo_changeset = [step["undo_op"] for step in planned]
    if any(str(op.get("type") or "") in _DELETE_TYPES for op in undo_changeset):
        return _outcome(
            status=STATUS_NEEDS_HUMAN,
            reason="the hide step planned a delete",
            changeset=undo_changeset,
            data_deletion=deletion,
            remaining_rows=_remaining_total(planned),
            remaining_by_field=_remaining_by_field(planned),
        )

    gate = _run_pipeline(
        undo_changeset,
        known_models=known_models,
        environment=environment,
        requester_id=requester_id,
        connection_id=connection_id,
        approvals=approvals,
        inbox=inbox,
        goal=goal,
        assumptions=assumptions
        if assumptions is not None
        else ["The inverse was computed from the applied change-set."],
    )
    base = {
        "changeset": undo_changeset,
        "data_deletion": deletion,
        "remaining_rows": _remaining_total(planned),
        "remaining_by_field": _remaining_by_field(planned),
        "pipeline": gate["pipeline"],
        "validation": gate["validation"],
        "policy": gate["policy"],
        "approval": gate["approval"],
        "reason": gate["reason"],
    }
    if not gate["ready"]:
        return _outcome(status=gate["status"], **base)

    memory_ok = _apply_inverse(store, planned)
    match = _compare_snapshots(expected_snapshot, observed_snapshot)
    status = STATUS_ROLLED_BACK if memory_ok and match else STATUS_NEEDS_HUMAN
    return _outcome(status=status, applied=memory_ok, snapshot_match=match, **base)


def approve_field_data_deletion(
    changeset: list[dict[str, Any]],
    *,
    known_models: set[str] | frozenset[str],
    environment: str,
    requester_id: str,
    connection_id: str,
    approvals: list[dict[str, str]] | None = None,
    inbox: Inbox | None = None,
    goal: str = "Delete data left in a hidden field",
    assumptions: list[str] | None = None,
) -> dict[str, Any]:
    """Run validate, policy, and approval for a field-data deletion.

    Inputs: a deletion change-set, normally the ``data_deletion`` changeset
    returned by ``undo``, plus the same pipeline arguments as ``undo``.
    Outputs: the pipeline result. ``applied`` and ``deletes_rows`` stay False.
    A denied or pending approval does not become APPROVED.
    Side effects: submits a card to the inbox. Does not mutate a memory store,
    does not remove rows, and does not call Odoo.
    """
    gate = _run_pipeline(
        changeset,
        known_models=known_models,
        environment=environment,
        requester_id=requester_id,
        connection_id=connection_id,
        approvals=approvals,
        inbox=inbox,
        goal=goal,
        assumptions=assumptions
        if assumptions is not None
        else ["Deleting leftover field data is a separate approval."],
    )
    status = STATUS_APPROVED if gate["ready"] else gate["status"]
    return _outcome(
        status=status,
        pipeline=gate["pipeline"],
        validation=gate["validation"],
        policy=gate["policy"],
        approval=gate["approval"],
        changeset=list(changeset),
        reason=gate["reason"],
        applied=False,
        deletes_rows=False,
    )


def _approval_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    """Copy production-R3 evidence from an approval record into ``Inbox.decide``.

    Inputs: one approval dict. Missing keys stay omitted so an older caller
    that only sends approver_id and decision is unchanged for risks that do
    not use this evidence.
    Output: the optional decide arguments that were present and not None.
    Side effects: none.
    """
    return {key: item[key] for key in _EVIDENCE_KEYS if key in item and item[key] is not None}


def _run_pipeline(
    changeset: list[dict[str, Any]],
    *,
    known_models: set[str] | frozenset[str],
    environment: str,
    requester_id: str,
    connection_id: str,
    approvals: list[dict[str, str]] | None,
    inbox: Inbox | None,
    goal: str,
    assumptions: list[str],
) -> dict[str, Any]:
    """Run validate, then policy, then the approval inbox.

    Inputs: the change-set and the inbox arguments.
    Outputs: ready, status, the steps that ran, and the stage payloads.
    Side effects: ``Inbox.submit`` and ``Inbox.decide`` when validation passes.
    Does not call Odoo.
    """
    steps: list[str] = ["validate"]
    report = validate(changeset, known_models=set(known_models))
    if not report["valid"]:
        return {
            "ready": False,
            "status": STATUS_INVALID,
            "pipeline": steps,
            "validation": report,
            "policy": None,
            "approval": None,
            "reason": "validation failed",
        }

    steps.append("policy")
    max_risk = str(report["max_risk"])
    decision = policy_decision(
        max_risk,
        environment,
        heavy=changeset_r4_posture(changeset) == "heavy" and max_risk == "R4",
    )
    active = inbox if inbox is not None else Inbox()
    steps.append("approval")
    submitted = active.submit(
        changeset,
        goal=goal,
        assumptions=assumptions,
        environment=environment,
        requester_id=requester_id,
        known_models=set(known_models),
        connection_id=connection_id,
    )
    if not submitted["ok"]:
        reason = str(submitted.get("error") or "approval was not opened")
        return {
            "ready": False,
            "status": STATUS_REJECTED,
            "pipeline": steps,
            "validation": report,
            "policy": decision,
            "approval": {"status": "denied", "error": reason, "card": None},
            "reason": reason,
        }

    card = submitted["card"]
    if not approvals:
        return {
            "ready": False,
            "status": STATUS_PENDING,
            "pipeline": steps,
            "validation": report,
            "policy": decision,
            "approval": {"status": card["status"], "card": card},
            "reason": "approval is required",
        }

    for item in approvals:
        approver_id = item.get("approver_id")
        decision_name = item.get("decision")
        if not approver_id or decision_name not in _APPROVAL_DECISIONS:
            return {
                "ready": False,
                "status": STATUS_INVALID,
                "pipeline": steps,
                "validation": report,
                "policy": decision,
                "approval": {"status": card["status"], "card": card},
                "reason": "approval is missing approver_id or decision",
            }
        try:
            card = active.decide(
                card["plan_hash"],
                approver_id=str(approver_id),
                decision=decision_name,  # type: ignore[arg-type]
                connection_id=connection_id,
                **_approval_evidence(item),
            )
        except InboxError as exc:
            return {
                "ready": False,
                "status": STATUS_REJECTED,
                "pipeline": steps,
                "validation": report,
                "policy": decision,
                "approval": {"status": "refused", "error": str(exc), "card": card},
                "reason": str(exc),
            }

    if card["status"] == "approved":
        return {
            "ready": True,
            "status": STATUS_APPROVED,
            "pipeline": steps,
            "validation": report,
            "policy": decision,
            "approval": {"status": "approved", "card": card},
            "reason": None,
        }
    if card["status"] == "pending":
        status = STATUS_PENDING
        reason = "approval is incomplete"
    else:
        status = STATUS_REJECTED
        reason = f"approval {card['status']}"
    return {
        "ready": False,
        "status": status,
        "pipeline": steps,
        "validation": report,
        "policy": decision,
        "approval": {"status": card["status"], "card": card},
        "reason": reason,
    }


def _plan_inverse(
    changeset: list[dict[str, Any]],
    *,
    field_rows: Mapping[str, int] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Build inverse steps in reverse order.

    Inputs: the applied change-set and optional row counts keyed by
    ``model:name``.
    Outputs: steps and an error string. The error is set when an op has no
    inverse, a field name is not safe to hide, or a row count is not a
    non-negative int. An empty change-set is an error.
    Side effects: none.
    """
    if not changeset:
        return [], "nothing to undo"
    steps: list[dict[str, Any]] = []
    for op in reversed(changeset):
        op_type = str(op.get("type") or "")
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if op_type == "field.create":
            count, count_error = _row_count(field_rows, params)
            if count_error is not None:
                return [], count_error
            if count > 0:
                hide, hide_error = _hide_field(params, count)
                if hide_error is not None:
                    return [], hide_error
                steps.append(hide)
                continue
        try:
            handler = handler_for(op_type)
        except KeyError:
            return [], f"{op_type or 'unknown'} has no inverse"
        inverse = handler.inverse(params)
        if inverse is None:
            return [], f"{op_type} has no inverse"
        steps.append(
            {
                "kind": "exact",
                "original": op,
                "undo_op": {"type": inverse["type"], "params": dict(inverse.get("params") or {})},
                "memory_key": handler.memory_key(params),
                "count": 0,
                "deletion": None,
            }
        )
    return steps, None


def _hide_field(params: dict[str, Any], count: int) -> tuple[dict[str, Any], str | None]:
    """Plan a view inherit that marks the field invisible.

    Inputs: ``field.create`` params and a positive row count.
    Outputs: a soft step, or an error when the field name is not a safe
    ``x_`` identifier.
    Side effects: none. Does not build a ``field.delete`` op into the undo.
    """
    model = str(params.get("model") or "")
    name = str(params.get("name") or "")
    if not _SAFE_FIELD_NAME.fullmatch(name) or name.startswith("x_studio_"):
        return {}, f"{name or 'field'} cannot be hidden safely"
    handler = handler_for("field.create")
    undo_op = {
        "type": "view.inherit.create",
        "params": {
            "model": model,
            "name": name,
            "xpath": f"//field[@name='{name}']",
            "position": "attributes",
            "invisible": True,
            "expect_matches": 1,
            "remaining_rows": count,
        },
    }
    deletion = {
        "type": "field.delete",
        "params": {"model": model, "name": name, "record_count": count},
    }
    return {
        "kind": "soft",
        "original": {"type": "field.create", "params": dict(params)},
        "undo_op": undo_op,
        "memory_key": handler.memory_key(params),
        "count": count,
        "deletion": deletion,
    }, None


def _deletion_plan(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Describe the separate deletion change-set for soft hides.

    Inputs: planned inverse steps.
    Outputs: None when no hide kept rows. Otherwise the deletion ops, their
    max risk, and flags showing they were not submitted or applied.
    Side effects: none.
    """
    ops = [step["deletion"] for step in steps if step.get("deletion")]
    if not ops:
        return None
    risks = [op_base_risk(str(op["type"]), op.get("params")) for op in ops]
    max_risk = max(risks, key=lambda risk: _RISK_ORDER.index(risk))
    return {
        "changeset": ops,
        "risks": risks,
        "max_risk": max_risk,
        "submitted": False,
        "applied": False,
        "deletes_rows": False,
    }


def _apply_inverse(store: dict[str, dict[str, Any]] | None, steps: list[dict[str, Any]]) -> bool:
    """Write an approved inverse into memory.

    Inputs: the memory store and planned steps.
    Outputs: True when every step was written.
    Side effects: exact steps call ``compensate_memory``. Soft steps record
    the hide op and set ``hidden`` plus ``remaining_rows`` on the existing
    field entry. They do not pop that entry and do not apply ``field.delete``.
    """
    if store is None:
        return False
    for step in steps:
        if step["kind"] == "soft":
            if not _apply_hide(store, step):
                return False
            continue
        try:
            compensate_memory(store, step["original"])
        except (PermissionError, ValueError, KeyError):
            return False
    return True


def _apply_hide(store: dict[str, dict[str, Any]], step: dict[str, Any]) -> bool:
    """Record the hide and keep the field entry, including any stored rows.

    Inputs: memory store and one soft step.
    Outputs: True when the field entry was marked hidden.
    Side effects: ``apply_memory`` for the view inherit. Sets ``hidden`` and
    ``remaining_rows`` on the field entry. Does not call ``compensate_memory``.
    """
    undo_op = step["undo_op"]
    if str(undo_op.get("type") or "") in _DELETE_TYPES:
        return False
    try:
        apply_memory(store, undo_op)
    except (PermissionError, ValueError, KeyError):
        return False
    entry = store.get(step["memory_key"])
    if not isinstance(entry, dict):
        return False
    entry["hidden"] = True
    entry["remaining_rows"] = step["count"]
    return True


def _compare_snapshots(
    expected: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> bool:
    """Compare the two post-undo snapshots.

    Inputs: expected and observed MetaSnapshots. Either may be missing.
    Outputs: True only when both were supplied and they match.
    Side effects: none.
    """
    if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
        return False
    return snapshots_match(expected, observed)


def _row_count(
    field_rows: Mapping[str, int] | None,
    params: Mapping[str, Any],
) -> tuple[int, str | None]:
    """Read the row count for one new field.

    Inputs: the count map and field params. A missing key means zero rows.
    Outputs: the count and an error when the stored count is not a
    non-negative int. Bool is rejected.
    Side effects: none.
    """
    if field_rows is None:
        return 0, None
    key = f"{params.get('model')}:{params.get('name')}"
    if key not in field_rows:
        return 0, None
    value = field_rows[key]
    if type(value) is not int or value < 0:
        return 0, f"{key} record count must be a non-negative int"
    return value, None


def _remaining_by_field(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        if step.get("kind") != "soft":
            continue
        params = step["undo_op"]["params"]
        rows.append({"model": params["model"], "name": params["name"], "count": step["count"]})
    return rows


def _remaining_total(steps: list[dict[str, Any]]) -> int:
    return sum(step["count"] for step in steps if step.get("kind") == "soft")


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, float, bool)):
        return value
    if type(value) is int:
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        normalized = [_normalize(item) for item in value]
        return sorted(normalized, key=_snapshot_sort_key)
    raise TypeError(f"snapshot value is not JSON: {type(value).__name__}")


def _snapshot_sort_key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), default=_refuse_default)


def _refuse_default(_value: Any) -> str:
    raise TypeError("snapshot value is not JSON")


def _outcome(**kwargs: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": STATUS_NEEDS_HUMAN,
        "pipeline": [],
        "validation": None,
        "policy": None,
        "approval": None,
        "changeset": [],
        "applied": False,
        "snapshot_match": None,
        "remaining_rows": 0,
        "remaining_by_field": [],
        "data_deletion": None,
        "reason": None,
        "deletes_rows": False,
    }
    body.update(kwargs)
    return body
