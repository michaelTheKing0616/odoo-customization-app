"""T1-C1 / PR-C — approved_craft checklist defaults off; toggle changes emitted views."""

from __future__ import annotations

from app.ai_conversation.understand import (
    APPROVED_CRAFT_KEYS,
    Understanding,
    coerce_approved_craft,
    default_approved_craft,
)
from app.ai_depth import _ensure_currency_on_amounts
from app.ai_enrich import _build_form_arch, _field_list
from app.ai_generate_ir import build_ir, stamp_generate_ir
from app.module_spec_codec import draft_dict_to_module_spec
from module_generator import render_module_files


def test_default_approved_craft_checklist_all_off() -> None:
    """API: every known craft row defaults False; empty input normalizes to all-off."""
    expected = {key: False for key in APPROVED_CRAFT_KEYS}
    assert default_approved_craft() == expected
    assert coerce_approved_craft(None) == expected
    assert coerce_approved_craft({}) == expected
    assert not any(coerce_approved_craft({}).values())
    assert not any(Understanding(title="Demo", grain="full_app").approved_craft.values())


def test_build_ir_leaves_craft_empty_when_draft_omits_approved_craft() -> None:
    draft = {
        "display_name": "Maintenance Tickets",
        "models": [{"model": "x_ticket", "mode": "new", "fields": [{"name": "x_name", "ttype": "char"}]}],
    }
    ir = build_ir(draft)
    assert ir.approved_craft == {}
    stamped = stamp_generate_ir(draft)
    assert stamped.approved_craft == {}
    assert draft["_generate_ir"]["approved_craft"] == {}


def _maintenance_amount_draft(*, money_slots: bool) -> dict:
    draft = {
        "technical_name": "maint_craft_demo",
        "display_name": "Maintenance Tickets",
        "_user_prompt": "Build Maintenance tickets: checklist and parts, Draft→Done",
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "description": "Ticket",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                ],
            }
        ],
    }
    if money_slots:
        draft["_approved_craft"] = {"money_slots": True}
    return draft


def _render_form_views_xml(draft: dict) -> str:
    _ensure_currency_on_amounts(draft)
    model = draft["models"][0]
    mid = str(model["model"])
    arch = _build_form_arch(
        str(model.get("description") or mid),
        _field_list(model),
        odoo_major=19,
        model_id=mid,
    )
    draft["views"] = [
        {
            "name": f"{mid}.form",
            "model": mid,
            "type": "form",
            "arch": arch,
            "mode": "primary",
        }
    ]
    spec = draft_dict_to_module_spec(draft)
    files = render_module_files(spec)
    return files[f"{draft['technical_name']}/views/views.xml"]


def test_generate_with_no_craft_rows_omits_currency_from_views_xml() -> None:
    """Negative: default-off craft must not admit x_currency_id into generated view XML."""
    draft = _maintenance_amount_draft(money_slots=False)
    xml = _render_form_views_xml(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_currency_id" not in names
    assert "x_currency_id" not in xml


def test_money_slots_toggle_adds_currency_to_views_xml() -> None:
    """Toggle one craft row (money_slots) changes generated views.xml."""
    off_xml = _render_form_views_xml(_maintenance_amount_draft(money_slots=False))
    on_draft = _maintenance_amount_draft(money_slots=True)
    on_xml = _render_form_views_xml(on_draft)
    assert "x_currency_id" not in off_xml
    assert "x_currency_id" in on_xml
    assert on_xml != off_xml
