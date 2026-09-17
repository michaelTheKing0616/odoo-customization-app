"""Studio Contract Compiler — model-agnostic flagship spine."""

from __future__ import annotations

from app.ai_component_builder import draft_component_from_prompt
from app.ai_draft_scorecard import attach_scorecard
from app.ai_studio_contract import (
    SURFACE_ON_WRITE,
    SURFACE_PICKING_FILTER,
    SURFACE_TRANSFERS_BUTTON,
    build_studio_contract,
    contract_diff,
    evaluate_studio_contract,
)

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


def test_ops_contract_lists_surfaces_and_delivery_placement() -> None:
    contract = build_studio_contract(OPS)
    assert contract["inherit_only"] is True
    assert contract["grain"] == "field_pack"
    assert contract["placement_group"] == "Delivery"
    assert SURFACE_PICKING_FILTER in contract["surfaces"]
    assert SURFACE_TRANSFERS_BUTTON in contract["surfaces"]
    assert SURFACE_ON_WRITE in contract["surfaces"]
    assert "no new app" in contract["summary"].lower() or "inherit-only" in contract["summary"].lower()


def test_s1_contract_has_delivery_without_ops_surfaces() -> None:
    contract = build_studio_contract(S1)
    assert contract["placement_group"] == "Delivery"
    assert contract["surfaces"] == []


def test_ops_draft_passes_contract_scorecard_on_flash_path() -> None:
    """Correctness must not require a premium model — finishers + scorecard suffice."""
    draft, _hosts, _warn = draft_component_from_prompt(OPS, grain="field_pack")
    attach_scorecard(draft, user_prompt=OPS)
    assert isinstance(draft.get("_studio_contract"), dict)
    score = draft.get("_contract_scorecard") or evaluate_studio_contract(draft)
    assert score["pass"] is True, score
    assert (draft.get("_form_slots") or {}).get("group_title") == "Delivery"
    assert draft.get("smart_buttons")
    assert draft.get("automations")
    assert any(
        isinstance(v, dict)
        and v.get("model") == "stock.picking"
        and v.get("type") == "search"
        for v in (draft.get("views") or [])
    )


def test_s1_draft_stays_clean_without_ops_surfaces() -> None:
    draft, _hosts, _warn = draft_component_from_prompt(S1, grain="field_pack")
    score = draft.get("_contract_scorecard") or evaluate_studio_contract(draft)
    assert score["pass"] is True, score
    assert not (draft.get("smart_buttons") or [])
    assert not (draft.get("automations") or [])
    assert (draft.get("_form_slots") or {}).get("group_title") == "Delivery"


def test_contract_diff_reports_surface_changes() -> None:
    a = build_studio_contract(S1)
    b = build_studio_contract(OPS)
    lines = contract_diff(a, b)
    assert any("Surface" in line or "surface" in line.lower() or "→" in line for line in lines)
