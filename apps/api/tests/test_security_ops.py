"""T8-OP-SEC risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

import pytest

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG, get_op, op_base_risk
from app.changeset.policy import policy_decision, risk_of
from app.changeset.security_ops import (
    GROUP_MUST_NOT_IMPLY_ADMIN,
    PRIVILEGED_ASSIGNMENT,
)

pytestmark = pytest.mark.no_app_db

_ADMIN_REFS = (
    "base.group_system",
    "base.group_erp_manager",
    "admin",
    "system",
    "Administration / Settings",
)


class _Port:
    """In-memory port. A security refusal must not call it."""

    def __init__(self, major: int | None = None) -> None:
        self.major = major
        self.calls: list[tuple] = []

    def create(self, model: str, values: dict) -> int:
        if model == "ir.rule" and self.major == 20:
            raise AssertionError("ir.rule create on major 20")
        self.calls.append(("create", model, dict(values)))
        return len(self.calls)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        if model == "ir.rule" and self.major == 20:
            raise AssertionError("ir.rule write on major 20")
        self.calls.append(("write", model, list(ids), dict(values)))


def _assert_r4(op: dict) -> None:
    assert op_base_risk(op["type"], op["params"]) == "R4"
    assert risk_of(op) == "R4"
    assert risk_of({**op, "risk": "R0"}) == "R4"
    for environment in ("production", "staging"):
        decision = policy_decision(risk_of(op), environment)
        assert decision["deny"] is True
        assert decision["allow"] is False


def test_user_unlink_stays_out_of_the_catalog() -> None:
    assert "user.unlink" not in OP_CATALOG
    assert get_op("user.unlink") is None
    with pytest.raises(KeyError):
        handler_for("user.unlink")
    for op_type, risk in (
        ("group.create", "R3"),
        ("access.create", "R3"),
        ("access.update", "R3"),
        ("rule.create", "R3"),
        ("rule.update", "R3"),
        ("field.groups.set", "R2"),
        ("user.groups.assign", "R3"),
        ("user.create", "R3"),
        ("user.archive", "R3"),
    ):
        assert OP_CATALOG[op_type].risk_base == risk


def test_group_that_implies_admin_is_r4_and_is_not_written() -> None:
    handler = handler_for("group.create")
    port = _Port()
    implied = (
        {"name": "Supervisor", "implied_ids": ["base.group_system"]},
        {"name": "Supervisor", "implies": ["base.group_erp_manager"]},
        {"name": "Supervisor", "implied_ids": [(4, "base.group_system")]},
        {"name": "Supervisor", "implied": {"xmlid": "base.group_system"}},
        {"name": "Supervisor", "admin": True},
        {"name": "Supervisor", "system": True},
        {"name": "Supervisor", "implies_admin": True},
    )
    for params in implied:
        op = {"type": "group.create", "params": params}
        _assert_r4(op)
        assert handler.refuse_reason(params) == GROUP_MUST_NOT_IMPLY_ADMIN
        assert handler.issues(params) == [GROUP_MUST_NOT_IMPLY_ADMIN]
        with pytest.raises(PermissionError, match="must not imply admin"):
            apply_memory({}, op)
        with pytest.raises(DispatchError, match="must not imply admin"):
            dispatch_op(port, op)
    assert port.calls == []


def test_group_create_does_not_imply_admin() -> None:
    params = {
        "name": "Sales Supervisor",
        "implied_ids": ["base.group_user"],
    }
    op = {"type": "group.create", "params": params}
    assert risk_of({**op, "risk": "R0"}) == "R3"
    assert handler_for("group.create").refuse_reason(params) is None
    store: dict = {}
    apply_memory(store, op)
    stored = next(iter(store.values()))
    blob = str(stored)
    for ref in _ADMIN_REFS:
        assert ref not in blob
    assert stored["params"]["implied_ids"] == ["base.group_user"]


def test_groupless_access_create_and_update_are_r4() -> None:
    for op_type in ("access.create", "access.update"):
        params = {"model": "sale.order", "name": "open"}
        op = {"type": op_type, "params": params}
        _assert_r4(op)
        handler = handler_for(op_type)
        assert handler.refuse_reason(params) == "group-less access is forbidden"
        assert "group-less access is forbidden" in handler.issues(params)
        with pytest.raises(PermissionError, match="group-less"):
            apply_memory({}, op)
    grouped = {
        "type": "access.create",
        "params": {"model": "sale.order", "name": "open", "group": "base.group_user"},
        "risk": "R0",
    }
    assert risk_of(grouped) == "R3"


def test_assigning_admin_system_or_service_is_r4() -> None:
    handler = handler_for("user.groups.assign")
    port = _Port()
    admin = {"user": 1, "admin": True}
    assert handler.refuse_reason(admin) == "admin group assignment is prohibited"
    assert handler.issues(admin) == ["admin group assignment is refused"]
    privileged = (
        admin,
        {"user": 1, "system": True},
        {"user": 1, "service": True},
        {"user": 1, "groups": ["base.group_system"]},
        {"user": 1, "groups": ["base.group_erp_manager"]},
        {"user": 1, "group_ids": ["base.group_service"]},
        {"user": 1, "groups": ["base.group_user", "service"]},
        {"user": 1, "group": "Administration / Access Rights"},
    )
    for params in privileged:
        op = {"type": "user.groups.assign", "params": params}
        _assert_r4(op)
        with pytest.raises(PermissionError):
            apply_memory({}, op)
        with pytest.raises(DispatchError):
            dispatch_op(port, op)
    assert port.calls == []
    ordinary = {"user": 1, "groups": ["sales.group_sale_manager"]}
    assert risk_of({"type": "user.groups.assign", "params": ordinary, "risk": "R0"}) == "R3"
    assert handler.refuse_reason(ordinary) is None
    assert handler.issues({"user": 1, "system": True}) == [PRIVILEGED_ASSIGNMENT]
    store: dict = {}
    apply_memory(store, {"type": "user.groups.assign", "params": ordinary})
    assert "base.group_system" not in str(store)


def test_rule_create_and_update_on_odoo_20_compile_to_ir_access() -> None:
    port = _Port(major=20)
    domain = "[('user_id', '=', user.id)]"
    created = dispatch_op(
        port,
        {
            "type": "rule.create",
            "params": {
                "name": "own",
                "model": "res.partner",
                "domain_force": domain,
                "groups": ["base.group_user"],
                "operation": "read",
            },
        },
    )
    updated = dispatch_op(
        port,
        {
            "type": "rule.update",
            "params": {
                "id": 7,
                "name": "own",
                "model": "res.partner",
                "domain_force": domain,
                "groups": ["base.group_user"],
                "operation": "write",
            },
        },
    )
    assert created == 1
    assert updated == 7
    assert port.calls == [
        (
            "create",
            "ir.access",
            {
                "name": "own",
                "model": "res.partner",
                "group": "base.group_user",
                "operation": "read",
                "domain": domain,
            },
        ),
        (
            "write",
            "ir.access",
            [7],
            {
                "name": "own",
                "model": "res.partner",
                "group": "base.group_user",
                "operation": "write",
                "domain": domain,
            },
        ),
    ]
    assert all(call[1] != "ir.rule" for call in port.calls)


def test_rule_create_without_major_stays_on_ir_rule() -> None:
    port = _Port()
    dispatch_op(
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
    assert port.calls[0][1] == "ir.rule"
    assert port.calls[0][2]["domain"] == "[('id','=',1)]"


def test_rule_on_20_refuses_kind_and_a_groupless_access_row() -> None:
    port = _Port(major=20)
    with pytest.raises(DispatchError, match="kind"):
        dispatch_op(
            port,
            {
                "type": "rule.create",
                "params": {
                    "name": "own",
                    "model": "res.partner",
                    "domain_force": "[('id','=',1)]",
                    "groups": ["base.group_user"],
                    "kind": "allow",
                },
            },
        )
    with pytest.raises(DispatchError, match="group-less"):
        dispatch_op(
            port,
            {
                "type": "rule.update",
                "params": {
                    "id": 7,
                    "name": "company",
                    "model": "res.partner",
                    "domain_force": "[('company_id', '=', 1)]",
                    "global": True,
                },
            },
        )
    assert port.calls == []


def test_field_groups_set_stays_r2() -> None:
    op = {
        "type": "field.groups.set",
        "params": {"model": "sale.order", "name": "x_note", "groups": ["base.group_user"]},
        "risk": "R0",
    }
    assert risk_of(op) == "R2"
