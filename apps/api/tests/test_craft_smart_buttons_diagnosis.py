"""Craft smart buttons — Diagnosis Nice-to-have chips → Generate gate."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db
os.environ["AI_INTENT_LLM"] = "off"

from app.ai_craft_smart_buttons import propose_craft_smart_buttons  # noqa: E402
from app.ai_conversation.understand import (  # noqa: E402
    apply_understanding_edits,
    build_understanding,
    diagnosis_clarification,
)
from app.ai_operator_surface import build_operator_surface  # noqa: E402
from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons  # noqa: E402

VISITOR = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

PREFER = (
    "On Contacts (res.partner), add checkbox Preferred for delivery and "
    "Delivery notes text under Delivery group. Do not create a new app."
)

PUNCH = (
    "We already use Community POS. What we don’t have is a simple loyalty punch card: "
    "buy 9 coffees get the 10th free, tied to the customer (Contacts)."
)


def test_visitor_log_proposes_employee_visits_craft_chip() -> None:
    u = build_understanding(VISITOR)
    props = u.craft_proposals
    assert props, "expected craft proposals on Visitor Log"
    assert props[0]["on_model"] == "hr.employee"
    assert props[0]["label"] == "Visits"
    assert props[0]["default_on"] is True
    assert props[0]["related_model"] == "x_visitor_log"
    if len(props) > 1:
        assert props[1]["default_on"] is False
    card = diagnosis_clarification(u)
    assert "«Visits» on Employees" in (card.get("nice_to_have") or [])


def test_removed_craft_chip_not_in_generate_ir() -> None:
    u = build_understanding(VISITOR)
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": [],
        },
    )
    assert locked.craft_smart_buttons == []
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "hr.employee",
                "label": "Visits",
                "related_model": "x_visitor_log",
                "relation_field": "x_host_id",
            }
        ],
        "_understanding": locked.to_dict(),
    }
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    hosts = {
        str(b.get("on_model"))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    assert "hr.employee" not in hosts
    assert "res.partner" not in hosts


def test_confirmed_craft_chip_stamped_on_generate() -> None:
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": kept,
        },
    )
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [],
        "_understanding": locked.to_dict(),
    }
    notes = apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert any("craft_smart_btn" in n for n in notes)
    btns = [b for b in draft["smart_buttons"] if isinstance(b, dict)]
    assert len(btns) == 1
    assert btns[0]["on_model"] == "hr.employee"
    assert btns[0]["source"] == "craft_confirmed"
    surface = build_operator_surface(draft)
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    assert "hr.employee" in hosts


def test_silent_invent_still_blocked_without_craft() -> None:
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                ],
            }
        ],
        "smart_buttons": [],
        "_understanding": {"grain": "full_app", "craft_smart_buttons": []},
    }
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert draft.get("smart_buttons") == []


def test_prefer_contacts_unchanged_no_craft() -> None:
    u = build_understanding(PREFER)
    assert u.inherit_existing is True
    assert u.host_model == "res.partner"
    assert propose_craft_smart_buttons(PREFER, u) == []
    assert u.craft_proposals == []


def test_punch_partner_tie_still_gets_contacts_without_craft() -> None:
    draft = {
        "display_name": "Punch Card",
        "grain": "full_app",
        "_user_prompt": PUNCH,
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [],
    }
    apply_stock_host_smart_buttons(draft, prompt=PUNCH)
    hosts = {b["on_model"] for b in draft["smart_buttons"]}
    assert "res.partner" in hosts

def test_llm_shaped_must_do_still_proposes_craft() -> None:
    """LLM enrich rewrites Must-do lines — craft must still parse Host/Company M2O."""
    from app.ai_craft_smart_buttons import propose_craft_smart_buttons

    class _U:
        grain = "full_app"
        inherit_existing = False
        title = "Visitor Log"
        constraints = [
            "Create new model `x_visitor_log` (Visitor Log).",
            "Add `company_id` field (Many2one to `res.partner`) for Company.",
            "Add `host_id` field (Many2one to `hr.employee`) for Host.",
        ]

    props = propose_craft_smart_buttons(VISITOR, _U())
    assert props, "LLM-shaped Must-do must still yield craft chips"
    assert props[0]["on_model"] == "hr.employee"
    assert props[0]["default_on"] is True
    assert any(p.get("on_model") == "res.partner" for p in props)

