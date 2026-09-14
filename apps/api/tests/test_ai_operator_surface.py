"""Operator surface map — discoverability for menus + smart-button hosts."""

from __future__ import annotations

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
