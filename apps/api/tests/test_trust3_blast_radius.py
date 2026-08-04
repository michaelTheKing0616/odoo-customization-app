"""TRUST-3 blast-radius tests."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("BULK_SAMPLE_FIRST_THRESHOLD", "50")
os.environ.setdefault("BULK_SAMPLE_SIZE", "10")
os.environ.setdefault("BULK_ANOMALY_HOURLY_LIMIT", "5")

from app.blast_radius import clamp_request_cap, plan_execution_ids  # noqa: E402
from app.bulk_suite.executor import execute_in_batches  # noqa: E402
from app.bulk_suite.transitions import PerRecordResult, run_bulk_transition  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.anomaly_guard import record_connection_mutations  # noqa: E402


def test_plan_execution_ids_sample_first() -> None:
    ids = list(range(1, 101))
    execute, pending, paused = plan_execution_ids(ids)
    assert paused is True
    assert len(execute) == 10
    assert len(pending) == 90


def test_plan_execution_ids_skips_when_continue() -> None:
    ids = list(range(1, 101))
    execute, pending, paused = plan_execution_ids(ids, continue_after_sample=True)
    assert paused is False
    assert execute == ids
    assert pending == []


def test_clamp_request_cap_by_risk() -> None:
    assert clamp_request_cap(5000, "destructive") == 200
    assert clamp_request_cap(5000, "reversible") == 1000


def test_execute_in_batches_aborts_between_batches() -> None:
    calls: list[int] = []

    def execute_chunk(chunk: list[int]) -> list[PerRecordResult]:
        calls.append(len(chunk))
        return [PerRecordResult(id=i, display_name=str(i), ok=True) for i in chunk]

    batch_num = {"n": 0}

    def should_abort() -> bool:
        return batch_num["n"] > 1

    def execute_chunk_counting(chunk: list[int]) -> list[PerRecordResult]:
        batch_num["n"] += 1
        return execute_chunk(chunk)

    results, aborted, pending = execute_in_batches(
        list(range(1, 11)),
        execute_chunk_counting,
        batch_size=3,
        sleep_ms=0,
        should_abort=should_abort,
    )
    assert aborted is True
    assert len(results) == 6
    assert pending == [7, 8, 9, 10]


def test_run_bulk_transition_sample_paused_status() -> None:
    client = MagicMock()

    def execute_kw(model, method, args, kwargs=None):
        if method == "read":
            ids = args[0]
            return [{"id": i, "display_name": f"R{i}"} for i in ids]
        return True

    client.execute_kw.side_effect = execute_kw

    result = run_bulk_transition(
        client,
        model="x.test",
        method="action_confirm",
        record_ids=list(range(1, 11)),
        dry_run=False,
        pending_ids=list(range(11, 61)),
        status="sample_paused",
    )
    assert result.status == "sample_paused"
    assert len(result.pending_ids) == 50
    assert result.processed_count == 10


def test_anomaly_guard_auto_pauses_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "bulk_anomaly_hourly_limit", 5)
    init_db()
    session = SessionLocal()
    try:
        conn = OdooConnection(
            id=str(uuid.uuid4()),
            name="Anomaly",
            url="http://127.0.0.1:8069",
            db_name="odoo",
            username="admin",
            secret_encrypted="enc",
            write_mode="standard",
        )
        session.add(conn)
        session.commit()
        event = record_connection_mutations(
            session,
            connection_id=conn.id,
            mutation_count=5,
            workspace=None,
        )
        assert event is not None
        session.refresh(conn)
        assert conn.writes_paused is True
    finally:
        session.close()
