"""Reusable component gallery seeds (AI-8)."""

from __future__ import annotations

from typing import Any

from app.ai_grain import INHERIT_FORM_XML, HOST_LABELS, module_for_model

# host_slot: fixed model | "any" with required anchor field
GALLERY: list[dict[str, Any]] = [
    {
        "id": "warranty_tracker",
        "name": "Warranty tracker",
        "description": "Track warranty start/end and status on sale orders.",
        "host_slot": "sale.order",
        "grain": "feature_slice",
        "fields": [
            {"name": "x_warranty_start", "ttype": "date", "string": "Warranty Start"},
            {"name": "x_warranty_end", "ttype": "date", "string": "Warranty End"},
            {
                "name": "x_warranty_status",
                "ttype": "selection",
                "string": "Warranty Status",
                "selection": "[('active','Active'),('expired','Expired'),('void','Void')]",
            },
        ],
        "sub_menu_name": "Warranty",
    },
    {
        "id": "inspection_checklist",
        "name": "Inspection checklist",
        "description": "Checklist fields + lines on project tasks.",
        "host_slot": "project.task",
        "grain": "feature_slice",
        "fields": [
            {
                "name": "x_inspection_state",
                "ttype": "selection",
                "string": "Inspection",
                "selection": "[('todo','To Do'),('pass','Pass'),('fail','Fail')]",
            },
            {"name": "x_inspection_due", "ttype": "date", "string": "Inspection Due"},
        ],
        "companion_model": {
            "model": "x_inspection_line",
            "description": "Inspection line",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Check item", "required": True},
                {"name": "x_done", "ttype": "boolean", "string": "Done"},
                {
                    "name": "x_task_id",
                    "ttype": "many2one",
                    "string": "Task",
                    "relation": "project.task",
                    "relation_field": "x_inspection_line_ids",
                },
            ],
            "host_o2m": {
                "name": "x_inspection_line_ids",
                "string": "Inspection lines",
                "relation": "x_inspection_line",
                "relation_field": "x_task_id",
            },
        },
        "sub_menu_name": "Inspections",
    },
    {
        "id": "compliance_status",
        "name": "Compliance status",
        "description": "Compliance status + expiry on contacts with reminder note.",
        "host_slot": "res.partner",
        "grain": "feature_slice",
        "fields": [
            {
                "name": "x_compliance_status",
                "ttype": "selection",
                "string": "Compliance Status",
                "selection": "[('ok','OK'),('review','Review'),('blocked','Blocked')]",
            },
            {"name": "x_compliance_expiry", "ttype": "date", "string": "Compliance Expiry"},
        ],
        "automations": [
            {
                "name": "Compliance expiry reminder",
                "model": "res.partner",
                "trigger": "on_time",
                "safe_actions": [{"kind": "create_activity", "activity_summary": "Compliance review due"}],
            }
        ],
    },
    {
        "id": "document_expiry_pack",
        "name": "Document expiry pack",
        "description": "Document expiry date + status — attaches to any model with a date anchor.",
        "host_slot": "any",
        "host_requires_field": "partner_id",
        "grain": "field_pack",
        "fields": [
            {"name": "x_document_expiry", "ttype": "date", "string": "Document Expiry"},
            {
                "name": "x_document_status",
                "ttype": "selection",
                "string": "Document Status",
                "selection": "[('valid','Valid'),('expiring','Expiring'),('expired','Expired')]",
            },
        ],
    },
]


def list_gallery() -> list[dict[str, str]]:
    return [
        {
            "id": g["id"],
            "name": g["name"],
            "description": g["description"],
            "host_slot": str(g.get("host_slot") or "any"),
        }
        for g in GALLERY
    ]


def get_gallery_seed(seed_id: str) -> dict[str, Any] | None:
    for g in GALLERY:
        if g["id"] == seed_id:
            return g
    return None


def gallery_seed_to_connect_points(
    seed: dict[str, Any],
    *,
    host_model: str,
) -> dict[str, Any]:
    mod = module_for_model(host_model)
    return {
        "host_model": host_model,
        "host_module": mod,
        "host_label": HOST_LABELS.get(host_model, host_model),
        "form_inherit_xml_id": INHERIT_FORM_XML.get(host_model),
        "form_xpath": "//sheet",
        "form_position": "inside",
        "menu_mode": "sub" if seed.get("sub_menu_name") else "none",
        "sub_menu_name": seed.get("sub_menu_name"),
        "gallery_id": seed["id"],
    }
