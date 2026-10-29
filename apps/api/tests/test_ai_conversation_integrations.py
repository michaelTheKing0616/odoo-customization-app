"""Job Autopilot must import shared ai_conversation hooks.

Expert ask answers questions about Odoo (ground-or-decline); it builds no app, so the
app-intent hooks do not apply there.
"""

from __future__ import annotations

import importlib


def test_job_autopilot_router_imports_conversation_hooks() -> None:
    mod = importlib.import_module("app.routers.job_autopilot")
    src = open(mod.__file__, encoding="utf-8").read()
    assert "ai_conversation.feature_hooks" in src
