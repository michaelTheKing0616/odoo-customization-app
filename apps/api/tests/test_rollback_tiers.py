"""5A-11 — compensating plan from change rows through the change-set pipeline."""

from __future__ import annotations

import pytest

from app.changeset.executor import reset_journal
from app.rollback_tiers import (
    NOT_REVERSIBLE_BY_THIS_TIER,
    CompensatingRefused,
    build_compensating_plan,
    run_compensating_pipeline,
)
from app.rpc_classify import classify_rpc


def test_compensating_plan_from_change_rows_goes_through_pipeline() -> None:
    reset_journal()
    rows = [
        {
            "kind": "change",
            "payload": {
                "model": "res.partner",
                "action": "created",
                "res_id": 12,
                "changes": {"name": {"old": None, "new": "Acme"}},
            },
        },
        {
            "kind": "change",
            "payload": {
                "model": "res.partner",
                "action": "updated",
                "res_id": 4,
                "changes": {"name": {"old": "Old Co", "new": "New Co"}},
            },
        },
    ]
    plan = build_compensating_plan(rows)
    assert plan.refused is False
    assert [op["type"] for op in plan.changeset] == ["data.update_batch", "data.unlink"]
    assert plan.changeset[0]["params"]["values"] == {"name": "Old Co"}
    assert plan.changeset[1]["params"] == {"model": "res.partner", "ids": [12]}

    result = run_compensating_pipeline(plan, known_models={"res.partner"}, environment="staging")
    assert result["ok"] is True
    assert result["validation"]["valid"] is True
    assert result["stage"] == "apply"
    assert all(item["deny"] is False for item in result["policy"])
    assert result["apply"]["status"] == "VERIFIED"
    assert result["apply"]["mode"] == "T"


def test_module_install_and_posted_entries_not_reversible_by_this_tier() -> None:
    plan = build_compensating_plan(
        [
            {
                "model": "ir.module.module",
                "action": "updated",
                "res_id": 8,
                "changes": {"state": {"old": "uninstalled", "new": "installed"}},
            },
            {
                "model": "account.move",
                "action": "updated",
                "res_id": 33,
                "changes": {"state": {"old": "draft", "new": "posted"}},
            },
            {
                "kind": "change",
                "payload": {
                    "model": "res.partner",
                    "action": "created",
                    "res_id": 1,
                    "changes": {},
                },
            },
        ]
    )
    kinds = {item["kind"] for item in plan.not_reversible_by_this_tier}
    assert kinds == {"module_install", "posted_entry"}
    assert all(
        item["reason"] == NOT_REVERSIBLE_BY_THIS_TIER
        for item in plan.not_reversible_by_this_tier
    )
    assert [op["type"] for op in plan.changeset] == ["data.unlink"]
    assert plan.changeset[0]["params"]["model"] == "res.partner"


def test_compensating_plan_unlink_res_users_refused_by_never_allowed() -> None:
    blocked = classify_rpc("res.users", "unlink", ids=[2])
    assert blocked.forbidden is True
    assert blocked.reason == "never_allowed"

    plan = build_compensating_plan(
        [
            {
                "kind": "change",
                "payload": {
                    "model": "res.users",
                    "action": "created",
                    "res_id": 2,
                    "changes": {"login": {"old": None, "new": "tmp"}},
                },
            }
        ]
    )
    assert plan.refused is True
    assert plan.reason == "never_allowed"
    assert plan.changeset == []
    with pytest.raises(CompensatingRefused, match="never_allowed"):
        run_compensating_pipeline(plan)


def test_created_account_move_without_state_is_not_reversible() -> None:
    plan = build_compensating_plan(
        [
            {
                "model": "account.move",
                "action": "created",
                "res_id": 44,
                "changes": {"name": {"old": None, "new": "INV/2026/001"}},
            }
        ]
    )
    assert plan.changeset == []
    assert not any(op.get("type") == "data.unlink" for op in plan.changeset)
    assert plan.not_reversible_by_this_tier
    assert all(
        item["reason"] == NOT_REVERSIBLE_BY_THIS_TIER
        for item in plan.not_reversible_by_this_tier
    )
    assert plan.not_reversible_by_this_tier[0]["model"] == "account.move"


def test_tiers_name_database_snapshot_without_live_restore() -> None:
    plan = build_compensating_plan([])
    by_id = {tier["id"]: tier for tier in plan.tiers}
    snapshot = by_id["database_snapshot"]
    assert snapshot["tier"] == 1
    assert snapshot["requires"] == "/web/database"
    assert snapshot["live_restore"] is False
    assert "odoo_online" in snapshot["not_for"]
    assert "odoo_sh" in snapshot["not_for"]
    assert "odoo_20" in snapshot["not_for"]
    assert by_id["compensating"]["pipeline"] == ("validate", "policy", "apply")
    assert by_id["manual"]["name"] == "Manual changelog"
