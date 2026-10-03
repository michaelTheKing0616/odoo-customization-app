"""Turn a typed op into Odoo ORM calls. There is no generic write."""

from __future__ import annotations

from typing import Any, Protocol

from app.changeset.data_ops import LIMITED_DATA_OPS, data_limit_issues, delete_port_reason
from app.changeset.handlers import handler_for
from app.changeset.protected_registry import resolve_op


class OdooPort(Protocol):
    def create(self, model: str, values: dict[str, Any]) -> int: ...

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None: ...


class DispatchError(ValueError):
    pass


_REFUSED = frozenset({"module.uninstall", "data.delete", "rpc.write"})


def _create_access_v20(port: OdooPort, params: dict[str, Any]) -> int | None:
    """access.create on major 20 goes through compile_access, never ir.rule."""
    from app.odoo20.access_compiler import AccessCompileError, apply_compiled_access

    right: dict[str, Any] = {
        "name": params.get("name"),
        "model": params.get("model"),
        "group": params.get("group"),
        "operation": params.get("operation") or "read",
    }
    if params.get("domain") not in (None, False, ""):
        right["domain"] = params.get("domain")
    if "kind" in params:
        right["kind"] = params.get("kind")
    created: list[int] = []

    def _create(model: str, values: dict[str, Any]) -> None:
        created.append(int(port.create(model, values)))

    try:
        apply_compiled_access(_create, 20, [right], None)
    except AccessCompileError as exc:
        raise DispatchError(str(exc)) from exc
    return created[-1] if created else None


def _dispatch_rule(port: OdooPort, op_type: str, params: dict[str, Any]) -> int | None:
    """rule.create and rule.update go through compile_changeset_rule.

    Inputs: port, op type, and params. Major comes from ``major_of``.
    Outputs: the created id, or the updated id. Odoo 20 writes ``ir.access``.
    A compiled access row with no group is refused before the port is called.
    Side effects: create or write on the port. No version comparison of its own.
    """
    from app.odoo20.access_compiler import (
        AccessCompileError,
        compile_changeset_rule,
        major_of,
    )

    issues = handler_for(op_type).issues(params)
    if issues:
        raise DispatchError("; ".join(issues))
    try:
        compiled = compile_changeset_rule(major_of(port), params)
    except AccessCompileError as exc:
        raise DispatchError(str(exc)) from exc
    prepared: list[tuple[str, dict[str, Any]]] = []
    for item in compiled:
        model = str(item.get("model") or "")
        values = dict(item.get("values") or {})
        if model == "ir.access" and not values.get("group"):
            raise DispatchError("group-less access is refused")
        if not values.get("model"):
            raise DispatchError("missing model")
        prepared.append((model, values))
    if not prepared:
        raise DispatchError(f"{op_type} did not compile")
    if op_type == "rule.update":
        ids = _rule_ids(params)
        if not ids:
            raise DispatchError("rule.update requires an id")
        for model, values in prepared:
            port.write(model, ids, values)
        return ids[0]
    last: int | None = None
    for model, values in prepared:
        last = port.create(model, values)
    return last


def _rule_ids(params: dict[str, Any]) -> list[int]:
    raw = params.get("ids")
    if isinstance(raw, list) and raw:
        ids: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int):
                raise DispatchError("rule.update requires an id")
            ids.append(item)
        return ids
    for key in ("id", "rule_id"):
        item = params.get(key)
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if item:
            return [item]
    return []


def dispatch_op(
    port: OdooPort,
    op: dict[str, Any],
    document: list[dict[str, Any]] | None = None,
) -> int | None:
    op_type = str(op.get("type") or "")
    doc = document if document is not None else [op]
    raw = op.get("params") if isinstance(op.get("params"), dict) else {}
    if op_type == "data.delete":
        blocked = delete_port_reason(op)
        if blocked:
            raise DispatchError(blocked)
    if op_type in _REFUSED:
        raise DispatchError(f"{op_type} is refused")
    try:
        reason = handler_for(op_type).refuse_reason(raw, document=doc)
    except KeyError:
        reason = f"no handler for {op_type}"
    if reason:
        raise DispatchError(reason)
    if op_type in LIMITED_DATA_OPS:
        limit_issues = data_limit_issues(raw)
        if limit_issues:
            raise DispatchError("; ".join(limit_issues))
    resolved = resolve_op(op, doc)
    params = resolved.get("params") if isinstance(resolved.get("params"), dict) else {}
    if op_type == "field.create":
        name = str(params.get("name") or "")
        model = str(params.get("model") or "")
        if not name.startswith("x_") or name.startswith("x_studio_"):
            raise DispatchError("field name must start with x_")
        if not model:
            raise DispatchError("model is required")
        return port.create(
            "ir.model.fields",
            {
                "name": name,
                "model": model,
                "field_description": params.get("field_description") or name,
                "ttype": params.get("ttype") or "char",
            },
        )
    if op_type == "mail_template.create":
        return port.create(
            "mail.template",
            {"name": params.get("name") or "template", "model": params.get("model")},
        )
    if op_type == "access.create":
        if not params.get("group"):
            raise DispatchError("group-less access is refused")
        from app.odoo20.access_compiler import major_of

        if major_of(port) >= 20:
            return _create_access_v20(port, params)
        return port.create(
            "ir.model.access",
            {
                "name": params.get("name"),
                "model_id": params.get("model"),
                "group_id": params.get("group"),
                "perm_read": True,
            },
        )
    if op_type in {"rule.create", "rule.update"}:
        return _dispatch_rule(port, op_type, params)
    if op_type == "module.install":
        module = str(params.get("module") or "")
        if not module:
            raise DispatchError("module name is required")
        return port.create("ir.module.module", {"name": module, "state": "to install"})
    if op_type == "setting.set":
        key = str(params.get("key") or "")
        if not key:
            raise DispatchError("key is required")
        payload = {"key": key, "value": params.get("value")}
        xmlid = params.get("xmlid")
        if xmlid:
            payload["xmlid"] = xmlid
        return port.create("ir.config_parameter", payload)
    if op_type == "config_record.upsert":
        model = str(params.get("model") or "")
        if not model:
            raise DispatchError("model is required")
        values = dict(params.get("values") or {})
        xmlid = params.get("xmlid")
        if xmlid:
            values = {**values, "xmlid": xmlid}
        existing_id = None
        lookup = getattr(port, "lookup_xmlid", None)
        if callable(lookup) and xmlid:
            existing_id = lookup(xmlid)
        if existing_id:
            port.write(model, [existing_id], values)
            return existing_id
        return port.create(model, values)
    raise DispatchError(f"no dispatcher for {op_type}")
