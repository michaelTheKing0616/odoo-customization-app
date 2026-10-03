"""Bridge security contract. No Odoo import and no network."""

from __future__ import annotations

import hashlib
import hmac
import json

PROTOCOL_VERSION = 1
KILL_SWITCH_PARAM = "ingenium.bridge.enabled"
_CALLBACK_KEYS = frozenset(
    {
        "callback",
        "callback_url",
        "telemetry",
        "telemetry_url",
        "webhook_url",
        "phone_home",
    }
)

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


def enabled_from_param(value: object) -> bool:
    """Kill switch. Missing means enabled. The strings 0, false, and False stop the bridge."""
    if value is None:
        return True
    return value not in {"0", "false", "False"}


def enabled_from_params(params: dict[str, object]) -> bool:
    """Read ingenium.bridge.enabled only. Any other key is ignored."""
    if KILL_SWITCH_PARAM not in params:
        return True
    return enabled_from_param(params[KILL_SWITCH_PARAM])


def assert_no_callback(payload: object) -> None:
    """INV-19. A callback or telemetry field is refused. Nothing is fetched."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in _CALLBACK_KEYS:
                raise BridgeError("outbound_refused")
            assert_no_callback(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_callback(item)


def apply_posture(
    ops: list[dict],
    *,
    environment: str,
    neutralized_clone: bool,
    mode: str,
) -> None:
    """Production R3 is blocked. Above R1 stays review-only until a neutralized clone exists."""
    if mode not in {"validate", "dry_run", "apply"}:
        raise BridgeError("unknown_mode")
    ceiling = 0
    ddl = False
    for op in ops:
        risk = str(op.get("risk") or "R0")
        if risk not in _RANK:
            raise BridgeError("unknown_risk")
        ceiling = max(ceiling, _RANK[risk])
        ddl = ddl or bool(op.get("ddl"))
    writing = mode != "validate"
    if environment == "production" and ceiling >= _RANK["R3"] and writing:
        raise BridgeError("production_r3_blocked")
    if environment == "staging" and not neutralized_clone and writing:
        raise BridgeError("neutralization_required")
    if not neutralized_clone and ceiling > _RANK["R1"] and writing:
        raise BridgeError("review_only")
    if mode == "dry_run" and ddl:
        raise BridgeError("ddl_no_inplace")


def dispatch_grant(*, server_secret: str, method: str, body: dict) -> str:
    """Control-plane grant. This is not an Odoo API key and is not a bridge method."""
    canonical = json.dumps(
        {"method": method, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hmac.new(server_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def authorize_direct_json(
    *,
    presented_key: str,
    dispatch_grant_value: str | None,
    server_secret: str,
    method: str,
    body: dict,
) -> None:
    """RT-36. Direct Bridge JSON authenticated only by a key is refused.

    The presented key is never sufficient and is never copied into the error.
    """
    if not isinstance(presented_key, str) or presented_key == "":
        raise BridgeError("stolen_key")
    if not isinstance(dispatch_grant_value, str) or dispatch_grant_value == "":
        raise BridgeError("stolen_key")
    if hmac.compare_digest(dispatch_grant_value, presented_key):
        raise BridgeError("stolen_key")
    expected = dispatch_grant(server_secret=server_secret, method=method, body=body)
    if not hmac.compare_digest(dispatch_grant_value, expected):
        raise BridgeError("stolen_key")


def assert_promotion(*, copy_database: bool, neutralized: bool) -> str:
    """Promotion replays a change-set. It does not copy a database."""
    if not neutralized:
        raise BridgeError("neutralization_required")
    if copy_database:
        raise BridgeError("database_copy_refused")
    return "replay"
