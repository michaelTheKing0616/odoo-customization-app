"""TRUST-8 production readiness checklist + production write-mode gate."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import ConnectionProductionReadiness, HealthCheckRun, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402
from app.production_readiness import evaluate_production_readiness  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn(*, username: str = "custom_user", version: str | None = "19.0") -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="readiness",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username=username,
            secret_encrypted=encrypt_secret("secret"),
            write_mode="standard",
            server_version=version,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def test_production_mode_blocked_until_checklist(client: TestClient) -> None:
    conn = _conn()
    resp = client.patch(
        f"/api/connections/{conn.id}/write-mode",
        json={"write_mode": "production"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "production_readiness_required"


def test_snapshot_drill_and_full_checklist_pass(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "production_write_mode_ga_unlocked", True)
    conn = _conn()
    drill = client.post(f"/api/connections/{conn.id}/production-readiness/snapshot-drill")
    assert drill.status_code == 200, drill.text
    snap_id = drill.json()["snapshot_id"]

    confirm = client.post(
        f"/api/connections/{conn.id}/production-readiness/confirm-least-privilege",
        json={"acknowledge_admin": False},
    )
    assert confirm.status_code == 200, confirm.text

    db = SessionLocal()
    try:
        db.add(
            HealthCheckRun(
                connection_id=conn.id,
                status="complete",
                ok_count=1,
                broken_count=0,
                report_json="[]",
                message="ok",
            )
        )
        db.commit()
    finally:
        db.close()

    verify = client.post(
        f"/api/connections/{conn.id}/production-readiness/verify-backup-artifact",
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["passed"] is True

    unlock = client.patch(
        f"/api/connections/{conn.id}/write-mode",
        json={"write_mode": "production"},
    )
    assert unlock.status_code == 200, unlock.text
    assert unlock.json()["write_mode"] == "production"

    artifact = client.get(f"/api/connections/{conn.id}/snapshots/{snap_id}/artifact.csv")
    assert artifact.status_code == 200
    assert "production-readiness-drill" in artifact.text


def test_admin_user_requires_acknowledge(client: TestClient) -> None:
    conn = _conn(username="admin")
    denied = client.post(
        f"/api/connections/{conn.id}/production-readiness/confirm-least-privilege",
        json={"acknowledge_admin": False},
    )
    assert denied.status_code == 400

    ok = client.post(
        f"/api/connections/{conn.id}/production-readiness/confirm-least-privilege",
        json={"acknowledge_admin": True},
    )
    assert ok.status_code == 200
    item = next(i for i in ok.json()["items"] if i["key"] == "least_privilege_confirmed")
    assert item["status"] == "warn"


def test_trust_safety_markdown_endpoint(client: TestClient) -> None:
    res = client.get("/api/trust/safety")
    assert res.status_code == 200
    body = res.json()
    assert "Reversibility" in body["markdown"]
    assert body["source"] == "docs/SAFETY.md"


def test_evaluate_fails_without_probe() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="no-probe",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="builder",
            secret_encrypted=encrypt_secret("x"),
            server_version=None,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        report = evaluate_production_readiness(db, conn)
        assert report.passed is False
        cap = next(i for i in report.items if i.key == "capability_matrix_probed")
        assert cap.status == "fail"
    finally:
        db.close()


def test_first_write_ack_persisted(client: TestClient) -> None:
    conn = _conn()
    res = client.post(f"/api/connections/{conn.id}/production-readiness/ack-first-write")
    assert res.status_code == 200
    assert res.json()["first_write_acknowledged"] is True

    db = SessionLocal()
    try:
        state = db.get(ConnectionProductionReadiness, conn.id)
        assert state is not None
        assert state.first_write_ack_at is not None
    finally:
        db.close()
