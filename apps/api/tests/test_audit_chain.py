"""Hash-chained audit log — pure verify/redact and optional Postgres integration."""

from __future__ import annotations

import os
import uuid

import pytest

from app.audit_chain import (
    GENESIS_PREV_HASH,
    append_entry,
    chain_hash,
    redact_payload,
    verify_chain,
    verify_db,
)


def _make_entry(
    *,
    ts: str,
    run_id: str | None,
    actor: str,
    kind: str,
    payload: dict,
    prev: str,
) -> dict:
    body = {
        "ts": ts,
        "run_id": run_id,
        "actor": actor,
        "kind": kind,
        "payload": payload,
        "prev": prev,
    }
    return {**body, "entry_hash": chain_hash(body)}


@pytest.mark.no_app_db
def test_audit_chain_and_tamper() -> None:
    e0 = _make_entry(
        ts="2026-10-02T12:00:00+00:00",
        run_id=None,
        actor="system",
        kind="test",
        payload={"step": 0},
        prev=GENESIS_PREV_HASH,
    )
    e1 = _make_entry(
        ts="2026-10-02T12:00:01+00:00",
        run_id="run-a",
        actor="user",
        kind="test",
        payload={"step": 1},
        prev=e0["entry_hash"],
    )
    e2 = _make_entry(
        ts="2026-10-02T12:00:02+00:00",
        run_id="run-a",
        actor="user",
        kind="test",
        payload={"step": 2},
        prev=e1["entry_hash"],
    )
    ok, bad = verify_chain([e0, e1, e2])
    assert ok is True
    assert bad is None

    tampered = {**e1, "payload": {"step": 1, "extra": "evil"}}
    ok2, bad2 = verify_chain([e0, tampered, e2])
    assert ok2 is False
    assert bad2 == 1


@pytest.mark.no_app_db
def test_redaction() -> None:
    out = redact_payload({"name": "Ada", "password": "secret", "api_key": "k"})
    assert out["name"] == "Ada"
    assert out["password"] == "[redacted]"
    assert out["api_key"] == "[redacted]"


@pytest.mark.no_app_db
def test_redaction_tuple_args_and_private_key() -> None:
    out = redact_payload({"args": ({"password": "x"},)})
    assert out["args"][0]["password"] == "[redacted]"
    assert isinstance(out["args"], tuple)
    assert redact_payload({"private_key": "pem"})["private_key"] == "[redacted]"


@pytest.mark.no_app_db
def test_genesis_prev_is_zeros() -> None:
    assert GENESIS_PREV_HASH == "0" * 64
    e0 = _make_entry(
        ts="2026-10-02T12:00:00+00:00",
        run_id=None,
        actor="system",
        kind="genesis",
        payload={},
        prev=GENESIS_PREV_HASH,
    )
    ok, bad = verify_chain([e0])
    assert ok is True
    assert bad is None

    bad_prev = {**e0, "prev": "1" * 64}
    ok2, bad2 = verify_chain([bad_prev])
    assert ok2 is False
    assert bad2 == 0


_INTEGRATION_URL = "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"


def _postgres_integration_available() -> bool:
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg not installed")
    try:
        with psycopg.connect(
            "host=127.0.0.1 port=5433 dbname=odoo_custom user=odoo_custom password=odoo_custom"
        ) as conn:
            conn.execute("SELECT 1")
    except Exception:
        pytest.skip("Postgres audit_chain integration DB not reachable")
    return True


def test_append_two_rows_verify_db() -> None:
    _postgres_integration_available()
    os.environ["DATABASE_URL"] = _INTEGRATION_URL
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.db_models import AuditChainEntry

    engine = create_engine(_INTEGRATION_URL, pool_pre_ping=True)
    AuditChainEntry.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE audit_chain_entries "
                "ADD COLUMN IF NOT EXISTS canonical_ts VARCHAR(64)"
            )
        )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    suffix = uuid.uuid4().hex[:8]
    try:
        append_entry(
            db,
            actor=f"test-{suffix}",
            kind="integration",
            payload={"n": 1},
            run_id=f"run-{suffix}",
        )
        append_entry(
            db,
            actor=f"test-{suffix}",
            kind="integration",
            payload={"n": 2},
            run_id=f"run-{suffix}",
        )
        ok, bad = verify_db(db)
        assert ok is True
        assert bad is None
    finally:
        db.query(AuditChainEntry).filter(AuditChainEntry.actor == f"test-{suffix}").delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
