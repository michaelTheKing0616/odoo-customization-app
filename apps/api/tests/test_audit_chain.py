"""Hash-chained audit log — pure verify/redact and optional Postgres integration."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.audit_chain import (
    ACCOUNTING_KINDS,
    GENESIS_PREV_HASH,
    RAW_LLM_KINDS,
    InProcessChainRecord,
    append_entry,
    chain_hash,
    redact_payload,
    retention_decision,
    sweep_side_copies,
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


def _side_record(
    *,
    kind: str,
    recorded: datetime,
    prev: str,
    side_copy: dict,
) -> InProcessChainRecord:
    entry = _make_entry(
        ts=recorded.isoformat(),
        run_id=None,
        actor="system",
        kind=kind,
        payload={"kept": True},
        prev=prev,
    )
    return InProcessChainRecord(entry=entry, recorded_at=recorded, side_copy=side_copy)


@pytest.mark.no_app_db
def test_side_copy_retention_sweep_keeps_entry_hash() -> None:
    """Raw LLM side copies expire at 7 days + 1s.

    Accounting kinds are still kept at 24 months. Other kinds expire at
    24 months + 1s. Sweeping clears only the side copy.
    """
    assert RAW_LLM_KINDS
    assert ACCOUNTING_KINDS
    assert RAW_LLM_KINDS.isdisjoint(ACCOUNTING_KINDS)
    raw_kind = min(RAW_LLM_KINDS)
    accounting_kind = min(ACCOUNTING_KINDS)
    normal_kind = "http_mutation"
    assert normal_kind not in RAW_LLM_KINDS
    assert normal_kind not in ACCOUNTING_KINDS

    recorded = datetime(2024, 1, 31, 15, 30, tzinfo=UTC)
    seven_days_and_one = recorded + timedelta(days=7, seconds=1)
    # 24 calendar months later, not 730 days (that lands a day earlier).
    twenty_four_months = datetime(2026, 1, 31, 15, 30, tzinfo=UTC)
    twenty_four_months_and_one = datetime(2026, 1, 31, 15, 30, 1, tzinfo=UTC)
    day_before_anniversary = twenty_four_months - timedelta(days=1)
    seven_years_and_one = datetime(2031, 1, 31, 15, 30, 1, tzinfo=UTC)

    assert retention_decision(
        kind=raw_kind, recorded_at=recorded, now=seven_days_and_one
    ).eligible is True
    assert retention_decision(
        kind=accounting_kind, recorded_at=recorded, now=twenty_four_months
    ).eligible is False
    assert retention_decision(
        kind=accounting_kind, recorded_at=recorded, now=twenty_four_months_and_one
    ).eligible is False
    assert retention_decision(
        kind=normal_kind, recorded_at=recorded, now=day_before_anniversary
    ).eligible is False
    assert retention_decision(
        kind=normal_kind, recorded_at=recorded, now=twenty_four_months_and_one
    ).eligible is True
    assert retention_decision(
        kind=accounting_kind, recorded_at=recorded, now=seven_years_and_one
    ).eligible is True

    prev = GENESIS_PREV_HASH
    records: list[InProcessChainRecord] = []
    for kind, side in (
        (raw_kind, {"raw_llm": "prompt text"}),
        (accounting_kind, {"journal": "sale"}),
        (normal_kind, {"detail": "http"}),
    ):
        record = _side_record(kind=kind, recorded=recorded, prev=prev, side_copy=side)
        records.append(record)
        prev = record.entry["entry_hash"]

    hashes = [record.entry["entry_hash"] for record in records]
    payloads = [dict(record.entry["payload"]) for record in records]
    entries = [record.entry for record in records]

    assert sweep_side_copies(records, now=seven_days_and_one) == 1
    assert records[0].side_copy is None
    assert records[1].side_copy == {"journal": "sale"}
    assert records[2].side_copy == {"detail": "http"}

    assert sweep_side_copies(records, now=twenty_four_months) == 0
    assert records[1].side_copy is not None
    assert records[2].side_copy is not None

    assert sweep_side_copies(records, now=twenty_four_months_and_one) == 1
    assert records[1].side_copy == {"journal": "sale"}
    assert records[2].side_copy is None

    assert sweep_side_copies(records, now=seven_years_and_one) == 1
    assert records[1].side_copy is None

    for record, entry_hash, payload, entry in zip(records, hashes, payloads, entries, strict=True):
        assert record.entry is entry
        assert record.entry["entry_hash"] == entry_hash
        assert record.entry["payload"] == payload

    ok, bad = verify_chain(entries)
    assert ok is True
    assert bad is None


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
