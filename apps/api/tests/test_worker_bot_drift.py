"""5C-05: out-of-band drift between plan and apply aborts the bot with STALE."""

from __future__ import annotations

from typing import Any

import pytest
from odoo_client.schema_fingerprint import schema_fingerprint

from app.changeset.executor import get_journal, reset_journal
from app.changeset.ops import OP_CATALOG
from app.worker_bot import WorkerBot

pytestmark = pytest.mark.no_app_db


def _mail_template_create() -> dict[str, Any]:
    return {
        "type": "mail_template.create",
        "params": {"name": "Drift test template", "model": "res.partner"},
    }


def _schema(fields: list[str], **volatile: Any) -> dict[str, Any]:
    slice_data: dict[str, Any] = {"model": "res.partner", "fields": list(fields)}
    slice_data.update(volatile)
    return slice_data


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def test_out_of_band_fake_database_change_aborts_apply_with_stale() -> None:
    """A schema edit after plan must not apply; outcome is STALE and journal stays empty."""
    assert OP_CATALOG["mail_template.create"].risk_base == "R1"
    schema_at_plan = _schema(["name", "email"])
    bot = WorkerBot("L3")
    plan = bot.plan(
        [_mail_template_create()],
        environment="staging",
        requester_id="user-1",
        connection_id="conn-a",
        known_models={"x_m", "res.partner"},
        goal="drift test",
        live_schema=schema_at_plan,
    )
    assert plan["action"] == "planned"
    assert plan.get("schema_fingerprint") == schema_fingerprint(schema_at_plan)

    drifted = _schema(["name", "email", "x_shadow"])
    assert schema_fingerprint(drifted) != plan["schema_fingerprint"]

    out = bot.apply_planned(plan, live_schema=drifted)
    assert out["applied"] is False
    assert out["outcome"] == "STALE"
    assert out["action"] == "aborted"
    assert get_journal() == []
