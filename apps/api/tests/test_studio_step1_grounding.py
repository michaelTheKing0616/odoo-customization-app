"""Step 1: stated app names, plain diagnosis summary, grounding, AI step default, outcome.

Fake LLM only. The Customer Health brief fixture is the operator's original text.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.ai_conversation.clarify import apply_clarification_answer  # noqa: E402
from app.ai_conversation.grounding import (  # noqa: E402
    StudioGrounding,
    brief_wants_llm,
    llm_timeout_for,
    reset_grounding,
    set_grounding,
)
from app.ai_conversation.intent_llm import (  # noqa: E402
    reset_intent_llm_override,
    set_intent_llm_override,
)
from app.ai_operator_brief import stated_app_name, stated_residual_kind  # noqa: E402
from app.studio_prefs import resolve_flash_ast_enrich  # noqa: E402

BRIEF = (Path(__file__).parent / "fixtures" / "customer_health_brief.md").read_text()
TITLE = "Customer Health & Retention Intelligence"
POLICY_BITS = ("Stock ", "custom residual", "Completeness", "Promote stays human", "Cert")


@pytest.mark.parametrize(
    ("brief", "name"),
    [
        (BRIEF, TITLE),
        ("Build an app named \"Visitor Desk\" for reception.", "Visitor Desk"),
        ("I need a module called Fleet Fuel Log to track fuel.", "Fleet Fuel Log"),
        ("Create an app: **Room Booking** for staff.", "Room Booking"),
        ("Build a tool titled \u201cGate Pass\u201d.", "Gate Pass"),
        ("# Vendor Scorecard\nTrack supplier quality per purchase.", "Vendor Scorecard"),
        ("An app called Sales and Ops Board for the floor.", "Sales and Ops Board"),
    ],
)
def test_stated_app_name(brief: str, name: str) -> None:
    assert stated_app_name(brief) == name
    assert stated_residual_kind(brief) == ("named", name)


@pytest.mark.parametrize(
    "brief",
    [
        "Create a complete custom Odoo application.",
        "Add a field called Priority on the Sales order.",
        "## 1. Core concept\nScores per account.",
        "# Add priority to Sales\nA selection field.",
        "Build a full new app.",
    ],
)
def test_cue_words_and_field_names_are_not_app_names(brief: str) -> None:
    assert stated_app_name(brief) == ""


def test_named_brief_skips_residual_question() -> None:
    from app.ai_conversation.intent_gate import assess_intent

    assessment = assess_intent(BRIEF, resolved_answers={})
    assert assessment.residual_kind == "named"
    assert "material_ambiguity" not in assessment.triggers
    assert "low_ir_confidence" not in assessment.triggers


def test_repasted_brief_does_not_double_prompt() -> None:
    merged, answers = apply_clarification_answer(
        BRIEF, merge_key="residual", answer_id="other", answer_text=BRIEF
    )
    assert answers["residual"] == "named in brief"
    assert len(merged) < len(BRIEF) * 1.1
    assert stated_residual_kind(merged) == ("named", TITLE)


def test_ai_step_default_long_on_short_unchanged_explicit_wins() -> None:
    short = "Add a Priority field on sales orders."
    assert brief_wants_llm(BRIEF) and not brief_wants_llm(short)
    assert resolve_flash_ast_enrich(prompt=BRIEF) is True
    assert resolve_flash_ast_enrich(prompt=short) is None  # env decides, as before
    assert resolve_flash_ast_enrich(prompt=BRIEF, request_override=False) is False
    assert resolve_flash_ast_enrich(prompt=BRIEF, connection_pref=False) is False


def test_understand_timeout_scales_with_length() -> None:
    assert llm_timeout_for("short brief") == 20.0
    assert 40.0 <= llm_timeout_for(BRIEF) <= 45.0
    assert llm_timeout_for(BRIEF * 4) == 60.0


@pytest.mark.parametrize(
    ("edition", "lead"),
    [("enterprise", "Stock Enterprise apps first"), ("community", "Stock Community apps first"), (None, "Stock apps first")],
)
def test_internal_honesty_is_edition_aware(edition: str | None, lead: str) -> None:
    from app.ai_generation_engine import classify_generation

    token = set_grounding(StudioGrounding(edition=edition) if edition else None)
    try:
        plan = classify_generation("Custom residual: visitor log. Guests sign in at the front desk.")
    finally:
        reset_grounding(token)
    assert plan.honesty.startswith(lead)


class _FakeProvider:
    name = "gemini"
    model = "gemini-2.5-flash"

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def generate_json(self, prompt: str, *, system: str = "", **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        if "You diagnose" not in system:
            return {}
        if self.fail is not None:
            raise self.fail
        return {
            "title": "Health Monitor",
            "summary": "",
            "constraints": ["Health score per customer (0 to 100)"],
        }


def _diagnosis_provider(monkeypatch: pytest.MonkeyPatch, provider: _FakeProvider) -> None:
    import app.llm_provider as lp
    from app.ai_conversation.understand import clear_enrich_cache

    clear_enrich_cache()
    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: provider)


def test_build_understanding_records_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_conversation.understand import build_understanding
    from app.llm_provider import LLMError

    provider = _FakeProvider(fail=LLMError("Gemini request timed out after 42s"))
    _diagnosis_provider(monkeypatch, provider)
    token = set_intent_llm_override(True)
    try:
        u = build_understanding(BRIEF)
    finally:
        reset_intent_llm_override(token)
    assert u.llm_outcome["status"] == "timed_out"
    assert u.llm_outcome["model"] == "gemini-2.5-flash"
    assert u.llm_outcome["prompt_chars"] > len(BRIEF) // 2
    assert u.source == "deterministic"
    assert u.title == TITLE


def test_build_understanding_skipped_when_ai_step_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_conversation.understand import build_understanding

    provider = _FakeProvider()
    _diagnosis_provider(monkeypatch, provider)
    token = set_intent_llm_override(False)
    try:
        u = build_understanding("Add a Priority field on sales orders.")
    finally:
        reset_intent_llm_override(token)
    assert u.llm_outcome == {"status": "skipped", "reason": "ai_step_off"}
    assert not [c for c in provider.calls if "You diagnose" in c["system"]]


def test_customer_health_session_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import app.routers.ai_studio as studio
    from app.crypto import encrypt_secret
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.main import app

    provider = _FakeProvider()
    _diagnosis_provider(monkeypatch, provider)
    plan = {
        "integrations": [
            {"module": "crm", "app_label": "CRM", "model": "crm.lead", "status": "available", "note": ""},
            {"module": "helpdesk", "app_label": "Helpdesk", "model": "helpdesk.ticket", "status": "left_out", "note": ""},
        ]
    }
    monkeypatch.setattr(studio, "_brief_gate", lambda conn, prompt: (None, plan))
    monkeypatch.setattr(studio, "_studio_schema_packet", lambda conn, prompt="": None)
    monkeypatch.setattr(studio, "_record_integration_plan", lambda db, out, plan: None)

    init_db()
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="step1-health",
            url="https://acme-health.odoo.com",
            db_name="acme",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="20.0+e",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    with TestClient(app) as client:
        res = client.post("/api/ai/sessions", json={"prompt": BRIEF, "connection_id": cid})
    assert res.status_code == 200, res.text
    out = res.json()
    clar = out["clarification"]
    assert clar["kind"] == "diagnosis", clar.get("question")  # no residual question
    assert clar["question"] == f"We'll build: {TITLE}"
    u = clar["understanding"]
    assert u["title"] == TITLE
    for bit in POLICY_BITS:
        assert bit not in u["summary"], (bit, u["summary"])
        assert bit not in clar["help"], (bit, clar["help"])
    assert "\u2014" not in u["summary"] and "\u2014" not in clar["help"]
    assert "Links to CRM" in u["summary"] and "Helpdesk is not installed yet" in u["summary"]
    assert u["policy_note"].startswith("Stock Enterprise apps first")
    assert clar["grounding"]["edition"] == "enterprise"
    assert clar["grounding"]["hosting"] == "online"
    assert clar["grounding"]["apps_missing"] == ["Helpdesk"]
    outcome = clar["llm_outcome"]
    assert outcome["status"] == "called" and outcome["model"] == "gemini-2.5-flash"
    assert outcome["prompt_chars"] > 0 and "latency_ms" in outcome
    diag_calls = [c for c in provider.calls if "You diagnose" in c["system"]]
    assert diag_calls  # primary fill (a one-shot repair fill may follow)
    assert "Odoo Enterprise" in diag_calls[0]["system"]
    assert "Odoo Online cannot install custom Python" in diag_calls[0]["system"]
    assert "hosted on Odoo Online" in diag_calls[0]["prompt"]
    assert diag_calls[0]["timeout_s"] > 20.0
    assert u["source"] == "mixed"
