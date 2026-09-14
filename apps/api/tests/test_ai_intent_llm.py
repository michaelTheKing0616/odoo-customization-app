"""Optional LLM intent tie-break — mock provider only in unit tests."""

from __future__ import annotations

import json

import pytest

from app.ai_conversation.intent_gate import IntentAssessment, assess_intent
from app.ai_conversation.intent_llm import intent_llm_enabled, maybe_llm_refine_assessment
from app.llm_provider import MockLLMProvider
from app.settings import settings


def test_intent_llm_disabled_by_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "off"
    assert intent_llm_enabled() is False


def test_pack_ambiguity_llm_can_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "on"
    settings.ai_llm_tier_fast = "mock"

    response = json.dumps(
        {
            "clear": True,
            "confidence": "high",
            "pack_id": "helpdesk_tickets",
            "rationale": "Prompt asks for internal tickets, not projects.",
        }
    )
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(json_response=response),
    )

    assessment = IntentAssessment(
        clear=False,
        triggers=["pack_ambiguity"],
        ir_confidence="medium",
        capability_path="residual_app",
    )
    refined = maybe_llm_refine_assessment(
        "Helpdesk tickets with requester and status workflow",
        assessment,
        ranked=[("helpdesk_tickets", 0.4), ("project_tracker", 0.38)],
    )
    assert refined.clear is True
    assert refined.llm_resolved is not None
    assert refined.llm_resolved.get("pack_id") == "helpdesk_tickets"


def test_intent_llm_can_extract_sales_host(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "on"
    settings.ai_llm_tier_fast = "mock"
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(
            json_response=json.dumps(
                {
                    "clear": True,
                    "confidence": "high",
                    "host_model": "sale.order",
                    "inherit_existing": True,
                    "needs_module": True,
                    "rationale": "Markup and WHT on stock Sales, not a new app.",
                }
            )
        ),
    )
    assessment = IntentAssessment(
        clear=False,
        triggers=["pack_ambiguity"],
        ir_confidence="low",
        capability_path="residual_app",
    )
    refined = maybe_llm_refine_assessment(
        "Add markup percent and withholding tax on every sale",
        assessment,
        ranked=[("restaurant", 0.31), ("retail_supermarket", 0.29)],
    )
    assert refined.clear is True
    assert refined.llm_resolved is not None
    assert refined.llm_resolved.get("host_model") == "sale.order"
    assert refined.llm_resolved.get("needs_module") is True


def test_pack_conflict_never_llm_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "on"
    settings.ai_llm_tier_fast = "mock"
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(
            json_response='{"clear": true, "confidence": "high", "pack_id": "project_tracker", "rationale": "wrong"}'
        ),
    )
    assessment = IntentAssessment(clear=False, triggers=["pack_conflict"])
    refined = maybe_llm_refine_assessment("tickets only", assessment, ranked=[])
    assert refined.clear is False


def test_assess_intent_uses_llm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "on"
    settings.ai_llm_tier_fast = "mock"
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": MockLLMProvider(
            json_response=json.dumps(
                {
                    "clear": True,
                    "confidence": "high",
                    "residual": "tickets",
                    "rationale": "Named ticket workflow",
                }
            )
        ),
    )
    prompt = "Internal support: I want tickets with requester and status, no project app."
    result = assess_intent(prompt)
    assert result.clear is True or "material_ambiguity" not in result.triggers
