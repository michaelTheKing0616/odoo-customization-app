"""DEV-1 — validate, test-run, and bind live code server actions."""

from __future__ import annotations

import ast
import re
from typing import Any, Literal

from odoo_client.client import OdooClient, OdooClientError
from sqlalchemy.orm import Session

from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation, save_snapshot

BindKind = Literal["standalone", "model_button", "automation"]

IMPORT_PATTERN = re.compile(r"^\s*(?:import|from)\s+", re.MULTILINE)
UNLINK_PATTERN = re.compile(r"\b(?:\.unlink\s*\(|unlink\s*\()", re.MULTILINE)
SUDO_PATTERN = re.compile(r"\b(?:\.sudo\s*\(|sudo\s*\()", re.MULTILINE)

SAFE_EVAL_CONTEXT: dict[str, list[dict[str, str]]] = {
    "19": [
        {"name": "records", "description": "Recordset the action runs on (may be empty)."},
        {"name": "record", "description": "First record when exactly one is selected."},
        {"name": "model", "description": "Model class for the action's target model."},
        {"name": "env", "description": "Odoo Environment (browse/create with usual ACLs)."},
        {"name": "log", "description": "Logger for safe messages."},
        {"name": "UserError", "description": "Raise to show a blocking error to the user."},
        {"name": "Warning", "description": "Raise to show a non-blocking warning."},
    ],
    "default": [
        {"name": "records", "description": "Recordset the action runs on."},
        {"name": "record", "description": "Single record shortcut when one active_id."},
        {"name": "model", "description": "Model class bound to the server action."},
        {"name": "env", "description": "Odoo Environment."},
        {"name": "log", "description": "Logger."},
        {"name": "UserError", "description": "User-facing error."},
    ],
}

SNIPPETS: list[dict[str, str]] = [
    {
        "id": "set_field",
        "label": "Set a field",
        "code": "for rec in records:\n    rec.write({'name': 'Updated from Code Studio'})",
    },
    {
        "id": "create_activity",
        "label": "Schedule activity",
        "code": (
            "for rec in records:\n"
            "    rec.activity_schedule('mail.mail_activity_data_todo', summary='Follow up')"
        ),
    },
    {
        "id": "post_message",
        "label": "Post chatter note",
        "code": "for rec in records:\n    rec.message_post(body='Code Studio note', message_type='comment')",
    },
    {
        "id": "guard_clause",
        "label": "Guard clause",
        "code": (
            "if not records:\n"
            "    raise UserError('Select at least one record.')\n"
            "for rec in records:\n"
            "    if rec.state != 'draft':\n"
            "        raise UserError('Only draft records allowed.')"
        ),
    },
]


def context_reference(major: int | None) -> list[dict[str, str]]:
    key = str(major) if major in {16, 17, 18, 19} else "default"
    return list(SAFE_EVAL_CONTEXT.get(key, SAFE_EVAL_CONTEXT["default"]))


def validate_code(code: str) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    try:
        ast.parse(code or "")
    except SyntaxError as exc:
        return {
            "ok": False,
            "syntax_ok": False,
            "warnings": [],
            "error": f"Syntax error: {exc.msg} (line {exc.lineno})",
        }
    if IMPORT_PATTERN.search(code):
        warnings.append(
            {
                "code": "imports_forbidden",
                "message": "Import statements are blocked in server-action safe_eval.",
            }
        )
    if UNLINK_PATTERN.search(code):
        warnings.append(
            {
                "code": "unlink_pattern",
                "message": "Code may delete records — rollback cannot restore deleted data.",
            }
        )
    if SUDO_PATTERN.search(code):
        warnings.append(
            {
                "code": "sudo_pattern",
                "message": "sudo() bypasses access rules — side effects may exceed your role.",
            }
        )
    return {"ok": True, "syntax_ok": True, "warnings": warnings, "error": None}


def _read_record_fields(client: OdooClient, model: str, record_id: int, fields: list[str]) -> dict[str, Any]:
    rows = client.execute_kw(
        model,
        "read",
        [[record_id]],
        {"fields": fields},
    )
    if not rows:
        raise OdooClientError(f"Record {model},{record_id} not found")
    return rows[0]


def _scalar_fields(client: OdooClient, model: str, *, limit: int = 12) -> list[str]:
    fg = client.execute_kw(model, "fields_get", [], {"attributes": ["type", "store"]})
    out: list[str] = []
    for name, meta in fg.items():
        if name in {"id", "display_name", "__last_update"}:
            continue
        ttype = meta.get("type")
        if ttype in {"one2many", "many2many", "binary", "html"}:
            continue
        out.append(name)
        if len(out) >= limit:
            break
    return out or ["display_name"]


def test_run_code(
    client: OdooClient,
    *,
    model: str,
    record_id: int | None,
    code: str,
) -> dict[str, Any]:
    validation = validate_code(code)
    if not validation["ok"]:
        return {"ok": False, "validation": validation, "ran_for_real": False}

    model_id = client.execute_kw(
        "ir.model",
        "search",
        [[("model", "=", model)]],
        {"limit": 1},
    )
    if not model_id:
        raise OdooClientError(f"Model {model!r} not found")

    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    field_names: list[str] = []
    if record_id is not None:
        field_names = _scalar_fields(client, model)
        before = _read_record_fields(client, model, record_id, field_names)

    action_id: int | None = None
    exc_text: str | None = None
    try:
        action_id = int(
            client.execute_kw(
                "ir.actions.server",
                "create",
                [
                    {
                        "name": "OC Code Studio test (ephemeral)",
                        "model_id": model_id[0],
                        "state": "code",
                        "code": code,
                    }
                ],
            )
        )
        ctx: dict[str, Any] = {}
        if record_id is not None:
            ctx = {
                "active_id": record_id,
                "active_ids": [record_id],
                "active_model": model,
            }
        client.execute_kw(
            "ir.actions.server",
            "run",
            [[action_id]],
            {"context": ctx},
        )
    except Exception as exc:  # noqa: BLE001
        exc_text = str(exc)
    finally:
        if action_id is not None:
            try:
                client.execute_kw("ir.actions.server", "unlink", [[action_id]])
            except Exception:  # noqa: BLE001
                pass

    if record_id is not None and exc_text is None:
        after = _read_record_fields(client, model, record_id, field_names)

    diff: list[dict[str, Any]] = []
    if before and after:
        for key in field_names:
            if before.get(key) != after.get(key):
                diff.append({"field": key, "before": before.get(key), "after": after.get(key)})

    return {
        "ok": exc_text is None,
        "validation": validation,
        "ran_for_real": True,
        "record": {"model": model, "id": record_id},
        "exception": exc_text,
        "field_diff": diff,
        "before": before,
        "after": after,
    }


def bind_code_action(
    db: Session,
    client: OdooClient,
    *,
    connection_id: str,
    name: str,
    model: str,
    code: str,
    bind_kind: BindKind,
    confirm_advanced: bool,
    confirm_phrase: str | None,
    trigger: str | None = None,
    filter_domain: str | None = None,
    bind_to_model: bool = True,
) -> dict[str, Any]:
    validation = validate_code(code)
    if not validation["ok"]:
        raise ValueError(validation.get("error") or "Invalid code")

    risks = [
        "Python runs with the Odoo credentials on this connection",
        "Rollback removes the action/automation — not data already changed",
    ]
    for w in validation.get("warnings") or []:
        risks.append(w.get("message", ""))

    warning = (
        "You are binding live Python (state=code) on this database. "
        "Review the code and confirm you accept the risks."
    )
    try:
        require_advanced_confirmation(
            confirm_advanced=confirm_advanced,
            confirm_phrase=confirm_phrase,
            warning=warning,
            risks=[r for r in risks if r],
        )
    except ConfirmationRequired:
        raise

    model_id = client.execute_kw(
        "ir.model",
        "search",
        [[("model", "=", model)]],
        {"limit": 1},
    )
    if not model_id:
        raise OdooClientError(f"Model {model!r} not found")

    snapshot_id: str | None = None
    result: dict[str, Any] = {"bind_kind": bind_kind, "code": code}

    if bind_kind == "automation":
        if not trigger:
            raise ValueError("trigger is required for automation bind")
        client.ensure_module_installed("base_automation")
        server_vals = {
            "name": f"{name} (code)",
            "model_id": model_id[0],
            "state": "code",
            "code": code,
        }
        auto_vals: dict[str, Any] = {
            "name": name,
            "model_id": model_id[0],
            "trigger": trigger,
            "active": True,
            "action_server_ids": [(0, 0, server_vals)],
        }
        if filter_domain:
            auto_vals["filter_domain"] = filter_domain
        auto_id = int(client.execute_kw("base.automation", "create", [auto_vals]))
        rows = client.execute_kw(
            "base.automation",
            "read",
            [[auto_id]],
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
        server_actions = []
        if rows and rows[0].get("action_server_ids"):
            server_actions = client.execute_kw(
                "ir.actions.server",
                "read",
                [rows[0]["action_server_ids"]],
                {"fields": ["id", "name", "state", "code", "model_id"]},
            )
        snap = save_snapshot(
            db,
            connection_id=connection_id,
            resource_type="automation",
            resource_key=f"automation:{auto_id}",
            label=f"Automation {name}",
            payload={"automation": rows[0], "server_actions": server_actions},
            reversible="partial",
        )
        snapshot_id = snap.id
        result.update({"automation_id": auto_id, "server_action_ids": rows[0].get("action_server_ids")})
    else:
        vals: dict[str, Any] = {
            "name": name,
            "model_id": model_id[0],
            "state": "code",
            "code": code,
        }
        if bind_kind == "model_button" or bind_to_model:
            vals["binding_model_id"] = model_id[0]
            vals["binding_type"] = "action"
        action_id = int(client.execute_kw("ir.actions.server", "create", [vals]))
        sa_rows = client.execute_kw(
            "ir.actions.server",
            "read",
            [[action_id]],
            {"fields": ["id", "name", "state", "code", "model_id", "binding_model_id", "binding_type"]},
        )
        snap = save_snapshot(
            db,
            connection_id=connection_id,
            resource_type="server_action",
            resource_key=f"server_action:{action_id}",
            label=f"Server action {name}",
            payload={"server_action": sa_rows[0], "created": True},
            reversible="partial",
        )
        snapshot_id = snap.id
        result.update({"server_action_id": action_id})

    result["snapshot_id"] = snapshot_id
    result["confirm_phrase_used"] = CONFIRM_PHRASE
    return result
