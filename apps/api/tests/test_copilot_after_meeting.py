"""Q7: after-meeting pack uses only grounded answers; unsure ones are 'to confirm'; email never sent."""

from __future__ import annotations

import pytest

from app.live_demo_copilot.after_meeting import build_after_meeting

pytestmark = pytest.mark.no_app_db


def test_pack():
    answers = [
        {"question": "Can we take deposits on quotations?", "speaker_name": "Ada", "bullets": ["Yes, with down payments in Sales."],
         "grounded": True, "declined": False, "citations": ["sale"], "confidence_flag": "high"},
        {"question": "Does stock update on delivery? Email me at ada@example.com", "speaker_name": "Ada", "bullets": [],
         "grounded": False, "declined": True, "citations": [], "confidence_flag": "low"},
    ]
    out = build_after_meeting(answers, 40, presenter="Tope")
    assert out["summary"].startswith("2 Odoo questions") and "1 answered" in out["summary"]
    assert [q["question"] for q in out["qa"]] == ["Can we take deposits on quotations?"]
    assert len(out["to_confirm"]) == 1 and "ada@example.com" not in out["to_confirm"][0]
    assert {p["app"] for p in out["starter_plan"]} >= {"Sales", "Inventory"}
    assert out["follow_up_email"]["sent"] is False and "ada@example.com" not in out["follow_up_email"]["body"]
