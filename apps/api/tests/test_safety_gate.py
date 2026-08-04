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
from app.db_models import DryRunReceipt, OdooConnection  # noqa: E402
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
