"""AI-8 API routes: propose-connect-points + generalize-component."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_propose_connect_points_route(client: TestClient) -> None:
    res = client.post(
        "/api/ai/propose-connect-points",
        json={
            "prompt": "add inspection checklist to project tasks",
            "gallery_id": "inspection_checklist",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["grain"] == "feature_slice"
    assert body["requires_review"] is True
    assert body["connect_points"]["host_model"] == "project.task"


def test_propose_connect_points_full_app(client: TestClient) -> None:
    res = client.post(
        "/api/ai/propose-connect-points",
        json={"prompt": "build a library management app from scratch", "grain": "full_app"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["grain"] == "full_app"
    assert body["requires_review"] is False


def test_generalize_component_requires_consent(client: TestClient) -> None:
    res = client.post(
        "/api/ai/generalize-component",
        json={"spec_json": {"technical_name": "x_test", "models": []}, "consent_share_template": False},
    )
    assert res.status_code == 403


def test_generalize_component_ok(client: TestClient) -> None:
    from app.ai_component_builder import draft_component_from_prompt

    draft, _, _ = draft_component_from_prompt(
        "add warranty to sale orders",
        available_models=["sale.order"],
        gallery_id="warranty_tracker",
    )
    res = client.post(
        "/api/ai/generalize-component",
        json={
            "spec_json": draft,
            "consent_share_template": True,
            "host_slot": "sale.order",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["host_slot"] == "sale.order"
    assert body["filename"].endswith(".py")
    assert "def candidate_pack" in body["source"] or "candidate_pack" in body["source"]
