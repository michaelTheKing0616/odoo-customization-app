"""Phase 7 auth tests — monkeypatch settings.auth_mode."""

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

from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health_reports_auth_flag(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert "auth_enabled" in res.json()


def test_auth_status_public(client: TestClient) -> None:
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    body = res.json()
    assert "auth_mode" in body
    assert "bootstrap_available" in body


def test_api_key_required_when_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", "oc_test_secret_key_phase7")

    denied = client.get("/api/connections")
    assert denied.status_code == 401

    ok = client.get(
        "/api/connections",
        headers={"Authorization": "Bearer oc_test_secret_key_phase7"},
    )
    assert ok.status_code == 200


def test_bootstrap_creates_first_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db import SessionLocal
    from app.db_models import AppApiKey

    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", None)

    db = SessionLocal()
    try:
        for row in db.query(AppApiKey).all():
            db.delete(row)
        db.commit()
    finally:
        db.close()

    boot = client.post("/api/auth/bootstrap")
    assert boot.status_code == 200, boot.text
    key = boot.json()["api_key"]
    assert key.startswith("oc_")

    listed = client.get("/api/auth/keys", headers={"Authorization": f"Bearer {key}"})
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    again = client.post("/api/auth/bootstrap")
    assert again.status_code == 409
