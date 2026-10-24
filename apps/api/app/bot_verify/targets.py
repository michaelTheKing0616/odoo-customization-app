"""BV-04: which Odoo a browser walkthrough may touch (D-BV-1, resolved 24 Oct).

Allowed: a DB named ``ingenium_`` / ``ingenium_wt_`` (disposable), or a connection whose
per-connection ``walkthrough_allowed`` flag was set by the owner. Everything else is
refused with TARGET_NOT_ALLOWED. Reserved ports are never targets. Every decision is
appended to the audit log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from app.sandbox import DEV_PORTS

TARGET_NOT_ALLOWED = "TARGET_NOT_ALLOWED"
RESERVED_PORTS: frozenset[int] = frozenset(
    {3002, 8001, 8002, 8012, 5433, 5436, 8069, 8070, 8071, 8072, 8073, 11434}
) | frozenset(DEV_PORTS)
MAJORS: frozenset[int] = frozenset({17, 18, 19, 20})
_DISPOSABLE = re.compile(r"^ingenium_(wt_)?[a-z0-9_]+$")

Kind = Literal["disposable_clone", "approved_connection"]

AUDIT_LOG: list[dict[str, str]] = []


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


def is_disposable(db_name: str) -> bool:
    return bool(_DISPOSABLE.match(str(db_name or "")))


def _audit(db_name: str, decision: str, reason: str) -> None:
    AUDIT_LOG.append(
        {
            "at": datetime.now(UTC).isoformat(),
            "db_name": str(db_name)[:80],
            "decision": decision,
            "reason": reason,
        }
    )


def resolve_target(
    *,
    url: str,
    db_name: str,
    major: int,
    walkthrough_allowed: bool = False,
    approved_by: str | None = None,
    owner_id: str | None = None,
) -> WalkTarget:
    """Return the walk target or raise TargetNotAllowed (audited either way)."""

    def refuse(reason: str) -> TargetNotAllowed:
        _audit(db_name, "refused", reason)
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
    elif walkthrough_allowed is True and approved_by and owner_id and approved_by == owner_id:
        kind = "approved_connection"
    else:
        raise refuse("not a disposable ingenium_ DB and no owner walkthrough approval")
    _audit(db_name, "allowed", kind)
    return WalkTarget(
        url=f"{parts.scheme}://{parts.hostname}:{port}",
        host=parts.hostname,
        port=port,
        db_name=db_name,
        major=int(major),
        kind=kind,
    )
