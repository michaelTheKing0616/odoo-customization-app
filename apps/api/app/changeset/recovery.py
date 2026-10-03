"""Crash recovery. A partial apply is never reported as finished.

``recover`` classifies a journal snapshot. ``recover_stale_applying`` is the
recovery job: it finds an APPLYING run whose heartbeat is stale and
compensates from that journal. Both take an in-memory list. Neither opens a
database connection. The durable table shapes live in the Alembic revision
``s9t0u1v2w3x4``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_ALLOWED = frozenset({"VERIFIED", "ROLLED_BACK", "NEEDS_HUMAN"})

# A heartbeat older than this is stale. Detection does not wait out the SLO.
STALE_HEARTBEAT = timedelta(seconds=60)
# Stale APPLYING must be noticeable inside this window (heartbeat 5s + 60s).
STALE_DETECT_SLO = timedelta(minutes=2)


def recover(entries: list[dict[str, Any]], *, mode: str, expected_ops: int) -> dict[str, Any]:
    if mode not in {"T", "C"}:
        raise ValueError("mode must be T or C")
    if expected_ops < 0:
        raise ValueError("expected_ops")
    results = [entry for entry in entries if entry.get("kind") == "RESULT"]
    compensates = [entry for entry in entries if entry.get("kind") == "COMPENSATE"]
    verified = any(entry.get("kind") == "VERIFIED" for entry in entries)
    verifying = any(entry.get("kind") == "VERIFYING" for entry in entries)
    result_indexes = [entry.get("index") for entry in results]
    report = {
        "results": result_indexes,
        "missing": [index for index in range(expected_ops) if index not in result_indexes],
        "compensates": [entry.get("index") for entry in compensates],
    }
    if any(entry.get("kind") == "UNKNOWN" for entry in entries):
        return {"status": "NEEDS_HUMAN", "report": report}
    compensated = set(report["compensates"]) >= set(result_indexes)
    if verified and not report["missing"] and len(results) == expected_ops:
        status = "VERIFIED"
    elif verified or (verifying and not results):
        status = "NEEDS_HUMAN"
    elif not results:
        status = "ROLLED_BACK"
    elif mode == "T":
        status = "ROLLED_BACK" if report["missing"] else "NEEDS_HUMAN"
    elif compensated:
        status = "ROLLED_BACK"
    else:
        status = "NEEDS_HUMAN"
    if status not in _ALLOWED or (status == "VERIFIED" and report["missing"]):
        status = "NEEDS_HUMAN"
    return {"status": status, "report": report}


class DatabaseApplyLock:
    """In-memory stand-in for ``apply_database_lock``.

    One holder per Odoo database. A second run cannot acquire the same
    database until the holder releases it.

    Inputs: database name and run id.
    Outputs: acquire returns True when this run holds the database.
    Side effects: mutates the in-memory map. Does not touch Postgres or Odoo.
    """

    def __init__(self) -> None:
        self._held: dict[str, dict[str, Any]] = {}

    def acquire(self, odoo_database: str, run_id: str, *, now: datetime) -> bool:
        if not odoo_database:
            raise ValueError("odoo_database")
        if not run_id:
            raise ValueError("run_id")
        current = self._held.get(odoo_database)
        if current is None:
            self._held[odoo_database] = {"run_id": run_id, "heartbeat": now}
            return True
        if current["run_id"] == run_id:
            current["heartbeat"] = now
            return True
        return False

    def release(self, odoo_database: str, run_id: str) -> None:
        current = self._held.get(odoo_database)
        if current is not None and current["run_id"] == run_id:
            del self._held[odoo_database]

    def holder(self, odoo_database: str) -> str | None:
        current = self._held.get(odoo_database)
        if current is None:
            return None
        return str(current["run_id"])

    def clear(self) -> None:
        self._held.clear()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _heartbeat(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("heartbeat")
    if raw is None:
        raw = entry.get("heartbeat_at")
    if isinstance(raw, datetime):
        return _as_utc(raw)
    if isinstance(raw, str) and raw:
        parsed = datetime.fromisoformat(raw)
        return _as_utc(parsed)
    return None


def _by_run(journal: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in journal:
        run_id = entry.get("run_id")
        if isinstance(run_id, str) and run_id:
            grouped.setdefault(run_id, []).append(entry)
    return grouped


def _is_applying(entries: list[dict[str, Any]]) -> bool:
    if any(entry.get("kind") in {"VERIFIED", "COMPENSATE", "ERROR"} for entry in entries):
        return False
    return any(entry.get("status") == "APPLYING" or entry.get("run_status") == "APPLYING" for entry in entries)


def _is_stale(entries: list[dict[str, Any]], *, now: datetime) -> bool:
    stamps = [stamp for stamp in (_heartbeat(entry) for entry in entries) if stamp is not None]
    if not stamps:
        return True
    return now - max(stamps) >= STALE_HEARTBEAT


def find_stale_applying(journal: list[dict[str, Any]], *, now: datetime) -> list[str]:
    """Run ids that are APPLYING and whose heartbeat is at least 60s old.

    Inputs: journal rows and the clock.
    Outputs: run ids, oldest heartbeat first. Empty when every APPLYING run
    is still inside the heartbeat window.
    Side effects: none. A heartbeat aged 60s is already inside the 2-minute
    detection SLO, so this does not wait for ``STALE_DETECT_SLO``.
    """
    now = _as_utc(now)
    stale: list[tuple[datetime, str]] = []
    for run_id, entries in _by_run(journal).items():
        if not _is_applying(entries) or not _is_stale(entries, now=now):
            continue
        stamps = [stamp for stamp in (_heartbeat(entry) for entry in entries) if stamp is not None]
        oldest = min(stamps) if stamps else now - STALE_DETECT_SLO
        stale.append((oldest, run_id))
    stale.sort()
    return [run_id for _stamp, run_id in stale]


def _compensate_intent(journal: list[dict[str, Any]], entries: list[dict[str, Any]], run_id: str) -> None:
    indexes = [
        entry.get("index")
        for entry in entries
        if entry.get("kind") == "INTENT" and isinstance(entry.get("index"), int)
    ]
    if indexes:
        for index in sorted(set(indexes), reverse=True):
            journal.append(
                {
                    "kind": "COMPENSATE",
                    "run_id": run_id,
                    "index": index,
                    "status": "ROLLED_BACK",
                }
            )
        return
    journal.append({"kind": "COMPENSATE", "run_id": run_id, "status": "ROLLED_BACK"})


def recover_stale_applying(
    journal: list[dict[str, Any]],
    *,
    now: datetime,
    locks: DatabaseApplyLock | None = None,
) -> dict[str, Any]:
    """Compensate a stale APPLYING run. Never report it as verified.

    Inputs: journal rows (mutated), clock, optional in-memory database lock.
    Outputs: ``verified`` is always False. A journal that has INTENT and no
    RESULT gains COMPENSATE rows and status ROLLED_BACK. An UNKNOWN row
    becomes NEEDS_HUMAN. This function has no write port, so it cannot retry
    a write.
    Side effects: appends COMPENSATE or ERROR rows. Releases a matching lock.
    Does not call Odoo and does not open Postgres.
    """
    runs: list[dict[str, Any]] = []
    for run_id in find_stale_applying(journal, now=now):
        entries = [entry for entry in journal if entry.get("run_id") == run_id]
        kinds = {entry.get("kind") for entry in entries}
        odoo_database = next(
            (entry.get("odoo_database") for entry in entries if isinstance(entry.get("odoo_database"), str)),
            "",
        )
        if "UNKNOWN" in kinds:
            if "ERROR" not in kinds:
                journal.append(
                    {
                        "kind": "ERROR",
                        "run_id": run_id,
                        "status": "NEEDS_HUMAN",
                        "reason": "unknown_outcome",
                    }
                )
            outcome = {"run_id": run_id, "status": "NEEDS_HUMAN", "verified": False, "compensated": False}
        elif "RESULT" not in kinds and "INTENT" in kinds:
            _compensate_intent(journal, entries, run_id)
            outcome = {"run_id": run_id, "status": "ROLLED_BACK", "verified": False, "compensated": True}
        else:
            outcome = {"run_id": run_id, "status": "NEEDS_HUMAN", "verified": False, "compensated": False}
        if locks is not None and isinstance(odoo_database, str) and odoo_database:
            locks.release(odoo_database, run_id)
        if outcome["status"] == "VERIFIED":
            outcome["status"] = "NEEDS_HUMAN"
            outcome["verified"] = False
        runs.append(outcome)

    if not runs:
        return {"status": "IDLE", "verified": False, "retried_write": False, "runs": []}
    status = "NEEDS_HUMAN" if any(run["status"] == "NEEDS_HUMAN" for run in runs) else "ROLLED_BACK"
    if status == "VERIFIED":
        status = "NEEDS_HUMAN"
    return {"status": status, "verified": False, "retried_write": False, "runs": runs}
