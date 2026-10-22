"""Persist plan cards. Rules stay in Inbox."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.changeset.inbox import Inbox, InboxError
from app.changeset.plan_card import (
    approval_is_expired,
    bound_schema_fp,
    changeset_ops_fingerprint,
    copy_sections_for_card,
    fingerprints_match,
    ops_from_card_changes,
)
from app.db_models import PlanCardRecord

_DECISIONS = frozenset({"approve", "deny", "deny_and_stop"})
# Process-local freeze windows. Not a customer database and not logged.
_FREEZE_WINDOWS: dict[str, tuple[datetime, datetime]] = {}


class PlanStale(Exception):
    """The presented plan hash or schema fingerprint is not the stored card."""


class ApprovalExpired(Exception):
    """Apply time is at or after the card expiry. RT-19."""


class FreezeWindow(Exception):
    """A freeze window blocks approve, and blocks apply. RT-20."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def set_freeze_window(connection_id: str, *, start: datetime, end: datetime) -> None:
    """Block approve for one connection while the clock is inside [start, end).

    Inputs: connection id and the window bounds. Naive datetimes are UTC.
    Output: none. end must be after start.
    Side effects: records the window in this process only. Does not write to a
    customer database and does not log the window.
    """
    if not connection_id:
        raise ValueError("connection_id is required")
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    if end_utc <= start_utc:
        raise ValueError("freeze window end must be after start")
    _FREEZE_WINDOWS[connection_id] = (start_utc, end_utc)


def clear_freeze_window(connection_id: str | None = None) -> None:
    """Drop one connection's freeze window, or every window when the id is omitted.

    Inputs: an optional connection id.
    Output: none.
    Side effects: removes process-local window state. Does not write to a database.
    """
    if connection_id is None:
        _FREEZE_WINDOWS.clear()
        return
    _FREEZE_WINDOWS.pop(connection_id, None)


def freeze_blocks_approve(connection_id: str, now: datetime | None = None) -> bool:
    """Whether approve must stop because a freeze window covers `now`.

    Inputs: connection id and an optional clock. The default clock is UTC now.
    Output: True when a window is recorded and start <= now < end.
    Side effects: none.
    """
    window = _FREEZE_WINDOWS.get(connection_id)
    if window is None:
        return False
    current = _as_utc(now or datetime.now(timezone.utc))
    start, end = window
    return start <= current < end


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
    """Validate, render, and store one plan card.

    Inputs: the Inbox.submit arguments, plus an optional `schema_slice` dict.
    The slice is not passed to Inbox. It becomes the card's schema fingerprint.
    Output: the Inbox submit result. A stored card includes `schema_fp`.
    Side effects: inserts or updates one plan_cards row when the plan is valid.
    Does not call Odoo.
    """
    schema_slice = kwargs.pop("schema_slice", None)
    result = Inbox().submit(**kwargs)
    if result.get("ok"):
        card = result["card"]
        card["schema_fp"] = bound_schema_fp(
            list(kwargs["changeset"]),
            environment=str(kwargs["environment"]),
            schema_slice=schema_slice if isinstance(schema_slice, dict) else None,
        )
        _void_superseded_pending(db, card)
        _write(db, card)
    return result


def _void_superseded_pending(db: Session, card: dict[str, Any]) -> None:
    """Mark pending cards with the same ops and a different hash as voided.

    Inputs: the session and the newly rendered card.
    Output: none.
    Side effects: updates matching pending plan_cards rows on this connection.
    Changing assumptions produces a new hash; the old fingerprint is void.
    Does not call Odoo and does not change fingerprint equality.
    """
    ops_fp = changeset_ops_fingerprint(ops_from_card_changes(card))
    changed = False
    rows = (
        db.query(PlanCardRecord)
        .filter(
            PlanCardRecord.connection_id == card["connection_id"],
            PlanCardRecord.status == "pending",
            PlanCardRecord.plan_hash != card["plan_hash"],
        )
        .all()
    )
    for row in rows:
        existing = json.loads(row.card_json)
        if changeset_ops_fingerprint(ops_from_card_changes(existing)) != ops_fp:
            continue
        existing["status"] = "voided"
        row.status = "voided"
        row.card_json = json.dumps(existing, sort_keys=True)
        db.add(row)
        changed = True
    if changed:
        db.commit()


def list_plans(db: Session, connection_id: str) -> list[dict[str, Any]]:
    """Return stored cards for one connection, each with the nine engine sections.

    Inputs: the session and the connection id.
    Output: cards newest-first. `sections` is rebuilt by the plan-card renderer
    so a row stored before that field existed still lists the nine titles.
    Side effects: none. Does not rewrite `card_json` or call Odoo.
    """
    rows = (
        db.query(PlanCardRecord)
        .filter(PlanCardRecord.connection_id == connection_id, PlanCardRecord.status.notin_(SUITE_KINDS))
        .order_by(PlanCardRecord.created_at.desc())
        .all()
    )
    cards: list[dict[str, Any]] = []
    for row in rows:
        card = json.loads(row.card_json)
        card["sections"] = copy_sections_for_card(card)
        cards.append(card)
    return cards


def _pending_card(db: Session, plan_hash: str, connection_id: str) -> tuple[Inbox, dict[str, Any]]:
    rows = (db.query(PlanCardRecord)
            .filter(PlanCardRecord.connection_id == connection_id, PlanCardRecord.status.notin_(SUITE_KINDS)).all())
    inbox = _inbox_from_rows(rows)
    card = inbox.cards.get(plan_hash)
    if card is None or card.get("connection_id") != connection_id:
        raise InboxError("not found")
    return inbox, card


def _require_fingerprint(card: dict[str, Any], *, plan_hash: str, body_plan_hash: str, schema_fp: str) -> None:
    if body_plan_hash != plan_hash or not fingerprints_match(
        card, plan_hash=body_plan_hash, schema_fp=schema_fp
    ):
        raise PlanStale("plan_stale")


def decide_plan(
    db: Session,
    plan_hash: str,
    *,
    approver_id: str,
    decision: str,
    connection_id: str,
    body_plan_hash: str,
    schema_fp: str,
    user_id: str | None = None,
    domain_owner: bool | None = None,
    role: str | None = None,
    simulation_passed: bool | None = None,
    backup_id: str | None = None,
    allowed_window: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record approve, deny, or deny-and-stop for the exact stored fingerprint.

    Inputs: the path plan hash, the body plan hash, the body schema fingerprint,
    the approver, the decision, the connection, the optional person id,
    domain-owner flag, role, simulation result, backup id, allowed window,
    and clock. Production R3 uses one approval and ignores the heavy-R4 facts.
    Production heavy R4 reads those facts. None leaves a fact unset.
    Output: the updated card.
    Side effects: writes the card when the decision is recorded.
    Raises PlanStale when either fingerprint differs. Raises FreezeWindow when
    the decision is approve and a freeze window covers the clock. Raises
    InboxError when the card is missing or the decision is not one of the
    three choices. Does not call Odoo and does not log the fingerprints.
    """
    if decision not in _DECISIONS:
        raise InboxError("decision must be approve, deny, or deny-and-stop")
    inbox, card = _pending_card(db, plan_hash, connection_id)
    _require_fingerprint(
        card, plan_hash=plan_hash, body_plan_hash=body_plan_hash, schema_fp=schema_fp
    )
    current = _as_utc(now or datetime.now(timezone.utc))
    if decision == "approve" and freeze_blocks_approve(connection_id, current):
        raise FreezeWindow("frozen")
    card = inbox.decide(
        plan_hash,
        approver_id=approver_id,
        decision=decision,  # type: ignore[arg-type]
        connection_id=connection_id,
        user_id=user_id,
        domain_owner=domain_owner,
        role=role,
        simulation_passed=simulation_passed,
        backup_id=backup_id,
        allowed_window=allowed_window,
        now=current,
    )
    _write(db, card)
    return card


def apply_approved_plan(
    db: Session,
    plan_hash: str,
    *,
    connection_id: str,
    body_plan_hash: str,
    schema_fp: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recheck the fingerprint, freeze, and expiry before an apply.

    Inputs: the stored plan hash, the fingerprint presented for apply, the
    connection, and an optional clock. Expiry is the card's expires_at, which
    follows the approval-flow window: 24 hours on production for R2 and above,
    and 7 days on staging.
    Output: a validity result when the approval may still be used.
    Side effects: none. Does not write the change-set, does not call Odoo,
    and does not log the fingerprints.
    Raises PlanStale when the presented fingerprint is not the card (RT-17).
    Raises FreezeWindow when a freeze window covers the clock (RT-20).
    Raises ApprovalExpired when the clock is at or after expires_at (RT-19).
    Raises InboxError when the card is missing or not approved.
    """
    _inbox, card = _pending_card(db, plan_hash, connection_id)
    _require_fingerprint(
        card, plan_hash=plan_hash, body_plan_hash=body_plan_hash, schema_fp=schema_fp
    )
    if card.get("status") != "approved":
        raise InboxError("plan is not approved")
    current = _as_utc(now or datetime.now(timezone.utc))
    if freeze_blocks_approve(connection_id, current):
        raise FreezeWindow("frozen")
    if approval_is_expired(card, current):
        raise ApprovalExpired("approval expired")
    return {"ok": True, "status": "approval_valid", "plan_hash": card["plan_hash"]}


__all__ = [
    "ApprovalExpired",
    "FreezeWindow",
    "InboxError",
    "PlanStale",
    "apply_approved_plan",
    "clear_freeze_window",
    "decide_plan",
    "freeze_blocks_approve",
    "list_plans",
    "set_freeze_window",
    "submit_plan",
]


# ---------------------------------------------------------------------------
# Suite change-set plans (Bulk Setup plans + Change Records batches).
# They persist here, in plan_cards, alongside engine plan cards. Their status
# column is the suite kind, so the engine inbox / list_plans / decide paths
# never see them (those read only engine statuses), and their plan_hash
# column is prefixed "s" so it can never collide with an engine card hash.
# Runs, receipts (dry_run_ledger) and undo are unchanged.
# ---------------------------------------------------------------------------
SUITE_KINDS = frozenset({"suite_plan", "suite_batch"})


class SuiteItem:
    """Row-like view of a stored suite plan/batch (same surface the suite routers use)."""

    def __init__(self, rec: PlanCardRecord) -> None:
        self.rec = rec
        body = json.loads(rec.card_json or "{}")
        self.kind: str = str(body.get("suite_kind") or rec.status)
        self.key: str = str(body.get("key") or "")
        self.name: str = str(body.get("name") or "")
        self.payload: dict[str, Any] = body.get("payload") or {}

    @property
    def id(self) -> str:
        return self.rec.id

    @property
    def connection_id(self) -> str:
        return self.rec.connection_id

    @property
    def created_at(self) -> datetime | None:
        return self.rec.created_at


def _suite_hash(payload: dict[str, Any]) -> str:
    import hashlib

    body = json.dumps(payload.get("steps") or payload.get("check") or payload, sort_keys=True, default=str)
    return "s" + hashlib.sha256(body.encode()).hexdigest()[:15]


def _suite_flush(db: Session, item: SuiteItem) -> None:
    item.rec.card_json = json.dumps({"suite_kind": item.kind, "key": item.key, "name": item.name[:120],
                                     "payload": item.payload}, default=str)
    item.rec.plan_hash = _suite_hash(item.payload)
    item.rec.status = item.kind
    db.add(item.rec)
    db.commit()


def save_suite_item(db: Session, *, connection_id: str, kind: str, key: str, name: str,
                    payload: dict[str, Any], item_id: str | None = None) -> SuiteItem:
    if kind not in SUITE_KINDS:
        raise ValueError(f"not a suite plan kind: {kind}")
    rec = PlanCardRecord(connection_id=connection_id, requester_id=str(payload.get("created_by_id") or "suite")[:36],
                         plan_hash="s", status=kind, card_json="{}")
    if item_id:
        rec.id = item_id
    item = SuiteItem(rec)
    item.kind, item.key, item.name, item.payload = kind, key, name[:120], payload
    _suite_flush(db, item)
    return item


def get_suite_item(db: Session, connection_id: str, item_id: str) -> SuiteItem | None:
    rec = (db.query(PlanCardRecord)
           .filter(PlanCardRecord.connection_id == connection_id, PlanCardRecord.id == item_id,
                   PlanCardRecord.status.in_(SUITE_KINDS))
           .one_or_none())
    return SuiteItem(rec) if rec is not None else None


def list_suite_items(db: Session, connection_id: str, kind: str) -> list[SuiteItem]:
    rows = (db.query(PlanCardRecord)
            .filter(PlanCardRecord.connection_id == connection_id, PlanCardRecord.status == kind)
            .order_by(PlanCardRecord.created_at.desc()).limit(200).all())
    return [SuiteItem(r) for r in rows]


def update_suite_item(db: Session, item: SuiteItem, payload: dict[str, Any]) -> None:
    item.payload = payload
    _suite_flush(db, item)


def suite_item_out(item: SuiteItem) -> dict[str, Any]:
    return {"id": item.id, "kind": item.kind, "key": item.key, "name": item.name, "payload": item.payload,
            "created_at": item.created_at.isoformat() if item.created_at else None}


def migrate_suite_items(db: Session) -> int:
    """Move saved suite plans/batches from the old builder-item store into plan_cards.

    Same ids (approvals, receipts and run links keep resolving). The old rows are kept,
    re-kinded "m:<kind>" (the kind column is 16 characters on Postgres), as the undo. Idempotent."""
    from app import view_engine_store as vs

    vs._ensure_tables(db)
    moved = 0
    rows = db.query(vs.ViewBuilderItem).filter(vs.ViewBuilderItem.kind.in_(SUITE_KINDS)).all()
    for row in rows:
        if db.get(PlanCardRecord, row.id) is None:
            out = vs.item_out(row)
            item = save_suite_item(db, connection_id=row.connection_id, kind=row.kind, key=row.key or "",
                                   name=row.name or "", payload=out["payload"], item_id=row.id)
            if row.created_at is not None:
                item.rec.created_at = row.created_at
                db.add(item.rec)
            moved += 1
        row.kind = f"m:{row.kind}"[:16]
        db.add(row)
    db.commit()
    return moved
