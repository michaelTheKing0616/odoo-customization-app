"""Config-as-code apply through the change-set executor. Fake port only."""

from __future__ import annotations

import pytest

from app.changeset.executor import reset_journal
from app.changeset.ops import OP_CATALOG
from app.changeset.plan_card import render_plan_card
from app.config_as_code.apply import (
    ApplyError,
    FakeConfigPort,
    MemoryDb,
    apply_plan,
    plan_to_changeset,
    port_fingerprint,
)
from app.config_as_code.loader import SECTIONS, SECTION_OP, compile_plan, load_spec
from app.odoo20.access_compiler import compile_access

_SPEC = """
version: 1
project: demo
custom_fields:
  - model: res.partner
    name: x_rc_number
    ttype: char
"""

_ADOPT_EXAMPLE = """
version: 1
project: adopt_demo
description: Adopt existing records by xmlid
target: staging
settings:
  - key: sale.auto_done
    xmlid: adopt_demo.sale_auto_done
    values:
      value: "True"
custom_fields:
  - model: res.partner
    name: x_rc_number
    ttype: char
    xmlid: adopt_demo.partner_x_rc_number
access_rights:
  - name: partner rc read
    model: res.partner
    group: base.group_user
    xmlid: adopt_demo.access_partner_rc
records:
  - model: res.partner.category
    xmlid: adopt_demo.tag_vip
    values:
      name: VIP
"""


def test_second_apply_writes_nothing() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SPEC))
    db = MemoryDb()
    assert apply_plan(db, plan) == 1
    reset_journal()
    assert apply_plan(db, plan) == 0
    assert db.writes == 1


def test_plan_apply_idempotent() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SPEC))
    port = FakeConfigPort()
    assert apply_plan(port, plan) == 1
    assert port.call_count > 0
    reset_journal()
    port.calls.clear()
    assert apply_plan(port, plan) == 0
    assert port.call_count == 0


def test_adopt_example_compiles() -> None:
    assert set(SECTION_OP) == set(SECTIONS)
    assert all(op in OP_CATALOG for op in SECTION_OP.values())
    plan = compile_plan(load_spec(_ADOPT_EXAMPLE))
    assert [entry["type"] for entry in plan] == [
        "setting.set",
        "field.create",
        "access.create",
        "config_record.upsert",
    ]
    assert all(entry["type"] in OP_CATALOG for entry in plan)
    assert {entry["xmlid"] for entry in plan} == {
        "adopt_demo.sale_auto_done",
        "adopt_demo.partner_x_rc_number",
        "adopt_demo.access_partner_rc",
        "adopt_demo.tag_vip",
    }


def test_fingerprint_drift_detected() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SPEC))
    port = FakeConfigPort()
    expected = port_fingerprint(port)
    assert apply_plan(port, plan, expected_fingerprint=expected) == 1
    assert port.call_count > 0

    reset_journal()
    drifted = FakeConfigPort()
    expected_empty = port_fingerprint(drifted)
    drifted.rows["poison"] = {"name": "someone-else-wrote"}
    with pytest.raises(ApplyError, match="plan_drift") as exc:
        apply_plan(drifted, plan, expected_fingerprint=expected_empty)
    assert exc.value.name == "plan_drift"
    assert drifted.call_count == 0


def test_errors_block_apply() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SPEC))
    plan.append(
        {
            "section": "custom_fields",
            "index": 1,
            "type": "setting.set",
            "xmlid": "demo.bad_type",
            "body": {"model": "res.partner", "name": "x_other", "ttype": "char"},
        }
    )
    port = FakeConfigPort()
    with pytest.raises(ApplyError, match="type_mismatch"):
        apply_plan(port, plan)
    assert port.call_count == 0
    with pytest.raises(ApplyError, match="write_mode_production_refused"):
        apply_plan(port, plan[:1], write_mode="production")
    assert port.call_count == 0


_SETTING_SPEC = """
version: 1
project: demo
settings:
  - key: group_auto_done_setting
    xmlid: demo.sale_auto_done
    values:
      value: "True"
"""


def test_destructive_changes_need_approval() -> None:
    reset_journal()
    plan = [
        {
            "type": "data.delete",
            "xmlid": "demo.purge_partner",
            "body": {"model": "res.partner", "ids": [1]},
        }
    ]
    port = FakeConfigPort()
    with pytest.raises(ApplyError, match="destructive_approval_required") as exc:
        apply_plan(port, plan)
    assert exc.value.name == "destructive_approval_required"
    assert port.call_count == 0

    result = apply_plan(port, plan, approve_destructive=True)
    assert port.call_count > 0
    assert result.status == "VERIFIED"
    assert result.plan_card["plan_hash"]
    assert result.plan_card["risk"]
    assert result.plan_card["environment"] == "sandbox"
    rebuilt = render_plan_card(
        plan_to_changeset(plan),
        goal="apply config",
        assumptions=("fake_port_only",),
        environment="sandbox",
    )
    assert result.plan_card["plan_hash"] == rebuilt["plan_hash"]
    assert set(result.plan_card) >= {"plan_hash", "risk", "environment"}

    class _NotAFakePort:
        def __init__(self) -> None:
            self.calls = 0
            self.rows: dict[str, dict] = {}
            self.applied_params: dict[str, dict] = {}

        def create(self, model: str, values: dict) -> int:
            self.calls += 1
            return 1

    outsider = _NotAFakePort()
    with pytest.raises(ApplyError, match="destructive_fake_port_only"):
        apply_plan(outsider, plan, approve_destructive=True)
    assert outsider.calls == 0


def test_production_requires_approval_for_everything() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SETTING_SPEC))
    port = FakeConfigPort()
    with pytest.raises(ApplyError, match="production_acknowledgement_required") as exc:
        apply_plan(port, plan, environment="production")
    assert exc.value.name == "production_acknowledgement_required"
    assert port.call_count == 0

    with pytest.raises(ApplyError, match="write_mode_production_refused") as exc:
        apply_plan(
            port,
            plan,
            write_mode="production",
            environment="production",
            acknowledge_production=True,
            approve_destructive=True,
        )
    assert exc.value.name == "write_mode_production_refused"
    assert port.call_count == 0

    result = apply_plan(port, plan, environment="production", acknowledge_production=True)
    assert result == 1
    assert result.status == "VERIFIED"
    assert result.plan_card["plan_hash"]
    assert result.plan_card["risk"]
    assert result.plan_card["environment"] == "production"


def test_read_back_verification_flags_ignored_writes() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SETTING_SPEC))
    port = FakeConfigPort(ignore_writes=True)
    result = apply_plan(port, plan)
    assert port.call_count > 0
    assert result.status != "VERIFIED"
    assert result.ignored
    assert all(entry["status"] == "ignored" for entry in result.ignored)


def test_version_aware_compilation() -> None:
    spec = [
        {
            "name": "own partner",
            "model": "res.partner",
            "group": "base.group_user",
            "operation": "read",
            "domain": "[('id','=',1)]",
        }
    ]
    ops_19 = compile_access(19, spec)
    ops_20 = compile_access(20, spec)
    assert [op["model"] for op in ops_19] == ["ir.model.access", "ir.rule"]
    assert [op["model"] for op in ops_20] == ["ir.access"]
    assert ops_19 != ops_20
    assert "perm_read" in ops_19[0]["values"]
    assert ops_20[0]["values"]["operation"] == "read"
    assert ops_20[0]["values"]["domain"] == "[('id','=',1)]"
    assert "kind" not in ops_20[0]["values"]
