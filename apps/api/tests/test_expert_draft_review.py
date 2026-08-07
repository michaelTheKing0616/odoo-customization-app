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
