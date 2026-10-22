"""Remember a dry-run and refuse the matching live write until one has been seen.

The hash ignores approval fields so a confirm step does not look like a different plan.
Receipts live in ``dry_run_seen`` (TTL 1 hour) so two workers share one ledger.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.plan_fingerprint import structural_dry_run_hash

_IGNORE = frozenset(
    {
        "dry_run",
        "receipt_token",
        "confirm_advanced",
        "confirm_phrase",
        "continue_after_sample",
    }
)
TTL_S = 60 * 60


class DryRunRequired(Exception):
    """A live write arrived without a matching dry-run in the shared ledger."""


class DryRunStore(Protocol):
    def remember(self, digest: str, *, now: datetime | None = None) -> None: ...

    def contains(self, digest: str, *, now: datetime | None = None) -> bool: ...


def _naive_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is not None:
        current = current.astimezone(UTC).replace(tzinfo=None)
    return current


class SqlDryRunStore:
    """Table-backed ledger. Each call opens its own session so workers do not share memory."""

    def __init__(self, session_factory: Any, model: type | None = None) -> None:
        self._session_factory = session_factory
        self._model = model

    def _model_cls(self) -> type:
        if self._model is None:
            from app.db_models import DryRunSeen

            self._model = DryRunSeen
        return self._model

    def remember(self, digest: str, *, now: datetime | None = None) -> None:
        model = self._model_cls()
        current = _naive_utc(now)
        expires = current + timedelta(seconds=TTL_S)
        db = self._session_factory()
        try:
            row = db.get(model, digest)
            if row is None:
                db.add(model(digest=digest, expires_at=expires, created_at=current))
            else:
                row.expires_at = expires
            self._drop_expired(db, model, current)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def contains(self, digest: str, *, now: datetime | None = None) -> bool:
        model = self._model_cls()
        current = _naive_utc(now)
        db = self._session_factory()
        try:
            row = db.get(model, digest)
            if row is None:
                return False
            if _naive_utc(row.expires_at) <= current:
                db.delete(row)
                db.commit()
                return False
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _drop_expired(db: Any, model: type, current: datetime) -> None:
        stale = db.query(model).all()
        for row in stale:
            if _naive_utc(row.expires_at) <= current:
                db.delete(row)


_bound: DryRunStore | None = None
_default: DryRunStore | None = None


def bind_store(store: DryRunStore | None) -> None:
    """Pin the ledger for tests. ``None`` restores the app-database store."""
    global _bound
    _bound = store


def active_store() -> DryRunStore:
    if _bound is not None:
        return _bound
    global _default
    if _default is None:
        from app.db import SessionLocal

        _default = SqlDryRunStore(SessionLocal)
    return _default


def _payload(args: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in args.items() if key not in _IGNORE}


def _key(tool: str, args: dict[str, Any]) -> str:
    return structural_dry_run_hash(tool, _payload(args))


def remember_dry_run(
    tool: str,
    args: dict[str, Any],
    *,
    store: DryRunStore | None = None,
    now: datetime | None = None,
) -> str:
    digest = _key(tool, args)
    (store or active_store()).remember(digest, now=now)
    return digest


def dry_run_was_seen(
    tool: str,
    args: dict[str, Any],
    *,
    store: DryRunStore | None = None,
    now: datetime | None = None,
) -> bool:
    digest = _key(tool, args)
    return (store or active_store()).contains(digest, now=now)


def enforce_dry_run(
    tool: str,
    args: dict[str, Any],
    *,
    dry_run: bool,
    store: DryRunStore | None = None,
    now: datetime | None = None,
) -> str:
    """Record a dry-run, or raise DryRunRequired when the live write was not previewed."""
    if dry_run:
        return remember_dry_run(tool, args, store=store, now=now)
    if not dry_run_was_seen(tool, args, store=store, now=now):
        raise DryRunRequired(
            f"Run {tool} with dry_run true before the live write. The parameters must match."
        )
    return _key(tool, args)
