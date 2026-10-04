"""Hash-chained tamper-evident audit append API."""

from __future__ import annotations

import calendar
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import AuditChainEntry

GENESIS_PREV_HASH = "0" * 64

# No caller emits these kinds yet. Retention reads only this pair.
# Tests use these members; do not add a second copy of the names.
RAW_LLM_KINDS: frozenset[str] = frozenset({"llm_raw_payload"})
ACCOUNTING_KINDS: frozenset[str] = frozenset({"accounting"})

RAW_LLM_RETENTION_DAYS = 7
DEFAULT_RETENTION_MONTHS = 24
ACCOUNTING_RETENTION_YEARS = 7

_REDACT_KEY = re.compile(
    r"(?i)(pass|password|secret|token|api[_-]?key|smtp_pass|authorization|"
    r"private_key|ssh_key|encryption_key|signing_key)",
)


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with sensitive key names redacted."""

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for key, val in obj.items():
                key_name = key if isinstance(key, str) else str(key)
                if _REDACT_KEY.search(key_name):
                    out[key] = "[redacted]"
                else:
                    out[key] = _walk(val)
            return out
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        if isinstance(obj, tuple):
            return tuple(_walk(item) for item in obj)
        return obj

    return _walk(payload)


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def chain_hash(body_without_hash: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical JSON hash body (no entry_hash field)."""
    raw = _canonical_json(body_without_hash).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _utc_canonical_ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.isoformat()


def _ts_iso(ts: datetime | str) -> str:
    if isinstance(ts, str):
        return ts
    return _utc_canonical_ts(ts)


def _entry_prev(entry: dict[str, Any]) -> str:
    if "prev" in entry:
        return str(entry["prev"])
    return str(entry["prev_hash"])


def verify_chain(entries: list[dict[str, Any]]) -> tuple[bool, int | None]:
    """Verify hash chain integrity; return (ok, first_bad_index)."""
    expected_prev = GENESIS_PREV_HASH
    for i, entry in enumerate(entries):
        prev = _entry_prev(entry)
        if prev != expected_prev:
            return False, i
        body = {
            "ts": _ts_iso(entry["ts"]),
            "run_id": entry.get("run_id"),
            "actor": entry["actor"],
            "kind": entry["kind"],
            "payload": entry["payload"],
            "prev": prev,
        }
        computed = chain_hash(body)
        if computed != entry["entry_hash"]:
            return False, i
        expected_prev = entry["entry_hash"]
    return True, None


def _hash_body(
    *,
    ts_canonical: str,
    run_id: str | None,
    actor: str,
    kind: str,
    payload: dict[str, Any],
    prev: str,
) -> dict[str, Any]:
    return {
        "ts": ts_canonical,
        "run_id": run_id,
        "actor": actor,
        "kind": kind,
        "payload": payload,
        "prev": prev,
    }


def _current_tip(db: Session, *, lock: bool) -> AuditChainEntry | None:
    q = (
        select(AuditChainEntry)
        .order_by(AuditChainEntry.ts.desc(), AuditChainEntry.id.desc())
        .limit(1)
    )
    if lock:
        dialect = db.bind.dialect.name if db.bind is not None else ""
        if dialect == "postgresql":
            q = q.with_for_update()
    return db.execute(q).scalar_one_or_none()


def _build_row(
    *,
    actor: str,
    kind: str,
    payload: dict[str, Any],
    run_id: str | None,
    prev: str,
) -> AuditChainEntry:
    redacted = redact_payload(payload)
    ts = datetime.now(UTC)
    canonical_ts = _utc_canonical_ts(ts)
    body = _hash_body(
        ts_canonical=canonical_ts,
        run_id=run_id,
        actor=actor,
        kind=kind,
        payload=redacted,
        prev=prev,
    )
    entry_hash = chain_hash(body)
    return AuditChainEntry(
        id=str(uuid.uuid4()),
        ts=ts,
        canonical_ts=canonical_ts,
        run_id=run_id,
        actor=actor,
        kind=kind,
        payload_json=_canonical_json(redacted),
        prev_hash=prev,
        entry_hash=entry_hash,
    )


def append_entry(
    db: Session,
    *,
    actor: str,
    kind: str,
    payload: dict[str, Any],
    run_id: str | None = None,
) -> AuditChainEntry:
    """Append a hash-chained audit row; serializes concurrent writers (fail closed on fork)."""
    dialect = db.bind.dialect.name if db.bind is not None else ""
    use_pg_lock = dialect == "postgresql"
    for attempt in range(2):
        try:
            tip = _current_tip(db, lock=use_pg_lock)
            prev = tip.entry_hash if tip is not None else GENESIS_PREV_HASH
            if dialect == "sqlite" and tip is not None:
                live_prev = tip.entry_hash
                if live_prev != prev:
                    prev = live_prev
            row = _build_row(
                actor=actor,
                kind=kind,
                payload=payload,
                run_id=run_id,
                prev=prev,
            )
            db.add(row)
            db.flush()
            if dialect == "sqlite":
                fork = (
                    db.query(AuditChainEntry)
                    .filter(
                        AuditChainEntry.prev_hash == prev,
                        AuditChainEntry.id != row.id,
                    )
                    .first()
                )
                if fork is not None:
                    db.rollback()
                    if attempt == 0:
                        continue
                    raise RuntimeError("audit chain fork detected")
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
            if dialect == "sqlite" and attempt == 0:
                continue
            raise
    raise RuntimeError("audit chain append failed after retry")


def verify_db(db: Session) -> tuple[bool, int | None]:
    """Load chain rows in ts, id order and verify tamper-evident hashes."""
    rows = (
        db.query(AuditChainEntry)
        .order_by(AuditChainEntry.ts.asc(), AuditChainEntry.id.asc())
        .all()
    )
    entries: list[dict[str, Any]] = []
    for row in rows:
        ts_for_hash = row.canonical_ts if row.canonical_ts else _ts_iso(row.ts)
        entries.append(
            {
                "ts": ts_for_hash,
                "run_id": row.run_id,
                "actor": row.actor,
                "kind": row.kind,
                "payload": json.loads(row.payload_json),
                "prev_hash": row.prev_hash,
                "entry_hash": row.entry_hash,
            }
        )
    return verify_chain(entries)


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _shift_months(moment: datetime, months: int) -> datetime:
    """Add calendar months. The day clamps to the last day of the target month.

    Inputs: a datetime and a non-negative month count.
    Outputs: the shifted datetime, same clock time and tzinfo when the day exists.
    Side effects: none.
    """
    if months < 0:
        raise ValueError("months must be zero or positive")
    month_index = (moment.month - 1) + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _retention_expires_at(kind: str, recorded_at: datetime) -> datetime:
    """End of the side-copy window. The chain row itself does not expire."""
    if kind in RAW_LLM_KINDS:
        return recorded_at + timedelta(days=RAW_LLM_RETENTION_DAYS)
    if kind in ACCOUNTING_KINDS:
        return _shift_months(recorded_at, ACCOUNTING_RETENTION_YEARS * 12)
    return _shift_months(recorded_at, DEFAULT_RETENTION_MONTHS)


@dataclass(frozen=True)
class RetentionDecision:
    """Whether a side copy may be dropped. Never a decision to delete the chain row."""

    kind: str
    recorded_at: datetime
    now: datetime
    expires_at: datetime
    eligible: bool


def retention_decision(
    *,
    kind: str,
    recorded_at: datetime,
    now: datetime,
) -> RetentionDecision:
    """Decide if a side copy is past retention.

    Raw-LLM kinds expire after 7 days. Accounting kinds stay 7 years.
    Every other kind stays 24 calendar months. Eligible one second after
    the window ends. The hashed chain row is not eligible for deletion.

    Inputs: chain kind, when the row was recorded, and the sweep clock.
    Outputs: a ``RetentionDecision``. ``eligible`` is true only for the side copy.
    Side effects: none. Does not read or write a database.
    """
    if kind in RAW_LLM_KINDS and kind in ACCOUNTING_KINDS:
        raise ValueError(f"kind {kind!r} is in both retention sets")
    recorded = _as_utc(recorded_at)
    current = _as_utc(now)
    expires_at = _retention_expires_at(kind, recorded)
    return RetentionDecision(
        kind=kind,
        recorded_at=recorded,
        now=current,
        expires_at=expires_at,
        eligible=current >= expires_at + timedelta(seconds=1),
    )


@dataclass
class InProcessChainRecord:
    """One hash-chain entry plus a side copy that is not part of the hash.

    ``entry`` is the ``verify_chain`` dict (payload and ``entry_hash`` included).
    ``side_copy`` is the only field the sweeper may clear.
    """

    entry: dict[str, Any]
    recorded_at: datetime
    side_copy: dict[str, Any] | None = None


def sweep_side_copies(records: list[InProcessChainRecord], *, now: datetime) -> int:
    """Drop side copies whose retention window has elapsed.

    Inputs: in-process records and the sweep clock.
    Outputs: how many side copies were set to None.
    Side effects: clears ``side_copy`` on eligible records. Does not change
    ``entry``, its payload, or ``entry_hash``. Does not open a database and
    does not delete a chain row.
    """
    dropped = 0
    for record in records:
        if record.side_copy is None:
            continue
        decision = retention_decision(
            kind=str(record.entry["kind"]),
            recorded_at=record.recorded_at,
            now=now,
        )
        if decision.eligible:
            record.side_copy = None
            dropped += 1
    return dropped
