"""Production Retry AI enrichment — residual recovery when LLM is down."""

from __future__ import annotations

import copy

from app.ai_document_shape import (
    draft_needs_residual_recovery,
    recover_residual_draft,
)
from app.ai_enrich_jobs import enrich_steps_for_draft, finalize_enriched_draft
from app.ai_llm_status import banner_for_mode

LAGOS = (
    "We already use Community POS. What we don’t have is a simple loyalty punch card: "
    "buy 9 coffees get the 10th free, tied to the customer (Contacts), cashier should see "
    "remaining punches on the POS-adjacent back office, not a fake receipt designer. "
    "Do not build x_receipt or copy GM/receipt studio. Receipts stay stock POS. "
    "One shop, Lagos, NGN. Residual is the punch card, not a new POS."
)


def _hollow_punch_card() -> dict:
    return {
        "technical_name": "punch_card",
        "display_name": "Punch Card",
        "depends": ["base", "mail"],
        "models": [
            {
                "model": "x_punch_card",
                "description": "Punch Card",
                "mode": "new",
                "source": "honesty_ir",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True}
                ],
            }
        ],
        "smart_buttons": [],
        "_user_prompt": LAGOS,
        "_document_shape": "register",
        "_ambition": "thin",
        "_pipeline": "honesty_seed",
        "_llm_status": {
            "mode": "pack_fallback",
            "reason": "honesty_seed",
            "failed_steps": [],
            "completed_steps": [],
        },
    }


def test_hollow_punch_card_needs_recovery() -> None:
    draft = _hollow_punch_card()
    assert draft_needs_residual_recovery(draft, prompt=LAGOS)


def test_recover_residual_stamps_partner_without_llm() -> None:
    draft = _hollow_punch_card()
    notes = recover_residual_draft(draft, prompt=LAGOS)
    assert notes
    header = draft["models"][0]
    names = {f["name"] for f in header["fields"]}
    assert "x_partner_id" in names
    assert "x_remaining_punches" in names or "x_punches" in names
    assert "contacts" in draft["depends"]
    assert any(b.get("on_model") == "res.partner" for b in draft.get("smart_buttons") or [])


def test_finalize_enrich_recovers_without_provider() -> None:
    draft = _hollow_punch_card()
    warnings = finalize_enriched_draft(
        draft,
        prompt=LAGOS,
        warnings=[],
        llm_mode="residual_recovered",
        completed_steps=["recover"],
    )
    assert any("recover" in w for w in warnings) or "x_partner_id" in {
        f["name"] for f in draft["models"][0]["fields"]
    }
    status = draft["_llm_status"]
    assert status.get("reason") == "residual_recovered" or "x_partner_id" in {
        f["name"] for f in draft["models"][0]["fields"]
    }


def test_enrich_steps_skip_depth_on_thin_honesty() -> None:
    draft = _hollow_punch_card()
    assert enrich_steps_for_draft(draft, prompt=LAGOS, failed_steps=None, provider=None) == []
    steps = enrich_steps_for_draft(
        draft, prompt=LAGOS, failed_steps=None, provider=object()
    )
    assert "depth" not in steps
    assert "quality" in steps


def test_banner_recommends_retry_for_honesty_seed() -> None:
    msg = banner_for_mode("pack_fallback", reason="honesty_seed") or ""
    assert "Retry AI enrichment" in msg
    assert "wake" in msg.lower() or "brief" in msg.lower()


def test_needs_draft_llm_retry_on_honesty_seed() -> None:
    from app.ai_enrich_jobs import needs_draft_llm_retry

    draft = _hollow_punch_card()
    assert needs_draft_llm_retry(draft, prompt=LAGOS)


def test_merge_prefers_richer_llm() -> None:
    from app.ai_enrich_jobs import _merge_llm_draft_retry

    hollow = _hollow_punch_card()
    rich = copy.deepcopy(hollow)
    rich["models"][0]["fields"] = [
        {"name": "x_name", "ttype": "char", "string": "Name"},
        {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
        {"name": "x_punches", "ttype": "integer", "string": "Punches"},
        {"name": "x_remaining_punches", "ttype": "integer", "string": "Remaining"},
    ]
    merged, notes = _merge_llm_draft_retry(hollow, rich, prompt=LAGOS)
    assert len(merged["models"][0]["fields"]) >= 4
    assert any("replaced" in n for n in notes)


def test_enrich_runtime_imports_recover_symbols() -> None:
    from app.ai_enrich_jobs import _import_enrich_runtime

    rt = _import_enrich_runtime()
    assert callable(rt["recover_residual_draft"])
    assert callable(rt["draft_needs_residual_recovery"])
    assert callable(rt["revive_llm_providers"])


def test_normalize_punch_card_collapses_duplicate_customer() -> None:
    from app.ai_document_shape import honor_operator_brief, normalize_punch_card_fields
    from app.ai_domain_nouns import domain_noun_coverage
    from app.ai_draft_scorecard import attach_scorecard

    draft = {
        "technical_name": "punch_card",
        "display_name": "Punch Card",
        "depends": ["base", "contacts", "hr", "mail", "stock", "purchase"],
        "models": [
            {
                "model": "x_punch_card",
                "description": "Punch Card",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_punch_card",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {"name": "x_remaining_punches", "ttype": "integer", "string": "Remaining Punches"},
                    {"name": "x_total_punches", "ttype": "integer", "string": "Total Punches"},
                    {"name": "x_last_punch_date", "ttype": "datetime", "string": "Last Punch Date"},
                    {
                        "name": "x_next_free_punch_date",
                        "ttype": "datetime",
                        "string": "Next Free Punch Date",
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {"name": "x_punches", "ttype": "integer", "string": "Punches", "default": 0},
                    {"name": "x_next_free", "ttype": "boolean", "string": "Next free"},
                    {
                        "name": "x_punches_for_reward",
                        "ttype": "integer",
                        "string": "Punches for free",
                        "default": 9,
                    },
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Punch Cards",
                "related_model": "x_punch_card",
                "relation_field": "x_partner_id",
            }
        ],
        "views": [
            {
                "name": "x_punch_card.form",
                "model": "x_punch_card",
                "type": "form",
                "arch": (
                    '<form><sheet><field name="x_punch_card"/>'
                    '<field name="x_partner_id"/><field name="x_total_punches"/>'
                    '<field name="x_next_free_punch_date"/></sheet></form>'
                ),
            }
        ],
        "reuse": {"models": ["res.partner"]},
        "_user_prompt": LAGOS,
        "_document_shape": "register",
        "_ambition": "thin",
    }
    notes = normalize_punch_card_fields(draft, prompt=LAGOS)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_partner_id" in names
    assert "x_punch_card" not in names
    assert "x_total_punches" not in names
    assert "x_next_free_punch_date" not in names
    assert "x_punches" in names
    assert "x_remaining_punches" in names
    assert "stock" not in draft["depends"]
    assert "purchase" not in draft["depends"]
    assert "hr" not in draft["depends"]
    assert "contacts" in draft["depends"]
    arch = draft["views"][0]["arch"]
    assert "x_next_free_punch_date" not in arch
    assert notes

    honor_operator_brief(draft, user_prompt=LAGOS)
    _items, uncovered, _w = domain_noun_coverage(draft, LAGOS)
    assert "contact" not in uncovered
    attach_scorecard(draft, user_prompt=LAGOS)
    findings = (draft.get("_scorecard") or {}).get("findings") or []
    assert not any(
        f.get("element") == "noun:contact" for f in findings if isinstance(f, dict)
    )


def test_gate_pos_order_m2o_no_create_and_stamp_help() -> None:
    from app.ai_document_shape import draft_needs_hygiene_repair, honor_operator_brief
    from app.ai_llm_status import attach_llm_status, finalize_llm_status

    draft = {
        "technical_name": "punch_card",
        "display_name": "Punch Card",
        "depends": ["base", "mail", "contacts", "point_of_sale"],
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_last_transaction_id",
                        "ttype": "many2one",
                        "string": "Last Transaction",
                        "relation": "pos.order",
                    },
                    {"name": "x_last_transaction_date", "ttype": "datetime"},
                    {"name": "x_punches", "ttype": "integer"},
                    {"name": "x_remaining_punches", "ttype": "integer"},
                ],
            }
        ],
        "smart_buttons": [],
        "views": [
            {
                "model": "x_punch_card",
                "type": "form",
                "arch": '<form><field name="x_last_transaction_id"/><field name="x_partner_id"/></form>',
            }
        ],
        "reuse": {"catalog_suggestions": [{"model": "pos.order", "reason": "x"}]},
        "_user_prompt": LAGOS,
        "_document_shape": "register",
    }
    assert draft_needs_hygiene_repair(draft, prompt=LAGOS) is True
    honor_operator_brief(draft, user_prompt=LAGOS)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_last_transaction_id" in names
    assert "x_last_transaction_date" in names
    assert "x_partner_id" in names
    tx = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_last_transaction_id")
    assert tx.get("options", {}).get("no_create") is True
    assert tx.get("options", {}).get("no_create_edit") is True
    assert tx.get("help")
    partner = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_partner_id")
    assert partner.get("required") is True
    assert partner.get("help")
    assert "point_of_sale" in draft["depends"]
    assert "no_create" in draft["views"][0]["arch"]
    assert any(b.get("on_model") == "res.partner" for b in draft["smart_buttons"])
    assert draft_needs_hygiene_repair(draft, prompt=LAGOS) is False
    attach_llm_status(draft, mode="llm_full", completed_steps=["quality"])
    finalize_llm_status(draft, mode="llm_full")
    assert draft["_llm_status"].get("enrichment_clean") is True
    assert draft["_llm_status"].get("retry_recommended") is False
