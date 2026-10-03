"""Persist plan cards. Rules stay in Inbox."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.changeset.inbox import Inbox, InboxError
from app.db_models import PlanCardRecord


def _inbox_from_rows(rows: list[PlanCardRecord]) -> Inbox:
    inbox = Inbox()
    for row in rows:
        card = json.loads(row.card_json)
        inbox.cards[card["plan_hash"]] = card
    return inbox


def _write(db: Session, card: dict[str, Any]) -> None:
    row = (
        db.query(PlanCardRecord)
        .filter(
            PlanCardRecord.plan_hash == card["plan_hash"],
            PlanCardRecord.connection_id == card["connection_id"],
        )
        .one_or_none()
    )
    payload = json.dumps(card, sort_keys=True)
    if row is None:
        db.add(
            PlanCardRecord(
                connection_id=card["connection_id"],
                requester_id=card["requester_id"],
                plan_hash=card["plan_hash"],
                status=card["status"],
                card_json=payload,
            )
        )
    else:
        row.status = card["status"]
        row.card_json = payload
        db.add(row)
    db.commit()


def submit_plan(db: Session, **kwargs: Any) -> dict[str, Any]:
    result = Inbox().submit(**kwargs)
    if result.get("ok"):
        _write(db, result["card"])
    return result


def list_plans(db: Session, connection_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(PlanCardRecord)
        .filter(PlanCardRecord.connection_id == connection_id)
        .order_by(PlanCardRecord.created_at.desc())
        .all()
    )
    return [json.loads(row.card_json) for row in rows]


def decide_plan(db: Session, plan_hash: str, *, approver_id: str, decision: str, connection_id: str) -> dict[str, Any]:
    rows = db.query(PlanCardRecord).filter(PlanCardRecord.connection_id == connection_id).all()
    inbox = _inbox_from_rows(rows)
    card = inbox.decide(
        plan_hash,
        approver_id=approver_id,
        decision=decision,  # type: ignore[arg-type]
        connection_id=connection_id,
    )
    _write(db, card)
    return card


__all__ = ["InboxError", "decide_plan", "list_plans", "submit_plan"]
