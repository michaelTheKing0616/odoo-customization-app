"""EXP2-2 expert draft review endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.draft_review import review_draft  # noqa: E402
from app.main import app  # noqa: E402

FIXTURE5 = Path(__file__).parent / "fixtures" / "draft_supermarket5_2026-08-07.json"
PROMPT = "A large, mega, super market with multiple branches around the world"


def _load_fixture5() -> dict:
    return json.loads(FIXTURE5.read_text())


def test_expert_review_draft_apply_improves_score() -> None:
    draft = _load_fixture5()
    before = review_draft(draft, user_prompt=PROMPT, apply_fixes=False)
    after = review_draft(draft, user_prompt=PROMPT, apply_fixes=True)
    assert after.score_after is not None
    assert after.score_after >= before.score_before
    assert after.score_after >= 9.0


def test_expert_review_draft_api() -> None:
    draft = _load_fixture5()
    with TestClient(app) as client:
        res = client.post(
            "/api/expert/review-draft",
            json={"draft": draft, "user_prompt": PROMPT, "apply_fixes": True},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["score_before"] < body["score_after"]
    assert body["draft"] is not None
    assert body["draft"].get("_scorecard", {}).get("score_0_10", 0) >= 9.0


def test_expert_does_not_invent_models_on_stock_reuse() -> None:
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_generation_engine import is_stock_reuse_draft
    from app.ai_pipeline import seed_studio_draft
    from test_ai_generation_engine import POS_STOCK_FIRST

    seed = seed_studio_draft(POS_STOCK_FIRST)
    draft = _finish_seed_draft(POS_STOCK_FIRST, seed, [])
    assert is_stock_reuse_draft(draft)
    models_before = list(draft.get("models") or [])
    result = review_draft(draft, user_prompt=POS_STOCK_FIRST, apply_fixes=True)
    assert result.draft is not None
    assert is_stock_reuse_draft(result.draft)
    assert result.draft.get("models") == models_before
    assert result.verdict == "no_repair_needed"
    assert any("no_repair" in n for n in result.repairs)
    assert result.score_after == result.score_before


def test_expert_reverts_when_closer_would_invent_stock_reuse_models() -> None:
    from app.expert.draft_review import _worse_after_closer

    original = {
        "_generation_engine": {"capability": "stock_reuse"},
        "models": [],
    }
    worse = {
        "_generation_engine": {"capability": "residual_app"},
        "models": [{"model": "x_receipt", "fields": []}],
    }
    reason = _worse_after_closer(original, worse, score_before=10.0, score_after=10.0)
    assert reason is not None
    assert "x_receipt" in reason or "stock_reuse" in reason


def test_expert_repairs_live_apply_activity_mixin() -> None:
    draft = {
        "technical_name": "x_ticket_app",
        "display_name": "Tickets",
        "depends": ["base"],
        "grain": "full_app",
        "models": [
            {
                "model": "x_ticket",
                "fields": [{"name": "x_name", "ttype": "char"}],
                "mixins": [],
            }
        ],
        "automations": [
            {
                "name": "ticket follow-up",
                "model": "x_ticket",
                "trigger": "on_create",
                "actions": [{"kind": "next_activity", "summary": "Follow up"}],
            }
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "_user_prompt": "help desk tickets with follow-up activities",
        "_generation_engine": {"capability": "residual_app"},
        "_scorecard": {"score_0_10": 8.0, "findings": []},
        "_live_apply": {
            "ready": False,
            "findings": [
                {
                    "detail": "live apply: next_activity needs mail.activity.mixin",
                    "element": "ticket follow-up",
                }
            ],
        },
    }
    before = review_draft(draft, user_prompt=draft["_user_prompt"], apply_fixes=False)
    assert any("mail.activity.mixin" in f.detail for f in before.findings)
    after = review_draft(draft, user_prompt=draft["_user_prompt"], apply_fixes=True)
    assert after.draft is not None
    assert after.score_after is not None
    assert after.score_after >= after.score_before
    ticket = next(m for m in after.draft["models"] if m.get("model") == "x_ticket")
    mixins = ticket.get("mixins") or []
    assert "mail.activity.mixin" in mixins
    autos = after.draft.get("automations") or []
    assert any(
        isinstance(a, dict) and a.get("model") == "x_ticket"
        for a in autos
    )
    live = after.draft.get("_live_apply") or {}
    details = " ".join(str(f.get("detail") or "") for f in (live.get("findings") or []))
    assert "mail.activity.mixin" not in details
    assert after.verdict != "no_repair_needed"


def test_expert_rebuilds_restaurant_pack_on_invoice_field_pack_prompt() -> None:
    from app.expert.draft_review import apply_deterministic_scorecard_fixes
    from test_ai_studio_seed import SLA_INVOICE_FIELD_PROMPT

    leaked = {
        "technical_name": "restaurant_management",
        "domain_pack": "restaurant",
        "grain": "full_app",
        "models": [
            {"model": "x_bill", "mode": "new", "fields": []},
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [{"name": "x_sla_due_date", "ttype": "datetime"}],
            },
        ],
        "_user_prompt": SLA_INVOICE_FIELD_PROMPT,
        "_generation_engine": {"capability": "residual_app", "grain": "field_pack"},
    }
    rebuilt, notes = apply_deterministic_scorecard_fixes(
        leaked, user_prompt=SLA_INVOICE_FIELD_PROMPT
    )
    models = {
        str(m.get("model"))
        for m in (rebuilt.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    assert models == {"account.move"}
    assert rebuilt.get("domain_pack") != "restaurant"
    assert any("field_pack" in n for n in notes)


def test_expert_rebuilds_hotel_pack_on_visitor_log_prompt() -> None:
    from app.expert.draft_review import apply_deterministic_scorecard_fixes
    from test_ai_studio_seed import VISITOR_LOG_PROMPT

    leaked = {
        "technical_name": "hotel_management",
        "domain_pack": "hotel",
        "grain": "full_app",
        "models": [
            {"model": "x_hotel", "mode": "new", "fields": []},
            {"model": "x_bill", "mode": "new", "fields": []},
            {"model": "x_room", "mode": "new", "fields": []},
        ],
        "_user_prompt": VISITOR_LOG_PROMPT,
        "_generation_engine": {"capability": "residual_app", "grain": "full_app"},
    }
    rebuilt, notes = apply_deterministic_scorecard_fixes(
        leaked, user_prompt=VISITOR_LOG_PROMPT
    )
    models = {
        str(m.get("model"))
        for m in (rebuilt.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    assert "x_hotel" not in models
    assert "x_bill" not in models
    assert "x_room" not in models
    assert rebuilt.get("domain_pack") != "hotel"
    assert any("incoherent vertical pack" in n for n in notes)


def test_expert_repairs_punch_card_hygiene_even_at_high_score() -> None:
    """Completeness can be green while Flash left two Customer M2Os — still repair."""
    from app.ai_document_shape import draft_needs_hygiene_repair

    lagos = (
        "We already use Community POS. What we don’t have is a simple loyalty punch card: "
        "buy 9 coffees get the 10th free, tied to the customer (Contacts). "
        "Receipts stay stock POS. Residual is the punch card, not a new POS."
    )
    draft = {
        "technical_name": "punch_card",
        "display_name": "Punch Card",
        "depends": ["base", "contacts", "hr", "mail", "stock", "purchase"],
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_punch_card",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                    {"name": "x_total_punches", "ttype": "integer"},
                    {"name": "x_punches", "ttype": "integer"},
                    {"name": "x_next_free_punch_date", "ttype": "datetime"},
                    {"name": "x_next_free", "ttype": "boolean"},
                ],
            }
        ],
        "smart_buttons": [],
        "views": [],
        "actions": [],
        "menus": [],
        "reuse": {"models": ["res.partner"]},
        "_user_prompt": lagos,
        "_document_shape": "register",
        "_generation_engine": {"capability": "residual_app"},
        "_llm_status": {"mode": "llm_full"},
        "_scorecard": {"score_0_10": 10.0, "findings": []},
    }
    assert draft_needs_hygiene_repair(draft, prompt=lagos)
    result = review_draft(
        draft, user_prompt=lagos, apply_fixes=True, include_narratives=False
    )
    assert result.verdict != "no_repair_needed"
    assert result.draft is not None
    names = {f["name"] for f in result.draft["models"][0]["fields"]}
    assert "x_partner_id" in names
    assert "x_punch_card" not in names
    assert "stock" not in result.draft["depends"]
    assert "purchase" not in result.draft["depends"]
