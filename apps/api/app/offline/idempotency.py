"""Idempotency claims for offline-queue work — repeated keys must not re-run compute."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.db_models import IdempotencyKey

_RESERVED = {"_offline_claim": "reserved"}


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}

    def claim(self, key: str, compute: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if not key or not str(key).strip():
            raise ValueError("idempotency key required")
        if key in self._results:
            return self._results[key]
        result = compute()
        self._results[key] = result
        return result


def _stored_result(row: IdempotencyKey) -> dict[str, Any] | None:
    payload = json.loads(row.result_json)
    if payload.get("_offline_claim") == "reserved":
        return None
    return payload


def claim_db(db: Session, key: str, compute: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if not key or not str(key).strip():
        raise ValueError("idempotency key required")

    for _attempt in range(32):
        existing = db.query(IdempotencyKey).filter_by(key=key).first()
        if existing is not None:
            stored = _stored_result(existing)
            if stored is not None:
                return stored
            db.expire(existing)
            time.sleep(0.01)
            continue

        row = IdempotencyKey(
            id=str(uuid.uuid4()),
            key=key,
            result_json=json.dumps(_RESERVED),
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue

        try:
            result = compute()
            row.result_json = json.dumps(result)
            db.commit()
            return result
        except (IntegrityError, StaleDataError):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            leftover = db.query(IdempotencyKey).filter_by(key=key).first()
            if leftover is not None and _stored_result(leftover) is None:
                db.delete(leftover)
                db.commit()
            raise

    existing = db.query(IdempotencyKey).filter_by(key=key).one()
    stored = _stored_result(existing)
    if stored is None:
        raise RuntimeError("idempotency key stayed reserved")
    return stored
