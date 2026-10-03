"""O20-04: major 20 access writes go through compile_access and never create ir.rule."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.changeset.dispatch import DispatchError, dispatch_op
from app.routers.access import CreateAccessBody, CreateRuleBody, create_right, create_rule
from app.spec_apply_ui import UiApplyResult, _apply_access_rules, _apply_draft_record_rules
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.compat.adapters import security_v20
from odoo_client.compat.registry import for_major


class RecordingPort:
    def __init__(self, major: int | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.major = major

    def create(self, model: str, values: dict[str, Any]) -> int:
        if model == "ir.rule":
            raise AssertionError("ir.rule create on major 20")
        self.calls.append(("create", model, dict(values)))
        return len(self.calls)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        self.calls.append(("write", model, list(ids), dict(values)))


class RecordingClient:
    """Duck client. create_record_rule records an ir.rule create so a missed branch fails."""

    def __init__(self, major: int) -> None:
        self.major = major
        self.capabilities = SimpleNamespace(major=major)
        self.calls: list[tuple[Any, ...]] = []
        self._seq = 0

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: Any = None) -> Any:
        self.calls.append((model, method, args, kwargs))
        if self.major >= 20 and model == "ir.rule" and method == "create":
            raise AssertionError("ir.rule create on major 20")
        if method == "create":
            self._seq += 1
            return self._seq
        if method == "search":
            return []
        return []

    def model_exists(self, model: str) -> bool:
        return True

    def field_exists(self, model: str, name: str) -> bool:
        return True

    def create_field(self, request: Any) -> Any:
        self.calls.append(("ir.model.fields", "create", [request]))
        return 1

    def list_record_rules(self, model: str | None = None, limit: int = 50) -> list[Any]:
        self.calls.append(("ir.rule", "search_read", [model]))
        return []

    def create_record_rule(self, request: Any) -> Any:
        return self.execute_kw("ir.rule", "create", [request])

    def create_access_right(self, request: Any) -> Any:
        return self.execute_kw("ir.model.access", "create", [request])


def _creates(client: RecordingClient, model: str | None = None) -> list[tuple[Any, ...]]:
    out = [call for call in client.calls if call[1] == "create"]
    if model is None:
        return out
    return [call for call in out if call[0] == model]


def _client_for(major: int) -> OdooClient:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    client.capabilities = for_major(major)
    return client


def test_dispatch_access_create_on_20_writes_ir_access() -> None:
    port = RecordingPort(major=20)
    created = dispatch_op(
        port,
        {
            "type": "access.create",
            "params": {
                "name": "read partner",
                "model": "res.partner",
                "group": "base.group_user",
                "operation": "read",
                "domain": "[('id','=',1)]",
            },
        },
    )
    assert created == 1
    assert port.calls == [
        (
            "create",
            "ir.access",
            {
                "name": "read partner",
                "model": "res.partner",
                "group": "base.group_user",
                "operation": "read",
                "domain": "[('id','=',1)]",
            },
        )
    ]
    assert "kind" not in port.calls[0][2]


def test_dispatch_access_create_on_20_refuses_kind() -> None:
    port = RecordingPort(major=20)
    with pytest.raises(DispatchError, match="kind"):
        dispatch_op(
            port,
            {
                "type": "access.create",
                "params": {
                    "name": "a",
                    "model": "res.partner",
                    "group": "base.group_user",
                    "kind": "allow",
                },
            },
        )
    assert port.calls == []


def test_dispatch_access_create_without_major_stays_on_ir_model_access() -> None:
    port = RecordingPort()
    dispatch_op(
        port,
        {
            "type": "access.create",
            "params": {"name": "open", "model": "res.partner", "group": "base.group_user"},
        },
    )
    assert port.calls[0][1] == "ir.model.access"


def test_rule_create_on_20_compiles_to_ir_access() -> None:
    """rule.create reuses compile_access. This is not a new major-20 branch."""
    port = RecordingPort(major=20)
    created = dispatch_op(
        port,
        {
            "type": "rule.create",
            "params": {
                "name": "own",
                "model": "res.partner",
                "domain_force": "[('id','=',1)]",
                "groups": ["base.group_user"],
            },
        },
    )
    assert created == 1
    assert port.calls == [
        (
            "create",
            "ir.access",
            {
                "name": "own",
                "model": "res.partner",
                "group": "base.group_user",
                "operation": "read",
                "domain": "[('id','=',1)]",
            },
        )
    ]


def test_spec_apply_access_on_20_writes_ir_access_with_domain() -> None:
    client = RecordingClient(20)
    result = UiApplyResult()
    _apply_access_rules(
        client,
        {
            "access_rules": [
                {
                    "name": "own",
                    "model": "x_job",
                    "group": "base.group_user",
                    "domain": "[('id','=',1)]",
                    "perm_read": True,
                    "perm_write": False,
                    "perm_create": False,
                    "perm_unlink": False,
                }
            ]
        },
        result,
    )
    creates = _creates(client)
    assert result.access_rights_created == 1
    assert [call[0] for call in creates] == ["ir.access"]
    values = creates[0][2][0]
    assert values["operation"] == "read"
    assert values["domain"] == "[('id','=',1)]"
    assert "kind" not in values


def test_spec_apply_group_record_rule_on_20_warns_and_keeps_applied_work() -> None:
    client = RecordingClient(20)
    result = UiApplyResult(models_created=["x_job"], fields_created=2)
    _apply_draft_record_rules(
        client,
        {
            "record_rules": [
                {
                    "name": "own",
                    "model": "x_job",
                    "domain_force": "[('id','=',1)]",
                    "group": "base.group_user",
                },
                {
                    "name": "company",
                    "model": "x_job",
                    "domain_force": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
                },
            ]
        },
        result,
    )
    assert result.models_created == ["x_job"]
    assert result.fields_created == 2
    assert result.record_rules_created == 0
    assert _creates(client) == []
    assert len(result.warnings) == 2
    assert all("access right with a domain" in warning for warning in result.warnings)
    assert not any(call[0] == "ir.access" for call in client.calls)
    _apply_access_rules(
        client,
        {
            "access_rules": [
                {
                    "name": "read job",
                    "model": "x_job",
                    "group": "sales.group_sale_salesman",
                    "perm_read": True,
                    "perm_write": False,
                    "perm_create": False,
                    "perm_unlink": False,
                }
            ]
        },
        result,
    )
    creates = _creates(client)
    assert [call[0] for call in creates] == ["ir.access"]
    assert creates[0][2][0]["name"] == "read job"
    assert creates[0][2][0]["group"] == "sales.group_sale_salesman"
    assert result.models_created == ["x_job"]
    assert result.fields_created == 2


def test_spec_apply_groupless_record_rule_on_20_does_not_create_ir_rule() -> None:
    client = RecordingClient(20)
    result = UiApplyResult()
    _apply_draft_record_rules(
        client,
        {
            "record_rules": [
                {
                    "name": "company",
                    "model": "x_job",
                    "domain": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
                }
            ]
        },
        result,
    )
    assert _creates(client) == []
    assert result.record_rules_created == 0
    assert any("ir.rule" in warning for warning in result.warnings)


def test_spec_apply_domain_right_on_19_still_calls_record_rule() -> None:
    client = RecordingClient(19)
    result = UiApplyResult()
    _apply_access_rules(
        client,
        {
            "access_rules": [
                {
                    "name": "own",
                    "model": "x_job",
                    "domain_force": "[('id','=',1)]",
                    "perm_read": True,
                }
            ]
        },
        result,
    )
    assert result.record_rules_created == 1
    assert _creates(client, "ir.rule")


def test_multi_company_live_on_20_does_not_claim_isolation() -> None:
    from app.multi_company_pack import apply_multi_company_live

    client = RecordingClient(20)
    out = apply_multi_company_live(client, ["x_job"])
    assert _creates(client, "ir.rule") == []
    assert _creates(client, "ir.access") == []
    assert out["rules_created"] == 0
    assert out["ok"] is False
    assert any(
        "company field may exist but row isolation was not applied" in warning
        and "Odoo 20 has no ir.rule" in warning
        for warning in out["warnings"]
    )


def test_library_template_on_20_does_not_claim_isolation() -> None:
    from app.app_templates import ScaffoldResult, _maybe_multi_company_rules

    client = RecordingClient(20)
    result = ScaffoldResult(template_id="library")
    _maybe_multi_company_rules(client, ["x_lib_book"], result)
    assert _creates(client, "ir.rule") == []
    assert _creates(client, "ir.access") == []
    assert any(
        "company field may exist but row isolation was not applied" in warning
        and "Odoo 20 has no ir.rule" in warning
        for warning in result.warnings
    )


def test_access_rule_v20_skips_only_the_existing_operation() -> None:
    class _Partial(RecordingClient):
        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: Any = None) -> Any:
            self.calls.append((model, method, args, kwargs))
            if method == "search":
                domain = args[0] if args else []
                operation = next(
                    (
                        term[2]
                        for term in domain
                        if isinstance(term, (list, tuple))
                        and len(term) >= 3
                        and term[0] == "operation"
                    ),
                    None,
                )
                if operation is None:
                    return [1]
                return [1] if operation == "read" else []
            if method == "create":
                self._seq += 1
                return self._seq
            return []

    client = _Partial(20)
    result = UiApplyResult()
    _apply_access_rules(
        client,
        {
            "access_rules": [
                {
                    "name": "job acl",
                    "model": "x_job",
                    "group": "base.group_user",
                    "perm_read": True,
                    "perm_write": True,
                    "perm_create": True,
                    "perm_unlink": True,
                }
            ]
        },
        result,
    )
    created_ops = [call[2][0]["operation"] for call in _creates(client, "ir.access")]
    assert created_ops == ["write", "create", "unlink"]
    assert result.access_rights_created == 1


def test_router_create_right_on_20_never_creates_ir_rule() -> None:
    client = _client_for(20)
    calls: list[tuple[Any, ...]] = []

    def execute_kw(model: str, method: str, args: list[Any], kwargs: Any = None) -> Any:
        calls.append((model, method, args))
        if model == "ir.rule" and method == "create":
            raise AssertionError("ir.rule create on major 20")
        if model == "ir.model" and method == "search":
            return [11]
        if method == "create":
            return 41
        return []

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    with patch("app.routers.access._client", return_value=client):
        out = create_right(
            "cid",
            CreateAccessBody(
                model="res.partner",
                name="read partner",
                group_id=3,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
            db=MagicMock(),
        )
    creates = [call for call in calls if call[1] == "create"]
    assert creates and all(call[0] == "ir.access" for call in creates)
    assert "kind" not in creates[0][2][0]
    assert out.model == "res.partner"
    assert out.id == 41


def test_router_create_rule_on_20_fails_with_rewrite_message() -> None:
    client = _client_for(20)

    def execute_kw(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("ir.rule create must not reach execute_kw on 20")

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    with patch("app.routers.access._client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            create_rule(
                "cid",
                CreateRuleBody(
                    model="res.partner",
                    name="own",
                    domain_force="[('id','=',1)]",
                    group_ids=[3],
                ),
                db=MagicMock(),
            )
    assert exc.value.status_code == 400
    assert "access right with a domain" in str(exc.value.detail)
    assert issubclass(security_v20.IrRuleNotSupportedOnOdoo20, Exception)
