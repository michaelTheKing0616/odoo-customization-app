"""In-memory journal executor (Mode T / Mode C). The bridge gate runs before any journal write."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.blast_radius import assert_production_apply_records, changeset_record_count
from app.changeset.ops import OP_CATALOG, get_op
from app.changeset.policy import risk_of
from app.changeset.protected_registry import protected_denial, reset_detections
from app.changeset.recovery import recover

_JOURNAL: list[dict[str, Any]] = []
_RESULTS_BY_FINGERPRINT: dict[str, dict[str, Any]] = {}
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
    """Test helper: clear journal and cached apply results."""
    _JOURNAL.clear()
    _RESULTS_BY_FINGERPRINT.clear()
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
    tenant: dict[str, Any] | None = None,
    environment: str = "",
    write_mode: str = "",
    record_count: int | None = None,
) -> dict[str, Any]:
    if mode not in {"T", "C"}:
        raise ValueError("mode must be T or C")

    count = changeset_record_count(changeset) if record_count is None else int(record_count)
    assert_production_apply_records(count, environment=environment, write_mode=write_mode)

    fp = changeset_fingerprint(changeset)
    protocol = _protocol()
    if approved_hash is not None and approved_hash != fp:
        raise protocol.BridgeError("approval_hash_mismatch")
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

    if fp in _RESULTS_BY_FINGERPRINT:
        return dict(_RESULTS_BY_FINGERPRINT[fp])

    heartbeat = datetime.now(timezone.utc).isoformat()
    run_id = fp
    applied_indices: list[int] = []
    status = "APPLIED"
    risk_bump = 0

    _JOURNAL.append(
        {
            "kind": "INTENT",
            "run_id": run_id,
            "plan_hash": fp,
            "mode": mode,
            "op_count": len(changeset),
            "heartbeat": heartbeat,
        }
    )

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

    if status == "APPLIED" and not any(entry.get("kind") == "UNKNOWN" and entry.get("run_id") == run_id for entry in _JOURNAL):
        _JOURNAL.append({"kind": "VERIFIED", "run_id": run_id, "plan_hash": fp})

    decision = recover(
        [entry for entry in _JOURNAL if entry.get("run_id") in {None, run_id}],
        mode=mode,
        expected_ops=len(changeset),
    )
    status = decision["status"]
    result = {
        "status": status,
        "plan_hash": fp,
        "mode": mode,
        "heartbeat": heartbeat,
        "risk_bump": risk_bump,
        "applied_count": len(applied_indices) if status == "VERIFIED" else 0,
        "report": decision["report"],
    }
    _RESULTS_BY_FINGERPRINT[fp] = result
    return dict(result)


class UnknownOutcome(Exception):
    """The transport may have committed. Do not write a RESULT and do not retry blindly."""


class _ApplyAbort(Exception):
    pass


def _strip_results_for_run(run_id: str) -> None:
    global _JOURNAL
    _JOURNAL = [e for e in _JOURNAL if not (e.get("run_id") == run_id and e.get("kind") == "RESULT")]
