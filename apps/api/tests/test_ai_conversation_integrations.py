"""Job Autopilot + Expert must import shared ai_conversation hooks."""

from __future__ import annotations

import importlib


def test_expert_ask_imports_conversation_hooks() -> None:
    mod = importlib.import_module("app.expert.ask")
    src = open(mod.__file__, encoding="utf-8").read()
    assert "ai_conversation.feature_hooks" in src


def test_job_autopilot_router_imports_conversation_hooks() -> None:
    mod = importlib.import_module("app.routers.job_autopilot")
    src = open(mod.__file__, encoding="utf-8").read()
    assert "ai_conversation.feature_hooks" in src
