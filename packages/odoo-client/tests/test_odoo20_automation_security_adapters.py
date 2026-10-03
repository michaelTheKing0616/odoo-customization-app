"""O20-03: automation_v20 / security_v20 (no live Odoo)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
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
    with pytest.raises(security_v20.AccessCompileError, match="access right with a domain"):
        security_v20.compile_access(
            [],
            [{"name": "company", "model": "x_job", "domain": "[]"}],
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


def test_client_create_access_right_on_20_compiles_to_ir_access() -> None:
    client = _client_for(20)
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args, kwargs))
        if model == "ir.rule" and method == "create":
            raise AssertionError("ir.rule create must not reach execute_kw on 20")
        if model == "ir.model" and method == "search":
            return [11]
        if method == "create":
            return 41
        return []

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    created = client.create_access_right(
        {
            "model": "res.partner",
            "name": "read partner",
            "group_id": 3,
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        }
    )
    creates = [call for call in calls if call[1] == "create"]
    assert creates == [
        (
            "ir.access",
            "create",
            [
                {
                    "name": "read partner",
                    "model": "res.partner",
                    "group": 3,
                    "operation": "read",
                    "domain": None,
                }
            ],
            None,
        )
    ]
    assert "kind" not in creates[0][2][0]
    assert created.id == 41
    assert created.perm_read is True
    assert created.perm_write is False


def test_client_create_access_right_on_19_still_uses_ir_model_access() -> None:
    client = _client_for(19)
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args))
        if model == "ir.model" and method == "search":
            return [11]
        if method == "create":
            return 8
        return []

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    created = client.create_access_right(
        {
            "model": "res.partner",
            "name": "own",
            "group_id": 3,
            "perm_read": True,
            "perm_write": True,
            "perm_create": False,
            "perm_unlink": False,
        }
    )
    assert [call[0] for call in calls if call[1] == "create"] == ["ir.model.access"]
    assert created.id == 8
    assert created.model_id == 11


def test_client_create_record_rule_on_20_raises_before_rpc() -> None:
    client = _client_for(20)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("ir.rule create must not reach execute_kw on 20")

    client.execute_kw = _boom  # type: ignore[method-assign]
    with pytest.raises(security_v20.IrRuleNotSupportedOnOdoo20, match="access right with a domain"):
        client.create_record_rule(
            {
                "name": "own",
                "model": "res.partner",
                "domain_force": "[('id','=',1)]",
                "group_ids": [3],
            }
        )


def test_ensure_default_model_access_on_20_creates_ir_access() -> None:
    client = _client_for(20)
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args))
        if model == "ir.rule" and method == "create":
            raise AssertionError("ir.rule create must not reach execute_kw on 20")
        if model == "ir.model.data" and method == "search_read":
            return [{"res_id": 3, "model": "res.groups"}]
        if model == "ir.model" and method == "search":
            return [11]
        if method == "search":
            return []
        if method == "create":
            return 41
        return []

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    row = client.ensure_default_model_access("x_job")
    creates = [call for call in calls if call[1] == "create"]
    assert creates
    assert {call[0] for call in creates} == {"ir.access"}
    assert all("kind" not in call[2][0] for call in creates)
    assert row.model == "x_job"
    assert row.group_id == 3


def test_security_adapter_future_major_does_not_create_ir_rule() -> None:
    client = _client_for(20)
    client.capabilities = replace(client.capabilities, major=21)

    def execute_kw(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ir.rule create must not reach execute_kw")

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    assert client._security_adapter() is security_v20
    with pytest.raises(security_v20.IrRuleNotSupportedOnOdoo20, match="ir.rule"):
        client.create_record_rule(
            {
                "name": "own",
                "model": "res.partner",
                "domain_force": "[('id','=',1)]",
                "group_ids": [3],
            }
        )


def _four_operation_rows() -> dict[int, dict[str, object]]:
    return {
        op_id: {
            "id": op_id,
            "name": "job acl",
            "model": "x_job",
            "group": 3,
            "operation": operation,
            "active": True,
        }
        for op_id, operation in (
            (1, "read"),
            (2, "write"),
            (3, "create"),
            (4, "unlink"),
        )
    } | {
        5: {
            "id": 5,
            "name": "other",
            "model": "x_job",
            "group": 3,
            "operation": "read",
            "active": True,
        }
    }


def test_delete_access_on_20_removes_all_four_operations() -> None:
    client = _client_for(20)
    rows = _four_operation_rows()
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args, kwargs))
        assert model != "ir.model.access"
        assert model != "ir.rule"
        if model == "ir.access" and method == "read":
            rid = args[0][0]
            return [rows[rid]] if rid in rows else []
        if model == "ir.access" and method == "search":
            domain = args[0]
            name = next(term[2] for term in domain if term[0] == "name")
            model_name = next(term[2] for term in domain if term[0] == "model")
            return [
                rid
                for rid, row in rows.items()
                if row["name"] == name and row["model"] == model_name
            ]
        if model == "ir.access" and method == "unlink":
            for rid in args[0]:
                rows.pop(rid, None)
            return True
        raise AssertionError((model, method, args))

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    client.delete_access(4)
    assert set(rows) == {5}
    unlinks = [call for call in calls if call[1] == "unlink"]
    assert unlinks == [("ir.access", "unlink", [[1, 2, 3, 4]], None)]


def test_update_access_on_20_writes_every_operation_row() -> None:
    client = _client_for(20)
    rows = _four_operation_rows()
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args))
        assert model != "ir.model.access"
        assert model != "ir.rule"
        if model == "ir.access" and method == "read":
            rid = args[0][0]
            return [dict(rows[rid])] if rid in rows else []
        if model == "ir.access" and method == "search":
            domain = args[0]
            name = next(term[2] for term in domain if term[0] == "name")
            model_name = next(term[2] for term in domain if term[0] == "model")
            return [
                rid
                for rid, row in rows.items()
                if row["name"] == name and row["model"] == model_name
            ]
        if model == "ir.access" and method == "write":
            for rid in args[0]:
                rows[rid].update(args[1])
            return True
        if model == "ir.access" and method == "search_read":
            return [dict(row) for row in rows.values()]
        if model == "ir.model" and method == "search":
            return [11]
        raise AssertionError((model, method, args))

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    updated = client.update_access(4, {"name": "renamed"})
    writes = [call for call in calls if call[1] == "write"]
    assert writes[0][0] == "ir.access"
    assert writes[0][2][0] == [1, 2, 3, 4]
    assert writes[0][2][1] == {"name": "renamed"}
    assert "kind" not in writes[0][2][1]
    assert updated.name == "renamed"
    assert all(row["name"] == "renamed" for rid, row in rows.items() if rid != 5)


def test_list_access_on_20_reads_ir_access_and_19_delete_stays_on_ir_model_access() -> None:
    client = _client_for(20)
    calls: list[tuple[object, ...]] = []

    def execute_kw(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls.append((model, method, args))
        assert model != "ir.model.access"
        if model == "ir.access" and method == "search_read":
            assert args[0] == [("model", "=", "x_job")]
            return [
                {
                    "id": 1,
                    "name": "job acl",
                    "model": "x_job",
                    "group": 3,
                    "operation": "read",
                    "active": True,
                }
            ]
        if model == "ir.model" and method == "search":
            return [11]
        raise AssertionError((model, method, args))

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    listed = client.list_access_rights(model="x_job")
    assert listed[0].model == "x_job"
    assert listed[0].perm_read is True
    assert listed[0].model_id == 11
    assert calls[0][0] == "ir.access"

    client19 = _client_for(19)
    calls19: list[tuple[object, ...]] = []

    def execute_kw_19(model: str, method: str, args: list, kwargs: object = None) -> object:
        calls19.append((model, method, args))
        if method == "search":
            return [7]
        if method == "unlink":
            return True
        return []

    client19.execute_kw = execute_kw_19  # type: ignore[method-assign]
    client19.delete_access(7)
    assert ("ir.model.access", "unlink") in [(call[0], call[1]) for call in calls19]
    assert all(call[0] != "ir.access" for call in calls19)


def test_update_access_on_20_does_not_write_perm_columns() -> None:
    client = _client_for(20)

    def execute_kw(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("perm-only update must not call ir.model.access")

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    with pytest.raises(OdooClientError, match="ir.access"):
        client.update_access(4, {"perm_read": False})
