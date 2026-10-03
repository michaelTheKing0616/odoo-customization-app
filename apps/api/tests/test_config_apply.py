"""Config-as-code apply through the change-set executor. Fake port only."""

from __future__ import annotations

import pytest

from app.changeset.executor import reset_journal
from app.changeset.ops import OP_CATALOG
from app.config_as_code.apply import ApplyError, FakeConfigPort, MemoryDb, apply_plan
from app.config_as_code.loader import SECTIONS, SECTION_OP, compile_plan, load_spec

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
