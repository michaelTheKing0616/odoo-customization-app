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
from app.db_models import (
    ConnectionProductionReadiness,
    HealthCheckRun,
    MetadataSnapshot,
    OdooConnection,
)  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402
from app.production_readiness import evaluate_production_readiness, run_snapshot_drill  # noqa: E402


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
    monkeypatch.setattr(
        "app.production_readiness._live_export_csv",
        lambda _connection: (
            "id,name,currency_id\n1,My Company,USD\n",
            "res.company",
            "live:res.company",
        ),
    )
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
    assert "production-readiness-drill" not in artifact.text
    # Real export: company CSV headers or tracked snapshot content
    assert ("id,name,currency_id" in artifact.text) or ("id,model,name" in artifact.text) or ("arch_present" in artifact.text) or len(artifact.text.strip().splitlines()) >= 2


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


def test_evaluate_todos_without_probe() -> None:
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
        assert cap.status == "todo"
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


def test_incomplete_checklist_uses_todo_not_fail() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="todo-check",
            url="https://experiment-company.odoo.com",
            db_name="experiment-company",
            username="builder",
            secret_encrypted=encrypt_secret("x"),
            server_version="19.0+e",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        report = evaluate_production_readiness(db, conn)
        statuses = {i.key: i.status for i in report.items}
        assert statuses["snapshot_restore_drill"] == "todo"
        assert statuses["backup_artifact_verified"] == "todo"
        assert statuses["least_privilege_confirmed"] == "todo"
        assert statuses["capability_matrix_probed"] == "pass"
        assert report.passed is False
        assert all(s != "fail" for k, s in statuses.items() if k != "health_check_green")
    finally:
        db.close()


def test_broken_health_is_fail_not_todo() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="broken-health",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="builder",
            secret_encrypted=encrypt_secret("x"),
            server_version="19.0",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        db.add(
            HealthCheckRun(
                connection_id=conn.id,
                status="complete",
                ok_count=0,
                broken_count=2,
                report_json="[]",
                message="broken",
            )
        )
        db.commit()
        report = evaluate_production_readiness(db, conn)
        health = next(i for i in report.items if i.key == "health_check_green")
        assert health.status == "fail"
        assert "2 broken" in health.detail
    finally:
        db.close()


def test_drill_prefers_tracked_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="tracked",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="builder",
            secret_encrypted=encrypt_secret("x"),
            server_version="19.0",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        tracked = MetadataSnapshot(
            connection_id=conn.id,
            resource_type="view",
            resource_key="view:42",
            label="Sale order form",
            payload_json=json.dumps({"view": {"id": 42, "name": "sale.order.form", "arch": "<form/>"}}),
            reversible="yes",
        )
        db.add(tracked)
        db.commit()

        def _boom(_connection):
            raise AssertionError("live export should not run when tracked snapshot exists")

        monkeypatch.setattr("app.production_readiness._live_export_csv", _boom)
        snap_id = run_snapshot_drill(db, conn)
        snap = db.get(MetadataSnapshot, snap_id)
        payload = json.loads(snap.payload_json)
        assert payload["source"].startswith("tracked:")
        assert "sale.order.form" in payload["csv"]
        assert "production-readiness-drill" not in payload["csv"]
    finally:
        db.close()

