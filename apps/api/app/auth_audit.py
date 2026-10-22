"""Typed auth events on the one hash chain (T6-03). No second table."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.audit_chain import append_entry
from app.db_models import AuditChainEntry

AUTH_EVENT_KINDS: frozenset[str] = frozenset({"login", "logout", "grant", "revoke", "totp"})


def record_auth_event(
    db: Session,
    *,
    kind: str,
    actor: str,
    target_user: str | None,
    provider: str | None,
    result: str,
    extra: dict[str, Any] | None = None,
) -> AuditChainEntry:
    """Append one typed auth row. Payload never includes a secret.

    Inputs: open session, kind, actor, target user, provider, result, optional extra.
    Outputs: the persisted chain row.
    Side effects: ``append_entry`` commits the session.
    """
    if kind not in AUTH_EVENT_KINDS:
        raise ValueError(f"unsupported auth audit kind {kind!r}")
    payload: dict[str, Any] = {
        "actor": actor,
        "target_user": target_user,
        "provider": provider,
        "result": result,
    }
    if extra:
        payload.update(extra)
    return append_entry(db, actor=actor, kind=kind, payload=payload)
