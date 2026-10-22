"""DEV-1 — validate, test-run, and bind live code server actions."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
from typing import Any, Literal

from odoo_client.client import OdooClient, OdooClientError
from sqlalchemy.orm import Session

from app.db_models import MetadataSnapshot
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation, save_snapshot

BindKind = Literal["standalone", "model_button", "automation"]

IMPORT_PATTERN = re.compile(r"^\s*(?:import|from)\s+", re.MULTILINE)
UNLINK_PATTERN = re.compile(r"\b(?:\.unlink\s*\(|unlink\s*\()", re.MULTILINE)
SUDO_PATTERN = re.compile(r"\b(?:\.sudo\s*\(|sudo\s*\()", re.MULTILINE)

BLOCKED_RULE_CODES = ("imports_forbidden", "sudo_pattern", "unlink_pattern")

OPTION_A_NOTE = (
    "custom code produced a module zip. It is not installed and it is not promoted. "
    "Sandbox the module, then a person publishes it."
)


class CodeStudioRuleError(ValueError):
    """Named refusal for the server-action path. No state=code row is written."""

    def __init__(
        self,
        rule: str,
        message: str,
        *,
        line: int | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        self.rule = rule
        self.line = line
        self.snapshot_id = snapshot_id
        super().__init__(message)

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


def _match_line(code: str, pattern: re.Pattern[str]) -> int | None:
    for index, line in enumerate(code.splitlines(), start=1):
        if pattern.search(line):
            return index
    return None


def _warning(code: str, message: str, line: int | None) -> dict[str, str]:
    row = {"code": code, "message": message}
    if line is not None:
        row["line"] = str(line)
    return row


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
            "line": exc.lineno,
        }
    if IMPORT_PATTERN.search(code):
        warnings.append(
            _warning(
                "imports_forbidden",
                "Import statements are blocked in server-action safe_eval.",
                _match_line(code, IMPORT_PATTERN),
            )
        )
    if UNLINK_PATTERN.search(code):
        warnings.append(
            _warning(
                "unlink_pattern",
                "unlink is blocked on the server-action path. Rollback cannot restore deleted data.",
                _match_line(code, UNLINK_PATTERN),
            )
        )
    if SUDO_PATTERN.search(code):
        warnings.append(
            _warning(
                "sudo_pattern",
                "sudo is blocked on the server-action path. It bypasses access rules.",
                _match_line(code, SUDO_PATTERN),
            )
        )
    return {"ok": True, "syntax_ok": True, "warnings": warnings, "error": None, "line": None}


def first_blocked_rule(validation: dict[str, Any]) -> dict[str, str] | None:
    by_code = {str(item.get("code")): item for item in validation.get("warnings") or []}
    for code in BLOCKED_RULE_CODES:
        hit = by_code.get(code)
        if hit:
            return hit
    return None


def _line_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rule_error(rule: dict[str, str]) -> CodeStudioRuleError:
    line = _line_int(rule.get("line"))
    where = f" (line {line})" if line else ""
    return CodeStudioRuleError(
        rule["code"],
        f"{rule['code']}{where}: {rule['message']}",
        line=line,
    )


def _code_digest(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def latest_code_test(db: Session, connection_id: str, code: str) -> dict[str, Any] | None:
    digest = _code_digest(code)
    row = (
        db.query(MetadataSnapshot)
        .filter(
            MetadataSnapshot.connection_id == connection_id,
            MetadataSnapshot.resource_type == "code_studio_test",
            MetadataSnapshot.resource_key == f"code_studio_test:{digest}",
        )
        .order_by(MetadataSnapshot.created_at.desc())
        .first()
    )
    if row is None:
        return None
    try:
        payload = json.loads(row.payload_json)
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": bool(payload.get("ok")),
        "snapshot_id": row.id,
        "exception": payload.get("exception"),
    }


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


def _write_test_snapshot(
    db: Session,
    connection_id: str,
    code: str,
    *,
    ok: bool,
    exception: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None = None,
) -> str:
    digest = _code_digest(code)
    snap = save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="code_studio_test",
        resource_key=f"code_studio_test:{digest}",
        label="Code Studio test run",
        payload={
            "code_sha256": digest,
            "ok": ok,
            "exception": exception,
            "before": before,
            "after": after,
        },
        reversible="partial",
    )
    return snap.id


def _finish_test_snapshot(
    db: Session,
    snapshot_id: str,
    code: str,
    *,
    ok: bool,
    exception: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    row = db.get(MetadataSnapshot, snapshot_id)
    if row is None:
        return
    row.payload_json = json.dumps(
        {
            "code_sha256": _code_digest(code),
            "ok": ok,
            "exception": exception,
            "before": before,
            "after": after,
        }
    )
    db.add(row)
    db.commit()


def test_run_code(
    client: OdooClient,
    *,
    db: Session,
    connection_id: str,
    model: str,
    record_id: int | None,
    code: str,
) -> dict[str, Any]:
    validation = validate_code(code)
    blocked = first_blocked_rule(validation)
    if not validation["ok"] or blocked is not None:
        rule = blocked or {
            "code": "syntax",
            "message": validation.get("error") or "Invalid code",
        }
        message = (
            f"{rule['code']}: {rule['message']}"
            if blocked is not None
            else str(validation.get("error") or "Invalid code")
        )
        snapshot_id = _write_test_snapshot(
            db,
            connection_id,
            code,
            ok=False,
            exception=message,
            before=None,
        )
        return {
            "ok": False,
            "validation": validation,
            "ran_for_real": False,
            "record": {"model": model, "id": record_id},
            "exception": message,
            "field_diff": [],
            "before": None,
            "after": None,
            "snapshot_id": snapshot_id,
            "rule": rule.get("code"),
        }

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

    snapshot_id = _write_test_snapshot(
        db,
        connection_id,
        code,
        ok=False,
        exception="Test has not finished.",
        before=before,
    )

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

    passed = exc_text is None
    _finish_test_snapshot(
        db,
        snapshot_id,
        code,
        ok=passed,
        exception=exc_text,
        before=before,
        after=after,
    )

    return {
        "ok": passed,
        "validation": validation,
        "ran_for_real": True,
        "record": {"model": model, "id": record_id},
        "exception": exc_text,
        "field_diff": diff,
        "before": before,
        "after": after,
        "snapshot_id": snapshot_id,
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
    blocked = first_blocked_rule(validation)
    if blocked is not None:
        raise _rule_error(blocked)
    prior = latest_code_test(db, connection_id, code)
    if prior is not None and not prior["ok"]:
        raise CodeStudioRuleError(
            "test_run_failed",
            (
                "test_run_failed: the last test of this code failed. "
                f"Snapshot {prior['snapshot_id']}."
            ),
            snapshot_id=str(prior["snapshot_id"]),
        )

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

    if bind_kind == "automation" and not trigger:
        raise ValueError("trigger is required for automation bind")

    result: dict[str, Any] = {"bind_kind": bind_kind, "code": code}
    snap = save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="automation" if bind_kind == "automation" else "server_action",
        resource_key=f"code_studio_bind:pending:{_code_digest(code)[:16]}",
        label=f"Before bind {name}",
        payload={
            "pending": True,
            "name": name,
            "model": model,
            "bind_kind": bind_kind,
            "code_sha256": _code_digest(code),
        },
        reversible="partial",
    )

    if bind_kind == "automation":
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
        snap.resource_type = "automation"
        snap.resource_key = f"automation:{auto_id}"
        snap.label = f"Automation {name}"
        snap.payload_json = json.dumps(
            {"pending": False, "automation": rows[0], "server_actions": server_actions}
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
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
        snap.resource_type = "server_action"
        snap.resource_key = f"server_action:{action_id}"
        snap.label = f"Server action {name}"
        snap.payload_json = json.dumps(
            {"pending": False, "server_action": sa_rows[0], "created": True}
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        result.update({"server_action_id": action_id})

    result["snapshot_id"] = snap.id
    result["confirm_phrase_used"] = CONFIRM_PHRASE
    return result


def _module_technical_name(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (raw or "").strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug or not slug[0].isalpha():
        slug = f"cs_{slug}" if slug else "cs_snippet"
    if len(slug) > 40:
        slug = slug[:40].rstrip("_")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", slug):
        raise ValueError("technical_name must be a lowercase python module name")
    return slug


def export_option_a_zip(
    *,
    name: str,
    model: str,
    code: str,
    technical_name: str | None = None,
    depends: list[str] | None = None,
    as_extension: bool = False,
    odoo_major: int | None = None,
) -> dict[str, Any]:
    """Build a custom-code module zip. Does not install or promote it."""
    if not (code or "").strip():
        raise ValueError("code is required")
    if not (model or "").strip():
        raise ValueError("model is required")
    from module_generator import ModuleSpec, build_module_zip

    tech = _module_technical_name(technical_name or name)
    body = (
        "# custom code export from Code Studio.\n"
        "# This module is not installed and not promoted by Code Studio.\n"
        "# Sandbox the zip, then a person publishes it.\n"
        f"# Target model: {model.strip()}\n\n"
        f"{code if code.endswith(chr(10)) else code + chr(10)}"
    )
    if as_extension:
        # An _inherit extension must be imported to load: root -> models -> file.
        stem = _slug_model(model)
        blocks = [
            {"source_file": "__init__.py", "content": "from . import models\n"},
            {"source_file": "models/__init__.py", "content": f"from . import {stem}\n"},
            {"source_file": f"models/{stem}.py", "content": body},
        ]
    else:
        blocks = [{"source_file": "code_studio_snippet.py", "content": body}]
    deps = [d for d in (depends or []) if isinstance(d, str) and re.fullmatch(r"[a-z0-9_]+", d)]
    spec = ModuleSpec(
        technical_name=tech,
        display_name=(name or tech)[:80],
        install_mode="python",
        depends=deps or ["base"],
        custom_code_blocks=blocks,
        odoo_major=odoo_major,
        **({"version": f"{int(odoo_major)}.0.1.0.0"} if odoo_major else {}),
    )
    zip_bytes = build_module_zip(spec)
    return {
        "ok": True,
        "installed": False,
        "promoted": False,
        "technical_name": tech,
        "filename": f"{tech}.zip",
        "content_base64": base64.b64encode(zip_bytes).decode("ascii"),
        "note": OPTION_A_NOTE,
    }


# ---------------------------------------------------------------- stock extension scaffold

EXTENSION_KINDS = ("selection_options", "computed_field", "behaviour")


def _slug_model(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_") + "_extension"


def _class_for(model: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^a-zA-Z0-9]+", model) if p) + "Extension"


def _py_str(value: str) -> str:
    return repr(str(value))


def stock_extension_scaffold(
    *,
    model: str,
    kind: str,
    field_name: str | None = None,
    label: str | None = None,
    options: list[dict[str, str]] | None = None,
) -> str:
    """Small _inherit extension for things only code can do on a built-in model.

    Never redefines a stock field: selection options use ``selection_add``.
    """
    model = (model or "").strip()
    if not re.fullmatch(r"[a-z0-9_.]+", model):
        raise ValueError("Pick a model first.")
    if kind not in EXTENSION_KINDS:
        raise ValueError("Pick what the custom code should do.")
    cls = _class_for(model)
    head = (
        "from odoo import api, fields, models\n\n\n"
        f"class {cls}(models.Model):\n"
        f"    _inherit = {model!r}\n"
    )
    if kind == "selection_options":
        fname = (field_name or "").strip()
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", fname):
            raise ValueError("Pick the choice field to add options to.")
        pairs = [
            (str(o.get("value") or "").strip(), str(o.get("label") or o.get("value") or "").strip())
            for o in (options or [])
            if isinstance(o, dict)
        ]
        pairs = [(v, lab) for v, lab in pairs if re.fullmatch(r"[a-z0-9_]+", v)]
        if not pairs:
            raise ValueError("Add at least one option (lowercase value, then a label).")
        add = ", ".join(f"({_py_str(v)}, {_py_str(lab)})" for v, lab in pairs)
        ondelete = ", ".join(f"{_py_str(v)}: 'set null'" for v, _ in pairs)
        return head + (
            "\n    # Adds options to Odoo's own choice field; the original options stay.\n"
            f"    {fname} = fields.Selection(\n"
            f"        selection_add=[{add}],\n"
            f"        ondelete={{{ondelete}}},\n"
            "    )\n"
        )
    if kind == "computed_field":
        fname = (field_name or "").strip()
        if not fname.startswith("x_"):
            fname = "x_" + re.sub(r"[^a-z0-9_]+", "_", fname.lower()).strip("_")
        if not re.fullmatch(r"x_[a-z0-9_]+", fname):
            raise ValueError("Give the new field a name.")
        text = label or fname[2:].replace("_", " ").capitalize()
        return head + (
            f"\n    {fname} = fields.Char(string={_py_str(text)}, compute='_compute_{fname}')\n\n"
            f"    @api.depends('display_name')\n"
            f"    def _compute_{fname}(self):\n"
            "        for record in self:\n"
            f"            # Replace with your rule.\n"
            f"            record.{fname} = record.display_name or False\n"
        )
    return head + (
        "\n    def write(self, vals):\n"
        "        # Change what happens when a record is saved, then keep Odoo's own behaviour.\n"
        "        return super().write(vals)\n"
    )
