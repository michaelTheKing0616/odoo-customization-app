"""Locked diagnosis IR — parse before App Studio generate."""

from __future__ import annotations

import pytest

from app.ai_conversation.understand import (
    append_locked_diagnosis,
    attach_understanding,
    build_understanding,
    diagnosis_clarification,
    parse_locked_diagnosis,
    understanding_contradictions,
)
from app.settings import settings

pytestmark = pytest.mark.no_app_db

CLIENT_MARKUP = (
    'The Client wants a "Mark-up" line added to every Sale they make. They purchase '
    "products on requests from their customers and the selling price is the additive "
    "value of the purchase/cost price and their own mark-up. The Markup is calculated "
    "as a percentage of every sale made in a single session/instance. The mark-up "
    "should be a range between 10% - 25% and they want to be able to choose at the "
    "time of entry into the Odoo DB which exact markup percentage (between 10% - 25%) "
    "is to be the markup for that particular sale. A Witholding Tax, on the markup is "
    "to be calculated as well. The Witholding Tax is made on the Markup portion of "
    "the total selling price only, and only for Sales, NOT Purchases."
)


@pytest.fixture(autouse=True)
def _intent_llm_off(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "off"
    yield
    settings.ai_intent_llm = "auto"


def test_markup_diagnosis_locks_sales_option_a() -> None:
    u = build_understanding(CLIENT_MARKUP)
    assert u.host_model == "sale.order"
    assert u.inherit_existing is True
    assert u.needs_module is True
    assert u.capability == "option_a_authored"
    assert u.title == "Sales markup"
    joined = " ".join(u.constraints).lower()
    assert "withholding" in joined or "markup" in joined
    card = diagnosis_clarification(u)
    assert card["kind"] == "diagnosis"
    assert card["merge_key"] == "diagnosis"
    assert card["understanding"]["host_model"] == "sale.order"
    assert any(row["id"] == "sale.order" for row in card["host_choices"])


def test_operator_can_edit_host_before_lock() -> None:
    from app.ai_conversation.understand import apply_understanding_edits

    u = build_understanding(CLIENT_MARKUP)
    edited = apply_understanding_edits(
        u,
        {
            "host_model": "purchase.order",
            "inherit_existing": True,
            "needs_module": True,
            "title": "PO markup",
            "operator_note": "This is on RFQs, not quotations",
        },
    )
    assert edited.host_model == "purchase.order"
    assert edited.title == "PO markup"
    assert edited.source == "operator"
    assert any("RFQs" in row for row in edited.constraints)
    blob = append_locked_diagnosis(CLIENT_MARKUP, edited)
    parsed = parse_locked_diagnosis(blob)
    assert parsed is not None
    assert parsed.host_model == "purchase.order"


def test_locked_block_round_trips() -> None:
    u = build_understanding(CLIENT_MARKUP)
    blob = append_locked_diagnosis(CLIENT_MARKUP, u)
    parsed = parse_locked_diagnosis(blob)
    assert parsed is not None
    assert parsed.host_model == "sale.order"
    assert parsed.needs_module is True
    assert parsed.capability == "option_a_authored"


def test_authored_seed_does_not_contradict_lock() -> None:
    from app.ai_generation_engine import maybe_seed_from_capability

    u = build_understanding(CLIENT_MARKUP)
    draft = maybe_seed_from_capability(CLIENT_MARKUP)
    assert draft is not None
    locked = append_locked_diagnosis(CLIENT_MARKUP, u)
    attach_understanding(draft, locked)
    assert draft["_understanding"]["contradictions"] == []


def test_invented_residual_contradicts_sales_inherit_lock() -> None:
    u = build_understanding(CLIENT_MARKUP)
    draft = {
        "models": [{"model": "x_markup_app", "fields": [{"name": "x_name"}]}],
        "_generation_engine": {"capability": "residual_app"},
    }
    findings = understanding_contradictions(draft, u)
    assert findings
    assert any("sale.order" in row or "invented" in row.lower() for row in findings)


def test_vendor_tin_diagnosis_is_field_pack_on_bills() -> None:
    prompt = (
        "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
        "required before Confirm. Do not add it on customer invoices."
    )
    u = build_understanding(prompt)
    assert u.host_model == "account.move"
    assert u.inherit_existing is True
    assert u.needs_module is False
    assert u.capability != "option_a_authored"

def test_s1_contacts_diagnosis_prefills_must_do() -> None:
    """Clear field-pack brief must prefill Must do (constraints) without LLM."""
    prompt = (
        "On Contacts (res.partner), add checkbox Preferred for delivery and "
        "Delivery notes text under Delivery group. Do not create a new app."
    )
    u = build_understanding(prompt)
    assert u.host_model == "res.partner"
    assert u.inherit_existing is True
    assert u.needs_module is False
    assert u.grain == "field_pack"
    joined = " | ".join(u.constraints).lower()
    assert "preferred for delivery" in joined
    assert "delivery notes" in joined
    assert "delivery group" in joined
    assert "new home-screen app" in joined or "do not create" in joined
    card = diagnosis_clarification(u)
    assert card["kind"] == "diagnosis"
    assert card["understanding"]["constraints"]
    assert any("Preferred for delivery" in row for row in card["understanding"]["constraints"])


def test_diagnosis_confirm_lock_still_requires_yes_build_this() -> None:
    from app.ai_conversation.understand import diagnosis_confirmed

    assert diagnosis_confirmed({"diagnosis": "confirm"}) is True
    assert diagnosis_confirmed({"diagnosis": "Yes — build this"}) is True
    assert diagnosis_confirmed({"diagnosis": "reject"}) is False
    assert diagnosis_confirmed({}) is False

