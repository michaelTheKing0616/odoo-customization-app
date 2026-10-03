"""Bridge, config-as-code, and Odoo 20 access compiler."""

from __future__ import annotations

import pytest

from app.bridge.contract import ContractError, validate_contract
from app.config_as_code.loader import SECTIONS, SpecError, compile_plan, load_spec
from app.odoo20.access_compiler import AccessCompileError, compile_access
from app.plan_fingerprint import plan_fingerprint


def _contract(**overrides: object) -> dict:
    base = {
        "odoo_connection_id": "odoo-1",
        "third_party_connection_id": "shop-1",
        "direction": "inbound",
        "webhook_signature_required": True,
        "entities": [{"name": "orders", "money": True, "money_policy": "odoo_wins"}],
    }
    base.update(overrides)
    return base


def test_tier_i_accepts_a_complete_contract() -> None:
    contract = validate_contract(_contract())
    assert contract.idempotency_key_field == "idempotency_key"
    assert contract.entities[0].money_policy == "odoo_wins"


def test_two_way_without_conflict_resolution_fails() -> None:
    with pytest.raises(ContractError):
        validate_contract(_contract(direction="two_way"))


def test_money_entity_without_policy_fails() -> None:
    with pytest.raises(ContractError):
        validate_contract(_contract(entities=[{"name": "orders", "money": True}]))


def test_inline_secret_is_rejected() -> None:
    with pytest.raises(ContractError, match="secrets"):
        validate_contract(_contract(api_key="sk_live_secret"))


def test_inline_connection_block_is_rejected() -> None:
    with pytest.raises(ContractError, match="connection_id"):
        validate_contract(_contract(odoo_target={"url": "https://odoo.example", "username": "admin"}))


def test_spec_section_count_and_order() -> None:
    assert len(SECTIONS) == 47
    assert SECTIONS[0] == "modules"
    assert SECTIONS[-1] == "records"


def test_literal_password_is_rejected() -> None:
    text = "version: 1\nproject: demo\nmail_servers:\n  - name: smtp\n    password: hunter2\n"
    with pytest.raises(SpecError, match="secret:"):
        load_spec(text)


def test_secret_pointer_and_x_field_compile() -> None:
    text = """
version: 1
project: demo
mail_servers:
  - name: smtp
    password: secret:MAIL_PASSWORD
custom_fields:
  - model: res.partner
    name: x_rc_number
    ttype: char
"""
    spec = load_spec(text)
    plan = compile_plan(spec)
    assert plan[0]["section"] == "mail_servers"
    assert plan[-1]["section"] == "custom_fields"
    assert "res_id" not in plan[-1]
    again = compile_plan(load_spec(text))
    assert plan_fingerprint(plan) == plan_fingerprint(again)


def test_studio_field_prefix_is_rejected() -> None:
    text = "version: 1\nproject: demo\ncustom_fields:\n  - model: res.partner\n    name: x_studio_note\n"
    with pytest.raises(SpecError):
        load_spec(text)


def test_custom_field_requires_x_prefix() -> None:
    without_prefix = (
        "version: 1\nproject: demo\ncustom_fields:\n  - model: res.partner\n    name: note\n"
    )
    with pytest.raises(SpecError, match="must start with x_"):
        load_spec(without_prefix)

    studio = (
        "version: 1\nproject: demo\ncustom_fields:\n  - model: res.partner\n    name: x_studio_note\n"
    )
    with pytest.raises(SpecError, match="x_studio_"):
        load_spec(studio)

    valid = (
        "version: 1\nproject: demo\ncustom_fields:\n  - model: res.partner\n    name: x_note\n"
    )
    spec = load_spec(valid)
    assert spec.custom_fields[0].name == "x_note"


def test_unknown_section_is_rejected() -> None:
    with pytest.raises(SpecError, match="unknown"):
        load_spec("version: 1\nproject: demo\nnot_a_section: []\n")


def test_example_spec_is_valid() -> None:
    text = """
version: 1
project: demo
settings:
  - key: mail.smtp_password
    values:
      value: secret:MAIL_SMTP_PASSWORD
custom_fields:
  - model: res.partner
    name: x_note
    ttype: text
"""
    spec = load_spec(text)
    assert spec.version == 1
    assert spec.project == "demo"
    plan = compile_plan(spec)
    assert plan
    assert all(entry["type"] for entry in plan)


def test_schema_errors() -> None:
    with pytest.raises(SpecError):
        load_spec("project: demo\n")

    with pytest.raises(SpecError, match="mapping"):
        load_spec("- not a mapping\n")

    with pytest.raises(SpecError, match="unknown"):
        load_spec("version: 1\nproject: demo\nbogus_top_level: []\n")


def test_duplicate_keys_rejected() -> None:
    text = """
version: 1
project: demo
settings:
  - key: sale.auto_done
    values:
      value: "True"
  - key: sale.auto_done
    values:
      value: "False"
"""
    with pytest.raises(SpecError, match="duplicate key"):
        load_spec(text)


def test_key_field_reference_and_placeholders() -> None:
    ok_refs = """
version: 1
project: demo
settings:
  - key: base.main_company
    values:
      value: ref:base.main_company
records:
  - model: res.partner
    values:
      name: name:Acme Ltd
      parent_id: find:res.partner|name=Acme Ltd
      comment: ?key:does.not.exist
"""
    spec = load_spec(ok_refs)
    assert spec.settings[0]["values"]["value"] == "ref:base.main_company"

    with pytest.raises(SpecError, match="secret:"):
        load_spec(
            "version: 1\nproject: demo\nmail_servers:\n"
            "  - name: smtp\n    password: plain-text-secret\n"
        )

    missing_key = """
version: 1
project: demo
settings:
  - key: only.one
    values:
      value: key:missing.setting
"""
    with pytest.raises(SpecError, match="unknown key"):
        load_spec(missing_key)


def test_odoo_20_access_compiles_to_ir_access() -> None:
    ops = compile_access(
        20,
        [{"name": "read partner", "model": "res.partner", "group": "sales.group_sale_salesman", "operation": "read"}],
    )
    assert ops == [
        {
            "model": "ir.access",
            "values": {
                "name": "read partner",
                "model": "res.partner",
                "group": "sales.group_sale_salesman",
                "operation": "read",
                "domain": None,
            },
        }
    ]


def test_odoo_20_group_record_rule_is_refused() -> None:
    with pytest.raises(AccessCompileError, match="ir.rule"):
        compile_access(20, [], [{"name": "own", "group": "base.group_user", "domain": "[]"}])


def test_odoo_20_global_record_rule_is_not_dropped() -> None:
    """A record rule with no group still raises. It is not an ir.access grant."""
    with pytest.raises(AccessCompileError, match="access right with a domain"):
        compile_access(
            20,
            [
                {
                    "name": "read job",
                    "model": "x_job",
                    "group": "base.group_user",
                    "operation": "read",
                    "domain": "[('id','=',1)]",
                }
            ],
            [
                {
                    "name": "company",
                    "model": "x_job",
                    "domain": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
                }
            ],
        )


def test_odoo_20_refuses_computed_kind() -> None:
    with pytest.raises(AccessCompileError, match="kind"):
        compile_access(20, [{"name": "a", "model": "res.partner", "kind": "allow"}])


def test_odoo_19_domain_right_becomes_access_plus_rule() -> None:
    ops = compile_access(
        19,
        [{"name": "own", "model": "res.partner", "group": "base.group_user", "domain": "[('id','=',1)]"}],
    )
    assert [op["model"] for op in ops] == ["ir.model.access", "ir.rule"]
