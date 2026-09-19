"""Operator surface map — discoverability for menus + smart-button hosts."""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_operator_surface import attach_operator_surface, build_operator_surface


def _punch_draft() -> dict:
    return {
        "technical_name": "punch_card",
        "display_name": "Punch Card",
        "depends": ["base", "mail", "contacts", "point_of_sale"],
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_last_transaction_id",
                        "ttype": "many2one",
                        "string": "Last Transaction",
                        "relation": "pos.order",
                    },
                    {"name": "x_punches", "ttype": "integer", "string": "Punches"},
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Punch Cards",
                "related_model": "x_punch_card",
                "relation_field": "x_partner_id",
            },
            {
                "on_model": "pos.order",
                "label": "Punch Cards",
                "related_model": "x_punch_card",
                "relation_field": "x_last_transaction_id",
            },
        ],
        "menus": [
            {
                "name": "Punch Card",
                "technical_name": "root_punch_card",
                "xml_id": "menu_root_punch_card",
            },
            {
                "name": "Punch Cards",
                "action_xml_id": "action_x_punch_card",
                "parent_xml_id": "menu_root_punch_card",
            },
        ],
        "_user_prompt": (
            "loyalty punch card tied to the customer (Contacts), "
            "cashier sees punches on the POS-adjacent back office"
        ),
    }


def test_punch_card_host_buttons_and_stock_links() -> None:
    surface = build_operator_surface(_punch_draft())
    hosts = {b["host_model"] for b in surface["host_buttons"]}
    assert "res.partner" in hosts
    assert "pos.order" in hosts
    partner = next(b for b in surface["host_buttons"] if b["host_model"] == "res.partner")
    assert partner["host_label"] == "Contacts"
    assert partner["button_label"] == "Punch Cards"
    links = {row["stock_model"]: row["field_label"] for row in surface["stock_links"]}
    assert links.get("res.partner") == "Customer"
    assert links.get("pos.order") == "Last Transaction"
    assert surface["app_menu"] and surface["app_menu"]["label"] == "Punch Card"
    assert "Contacts" in surface["summary"] or "stock forms" in surface["summary"]


def test_attach_operator_surface_stamps_draft() -> None:
    draft = _punch_draft()
    notes = attach_operator_surface(draft)
    assert any("operator_surface" in n for n in notes)
    assert draft["_operator_surface"]["host_buttons"]
    assert len(draft["_operator_surface"]["host_buttons"]) == 2


def test_residual_custom_button_listed_separately() -> None:
    draft = _punch_draft()
    draft["models"].append(
        {
            "model": "x_punch_visit",
            "mode": "new",
            "fields": [
                {
                    "name": "x_punch_card_id",
                    "ttype": "many2one",
                    "relation": "x_punch_card",
                }
            ],
        }
    )
    draft["smart_buttons"].append(
        {
            "on_model": "x_punch_card",
            "label": "Visits",
            "related_model": "x_punch_visit",
            "relation_field": "x_punch_card_id",
        }
    )
    surface = build_operator_surface(draft)
    assert any(b["button_label"] == "Visits" for b in surface["residual_buttons"])
    assert all(b["host_model"] != "x_punch_card" for b in surface["host_buttons"])


def test_option_a_inherit_is_not_residual_app_fallback() -> None:
    surface = build_operator_surface(
        {
            "display_name": "Sales markup",
            "technical_name": "sales_markup",
            "_capability_primary_option_a": True,
            "_generation_engine": {
                "capability": "option_a_authored",
                "host_model": "sale.order",
            },
            "models": [{"model": "sale.order", "mode": "inherit", "fields": []}],
            "menus": [],
            "smart_buttons": [],
        }
    )
    assert "residual app" not in surface["summary"]
    assert "sale.order" in surface["summary"]
    assert "Option A module" in surface["summary"]


def test_residual_full_app_find_it_no_contacts_invent() -> None:
    """Restaurant / Visitor residual: app menu only — no «App» ×N on Contacts."""
    from app.ai_rules import apply_pattern_rules
    from app.ai_operator_surface import build_operator_surface, attach_operator_surface
    import copy
    from app.ai_domain_pack_restaurant import restaurant_pack

    draft = copy.deepcopy(restaurant_pack())
    draft["grain"] = "full_app"
    draft["_user_prompt"] = (
        "Build Restaurant Management app with tables, reservations, guests as Contacts"
    )
    apply_pattern_rules(draft)
    # Even if rules / pack left partner buttons, find-it must not invent host Contacts.
    draft.setdefault("smart_buttons", []).append(
        {
            "on_model": "res.partner",
            "label": "Restaurant Management",
            "related_model": "x_reservation",
            "relation_field": "x_partner_id",
        }
    )
    draft.setdefault("smart_buttons", []).append(
        {
            "on_model": "res.partner",
            "label": "Restaurant Management",
            "related_model": "x_order",
            "relation_field": "x_partner_id",
        }
    )
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    assert not any(b["host_model"] == "res.partner" for b in surface["host_buttons"])
    summary = surface["summary"]
    assert summary.count("Restaurant Management") <= 1 or "Contacts" not in summary
    assert "on Contacts" not in summary


def test_prefer_contacts_inherit_still_hosts() -> None:
    surface = build_operator_surface(
        {
            "display_name": "Contacts field",
            "technical_name": "contacts_field",
            "grain": "field_pack",
            "_generation_engine": {"grain": "field_pack", "host_model": "res.partner"},
            "models": [{"model": "res.partner", "mode": "inherit", "fields": []}],
            "menus": [],
            "smart_buttons": [],
            "_user_prompt": "Prefer Contacts — add loyalty note on the contact form",
        }
    )
    assert "residual app" not in surface["summary"].lower() or "Contacts" in surface["summary"]


def test_visitor_log_residual_clean_find_it() -> None:
    draft = {
        "display_name": "Visitor Log",
        "technical_name": "visitor_log",
        "grain": "full_app",
        "_user_prompt": "Visitor Log: Name, Company, Host (Employee). Simple list + form.",
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Visitor Log",
                "related_model": "x_visitor_log",
                "relation_field": "x_partner_id",
            }
        ],
        "menus": [
            {"name": "Visitor Log", "xml_id": "menu_root_visitor_log"},
        ],
    }
    surface = build_operator_surface(draft)
    assert all(b["host_model"] != "res.partner" for b in surface["host_buttons"])
    assert surface["app_menu"] and surface["app_menu"]["label"] == "Visitor Log"
