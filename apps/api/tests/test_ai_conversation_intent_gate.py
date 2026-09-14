"""Intent resolution gate — rental, clinic, helpdesk, low IR."""

from __future__ import annotations

from app.ai_conversation.clarify import apply_clarification_answer, build_clarification
from app.ai_conversation.intent_gate import assess_intent, should_block_generation
from app.ai_domain_coherence import should_apply_domain_pack
from app.ai_domain_pack_project_tracker import project_tracker_pack
from app.ai_operator_brief import build_operator_brief

HELPDESK_PROMPT = (
    "Helpdesk is Slack screenshots. I want tickets: requester (employee), asset tag, "
    "category (laptop/network/access), priority, description, status draft → in progress "
    "→ waiting → done."
)

CLINIC_PROMPT = "A neighborhood clinic with walk-in appointments and patient records."


def test_bare_rental_triggers_clarification() -> None:
    assessment = assess_intent("rental")
    assert assessment.clear is False
    assert "rental_ambiguity" in assessment.triggers
    assert should_block_generation(assessment)
    clarify = build_clarification(assessment)
    assert clarify is not None
    assert clarify.get("merge_key") == "rental_domain"


def test_clear_clinic_prompt_proceeds() -> None:
    assessment = assess_intent(CLINIC_PROMPT)
    assert assessment.clear is True
    assert should_block_generation(assessment) is False


def test_session_already_admitted_skips_regate() -> None:
    from app.ai_conversation.intent_gate import session_already_admitted

    assert session_already_admitted("ready") is True
    assert session_already_admitted("clarifying") is False


def test_low_ir_stock_first_prompt_blocks() -> None:
    prompt = "Configure Odoo for our business using standard apps only."
    assessment = assess_intent(prompt)
    assert assessment.ir_confidence == "low"
    assert should_block_generation(assessment)
    clarify = build_clarification(assessment)
    assert clarify is not None
    assert clarify.get("merge_key") == "ir_confidence"


def test_clarify_merge_sets_residual_app() -> None:
    prompt = "Configure Odoo for our business using standard apps only."
    merged, answers = apply_clarification_answer(
        prompt,
        merge_key="ir_confidence",
        answer_id="residual_app",
        answer_text="Custom app",
    )
    assert answers["ir_confidence"] == "residual_app"
    assert "residual_app" in merged or "Custom residual" in merged
    reassess = assess_intent(merged, resolved_answers=answers)
    assert reassess.ir_confidence in {"high", "medium"}


def test_helpdesk_blocks_project_tracker_embedding() -> None:
    pack = project_tracker_pack()
    ok, notes = should_apply_domain_pack(
        HELPDESK_PROMPT,
        "project_tracker",
        pack,
        retrieval_score=0.49,
        retrieval_method="embedding",
    )
    assert ok is False
    assert notes


PURCHASE_REQUEST_PROMPT = (
    "Purchase requests with amount, requester, and a manager approval flow.\n"
    "Staff submit a request; a manager must approve or refuse it.\n"
    "When something is waiting, notify the manager with a to-do."
)


def test_purchase_request_prompt_is_clear_without_pack_choice() -> None:
    first = assess_intent(PURCHASE_REQUEST_PROMPT)
    assert first.clear is True
    assert "pack_ambiguity" not in first.triggers
    assert "low_ir_confidence" not in first.triggers
    assert build_clarification(first) is None


def test_leave_request_prompt_is_clear_without_stock_chip() -> None:
    from app.ai_conversation.intent_gate import thin_document_brief

    prompt = (
        "Leave requests with a start date. An approver must approve or refuse it. "
        "Notify the approver with a to-do."
    )
    assert thin_document_brief(prompt)
    assessment = assess_intent(prompt)
    assert assessment.clear is True
    assert "low_ir_confidence" not in assessment.triggers
    assert build_clarification(assessment) is None


def test_purchase_request_pack_choice_does_not_ask_stock_vs_custom() -> None:
    merged, answers = apply_clarification_answer(
        PURCHASE_REQUEST_PROMPT,
        merge_key="pack_choice",
        answer_id="transactional",
        answer_text="One simple document (no vertical pack)",
    )
    assert "Capability path: residual_app" in merged
    assert answers.get("ir_confidence") == "residual_app"
    second = assess_intent(merged, resolved_answers=answers)
    assert second.clear is True
    assert "low_ir_confidence" not in second.triggers
    assert build_clarification(second) is None


def test_stock_chip_after_simple_document_does_not_wipe_residual() -> None:
    merged, answers = apply_clarification_answer(
        PURCHASE_REQUEST_PROMPT,
        merge_key="pack_choice",
        answer_id="transactional",
        answer_text="One simple document (no vertical pack)",
    )
    wiped, answers = apply_clarification_answer(
        PURCHASE_REQUEST_PROMPT,
        merge_key="ir_confidence",
        answer_id="stock_first",
        answer_text="Stock Community apps only",
        resolved_answers=answers,
    )
    assert "Custom residual: named in brief" in wiped
    assert "Capability path: residual_app" in wiped
    assert "stock Community apps only" not in wiped.split("Custom residual", 1)[-1][:80]
    assert answers["ir_confidence"] == "residual_app"
    from app.ai_generation_engine import classify_generation
    from app.ai_operator_brief import wants_stock_reuse

    assert wants_stock_reuse(wiped) is False
    assert classify_generation(wiped).capability != "stock_reuse"


def test_helpdesk_brief_is_high_confidence() -> None:
    brief = build_operator_brief(HELPDESK_PROMPT)
    assert brief.ir_confidence == "high"
    assert brief.custom_residual == "tickets"


VENDOR_TIN_PROMPT = (
    "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
    "required before Confirm. Do not add it on customer invoices."
)


def test_vendor_tin_field_pack_skips_pack_choice() -> None:
    assessment = assess_intent(VENDOR_TIN_PROMPT)
    assert assessment.clear is True
    assert "pack_ambiguity" not in assessment.triggers
    assert "low_ir_confidence" not in assessment.triggers
    clarify = build_clarification(assessment, prompt=VENDOR_TIN_PROMPT)
    assert clarify is None


def test_pack_ambiguity_copy_is_plain_language() -> None:
    from app.ai_conversation.intent_gate import IntentAssessment

    assessment = IntentAssessment(
        clear=False,
        triggers=["pack_ambiguity"],
        competing_pack_id="project_tracker",
        notes=["Ambiguous pack fit: project_tracker@0.31 vs restaurant@0.29"],
    )
    clarify = build_clarification(assessment, prompt="track our work this quarter")
    assert clarify is not None
    blob = " ".join(
        [str(clarify.get("question") or ""), str(clarify.get("help") or "")]
        + [str(opt.get("label") or "") for opt in (clarify.get("options") or [])]
    ).lower()
    assert "which domain" not in blob
    assert "vertical pack" not in blob
    assert "helpdesk" not in blob
    ids = [opt["id"] for opt in (clarify.get("options") or [])]
    assert ids[0] == "on_existing_form"
    assert "transactional" in ids
    assert "helpdesk_tickets" not in ids


def test_pack_ambiguity_helpdesk_only_when_prompt_says_tickets() -> None:
    from app.ai_conversation.intent_gate import IntentAssessment

    assessment = IntentAssessment(
        clear=False,
        triggers=["pack_ambiguity"],
        competing_pack_id="helpdesk_tickets",
        notes=["Ambiguous pack fit: helpdesk_tickets@0.40 vs project_tracker@0.38"],
    )
    without = build_clarification(assessment, prompt="track our work this quarter")
    assert without is not None
    assert "helpdesk_tickets" not in [opt["id"] for opt in (without.get("options") or [])]

    with_tickets = build_clarification(
        assessment, prompt="internal tickets for IT support"
    )
    assert with_tickets is not None
    ids = [opt["id"] for opt in (with_tickets.get("options") or [])]
    assert "helpdesk_tickets" in ids
    labels = " ".join(opt["label"] for opt in with_tickets["options"]).lower()
    assert "asks for help" in labels
    assert "vertical pack" not in labels


CLIENT_MARKUP_PROMPT = (
    'The Client wants a "Mark-up" line added to every Sale they make. They purchase '
    "products on requests from their customers and the selling price is the additive "
    "value of the purchase/cost price and their own mark-up. A Witholding Tax, on the "
    "markup is to be calculated as well, only for Sales, NOT Purchases."
)


def test_sales_markup_skips_pack_choice() -> None:
    assessment = assess_intent(CLIENT_MARKUP_PROMPT)
    assert assessment.clear is True
    assert "pack_ambiguity" not in assessment.triggers
    assert "low_ir_confidence" not in assessment.triggers
    assert build_clarification(assessment, prompt=CLIENT_MARKUP_PROMPT) is None


def test_on_existing_form_does_not_stamp_named_residual() -> None:
    merged, answers = apply_clarification_answer(
        VENDOR_TIN_PROMPT,
        merge_key="pack_choice",
        answer_id="on_existing_form",
        answer_text="Add it to a form you already use",
    )
    assert "Custom residual: named in brief" not in merged
    assert "existing Odoo form" in merged
    assert "Do not create a new home-screen app" in merged
    assert answers.get("ir_confidence") != "residual_app"
    wiped, answers = apply_clarification_answer(
        VENDOR_TIN_PROMPT,
        merge_key="ir_confidence",
        answer_id="stock_first",
        answer_text="Use Odoo’s standard apps only",
        resolved_answers=answers,
    )
    assert "stock Community apps only" not in wiped
    assert "existing Odoo form" in wiped
    assert answers.get("ir_confidence") != "stock_first"

