"""T6-05 — nine copy sections from the engine; assumption change voids the old card."""

from __future__ import annotations

import json
import os
import uuid

import pytest

from app.changeset.inbox import Inbox, InboxError
from app.changeset.plan_card import PLAN_CARD_COPY_SECTIONS, compute_plan_hash, render_plan_card

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)

from app.changeset.store import decide_plan, list_plans, submit_plan  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import PlanCardRecord  # noqa: E402

_FIELD = {"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}


@pytest.mark.no_app_db
def test_render_emits_nine_copy_sections_in_order() -> None:
    card = render_plan_card(
        [_FIELD],
        goal="Add a note",
        assumptions=["the field is empty"],
        environment="staging",
    )
    titles = [section["title"] for section in card["sections"]]
    assert titles == list(PLAN_CARD_COPY_SECTIONS)
    assert len(card["sections"]) == 9
    bodies = [section["body"] for section in card["sections"]]
    assert all(isinstance(body, str) and body for body in bodies)
    assert "Add a note" in card["sections"][0]["body"]
    assert "the field is empty" in card["sections"][0]["body"]
    assert "field.create" in card["sections"][1]["body"]
    assert card["sections"][8]["body"].startswith(card["plan_hash"])


@pytest.mark.no_app_db
def test_changing_an_assumption_produces_a_new_hash_and_voids_the_old_card() -> None:
    inbox = Inbox()
    first = inbox.submit(
        [_FIELD],
        goal="Add a note",
        assumptions=["empty"],
        environment="staging",
        requester_id="u1",
        known_models={"x_m"},
        connection_id="c1",
    )
    assert first["ok"] is True
    old_hash = first["card"]["plan_hash"]
    second = inbox.submit(
        [_FIELD],
        goal="Add a note",
        assumptions=["the host already has the field"],
        environment="staging",
        requester_id="u1",
        known_models={"x_m"},
        connection_id="c1",
    )
    assert second["ok"] is True
    new_hash = second["card"]["plan_hash"]
    assert new_hash != old_hash
    assert new_hash == compute_plan_hash([_FIELD], assumptions=["the host already has the field"])
    assert inbox.cards[old_hash]["status"] == "voided"
    assert inbox.cards[new_hash]["status"] == "pending"
    with pytest.raises(InboxError, match="not pending"):
        inbox.decide(old_hash, approver_id="u2", decision="approve", connection_id="c1")


def test_persisted_assumption_change_voids_the_old_card() -> None:
    init_db()
    db = SessionLocal()
    try:
        connection = f"t605-{uuid.uuid4().hex[:8]}"
        first = submit_plan(
            db,
            changeset=[_FIELD],
            goal="Add a note",
            assumptions=["empty"],
            environment="staging",
            requester_id="user-1",
            known_models={"x_m"},
            connection_id=connection,
        )
        assert first["ok"] is True
        old = first["card"]
        second = submit_plan(
            db,
            changeset=[_FIELD],
            goal="Add a note",
            assumptions=["revised"],
            environment="staging",
            requester_id="user-1",
            known_models={"x_m"},
            connection_id=connection,
        )
        assert second["ok"] is True
        new = second["card"]
        assert new["plan_hash"] != old["plan_hash"]
        listed = {card["plan_hash"]: card for card in list_plans(db, connection)}
        assert listed[old["plan_hash"]]["status"] == "voided"
        assert listed[new["plan_hash"]]["status"] == "pending"
        with pytest.raises(InboxError, match="not pending"):
            decide_plan(
                db,
                old["plan_hash"],
                approver_id="user-2",
                decision="approve",
                connection_id=connection,
                body_plan_hash=old["plan_hash"],
                schema_fp=old["schema_fp"],
            )
    finally:
        db.close()


def test_listed_card_includes_nine_section_titles_in_order() -> None:
    init_db()
    db = SessionLocal()
    try:
        connection = f"t605-list-{uuid.uuid4().hex[:8]}"
        result = submit_plan(
            db,
            changeset=[_FIELD],
            goal="Add a note",
            assumptions=["empty"],
            environment="staging",
            requester_id="user-1",
            known_models={"x_m"},
            connection_id=connection,
        )
        assert result["ok"] is True
        row = (
            db.query(PlanCardRecord)
            .filter(
                PlanCardRecord.connection_id == connection,
                PlanCardRecord.plan_hash == result["card"]["plan_hash"],
            )
            .one()
        )
        stored = json.loads(row.card_json)
        stored.pop("sections", None)
        row.card_json = json.dumps(stored, sort_keys=True)
        db.add(row)
        db.commit()
        assert "sections" not in json.loads(row.card_json)

        listed = list_plans(db, connection)
        assert len(listed) == 1
        titles = [section["title"] for section in listed[0]["sections"]]
        assert titles == list(PLAN_CARD_COPY_SECTIONS)
    finally:
        db.close()
