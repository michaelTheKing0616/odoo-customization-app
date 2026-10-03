"""T8-SIM. Four simulation modes on in-memory fakes. No socket and no Odoo."""

from __future__ import annotations

import socket

import pytest

from app.agent_runtime.phases import assert_transition
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
    policy_allows_r1_direct,
    recorded_simulation,
    reset_simulations,
    run_mode,
    simulate,
)

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _isolated_simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_simulations()

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


def test_static_mode_always_runs() -> None:
    plans = ([_menu()], [_field()], [_access()])
    for ops in plans:
        report = simulate(ops, records=_records())
        assert report.selected[0] == MODE_STATIC
        static = _mode(report, MODE_STATIC)
        assert static.passed is True
        assert static.path_taken is True
        assert static.detail == "static"
        assert static.socket_opened is False
        assert static.live is False
        assert static.contacted_odoo is False
        assert report.live is False
        assert report.socket_opened is False
        assert_transition("SIMULATE", report.phase)
        assert report.phase == "PRESENT"


def test_bridge_inplace_dry_run_for_non_ddl() -> None:
    op = _menu()
    assert get_op("menu.create").ddl is False
    assert risk_of(op) == "R1"
    records = _records()
    report = simulate([op], records=records)
    assert report.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_SYNTHETIC)
    bridge = _mode(report, MODE_BRIDGE_INPLACE)
    assert bridge.passed is True
    assert bridge.path_taken is True
    assert bridge.detail == "rolled_back"
    assert bridge.rolled_back is True
    assert bridge.writes == 0
    assert bridge.target == "scratch"
    assert bridge.op_types == ("menu.create",)
    assert bridge.live is False
    assert bridge.contacted_odoo is False
    assert bridge.copied_customer_database is False
    assert records == {"rows": [{"id": "local-1"}]}
    assert "_applied" not in records


def test_staging_mode_for_ddl() -> None:
    op = _field()
    assert get_op("field.create").ddl is True
    assert risk_of(op) == "R2"
    records = _records()
    report = simulate([op], records=records)
    assert report.selected == (MODE_STATIC, MODE_STAGING, MODE_SYNTHETIC)
    staging = _mode(report, MODE_STAGING)
    assert staging.passed is True
    assert staging.path_taken is True
    assert staging.detail == "neutralized_clone"
    assert staging.target == "staging"
    assert staging.op_types == ("field.create",)
    assert staging.writes == 0
    assert staging.copied_customer_database is False
    assert staging.live is False
    assert staging.contacted_odoo is False
    assert records == {"rows": [{"id": "local-1"}]}
    assert "_neutralized" not in records


def test_staging_mode_for_risk_at_or_above_r3() -> None:
    op = _access()
    assert get_op("access.create").ddl is False
    assert risk_of(op) == "R3"
    report = simulate([op], records=_records())
    assert report.risk == "R3"
    assert report.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_STAGING, MODE_SYNTHETIC)
    staging = _mode(report, MODE_STAGING)
    assert staging.passed is True
    assert staging.target == "staging"
    assert staging.detail == "neutralized_clone"
    assert staging.op_types == ("access.create",)
    assert staging.copied_customer_database is False

    escalated = simulate([_menu()], risk="R4", records=_records())
    assert escalated.risk == "R4"
    assert escalated.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_STAGING, MODE_SYNTHETIC)

    held_down = simulate([op], risk="R0", records=_records())
    assert held_down.risk == "R3"
    assert held_down.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_STAGING, MODE_SYNTHETIC)

    functional = simulate([_report()], records=_records())
    assert functional.risk == "R2"
    assert functional.selected == (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_SYNTHETIC)


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
    assert synthetic.contacted_odoo is False
    assert synthetic.copied_customer_database is False
    assert "local-1" not in synthetic.synthetic_ids
    assert records == {"rows": [{"id": "local-1"}]}


def test_failed_simulation_returns_the_plan_to_planning() -> None:
    ops = [_menu()]
    passed = simulate(ops, records=_records())
    assert passed.recorded is True
    assert recorded_simulation(passed.plan_id) is not None

    failed = simulate(ops, records=_records(), fail_mode=MODE_SYNTHETIC)
    assert failed.passed is False
    assert failed.phase == "PLAN"
    assert failed.returned_to_planning is True
    assert failed.recorded is False
    assert failed.live is False
    assert_transition("SIMULATE", failed.phase)
    assert _mode(failed, MODE_STATIC).passed is True
    assert _mode(failed, MODE_SYNTHETIC).passed is False
    assert _mode(failed, MODE_SYNTHETIC).detail == "simulation_failed"
    assert recorded_simulation(failed.plan_id) is None
    with pytest.raises(SimulationRequired) as caught:
        guard_production_apply(ops, environment="production")
    assert caught.value.code == "simulation_required"


def test_production_apply_without_recorded_simulation_is_refused() -> None:
    menu = [_menu()]
    reset_journal()
    with pytest.raises(SimulationRequired) as caught:
        guard_production_apply(menu, environment="production")
    assert caught.value.code == "simulation_required"
    with pytest.raises(SimulationRequired):
        apply(menu, mode="T", environment="production")
    assert get_journal() == []

    report_ops = [_report()]
    assert risk_of(report_ops[0]) == "R2"
    with pytest.raises(SimulationRequired):
        guard_production_apply(report_ops, environment="production")

    recorded = simulate(menu, records=_records())
    assert recorded.passed is True
    assert recorded.recorded is True
    assert guard_production_apply(menu, environment="production") is None
    with pytest.raises(SimulationRequired):
        guard_production_apply(report_ops, environment="production")
    assert guard_production_apply(menu, environment="staging") is None
    admitted = apply(menu, mode="T", environment="production")
    assert admitted["status"] in {"APPLIED", "VERIFIED"}
    assert admitted["applied_count"] == 1
    reset_journal()


def test_r1_direct_policy_allows_production_apply_without_simulation() -> None:
    menu = [_menu()]
    matrix = policy_decision("R1", "production")
    assert matrix["needs_simulation"] is True
    assert policy_allows_r1_direct("R1", matrix) is False
    with pytest.raises(SimulationRequired):
        guard_production_apply(menu, environment="production", decision=matrix)

    direct = {"allow": True, "approvers": 1, "needs_simulation": False, "deny": False}
    assert policy_allows_r1_direct("R1", direct) is True
    assert policy_allows_r1_direct("R2", direct) is False
    admitted = guard_production_apply(
        menu,
        environment="production",
        risk="R1",
        decision=direct,
    )
    assert admitted is None
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


def test_ddl_op_does_not_take_the_inplace_dry_run_path() -> None:
    records = _records()
    forged = {**_field(), "ddl": False}
    report = simulate([forged], records=records)
    assert MODE_BRIDGE_INPLACE not in report.selected
    assert report.selected == (MODE_STATIC, MODE_STAGING, MODE_SYNTHETIC)
    assert records == {"rows": [{"id": "local-1"}]}

    refused = run_mode(MODE_BRIDGE_INPLACE, [forged], records=records)
    assert refused.path_taken is False
    assert refused.passed is False
    assert refused.detail == "ddl_no_inplace"
    assert refused.op_types == ("field.create",)
    assert refused.writes == 0
    assert refused.live is False
    assert records == {"rows": [{"id": "local-1"}]}

    mixed_records = _records()
    mixed = simulate([_menu(), forged], records=mixed_records)
    bridge = _mode(mixed, MODE_BRIDGE_INPLACE)
    assert bridge.path_taken is True
    assert bridge.op_types == ("menu.create",)
    staging = _mode(mixed, MODE_STAGING)
    assert staging.op_types == ("field.create",)
    assert mixed_records == {"rows": [{"id": "local-1"}]}
