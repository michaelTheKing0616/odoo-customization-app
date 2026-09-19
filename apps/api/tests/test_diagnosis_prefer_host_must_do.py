"""Diagnosis host + Must-do: Prefer-for-delivery briefs must stay on Contacts."""

from __future__ import annotations

import pytest

from app.ai_conversation.understand import build_understanding
from app.ai_grain import named_host_from_prompt, preferred_inherit_host
from app.settings import settings

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _intent_llm_off(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "off"
    yield
    settings.ai_intent_llm = "auto"


def test_delivery_notes_on_contacts_is_not_stock_picking() -> None:
    p = "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group."
    assert named_host_from_prompt(p) == "res.partner"
    assert preferred_inherit_host(p) == "res.partner"


def test_automation_only_stays_on_res_partner() -> None:
    p = (
        "On res.partner, when Preferred for delivery is checked, create a light "
        "follow-up activity. Fields already exist. Inherit-only — no new app."
    )
    u = build_understanding(p)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "stock.picking" not in joined
    assert "automation" in joined or "prefer" in joined
    assert any("reuse" in c.lower() for c in u.constraints)


def test_filter_only_hosts_contacts_not_inventory_form() -> None:
    p = (
        "Preferred for delivery already exists on Contacts. Add an optional filter "
        "on Delivery/Inventory (stock.picking) lists for preferred-delivery partners. "
        "No new app tile."
    )
    u = build_understanding(p)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "filter" in joined
    assert "smart button" not in joined
    assert any("reuse" in c.lower() for c in u.constraints)


def test_placement_stress_authors_both_fields_without_forcing_group() -> None:
    p = "Prefer for delivery checkbox and Delivery notes on Contacts. Still inherit-only, no new app."
    u = build_understanding(p)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "prefer" in joined and "delivery notes" in joined
    assert "place under" not in joined  # prompt omitted group


def test_negative_correction_rejects_submenu_keeps_contacts_delivery_filter() -> None:
    p = (
        "Contact extras for delivery preferences with a Prefer submenu. Wait — "
        "actually inherit-only on res.partner, no new app tile, Prefer for delivery "
        "+ Delivery notes under Delivery, plus transfers filter."
    )
    u = build_understanding(p)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "submenu" not in joined
    assert "prefer" in joined and "delivery notes" in joined
    assert "place under delivery" in joined
    assert "filter" in joined
    assert "smart button" not in joined
