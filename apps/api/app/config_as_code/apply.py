"""Apply a compiled config plan through the in-memory change-set executor.

Fake port only. write_mode=production stays refused. L4 stays off.
"""

from __future__ import annotations

from typing import Any

from app.changeset.executor import apply as apply_changeset
from app.changeset.ops import OP_CATALOG
from app.config_as_code.loader import SECTION_OP, CompileError, op_for_section


class ApplyError(ValueError):
    """Named apply failure (type_mismatch, write_mode_production_refused, …)."""

    def __init__(self, name: str, detail: str = "") -> None:
        self.name = name
        message = name if not detail else f"{name}: {detail}"
        super().__init__(message)


class MemoryDb:
    """In-memory upsert store that also satisfies the fake OdooPort."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.writes = 0
        self.applied_params: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._by_id: dict[int, str] = {}

    def upsert(self, key: str, body: dict[str, Any]) -> bool:
        if self.rows.get(key) == body:
            return False
        self.rows[key] = dict(body)
        self.writes += 1
        return True

    def create(self, model: str, values: dict[str, Any]) -> int:
        self.writes += 1
        self._seq += 1
        key = str(values.get("xmlid") or f"{model}:{self._seq}")
        self.rows[key] = dict(values)
        self._by_id[self._seq] = key
        return self._seq

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        self.writes += 1
        for rid in ids:
            key = self._by_id.get(rid)
            if key is None:
                continue
            current = dict(self.rows.get(key) or {})
            current.update(values)
            self.rows[key] = current


class FakeConfigPort:
    """Recording OdooPort. create/write increment call_count. No network."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.applied_params: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._by_id: dict[int, str] = {}
        self.rows: dict[str, dict[str, Any]] = {}

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def create(self, model: str, values: dict[str, Any]) -> int:
        self.calls.append(("create", model, dict(values)))
        self._seq += 1
        key = str(values.get("xmlid") or f"{model}:{self._seq}")
        self.rows[key] = dict(values)
        self._by_id[self._seq] = key
        return self._seq

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        self.calls.append(("write", model, list(ids), dict(values)))
        for rid in ids:
            key = self._by_id.get(rid)
            if key is None:
                continue
            current = dict(self.rows.get(key) or {})
            current.update(values)
            self.rows[key] = current


def _string_fields_for(op_type: str) -> tuple[str, ...]:
    if op_type == "field.create":
        return ("name", "model", "ttype", "field_description")
    if op_type == "setting.set":
        return ("key",)
    if op_type == "access.create":
        return ("name", "model", "group")
    if op_type == "config_record.upsert":
        return ("model",)
    return ()


def _params_for(op_type: str, body: dict[str, Any], xmlid: str) -> dict[str, Any]:
    params = dict(body)
    params["xmlid"] = xmlid
    if op_type == "setting.set":
        values = body.get("values") if isinstance(body.get("values"), dict) else {}
        params["key"] = body.get("key") or values.get("key")
        if "value" not in body and "value" in values:
            params["value"] = values.get("value")
    elif op_type == "module.install":
        params["module"] = body.get("module") or body.get("name")
    elif op_type == "access.create":
        params["group"] = body.get("group") or body.get("group_id")
    elif op_type == "config_record.upsert":
        if not params.get("model"):
            params["model"] = body.get("model") or "ir.config_parameter"
    return params


def plan_to_changeset(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn compiled plan entries into catalog ops. Fail closed on a missing op."""
    changeset: list[dict[str, Any]] = []
    for entry in plan:
        op_type = str(entry.get("type") or "")
        section = str(entry.get("section") or "")
        if not op_type:
            if section:
                op_type = op_for_section(section)
            else:
                raise CompileError("no_matching_op")
        if op_type not in OP_CATALOG:
            raise CompileError("no_matching_op", op_type)
        body = entry.get("body") if isinstance(entry.get("body"), dict) else {}
        xmlid = str(entry.get("xmlid") or body.get("xmlid") or "")
        changeset.append(
            {
                "type": op_type,
                "xmlid": xmlid,
                "section": section,
                "params": _params_for(op_type, dict(body), xmlid),
            }
        )
    return changeset


def _assert_types(changeset: list[dict[str, Any]]) -> None:
    """Type mismatch blocks the whole apply before any write."""
    for op in changeset:
        op_type = str(op.get("type") or "")
        section = str(op.get("section") or "")
        if op_type not in OP_CATALOG:
            raise ApplyError("type_mismatch", op_type)
        expected = SECTION_OP.get(section)
        if expected and expected != op_type:
            raise ApplyError("type_mismatch", f"{section} expected {expected} got {op_type}")
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        for field in _string_fields_for(op_type):
            value = params.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ApplyError("type_mismatch", f"{op_type}.{field}")


def _remembered_params(port: Any) -> dict[str, dict[str, Any]]:
    store = getattr(port, "applied_params", None)
    if not isinstance(store, dict):
        port.applied_params = {}
        store = port.applied_params
    return store


def _needs_write(port: Any, xmlid: str, params: dict[str, Any]) -> bool:
    if not xmlid:
        return True
    store = _remembered_params(port)
    existing = store.get(xmlid)
    return existing != params


def apply_plan(
    db: MemoryDb | Any,
    plan: list[dict[str, Any]],
    *,
    write_mode: str = "",
    environment: str = "",
    acknowledge_production: bool = False,
    mode: str = "C",
) -> int:
    """Apply through the change-set executor. Second apply writes nothing when values match.

    write_mode=production is refused. A production environment still needs
    acknowledge_production (sandbox / confirmed staging only).
    """
    if str(write_mode or "").strip().lower() == "production":
        raise ApplyError("write_mode_production_refused")
    if str(environment or "").strip().lower() == "production" and not acknowledge_production:
        raise ApplyError("production_acknowledgement_required")

    changeset = plan_to_changeset(plan)
    _assert_types(changeset)

    pending: list[dict[str, Any]] = []
    for op in changeset:
        xmlid = str(op.get("xmlid") or "")
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if not _needs_write(db, xmlid, params):
            continue
        pending.append({"type": op["type"], "params": dict(params), "xmlid": xmlid})

    if not pending:
        return 0

    result = apply_changeset(pending, mode=mode, port=db)
    if result.get("status") != "VERIFIED":
        raise ApplyError("apply_failed", str(result.get("status")))

    store = _remembered_params(db)
    for op in pending:
        store[str(op.get("xmlid") or "")] = dict(op.get("params") or {})
    return len(pending)
