"""WAL recovery on a fake journal. No database and no Odoo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.changeset.executor import UnknownOutcome, apply, get_journal, reset_journal
from app.changeset.recovery import (
    STALE_DETECT_SLO,
    STALE_HEARTBEAT,
    DatabaseApplyLock,
    find_stale_applying,
    recover_stale_applying,
)

_NOW = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)


def _field() -> dict:
    return {"type": "field.create", "params": {"model": "x_test.model", "name": "x_flag", "field_type": "char"}}


def _applying(run_id: str, *, age: timedelta, indexes: list[int] | None = None) -> list[dict]:
    heartbeat = (_NOW - age).isoformat()
    rows: list[dict] = [
        {
            "kind": "INTENT",
            "run_id": run_id,
            "status": "APPLYING",
            "mode": "C",
            "heartbeat": heartbeat,
            "odoo_database": "odoo-db",
            "op_count": 2,
        }
    ]
    for index in indexes or []:
        rows.append({"kind": "INTENT", "run_id": run_id, "index": index, "heartbeat": heartbeat})
        rows.append({"kind": "BEFORE", "run_id": run_id, "index": index})
    return rows


def test_intent_without_result_is_compensated_and_not_verified() -> None:
    journal = _applying("run-1", age=STALE_HEARTBEAT + timedelta(seconds=30), indexes=[0, 1])
    locks = DatabaseApplyLock()
    assert locks.acquire("odoo-db", "run-1", now=_NOW - STALE_HEARTBEAT)
    decision = recover_stale_applying(journal, now=_NOW, locks=locks)
    compensates = [entry for entry in journal if entry.get("kind") == "COMPENSATE"]
    assert [entry.get("index") for entry in compensates] == [1, 0]
    assert decision["status"] == "ROLLED_BACK"
    assert decision["verified"] is False
    assert decision["retried_write"] is False
    assert decision["runs"][0]["status"] != "VERIFIED"
    assert not any(entry.get("kind") == "RESULT" for entry in journal)
    assert not any(entry.get("kind") == "VERIFIED" for entry in journal)
    assert locks.holder("odoo-db") is None


def test_stale_applying_detected_within_two_minutes() -> None:
    assert STALE_HEARTBEAT < STALE_DETECT_SLO
    fresh = _applying("fresh", age=STALE_HEARTBEAT - timedelta(seconds=1))
    stale = _applying("stale", age=timedelta(seconds=90))
    assert timedelta(seconds=90) < STALE_DETECT_SLO
    assert find_stale_applying(fresh, now=_NOW) == []
    assert find_stale_applying(stale, now=_NOW) == ["stale"]
    inside_slo = _applying("inside", age=STALE_DETECT_SLO - timedelta(seconds=1))
    assert find_stale_applying(inside_slo, now=_NOW) == ["inside"]
    left_alone = recover_stale_applying(fresh, now=_NOW)
    assert left_alone["status"] == "IDLE"
    assert not any(entry.get("kind") == "COMPENSATE" for entry in fresh)


def test_unknown_outcome_does_not_retry_the_write() -> None:
    journal = _applying("run-unknown", age=timedelta(seconds=90))
    journal.append({"kind": "UNKNOWN", "run_id": "run-unknown", "index": 0})
    before = [dict(entry) for entry in journal]
    decision = recover_stale_applying(journal, now=_NOW)
    assert decision["status"] == "NEEDS_HUMAN"
    assert decision["verified"] is False
    assert decision["retried_write"] is False
    assert not any(entry.get("kind") == "RESULT" for entry in journal)
    assert not any(entry.get("kind") == "COMPENSATE" for entry in journal)
    assert [entry.get("kind") for entry in journal] == [entry.get("kind") for entry in before] + ["ERROR"]

    reset_journal()

    class _Port:
        def __init__(self) -> None:
            self.creates = 0
            self.writes = 0

        def create(self, model: str, values: dict) -> int:
            self.creates += 1
            raise UnknownOutcome()

        def write(self, model: str, ids: list[int], values: dict) -> None:
            self.writes += 1

    port = _Port()
    field = _field()
    first = apply([field], mode="T", port=port)
    second = apply([field], mode="T", port=port)
    assert first["status"] == "NEEDS_HUMAN"
    assert second["status"] == "NEEDS_HUMAN"
    assert first["applied_count"] == 0
    assert port.creates == 1
    assert port.writes == 0
    assert any(entry.get("kind") == "UNKNOWN" for entry in get_journal())
    assert not any(entry.get("kind") == "RESULT" for entry in get_journal())


def test_one_apply_per_odoo_database() -> None:
    lock = DatabaseApplyLock()
    assert lock.acquire("db-a", "run-1", now=_NOW) is True
    assert lock.acquire("db-a", "run-2", now=_NOW) is False
    assert lock.acquire("db-b", "run-2", now=_NOW) is True
    reset_journal()
    blocked = apply([_field()], mode="T", odoo_database="db-a", apply_lock=lock)
    assert blocked["status"] == "NEEDS_HUMAN"
    assert blocked["report"]["reason"] == "database_busy"
    assert get_journal() == []
    assert lock.holder("db-a") == "run-1"


def test_journal_migration_declares_wal_tables_and_is_not_applied_here() -> None:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "s9t0u1v2w3x4_journal_wal.py"
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "s9t0u1v2w3x4"' in text
    assert 'down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"' in text
    assert '"journal_entry"' in text
    assert '"before_image"' in text
    assert '"apply_database_lock"' in text
    assert "op.create_table" in text
