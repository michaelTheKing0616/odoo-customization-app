"""Operator brief IR — structure any prompt without inventing facts."""

from __future__ import annotations

from app.ai_capability_gaps import assess_capability_gaps
from app.ai_domain_packs import match_domain_pack
from app.ai_operator_brief import build_operator_brief, prompt_for_generators
from app.ai_pipeline import seed_studio_draft
from app.job_autopilot.planner import build_job_packet


GM_STYLE = """
GM Pos Receipt Configurator
Description
Design your Point of Sale receipt visually: font sizes, showable fields, separators,
spacing, paper width and a real-time preview.

The standard Odoo POS receipt only lets you add a plain-text header and footer.

Let the cashier choose which design to print right before printing. Everything is
configured per pos.config.

Ready-made designs for 58 mm and 80 mm and an optional custom QR code on the receipt.

Benefits
Adapt the receipt to each business type: bar, restaurant, retail or market.
"""

MESSY_ONE_LINER = "pos receipt designer with live preview and 80 mm paper please"


def test_gm_style_paste_is_option_a_not_restaurant_pack() -> None:
    brief = build_operator_brief(GM_STYLE)
    assert brief.capability_path == "option_a"
    assert "point_of_sale" in brief.stock_reuse
    assert "cashier" in brief.actors
    assert "country" in brief.unknowns
    assert "currency" in brief.unknowns
    assert "company name" in brief.unknowns
    assert "restaurant" not in (brief.industry or "").lower()
    assert brief.custom_residual.lower().startswith("none")
    assert "invent" in brief.custom_residual.lower()
    gaps = assess_capability_gaps(GM_STYLE)
    assert any(g.id == "pos_receipt_designer" for g in gaps.gaps)
    assert gaps.primary_option_a is True
    assert match_domain_pack(GM_STYLE) is None


def test_messy_and_structured_share_stated_slots_only() -> None:
    messy = build_operator_brief(MESSY_ONE_LINER)
    structured = build_operator_brief(
        "# Operator brief\n"
        "Goal: POS receipt designer with live preview.\n"
        "Paper: 80 mm.\n"
    )
    assert messy.capability_path == structured.capability_path == "option_a"
    assert "point_of_sale" in messy.stock_reuse
    assert "point_of_sale" in structured.stock_reuse
    assert "country" in messy.unknowns
    assert "country" in structured.unknowns
    assert messy.formatted.startswith("# Operator brief")


def test_stated_facts_are_kept_and_not_padded() -> None:
    text = (
        "Adeyemi, Okonkwo & Partners law firm. Domain is Law Firm / Legal Practice. "
        "Custom residual is the matter file. Multi-company is not required. "
        "We invoice in naira in Nigeria."
    )
    brief = build_operator_brief(text)
    assert "law firm" in brief.industry.lower()
    assert "matter file" in brief.custom_residual.lower()
    assert "country" not in brief.unknowns
    assert "currency" not in brief.unknowns
    assert brief.capability_path != "option_a"
    assert "naira" in text.lower()


def test_negation_does_not_become_scope() -> None:
    brief = build_operator_brief(
        "Recording studio, not a restaurant. Custom residual is the booking."
    )
    assert any("restaurant" in x.lower() for x in brief.out_of_scope)
    assert "booking" in brief.custom_residual.lower()
    assert "restaurant" not in brief.custom_residual.lower()


def test_visitor_log_honesty_ir() -> None:
    from tests.test_ai_pack_disambiguation import VISITOR_LOG_PROMPT

    brief = build_operator_brief(VISITOR_LOG_PROMPT)
    assert "crm" in [x.lower() for x in brief.out_of_scope]
    assert any("contact" in x.lower() for x in brief.out_of_scope)
    assert not any("and not" in x.lower() for x in brief.out_of_scope)
    assert "visitor log" in brief.custom_residual.lower()
    assert "country" not in brief.unknowns
    assert "account" in brief.forbidden_bridges
    assert "crm" in brief.forbidden_bridges
    assert brief.country == "Ghana"
    assert "account" not in brief.stock_reuse
    assert "crm" not in brief.stock_reuse
    assert "hr" in brief.stock_reuse
    assert brief.capability_path == "residual_app"
    blob = prompt_for_generators(VISITOR_LOG_PROMPT)
    assert "Forbidden stock bridges" in blob
    assert "account" in blob
    out = prompt_for_generators("We need a POS receipt designer")
    assert "Operator brief" in out
    assert "POS receipt designer" in out
    assert "do not invent" in out.lower()


def test_stock_first_pos_brief_is_not_option_a() -> None:
    from app.ai_operator_brief import (
        build_operator_brief,
        is_pos_receipt_prompt,
        is_explicit_stock_first,
    )

    text = (
        "# Operator brief\n## Goal\nStand up Community Point of Sale for one company.\n"
        "## Custom residual\nNone. Do not invent x_receipt.\n"
        "## Out of scope\n- Visual drag-and-drop receipt designer\n"
        "## Capability path\nstock_first (+ later Option A only if we explicitly ask for receipt OWL/QWeb)\n"
    )
    assert is_explicit_stock_first(text)
    assert is_pos_receipt_prompt(text) is False
    brief = build_operator_brief(text)
    assert brief.capability_path == "stock_first"
    assert not brief.goal.lower().startswith("# operator brief")
    gaps = assess_capability_gaps(text)
    assert gaps.primary_option_a is False
    assert gaps.gaps == []


def test_seed_studio_skips_restaurant_pack_for_receipt_prompt() -> None:
    draft = seed_studio_draft(GM_STYLE)
    assert draft.get("domain_pack") != "restaurant"
    blob = draft.get("_operator_brief") or {}
    assert blob.get("capability_path") == "option_a"
    assert draft.get("technical_name") == "pos_receipt_options"
    models = {m.get("model") for m in draft.get("models") or []}
    assert "x_receipt" not in models
    assert "pos.config" in models


def test_autopilot_packet_has_structured_brief_no_receipt_residual() -> None:
    packet = build_job_packet(GM_STYLE, use_llm=False)
    assert packet.structured_brief.startswith("# Operator brief")
    assert packet.custom_residuals == []
    assert "point_of_sale" in packet.stock_apps
    assert any("Unknowns" in w for w in packet.warnings)
    assert any("Option A" in d for d in packet.decision_record)


def test_brief_llm_contract_is_shape_agnostic_not_visitor_specific() -> None:
    from app.ai_ollama import module_spec_system_prompt
    from app.ai_operator_brief import brief_llm_contract
    from tests.test_ai_generation_engine import POS_STOCK_FIRST
    from tests.test_ai_pack_disambiguation import VISITOR_LOG_PROMPT
    from tests.test_ai_studio_seed import SLA_INVOICE_FIELD_PROMPT

    accra = brief_llm_contract(VISITOR_LOG_PROMPT)
    assert "OPERATOR BRIEF CONTRACT" in accra
    assert "Document shape: register" in accra
    assert "no x_company_id" in accra
    assert "check-in" in accra.lower()
    assert "one header" in accra.lower()
    assert "invoicing" in accra.lower() or "account" in accra.lower()

    keys = brief_llm_contract(
        "Warehouse still uses a paper book. I want a simple key log in Odoo: "
        "key name, who signed it out (an employee), purpose, time in, time out."
    )
    assert "Document shape: register" in keys
    assert "no x_company_id" in keys
    assert "x_visitor_log" not in keys
    assert "visitor" not in keys.lower()

    sla = brief_llm_contract(SLA_INVOICE_FIELD_PROMPT)
    assert "Document shape: field_pack" in sla
    assert "inherit" in sla.lower()
    assert "no new root menu" in sla.lower()

    pos = brief_llm_contract(POS_STOCK_FIRST)
    assert "Document shape: stock_reuse" in pos
    assert "models: []" in pos

    crm = brief_llm_contract("Build a simple CRM for local shops")
    assert "Document shape: workspace" in crm or "Document shape: transactional_header" in crm
    assert "one header x_*" not in crm

    sys_accra = module_spec_system_prompt(VISITOR_LOG_PROMPT)
    assert accra in sys_accra
    assert "honor the operator" in sys_accra.lower()
    assert "workspace / transactional_header only" in sys_accra


LAGOS_PUNCH_CARD = (
    "We already use Community POS. What we don’t have is a simple loyalty punch card: "
    "buy 9 coffees get the 10th free, tied to the customer (Contacts), cashier should see "
    "remaining punches on the POS-adjacent back office, not a fake receipt designer. "
    "Do not build x_receipt or copy GM/receipt studio. Receipts stay stock POS. "
    "One shop, Lagos, NGN. Residual is the punch card, not a new POS."
)


def test_lagos_punch_card_is_residual_register_not_stock_first() -> None:
    from app.ai_document_shape import classify_document_shape
    from app.ai_operator_brief import (
        brief_llm_contract,
        build_operator_brief,
        is_explicit_stock_first,
        stated_residual_kind,
    )
    from app.ai_pipeline import seed_studio_draft

    kind, noun = stated_residual_kind(LAGOS_PUNCH_CARD)
    assert kind == "named"
    assert "punch" in noun.lower()
    assert is_explicit_stock_first(LAGOS_PUNCH_CARD) is False
    brief = build_operator_brief(LAGOS_PUNCH_CARD)
    assert brief.capability_path == "residual_app"
    assert "punch" in (brief.custom_residual or "").lower()
    assert "point_of_sale" in brief.stock_reuse
    assert classify_document_shape(LAGOS_PUNCH_CARD, {}) == "register"
    contract = brief_llm_contract(LAGOS_PUNCH_CARD)
    assert "Document shape: register" in contract
    seed = seed_studio_draft(LAGOS_PUNCH_CARD)
    models = {str(m.get("model")) for m in seed.get("models") or []}
    assert "x_stay" not in models
    assert "x_receipt" not in models
    assert any("punch" in m for m in models) or any(
        "loyalty" in m for m in models
    ) or seed.get("_document_shape") == "register"
    header = next(
        m
        for m in (seed.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    )
    field_names = {str(f.get("name")) for f in (header.get("fields") or []) if isinstance(f, dict)}
    assert "x_partner_id" in field_names
    assert "x_remaining_punches" in field_names or "x_punches" in field_names
    assert any(
        isinstance(b, dict) and b.get("on_model") == "res.partner"
        for b in (seed.get("smart_buttons") or [])
    )
    assert "contacts" in (seed.get("depends") or [])


def test_receipts_stay_stock_alone_is_not_stock_first_capability() -> None:
    from app.ai_operator_brief import is_explicit_stock_first, is_pos_receipt_prompt

    text = "We need loyalty punches. Receipts stay stock POS. Do not build x_receipt."
    assert is_explicit_stock_first(text) is False
    assert is_pos_receipt_prompt(text) is False


def test_brief_ir_confidence_and_authoritative_labels() -> None:
    from app.ai_llm_prompt_log import log_llm_prompt_payload
    from app.ai_operator_brief import brief_llm_contract, build_operator_brief
    from app.settings import settings

    brief = build_operator_brief(LAGOS_PUNCH_CARD)
    assert brief.residual_kind == "named"
    assert brief.capability_source == "inferred"
    assert brief.ir_confidence == "high"
    assert "IR provenance" in brief.formatted
    contract = brief_llm_contract(LAGOS_PUNCH_CARD)
    assert "Source of truth" in contract
    assert "ir_confidence=high" in contract
    assert "verbatim — authoritative" in prompt_for_generators(LAGOS_PUNCH_CARD)
    assert "may be wrong" in prompt_for_generators(LAGOS_PUNCH_CARD)

    # Low-confidence class: no named residual, inferred stock_first.
    thin = build_operator_brief("Stand up Community POS for one shop in Lagos.")
    assert thin.residual_kind == "unstated"
    assert thin.capability_source == "inferred"
    assert thin.ir_confidence == "low"
    assert "IR confidence is low" in brief_llm_contract(
        "Stand up Community POS for one shop in Lagos."
    )

    prev = settings.ai_log_llm_prompts
    settings.ai_log_llm_prompts = True
    try:
        path = log_llm_prompt_payload(
            step="test_hop",
            prompt="hello operator",
            system="sys",
            provider="TestProvider",
        )
        assert path and path.endswith(".json")
        from pathlib import Path

        assert Path(path).is_file()
        Path(path).unlink(missing_ok=True)
    finally:
        settings.ai_log_llm_prompts = prev
