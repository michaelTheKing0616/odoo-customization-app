"""O20-03: automation_v20 / security_v20 (no live Odoo)."""

from __future__ import annotations

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.automation import RelatedWriteAction, UpdateFieldAction
from odoo_client.compat.adapters import (
    automation_v16,
    automation_v17,
    automation_v18,
    automation_v19,
    automation_v20,
    security_v20,
    views_v19,
    views_v20,
)
from odoo_client.compat.registry import for_major


def _client_for(major: int) -> OdooClient:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    client.capabilities = for_major(major)
    return client


def test_security_v20_access_model_is_ir_access() -> None:
    assert security_v20.access_model() == "ir.access"


def test_security_v20_create_record_rule_raises_named_error() -> None:
    with pytest.raises(security_v20.IrRuleNotSupportedOnOdoo20, match="ir.rule"):
        security_v20.create_record_rule(
            {"name": "own", "model": "res.partner", "group": "base.group_user"}
        )


def test_security_v20_compile_refuses_kind_and_group_rule() -> None:
    with pytest.raises(security_v20.AccessCompileError, match="kind"):
        security_v20.compile_access(
            [{"name": "a", "model": "res.partner", "kind": "allow"}]
        )
    with pytest.raises(security_v20.AccessCompileError, match="ir.rule"):
        security_v20.compile_access(
            [],
            [{"name": "own", "group": "base.group_user", "domain": "[]"}],
        )


def test_security_v20_compile_emits_ir_access_fields() -> None:
    ops = security_v20.compile_access(
        [
            {
                "name": "read partner",
                "model": "res.partner",
                "group": "sales.group_sale_salesman",
                "operation": "read",
            }
        ]
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
    assert "kind" not in ops[0]["values"]


def test_automation_v20_cron_does_not_emit_numbercall() -> None:
    vals = automation_v20.encode_cron_vals(
        name="nightly",
        model_id=7,
        code="env['res.partner'].search([]).mapped('id')",
    )
    assert "numbercall" not in vals
    assert vals["state"] == "code"
    assert vals["model_id"] == 7
    assert vals["interval_type"] == "days"


def test_automation_v20_keeps_separate_server_action() -> None:
    server_vals = automation_v20.encode_update_field_server_vals(
        name="Rule",
        model_id=7,
        action=UpdateFieldAction(field_name="x_note", value="hi"),
    )
    auto = automation_v20.build_automation_record_vals(
        name="Rule",
        model_id=7,
        trigger="on_create",
        active=True,
        server_vals=server_vals,
    )
    assert auto["action_server_ids"][0][0] == 0
    assert auto["action_server_ids"][0][2]["state"] == "object_write"
    assert auto["action_server_ids"][0][2]["update_path"] == "x_note"


def test_automation_v20_related_write_still_uses_update_path() -> None:
    vals = automation_v20.encode_related_write_server_vals(
        name="Rule",
        model_id=7,
        action=RelatedWriteAction(
            relation_field="x_vehicle_id",
            field_name="x_status",
            value="rented",
        ),
    )
    assert vals["update_path"] == "x_vehicle_id.x_status"


def test_major_20_selects_v20_adapters_only() -> None:
    c20 = _client_for(20)
    assert c20._automation_adapter() is automation_v20
    assert c20._security_adapter() is security_v20
    assert c20._views_adapter() is views_v20
    for major, expected in (
        (16, automation_v16),
        (17, automation_v17),
        (18, automation_v18),
        (19, automation_v19),
    ):
        client = _client_for(major)
        assert client._automation_adapter() is expected
        assert client._security_adapter() is None
        assert client._automation_adapter() is not automation_v20
        assert client._views_adapter() is not views_v20
    assert _client_for(19)._views_adapter() is views_v19


def test_client_create_record_rule_on_20_raises_before_rpc() -> None:
    client = _client_for(20)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("ir.rule create must not reach execute_kw on 20")

    client.execute_kw = _boom  # type: ignore[method-assign]
    with pytest.raises(security_v20.IrRuleNotSupportedOnOdoo20, match="ir.rule"):
        client.create_record_rule(
            {
                "name": "own",
                "model": "res.partner",
                "domain_force": "[('id','=',1)]",
            }
        )
