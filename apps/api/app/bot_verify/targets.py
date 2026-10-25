"""BV-04 / BV-AUDIT: which Odoo a browser walkthrough may touch (D-BV-1, resolved 24 Oct).

Allowed: a DB named ``ingenium_`` / ``ingenium_wt_`` (disposable), or a connection whose
stored ``walkthrough_allowed`` approval was set by its owner (verify_walk_approvals).
Approval is read from stored state keyed by connection, never from caller arguments.
Everything else is refused with TARGET_NOT_ALLOWED. Reserved ports are never targets.
Every allow/refuse decision is written to verify_audit (BV-AUDIT); if the audit row
cannot be written, the walk is refused.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from sqlalchemy import Engine, select

from app.bot_verify.models import VerifyAuditRow, VerifyWalkApprovalRow
from app.sandbox import DEV_PORTS

TARGET_NOT_ALLOWED = "TARGET_NOT_ALLOWED"
RESERVED_PORTS: frozenset[int] = frozenset(
    {3002, 8001, 8002, 8012, 5433, 5436, 8069, 8070, 8071, 8072, 8073, 11434}
) | frozenset(DEV_PORTS)
MAJORS: frozenset[int] = frozenset({17, 18, 19, 20})
_DISPOSABLE = re.compile(r"^ingenium_(wt_)?[a-z0-9_]+$")
_IGNORED_CALLER_FLAGS = frozenset({"walkthrough_allowed", "approved_by", "owner_id"})

Kind = Literal["disposable_clone", "approved_connection"]

_log = logging.getLogger("ingenium.bot_verify.audit")

verify_audit = VerifyAuditRow.__table__
verify_walk_approvals = VerifyWalkApprovalRow.__table__


class TargetNotAllowed(Exception):
    code = TARGET_NOT_ALLOWED

    def __init__(self, reason: str) -> None:
        super().__init__(f"{TARGET_NOT_ALLOWED}: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class WalkTarget:
    url: str
    host: str
    port: int
    db_name: str
    major: int
    kind: Kind

    @property
    def origin(self) -> str:
        return f"{urlsplit(self.url).scheme}://{self.host}:{self.port}"


@dataclass(frozen=True)
class WalkApproval:
    walkthrough_allowed: bool
    approved_by: str | None
    owner_id: str | None

    @property
    def granted(self) -> bool:
        return (
            self.walkthrough_allowed is True
            and bool(self.approved_by)
            and bool(self.owner_id)
            and self.approved_by == self.owner_id
        )


class AuditStore:
    """verify_audit + verify_walk_approvals behind an injected engine."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def record(self, connection_id: str | None, db_name: str, decision: str, reason: str) -> None:
        with self.engine.begin() as c:
            c.execute(
                verify_audit.insert().values(
                    connection_id=connection_id,
                    db_name=str(db_name or "")[:80],
                    decision=decision,
                    reason=str(reason)[:200],
                    at=datetime.now(UTC),
                )
            )

    def approval(self, connection_id: str | None) -> WalkApproval:
        if not connection_id:
            return WalkApproval(False, None, None)
        a = verify_walk_approvals
        with self.engine.connect() as c:
            row = c.execute(select(a).where(a.c.connection_id == connection_id)).first()
        if row is None:
            return WalkApproval(False, None, None)
        return WalkApproval(row.walkthrough_allowed is True, row.approved_by, row.owner_id)

    def set_approval(
        self, connection_id: str, *, allowed: bool, approved_by: str | None, owner_id: str | None
    ) -> None:
        a = verify_walk_approvals
        vals = {
            "walkthrough_allowed": bool(allowed),
            "approved_by": approved_by,
            "owner_id": owner_id,
            "approved_at": datetime.now(UTC),
        }
        with self.engine.begin() as c:
            hit = c.execute(
                a.update().where(a.c.connection_id == connection_id).values(**vals)
            ).rowcount
            if not hit:
                c.execute(a.insert().values(connection_id=connection_id, **vals))

    def log(self, connection_id: str | None = None) -> list[dict[str, Any]]:
        t = verify_audit
        q = select(t).order_by(t.c.id)
        if connection_id is not None:
            q = q.where(t.c.connection_id == connection_id)
        with self.engine.connect() as c:
            rows = c.execute(q).all()
        return [
            {
                "at": r.at.isoformat(),
                "connection_id": r.connection_id,
                "db_name": r.db_name,
                "decision": r.decision,
                "reason": r.reason,
            }
            for r in rows
        ]


_STORE: Any = None


def configure_audit_store(store: Any) -> None:
    """Wire the audit/approval store (production: AuditStore(engine); tests: a double)."""
    global _STORE
    _STORE = store


def audit_store() -> Any:
    return _STORE


def audit_log(connection_id: str | None = None) -> list[dict[str, Any]]:
    """Read-through view of persisted decisions (replaces the old in-memory AUDIT_LOG)."""
    if _STORE is None:
        raise TargetNotAllowed("audit store not configured")
    return _STORE.log(connection_id)


def is_disposable(db_name: str) -> bool:
    return bool(_DISPOSABLE.match(str(db_name or "")))


def _audit(connection_id: str | None, db_name: str, decision: str, reason: str) -> None:
    if _STORE is None:
        raise TargetNotAllowed("audit store not configured")
    try:
        _STORE.record(connection_id, db_name, decision, reason)
    except Exception as exc:  # noqa: BLE001 - an unaudited walk must not run
        _log.error("verify audit write failed: %s", type(exc).__name__)
        raise TargetNotAllowed("audit write failed") from exc


def resolve_target(
    *,
    url: str,
    db_name: str,
    major: int,
    connection_id: str | None = None,
    **caller_flags: Any,
) -> WalkTarget:
    """Return the walk target or raise TargetNotAllowed (persisted either way).

    walkthrough_allowed / approved_by / owner_id passed by a caller are ignored: approval
    comes only from the stored row for ``connection_id``.
    """
    unknown = set(caller_flags) - _IGNORED_CALLER_FLAGS
    if unknown:
        raise TypeError(f"unexpected arguments: {sorted(unknown)}")

    def refuse(reason: str) -> TargetNotAllowed:
        _audit(connection_id, db_name, "refused", reason)
        return TargetNotAllowed(reason)

    parts = urlsplit(str(url or ""))
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise refuse("bad url")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port in RESERVED_PORTS:
        raise refuse(f"reserved port {port}")
    if int(major) not in MAJORS:
        raise refuse(f"unsupported Odoo {major}")
    if is_disposable(db_name):
        kind: Kind = "disposable_clone"
    elif _STORE is not None and _STORE.approval(connection_id).granted:
        kind = "approved_connection"
    else:
        raise refuse("not a disposable ingenium_ DB and no stored owner walkthrough approval")
    _audit(connection_id, db_name, "allowed", kind)
    return WalkTarget(
        url=f"{parts.scheme}://{parts.hostname}:{port}",
        host=parts.hostname,
        port=port,
        db_name=db_name,
        major=int(major),
        kind=kind,
    )
