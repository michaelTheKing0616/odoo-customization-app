"""TRUST-2 SafetyGate unit tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_models import Workspace  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import DryRunReceipt, MetadataSnapshot, OdooConnection  # noqa: E402
from app.safety_gate import SafetyGate, SafetyGateError, SafetySpec, params_fingerprint  # noqa: E402


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _connection(**overrides) -> OdooConnection:
    base = dict(
        id=str(uuid.uuid4()),
        name="Test",
        url="http://127.0.0.1:8069",
        db_name="odoo",
        username="admin",
        secret_encrypted="enc",
        write_mode="standard",
        writes_paused=False,
    )
    base.update(overrides)
    return OdooConnection(**base)


def test_preflight_checks_writes_paused_before_write_mode(db) -> None:
    conn = _connection(writes_paused=True, write_mode="observer")
    ws = Workspace(id="ws-1", name="W", slug="w", plan="free_solo", writes_paused=False)
    gate = SafetyGate(db, connection=conn, workspace=ws)
    spec = SafetySpec(risk="reversible", odoo_mutation=True)
    with pytest.raises(SafetyGateError) as exc:
        gate.preflight(spec)
    assert exc.value.refusal.code == "writes_paused"


def _persist_connection(db, **overrides) -> OdooConnection:
    conn = _connection(**overrides)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def _persist_snapshot(
    db,
    connection_id: str,
    *,
    created_at: datetime | None = None,
) -> MetadataSnapshot:
    snap = MetadataSnapshot(
        connection_id=connection_id,
        resource_type="view",
        resource_key="view:1",
        label="preflight-snap",
        payload_json="{}",
        reversible="yes",
    )
    if created_at is not None:
        snap.created_at = created_at
    db.add(snap)
    db.commit()
    db.refresh(snap)
    if created_at is not None:
        snap.created_at = created_at
        db.add(snap)
        db.commit()
        db.refresh(snap)
    return snap


def test_preflight_production_two_hour_old_snapshot_refused(db) -> None:
    conn = _persist_connection(db, write_mode="production")
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    stale = _persist_snapshot(db, conn.id, created_at=now - timedelta(hours=2))
    gate = SafetyGate(db, connection=conn)
    spec = SafetySpec(risk="destructive")
    with pytest.raises(SafetyGateError) as exc:
        gate.preflight(spec, snapshot_id=stale.id, now=now)
    assert exc.value.refusal.code == "snapshot_required"
    assert "10-minute freshness window" in exc.value.refusal.message


def test_preflight_production_snapshot_from_other_connection_refused(db) -> None:
    conn = _persist_connection(db, write_mode="production")
    other = _persist_connection(db, write_mode="production")
    foreign = _persist_snapshot(db, other.id)
    gate = SafetyGate(db, connection=conn)
    spec = SafetySpec(risk="destructive")
    with pytest.raises(SafetyGateError) as exc:
        gate.preflight(spec, snapshot_id=foreign.id)
    assert exc.value.refusal.code == "snapshot_required"
    assert "different connection" in exc.value.refusal.message


def test_preflight_production_billable_method_without_fresh_snapshot_refused(db) -> None:
    conn = _persist_connection(db, write_mode="production")
    gate = SafetyGate(db, connection=conn)
    spec = SafetySpec(risk="reversible")
    with pytest.raises(SafetyGateError) as exc:
        gate.preflight(spec, method="button_install")
    assert exc.value.refusal.code == "snapshot_required"


def test_preflight_passes_connection_server_version_major(monkeypatch) -> None:
    seen: dict = {}

    def _capture(**kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.setattr("app.safety_gate.require_production_snapshot", _capture)
    conn = _connection(server_version="21.0", write_mode="standard")
    SafetyGate(None, connection=conn).preflight(SafetySpec(risk="destructive"))  # type: ignore[arg-type]
    assert seen["odoo_major"] == 21


def test_preflight_missing_server_version_passes_none(monkeypatch) -> None:
    seen: dict = {}

    def _capture(**kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.setattr("app.safety_gate.require_production_snapshot", _capture)
    conn = _connection(write_mode="standard")
    SafetyGate(None, connection=conn).preflight(SafetySpec(risk="destructive"))  # type: ignore[arg-type]
    assert seen["odoo_major"] is None


def test_preflight_blank_server_version_passes_none(monkeypatch) -> None:
    seen: dict = {}

    def _capture(**kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.setattr("app.safety_gate.require_production_snapshot", _capture)
    conn = _connection(server_version="  ", write_mode="standard")
    SafetyGate(None, connection=conn).preflight(SafetySpec(risk="destructive"))  # type: ignore[arg-type]
    assert seen["odoo_major"] is None


def test_preflight_observer_mode(db) -> None:
    conn = _connection(write_mode="observer")
    gate = SafetyGate(db, connection=conn)
    spec = SafetySpec(risk="reversible", odoo_mutation=True)
    with pytest.raises(SafetyGateError) as exc:
        gate.preflight(spec)
    assert exc.value.refusal.code == "observer_mode"


def test_dry_run_receipt_issue_and_consume(db) -> None:
    conn = _connection()
    db.add(conn)
    db.commit()
    gate = SafetyGate(db, connection=conn)
    params = {"model": "res.partner", "method": "action_confirm", "ids": [1, 2]}
    token = gate.issue_dry_run_receipt(
        connection_id=conn.id,
        operation="bulk.transitions.run",
        params=params,
    )
    spec = SafetySpec(risk="reversible", dry_run_first=True)
    gate.require_dry_run_receipt(
        spec,
        connection_id=conn.id,
        operation="bulk.transitions.run",
        params=params,
        receipt_token=token,
    )
    with pytest.raises(SafetyGateError) as exc:
        gate.require_dry_run_receipt(
            spec,
            connection_id=conn.id,
            operation="bulk.transitions.run",
            params=params,
            receipt_token=token,
        )
    assert exc.value.refusal.code == "dry_run_receipt_invalid"


def test_dry_run_receipt_rejects_param_drift(db) -> None:
    conn = _connection()
    db.add(conn)
    db.commit()
    gate = SafetyGate(db, connection=conn)
    params = {"model": "res.partner", "ids": [1]}
    token = gate.issue_dry_run_receipt(
        connection_id=conn.id,
        operation="op",
        params=params,
    )
    spec = SafetySpec(risk="reversible", dry_run_first=True)
    with pytest.raises(SafetyGateError) as exc:
        gate.require_dry_run_receipt(
            spec,
            connection_id=conn.id,
            operation="op",
            params={"model": "res.partner", "ids": [1, 2]},
            receipt_token=token,
        )
    assert exc.value.refusal.code == "dry_run_receipt_invalid"


def test_dry_run_receipt_expired(db) -> None:
    conn = _connection()
    db.add(conn)
    db.commit()
    token = str(uuid.uuid4())
    import hashlib

    params = {"x": 1}
    row = DryRunReceipt(
        connection_id=conn.id,
        operation="op",
        params_hash=params_fingerprint(params),
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(row)
    db.commit()
    gate = SafetyGate(db, connection=conn)
    spec = SafetySpec(risk="reversible", dry_run_first=True)
    with pytest.raises(SafetyGateError) as exc:
        gate.require_dry_run_receipt(
            spec,
            connection_id=conn.id,
            operation="op",
            params={"x": 1},
            receipt_token=token,
        )
    assert exc.value.refusal.code == "dry_run_receipt_invalid"
