"""Turn a typed op into Odoo ORM calls. There is no generic write."""

from __future__ import annotations

from typing import Any, Protocol

from app.changeset.handlers import handler_for
from app.changeset.protected_registry import resolve_op


class OdooPort(Protocol):
    def create(self, model: str, values: dict[str, Any]) -> int: ...

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None: ...


class DispatchError(ValueError):
    pass


_REFUSED = frozenset({"module.uninstall", "data.delete", "rpc.write"})


def dispatch_op(
    port: OdooPort,
    op: dict[str, Any],
    document: list[dict[str, Any]] | None = None,
) -> int | None:
    op_type = str(op.get("type") or "")
    doc = document if document is not None else [op]
    raw = op.get("params") if isinstance(op.get("params"), dict) else {}
    if op_type in _REFUSED:
        raise DispatchError(f"{op_type} is refused")
    try:
        reason = handler_for(op_type).refuse_reason(raw, document=doc)
    except KeyError:
        reason = f"no handler for {op_type}"
    if reason:
        raise DispatchError(reason)
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
        return port.create(
            "ir.model.access",
            {
                "name": params.get("name"),
                "model_id": params.get("model"),
                "group_id": params.get("group"),
                "perm_read": True,
            },
        )
    if op_type == "module.install":
        module = str(params.get("module") or "")
        if not module:
            raise DispatchError("module name is required")
        return port.create("ir.module.module", {"name": module, "state": "to install"})
    raise DispatchError(f"no dispatcher for {op_type}")
