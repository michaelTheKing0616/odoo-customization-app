"""Generate roots — Delivery Live vs Option A, Contract↔canvas identity, status≠smart buttons.

General rules (not Visitor/Restaurant one-offs).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.understand import (  # noqa: E402
    Understanding,
    brief_implies_option_a,
    build_understanding,
    diagnosis_clarification,
    reconcile_contract_with_draft,
)
from app.ai_odoo_app_bar import (  # noqa: E402
    looks_like_register,
    scrub_selection_chrome_smart_buttons,
)
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.preview_views import _selection_chrome_labels, _smart_buttons_for_model  # noqa: E402


VISITOR = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

RESTAURANT = (
    "Dining Tables for our restaurant. Name, Capacity, Status "
    "(selection: Free / Seated / Reserved / Dirty / Blocked). Simple list + form."
)

PREFER = (
    "On Contacts (res.partner), add Preferred for delivery boolean and "
    "Delivery notes. Do not create a new app."
)


def test_visitor_diagnosis_live_fields_not_option_a() -> None:
    u = build_understanding(VISITOR)
    assert u.needs_module is False
    assert u.capability == "residual_app"
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.inherit_existing is False
    card = diagnosis_clarification(u)
    assert card["understanding"]["needs_module"] is False
    assert not brief_implies_option_a(VISITOR)


def test_llm_noise_cannot_flip_residual_to_option_a() -> None:
    """Simulate LLM saying needs_module=true on a plain residual brief."""
    from app.ai_conversation import understand as und

    det = und._deterministic_understanding(VISITOR)
    assert det.needs_module is False
    # Force enrich path body: residual_full clears needs even if parsed says true
    parsed = {
        "title": "Visitor Log",
        "summary": "log visitors",
        "needs_module": True,
        "inherit_existing": False,
        "constraints": list(det.constraints),
        "out_of_scope": [],
        "confidence": "high",
    }
    # Replicate enrich merge rules via build_understanding post-force
    dirty = Understanding(
        capability="residual_app",
        grain="full_app",
        host_model=None,
        inherit_existing=False,
        needs_module=True,
        title="Visitor Log",
        summary="x",
    )
    fixed = und._force_live_fields_for_residual(dirty, VISITOR)
    assert fixed.needs_module is False


def test_option_a_brief_still_needs_module() -> None:
    brief = "Add a QWeb PDF report controller on sale.order with Python compute."
    assert brief_implies_option_a(brief) is True


def test_reconcile_wipes_visitor_contract_on_restaurant_draft() -> None:
    draft = {
        "display_name": "Dining Tables",
        "grain": "full_app",
        "models": [{"model": "x_dining_table", "mode": "new", "fields": []}],
    }
    locked = Understanding(
        capability="residual_app",
        grain="full_app",
        host_model=None,
        inherit_existing=False,
        title="Visitor Log",
        source="locked",
    )
    rebuilt = reconcile_contract_with_draft(draft, locked)
    assert rebuilt.title == "Dining Tables"
    assert rebuilt.needs_module is False


def test_restaurant_seed_uses_residual_title_not_pack_stamp() -> None:
    draft = seed_studio_draft(RESTAURANT)
    assert "Dining" in str(draft.get("display_name") or "")
    assert draft.get("display_name") != "Restaurant Management"


def test_dining_table_looks_like_register() -> None:
    assert looks_like_register("x_dining_table") is True
    assert looks_like_register("x_visitor_log") is True


def test_selection_chrome_filters_type_and_ttype_fields() -> None:
    draft = {
        "models": [
            {
                "model": "x_dining_table",
                "fields": [
                    {
                        "name": "x_status",
                        "type": "selection",  # LLM often emits type, not ttype
                        "selection": (
                            "[('free','Free'),('seated','Seated'),"
                            "('reserved','Reserved'),('dirty','Dirty'),"
                            "('blocked','Blocked')]"
                        ),
                    }
                ],
            }
        ],
        "smart_buttons": [
            {"on_model": "x_dining_table", "label": "Reserved", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Seated", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Dirty", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Blocked", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Reservations", "related_model": "x_res"},
        ],
    }
    chrome = _selection_chrome_labels(draft, "x_dining_table")
    assert "reserved" in chrome and "dirty" in chrome
    labels = {b["string"] for b in _smart_buttons_for_model(draft, "x_dining_table", arch_buttons=[])}
    assert "Reserved" not in labels
    assert "Seated" not in labels
    assert "Dirty" not in labels
    assert "Blocked" not in labels
    assert "Reservations" in labels


def test_scrub_selection_chrome_smart_buttons_ir() -> None:
    draft = {
        "models": [
            {
                "model": "x_dining_table",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('free','Free'),('seated','Seated'),"
                            "('reserved','Reserved'),('dirty','Needs cleaning'),"
                            "('blocked','Blocked')]"
                        ),
                    }
                ],
            }
        ],
        "smart_buttons": [
            {"on_model": "x_dining_table", "label": "Reserved", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Dirty", "related_model": "x_res"},
            {"on_model": "x_dining_table", "label": "Tables", "related_model": "x_res"},
        ],
    }
    notes = scrub_selection_chrome_smart_buttons(draft)
    labels = {b.get("label") for b in draft["smart_buttons"]}
    assert "Reserved" not in labels
    assert "Dirty" not in labels
    assert "Tables" in labels
    assert notes


def test_prefer_contacts_unchanged() -> None:
    u = build_understanding(PREFER)
    assert u.inherit_existing is True
    assert u.host_model == "res.partner"
    assert u.grain == "field_pack"
