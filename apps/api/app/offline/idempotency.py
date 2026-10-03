"""Idempotency claims for offline-queue work — repeated keys must not re-run compute."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import IdempotencyKey


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


def claim_db(db: Session, key: str, compute: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if not key or not str(key).strip():
        raise ValueError("idempotency key required")
    existing = db.query(IdempotencyKey).filter_by(key=key).first()
    if existing is not None:
        return json.loads(existing.result_json)
    result = compute()
    row = IdempotencyKey(
        id=str(uuid.uuid4()),
        key=key,
        result_json=json.dumps(result),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(IdempotencyKey).filter_by(key=key).one()
        return json.loads(existing.result_json)
    return result
