"""Odoo create-gate registry — preempt backend Invalid Operation hard blocks."""

from __future__ import annotations

from app.ai_odoo_create_gates import (
    apply_odoo_create_gates,
    draft_has_unguarded_create_gates,
)


def test_pos_order_kept_with_no_create_options() -> None:
    draft = {
        "models": [
            {
                "model": "x_punch_card",
                "fields": [
                    {
                        "name": "x_last_transaction_id",
                        "ttype": "many2one",
                        "relation": "pos.order",
                    }
                ],
            }
        ],
        "views": [
            {
                "model": "x_punch_card",
                "type": "form",
                "arch": '<form><field name="x_last_transaction_id"/></form>',
            }
        ],
    }
    assert draft_has_unguarded_create_gates(draft) is True
    notes = apply_odoo_create_gates(draft)
    assert any("no_create" in n for n in notes)
    field = draft["models"][0]["fields"][0]
    assert field["options"]["no_create"] is True
    assert field["options"]["no_create_edit"] is True
    assert field.get("help")
    assert "no_create" in draft["views"][0]["arch"]
    assert draft_has_unguarded_create_gates(draft) is False


def test_pos_order_line_stripped() -> None:
    draft = {
        "models": [
            {
                "model": "x_thing",
                "fields": [
                    {
                        "name": "x_line_id",
                        "ttype": "many2one",
                        "relation": "pos.order.line",
                    },
                    {"name": "x_name", "ttype": "char"},
                ],
            }
        ],
        "views": [
            {
                "model": "x_thing",
                "arch": '<form><field name="x_line_id"/><field name="x_name"/></form>',
            }
        ],
        "reuse": {
            "catalog_suggestions": [
                {"model": "pos.order.line", "reason": "noise"},
                {"model": "res.partner", "reason": "ok"},
            ]
        },
    }
    assert draft_has_unguarded_create_gates(draft) is True
    notes = apply_odoo_create_gates(draft)
    assert any("stripped" in n for n in notes)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_line_id" not in names
    assert "x_name" in names
    assert "x_line_id" not in draft["views"][0]["arch"]
    models = {r["model"] for r in draft["reuse"]["catalog_suggestions"]}
    assert "pos.order.line" not in models
    assert "res.partner" in models
    assert draft_has_unguarded_create_gates(draft) is False
