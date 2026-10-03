"""Integration event queue — idempotent enqueue and dead-letter marking."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import IntegrationEvent

_FORBIDDEN_KEY = re.compile(r"password|api_key|secret|token", re.IGNORECASE)


def _reject_secret_keys(payload: object, *, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            here = f"{path}.{key}" if path else str(key)
            if _FORBIDDEN_KEY.search(str(key)):
                raise ValueError(f"payload must not contain secret key: {here}")
            _reject_secret_keys(value, path=here)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_secret_keys(item, path=f"{path}[{index}]")


def _new_event(*, connection_id: str, idempotency_key: str, payload: dict) -> IntegrationEvent:
    return IntegrationEvent(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        idempotency_key=idempotency_key,
        payload_json=json.dumps(payload),
        status="queued",
        attempts=0,
    )


def enqueue_pure(
    events: list[Any],
    *,
    connection_id: str,
    idempotency_key: str,
    payload: dict,
) -> Any:
    """In-memory idempotent enqueue; mutates ``events`` when inserting."""
    _reject_secret_keys(payload)
    for event in events:
        if event.connection_id == connection_id and event.idempotency_key == idempotency_key:
            return event
    event = _new_event(
        connection_id=connection_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    events.append(event)
    return event


def enqueue(
    db: Session,
    connection_id: str,
    idempotency_key: str,
    payload: dict,
) -> IntegrationEvent:
    """Persist a queued event; duplicate keys return the existing row."""
    _reject_secret_keys(payload)
    existing = (
        db.query(IntegrationEvent)
        .filter_by(connection_id=connection_id, idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        return existing
    event = enqueue_pure(
        [],
        connection_id=connection_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def mark_dead(event: Any, reason: str) -> Any:
    """Mark an event dead and count one delivery attempt."""
    del reason  # reserved for logging / future dead-letter detail
    event.status = "dead"
    event.attempts = int(getattr(event, "attempts", 0) or 0) + 1
    return event
