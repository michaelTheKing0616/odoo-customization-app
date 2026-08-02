"""Audit log middleware tests."""

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
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import AuditLog  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_mutating_request_writes_audit_row(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    before = SessionLocal().query(AuditLog).count()
    # Invalid body still mutates → still audited
    res = client.post("/api/connections", json={})
    assert res.status_code in {400, 422}
    after = SessionLocal().query(AuditLog).count()
    assert after >= before + 1
    row = SessionLocal().query(AuditLog).order_by(AuditLog.created_at.desc()).first()
    assert row is not None
    assert row.method == "POST"
    assert row.path.startswith("/api/connections")


def test_get_skips_audit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    before = SessionLocal().query(AuditLog).count()
    res = client.get("/health")
    assert res.status_code == 200
    after = SessionLocal().query(AuditLog).count()
    assert after == before


def test_list_audit_logs(client: TestClient) -> None:
    client.post("/api/connections", json={})
    res = client.get("/api/audit/logs?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    if body:
        assert "method" in body[0]
        assert "path" in body[0]
        assert "status_code" in body[0]
