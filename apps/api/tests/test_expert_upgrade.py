"""Expert explain + NL search + chatter bridge tests."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.draft_review import review_draft  # noqa: E402
from app.expert.explain import build_explain_question  # noqa: E402
from app.expert.nl_search import nl_search  # noqa: E402
from app.expert.suggested_prompts import suggested_prompts_for_context  # noqa: E402
from app.main import app  # noqa: E402


def test_build_explain_question_model_and_field() -> None:
    draft = {
        "models": [
            {
                "model": "x_branch",
                "description": "Store branch",
                "fields": [{"name": "x_code", "ttype": "char", "string": "Code"}],
            }
        ]
    }
    q = build_explain_question(model="x_branch", field="x_code", draft=draft)
    assert "x_code" in q
    assert "x_branch" in q


def test_review_draft_includes_narrative_fallback_without_db() -> None:
    draft = {
        "name": "test_app",
        "models": [{"model": "x_test", "fields": [{"name": "name", "ttype": "char"}]}],
    }
    result = review_draft(draft, user_prompt="test", include_narratives=True, db=None)
    narrated = [f for f in result.findings if f.narrative_paragraph]
    assert narrated
    assert "Expert review (cited):" in result.review_markdown


def test_suggested_prompts_wizard_route() -> None:
    rows = suggested_prompts_for_context(route="/connections/abc/wizard", model="x_branch")
    assert any(r["id"] == "draft-score" for r in rows)
    assert rows[0]["id"] == "explain-model"


def test_nl_search_routes_wizard_query() -> None:
    result = nl_search("open ai wizard draft", connection_id="conn-1")
    assert any(h.id == "nav-wizard" for h in result.hits)


def test_expert_suggested_prompts_api() -> None:
    with TestClient(app) as client:
        res = client.get("/api/expert/suggested-prompts", params={"route": "/wizard", "model": "x_a"})
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert body[0]["question"]


def test_expert_nl_search_api() -> None:
    with TestClient(app) as client:
        res = client.post(
            "/api/expert/nl-search",
            json={"query": "how do I bulk edit", "connection_id": "missing-id"},
        )
    assert res.status_code == 200
    assert "hits" in res.json()


def test_expert_post_chatter_requires_confirm() -> None:
    with TestClient(app) as client:
        res = client.post(
            "/api/expert/post-to-chatter",
            json={
                "connection_id": "x",
                "model": "x_test",
                "res_id": 1,
                "body_markdown": "hello",
                "confirmed": False,
            },
        )
    assert res.status_code == 400
