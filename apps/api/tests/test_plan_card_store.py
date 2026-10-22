"""Persisted plan cards against the local database."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)

from app.changeset.store import decide_plan, list_plans, submit_plan  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402


def test_persisted_card_is_scoped_to_the_connection() -> None:
    init_db()
    db = SessionLocal()
    try:
        connection = "persist-conn-a"
        other = "persist-conn-b"
        result = submit_plan(
            db,
            changeset=[{"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}],
            goal="Add a note",
            assumptions=["empty"],
            environment="staging",
            requester_id="user-1",
            known_models={"x_m"},
            connection_id=connection,
        )
        assert result["ok"] is True
        assert list_plans(db, other) == []
        assert list_plans(db, connection)[0]["plan_hash"] == result["card"]["plan_hash"]
        card = decide_plan(
            db,
            result["card"]["plan_hash"],
            approver_id="user-2",
            decision="approve",
            connection_id=connection,
            body_plan_hash=result["card"]["plan_hash"],
            schema_fp=result["card"]["schema_fp"],
        )
        assert card["status"] == "approved"
    finally:
        db.close()
