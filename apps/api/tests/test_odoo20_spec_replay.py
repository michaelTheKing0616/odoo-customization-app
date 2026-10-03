"""O20-16: a 19 config spec replayed on 20 applies or fails closed. Fake port only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.changeset.executor import reset_journal
from app.config_as_code.apply import FakeConfigPort
from app.config_as_code.loader import compile_plan, load_spec
from app.odoo20.access_compiler import compile_access
from app.odoo20.spec_replay import (
    KNOWN_REFUSALS,
    MigrationNote,
    first_migration_note,
    replay_19_on_20,
    verify_row_ids,
)
from odoo_client.compat.version_table import difference

_RUNBOOK = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runbooks"
    / "odoo20-spec-that-will-not-translate.md"
)

_CLEAN_19 = """
version: 1
project: replay_ok
settings:
  - key: sale.auto_done
    xmlid: replay_ok.sale_auto_done
    values:
      value: "True"
access_rights:
  - name: own partner
    model: res.partner
    group: base.group_user
    operation: read
    domain: "[('id','=',1)]"
    xmlid: replay_ok.access_own_partner
"""

_SAFE_THEN_COMPANY_TYPE = """
version: 1
project: replay_half
settings:
  - key: sale.auto_done
    xmlid: replay_half.sale_auto_done
    values:
      value: "True"
records:
  - model: res.partner
    xmlid: replay_half.acme
    values:
      name: Acme
      company_type: company
"""

_GROUP_RULE = """
version: 1
project: replay_rule
settings:
  - key: sale.auto_done
    xmlid: replay_rule.sale_auto_done
    values:
      value: "True"
record_rules:
  - name: own partners
    model: res.partner
    group: base.group_user
    domain_force: "[('user_id','=',user.id)]"
    xmlid: replay_rule.own_partners
"""

_PERCENTAGE_PRICELIST = """
version: 1
project: replay_price
settings:
  - key: sale.auto_done
    xmlid: replay_price.sale_auto_done
    values:
      value: "True"
pricelists:
  - name: Trade
    xmlid: replay_price.trade
    values:
      name: Trade
      compute_price: percentage
"""

_COMPANY_REGISTRY = """
version: 1
project: replay_reg
records:
  - model: res.company
    xmlid: replay_reg.main
    values:
      name: Main
      company_registry: RC123
"""

_VERIFY_TAX = """
version: 1
project: replay_verify
taxes:
  - name: VAT
    xmlid: replay_verify.vat
    values:
      name: VAT
      price_include: true
"""


def _creates(port: FakeConfigPort, model: str) -> list[tuple]:
    return [call for call in port.calls if call[0] == "create" and call[1] == model]


def test_clean_19_spec_applies_through_access_compiler() -> None:
    reset_journal()
    port = FakeConfigPort()
    result = replay_19_on_20(_CLEAN_19, port)
    assert result == 2
    assert port.major == 20
    assert port.call_count > 0
    assert _creates(port, "ir.access")
    assert not _creates(port, "ir.model.access")
    assert not _creates(port, "ir.rule")
    rights = [
        {
            "name": "own partner",
            "model": "res.partner",
            "group": "base.group_user",
            "operation": "read",
            "domain": "[('id','=',1)]",
        }
    ]
    compiled = compile_access(20, rights, None)
    assert [op["model"] for op in compiled] == ["ir.access"]
    assert difference("access", 20) == "ir.access"


def test_refused_company_type_writes_nothing() -> None:
    reset_journal()
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="company_type removed") as caught:
        replay_19_on_20(_SAFE_THEN_COMPANY_TYPE, port)
    assert caught.value.name == "company_type_removed"
    assert port.call_count == 0
    assert port.rows == {}


def test_refused_group_record_rule_writes_nothing() -> None:
    reset_journal()
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="ir.access with a domain") as caught:
        replay_19_on_20(_GROUP_RULE, port)
    assert caught.value.name == "group_record_rule"
    assert port.call_count == 0


def test_refused_percentage_pricelist_writes_nothing() -> None:
    reset_journal()
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="percentage pricelist is discount") as caught:
        replay_19_on_20(_PERCENTAGE_PRICELIST, port)
    assert caught.value.name == "percentage_pricelist_is_discount"
    assert port.call_count == 0


def test_refused_company_registry_writes_nothing() -> None:
    reset_journal()
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="additional identifiers") as caught:
        replay_19_on_20(_COMPANY_REGISTRY, port)
    assert caught.value.name == "company_registry_is_additional_identifiers"
    assert port.call_count == 0


def test_verify_row_is_named_not_translated_not_guessed() -> None:
    reset_journal()
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="tax_included is not translated") as caught:
        replay_19_on_20(_VERIFY_TAX, port)
    assert caught.value.name == "not_translated"
    assert "override" not in str(caught.value).lower()
    assert port.call_count == 0
    assert "V06" in verify_row_ids(major=19)
    assert set(verify_row_ids(major=19)) == {"V06", "V24", "V26", "V28", "V29", "V30"}


def test_first_refused_op_leaves_zero_writes() -> None:
    reset_journal()
    plan = compile_plan(load_spec(_SAFE_THEN_COMPANY_TYPE))
    note = first_migration_note(plan)
    assert note is not None
    assert note.name == "company_type_removed"
    port = FakeConfigPort()
    with pytest.raises(MigrationNote, match="company_type removed"):
        replay_19_on_20(_SAFE_THEN_COMPANY_TYPE, port)
    assert port.call_count == 0


def test_runbook_lists_known_refusals_and_verify_rows() -> None:
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert "Odoo 20 spec that will not translate" in text
    for _name, note in KNOWN_REFUSALS:
        assert note in text
    for vid in verify_row_ids(major=19):
        assert vid in text
    assert "not translated" in text.lower()
    assert "do not guess" in text.lower() or "not guessed" in text.lower()
