"""Turn a typed op into Odoo ORM calls. There is no generic write."""

from __future__ import annotations

from typing import Any, Protocol

from app.changeset.data_ops import (
    BATCH_SIZE,
    DATA_APPLY_OPS,
    LIMITED_DATA_OPS,
    PARTNER_MERGE_WIZARD,
    ROW_CAP,
    ROW_CAP_EXCEEDED,
    chunk_ids,
    chunk_rows,
    data_domain,
    data_ids,
    data_limit_issues,
    data_model,
    data_payload_issues,
    data_rows,
    delete_port_reason,
    merge_destination,
    translation_values,
)
from app.changeset.handlers import handler_for
from app.changeset.policy import heavy_gate_refusal, r4_gate
from app.changeset.logic_ops import (
    LOGIC_OP_TYPES,
    logic_payload_issues,
    logic_target_model,
    logic_values,
    logic_write_ids,
    logic_write_op,
    stage_reorder_writes,
)
from app.changeset.protected_registry import resolve_op
from app.changeset.schema_ops import SCHEMA_OP_TYPES
from app.changeset.setting_ops import (
    SETTING_OP_TYPES,
    company_write,
    config_param_args,
    module_name,
    setting_values,
)
from app.changeset.ui_ops import (
    UI_OP_TYPES,
    ui_target_model,
    ui_values,
    ui_write_ids,
    ui_write_op,
)


class OdooPort(Protocol):
    def create(self, model: str, values: dict[str, Any]) -> int: ...

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None: ...


class OdooCallPort(OdooPort, Protocol):
    """A port that can also call one public model method.

    Settings and module ops need it. A port without ``execute_kw`` refuses
    those ops before any write.
    """

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any: ...


class DispatchError(ValueError):
    pass


_REFUSED = frozenset({"module.uninstall", "rpc.write"})


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
    if op_type in SCHEMA_OP_TYPES:
        return _dispatch_schema(port, op_type, params)
    if op_type in UI_OP_TYPES:
        return _dispatch_ui(port, op_type, params)
    if op_type in LOGIC_OP_TYPES:
        return _dispatch_logic(port, op_type, params, op=op)
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
    if op_type in SETTING_OP_TYPES:
        return _dispatch_setting(port, op_type, params, op=op)
    if op_type in DATA_APPLY_OPS:
        return _dispatch_data(port, op_type, params)
    raise DispatchError(f"no dispatcher for {op_type}")


def _dispatch_setting(
    port: OdooPort,
    op_type: str,
    params: dict[str, Any],
    *,
    op: dict[str, Any] | None = None,
) -> int | None:
    """Apply one settings or module op through public model methods.

    Inputs: the port, catalog type, and resolved params. Protected keys, lock
    dates, and ``module.uninstall`` were refused before this runs. Fiscal year,
    currency, and chart of accounts may proceed when the heavy gate passed.
    Outputs: the settings wizard id, company id, or module id. ``None`` for
    ``config_param.set``.
    Side effects: ``setting.set`` creates a ``res.config.settings`` row and
    calls ``execute``. ``config_param.set`` calls
    ``ir.config_parameter.set_param``. ``company.update`` writes
    ``res.company``. ``module.install`` and ``module.upgrade`` read the
    ``ir.module.module`` row by name, then call ``button_immediate_install``
    or ``button_immediate_upgrade``. An installed module is not installed
    again. Every payload is checked before the first port call.
    """
    issues = handler_for(op_type).issues(params)
    if op_type == "company.update" and op is not None and r4_gate(op) == "heavy" and heavy_gate_refusal(op) is None:
        issues = [item for item in issues if "lock date" in item]
    if issues:
        raise DispatchError("; ".join(issues))
    try:
        if op_type == "company.update":
            ids, values = company_write(params)
            port.write("res.company", ids, values)
            return ids[0]
        call = _method_caller(port, op_type)
        if op_type == "setting.set":
            wizard_id = port.create("res.config.settings", setting_values(params))
            call("res.config.settings", "execute", [[wizard_id]])
            return wizard_id
        if op_type == "config_param.set":
            call("ir.config_parameter", "set_param", config_param_args(params))
            return None
        return _dispatch_module(call, op_type, module_name(params))
    except ValueError as exc:
        if isinstance(exc, DispatchError):
            raise
        raise DispatchError(str(exc)) from exc


def _method_caller(port: OdooPort, op_type: str) -> Any:
    call = getattr(port, "execute_kw", None)
    if not callable(call):
        raise DispatchError(f"{op_type} needs a port that can call model methods")
    return call


def _dispatch_module(call: Any, op_type: str, name: str) -> int:
    """Install or upgrade one module found by technical name.

    Inputs: the port's ``execute_kw``, the op type, and a validated name.
    Outputs: the ``ir.module.module`` id.
    Side effects: one ``search_read``, then at most one button call.
    """
    rows = call(
        "ir.module.module",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["id", "state"], "limit": 1},
    )
    if not rows:
        raise DispatchError(f"module {name} is not on this database")
    module_id = int(rows[0]["id"])
    state = str(rows[0].get("state") or "")
    if op_type == "module.install":
        if state == "installed":
            return module_id
        if state == "uninstallable":
            raise DispatchError(f"module {name} cannot be installed on this database")
        call("ir.module.module", "button_immediate_install", [[module_id]])
        return module_id
    if state != "installed":
        raise DispatchError(f"module {name} is not installed, so it cannot be upgraded")
    call("ir.module.module", "button_immediate_upgrade", [[module_id]])
    return module_id


def _dispatch_ui(port: OdooPort, op_type: str, params: dict[str, Any]) -> int | None:
    """Write one UI-family op through the existing port.

    Inputs: the port, catalog type, and resolved params. Inherit issues and
    RT-22 run before any create or write.
    Outputs: the created or written id when the port returns one.
    Side effects: create or write on public ``ir.ui.view``,
    ``ir.actions.act_window``, ``ir.ui.menu``, ``ir.filters``, or
    ``ir.actions.report`` rows. No live Odoo call of its own.
    """
    issues = handler_for(op_type).issues(params)
    if issues:
        raise DispatchError("; ".join(issues))
    model = ui_target_model(op_type)
    values = ui_values(op_type, params)
    if ui_write_op(op_type):
        ids = ui_write_ids(params)
        if not ids:
            raise DispatchError(f"{op_type} requires an id")
        port.write(model, ids, values)
        return ids[0]
    return port.create(model, values)


def _dispatch_logic(port: OdooPort, op_type: str, params: dict[str, Any], *, op: dict[str, Any] | None = None) -> int | None:
    """Write one logic-family op through the existing port.

    Inputs: the port, catalog type, and resolved params. Handler issues
    (token scan, RT-25, sequence refusals) and payload issues run before any
    create or write. Risk and approval were already gated by the executor.
    Outputs: the created or first written id.
    Side effects: create or write on public ``ir.actions.server``,
    ``base.automation``, ``ir.cron``, ``ir.sequence``, ``mail.template``,
    ``mail.activity.type``, a stage model, or ``params["model"]`` for
    config_record. ``stage.upsert`` and ``config_record.upsert`` write the
    row found by ``id`` or ``lookup_xmlid`` when the port has one, else create.
    No live Odoo call of its own.
    """
    issues = handler_for(op_type).issues(params) + logic_payload_issues(op_type, params)
    if issues:
        raise DispatchError("; ".join(issues))
    model = logic_target_model(op_type, params)
    if op_type == "stage.reorder":
        writes = stage_reorder_writes(params)
        if not writes:
            raise DispatchError("stage.reorder requires ids")
        for stage_id, values in writes:
            port.write(model, [stage_id], values)
        return writes[0][0]
    values = logic_values(op_type, params)
    if op_type == "stage.upsert":
        return _upsert_stage(port, model, params, values)
    if op_type == "config_record.upsert":
        return _upsert_config_record(port, model, params, values)
    if logic_write_op(op_type):
        ids = logic_write_ids(params)
        if not ids:
            raise DispatchError(f"{op_type} requires an id")
        port.write(model, ids, values)
        return ids[0]
    return port.create(model, values)


def _upsert_stage(
    port: OdooPort,
    model: str,
    params: dict[str, Any],
    values: dict[str, Any],
) -> int | None:
    """Write the stage named by ``id`` or ``xmlid``, or create it.

    Inputs: port, stage model, params, and allowlisted values.
    Outputs: the written or created id.
    Side effects: one write or one create. ``xmlid`` is passed to create the
    same way ``config_record.upsert`` passes it.
    """
    ids = logic_write_ids(params)
    xmlid = params.get("xmlid")
    if not ids and xmlid:
        lookup = getattr(port, "lookup_xmlid", None)
        found = lookup(xmlid) if callable(lookup) else None
        if found:
            ids = [found]
    if ids:
        port.write(model, ids, values)
        return ids[0]
    if not values.get("name"):
        raise DispatchError("stage.upsert requires a name")
    if xmlid:
        values = {**values, "xmlid": xmlid}
    return port.create(model, values)


def _upsert_config_record(
    port: OdooPort,
    model: str,
    params: dict[str, Any],
    values: dict[str, Any],
) -> int | None:
    """Write the config row named by ``id`` or ``xmlid``, or create it.

    Inputs: port, target model, params, and ``params["values"]``.
    Outputs: the written or created id.
    Side effects: one write or one create. Preserves the prior
    ``config_record.upsert`` lookup via ``port.lookup_xmlid``.
    """
    ids = logic_write_ids(params)
    xmlid = params.get("xmlid")
    if not ids and xmlid:
        lookup = getattr(port, "lookup_xmlid", None)
        found = lookup(xmlid) if callable(lookup) else None
        if found:
            ids = [int(found)]
    if ids:
        port.write(model, ids, values)
        return ids[0]
    if xmlid:
        values = {**values, "xmlid": xmlid}
    return port.create(model, values)


def _dispatch_schema(port: OdooPort, op_type: str, params: dict[str, Any]) -> int | None:
    """Write one schema-family op through the existing port.

    Inputs: the port, catalog type, and resolved params. Issues run before
    any create or write so cascade, type change, and non-``x_`` SQL stay off
    the port.
    Outputs: the created or written id when the port returns one.
    Side effects: create or write on public ``ir.model*`` rows. No live Odoo
    call of its own.
    """
    issues = handler_for(op_type).issues(params)
    if issues:
        raise DispatchError("; ".join(issues))
    if op_type == "field.create":
        return _create_field(port, params)
    if op_type == "model.create":
        model = str(params.get("model") or "")
        if not model:
            raise DispatchError("model is required")
        return port.create("ir.model", {"model": model, "name": params.get("name") or model})
    if op_type == "model.scaffold":
        return _create_scaffold(port, params)
    if op_type == "constraint.sql":
        model = str(params.get("model") or "")
        name = str(params.get("name") or "x_constraint")
        return port.create(
            "ir.model.constraint",
            {
                "name": name,
                "model": model,
                "definition": params.get("definition") or "",
                "type": "sql",
            },
        )
    ids = _schema_ids(params)
    if not ids:
        raise DispatchError(f"{op_type} requires an id")
    if op_type == "field.delete":
        port.write("ir.model.fields", ids, {"name": str(params.get("name") or "")})
        return ids[0]
    values = _schema_write_values(op_type, params)
    port.write("ir.model.fields", ids, values)
    return ids[0]


def _create_field(port: OdooPort, params: dict[str, Any]) -> int:
    """Create one ``ir.model.fields`` row. Payload stays the existing shape.

    Inputs: port and ``field.create`` params.
    Outputs: the created id.
    Side effects: ``port.create`` on ``ir.model.fields``.
    """
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


def _create_scaffold(port: OdooPort, params: dict[str, Any]) -> int:
    """Create the model, then each nested field, through this dispatcher.

    Inputs: port and ``model.scaffold`` params.
    Outputs: the created model id.
    Side effects: ``ir.model`` create, then each child ``field.create``.
    """
    model = str(params.get("model") or "")
    if not model:
        raise DispatchError("model is required")
    fields = params.get("fields")
    pending: list[dict[str, Any]] = []
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, dict):
                body = dict(field)
                body.setdefault("model", model)
                child_issues = handler_for("field.create").issues(body)
                if child_issues:
                    raise DispatchError("; ".join(child_issues))
                pending.append(body)
    created = port.create("ir.model", {"model": model, "name": params.get("name") or model})
    for body in pending:
        _create_field(port, body)
    return created


def _schema_ids(params: dict[str, Any]) -> list[int]:
    """Read write ids from schema-op params.

    Inputs: op params. ``ids`` is a list of ints. ``id`` or ``field_id`` is
    one int. Bools are ignored.
    Outputs: the ids, or an empty list when none are usable.
    Side effects: none.
    """
    raw = params.get("ids")
    if isinstance(raw, list) and raw:
        ids: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int):
                raise DispatchError("schema write requires an id")
            ids.append(item)
        return ids
    for key in ("id", "field_id"):
        item = params.get(key)
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if item:
            return [item]
    return []


def _schema_write_values(op_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Public ``ir.model.fields`` values for an update-style schema op.

    Inputs: op type and params. Type is never written.
    Outputs: a values dict the port can write.
    Side effects: none.
    """
    values: dict[str, Any] = {}
    if params.get("string"):
        values["field_description"] = params.get("string")
    if params.get("help") is not None:
        values["help"] = params.get("help")
    if op_type == "selection.update" and params.get("selection") is not None:
        values["selection"] = params.get("selection")
    if op_type == "field.deprecate":
        values.setdefault("field_description", params.get("name"))
    if not values:
        values["name"] = params.get("name")
    return values


def _dispatch_data(port: OdooPort, op_type: str, params: dict[str, Any]) -> int | None:
    """Apply one data-family op through public ORM calls.

    Inputs: the port, catalog type, and resolved params. Refusals, the
    sample/cap/batch limits, and ``stock.quant`` already ran in
    ``dispatch_op``. ``data.delete`` unlinks allow-listed ids only after the heavy gate.
    Outputs: the first created or written id.
    Side effects: every payload issue and every lookup read runs before the
    first create or write. Writes go out in batches of 200 ids.
    ``data.create_batch`` calls ``create`` once per row, grouped in batches of
    200. ``data.update_batch`` / ``data.archive_batch`` write the explicit ids,
    or ids found by ``search`` on the domain (limit 1001; more than 1000 is
    refused). ``data.import_upsert`` writes rows with an id, else looks each
    key up with ``search`` (limit 2) and writes one match or creates.
    ``data.merge`` creates ``base.partner.merge.automatic.wizard`` and calls
    ``action_merge``. ``translation.upsert`` calls ``write`` with
    ``context={'lang': lang}``. Method calls need the port's ``execute_kw``.
    """
    issues = handler_for(op_type).issues(params) + data_payload_issues(op_type, params)
    if issues:
        raise DispatchError("; ".join(dict.fromkeys(issues)))
    model = data_model(params)
    if op_type == "data.create_batch":
        first: int | None = None
        for chunk in chunk_rows(data_rows(params) or []):
            for row in chunk:
                created = port.create(model, row)
                if first is None:
                    first = created
        return first
    if op_type in {"data.update_batch", "data.archive_batch"}:
        ids = _data_target_ids(port, op_type, model, params)
        values = {"active": False} if op_type == "data.archive_batch" else dict(params["values"])
        for chunk in chunk_ids(ids):
            port.write(model, chunk, values)
        return ids[0]
    if op_type == "data.import_upsert":
        return _dispatch_upsert(port, model, params)
    if op_type == "data.merge":
        call = _method_caller(port, op_type)
        ids = data_ids(params)
        dst = merge_destination(params)
        wizard_id = port.create(
            PARTNER_MERGE_WIZARD,
            {"partner_ids": [[6, 0, ids]], "dst_partner_id": dst},
        )
        call(PARTNER_MERGE_WIZARD, "action_merge", [[wizard_id]])
        return dst
    if op_type == "translation.upsert":
        call = _method_caller(port, op_type)
        ids = data_ids(params)
        values = translation_values(params)
        lang = str(params.get("lang"))
        for chunk in chunk_ids(ids):
            call(model, "write", [chunk, values], {"context": {"lang": lang}})
        return ids[0]
    if op_type == "data.delete":
        ids = _data_target_ids(port, op_type, model, params)
        unlink = getattr(port, "unlink", None)
        for chunk in chunk_ids(ids):
            if callable(unlink):
                unlink(model, chunk)
            else:
                _method_caller(port, op_type)(model, "unlink", [chunk])
        return ids[0]
    raise DispatchError(f"no dispatcher for {op_type}")


def _data_target_ids(
    port: OdooPort, op_type: str, model: str, params: dict[str, Any]
) -> list[int]:
    """Ids an update or archive batch will write.

    Inputs: port, op type, model, and params.
    Outputs: explicit ids, or ids from one ``search`` on the domain.
    Side effects: at most one ``search`` read. More than 1000 matches, or
    none, is refused before any write.
    """
    ids = data_ids(params)
    if not ids:
        call = _method_caller(port, op_type)
        found = call(model, "search", [data_domain(params)], {"limit": ROW_CAP + 1})
        ids = [int(item) for item in (found or [])]
    if len(ids) > ROW_CAP:
        raise DispatchError(ROW_CAP_EXCEEDED)
    if not ids:
        raise DispatchError(f"{op_type} matched no records")
    return ids


def _dispatch_upsert(port: OdooPort, model: str, params: dict[str, Any]) -> int | None:
    """Write rows that match, create rows that do not.

    Inputs: port, model, and ``data.import_upsert`` params.
    Outputs: the first written or created id.
    Side effects: every key ``search`` runs first. Two matches for one key
    refuse the op before any write. Then writes and creates in row order,
    in batches of 200.
    """
    key = params.get("key")
    plan: list[tuple[int | None, dict[str, Any]]] = []
    for row in data_rows(params) or []:
        values = {k: v for k, v in row.items() if k != "id"}
        row_id = row.get("id")
        if isinstance(row_id, int) and not isinstance(row_id, bool) and row_id > 0:
            plan.append((row_id, values))
            continue
        call = _method_caller(port, "data.import_upsert")
        found = call(model, "search", [[[key, "=", row[key]]]], {"limit": 2}) or []
        if len(found) > 1:
            raise DispatchError(
                f"data.import_upsert key {key}={row[key]!r} matches more than one record"
            )
        plan.append((int(found[0]) if found else None, values))
    if len(plan) > ROW_CAP:
        raise DispatchError(ROW_CAP_EXCEEDED)
    first: int | None = None
    for start in range(0, len(plan), BATCH_SIZE):
        for record_id, values in plan[start : start + BATCH_SIZE]:
            if record_id is None:
                record_id = port.create(model, values)
            else:
                port.write(model, [record_id], values)
            if first is None:
                first = record_id
    return first
