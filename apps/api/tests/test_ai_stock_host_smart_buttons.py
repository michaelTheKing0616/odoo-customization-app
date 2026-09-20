"""Stock-host smart-button policy — navigation from Contacts/Employees/Orders → residual."""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_document_shape import honor_operator_brief
from app.ai_stock_host_smart_buttons import (
    apply_stock_host_smart_buttons,
    draft_missing_stock_host_smart_buttons,
)

LAGOS = (
    "We already use Community POS. What we don’t have is a simple loyalty punch card: "
    "buy 9 coffees get the 10th free, tied to the customer (Contacts), cashier should see "
    "remaining punches on the POS-adjacent back office, not a fake receipt designer. "
    "Do not build x_receipt or copy GM/receipt studio. Receipts stay stock POS. "
    "One shop, Lagos, NGN. Residual is the punch card, not a new POS."
)

VISITOR = (
    "Simple office visitor log for the front desk: visitor name, company, time in, "
    "time out, employee hosting them. No CRM, no hotel PMS."
)


def test_punch_card_gets_contacts_and_pos_buttons() -> None:
    draft = {
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
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_last_transaction_id",
                        "ttype": "many2one",
                        "relation": "pos.order",
                        "options": {"no_create": True, "no_create_edit": True},
                    },
                ],
            }
        ],
        "smart_buttons": [],
        "_user_prompt": LAGOS,
        "_document_shape": "register",
    }
    assert draft_missing_stock_host_smart_buttons(draft, prompt=LAGOS) is True
    notes = apply_stock_host_smart_buttons(draft, prompt=LAGOS)
    assert any("stock_host_btn" in n for n in notes)
    hosts = {b["on_model"] for b in draft["smart_buttons"]}
    assert "res.partner" in hosts
    assert "pos.order" in hosts
    partner = next(b for b in draft["smart_buttons"] if b["on_model"] == "res.partner")
    assert partner["related_model"] == "x_punch_card"
    assert partner["relation_field"] == "x_partner_id"
    assert partner.get("requires_inherit_view") is True
    assert draft_missing_stock_host_smart_buttons(draft, prompt=LAGOS) is False


def test_visitor_log_drops_contacts_and_employee_stock_hosts() -> None:
    """Residual full_app: Host→Employee is a form M2O, never an Employees smart button."""
    draft = {
        "technical_name": "visitor_log",
        "display_name": "Visitor Log",
        "grain": "full_app",
        "depends": ["base", "mail", "hr"],
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
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
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
            },
            {
                "on_model": "hr.employee",
                "label": "Visitor Log",
                "related_model": "x_visitor_log",
                "relation_field": "x_employee_id",
            },
        ],
        "_user_prompt": VISITOR,
        "_document_shape": "register",
    }
    honor_operator_brief(draft, user_prompt=VISITOR)
    hosts = {b["on_model"] for b in (draft.get("smart_buttons") or []) if isinstance(b, dict)}
    assert "res.partner" not in hosts
    assert "hr.employee" not in hosts


def test_sale_order_m2o_gets_button_on_field_pack_not_residual() -> None:
    """Residual full_app keeps Sale Order as a form M2O — Prefer/field_pack may still invent."""
    residual = {
        "display_name": "Delivery Notes",
        "grain": "full_app",
        "models": [
            {
                "model": "x_delivery_note",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_sale_order_id",
                        "ttype": "many2one",
                        "relation": "sale.order",
                    }
                ],
            }
        ],
        "smart_buttons": [],
        "_user_prompt": "Delivery notes linked to sales orders",
    }
    apply_stock_host_smart_buttons(residual, prompt=residual["_user_prompt"])
    assert not any(b.get("on_model") == "sale.order" for b in residual["smart_buttons"])

    field_pack = {
        "display_name": "Delivery Notes on Sales",
        "grain": "field_pack",
        "models": [
            {
                "model": "sale.order",
                "mode": "inherit",
                "fields": [
                    {"name": "x_delivery_note_count", "ttype": "integer"},
                ],
            },
            {
                "model": "x_delivery_note",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_sale_order_id",
                        "ttype": "many2one",
                        "relation": "sale.order",
                    }
                ],
            },
        ],
        "smart_buttons": [],
        "_user_prompt": "Add delivery notes related to sales orders on the Sales form",
    }
    # Inherit-only primary is field_pack — not residual invent suppression.
    # With a companion x_ model, grain field_pack still allows stock-host stamp.
    apply_stock_host_smart_buttons(field_pack, prompt=field_pack["_user_prompt"])
    assert any(b.get("on_model") == "sale.order" for b in field_pack["smart_buttons"])
