"""Bridge security contract. No Odoo import and no network."""

from __future__ import annotations

PROTOCOL_VERSION = 1

READ_METHODS = frozenset(
    {
        "ping",
        "introspect",
        "combined_view",
        "effective_access",
        "render_check",
    }
)
WRITE_METHODS = frozenset({"apply_changeset", "rollback_changeset"})
PROHIBITED_OPS = frozenset({"module.uninstall", "data.delete", "rpc.write"})
_RANK = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


class BridgeError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def authorize(
    *,
    method: str,
    protocol_version: int,
    enabled: bool,
    groups: set[str],
    caller_id: int,
    user_id: int | None = None,
    escalated: bool = False,
) -> None:
    if protocol_version != PROTOCOL_VERSION:
        raise BridgeError("protocol_mismatch")
    if not enabled:
        raise BridgeError("kill_switch")
    if method not in READ_METHODS | WRITE_METHODS:
        raise BridgeError("unknown_method")
    if escalated:
        raise BridgeError("system_escalation")
    if "reader" not in groups and "operator" not in groups:
        raise BridgeError("reader_required")
    if method in WRITE_METHODS and "operator" not in groups:
        raise BridgeError("operator_required")
    if user_id is not None and user_id != caller_id and "operator" not in groups:
        raise BridgeError("impersonation_denied")


def authorize_apply(
    ops: list[dict],
    *,
    known_types: set[str],
    protocol_version: int,
    enabled: bool,
    groups: set[str],
    caller_id: int,
    max_risk: str,
    mode: str,
    escalated: bool = False,
) -> None:
    authorize(
        method="apply_changeset",
        protocol_version=protocol_version,
        enabled=enabled,
        groups=groups,
        caller_id=caller_id,
        escalated=escalated,
    )
    if mode not in {"validate", "dry_run", "apply"}:
        raise BridgeError("unknown_mode")
    for op in ops:
        op_type = str(op.get("type") or "")
        if op_type not in known_types or op_type in PROHIBITED_OPS:
            raise BridgeError("unknown_op" if op_type not in known_types else "prohibited_op")
        if mode == "dry_run" and op.get("ddl"):
            raise BridgeError("ddl_no_inplace")
        risk = str(op.get("risk") or "R0")
        if risk not in _RANK or max_risk not in _RANK:
            raise BridgeError("unknown_risk")
        if _RANK[risk] > _RANK[max_risk]:
            raise BridgeError("max_risk")


def ping_payload(*, server_version: str, edition: str, module_hash: str, capabilities: dict[str, str]) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "bridge_version": "1",
        "server_version": server_version,
        "edition": edition,
        "module_hash": module_hash,
        "capabilities": capabilities,
        "enabled": True,
    }
