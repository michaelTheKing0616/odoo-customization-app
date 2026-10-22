"""REG-NP-T8. Pin schema, UI, logic, settings, simulation, snapshot, and CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.changeset.executor import apply, get_journal, reset_journal
from app.changeset.handlers import all_handlers, apply_memory, compensate_memory, handler_for
from app.changeset.logic_ops import logic_base_raise, safe_eval_ast_issues
from app.changeset.meta_snapshot import MetaSnapshot, equal
from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.schema_ops import (
    CASCADE_FORBIDDEN,
    CONSTRAINT_X_MODELS_ONLY,
    TYPE_CHANGE_UNSUPPORTED,
    constraint_sql_issues,
    field_update_issues,
)
from app.changeset.setting_ops import setting_base_raise
from app.changeset.simulate import (
    SimulationRequired,
    guard_production_apply,
    policy_allows_r1_direct,
    reset_simulations,
    simulate,
)

pytestmark = pytest.mark.no_app_db

_API = Path(__file__).resolve().parents[1]
_FIXTURE = _API / "tests" / "fixtures" / "changeset_cli_two_ops.json"
_SCHEMA_OPS = (
    "model.create",
    "model.scaffold",
    "field.create",
    "field.update",
    "field.deprecate",
    "field.delete",
    "selection.update",
    "constraint.sql",
)
_UI_OPS = (
    "view.inherit.create",
    "view.inherit.update",
    "view.archive",
    "view.create_base",
    "action.window.create",
    "action.window.update",
    "menu.create",
    "menu.update",
    "menu.archive",
    "filter.create",
    "filter.update",
    "report.inherit",
    "report.action.create",
    "report.action.update",
)
_REPORT_OPS = ("report.inherit", "report.action.create", "report.action.update")
_CHANNELS = ("code", "email", "sms", "webhook")
_DIRECT_MATRIX = {"allow": True, "deny": False, "needs_simulation": False}

_FIELD_CREATE = {
    "type": "field.create",
    "params": {"model": "sale.order", "name": "x_po_reference", "ttype": "char"},
}


@pytest.fixture(autouse=True)
def _isolated_reg_np_t8() -> None:
    reset_simulations()
    reset_journal()
    yield
    reset_simulations()
    reset_journal()


def _menu(name: str = "Jobs") -> list[dict[str, Any]]:
    return [{"type": "menu.create", "params": {"name": name, "model": "ir.ui.menu"}}]


def _reverse(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse(item) for item in reversed(value)]
    return value


def _snapshot_payload() -> dict[str, Any]:
    return {
        "fields": [
            {"model": "sale.order", "name": "x_note", "ttype": "char", "selection": ["b", "a"]},
            {"model": "x_job", "name": "x_ref", "ttype": "char"},
        ],
        "menus": [
            {"name": "Jobs", "sequence": 10},
            {"name": "Tasks", "sequence": 20},
        ],
    }


_CLI_TIMEOUT = 180


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.changeset.cli", *args],
        cwd=_API,
        check=False,
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT,
    )


def test_ac1_schema_catalog_memory_round_trip() -> None:
    assert set(all_handlers()) == set(OP_CATALOG)
    for op_type in _SCHEMA_OPS:
        assert op_type in OP_CATALOG
    for op_type in ("model.create", "model.scaffold", "field.create"):
        entry = OP_CATALOG[op_type]
        assert entry.risk_base == "R2"
        assert entry.reversible == "E"
        assert entry.ddl is True
    assert OP_CATALOG["field.update"].risk_base == "R1"
    assert op_base_risk("field.create", {"model": "sale.order", "name": "x_po_reference"}) == "R2"
    assert op_base_risk("field.create", {"compute": "  "}) == "R2"
    assert op_base_risk("field.update", {"model": "sale.order", "name": "x_note"}) == "R1"
    sale_delete = {"model": "sale.order", "name": "x_old", "record_count": 5}
    empty_account = {"model": "account.move", "name": "x_old", "record_count": 0}
    assert op_base_risk("field.delete", sale_delete) == "R3"
    assert op_base_risk("field.delete", empty_account) == "R3"
    assert op_base_risk("field.delete", {"model": "hr.employee", "name": "x_old"}) == "R3"
    assert op_base_risk("constraint.sql", {"model": "x_job"}) == "R3"
    assert constraint_sql_issues({"model": "x_job"}) == []
    same_type = {"model": "sale.order", "name": "x_note", "ttype": "char", "current_type": "char"}
    assert field_update_issues(same_type) == []
    plain = {"model": "sale.order", "name": "x_po_reference", "ttype": "char"}
    assert CASCADE_FORBIDDEN not in handler_for("field.create").issues(plain)

    store: dict[str, dict[str, Any]] = {}
    apply_memory(store, _FIELD_CREATE)
    assert store == {
        "field.create:sale.order:x_po_reference": {
            "type": "field.create",
            "params": dict(_FIELD_CREATE["params"]),
        }
    }
    compensate_memory(store, _FIELD_CREATE)
    assert store == {}


def test_ac1_schema_refuses_compute_type_change_cascade_and_non_x_constraint() -> None:
    assert op_base_risk("field.create", {"compute": "_compute_x"}) == "R3"
    assert op_base_risk("field.update", {"compute": "_compute_x"}) == "R3"
    for model in ("account.move", "hr.employee", "stock.quant"):
        crowded = {"model": model, "name": "x_old", "record_count": 3}
        assert op_base_risk("field.delete", crowded) == "R4"
    change = {"model": "sale.order", "name": "x_note", "ttype": "integer", "current_type": "char"}
    assert TYPE_CHANGE_UNSUPPORTED == "field type change is unsupported"
    assert field_update_issues(change) == [TYPE_CHANGE_UNSUPPORTED]
    assert handler_for("field.update").issues(change) == [TYPE_CHANGE_UNSUPPORTED]
    assert constraint_sql_issues({"model": "sale.order"}) == [CONSTRAINT_X_MODELS_ONLY]
    stock_constraint = handler_for("constraint.sql").issues({"model": "sale.order"})
    assert stock_constraint == [CONSTRAINT_X_MODELS_ONLY]
    assert op_base_risk("constraint.sql", {"model": "sale.order"}) == "R3"
    cascade_field = {
        "model": "sale.order",
        "name": "x_po_reference",
        "ttype": "many2one",
        "relation": "res.partner",
        "on_delete": "cascade",
    }
    assert handler_for("field.create").issues(cascade_field) == [CASCADE_FORBIDDEN]
    scaffold = {"model": "x_job", "fields": [{"name": "x_parent_id", "on_delete": "cascade"}]}
    assert handler_for("model.scaffold").issues(scaffold) == [CASCADE_FORBIDDEN]


def test_ac2_view_inherit_anchor_and_report_ops_are_r2() -> None:
    for op_type in _UI_OPS:
        expected = "R2" if op_type in _REPORT_OPS else "R1"
        assert OP_CATALOG[op_type].risk_base == expected
    anchored = {"model": "sale.order", "xpath": "//field[@name='partner_id']"}
    for op_type in ("view.inherit.create", "view.inherit.update"):
        assert handler_for(op_type).issues(anchored) == []


def test_ac2_view_inherit_rejects_missing_anchor_and_multiple_matches() -> None:
    counted = {"model": "sale.order", "xpath": "//field[@name='partner_id']", "expect_matches": 2}
    for op_type in ("view.inherit.create", "view.inherit.update"):
        handler = handler_for(op_type)
        assert handler.issues({"model": "sale.order"}) != []
        assert handler.issues(counted) != []


def test_ac3_logic_channels_raise_to_r3_and_cron_stays_r3() -> None:
    for op_type in ("server_action.create", "server_action.update"):
        assert logic_base_raise(op_type, {"state": "object_write"}) is None
        assert op_base_risk(op_type, {"state": "object_write"}) == "R2"
        for channel in _CHANNELS:
            assert logic_base_raise(op_type, {"state": channel}) == "R3"
            assert op_base_risk(op_type, {"action_type": channel}) == "R3"
    for op_type in ("automation.create", "automation.update", "automation.disable"):
        assert logic_base_raise(op_type, {"outbound": True}) == "R3"
        assert logic_base_raise(op_type, {"mass": True}) == "R3"
        assert op_base_risk(op_type, {"kind": "outbound"}) == "R3"
        assert op_base_risk(op_type, {"trigger": "mass"}) == "R3"
    plain_sequence = {"code": "sale.order", "name": "Sales"}
    assert logic_base_raise("sequence.create", plain_sequence) is None
    assert op_base_risk("sequence.create", plain_sequence) == "R2"
    for op_type in ("cron.create", "cron.update", "cron.disable"):
        params = {"model": "sale.order", "name": "Nightly"}
        assert OP_CATALOG[op_type].risk_base == "R3"
        assert logic_base_raise(op_type, params) is None
        assert op_base_risk(op_type, params) == "R3"


def test_ac3_sensitive_sequence_is_r4_and_safe_eval_does_not_execute(tmp_path: Path) -> None:
    for op_type in ("sequence.create", "sequence.update"):
        for params in (
            {"code": "sale.order", "name": "Sales", "accounting": True},
            {"code": "sale.order", "name": "Sales", "journal": True},
            {"code": "sale.order", "name": "Sales", "legal": True},
        ):
            assert logic_base_raise(op_type, params) == "R4"
            assert op_base_risk(op_type, params) == "R4"
    target = tmp_path / "executed.txt"
    source = f"open({str(target)!r}, 'w').write('executed')\nraise SystemExit('executed')"
    assert safe_eval_ast_issues(source) == []
    assert target.exists() is False


def test_ac4_module_setting_is_r3_and_install_has_no_inverse() -> None:
    assert setting_base_raise("setting.set", {"key": "module_account"}) == "R3"
    assert op_base_risk("setting.set", {"key": "module_account"}) == "R3"
    assert setting_base_raise("setting.set", {"key": "group_sale_order"}) is None
    assert op_base_risk("setting.set", {"key": "group_sale_order"}) == "R2"
    assert setting_base_raise("config_param.set", {"key": "sale.default_note"}) is None
    assert op_base_risk("config_param.set", {"key": "sale.default_note"}) == "R2"
    assert setting_base_raise("company.update", {"name": "Acme"}) is None
    assert op_base_risk("company.update", {"name": "Acme"}) == "R2"
    install = OP_CATALOG["module.install"]
    assert install.risk_base == "R3"
    assert install.reversible == "S"
    handler = handler_for("module.install")
    assert handler.refuse_reason({"module": "sale"}) is None
    assert handler.inverse({"module": "sale"}) is None


def test_ac4_protected_company_lock_and_uninstall_are_refused() -> None:
    assert setting_base_raise("config_param.set", {"key": "database.secret"}) == "R4"
    assert op_base_risk("config_param.set", {"key": "database.secret"}) == "R4"
    assert setting_base_raise("company.update", {"lock_date": "2026-01-31"}) == "R4"
    assert op_base_risk("company.update", {"lock_date": "2026-01-31"}) == "R4"
    uninstall = OP_CATALOG["module.uninstall"]
    assert uninstall.risk_base == "R4"
    assert uninstall.reversible == "N"
    assert handler_for("module.uninstall").inverse({"module": "sale"}) is None
    store = {"kept": {"type": "field.create", "params": {"name": "x_kept"}}}
    with pytest.raises(PermissionError):
        compensate_memory(store, {"type": "module.uninstall", "params": {"module": "sale"}})
    assert "kept" in store


def test_ac5_recorded_simulation_and_r1_direct_allow_production() -> None:
    menu = _menu()
    assert guard_production_apply(menu, environment="staging") is None
    report = simulate(menu)
    assert report.passed is True
    assert report.plan_hash
    assert guard_production_apply(menu, environment="production") is None
    assert policy_allows_r1_direct("R1", _DIRECT_MATRIX) is True


def test_ac5_production_without_matching_simulation_refuses() -> None:
    menu = _menu()
    other = _menu("Other")
    with pytest.raises(SimulationRequired) as caught:
        guard_production_apply(menu, environment="production")
    assert caught.value.code == "simulation_required"
    with pytest.raises(SimulationRequired):
        apply(menu, mode="T", environment="production")
    assert get_journal() == []
    passed = simulate(menu)
    assert passed.passed is True
    with pytest.raises(SimulationRequired) as mismatched:
        guard_production_apply(other, environment="production")
    assert mismatched.value.code == "simulation_required"
    assert policy_allows_r1_direct("R2", _DIRECT_MATRIX) is False
    assert policy_allows_r1_direct("R3", _DIRECT_MATRIX) is False


def test_ac6_snapshot_equality_ignores_list_order() -> None:
    payload = _snapshot_payload()
    reversed_payload = _reverse(payload)
    assert reversed_payload != payload
    assert equal(payload, reversed_payload) is True
    assert MetaSnapshot.build(payload) == MetaSnapshot.build(reversed_payload)


def test_ac6_renamed_field_does_not_compare_equal() -> None:
    payload = _snapshot_payload()
    renamed = _snapshot_payload()
    renamed["fields"][0] = {**renamed["fields"][0], "name": "x_note_renamed"}
    assert equal(payload, renamed) is False
    assert MetaSnapshot.build(payload) != MetaSnapshot.build(renamed)


def test_ac7_cli_runs_two_ops_on_fake_port_without_an_llm_import() -> None:
    loaded = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert [op["type"] for op in loaded["ops"]] == ["field.create", "view.inherit.create"]
    assert loaded["ops"][0]["params"]["name"] == "x_customer_ref"
    assert loaded["ops"][1]["params"]["xpath"] == "//field[@name='partner_id']"

    script = """
import contextlib, io, json, runpy, sys
path = sys.argv[1]
commands = ["plan", "validate", "simulate", "apply", "rollback"]
rows = []
for command in commands:
    sys.argv = ["app.changeset.cli", command, path]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            runpy.run_module("app.changeset.cli", run_name="__main__")
        except SystemExit as exc:
            code = int(exc.code or 0)
    rows.append(
        {
            "command": command,
            "code": code,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }
    )
roots = ("app.llm_gateway", "google", "anthropic", "openai", "litellm")
leaked = [
    name
    for name in sys.modules
    if any(name == root or name.startswith(root + ".") for root in roots)
]
json.dump({"rows": rows, "leaked": leaked, "commands": commands}, sys.stdout)
"""
    scanned = subprocess.run(
        [sys.executable, "-c", script, str(_FIXTURE)],
        cwd=_API,
        check=False,
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT,
    )
    assert scanned.returncode == 0, scanned.stderr
    report = json.loads(scanned.stdout)
    assert report["commands"] == ["plan", "validate", "simulate", "apply", "rollback"]
    assert report["leaked"] == []
    payloads: dict[str, dict[str, Any]] = {}
    for row in report["rows"]:
        assert row["code"] == 0, row
        assert "Traceback" not in row["stderr"]
        payloads[row["command"]] = json.loads(row["stdout"])
        assert payloads[row["command"]]["port"] == "fake"
        assert payloads[row["command"]]["op_count"] == 2
    applied = payloads["apply"]
    assert applied["status"] == "VERIFIED"
    assert applied["port_calls"] == 2
    assert [row["model"] for row in applied["created"]] == ["ir.model.fields", "ir.ui.view"]
    assert applied["created"][0]["values"]["name"] == "x_customer_ref"


def test_ac7_bad_file_exits_with_one_error_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    completed = _run_cli("apply", str(path))
    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    assert "Traceback" not in completed.stdout
    lines = completed.stderr.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: ")
