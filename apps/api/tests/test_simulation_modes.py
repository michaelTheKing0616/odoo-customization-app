"""T8-SIM acceptance: one test per mode, plan-hash binding, INV-06."""

from __future__ import annotations

import socket

import pytest

from app.changeset.executor import apply, get_journal, reset_journal
from app.changeset.ops import get_op
from app.changeset.policy import policy_decision, risk_of
from app.changeset.simulate import (
    MODE_BRIDGE_INPLACE,
    MODE_STAGING,
    MODE_STATIC,
    MODE_SYNTHETIC,
    SimulationRequired,
    guard_production_apply,
    plan_hash,
    policy_allows_r1_direct,
    recorded_simulation,
    reset_simulations,
    select_modes,
    simulate,
)

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_simulations()
    reset_journal()

    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("simulation opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _menu() -> dict:
    return {"type": "menu.create", "params": {"model": "ir.ui.menu"}}


def _field() -> dict:
    return {
        "type": "field.create",
        "params": {"model": "sale.order", "name": "x_note", "field_type": "char"},
    }


def _access() -> dict:
    return {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}}


def _report() -> dict:
    return {"type": "report.inherit", "params": {"model": "sale.order"}}


def _records() -> dict:
    return {"rows": [{"id": "local-1"}]}


def _mode(report, name: str):
    return next(item for item in report.modes if item.mode == name)


class FakeStagingPort:
    """In-process staging stand-in. No host, socket, or real database."""

    def __init__(self) -> None:
        self.staging_runs: list[list[str]] = []
        self.created_databases: list[str] = []


def test_static_mode() -> None:
    ops = [_menu()]
    report = simulate(ops, records=_records())
    assert report.selected[0] == MODE_STATIC
    static = _mode(report, MODE_STATIC)
    assert static.passed is True
    assert static.path_taken is True
    assert static.detail == "static"
    assert static.live is False
    assert static.contacted_odoo is False
    assert report.phase == "PRESENT"
    assert report.plan_hash == plan_hash(ops)


def test_bridge_inplace_dry_run_mode_for_non_ddl() -> None:
    op = _menu()
    assert get_op("menu.create").ddl is False
    records = _records()
    report = simulate([op], records=records)
    assert MODE_BRIDGE_INPLACE in report.selected
    assert MODE_STAGING not in report.selected
    bridge = _mode(report, MODE_BRIDGE_INPLACE)
    assert bridge.passed is True
    assert bridge.path_taken is True
    assert bridge.rolled_back is True
    assert bridge.detail == "rolled_back"
    assert bridge.target == "scratch"
    assert bridge.op_types == ("menu.create",)
    assert bridge.live is False
    assert records == {"rows": [{"id": "local-1"}]}


def test_staging_mode_for_ddl_and_high_risk() -> None:
    field = _field()
    assert get_op("field.create").ddl is True
    assert risk_of(field) == "R2"
    records = _records()
    port = FakeStagingPort()
    report = simulate([field], records=records, staging_port=port)
    assert report.selected == (MODE_STATIC, MODE_STAGING, MODE_SYNTHETIC)
    staging = _mode(report, MODE_STAGING)
    assert staging.passed is True
    assert staging.path_taken is True
    assert staging.target == "staging"
    assert staging.detail == "fake_staging_port"
    assert staging.copied_customer_database is False
    assert port.staging_runs == [["field.create"]]
    assert port.created_databases == []
    assert records == {"rows": [{"id": "local-1"}]}

    access = _access()
    assert get_op("access.create").ddl is False
    assert risk_of(access) == "R3"
    high = simulate([access], records=_records())
    assert high.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_STAGING, MODE_SYNTHETIC)
    assert select_modes([_menu()], "R4") == (
        MODE_STATIC,
        MODE_BRIDGE_INPLACE,
        MODE_STAGING,
        MODE_SYNTHETIC,
    )


def test_synthetic_record_mode() -> None:
    records = _records()
    report = simulate([_menu(), _report()], records=records)
    synthetic = _mode(report, MODE_SYNTHETIC)
    assert synthetic.passed is True
    assert synthetic.path_taken is True
    assert synthetic.target == "synthetic"
    assert synthetic.detail == "synthetic_rows"
    assert synthetic.synthetic_ids == ("synthetic-1", "synthetic-2")
    assert synthetic.live is False
    assert "local-1" not in synthetic.synthetic_ids
    assert records == {"rows": [{"id": "local-1"}]}


def test_failed_simulation_returns_plan_to_planning() -> None:
    ops = [_menu()]
    ok = simulate(ops, records=_records())
    assert ok.recorded is True
    assert recorded_simulation(ok.plan_id) is not None

    failed = simulate(ops, records=_records(), fail_mode=MODE_BRIDGE_INPLACE)
    assert failed.passed is False
    assert failed.phase == "PLAN"
    assert failed.returned_to_planning is True
    assert failed.recorded is False
    assert failed.plan_hash == plan_hash(ops)
    assert recorded_simulation(failed.plan_id) is None
    with pytest.raises(SimulationRequired):
        guard_production_apply(ops, environment="production")


def test_production_apply_refused_without_recorded_simulation() -> None:
    menu = [_menu()]
    with pytest.raises(SimulationRequired) as caught:
        guard_production_apply(menu, environment="production")
    assert caught.value.code == "simulation_required"
    with pytest.raises(SimulationRequired):
        apply(menu, mode="T", environment="production")
    assert get_journal() == []

    recorded = simulate(menu, records=_records())
    assert recorded.passed is True
    assert recorded.plan_hash == plan_hash(menu)
    assert guard_production_apply(menu, environment="production") is None
    assert guard_production_apply(menu, environment="staging") is None


def test_production_apply_refused_when_recorded_sim_is_for_different_plan_hash() -> None:
    menu = [_menu()]
    other = [_field()]
    recorded = simulate(menu, records=_records())
    assert recorded.passed is True
    assert recorded.plan_hash == plan_hash(menu)
    assert recorded.plan_hash != plan_hash(other)
    assert guard_production_apply(menu, environment="production") is None
    with pytest.raises(SimulationRequired):
        guard_production_apply(other, environment="production")
    with pytest.raises(SimulationRequired):
        apply(other, mode="T", environment="production")
    assert get_journal() == []

    # Same ledger entry must not cover a mutated plan (different ops / hash).
    mutated = [{"type": "menu.create", "params": {"model": "ir.ui.menu", "name": "Other"}}]
    assert plan_hash(mutated) != recorded.plan_hash
    with pytest.raises(SimulationRequired):
        guard_production_apply(mutated, environment="production")


def test_r1_direct_allowed_only_where_policy_allows() -> None:
    menu = [_menu()]
    assert risk_of(menu[0]) == "R1"
    matrix = policy_decision("R1", "production")
    assert matrix["needs_simulation"] is True
    assert policy_allows_r1_direct("R1", matrix) is False
    with pytest.raises(SimulationRequired):
        guard_production_apply(menu, environment="production", decision=matrix)

    direct = {"allow": True, "approvers": 1, "needs_simulation": False, "deny": False}
    assert policy_allows_r1_direct("R1", direct) is True
    assert policy_allows_r1_direct("R2", direct) is False
    assert policy_allows_r1_direct("R3", direct) is False
    assert guard_production_apply(menu, environment="production", decision=direct) is None

    with pytest.raises(SimulationRequired):
        guard_production_apply(
            [_report()],
            environment="production",
            risk="R2",
            decision=direct,
        )
    with pytest.raises(SimulationRequired):
        guard_production_apply(
            [_field()],
            environment="production",
            risk="R1",
            decision=direct,
        )
