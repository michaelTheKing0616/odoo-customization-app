"""REG-NP-5A oracle pins. One positive and one negative test per AC."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from odoo_client.rpc_policy import NEVER_ALLOWED

from app.agent_runtime.runtime import (
    MAX_STEPS,
    MAX_TOOL_CALLS,
    AgentRuntime,
    BudgetExceeded,
)
from app.audit_chain import GENESIS_PREV_HASH, verify_chain
from app.blast_radius import (
    PRODUCTION_APPLY_RECORD_CAP,
    BlastRadiusExceeded,
    assert_production_apply_records,
)
from app.changeset.policy import policy_decision, self_approval_allowed
from app.mcp_guard import McpWriteForbidden, mcp_call
from app.plan_fingerprint import plan_fingerprint, structural_dry_run_hash
from app.rollback_tiers import NOT_REVERSIBLE_BY_THIS_TIER, build_compensating_plan
from app.rpc_classify import READ_METHODS, classify_rpc, policy_allows
from app.snapshot_gate import (
    FRESHNESS_WINDOW,
    SnapshotRequired,
    require_production_snapshot,
)
from app.worker_bot.l4_policy import L4_MAX_BLAST

_ROOT = Path(__file__).resolve().parents[3]
_RPC_TESTS = _ROOT / "apps/api/tests/test_rpc_classify.py"
_AUDIT_TESTS = _ROOT / "apps/api/tests/test_audit_chain.py"
_BRIDGE_TESTS = _ROOT / "apps/api/tests/test_bridge_protocol.py"
_EXECUTOR_TESTS = _ROOT / "apps/api/tests/test_executor_bridge.py"
_T6_CARD = _ROOT / "docs/plans/next-phase/cards/T6_AUTH_INBOX.md"

_DRY_RUN_HASH = "1358816a89d96233a63b788dcb12f9c9d236a6a59da1065b5edfd328def8cbb2"
_PLAN_FINGERPRINT = "8a1e31fc0a9b80d0"
_VERBATIM_READ_METHODS = frozenset(
    {
        "search",
        "search_read",
        "read",
        "search_count",
        "fields_get",
        "name_search",
        "default_get",
        "read_group",
        "formatted_read_group",
        "context_get",
        "exists",
        "get_views",
    }
)
_VERBATIM_NEVER_ALLOWED = (
    ("res.users", "unlink"),
    ("res.company", "unlink"),
    ("ir.model.data", "unlink"),
    ("ir.config_parameter", "unlink"),
    ("res.users.apikeys", "*"),
)
_RPC_ORACLE_NAMES = (
    "test_read_is_read",
    "test_create_is_reversible",
    "test_unlink_destructive_and_forbidden",
    "test_security_models_destructive",
    "test_billable_depends_on_edition",
    "test_protected_params_forbidden",
    "test_mass_write",
    "test_policy_thresholds",
)
_AUDIT_ORACLE_NAMES = (
    "test_audit_chain_and_tamper",
    "test_redaction",
)
_KILL_SWITCH_BRIDGE = "test_kill_switch_protocol_and_escalation_refuse_before_work"
_KILL_SWITCH_EXECUTOR = "test_reader_and_kill_switch_do_not_touch_the_port_or_journal"


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _has_assert(fn: ast.FunctionDef) -> bool:
    return any(isinstance(node, ast.Assert) for node in ast.walk(fn))


def _string_constants(fn: ast.FunctionDef) -> set[str]:
    return {
        node.value
        for node in ast.walk(fn)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_ac1_search_read_maps_to_bucket_a() -> None:
    classified = classify_rpc("res.partner", "search_read", ids=[1])
    assert classified.risk == "READ"
    assert classified.bucket == "A"
    assert classified.forbidden is False
    assert READ_METHODS == _VERBATIM_READ_METHODS


def test_ac1_mutations_are_not_bucket_a() -> None:
    created = classify_rpc("res.partner", "create", values={"name": "x"})
    assert created.risk == "REVERSIBLE"
    assert created.bucket == "B"
    assert created.forbidden is False

    unlinked = classify_rpc("res.partner", "unlink", ids=[1])
    assert unlinked.risk == "DESTRUCTIVE"
    assert unlinked.bucket == "C"
    assert unlinked.forbidden is False

    community = classify_rpc("ir.module.module", "button_install", edition="community")
    assert community.risk == "DESTRUCTIVE"
    assert community.bucket == "C"
    assert community.forbidden is False

    enterprise = classify_rpc("ir.module.module", "button_install", edition="enterprise")
    assert enterprise.risk == "BILLABLE"
    assert enterprise.bucket == "C"
    assert enterprise.forbidden is False

    mass = classify_rpc("res.partner", "write", ids=list(range(51)), values={"name": "a"})
    assert mass.risk == "DESTRUCTIVE"
    assert mass.bucket == "C"
    assert mass.forbidden is False
    assert mass.reason == "mass_write"


def test_ac2_structural_hash_drops_dry_run() -> None:
    with_flag = structural_dry_run_hash("install", {"a": 1, "dry_run": True})
    without_flag = structural_dry_run_hash("install", {"a": 1})
    reordered = structural_dry_run_hash("install", {"dry_run": False, "a": 1})
    assert with_flag == _DRY_RUN_HASH
    assert without_flag == _DRY_RUN_HASH
    assert reordered == _DRY_RUN_HASH


def test_ac2_changed_payload_changes_the_hash() -> None:
    other_args = structural_dry_run_hash("install", {"a": 2, "dry_run": True})
    other_tool = structural_dry_run_hash("apply", {"a": 1, "dry_run": True})
    assert other_args != _DRY_RUN_HASH
    assert other_tool != _DRY_RUN_HASH


def test_ac3_fingerprint_excludes_res_id() -> None:
    with_id = plan_fingerprint([{"op": "write", "res_id": 5, "vals": {"name": "a"}}])
    without_id = plan_fingerprint([{"op": "write", "vals": {"name": "a"}}])
    assert with_id == _PLAN_FINGERPRINT
    assert without_id == _PLAN_FINGERPRINT
    assert len(with_id) == 16


def test_ac3_changed_vals_change_the_fingerprint() -> None:
    changed = plan_fingerprint([{"op": "write", "res_id": 5, "vals": {"name": "b"}}])
    assert changed != _PLAN_FINGERPRINT
    assert len(changed) == 16


def test_ac4_approved_unlink_stays_never_allowed() -> None:
    classified = classify_rpc("res.users", "unlink", ids=[1], approved=True)
    assert classified.forbidden is True
    assert classified.reason == "never_allowed"
    assert classified.risk == "DESTRUCTIVE"
    assert classified.bucket == "C"
    assert NEVER_ALLOWED == _VERBATIM_NEVER_ALLOWED


def test_ac4_never_allowed_has_no_policy_override() -> None:
    classified = classify_rpc("res.users", "unlink", ids=[1], approved=True)
    assert policy_allows(classified, environment="staging") is False
    assert policy_allows(classified, environment="production") is False


def test_ac5_empty_chain_verifies() -> None:
    assert GENESIS_PREV_HASH == "0" * 64
    assert verify_chain([]) == (True, None)


def test_ac5_wrong_prev_hash_breaks_at_zero() -> None:
    assert verify_chain([{"prev_hash": "1" * 64}]) == (False, 0)


def test_ac6_staging_and_fresh_snapshot_pass() -> None:
    require_production_snapshot(
        write_mode="staging",
        risk="destructive",
        snapshot_id=None,
        snapshot_exists=False,
    )
    require_production_snapshot(
        write_mode="production",
        risk="read",
        snapshot_id=None,
        snapshot_exists=False,
    )
    now = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
    require_production_snapshot(
        write_mode="production",
        risk="destructive",
        snapshot_id="snap-fresh",
        snapshot_exists=True,
        snapshot_created_at=now - timedelta(minutes=9),
        now=now,
    )
    assert FRESHNESS_WINDOW == timedelta(minutes=10)


def test_ac6_missing_or_stale_production_snapshot_raises() -> None:
    required = "A snapshot recorded for this connection is required"
    with pytest.raises(SnapshotRequired, match=required):
        require_production_snapshot(
            write_mode="production",
            risk="destructive",
            snapshot_id=None,
            snapshot_exists=False,
        )
    with pytest.raises(SnapshotRequired, match=required):
        require_production_snapshot(
            write_mode="production",
            risk="billable",
            snapshot_id=None,
            snapshot_exists=False,
        )
    now = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
    with pytest.raises(SnapshotRequired, match="older than the 10-minute freshness window"):
        require_production_snapshot(
            write_mode="production",
            risk="destructive",
            snapshot_id="snap-old",
            snapshot_exists=True,
            snapshot_created_at=now - timedelta(minutes=11),
            now=now,
        )


def test_ac7_mcp_search_returns_read() -> None:
    assert mcp_call("search") == "read"


def test_ac7_mcp_create_is_forbidden() -> None:
    with pytest.raises(McpWriteForbidden, match="MCP cannot call create"):
        mcp_call("create")


def test_ac8_production_allows_read() -> None:
    read = classify_rpc("res.partner", "read", ids=[1])
    search = classify_rpc("res.partner", "search_read", ids=[1])
    assert policy_allows(read, environment="production") is True
    assert policy_allows(search, environment="production") is True


def test_ac8_production_refuses_non_read() -> None:
    created = classify_rpc("res.partner", "create", values={"name": "x"})
    unlinked = classify_rpc("res.partner", "unlink", ids=[1])
    users = classify_rpc("res.users", "unlink", ids=[1], approved=True)
    community = classify_rpc("ir.module.module", "button_install", edition="community")
    enterprise = classify_rpc("ir.module.module", "button_install", edition="enterprise")
    mass = classify_rpc("res.partner", "write", ids=list(range(51)), values={"name": "a"})
    assert policy_allows(created, environment="production") is False
    assert policy_allows(unlinked, environment="production") is False
    assert policy_allows(users, environment="production") is False
    assert policy_allows(community, environment="production") is False
    assert policy_allows(enterprise, environment="production") is False
    assert policy_allows(mass, environment="production") is False


def test_ac9_staging_allows_read_and_create() -> None:
    read = classify_rpc("res.partner", "read", ids=[1])
    created = classify_rpc("res.partner", "create", values={"name": "x"})
    assert policy_allows(read, environment="staging") is True
    assert policy_allows(created, environment="staging") is True


def test_ac9_staging_refuses_destructive() -> None:
    unlinked = classify_rpc("res.partner", "unlink", ids=[1])
    users = classify_rpc("res.users", "unlink", ids=[1], approved=True)
    community = classify_rpc("ir.module.module", "button_install", edition="community")
    enterprise = classify_rpc("ir.module.module", "button_install", edition="enterprise")
    mass = classify_rpc("res.partner", "write", ids=list(range(51)), values={"name": "a"})
    assert policy_allows(unlinked, environment="staging") is False
    assert policy_allows(users, environment="staging") is False
    assert policy_allows(community, environment="staging") is False
    assert policy_allows(enterprise, environment="staging") is False
    assert policy_allows(mass, environment="staging") is False


def test_ac10_named_oracle_tests_exist() -> None:
    rpc_names = set(_functions(_RPC_TESTS))
    audit_names = set(_functions(_AUDIT_TESTS))
    assert set(_RPC_ORACLE_NAMES) <= rpc_names
    assert set(_AUDIT_ORACLE_NAMES) <= audit_names


def test_ac10_named_oracle_tests_assert() -> None:
    rpc_fns = _functions(_RPC_TESTS)
    audit_fns = _functions(_AUDIT_TESTS)
    for name in _RPC_ORACLE_NAMES:
        assert _has_assert(rpc_fns[name])
    for name in _AUDIT_ORACLE_NAMES:
        assert _has_assert(audit_fns[name])


def test_ac11_created_partner_emits_unlink() -> None:
    plan = build_compensating_plan(
        [
            {
                "kind": "change",
                "payload": {"model": "res.partner", "action": "created", "res_id": 4},
            }
        ]
    )
    assert plan.changeset == [
        {"type": "data.unlink", "params": {"model": "res.partner", "ids": [4]}}
    ]
    assert plan.refused is False
    assert plan.not_reversible_by_this_tier == []


def test_ac11_irreversible_rows_are_not_inverted() -> None:
    blocked = build_compensating_plan(
        [
            {
                "kind": "change",
                "payload": {
                    "model": "ir.module.module",
                    "action": "button_install",
                    "res_id": 3,
                },
            },
            {
                "kind": "change",
                "payload": {"model": "account.move", "action": "posted", "res_id": 9},
            },
        ]
    )
    assert blocked.changeset == []
    assert blocked.refused is False
    assert {row["model"] for row in blocked.not_reversible_by_this_tier} == {
        "ir.module.module",
        "account.move",
    }
    assert {row["reason"] for row in blocked.not_reversible_by_this_tier} == {
        NOT_REVERSIBLE_BY_THIS_TIER
    }
    assert NOT_REVERSIBLE_BY_THIS_TIER == "not reversible by this tier"

    users = build_compensating_plan(
        [
            {
                "kind": "change",
                "payload": {"model": "res.users", "action": "created", "res_id": 1},
            }
        ]
    )
    assert users.refused is True
    assert users.reason == "never_allowed"
    assert users.changeset == []


def test_ac12_budgets_and_pointers_hold() -> None:
    assert MAX_STEPS == 40
    assert MAX_TOOL_CALLS == 120
    assert PRODUCTION_APPLY_RECORD_CAP == 200
    assert L4_MAX_BLAST == 50
    runtime = AgentRuntime()
    stepped = runtime.start()
    stepped.step = 39
    runtime.complete_phase(stepped, "DISCOVER")
    assert stepped.step == 40

    called = runtime.start()
    called.phase = "DISCOVER"
    called.tool_calls = 119
    runtime.call_tool(called, "schema_search", {})
    assert called.tool_calls == 120

    assert_production_apply_records(200, environment="production")
    assert self_approval_allowed("R3") is True
    assert policy_decision("R3", "production", autonomy="L4")["approvers"] == 1

    headings = [
        line
        for line in _T6_CARD.read_text(encoding="utf-8").splitlines()
        if line.startswith("### T6-04") or line.startswith("### T6-06")
    ]
    assert any(line.startswith("### T6-04") for line in headings)
    assert any(line.startswith("### T6-06") for line in headings)

    bridge = _functions(_BRIDGE_TESTS)
    executor = _functions(_EXECUTOR_TESTS)
    assert "kill_switch" in _string_constants(bridge[_KILL_SWITCH_BRIDGE])
    assert "kill_switch" in _string_constants(executor[_KILL_SWITCH_EXECUTOR])


def test_ac12_over_budget_is_refused() -> None:
    runtime = AgentRuntime()
    stepped = runtime.start()
    stepped.step = 40
    with pytest.raises(BudgetExceeded, match="max steps"):
        runtime.complete_phase(stepped, "DISCOVER")
    assert stepped.status == "aborted_budget"

    called = runtime.start()
    called.phase = "DISCOVER"
    called.tool_calls = 120
    with pytest.raises(BudgetExceeded, match="max tool calls"):
        runtime.call_tool(called, "schema_search", {})
    assert called.status == "aborted_budget"

    with pytest.raises(BlastRadiusExceeded):
        assert_production_apply_records(201, environment="production")
