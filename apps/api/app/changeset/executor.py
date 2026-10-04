"""In-memory journal executor (Mode T / Mode C).

The bridge gate runs before any journal write. A freeze and a missing domain
owner refuse before that write. After a successful in-memory apply, ``verify``
reads the caller-supplied observation. WAL rows still live in ``_JOURNAL``.
The Alembic revision ``s9t0u1v2w3x4`` declares ``journal_entry``,
``before_image``, and ``apply_database_lock``; this process does not write
those tables. ``recover_stale_applying`` reads a journal list, not Postgres.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from odoo_client.schema_fingerprint import schema_fingerprint as hash_schema

from app.blast_radius import assert_production_apply_records, changeset_record_count
from app.changeset.ops import OP_CATALOG, get_op
from app.changeset.policy import apply_blocked, policy_decision, policy_for_op, risk_of
from app.changeset.protected_registry import protected_denial, reset_detections
from app.changeset.recovery import DatabaseApplyLock, recover
from app.changeset.simulate import guard_production_apply
from app.changeset.verify import verify

_JOURNAL: list[dict[str, Any]] = []
_RESULTS_BY_FINGERPRINT: dict[str, dict[str, Any]] = {}
_APPLY_LOCK = DatabaseApplyLock()
_PROTOCOL: Any = None


def _protocol() -> Any:
    global _PROTOCOL
    if _PROTOCOL is None:
        path = Path(__file__).resolve().parents[4] / "odoo_addons" / "ingenium_bridge" / "protocol.py"
        spec = importlib.util.spec_from_file_location("ingenium_bridge_protocol", path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def changeset_fingerprint(changeset: list[dict[str, Any]]) -> str:
    canonical = json.dumps(changeset, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def reset_journal() -> None:
    """Test helper: clear journal, cached apply results, and the process lock."""
    _JOURNAL.clear()
    _RESULTS_BY_FINGERPRINT.clear()
    _APPLY_LOCK.clear()
    reset_detections()


def get_journal() -> list[dict[str, Any]]:
    return list(_JOURNAL)


def _gated_ops(changeset: list[dict[str, Any]], tenant: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gated: list[dict[str, Any]] = []
    for op in changeset:
        op_type = str(op.get("type") or "")
        entry = get_op(op_type)
        gated.append(
            {
                **op,
                "type": op_type,
                "risk": risk_of(op, tenant=tenant, document=changeset) if entry is not None else "R4",
                "ddl": bool(entry.ddl) if entry is not None else False,
            }
        )
    return gated


def _schema_binding_matches(approved: str, live_schema: dict[str, Any] | None) -> bool:
    """Whether the live schema slice still matches the approved fingerprint.

    Inputs: the fingerprint bound at approval, and the schema slice at apply time.
    Outputs: True only when ``live_schema`` is a dict and its fingerprint equals
    ``approved``. A missing or non-dict slice is False.
    Side effects: none. Does not call Odoo.
    """
    if not isinstance(live_schema, dict):
        return False
    return hash_schema(live_schema) == approved


def _has_domain_owner(approvers: list[Any] | None) -> bool:
    """Whether the approver list includes a domain owner.

    Inputs: approver records. ``None`` and an empty list do not.
    A record counts when ``domain_owner`` is true or ``role`` is ``domain_owner``.
    Outputs: True when at least one record qualifies.
    Side effects: none.
    """
    if not approvers:
        return False
    for item in approvers:
        if not isinstance(item, Mapping):
            continue
        if item.get("domain_owner") is True:
            return True
        if item.get("role") == "domain_owner":
            return True
    return False


def _policy_decisions(
    changeset: list[dict[str, Any]],
    *,
    environment: str,
    tenant: dict[str, Any] | None,
) -> list[dict[str, bool | int]]:
    """Policy for each op, or one open decision when the change-set is empty.

    Inputs: the change-set, environment, and optional tenant overlay.
    A blank environment follows the production matrix.
    Outputs: one decision per op.
    Side effects: none. Does not call Odoo.
    """
    env = environment or "production"
    if not changeset:
        return [policy_decision("R0", env)]
    return [policy_for_op(op, env, tenant=tenant, document=changeset) for op in changeset]


def _refuse_blocked_apply(
    changeset: list[dict[str, Any]],
    *,
    environment: str,
    tenant: dict[str, Any] | None,
    frozen: bool,
    approvers: list[Any] | None,
) -> None:
    """Stop a frozen apply, a denied apply, or an elevate apply with no domain owner.

    Inputs: the change-set and the policy inputs ``apply`` already has.
    Outputs: none when the apply may continue to the journal.
    Side effects: none. Raises BridgeError ``frozen`` when ``apply_blocked``
    is true because a freeze is on. Raises ``apply_blocked`` when the decision
    denies or does not allow. Raises ``domain_owner_required`` when policy
    sets ``domain_owner`` and the approver list has no domain owner.
    Does not journal, does not touch a port, and does not call Odoo.
    """
    protocol = _protocol()
    decisions = _policy_decisions(changeset, environment=environment, tenant=tenant)
    for decision in decisions:
        if apply_blocked(decision, frozen=frozen):
            raise protocol.BridgeError("frozen" if frozen else "apply_blocked")
    if any(bool(decision.get("domain_owner")) for decision in decisions) and not _has_domain_owner(approvers):
        raise protocol.BridgeError("domain_owner_required")


def schema_drift_status(approved_fingerprint: str, live_schema: dict[str, Any] | None) -> str:
    """Status of the schema slice after approval.

    Inputs: the fingerprint bound at approval, and the schema slice seen at
    apply time. The slice is a dict. It is not a database connection.
    Outputs: ``STALE`` when the live slice is a dict and its fingerprint
    differs from ``approved_fingerprint``. ``CURRENT`` when they match.
    Side effects: none. Does not call Odoo and does not apply.
    Raises BridgeError ``schema_fingerprint_mismatch`` when the approved
    fingerprint is empty or the live slice is missing or not a dict.
    Absence is not ``STALE`` and is not a successful apply.
    """
    protocol = _protocol()
    if not isinstance(approved_fingerprint, str) or approved_fingerprint == "":
        raise protocol.BridgeError("schema_fingerprint_mismatch")
    if not isinstance(live_schema, dict):
        raise protocol.BridgeError("schema_fingerprint_mismatch")
    if hash_schema(live_schema) != approved_fingerprint:
        return "STALE"
    return "CURRENT"


def apply(
    changeset: list[dict[str, Any]],
    *,
    mode: str,
    fail_at: int | None = None,
    port: Any | None = None,
    groups: set[str] | None = None,
    enabled: bool = True,
    protocol_version: int = 1,
    max_risk: str = "R3",
    caller_id: int = 1,
    approved_hash: str | None = None,
    escalated: bool = False,
    expected_fingerprint: str | None = None,
    live_fingerprint: str | None = None,
    schema_fingerprint: str | None = None,
    live_schema: dict[str, Any] | None = None,
    tenant: dict[str, Any] | None = None,
    environment: str = "",
    write_mode: str = "",
    record_count: int | None = None,
    odoo_database: str = "",
    apply_lock: DatabaseApplyLock | None = None,
    frozen: bool = False,
    approvers: list[Mapping[str, Any]] | None = None,
    observation: Mapping[str, Any] | None = None,
    model_success: bool | None = None,
) -> dict[str, Any]:
    """Apply one change-set in memory.

    Inputs: the change-set, mode T or C, and the existing bridge gates.
    ``frozen`` is read by ``apply_blocked``. ``approvers`` is the list checked
    when policy sets ``domain_owner``. ``observation`` is fake evidence for
    ``verify`` after the in-memory writes succeed. ``model_success`` is passed
    through and does not decide the outcome.
    Outputs: the journal decision. A freeze or a missing domain owner raises
    before any journal or port write.
    Side effects: may append journal rows. Does not call Odoo and does not
    render a live view.
    """
    if mode not in {"T", "C"}:
        raise ValueError("mode must be T or C")

    count = changeset_record_count(changeset) if record_count is None else int(record_count)
    assert_production_apply_records(count, environment=environment, write_mode=write_mode)
    guard_production_apply(changeset, environment=environment)

    fp = changeset_fingerprint(changeset)
    protocol = _protocol()
    if approved_hash is not None and approved_hash != fp:
        raise protocol.BridgeError("approval_hash_mismatch")
    if schema_fingerprint is not None and not _schema_binding_matches(
        schema_fingerprint, live_schema
    ):
        raise protocol.BridgeError("schema_fingerprint_mismatch")
    if expected_fingerprint is not None and live_fingerprint != expected_fingerprint:
        raise protocol.BridgeError("stale_fingerprint")
    for op in changeset:
        entry = get_op(str(op.get("type") or ""))
        if protected_denial(op, document=changeset, tenant=tenant):
            raise protocol.BridgeError("protected_deny")
        if mode == "C" and entry is not None and entry.reversible == "N":
            raise protocol.BridgeError("mode_c_irreversible")
    protocol.authorize_apply(
        _gated_ops(changeset, tenant),
        known_types=set(OP_CATALOG),
        protocol_version=protocol_version,
        enabled=enabled,
        groups=set(groups) if groups is not None else {"operator"},
        caller_id=caller_id,
        max_risk=max_risk,
        mode="apply",
        escalated=escalated,
    )
    _refuse_blocked_apply(
        changeset,
        environment=environment,
        tenant=tenant,
        frozen=frozen,
        approvers=list(approvers) if approvers is not None else None,
    )

    lock_held = False
    active_lock: DatabaseApplyLock | None = None
    if odoo_database:
        active_lock = apply_lock if apply_lock is not None else _APPLY_LOCK
        if not active_lock.acquire(odoo_database, fp, now=datetime.now(timezone.utc)):
            return {
                "status": "NEEDS_HUMAN",
                "plan_hash": fp,
                "mode": mode,
                "heartbeat": datetime.now(timezone.utc).isoformat(),
                "risk_bump": 0,
                "applied_count": 0,
                "report": {
                    "reason": "database_busy",
                    "odoo_database": odoo_database,
                    "results": [],
                    "missing": [],
                    "compensates": [],
                },
            }
        lock_held = True

    try:
        return _apply_journaled(
            changeset,
            mode=mode,
            fail_at=fail_at,
            port=port,
            fp=fp,
            odoo_database=odoo_database,
            observation=observation,
            model_success=model_success,
        )
    finally:
        if lock_held and active_lock is not None:
            active_lock.release(odoo_database, fp)


def _apply_journaled(
    changeset: list[dict[str, Any]],
    *,
    mode: str,
    fail_at: int | None,
    port: Any | None,
    fp: str,
    odoo_database: str,
    observation: Mapping[str, Any] | None = None,
    model_success: bool | None = None,
) -> dict[str, Any]:
    if fp in _RESULTS_BY_FINGERPRINT:
        return dict(_RESULTS_BY_FINGERPRINT[fp])

    heartbeat = datetime.now(timezone.utc).isoformat()
    run_id = fp
    applied_indices: list[int] = []
    status = "APPLIED"
    risk_bump = 0
    run_intent: dict[str, Any] = {
        "kind": "INTENT",
        "run_id": run_id,
        "plan_hash": fp,
        "mode": mode,
        "op_count": len(changeset),
        "heartbeat": heartbeat,
        "status": "APPLYING",
    }
    if odoo_database:
        run_intent["odoo_database"] = odoo_database
    _JOURNAL.append(run_intent)

    try:
        for index, op in enumerate(changeset):
            op_type = str(op.get("type", ""))
            entry = get_op(op_type)
            _JOURNAL.append(
                {
                    "kind": "INTENT",
                    "run_id": run_id,
                    "index": index,
                    "type": op_type,
                    "heartbeat": datetime.now(timezone.utc).isoformat(),
                }
            )
            _JOURNAL.append(
                {
                    "kind": "BEFORE",
                    "run_id": run_id,
                    "index": index,
                    "type": op_type,
                    "snapshot": {"op": op},
                }
            )

            if fail_at is not None and index == fail_at:
                if mode == "T":
                    status = "ROLLED_BACK"
                    raise _ApplyAbort()
                status = "PARTIALLY_ROLLED_BACK"
                risk_bump = 1
                raise _ApplyAbort()

            if port is not None:
                from app.changeset.dispatch import dispatch_op

                try:
                    dispatch_op(port, op, document=changeset)
                except UnknownOutcome:
                    # The write may have landed. Do not dispatch this op again.
                    _JOURNAL.append({"kind": "UNKNOWN", "run_id": run_id, "index": index, "type": op_type})
                    raise _ApplyAbort()

            _JOURNAL.append(
                {
                    "kind": "RESULT",
                    "run_id": run_id,
                    "index": index,
                    "type": op_type,
                    "status": "APPLIED",
                    "reversible": entry.reversible if entry else "N",
                }
            )
            applied_indices.append(index)

    except _ApplyAbort:
        if mode == "T" and not any(entry.get("kind") == "UNKNOWN" and entry.get("run_id") == run_id for entry in _JOURNAL):
            _strip_results_for_run(run_id)
        elif mode == "C" and not any(entry.get("kind") == "UNKNOWN" and entry.get("run_id") == run_id for entry in _JOURNAL):
            for idx in reversed(applied_indices):
                op = changeset[idx]
                _JOURNAL.append(
                    {
                        "kind": "COMPENSATE",
                        "run_id": run_id,
                        "index": idx,
                        "type": op.get("type"),
                    }
                )
            risk_bump = 1
        else:
            risk_bump = 1

    verification: dict[str, Any] | None = None
    unknown = any(entry.get("kind") == "UNKNOWN" and entry.get("run_id") == run_id for entry in _JOURNAL)
    if status == "APPLIED" and not unknown:
        if observation is not None:
            verification = verify(changeset, observation, model_success=model_success)
            if verification["verified"]:
                _JOURNAL.append({"kind": "VERIFIED", "run_id": run_id, "plan_hash": fp})
            elif verification["rolled_back"]:
                _strip_results_for_run(run_id)
                for item in verification["compensations"]:
                    _JOURNAL.append(
                        {
                            "kind": "COMPENSATE",
                            "run_id": run_id,
                            "index": item["index"],
                            "type": item["type"],
                        }
                    )
        else:
            _JOURNAL.append({"kind": "VERIFIED", "run_id": run_id, "plan_hash": fp})

    decision = recover(
        [entry for entry in _JOURNAL if entry.get("run_id") in {None, run_id}],
        mode=mode,
        expected_ops=len(changeset),
    )
    status = decision["status"]
    run_intent["status"] = status
    result = {
        "status": status,
        "plan_hash": fp,
        "mode": mode,
        "heartbeat": heartbeat,
        "risk_bump": risk_bump,
        "applied_count": len(applied_indices) if status == "VERIFIED" else 0,
        "report": decision["report"],
    }
    if verification is not None:
        result["verification"] = verification
    _RESULTS_BY_FINGERPRINT[fp] = result
    return dict(result)


class UnknownOutcome(Exception):
    """The transport may have committed. Do not write a RESULT and do not retry blindly."""


class _ApplyAbort(Exception):
    pass


def _strip_results_for_run(run_id: str) -> None:
    global _JOURNAL
    _JOURNAL = [e for e in _JOURNAL if not (e.get("run_id") == run_id and e.get("kind") == "RESULT")]
