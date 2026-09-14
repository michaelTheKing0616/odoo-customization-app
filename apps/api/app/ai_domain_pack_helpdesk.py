"""Internal helpdesk tickets — thin residual, not project management or timesheets."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def helpdesk_tickets_pack() -> dict[str, Any]:
    ticket_status = _sel(
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("waiting", "Waiting"),
        ("done", "Done"),
    )
    category = _sel(
        ("laptop", "Laptop"),
        ("network", "Network"),
        ("access", "Access"),
    )
    priority = _sel(
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    )

    return {
        "technical_name": "helpdesk_tickets",
        "display_name": "Helpdesk",
        "depends": ["base", "contacts", "mail", "hr"],
        "domain_pack": "helpdesk_tickets",
        "document_shape": "workspace",
        "tags": [
            "helpdesk",
            "ticket",
            "support",
            "IT",
            "asset tag",
            "requester",
            "internal support",
        ],
        "anti_patterns": [
            "Do NOT clone project.task or project.project — tickets are x_ticket only",
            "Do NOT add x_project, x_milestone, x_team_member, or PM workspace models",
            "Time spent is x_ticket_time_line O2M — not hr_timesheet or a second Timesheet app",
            "This is internal helpdesk, not ITSM / SLA enterprise helpdesk",
        ],
        "models": [
            {
                "model": "x_ticket",
                "description": "Ticket",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "in_progress"],
                        ["in_progress", "waiting"],
                        ["waiting", "done"],
                    ],
                    "states": ["draft", "in_progress", "waiting", "done"],
                    "statusbar_visible": ["draft", "in_progress", "waiting", "done"],
                },
                "fields": [
                    {
                        "name": "x_name",
                        "ttype": "char",
                        "string": "Subject",
                        "required": True,
                        "help": "Short title for the ticket.",
                    },
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Auto-numbered via ir.sequence (TICKET/00001)",
                    },
                    {
                        "name": "x_requester_id",
                        "ttype": "many2one",
                        "string": "Requester",
                        "relation": "hr.employee",
                        "required": True,
                        "help": "Employee who opened the ticket — link-only to HR.",
                    },
                    {
                        "name": "x_asset_tag",
                        "ttype": "char",
                        "string": "Asset Tag",
                    },
                    {
                        "name": "x_category",
                        "ttype": "selection",
                        "string": "Category",
                        "selection": category,
                    },
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": priority,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": ticket_status,
                        "required": True,
                        "default": "draft",
                        "tracking": True,
                    },
                    {
                        "name": "x_description",
                        "ttype": "text",
                        "string": "Description",
                    },
                    {
                        "name": "x_time_line_ids",
                        "ttype": "one2many",
                        "string": "Time Spent",
                        "relation": "x_ticket_time_line",
                        "relation_field": "x_ticket_id",
                    },
                ],
                "is_mail_thread": True,
                "is_mail_activity": True,
            },
            {
                "model": "x_ticket_time_line",
                "description": "Time Spent Line",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_name",
                        "ttype": "char",
                        "string": "Entry",
                        "required": True,
                    },
                    {
                        "name": "x_ticket_id",
                        "ttype": "many2one",
                        "string": "Ticket",
                        "relation": "x_ticket",
                        "required": True,
                    },
                    {
                        "name": "x_hours",
                        "ttype": "float",
                        "string": "Hours",
                        "required": True,
                    },
                    {
                        "name": "x_note",
                        "ttype": "text",
                        "string": "Note",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "hr.employee",
                "label": "Tickets",
                "related_model": "x_ticket",
                "relation_field": "x_requester_id",
                "icon": "fa-ticket",
                "requires_inherit_view": True,
                "note": "Applied as inherit on Employees button_box",
                "source": "stock_host_smart_button",
            }
        ],
        "reuse_hints": [
            {
                "model": "hr.employee",
                "reason": "Requester on tickets — do not invent x_staff",
            },
        ],
        "reuse_stock": [
            {
                "model": "hr.employee",
                "reason": "Ticket requester",
                "forbid_parallel": ["x_employee", "x_staff", "x_requester"],
            },
        ],
    }


_HELPDESK_FORBIDDEN_APPS = frozenset({"project", "purchase"})
_HELPDESK_FORBIDDEN_MODELS = frozenset(
    {"project.task", "project.project", "purchase.order", "purchase.order.line"}
)
_HELPDESK_FORBIDDEN_FIELDS = frozenset(
    {
        "x_project_id",
        "x_purchase_order_id",
        "x_task_id",
        "x_milestone_id",
        "x_timesheet_ids",
    }
)


def _is_helpdesk_draft(draft: dict[str, Any], prompt: str) -> bool:
    if str(draft.get("domain_pack") or "") == "helpdesk_tickets":
        return True
    try:
        from app.ai_domain_coherence import helpdesk_ticket_intent

        return helpdesk_ticket_intent(prompt or str(draft.get("_user_prompt") or ""))
    except Exception:  # noqa: BLE001
        return False


def scrub_helpdesk_prompt_fit(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Tickets stay x_ticket + time lines — never a fake Project / PO / second employee."""
    text = prompt or str(draft.get("_user_prompt") or "")
    if not _is_helpdesk_draft(draft, text):
        return []
    notes: list[str] = []
    removed = {
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and (
            str(m.get("model") or "") in _HELPDESK_FORBIDDEN_MODELS
            or (
                str(m.get("mode") or "") == "inherit"
                and str(m.get("model") or "") in _HELPDESK_FORBIDDEN_MODELS
            )
        )
    }
    if removed:
        from app.ai_domain_packs import _purge_draft_artifacts_for_models

        try:
            from app.ai_odoo_app_bar import _retarget_removed_relations

            notes.extend(_retarget_removed_relations(draft, removed))
        except Exception:  # noqa: BLE001
            pass
        _purge_draft_artifacts_for_models(draft, removed)
        notes.append("helpdesk: dropped " + ", ".join(sorted(removed)))

    depends = [str(d) for d in (draft.get("depends") or []) if d]
    cleaned = [d for d in depends if d not in _HELPDESK_FORBIDDEN_APPS]
    if cleaned != depends:
        draft["depends"] = cleaned
        notes.append("helpdesk: depends without project/purchase")

    try:
        from app.ai_odoo_app_bar import _drop_named_fields
    except Exception:  # noqa: BLE001
        _drop_named_fields = None  # type: ignore[assignment]

    for model in list(draft.get("models") or []):
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        drop: set[str] = set()
        employee_fields = [
            str(f.get("name") or "")
            for f in fields
            if str(f.get("relation") or "") == "hr.employee"
        ]
        if len(employee_fields) > 1:
            keep_emp = (
                "x_requester_id" if "x_requester_id" in employee_fields else employee_fields[0]
            )
            drop.update(n for n in employee_fields if n and n != keep_emp)
        for field in fields:
            fname = str(field.get("name") or "")
            rel = str(field.get("relation") or "")
            if fname in _HELPDESK_FORBIDDEN_FIELDS or rel in _HELPDESK_FORBIDDEN_MODELS:
                drop.add(fname)
        if mid.endswith("_time_line") or mid == "x_ticket_time_line":
            names = {str(f.get("name") or "") for f in fields}
            if "x_status" in names:
                drop.add("x_status")
                model.pop("state_field", None)
                model["is_workflow"] = False
            if "x_note" not in names:
                fields.append(
                    {
                        "name": "x_note",
                        "ttype": "text",
                        "string": "Note",
                    }
                )
                model["fields"] = fields
                notes.append(f"helpdesk: {mid} keeps hours + note")
        if drop:
            if _drop_named_fields:
                _drop_named_fields(draft, mid, drop)
            else:
                model["fields"] = [f for f in fields if str(f.get("name") or "") not in drop]
            notes.append(f"helpdesk: dropped {', '.join(sorted(drop))} on {mid}")

    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        kept = [
            b
            for b in buttons
            if not (
                isinstance(b, dict)
                and (
                    str(b.get("on_model") or "") in _HELPDESK_FORBIDDEN_MODELS
                    or str(b.get("related_model") or "") in _HELPDESK_FORBIDDEN_MODELS
                )
            )
        ]
        if len(kept) != len(buttons):
            draft["smart_buttons"] = kept
            notes.append("helpdesk: dropped Project/PO smart buttons")
    return notes


__all__ = ["helpdesk_tickets_pack", "scrub_helpdesk_prompt_fit"]
