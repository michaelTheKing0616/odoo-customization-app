"""Residual full_app Generate IR — Visitor Log + Restaurant; Prefer Contacts unchanged."""

from __future__ import annotations

import copy

import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_document_shape import honor_operator_brief, naming_from_residual
from app.ai_operator_surface import build_operator_surface
from app.ai_rules import apply_pattern_rules
from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons
from app.preview_views import build_form_preview, residual_form_preview

VISITOR_PROMPT = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose, Host (Employee). Simple list + form, menu under Services."
)

RESTAURANT_PROMPT = (
    "Build Restaurant Management with dining tables and reservations. "
    "Customer (link to Contact) on reservations. Simple list + form."
)


def _visitor_draft() -> dict:
    return {
        "display_name": "Tiny Visitor Log App: Model",
        "technical_name": "tiny_visitor_log_app_model",
        "grain": "full_app",
        "_user_prompt": VISITOR_PROMPT,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "description": "Visitor Log",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Company",
                    },
                    {"name": "x_visit_date", "ttype": "date", "string": "Visit date"},
                    {"name": "x_purpose", "ttype": "char", "string": "Purpose"},
                    {
                        "name": "x_host_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                        "string": "Host",
                    },
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "hr.employee",
                "label": "Tiny Visitor Log App Models",
                "related_model": "x_visitor_log",
                "relation_field": "x_host_id",
            }
        ],
        "views": [
            {
                "model": "x_visitor_log",
                "type": "form",
                "arch": (
                    '<form string="Visitor Log">'
                    "<sheet>"
                    '<group name="identity" string="IDENTITY"></group>'
                    "</sheet>"
                    "</form>"
                ),
            }
        ],
        "menus": [{"name": "Tiny Visitor Log App Models", "xml_id": "menu_root_visitor"}],
    }


def test_naming_from_residual_visitor_log_not_tiny_app_model() -> None:
    display, slug = naming_from_residual(VISITOR_PROMPT)
    assert display == "Visitor Log"
    assert slug == "visitor_log"
    assert "Tiny" not in display
    assert "Model" not in display


def test_visitor_generate_ir_no_employees_host_button() -> None:
    draft = _visitor_draft()
    display, slug = naming_from_residual(VISITOR_PROMPT)
    draft["display_name"] = display
    draft["technical_name"] = slug
    apply_stock_host_smart_buttons(draft, prompt=VISITOR_PROMPT)
    apply_pattern_rules(draft)
    honor_operator_brief(draft, user_prompt=VISITOR_PROMPT)
    hosts = {
        str(b.get("on_model") or "")
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    assert "hr.employee" not in hosts
    assert "res.partner" not in hosts
    assert "calendar.event" not in hosts
    assert draft["display_name"] == "Visitor Log"


def test_visitor_form_preview_binds_must_do_fields() -> None:
    draft = _visitor_draft()
    draft["display_name"] = "Visitor Log"
    form = build_form_preview(draft)
    assert form is not None
    names = {
        f.get("name")
        for g in (form.get("groups") or [])
        for f in (g.get("fields") or [])
    }
    for required in ("x_name", "x_company_id", "x_visit_date", "x_purpose", "x_host_id"):
        assert required in names
    residual = residual_form_preview(draft)
    assert residual is not None
    rnames = {
        f.get("name")
        for g in (residual.get("groups") or [])
        for f in (g.get("fields") or [])
    }
    assert "x_visit_date" in rnames


def test_visitor_find_it_has_no_employees_host_chip() -> None:
    draft = _visitor_draft()
    draft["display_name"] = "Visitor Log"
    draft["menus"] = [{"name": "Visitor Log", "xml_id": "menu_root_visitor"}]
    apply_stock_host_smart_buttons(draft, prompt=VISITOR_PROMPT)
    surface = build_operator_surface(draft)
    assert surface["app_menu"] and surface["app_menu"]["label"] == "Visitor Log"
    assert surface["host_buttons"] == []
    stock = {s.get("stock_model") for s in surface.get("stock_links") or []}
    assert "hr.employee" in stock or "res.partner" in stock
    # Find-it may mention Employees as a linked field label — never as a host smart button.
    assert surface["host_buttons"] == []
    assert "on Employees" not in surface["summary"]
    assert "on Contacts" not in surface["summary"]


def test_restaurant_residual_no_contacts_host_invent() -> None:
    draft = {
        "display_name": "Restaurant Management",
        "grain": "full_app",
        "_user_prompt": RESTAURANT_PROMPT,
        "models": [
            {
                "model": "x_dining_table",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_reservation",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Restaurant Management",
                "related_model": "x_reservation",
                "relation_field": "x_partner_id",
            }
        ],
        "menus": [{"name": "Restaurant Management", "xml_id": "menu_root_restaurant"}],
    }
    apply_stock_host_smart_buttons(draft, prompt=RESTAURANT_PROMPT)
    apply_pattern_rules(draft)
    hosts = {
        str(b.get("on_model") or "")
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    assert "res.partner" not in hosts
    surface = build_operator_surface(draft)
    assert surface["host_buttons"] == []


def test_prefer_contacts_inherit_keeps_host_path() -> None:
    """Prefer Contacts inherit (field_pack) is unchanged — not residual invent."""
    draft = {
        "display_name": "Delivery Preferences",
        "grain": "field_pack",
        "_user_prompt": (
            "On Contacts (res.partner), add Preferred for delivery checkbox "
            "and Delivery notes. Do not create a new app."
        ),
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": "x_preferred_delivery", "ttype": "boolean"},
                    {"name": "x_delivery_notes", "ttype": "text"},
                ],
            }
        ],
        "smart_buttons": [],
    }
    # field_pack is not residual full_app — scrub must not wipe Prefer inherit drafts
    apply_stock_host_smart_buttons(draft, prompt=draft["_user_prompt"])
    assert draft["models"][0]["mode"] == "inherit"
    assert draft["models"][0]["model"] == "res.partner"
