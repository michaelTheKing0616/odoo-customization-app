"""Inherit-only ops field_pack must author Delivery placement + workflow surfaces."""

from __future__ import annotations

from app.ai_component_builder import draft_component_from_prompt
from app.ai_form_slots import named_group_title
from app.ai_grain import classify_grain, is_inherit_only_ops

OPS = (
    "Prefer for delivery + Delivery notes on res.partner already persist. "
    "Extend so they matter in workflows: surface preferred-delivery Contacts on "
    "pickings/transfers (domain or smart button), optional filter on Delivery/Inventory "
    "lists, and/or a light automation when the box is checked. Still inherit-only — "
    "no new app tile."
)

S1 = (
    "On Contacts, add checkbox Preferred for delivery and Delivery notes text under "
    "Delivery group. Do not create a new app."
)


def test_ops_brief_is_field_pack_inherit_only() -> None:
    assert is_inherit_only_ops(OPS) is True
    assert classify_grain(OPS) == "field_pack"


def test_ops_places_fields_under_delivery_group() -> None:
    assert named_group_title(OPS) == "Delivery"
    draft, _hosts, _warn = draft_component_from_prompt(OPS, grain="field_pack")
    slots = draft.get("_form_slots") or {}
    assert slots.get("group_title") == "Delivery"
    assert slots.get("fields", {}).get("x_preferred_for_delivery") == "new_tab"
    assert slots.get("fields", {}).get("x_delivery_notes") == "new_tab"
    arch = next(
        (
            str(v.get("arch") or "")
            for v in (draft.get("views") or [])
            if isinstance(v, dict)
            and str(v.get("model")) == "res.partner"
            and str(v.get("type") or "form") == "form"
        ),
        "",
    )
    assert 'string="Delivery"' in arch
    assert "other_info" not in arch
    assert "internal_notes" not in arch


def test_ops_authors_picking_filter_smart_button_and_automation() -> None:
    draft, _hosts, _warn = draft_component_from_prompt(OPS, grain="field_pack")
    search = [
        v
        for v in (draft.get("views") or [])
        if isinstance(v, dict)
        and str(v.get("model")) == "stock.picking"
        and str(v.get("type")) == "search"
    ]
    assert search, "expected stock.picking search filter view"
    arch = str(search[0].get("arch") or "")
    assert "Preferred delivery contact" in arch
    assert "partner_id.x_preferred_for_delivery" in arch

    buttons = draft.get("smart_buttons") or []
    assert any(
        isinstance(b, dict)
        and b.get("on_model") == "res.partner"
        and b.get("related_model") == "stock.picking"
        for b in buttons
    ), buttons

    autos = draft.get("automations") or []
    assert any(
        isinstance(a, dict)
        and a.get("model") == "res.partner"
        and "x_preferred_for_delivery" in str(a.get("filter_domain") or "")
        for a in autos
    ), autos


def test_s1_stays_delivery_without_ops_surfaces() -> None:
    assert named_group_title(S1) == "Delivery"
    draft, _hosts, _warn = draft_component_from_prompt(S1, grain="field_pack")
    slots = draft.get("_form_slots") or {}
    assert slots.get("group_title") == "Delivery"
    assert not (draft.get("smart_buttons") or [])
    assert not (draft.get("automations") or [])
    assert not any(
        isinstance(v, dict) and str(v.get("model")) == "stock.picking"
        for v in (draft.get("views") or [])
    )
