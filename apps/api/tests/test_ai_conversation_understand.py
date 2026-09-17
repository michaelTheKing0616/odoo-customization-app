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



S1_CONTACTS = (
    "On Contacts (res.partner), add checkbox Preferred for delivery and "
    "Delivery notes text under Delivery group. Do not create a new app."
)

MEDIUM_MULTI = (
    "On Sales Orders, add a Priority dropdown (Low/Normal/High), a boolean "
    "Needs follow-up, and a Follow-up notes text field under the Other Info "
    "tab. When Needs follow-up is checked, Follow-up notes is required before "
    "Confirm. Do not create a new home-screen app."
)

FULL_APP = (
    "Build a neighborhood clinic app: patients with name and phone, walk-in "
    "appointments with status draft → confirmed → done, and a simple list + form. "
    "New home-screen app is fine."
)


def test_score_must_do_empty_on_clear_brief_fails() -> None:
    from app.ai_conversation.understand import score_must_do_constraints

    scored = score_must_do_constraints(
        S1_CONTACTS,
        [],
        host="res.partner",
        inherit=True,
    )
    assert scored["pass"] is False
    assert scored["score"] == 0.0
    assert any("empty" in r.lower() for r in scored["reasons"])


def test_score_must_do_s1_det_passes() -> None:
    from app.ai_conversation.understand import score_must_do_constraints

    rows = [
        "On Contacts (res.partner)",
        "Checkbox: Preferred for delivery",
        "Text field: Delivery notes",
        "Place under Delivery group",
        "Do not create a new home-screen app",
    ]
    scored = score_must_do_constraints(
        S1_CONTACTS, rows, host="res.partner", inherit=True
    )
    assert scored["pass"] is True
    assert scored["score"] >= 0.65


def test_score_must_do_host_steal_delivery_notes_not_picking() -> None:
    """Delivery notes on Contacts must not claim stock.picking as host."""
    from app.ai_conversation.understand import score_must_do_constraints

    stolen = [
        "On Inventory (stock.picking)",
        "Text field: Delivery notes",
        "Do not create a new home-screen app",
    ]
    scored = score_must_do_constraints(
        S1_CONTACTS, stolen, host="res.partner", inherit=True
    )
    assert scored["pass"] is False
    assert any("host-steal" in r.lower() for r in scored["reasons"])


def test_score_must_do_forbidden_account_tax() -> None:
    from app.ai_conversation.understand import score_must_do_constraints

    rows = [
        "On Sales (sale.order)",
        "Create account.tax for WHT",
        "Markup 10-25%",
    ]
    scored = score_must_do_constraints(
        CLIENT_MARKUP, rows, host="sale.order", inherit=True, needs_module=True
    )
    assert scored["pass"] is False
    assert any("forbidden" in r.lower() for r in scored["reasons"])


def test_host_steal_regression_preferred_inherit_host() -> None:
    from app.ai_grain import preferred_inherit_host

    assert preferred_inherit_host(S1_CONTACTS) == "res.partner"


def test_llm_enrich_runs_even_when_confidence_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM-first: do not skip enrich just because confidence=high and host present."""
    from app.llm_provider import MockLLMProvider

    settings.ai_intent_llm = "on"
    calls: list[str] = []

    class Tracking(MockLLMProvider):
        def generate_json(self, prompt: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(prompt)
            return (
                '{"title":"Contacts delivery fields","summary":"Fields on Contacts.",'
                '"host_model":"res.partner","inherit_existing":true,"needs_module":false,'
                '"constraints":['
                '"On Contacts (res.partner)",'
                '"Checkbox: Preferred for delivery",'
                '"Text field: Delivery notes",'
                '"Place under Delivery group",'
                '"Do not create a new home-screen app"'
                '],"out_of_scope":["new home-screen app"],"confidence":"high"}'
            )

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": Tracking(),
    )
    u = build_understanding(S1_CONTACTS)
    assert calls, "LLM enrich must run for high-confidence S1"
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "preferred for delivery" in joined
    assert "delivery notes" in joined
    assert "stock.picking" not in joined
    stamp = u.to_dict().get("_must_do_score")
    assert isinstance(stamp, dict)
    assert stamp["pass"] is True


def test_llm_must_do_medium_multi_req(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm_provider import MockLLMProvider

    settings.ai_intent_llm = "on"
    payload = (
        '{"title":"Sales follow-up fields","summary":"Priority and follow-up on SO.",'
        '"host_model":"sale.order","inherit_existing":true,"needs_module":false,'
        '"constraints":['
        '"On Sales Orders (sale.order)",'
        '"Dropdown: Priority (Low/Normal/High)",'
        '"Boolean: Needs follow-up",'
        '"Text field: Follow-up notes",'
        '"Place under Other Info tab",'
        '"When Needs follow-up is checked, Follow-up notes required before Confirm",'
        '"Do not create a new home-screen app"'
        '],"out_of_scope":["new home-screen app"],"confidence":"high"}'
    )
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(json_response=payload),
    )
    u = build_understanding(MEDIUM_MULTI)
    joined = " | ".join(u.constraints).lower()
    assert "priority" in joined
    assert "follow-up" in joined or "follow up" in joined
    assert "confirm" in joined
    assert u.host_model == "sale.order"
    assert u.to_dict()["_must_do_score"]["pass"] is True


def test_llm_must_do_full_app_infers_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm_provider import MockLLMProvider

    settings.ai_intent_llm = "on"
    payload = (
        '{"title":"Clinic walk-ins","summary":"Patients and appointments app.",'
        '"host_model":"","inherit_existing":false,"needs_module":false,'
        '"constraints":['
        '"New home-screen clinic app",'
        '"Model: patients with name and phone",'
        '"Model: walk-in appointments",'
        '"Appointment status workflow: draft → confirmed → done",'
        '"List + form views for patients and appointments"'
        '],"out_of_scope":["Option A Python module"],"confidence":"high"}'
    )
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(json_response=payload),
    )
    u = build_understanding(FULL_APP)
    joined = " | ".join(u.constraints).lower()
    assert "patient" in joined
    assert "draft" in joined and "done" in joined
    assert u.inherit_existing is False or "new" in joined


def test_llm_weak_must_do_repairs_then_merges_det(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Low score → one repair retry → merge best of det+LLM."""
    settings.ai_intent_llm = "on"
    # Empty det seed so weak LLM cannot hide behind deterministic backstop.
    monkeypatch.setattr(
        "app.ai_conversation.understand._brief_must_do_constraints",
        lambda *a, **k: [],
    )
    weak = (
        '{"title":"Contacts","summary":"Stuff.","host_model":"res.partner",'
        '"inherit_existing":true,"constraints":["ok"],"out_of_scope":[],'
        '"confidence":"high"}'
    )
    strong = (
        '{"title":"Contacts delivery","summary":"Fields on Contacts.",'
        '"host_model":"res.partner","inherit_existing":true,"needs_module":false,'
        '"constraints":['
        '"On Contacts (res.partner)",'
        '"Checkbox: Preferred for delivery",'
        '"Text field: Delivery notes",'
        '"Place under Delivery group",'
        '"Do not create a new home-screen app"'
        '],"out_of_scope":["new home-screen app"],"confidence":"high"}'
    )
    responses = [weak, strong]
    calls: list[str] = []

    class Seq:
        name = "mock"

        def generate_json(self, prompt: str, **kwargs):  # type: ignore[no-untyped-def]
            _ = kwargs
            calls.append(prompt)
            if not responses:
                return strong
            return responses.pop(0)

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": Seq(),
    )
    u = build_understanding(S1_CONTACTS)
    assert len(calls) >= 2, f"expected repair retry, got {len(calls)} calls"
    assert any("REPAIR PASS" in c for c in calls)
    joined = " | ".join(u.constraints).lower()
    assert "preferred for delivery" in joined
    assert "delivery notes" in joined
    assert u.to_dict()["_must_do_score"]["pass"] is True


def test_llm_host_steal_output_downgrades_to_det(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM claiming stock.picking for Contacts brief must lose to det seed."""
    from app.llm_provider import MockLLMProvider

    settings.ai_intent_llm = "on"
    stolen = (
        '{"title":"Delivery","summary":"On pickings.",'
        '"host_model":"stock.picking","inherit_existing":true,'
        '"constraints":['
        '"On Inventory (stock.picking)",'
        '"Text field: Delivery notes"'
        '],"out_of_scope":[],"confidence":"high"}'
    )
    # Same stolen payload on repair — det should win by score
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(json_response=stolen),
    )
    u = build_understanding(S1_CONTACTS)
    # Host stays deterministic (LLM cannot override allowlisted host)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "stock.picking" not in joined
    assert "preferred for delivery" in joined or "contacts" in joined


def test_must_do_score_stamped_when_llm_off() -> None:
    u = build_understanding(S1_CONTACTS)
    stamp = u.to_dict().get("_must_do_score")
    assert isinstance(stamp, dict)
    assert "score" in stamp
    assert stamp["pass"] is True


def test_operator_edits_still_override_must_do() -> None:
    from app.ai_conversation.understand import apply_understanding_edits

    u = build_understanding(S1_CONTACTS)
    edited = apply_understanding_edits(
        u,
        {"constraints": ["On Contacts only", "Checkbox: VIP delivery"]},
    )
    assert edited.constraints == ["On Contacts only", "Checkbox: VIP delivery"]
    assert edited.source == "operator"
