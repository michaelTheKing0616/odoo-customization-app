"""Studio Contract Compiler — model-agnostic flagship spine."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_app_db

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


def test_residual_full_app_contract_no_stock_host() -> None:
    """Dining Tables / Restaurant must not stamp calendar.event «field pack»."""
    from app.ai_grain import classify_grain
    from app.ai_studio_contract import build_studio_contract

    dining = (
        "Dining Tables for our restaurant. Name, Capacity, Status (selection: Free / Seated / Reserved). "
        "Reservations with guest and party size on the calendar. List + form, new menu."
    )
    g = classify_grain(dining)
    assert g == "full_app"
    c = build_studio_contract(dining, grain=g)
    assert c["grain"] == "full_app"
    assert c.get("host_model") in (None, "")
    assert c.get("inherit_only") is False
    assert "field pack" not in (c.get("title") or "").lower()
    assert "calendar" not in (c.get("title") or "").lower()
    assert "dining" in (c.get("title") or "").lower()


def test_prefer_contract_still_contacts_field_pack() -> None:
    from app.ai_grain import classify_grain
    from app.ai_studio_contract import build_studio_contract

    pref = (
        "On Contacts, add checkbox Preferred for delivery and Delivery notes "
        "under Delivery group. Do not create a new app."
    )
    c = build_studio_contract(pref, grain=classify_grain(pref))
    assert c["grain"] == "field_pack"
    assert c["host_model"] == "res.partner"
    assert c.get("inherit_only") is True


def test_attach_ignores_stolen_calendar_inherit_on_full_app() -> None:
    """Draft may still carry calendar.event inherit from alias noise — Contract must not."""
    from app.ai_studio_contract import attach_studio_contract

    prompt = (
        "Build a Restaurant Management app with Dining Tables. "
        "Reservations with guest and party size on the calendar. Create/read only."
    )
    draft = {
        "grain": "full_app",
        "display_name": "Restaurant Management",
        "models": [
            {"model": "x_dining_table", "mode": "new", "fields": []},
            {"model": "calendar.event", "mode": "inherit", "fields": []},
        ],
    }
    contract = attach_studio_contract(draft, prompt)
    assert contract.get("grain") == "full_app"
    assert contract.get("host_model") in (None, "")
    assert "field pack" not in (contract.get("title") or "").lower()
    assert "calendar" not in (contract.get("title") or "").lower()
    assert "restaurant" in (contract.get("title") or "").lower() or "dining" in (
        contract.get("title") or ""
    ).lower()
    assert draft["_studio_contract"].get("host_model") in (None, "")
