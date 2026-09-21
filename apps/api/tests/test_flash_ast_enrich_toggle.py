"""Studio Flash AST enrich toggle — off = floor only; on = enrich path callable."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_conversation.intent_llm import (
    intent_llm_enabled,
    reset_intent_llm_override,
    set_intent_llm_override,
)
from app.ai_conversation.understand import build_understanding
from app.studio_prefs import resolve_flash_ast_enrich


PREFER_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(start and end dates). Show a status hint when PO is set but delivery window "
    "is incomplete. Do not create a new app — inherit sale.order."
)


def test_env_off_means_floor_only() -> None:
    token = set_intent_llm_override(None)
    try:
        assert intent_llm_enabled() is False
        u = build_understanding(PREFER_SALES)
        assert u.constraints
        joined = " ".join(u.constraints).lower()
        assert "status hint" in joined or "po" in joined or "delivery" in joined
    finally:
        reset_intent_llm_override(token)


def test_toggle_off_forces_floor_even_if_env_on(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "ai_intent_llm", "on")
    token = set_intent_llm_override(False)
    try:
        assert intent_llm_enabled() is False
        u = build_understanding(PREFER_SALES)
        joined = " ".join(u.constraints).lower()
        assert "po" in joined or "delivery" in joined
    finally:
        reset_intent_llm_override(token)


def test_toggle_on_opens_enrich_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings
    from app.ai_conversation import understand as u_mod

    monkeypatch.setattr(settings, "ai_intent_llm", "off")
    token = set_intent_llm_override(True)
    try:
        assert intent_llm_enabled() is True
        det = u_mod._deterministic_understanding(PREFER_SALES)
        assert u_mod._should_llm_enrich(PREFER_SALES, det) is True
        with patch.object(u_mod, "_llm_enrich", side_effect=lambda prompt, det: det) as enrich:
            u_mod.build_understanding(PREFER_SALES)
            assert enrich.called
    finally:
        reset_intent_llm_override(token)


def test_resolve_pref_precedence() -> None:
    assert resolve_flash_ast_enrich(connection_pref=True, request_override=False) is False
    assert resolve_flash_ast_enrich(connection_pref=False, request_override=True) is True
    assert resolve_flash_ast_enrich(connection_pref=True, request_override=None) is True
    assert resolve_flash_ast_enrich(connection_pref=None, request_override=None) is None
