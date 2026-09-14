"""Deterministic hygiene for approval-style drafts."""

from __future__ import annotations

from app.ai_rules import apply_pattern_rules


def test_collapse_custom_requesters_to_hr_employee() -> None:
    draft = {
        "technical_name": "named_in_brief",
        "display_name": "Purchase Requests",
        "_approval_flow": {"kind": "community_button_gate"},
        "models": [
            {
                "model": "x_purchase_request",
                "description": "Purchase Request",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_requester_id",
                        "ttype": "many2one",
                        "relation": "x_requester",
                        "string": "Requester",
                    },
                ],
            },
            {
                "model": "x_requester",
                "description": "Requester",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Request Name", "required": True}
                ],
            },
        ],
        "views": [
            {
                "model": "x_purchase_request",
                "type": "form",
                "arch": "<form><sheet><field name=\"x_name\"/></sheet></form>",
            },
            {
                "model": "x_requester",
                "type": "form",
                "arch": "<form><sheet><field name=\"x_name\"/></sheet></form>",
            },
        ],
        "actions": [
            {"name": "Requests", "model": "x_purchase_request", "technical_name": "action_x_purchase_request"},
            {"name": "Requesters", "model": "x_requester", "technical_name": "action_x_requester"},
        ],
        "menus": [
            {
                "name": "Requesters",
                "xml_id": "menu_x_requester",
                "technical_name": "menu_x_requester",
                "action_xml_id": "action_x_requester",
                "parent_xml_id": "menu_root_named_in_brief",
            }
        ],
        "depends": ["base"],
    }

    notes = apply_pattern_rules(draft)
    assert any("requester-scrub" in n for n in notes)

    models = draft.get("models") or []
    assert all(m.get("model") != "x_requester" for m in models if isinstance(m, dict))

    pr_model = next(m for m in models if isinstance(m, dict) and m.get("model") == "x_purchase_request")
    requester_field = next(
        f
        for f in (pr_model.get("fields") or [])
        if isinstance(f, dict) and f.get("name") == "x_requester_id"
    )
    assert requester_field.get("relation") == "hr.employee"

    actions = draft.get("actions") or []
    assert all(a.get("model") != "x_requester" for a in actions if isinstance(a, dict))

    menus = draft.get("menus") or []
    assert all(
        not (isinstance(m, dict) and str(m.get("technical_name") or "").startswith("menu_x_requester"))
        for m in menus
    )

