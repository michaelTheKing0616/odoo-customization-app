"""Snapshot + rollback helpers for risky Odoo metadata mutations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import MetadataSnapshot
from odoo_client.client import OdooClient, OdooClientError


CONFIRM_PHRASE = "I understand the risks"


class ConfirmationRequired(Exception):
    def __init__(self, warning: str, risks: list[str]) -> None:
        self.warning = warning
        self.risks = risks
        super().__init__(warning)


def require_advanced_confirmation(
    *,
    confirm_advanced: bool,
    confirm_phrase: str | None,
    warning: str,
    risks: list[str],
) -> None:
    if confirm_advanced and (confirm_phrase or "").strip() == CONFIRM_PHRASE:
        return
    raise ConfirmationRequired(warning=warning, risks=risks)


def save_snapshot(
    db: Session,
    *,
    connection_id: str,
    resource_type: str,
    resource_key: str,
    label: str,
    payload: dict[str, Any],
    reversible: str = "yes",
) -> MetadataSnapshot:
    row = MetadataSnapshot(
        connection_id=connection_id,
        resource_type=resource_type,
        resource_key=resource_key,
        label=label,
        payload_json=json.dumps(payload),
        reversible=reversible,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def snapshot_view(db: Session, connection_id: str, client: OdooClient, view_id: int) -> MetadataSnapshot:
    view = client.get_view(view_id)
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="view",
        resource_key=f"view:{view_id}",
        label=f"View {view.name} ({view.model}/{view.type})",
        payload={"view": view.model_dump()},
        reversible="yes",
    )


def snapshot_automation(
    db: Session, connection_id: str, client: OdooClient, automation_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "base.automation",
        "read",
        [[automation_id]],
        {
            "fields": [
                "id",
                "name",
                "model_id",
                "trigger",
                "active",
                "filter_domain",
                "action_server_ids",
            ]
        },
    )
    if not rows:
        raise OdooClientError(f"Automation {automation_id} not found")
    auto = rows[0]
    server_actions = []
    if auto.get("action_server_ids"):
        server_actions = client.execute_kw(
            "ir.actions.server",
            "read",
            [auto["action_server_ids"]],
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "state",
                    "code",
                    "update_path",
                    "evaluation_type",
                    "value",
                    "activity_type_id",
                    "activity_summary",
                    "activity_user_type",
                    "activity_user_id",
                    "activity_user_field_name",
                ]
            },
        )
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="automation",
        resource_key=f"automation:{automation_id}",
        label=f"Automation {auto.get('name')}",
        payload={"automation": auto, "server_actions": server_actions},
        reversible="yes",
    )


def snapshot_field(
    db: Session,
    connection_id: str,
    client: OdooClient,
    field_id: int,
    *,
    created: bool = False,
) -> MetadataSnapshot:
    field = client.read_field_raw(field_id)
    name = field.get("name") or field_id
    # Post-create: rollback may unlink metadata; DB column / data loss is partial.
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="field",
        resource_key=f"field:{field_id}",
        label=f"Field {name}",
        payload={"field": field, "created": created},
        reversible="partial",
    )


def snapshot_model(
    db: Session,
    connection_id: str,
    client: OdooClient,
    model_name: str,
    *,
    created: bool = False,
) -> MetadataSnapshot:
    model = client.read_model_raw(model_name)
    fields = [
        client.read_field_raw(f.id)
        for f in client.list_fields(model_name)
        if f.name.startswith("x_") or f.state == "manual"
    ]
    # Post-create: unlink may leave residual tables — reversible=partial honesty.
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="model",
        resource_key=f"model:{model_name}",
        label=f"Model {model_name}",
        payload={"model": model, "fields": fields, "created": created},
        reversible="partial",
    )


def snapshot_access(
    db: Session, connection_id: str, client: OdooClient, access_id: int
) -> MetadataSnapshot:
    row = client.get_access_right(access_id)
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="access",
        resource_key=f"access:{access_id}",
        label=f"Access {row.name}",
        payload={"access": row.model_dump()},
        reversible="yes",
    )


def snapshot_rule(
    db: Session, connection_id: str, client: OdooClient, rule_id: int
) -> MetadataSnapshot:
    row = client.get_record_rule(rule_id)
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="rule",
        resource_key=f"rule:{rule_id}",
        label=f"Rule {row.name}",
        payload={"rule": row.model_dump(by_alias=True)},
        reversible="yes",
    )


def snapshot_menu(
    db: Session, connection_id: str, client: OdooClient, menu_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "ir.ui.menu",
        "read",
        [[menu_id]],
        {"fields": ["name", "parent_id", "action", "sequence", "web_icon", "active"]},
    )
    if not rows:
        raise LookupError(f"Menu {menu_id} not found")
    row = rows[0]
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="menu",
        resource_key=f"menu:{menu_id}",
        label=f"Menu {row.get('name')}",
        payload={"menu": row},
        reversible="yes",
    )


def snapshot_report(
    db: Session, connection_id: str, client: OdooClient, report_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "ir.actions.report",
        "read",
        [[report_id]],
        {
            "fields": [
                "name",
                "model",
                "report_type",
                "report_name",
                "paperformat_id",
            ]
        },
    )
    if not rows:
        raise LookupError(f"Report {report_id} not found")
    report = rows[0]
    qweb = None
    key = report.get("report_name")
    if key:
        views = client.execute_kw(
            "ir.ui.view",
            "search_read",
            [[("key", "=", key), ("type", "=", "qweb")]],
            {"fields": ["id", "name", "arch", "key"], "limit": 1},
        )
        if views:
            qweb = views[0]
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="report",
        resource_key=f"report:{report_id}",
        label=f"Report {report.get('name')}",
        payload={"report": report, "qweb_view": qweb},
        reversible="yes",
    )


def snapshot_action(
    db: Session,
    connection_id: str,
    client: OdooClient,
    *,
    model: str,
    action_id: int,
    created: bool = False,
) -> MetadataSnapshot:
    """Snapshot ir.actions.* row (server / window / etc).

    When ``created=True``, rollback unlinks the action (honest for post-create
    snapshots). Update-before snapshots restore scalar vals via write.
    """
    preferred = [
        "name",
        "model_id",
        "state",
        "code",
        "binding_model_id",
        "binding_type",
        "res_model",
        "view_mode",
        "domain",
        "context",
        "target",
        "update_path",
        "evaluation_type",
        "value",
    ]
    try:
        fg = client.execute_kw(model, "fields_get", [], {"attributes": ["type"]})
        fields = [f for f in preferred if isinstance(fg, dict) and f in fg]
        if "name" not in fields:
            fields = ["name"]
    except Exception:  # noqa: BLE001
        fields = ["name"]
    rows = client.execute_kw(model, "read", [[action_id]], {"fields": fields})
    if not rows:
        raise LookupError(f"{model} {action_id} not found")
    vals = rows[0]
    # Rollback for newly created actions = unlink; updates = write restore.
    reversible = "yes" if created else "yes"
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="action",
        resource_key=f"action:{model}:{action_id}",
        label=f"Action {vals.get('name') or action_id} ({model})",
        payload={
            "model": model,
            "id": action_id,
            "vals": vals,
            "created": created,
        },
        reversible=reversible,
    )


def snapshot_created_menu(
    db: Session, connection_id: str, client: OdooClient, menu_id: int
) -> MetadataSnapshot:
    """Post-create menu snapshot — rollback deletes the new menu."""
    snap = snapshot_menu(db, connection_id, client, menu_id)
    payload = json.loads(snap.payload_json)
    payload["created"] = True
    snap.payload_json = json.dumps(payload)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def snapshot_created_report(
    db: Session, connection_id: str, client: OdooClient, report_id: int
) -> MetadataSnapshot:
    """Post-create report snapshot — rollback unlinks the report action (QWeb may remain)."""
    snap = snapshot_report(db, connection_id, client, report_id)
    payload = json.loads(snap.payload_json)
    payload["created"] = True
    # QWeb orphan after unlink is partial honesty.
    snap.reversible = "partial"
    snap.payload_json = json.dumps(payload)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def snapshot_created_access(
    db: Session, connection_id: str, client: OdooClient, access_id: int
) -> MetadataSnapshot:
    snap = snapshot_access(db, connection_id, client, access_id)
    payload = json.loads(snap.payload_json)
    payload["created"] = True
    snap.payload_json = json.dumps(payload)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def snapshot_created_rule(
    db: Session, connection_id: str, client: OdooClient, rule_id: int
) -> MetadataSnapshot:
    snap = snapshot_rule(db, connection_id, client, rule_id)
    payload = json.loads(snap.payload_json)
    payload["created"] = True
    snap.payload_json = json.dumps(payload)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def snapshot_paperformat(
    db: Session, connection_id: str, client: OdooClient, paperformat_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "report.paperformat",
        "read",
        [[paperformat_id]],
        {
            "fields": [
                "name",
                "format",
                "orientation",
                "margin_top",
                "margin_bottom",
                "margin_left",
                "margin_right",
                "header_line",
                "header_spacing",
                "dpi",
            ]
        },
    )
    if not rows:
        raise LookupError(f"Paperformat {paperformat_id} not found")
    row = rows[0]
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="paperformat",
        resource_key=f"paperformat:{paperformat_id}",
        label=f"Paperformat {row.get('name')}",
        payload={"paperformat": row},
        reversible="yes",
    )


def snapshot_ir_default(
    db: Session, connection_id: str, client: OdooClient, default_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "ir.default",
        "read",
        [[default_id]],
        {"fields": ["field_id", "json_value", "user_id", "company_id", "condition"]},
    )
    if not rows:
        raise LookupError(f"ir.default {default_id} not found")
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="ir_default",
        resource_key=f"ir_default:{default_id}",
        label=f"ir.default {default_id}",
        payload={"ir_default": rows[0]},
        reversible="yes",
    )


def snapshot_config_parameter(
    db: Session, connection_id: str, client: OdooClient, param_id: int
) -> MetadataSnapshot:
    rows = client.execute_kw(
        "ir.config_parameter",
        "read",
        [[param_id]],
        {"fields": ["key", "value"]},
    )
    if not rows:
        raise LookupError(f"ir.config_parameter {param_id} not found")
    row = rows[0]
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="config_parameter",
        resource_key=f"config_parameter:{param_id}",
        label=f"Config {row.get('key')}",
        payload={"config_parameter": row},
        reversible="yes",
    )


def list_snapshots(db: Session, connection_id: str, *, limit: int = 50) -> list[MetadataSnapshot]:
    return (
        db.query(MetadataSnapshot)
        .filter(MetadataSnapshot.connection_id == connection_id)
        .order_by(MetadataSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


def rollback_snapshot(
    db: Session,
    client: OdooClient,
    snapshot_id: str,
    *,
    connection_id: str | None = None,
) -> dict[str, Any]:
    row = db.get(MetadataSnapshot, snapshot_id)
    if row is None:
        raise LookupError("Snapshot not found")
    if connection_id is not None and row.connection_id != connection_id:
        raise LookupError("Snapshot not found for this connection")
    if row.reversible == "no":
        raise OdooClientError("This snapshot is marked non-reversible")

    payload = json.loads(row.payload_json)

    if row.resource_type == "view":
        view = payload["view"]
        client.update_view_arch(int(view["id"]), view.get("arch") or "")
        return {"restored": "view", "id": view["id"]}

    if row.resource_type == "automation":
        auto = payload["automation"]
        auto_id = int(auto["id"])
        # Best-effort: restore automation scalar fields; re-link existing server actions.
        vals: dict[str, Any] = {
            "name": auto.get("name"),
            "trigger": auto.get("trigger"),
            "active": auto.get("active"),
            "filter_domain": auto.get("filter_domain") or False,
        }
        client.execute_kw("base.automation", "write", [[auto_id], vals])
        for sa in payload.get("server_actions") or []:
            sa_id = int(sa["id"])
            sa_vals = {
                k: sa.get(k)
                for k in (
                    "name",
                    "state",
                    "code",
                    "update_path",
                    "evaluation_type",
                    "value",
                    "activity_summary",
                    "activity_user_type",
                    "activity_user_field_name",
                )
                if sa.get(k) is not False
            }
            # Many2ones
            for m2o in ("activity_type_id", "activity_user_id"):
                if isinstance(sa.get(m2o), (list, tuple)):
                    sa_vals[m2o] = sa[m2o][0]
                elif sa.get(m2o):
                    sa_vals[m2o] = sa[m2o]
            client.execute_kw("ir.actions.server", "write", [[sa_id], sa_vals])
        return {"restored": "automation", "id": auto_id}

    if row.resource_type == "server_action":
        sa = payload.get("server_action") or {}
        sa_id = int(sa["id"])
        if payload.get("created"):
            client.execute_kw("ir.actions.server", "unlink", [[sa_id]])
            return {"restored": "server_action", "id": sa_id, "action": "unlinked"}
        sa_vals = {
            k: sa.get(k)
            for k in ("name", "state", "code", "binding_model_id", "binding_type")
            if sa.get(k) is not False
        }
        if isinstance(sa.get("binding_model_id"), (list, tuple)):
            sa_vals["binding_model_id"] = sa["binding_model_id"][0]
        client.execute_kw("ir.actions.server", "write", [[sa_id], sa_vals])
        return {"restored": "server_action", "id": sa_id}

    if row.resource_type == "access":
        access = payload["access"]
        access_id = int(access["id"])
        if payload.get("created"):
            client.execute_kw("ir.model.access", "unlink", [[access_id]])
            return {"restored": "access", "id": access_id, "action": "unlinked"}
        vals = {
            k: access.get(k)
            for k in (
                "name",
                "perm_read",
                "perm_write",
                "perm_create",
                "perm_unlink",
            )
            if access.get(k) is not None
        }
        client.execute_kw("ir.model.access", "write", [[access_id], vals])
        return {"restored": "access", "id": access_id}

    if row.resource_type == "rule":
        rule = payload.get("rule") or payload.get("record_rule") or {}
        rule_id = int(rule["id"])
        if payload.get("created"):
            client.execute_kw("ir.rule", "unlink", [[rule_id]])
            return {"restored": "rule", "id": rule_id, "action": "unlinked"}
        vals: dict[str, Any] = {
            k: rule.get(k)
            for k in (
                "name",
                "domain_force",
                "active",
                "perm_read",
                "perm_write",
                "perm_create",
                "perm_unlink",
            )
            if rule.get(k) is not None and rule.get(k) is not False
        }
        if "domain_force" in rule:
            vals["domain_force"] = rule.get("domain_force") or "[(1, '=', 1)]"
        client.execute_kw("ir.rule", "write", [[rule_id], vals])
        return {"restored": "rule", "id": rule_id}

    if row.resource_type == "menu":
        menu = payload["menu"]
        menu_id = int(menu["id"])
        if payload.get("created"):
            client.execute_kw("ir.ui.menu", "unlink", [[menu_id]])
            return {"restored": "menu", "id": menu_id, "action": "unlinked"}
        # Pre-delete snapshot: recreate if gone, else write restore.
        if payload.get("deleted"):
            create_vals: dict[str, Any] = {"name": menu.get("name") or "Restored menu"}
            for k in ("sequence", "web_icon", "active"):
                if menu.get(k) is not None and menu.get(k) is not False:
                    create_vals[k] = menu[k]
            if isinstance(menu.get("parent_id"), (list, tuple)) and menu["parent_id"]:
                create_vals["parent_id"] = menu["parent_id"][0]
            if menu.get("action"):
                create_vals["action"] = menu["action"]
            new_id = int(client.execute_kw("ir.ui.menu", "create", [create_vals]))
            return {"restored": "menu", "id": new_id, "action": "recreated"}
        vals = {}
        for k in ("name", "sequence", "web_icon", "active"):
            if menu.get(k) is not None and menu.get(k) is not False:
                vals[k] = menu[k]
        if isinstance(menu.get("parent_id"), (list, tuple)) and menu["parent_id"]:
            vals["parent_id"] = menu["parent_id"][0]
        elif menu.get("parent_id") is False:
            vals["parent_id"] = False
        if menu.get("action"):
            vals["action"] = menu["action"]
        client.execute_kw("ir.ui.menu", "write", [[menu_id], vals])
        return {"restored": "menu", "id": menu_id}

    if row.resource_type == "report":
        report = payload["report"]
        report_id = int(report["id"])
        if payload.get("created"):
            # Partial: unlinks report action; orphaned QWeb view may remain.
            client.execute_kw("ir.actions.report", "unlink", [[report_id]])
            return {"restored": "report", "id": report_id, "action": "unlinked", "partial": True}
        if payload.get("deleted"):
            create_vals = {
                k: report.get(k)
                for k in ("name", "model", "report_type", "report_name")
                if report.get(k) is not None
            }
            if isinstance(report.get("paperformat_id"), (list, tuple)) and report["paperformat_id"]:
                create_vals["paperformat_id"] = report["paperformat_id"][0]
            new_id = int(client.execute_kw("ir.actions.report", "create", [create_vals]))
            return {"restored": "report", "id": new_id, "action": "recreated", "partial": True}
        vals = {
            k: report.get(k)
            for k in ("name", "model", "report_type", "report_name")
            if report.get(k) is not None
        }
        if isinstance(report.get("paperformat_id"), (list, tuple)) and report["paperformat_id"]:
            vals["paperformat_id"] = report["paperformat_id"][0]
        client.execute_kw("ir.actions.report", "write", [[report_id], vals])
        qweb = payload.get("qweb_view")
        if qweb and qweb.get("id") and qweb.get("arch") is not None:
            client.execute_kw(
                "ir.ui.view", "write", [[int(qweb["id"])], {"arch": qweb["arch"]}]
            )
        return {"restored": "report", "id": report_id}

    if row.resource_type == "action":
        model = str(payload.get("model") or "ir.actions.server")
        action_id = int(payload["id"])
        if payload.get("created"):
            client.execute_kw(model, "unlink", [[action_id]])
            return {"restored": "action", "id": action_id, "action": "unlinked", "model": model}
        vals_src = payload.get("vals") or {}
        write_vals: dict[str, Any] = {}
        for k, v in vals_src.items():
            if k in {"id"}:
                continue
            if isinstance(v, (list, tuple)) and len(v) >= 1:
                write_vals[k] = v[0]
            elif v is not False and v is not None:
                write_vals[k] = v
        if write_vals:
            client.execute_kw(model, "write", [[action_id], write_vals])
        return {"restored": "action", "id": action_id, "model": model}

    if row.resource_type == "field":
        field = payload.get("field") or {}
        field_id = int(field.get("id") or 0)
        # Post-create honesty: unlink when possible; DB column drop is partial.
        if payload.get("created") and field_id:
            client.execute_kw("ir.model.fields", "unlink", [[field_id]])
            return {
                "restored": "field",
                "id": field_id,
                "action": "unlinked",
                "partial": True,
            }
        raise OdooClientError(
            "Field rollback is partial — only post-create unlink is supported"
        )

    if row.resource_type == "model":
        model_row = payload.get("model") or {}
        model_id = model_row.get("id")
        # Post-create honesty: attempt unlink; residual tables/data may remain.
        if payload.get("created") and model_id:
            client.execute_kw("ir.model", "unlink", [[int(model_id)]])
            return {
                "restored": "model",
                "id": int(model_id),
                "action": "unlinked",
                "partial": True,
            }
        raise OdooClientError(
            "Model rollback is partial — only post-create unlink is supported"
        )

    if row.resource_type == "paperformat":
        pf = payload.get("paperformat") or {}
        pf_id = int(pf["id"])
        if payload.get("created"):
            client.execute_kw("report.paperformat", "unlink", [[pf_id]])
            return {"restored": "paperformat", "id": pf_id, "action": "unlinked"}
        write_vals = {
            k: pf.get(k)
            for k in (
                "name",
                "format",
                "orientation",
                "margin_top",
                "margin_bottom",
                "margin_left",
                "margin_right",
                "header_line",
                "header_spacing",
                "dpi",
            )
            if pf.get(k) is not None and pf.get(k) is not False
        }
        if write_vals:
            client.execute_kw("report.paperformat", "write", [[pf_id], write_vals])
        return {"restored": "paperformat", "id": pf_id}

    if row.resource_type == "ir_default":
        default = payload.get("ir_default") or {}
        default_id = int(default["id"])
        if payload.get("created"):
            client.execute_kw("ir.default", "unlink", [[default_id]])
            return {"restored": "ir_default", "id": default_id, "action": "unlinked"}
        write_vals = {}
        for k in ("json_value", "condition"):
            if default.get(k) is not None and default.get(k) is not False:
                write_vals[k] = default[k]
        if write_vals:
            client.execute_kw("ir.default", "write", [[default_id], write_vals])
        return {"restored": "ir_default", "id": default_id}

    if row.resource_type == "config_parameter":
        param = payload.get("config_parameter") or {}
        param_id = int(param["id"])
        if payload.get("created"):
            client.execute_kw("ir.config_parameter", "unlink", [[param_id]])
            return {"restored": "config_parameter", "id": param_id, "action": "unlinked"}
        write_vals = {}
        if param.get("value") is not None:
            write_vals["value"] = param["value"]
        if write_vals:
            client.execute_kw("ir.config_parameter", "write", [[param_id], write_vals])
        return {"restored": "config_parameter", "id": param_id}

    if row.resource_type == "ir_cron":
        cron = payload.get("ir_cron") or {}
        cron_id = int(cron["id"])
        write_vals = {}
        if cron.get("active") is not None:
            write_vals["active"] = cron["active"]
        if write_vals:
            client.execute_kw("ir.cron", "write", [[cron_id], write_vals])
        return {"restored": "ir_cron", "id": cron_id}

    raise OdooClientError(f"Rollback not implemented for resource_type={row.resource_type}")
