"""Optional live expert run recorder — writes docs/research/expert_runs_<date>/."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

pytestmark = pytest.mark.integration

_REPO = Path(__file__).resolve().parents[3]
_OUT = _REPO / "docs" / "research" / f"expert_runs_{date.today().isoformat()}"

_QUESTIONS = [
    ("run_01_xpath_inherit.json", "How does xpath view inheritance work in Odoo Community?", {"route": "/designer", "model": "res.partner"}),
    ("run_02_access_error.json", "Diagnose this error on my connection\n\nError log:\nAccessError: You are not allowed to modify 'res.partner' records.", {"route": "/builder", "model": "res.partner", "pasted_error": "AccessError: You are not allowed to modify 'res.partner' records."}),
    ("run_03_protected_tiers.json", "What are the protected module tiers?", {"route": "/builder"}),
]


@pytest.mark.skipif(os.getenv("EXPERT_RUNS_LIVE") != "1", reason="set EXPERT_RUNS_LIVE=1 for live capture")
def test_record_expert_runs_live() -> None:
    from app.expert.ask import ask_expert, expert_assist_enabled
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection

    if not expert_assist_enabled():
        pytest.skip("AI_ASSIST must be enabled (e.g. ollama)")

    init_db()
    db = SessionLocal()
    try:
        row = db.query(OdooConnection).order_by(OdooConnection.created_at.desc()).first()
        if row is None:
            pytest.skip("No connection in app DB")
        _OUT.mkdir(parents=True, exist_ok=True)
        for filename, question, ui_context in _QUESTIONS:
            result = ask_expert(
                db,
                question=question,
                connection_id=row.id,
                ui_context=ui_context,
            )
            payload = {
                "recorded_at": date.today().isoformat(),
                "mode": "live",
                "connection_id": row.id,
                "question": question,
                "ui_context": ui_context,
                "response": {
                    "answer_markdown": result.answer_markdown,
                    "citations": [c.to_dict() for c in result.citations],
                    "grounded": result.grounded,
                    "declined": result.declined,
                    "caution_flags": result.caution_flags,
                },
            }
            (_OUT / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    finally:
        db.close()

    assert (_OUT / "run_01_xpath_inherit.json").is_file()
