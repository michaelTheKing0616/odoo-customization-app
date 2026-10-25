"""Append-only, hash-chained Bot audit writer.

Fail closed: if the row is not written, the caller must not write to Odoo. DB triggers forbid
UPDATE/DELETE/TRUNCATE and the table is owned by a NOLOGIN role (the app role can only
INSERT/SELECT). Each append is also anchored (id, row count, head hash) in an append-only
file outside the database, so ``verify_chain`` detects tail truncation as well as edits.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bots.risk.rules import RANK

GENESIS = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^[A-Za-z0-9:_./-]{1,200}$")
_TASK = re.compile(r"^[A-Za-z0-9_.:*/-]{1,200}$")
_CHAIN_LOCK = 0x0B07A0D1  # advisory lock serialising chain appends
REDACTED = "[REDACTED]"
# key-name patterns, with or without ':' / '=' separators, and bare secret-looking values
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(pass(word|wd|phrase)?|pwd|secret|token|api[\s_-]?key|apikey|"
        r"private[\s_-]?key|client[\s_-]?secret|authorization|bearer|credential)s?\b"
        r"\s*[:=]?\s*\S+"
    ),
    re.compile(r"\b(sk|pk|ghp|gho|xox[abp]|AKIA)[A-Za-z0-9_-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}"),  # long base64 / hex blob
)
# id-shaped fields: only key-name patterns apply (they legitimately hold long hex ids)
_ID_FIELDS = frozenset({"db_fingerprint", "idempotency_key", "job_id", "diff_hash"})
# catalogue ids (e.g. m:payment.token:change) carry model names: value patterns only
_CATALOGUE_FIELDS = frozenset({"task_id", "rule_ids", "risk_class", "decision", "caps_hit"})


class AuditError(RuntimeError):
    """The audit row could not be written or is invalid; the write must not happen."""


class CapError(AuditError):
    """The intent would take the job past its approved record count."""


@dataclass(frozen=True)
class AuditRow:
    db_fingerprint: str
    task_id: str
    actor: str
    approval_level: int
    risk_class: str
    rule_ids: str
    diff_hash: str
    blast_count: int
    batch_no: int
    idempotency_key: str
    decision: str
    reason: str
    approver: str | None = None
    caps_hit: str = ""
    snapshot_id: str | None = None
    before_image_ref: str | None = None
    job_id: str = "-"
    n_records: int = 0


def find_secret(value: str, *, kind: str = "text") -> bool:
    pats = {"id": _SECRET_PATTERNS[:1], "catalogue": _SECRET_PATTERNS[1:]}.get(
        kind, _SECRET_PATTERNS
    )
    return any(p.search(value) for p in pats)


def redact(value: str) -> str:
    """Replace anything secret-shaped; used on free text before it reaches a row."""
    for p in _SECRET_PATTERNS:
        value = p.sub(REDACTED, value)
    return value


def validate(row: AuditRow) -> None:
    if row.risk_class not in RANK:
        raise AuditError(f"unknown risk class {row.risk_class!r}")
    if not _HEX64.match(row.diff_hash):
        raise AuditError("diff_hash must be a sha256 hex digest, never the diff itself")
    if row.approval_level not in (0, 1, 2, 3) or min(row.blast_count, row.batch_no) < 0:
        raise AuditError("bad level/blast/batch")
    if row.n_records < 0:
        raise AuditError("bad n_records")
    for name, val in asdict(row).items():
        kind = "id" if name in _ID_FIELDS else "catalogue" if name in _CATALOGUE_FIELDS else ""
        if isinstance(val, str) and find_secret(val, kind=kind):
            raise AuditError(f"secret-like content in {name}")
    if not _TASK.match(row.task_id):
        raise AuditError("task_id must be a catalogue id")
    for ref in (row.before_image_ref, row.snapshot_id):
        if ref is not None and not _REF.match(ref):
            raise AuditError("references must be opaque ids, not values")


def _payload(row: AuditRow, prev: str) -> str:
    return json.dumps({**asdict(row), "prev_hash": prev}, sort_keys=True, separators=(",", ":"))


def row_hash(row: AuditRow, prev: str) -> str:
    return hashlib.sha256(_payload(row, prev).encode()).hexdigest()


def default_anchor(engine: Engine) -> Path:
    env = os.environ.get("BOT_AUDIT_ANCHOR")
    if env:
        return Path(env)
    return Path.home() / ".ingenium" / "bot_audit" / f"{engine.url.database}.anchor"


class AuditLog:
    def __init__(self, engine: Engine, anchor: Path | None = None) -> None:
        self.engine = engine
        self._local = threading.local()
        self.anchor = anchor if anchor is not None else (engine and default_anchor(engine))

    def _write_anchor(self, row_id: int, count: int, h: str) -> None:
        self.anchor.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.anchor, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, f"{row_id} {count} {h}\n".encode())
            os.fsync(fd)
        finally:
            os.close(fd)

    def append(self, row: AuditRow) -> str:
        """Append one row (chain-locked; anchored before commit). With ``job_cap`` the row is
        an intent whose records must keep the job's cumulative total <= job_cap."""
        validate(row)
        job_cap = getattr(self._local, "job_cap", None)
        try:
            with self.engine.begin() as c:
                c.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK})
                if job_cap is not None:
                    taken = c.execute(
                        text(
                            "SELECT 1 FROM bot_audit WHERE job_id=:j AND batch_no=:b"
                            " AND decision='intent'"
                        ),
                        {"j": row.job_id, "b": row.batch_no},
                    ).first()
                    if taken:
                        raise AuditError("audit write failed: IntegrityError (batch claimed)")
                    used = c.execute(
                        text(
                            "SELECT coalesce(sum(n_records),0) FROM bot_audit"
                            " WHERE job_id=:j AND decision='intent'"
                        ),
                        {"j": row.job_id},
                    ).scalar()
                    if used + row.n_records > job_cap:
                        raise CapError(f"job total {used}+{row.n_records} > approved {job_cap}")
                prev = c.execute(
                    text("SELECT row_hash FROM bot_audit ORDER BY id DESC LIMIT 1")
                ).scalar()
                prev = prev or GENESIS
                h = row_hash(row, prev)
                rid = c.execute(
                    text(
                        "INSERT INTO bot_audit (db_fingerprint, task_id, actor, approver,"
                        " approval_level, risk_class, rule_ids, diff_hash, blast_count, batch_no,"
                        " caps_hit, snapshot_id, before_image_ref, idempotency_key, decision,"
                        " reason, job_id, n_records, prev_hash, row_hash) VALUES"
                        " (:db_fingerprint, :task_id, :actor, :approver, :approval_level,"
                        " :risk_class, :rule_ids, :diff_hash, :blast_count, :batch_no, :caps_hit,"
                        " :snapshot_id, :before_image_ref, :idempotency_key, :decision, :reason,"
                        " :job_id, :n_records, :prev, :h) RETURNING id"
                    ),
                    {**asdict(row), "prev": prev, "h": h},
                ).scalar()
                count = c.execute(text("SELECT count(*) FROM bot_audit")).scalar()
                self._write_anchor(rid, count, h)  # failure rolls the row back
            return h
        except AuditError:
            raise
        except Exception as exc:  # connection drop, constraint, trigger, anchor: fail closed
            raise AuditError(f"audit write failed: {type(exc).__name__}") from exc

    def claim(self, row: AuditRow, *, job_cap: int | None = None) -> bool:
        """Write the 'intent' row. False (plus a 'duplicate' row) if this (db, key, batch) or
        (job, batch) is already claimed; unique partial indexes make this race-safe."""
        self._local.job_cap = job_cap
        try:
            self.append(row)
            return True
        except CapError:
            raise
        except AuditError as exc:
            if "IntegrityError" not in str(exc):
                raise
        finally:
            self._local.job_cap = None
        self.append(replace(row, decision="duplicate", reason="already claimed", n_records=0))
        return False

    def verify_chain(self) -> tuple[bool, int | None]:
        """Recompute the hash chain and compare the tail with the external anchor.
        Returns (ok, first bad id; -1 = tail missing / anchor mismatch)."""
        cols = list(AuditRow.__dataclass_fields__)
        prev, last_id, n, by_id = GENESIS, None, 0, {}
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    f"SELECT id, {', '.join(cols)}, prev_hash, row_hash FROM bot_audit ORDER BY id"
                )
            ).mappings()
            for r in rows:
                row = AuditRow(**{k: r[k] for k in cols})
                if r["prev_hash"] != prev or row_hash(row, prev) != r["row_hash"]:
                    return False, r["id"]
                prev, last_id, n = r["row_hash"], r["id"], n + 1
                by_id[r["id"]] = r["row_hash"]
        lines = self.anchor.read_text().split() if self.anchor.exists() else []
        if not lines:
            return (n == 0), (None if n == 0 else -1)
        a_id, a_count, a_hash = int(lines[-3]), int(lines[-2]), lines[-1]
        if by_id.get(a_id) != a_hash or n < a_count or (last_id is not None and last_id < a_id):
            return False, -1
        return True, None
