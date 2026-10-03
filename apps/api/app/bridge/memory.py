"""In-memory bridge. No Odoo, no network, and no database copy.

The live addon still owns real savepoints, view reads, and ir.config_parameter.
This module proves the protocol decisions those entrypoints must keep.
"""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.changeset.ops import OP_CATALOG

_PROTOCOL: Any = None


class OutboundSpy:
    """Records URL calls. Bridge methods must leave `urls` empty."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def request(self, url: str, **_kwargs: object) -> None:
        self.urls.append(url)
        raise RuntimeError("outbound")


def load_protocol() -> Any:
    global _PROTOCOL
    if _PROTOCOL is not None:
        return _PROTOCOL
    path = Path(__file__).resolve().parents[4] / "odoo_addons" / "ingenium_bridge" / "protocol.py"
    spec = importlib.util.spec_from_file_location("ingenium_bridge_protocol_memory", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    _PROTOCOL = module
    return module


def _parse_execute_kw(envelope: object) -> tuple[str, list]:
    protocol = load_protocol()
    if not isinstance(envelope, dict):
        raise protocol.BridgeError("stolen_key")
    params = envelope.get("params")
    if not isinstance(params, dict):
        raise protocol.BridgeError("stolen_key")
    args = params.get("args")
    if not isinstance(args, list) or len(args) < 5 or not isinstance(args[4], str):
        raise protocol.BridgeError("stolen_key")
    method_args = args[5] if len(args) > 5 else []
    if not isinstance(method_args, list):
        raise protocol.BridgeError("stolen_key")
    return args[4], method_args


class InMemoryBridge:
    """Seven bridge methods against a dict. The outbound spy is never invoked."""

    def __init__(
        self,
        *,
        params: dict[str, object] | None = None,
        groups: set[str] | None = None,
        caller_id: int = 1,
        known_types: set[str] | None = None,
        outbound: OutboundSpy | None = None,
        server_secret: str = "memory-bridge-secret",
    ) -> None:
        self._protocol = load_protocol()
        self.params = dict(params or {})
        self.groups = set(groups) if groups is not None else {"operator"}
        self.caller_id = caller_id
        self.known_types = set(known_types) if known_types is not None else set(OP_CATALOG)
        self.outbound = outbound if outbound is not None else OutboundSpy()
        self.server_secret = server_secret
        self.records: dict[str, Any] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.transactions_opened = 0
        self.transactions_committed = 0
        self.transactions_rolled_back = 0
        self.savepoints_rolled_back = 0

    def ping(self) -> dict:
        self._gate("ping")
        payload = self._protocol.ping_payload(
            server_version="19.0",
            edition="community",
            module_hash="memory",
            capabilities={},
        )
        self._protocol.assert_no_callback(payload)
        return payload

    def introspect(self, batch_spec: dict) -> dict:
        self._gate("introspect")
        if not isinstance(batch_spec, dict):
            raise self._protocol.BridgeError("bad_batch")
        self._protocol.assert_no_callback(batch_spec)
        return {"requested": sorted(str(key) for key in batch_spec)}

    def combined_view(self, model: str, view_type: str, user_id: int | None = None) -> dict:
        self._gate("combined_view", user_id=user_id)
        return {"model": model, "view_type": view_type}

    def effective_access(self, model: str, user_ids: list) -> dict:
        self._gate("effective_access")
        self._protocol.assert_no_callback(user_ids)
        return {"model": model, "users": list(user_ids)[:20]}

    def render_check(self, kind: str, ref: str) -> dict:
        self._gate("render_check")
        if kind not in {"view", "report", "template"}:
            raise self._protocol.BridgeError("unknown_render_kind")
        before = deepcopy(self.records)
        self.records["__render_probe__"] = ref
        self.records = before
        self.savepoints_rolled_back += 1
        return {"kind": kind, "ref": ref, "writes": 0, "rolled_back": True}

    def apply_changeset(
        self,
        ops: list[dict],
        *,
        mode: str = "apply",
        environment: str = "",
        neutralized_clone: bool = False,
        max_risk: str = "R3",
        fail_at: int | None = None,
    ) -> dict:
        self._gate("apply_changeset")
        self._protocol.assert_no_callback(ops)
        self._protocol.authorize_apply(
            ops,
            known_types=self.known_types,
            protocol_version=1,
            enabled=self._protocol.enabled_from_params(self.params),
            groups=self.groups,
            caller_id=self.caller_id,
            max_risk=max_risk,
            mode=mode,
        )
        self._protocol.apply_posture(
            ops,
            environment=environment,
            neutralized_clone=neutralized_clone,
            mode=mode,
        )
        if mode == "validate":
            return {"status": "validated", "writes": 0, "copied_database": False}
        self.transactions_opened += 1
        before = deepcopy(self.records)
        try:
            if mode == "dry_run":
                scratch = deepcopy(self.records)
                for index, op in enumerate(ops):
                    if fail_at is not None and index == fail_at:
                        raise self._protocol.BridgeError("apply_failed")
                    self._mutate(scratch, op)
                if self.records != before:
                    raise self._protocol.BridgeError("ddl_no_inplace")
                self.transactions_rolled_back += 1
                return {"status": "dry_run", "writes": 0, "rolled_back": True, "copied_database": False}
            for index, op in enumerate(ops):
                if fail_at is not None and index == fail_at:
                    raise self._protocol.BridgeError("apply_failed")
                self._mutate(self.records, op)
            changeset_id = f"cs-{len(self.snapshots) + 1}"
            self.snapshots[changeset_id] = before
            self.transactions_committed += 1
            return {
                "status": "applied",
                "writes": len(ops),
                "changeset_id": changeset_id,
                "copied_database": False,
            }
        except Exception:
            self.records = before
            self.transactions_rolled_back += 1
            raise

    def rollback_changeset(self, changeset_id: str) -> dict:
        self._gate("rollback_changeset")
        before = self.snapshots.get(changeset_id)
        if before is None:
            raise self._protocol.BridgeError("unknown_changeset")
        self.records = deepcopy(before)
        return {"rolled_back": True, "copied_database": False}

    def direct_json(
        self,
        envelope: dict,
        *,
        presented_key: str,
        dispatch_grant_value: str | None = None,
    ) -> dict:
        """RT-36 entry. A key alone never reaches apply."""
        method, method_args = _parse_execute_kw(envelope)
        body = {"args": method_args}
        self._protocol.authorize_direct_json(
            presented_key=presented_key,
            dispatch_grant_value=dispatch_grant_value,
            server_secret=self.server_secret,
            method=method,
            body=body,
        )
        if method == "ping":
            return self.ping()
        if method == "introspect":
            return self.introspect(method_args[0] if method_args else {})
        if method == "combined_view":
            return self.combined_view(str(method_args[0]), str(method_args[1]))
        if method == "effective_access":
            return self.effective_access(str(method_args[0]), list(method_args[1]))
        if method == "render_check":
            return self.render_check(str(method_args[0]), str(method_args[1]))
        if method == "apply_changeset":
            ops = method_args[0] if method_args else []
            apply_mode = method_args[1] if len(method_args) > 1 else "apply"
            return self.apply_changeset(
                ops,
                mode=apply_mode,
                environment="production",
                neutralized_clone=True,
                max_risk="R2",
            )
        if method == "rollback_changeset":
            return self.rollback_changeset(str(method_args[0]))
        self._gate(method)
        raise self._protocol.BridgeError("unknown_method")

    def promote(
        self,
        ops: list[dict],
        *,
        source: Any,
        copy_database: bool = False,
        neutralized: bool = False,
        max_risk: str = "R2",
    ) -> dict:
        """Replay `ops` onto this bridge. `source.duplicate` is not called."""
        self._protocol.assert_promotion(copy_database=copy_database, neutralized=neutralized)
        result = self.apply_changeset(
            ops,
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk=max_risk,
        )
        return {
            "action": "replay",
            "copied_database": False,
            "changeset_id": result["changeset_id"],
        }

    def _gate(self, method: str, user_id: int | None = None) -> None:
        self._protocol.authorize(
            method=method,
            protocol_version=1,
            enabled=self._protocol.enabled_from_params(self.params),
            groups=self.groups,
            caller_id=self.caller_id,
            user_id=user_id,
        )

    @staticmethod
    def _mutate(records: dict[str, Any], op: dict) -> None:
        applied = records.get("applied")
        if not isinstance(applied, list):
            applied = []
            records["applied"] = applied
        applied.append(str(op.get("type") or ""))
