"""Apply a compiled config plan through the in-memory change-set executor.

Fake port only. write_mode=production stays refused. L4 stays off.
Destructive ops need an explicit approval flag. Production environment
needs acknowledge_production. Neither flag bypasses write_mode=production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.changeset.executor import apply as apply_changeset
from app.changeset.ops import OP_CATALOG
from app.changeset.plan_card import render_plan_card
from app.config_as_code.loader import SECTION_OP, CompileError, op_for_section
from app.plan_fingerprint import fingerprints_match, plan_fingerprint

# Catalog ops that delete, uninstall, merge partners, or post. Not reversible.
DESTRUCTIVE_OP_TYPES = frozenset(
    {
        "data.delete",
        "module.uninstall",
        "data.merge",
        "account.post",
    }
)
_DESTRUCTIVE_INTENTS = frozenset({"partner_merge", "posting", "opening_balances"})
_PARTNER_MERGE_MODELS = frozenset(
    {
        "base.partner.merge.automatic.wizard",
        "base.partner.merge.wizard",
    }
)


@dataclass
class ApplyResult:
    """Outcome of a fake-port apply. Equals an int via applied_count for 5B-02 tests."""

    applied_count: int = 0
    status: str = "VERIFIED"
    ignored: list[dict[str, Any]] = field(default_factory=list)
    plan_card: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.applied_count == other
        if isinstance(other, ApplyResult):
            return (
                self.applied_count == other.applied_count
                and self.status == other.status
                and self.ignored == other.ignored
            )
        return NotImplemented

    def __int__(self) -> int:
        return self.applied_count


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

    def __init__(self, *, ignore_writes: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.applied_params: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._by_id: dict[int, str] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self.ignore_writes = ignore_writes

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def create(self, model: str, values: dict[str, Any]) -> int:
        self.calls.append(("create", model, dict(values)))
        self._seq += 1
        if self.ignore_writes:
            return self._seq
        key = str(values.get("xmlid") or f"{model}:{self._seq}")
        self.rows[key] = dict(values)
        self._by_id[self._seq] = key
        return self._seq

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        self.calls.append(("write", model, list(ids), dict(values)))
        if self.ignore_writes:
            return
        for rid in ids:
            key = self._by_id.get(rid)
            if key is None:
                continue
            current = dict(self.rows.get(key) or {})
            current.update(values)
            self.rows[key] = current

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Model-method calls (settings execute, set_param, module buttons): recorded, no network."""
        self.calls.append(("call", model, method, list(args or []), dict(kwargs or {})))
        return True


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
    elif op_type in {"module.install", "module.uninstall"}:
        params["module"] = body.get("module") or body.get("name")
    elif op_type == "access.create":
        params["group"] = body.get("group") or body.get("group_id")
    elif op_type in {"data.delete", "data.merge", "account.post"}:
        if not params.get("model"):
            params["model"] = body.get("model") or "res.partner"
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


def _row_changes(port: Any) -> list[dict[str, Any]]:
    """Fake port/db rows as the list-of-dicts shape ``plan_fingerprint`` already hashes."""
    rows = getattr(port, "rows", None)
    if not isinstance(rows, dict):
        return []
    changes: list[dict[str, Any]] = []
    for key in sorted(rows):
        body = rows[key]
        entry: dict[str, Any] = {"xmlid": str(key)}
        if isinstance(body, dict):
            entry.update(body)
        else:
            entry["value"] = body
        changes.append(entry)
    return changes


def port_fingerprint(port: Any) -> str:
    """SHA-256[:16] of fake port/db rows. Same format as compile ``plan_fingerprint``."""
    return plan_fingerprint(_row_changes(port))


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


def _is_destructive(op: dict[str, Any]) -> bool:
    op_type = str(op.get("type") or "")
    if op_type in DESTRUCTIVE_OP_TYPES:
        return True
    params = op.get("params") if isinstance(op.get("params"), dict) else {}
    if str(params.get("intent") or "") in _DESTRUCTIVE_INTENTS:
        return True
    model = str(params.get("model") or "")
    return model in _PARTNER_MERGE_MODELS


def _apply_destructive_on_fake(port: Any, op: dict[str, Any]) -> None:
    """Record an approved destructive op on the fake port. No network, no dispatch.

    A real port is refused. The change-set dispatcher still refuses data.delete.
    """
    if not isinstance(port, (FakeConfigPort, MemoryDb)):
        raise ApplyError("destructive_fake_port_only")
    params = dict(op.get("params") or {})
    xmlid = str(op.get("xmlid") or "")
    if xmlid:
        params.setdefault("xmlid", xmlid)
    model = str(params.get("model") or f"ingenium.{op.get('type')}")
    port.create(model, params)


def _row_for(port: Any, xmlid: str, params: dict[str, Any]) -> dict[str, Any] | None:
    rows = getattr(port, "rows", None)
    if not isinstance(rows, dict):
        return None
    if xmlid and isinstance(rows.get(xmlid), dict):
        return rows[xmlid]
    key = params.get("key")
    name = params.get("name")
    model = params.get("model")
    for body in rows.values():
        if not isinstance(body, dict):
            continue
        if key and body.get("key") == key:
            return body
        if name and body.get("name") == name and (not model or body.get("model") == model):
            return body
    return None


def _read_back_ignored(port: Any, pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ignored: list[dict[str, Any]] = []
    for op in pending:
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        xmlid = str(op.get("xmlid") or params.get("xmlid") or "")
        if _row_for(port, xmlid, params) is None:
            ignored.append({"xmlid": xmlid, "type": op.get("type"), "status": "ignored"})
    return ignored


def apply_plan(
    db: MemoryDb | Any,
    plan: list[dict[str, Any]],
    *,
    write_mode: str = "",
    environment: str = "",
    acknowledge_production: bool = False,
    approve_destructive: bool = False,
    mode: str = "C",
    expected_fingerprint: str | None = None,
) -> ApplyResult:
    """Apply through the change-set executor. Second apply writes nothing when values match.

    write_mode=production is refused and is not bypassed by acknowledge_production
    or approve_destructive. A production environment still needs
    acknowledge_production (sandbox / confirmed staging only).
    Destructive catalog ops need approve_destructive before any port call.
    When ``expected_fingerprint`` is passed and fake-port rows have changed,
    raise ``plan_drift`` before any create/write. Omit it to keep today's apply.
    """
    if str(write_mode or "").strip().lower() == "production":
        raise ApplyError("write_mode_production_refused")
    if str(environment or "").strip().lower() == "production" and not acknowledge_production:
        raise ApplyError("production_acknowledgement_required")
    if expected_fingerprint is not None and not fingerprints_match(
        expected_fingerprint, _row_changes(db)
    ):
        raise ApplyError("plan_drift")

    changeset = plan_to_changeset(plan)
    _assert_types(changeset)

    if any(_is_destructive(op) for op in changeset) and not approve_destructive:
        raise ApplyError("destructive_approval_required")

    card = render_plan_card(
        changeset,
        goal="apply config",
        assumptions=("fake_port_only",),
        environment=environment or "sandbox",
    )

    pending: list[dict[str, Any]] = []
    for op in changeset:
        xmlid = str(op.get("xmlid") or "")
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if not _needs_write(db, xmlid, params):
            continue
        pending.append({"type": op["type"], "params": dict(params), "xmlid": xmlid})

    if not pending:
        return ApplyResult(0, "VERIFIED", [], card)

    destructive = [op for op in pending if _is_destructive(op)]
    safe = [op for op in pending if not _is_destructive(op)]
    if destructive:
        for op in destructive:
            _apply_destructive_on_fake(db, op)
    if safe:
        result = apply_changeset(safe, mode=mode, port=db)
        if result.get("status") != "VERIFIED":
            raise ApplyError("apply_failed", str(result.get("status")))

    ignored = _read_back_ignored(db, pending)
    if ignored:
        return ApplyResult(len(pending), "IGNORED", ignored, card)

    store = _remembered_params(db)
    for op in pending:
        store[str(op.get("xmlid") or "")] = dict(op.get("params") or {})
    return ApplyResult(len(pending), "VERIFIED", [], card)
