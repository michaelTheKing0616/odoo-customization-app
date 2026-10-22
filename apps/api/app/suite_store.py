"""Suite persistence facade: the view_engine_store API the suite routers already use, with
setup plans and change batches persisted via the shared changeset store (plan_cards).
Runs, schedules, policy, pauses and approvals stay in the builder-item store, so receipts
and undo are unchanged. Anything not overridden here passes through to view_engine_store."""
from __future__ import annotations

import threading
import weakref
from typing import Any

from sqlalchemy.orm import Session

from app import view_engine_store as _vs
from app.changeset import store as _cs

_migrated: "weakref.WeakSet[Any]" = weakref.WeakSet()  # per engine (tests make a fresh one each time)
_lock = threading.Lock()


def _ensure_migrated(db: Session) -> None:
    key = db.get_bind()
    key = getattr(key, "engine", key)
    if key in _migrated:
        return
    with _lock:
        if key in _migrated:
            return
        from app.db_models import PlanCardRecord

        PlanCardRecord.__table__.create(db.get_bind(), checkfirst=True)  # alembic owns it in prod; tests' sqlite may not
        _cs.migrate_suite_items(db)
        _migrated.add(key)


def save_item(db: Session, *, connection_id: str, kind: str, key: str, name: str, payload: dict[str, Any],
              replace_key: bool = False) -> Any:
    if kind in _cs.SUITE_KINDS:
        _ensure_migrated(db)
        return _cs.save_suite_item(db, connection_id=connection_id, kind=kind, key=key, name=name, payload=payload)
    return _vs.save_item(db, connection_id=connection_id, kind=kind, key=key, name=name, payload=payload,
                         replace_key=replace_key)


def get_item(db: Session, connection_id: str, item_id: str) -> Any:
    _ensure_migrated(db)
    return _cs.get_suite_item(db, connection_id, item_id) or _vs.get_item(db, connection_id, item_id)


def list_items(db: Session, connection_id: str, kind: str, key: str | None = None) -> list[Any]:
    if kind in _cs.SUITE_KINDS:
        _ensure_migrated(db)
        rows = _cs.list_suite_items(db, connection_id, kind)
        return [r for r in rows if key is None or r.key == key]
    return _vs.list_items(db, connection_id, kind, key)


def update_item(db: Session, row: Any, payload: dict[str, Any]) -> None:
    if isinstance(row, _cs.SuiteItem):
        _cs.update_suite_item(db, row, payload)
    else:
        _vs.update_item(db, row, payload)


def item_out(row: Any) -> dict[str, Any]:
    return _cs.suite_item_out(row) if isinstance(row, _cs.SuiteItem) else _vs.item_out(row)


def __getattr__(name: str) -> Any:
    return getattr(_vs, name)
