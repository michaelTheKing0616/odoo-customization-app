"""GATE-L4-01: tenant allow-list content. L4 stays off as a runtime level."""

from __future__ import annotations

import pytest

from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.protected_registry import protection_level
from app.worker_bot.l4_policy import (
    L4_BASE_RISK,
    L4_NOT_ON_ALLOW_LIST,
    L4_OUTBOUND,
    L4_PROTECTED,
    L4_R2_DDL,
    AllowListRegistry,
    l4_gate_01_refusal,
    l4_may_apply,
    record_allow_list_change,
)

pytestmark = pytest.mark.no_app_db

_TENANT = "tenant-a"
_PLAN_HASH = "a" * 16
_READY = {
    "rows": 1,
    "mode_t": True,
    "staging_verified": True,
    "plan_mode": "T",
    "plan_hash": _PLAN_HASH,
    "staging_applies": (
        {"plan_hash": _PLAN_HASH, "verified": True, "environment": "staging"},
    ),
}


def _may(op_type: str, *, risk: str, params: dict | None = None, allow_list: frozenset[str] | None = None) -> bool:
    return l4_may_apply(
        risk=risk,
        op_type=op_type,
        params=params,
        allow_list=allow_list,
        **_READY,
    )


def test_op_outside_the_tenant_allow_list_is_refused() -> None:
    registry = AllowListRegistry()
    recorded = record_allow_list_change(
        registry,
        role="admin",
        tenant=_TENANT,
        op_type="mail_template.create",
        admin_id="admin-1",
    )
    assert recorded.recorded is True
    listed = registry.ops(_TENANT)
    assert listed == frozenset({"mail_template.create"})
    assert l4_gate_01_refusal(op_type="view.archive", allow_list=listed) == L4_NOT_ON_ALLOW_LIST
    assert _may("view.archive", risk="R1", allow_list=listed) is False
    assert l4_gate_01_refusal(op_type="mail_template.create", allow_list=listed) is None
    assert _may("mail_template.create", risk="R1", allow_list=listed) is True
    assert registry.ops(_TENANT) == listed


@pytest.mark.parametrize("op_type", ["field.create", "model.create", "model.scaffold"])
def test_r2_ddl_op_is_refused_even_when_allow_listed(op_type: str) -> None:
    entry = OP_CATALOG[op_type]
    params = {"model": "x_m", "name": "x_note", "field_type": "char"}
    assert entry.risk_base == "R2"
    assert entry.ddl is True
    assert op_base_risk(op_type, params) == "R2"
    listed = frozenset({op_type})
    assert l4_gate_01_refusal(op_type=op_type, params=params, allow_list=listed) == L4_R2_DDL
    assert _may(op_type, risk="R2", params=params, allow_list=listed) is False
    assert _may(op_type, risk="R1", params=params, allow_list=listed) is False


def test_r2_non_ddl_non_protected_non_outbound_on_the_list_may_pass() -> None:
    params = {"model": "sale.order", "name": "Inherit the quotation report"}
    assert OP_CATALOG["report.inherit"].risk_base == "R2"
    assert OP_CATALOG["report.inherit"].ddl is False
    assert op_base_risk("report.inherit", params) == "R2"
    assert protection_level({"type": "report.inherit", "params": params}) is None
    listed = frozenset({"report.inherit"})
    assert l4_gate_01_refusal(op_type="report.inherit", params=params, allow_list=listed) is None
    assert _may("report.inherit", risk="R2", params=params, allow_list=listed) is True


def test_r2_protected_target_is_refused() -> None:
    params = {"model": "product.category", "domain": [], "values": {"name": "Shelf"}}
    assert OP_CATALOG["data.update_batch"].risk_base == "R2"
    assert OP_CATALOG["data.update_batch"].ddl is False
    assert op_base_risk("data.update_batch", params) == "R2"
    assert protection_level({"type": "data.update_batch", "params": params}) == "elevate"
    listed = frozenset({"data.update_batch"})
    assert l4_gate_01_refusal(op_type="data.update_batch", params=params, allow_list=listed) == L4_PROTECTED
    assert _may("data.update_batch", risk="R2", params=params, allow_list=listed) is False


def test_r3_base_risk_is_refused_when_the_op_is_allow_listed() -> None:
    params = {"model": "res.partner", "name": "x_acl", "group": "sales.group_sale_user"}
    assert op_base_risk("access.create", params) == "R3"
    listed = frozenset({"access.create"})
    assert l4_gate_01_refusal(op_type="access.create", params=params, allow_list=listed) == L4_BASE_RISK
    assert _may("access.create", risk="R1", params=params, allow_list=listed) is False


def test_supplied_r3_on_an_r1_op_stays_refused() -> None:
    listed = frozenset({"mail_template.create"})
    assert l4_gate_01_refusal(op_type="mail_template.create", allow_list=listed) is None
    assert _may("mail_template.create", risk="R3", allow_list=listed) is False


@pytest.mark.parametrize(
    "email_params",
    [
        {"model": "sale.order", "name": "Mail the customer", "actions": [{"state": "email"}]},
        {"model": "sale.order", "name": "Mail the customer", "actions": [{"action": "email"}]},
        {
            "model": "sale.order",
            "name": "Mail the customer",
            "action_kind": "mail_post",
            "mail_post_method": "email",
        },
    ],
)
def test_r2_automation_create_with_email_action_is_refused_as_outbound(email_params: dict) -> None:
    plain = {"model": "sale.order", "name": "On confirm"}
    listed = frozenset({"automation.create"})
    assert OP_CATALOG["automation.create"].risk_base == "R2"
    assert OP_CATALOG["automation.create"].ddl is False
    assert op_base_risk("automation.create", plain) == "R2"
    assert op_base_risk("automation.create", email_params) == "R2"
    assert protection_level({"type": "automation.create", "params": email_params}) is None
    assert l4_gate_01_refusal(op_type="automation.create", params=plain, allow_list=listed) is None
    assert _may("automation.create", risk="R2", params=plain, allow_list=listed) is True
    assert (
        l4_gate_01_refusal(op_type="automation.create", params=email_params, allow_list=listed)
        == L4_OUTBOUND
    )
    assert _may("automation.create", risk="R2", params=email_params, allow_list=listed) is False
    assert _may("automation.create", risk="R1", params=email_params, allow_list=listed) is False


def test_r2_automation_create_safe_actions_mail_post_is_refused_as_outbound() -> None:
    email_params = {
        "model": "sale.order",
        "name": "Mail the customer",
        "safe_actions": [{"kind": "mail_post", "mail_post_method": "email"}],
    }
    listed = frozenset({"automation.create"})
    assert op_base_risk("automation.create", email_params) == "R2"
    assert protection_level({"type": "automation.create", "params": email_params}) is None
    assert (
        l4_gate_01_refusal(op_type="automation.create", params=email_params, allow_list=listed)
        == L4_OUTBOUND
    )
    assert _may("automation.create", risk="R2", params=email_params, allow_list=listed) is False
    assert _may("automation.create", risk="R1", params=email_params, allow_list=listed) is False


@pytest.mark.parametrize(
    "action_server_ids",
    [
        [{"state": "mail_post", "mail_post_method": "email"}],
        [(0, 0, {"state": "mail_post", "mail_post_method": "email"})],
    ],
)
def test_r2_automation_create_action_server_ids_mail_post_email_is_refused_as_outbound(
    action_server_ids: list,
) -> None:
    email_params = {
        "model": "sale.order",
        "name": "Mail the customer",
        "action_server_ids": action_server_ids,
    }
    listed = frozenset({"automation.create"})
    assert op_base_risk("automation.create", email_params) == "R2"
    assert protection_level({"type": "automation.create", "params": email_params}) is None
    assert (
        l4_gate_01_refusal(op_type="automation.create", params=email_params, allow_list=listed)
        == L4_OUTBOUND
    )
    assert _may("automation.create", risk="R2", params=email_params, allow_list=listed) is False
    assert _may("automation.create", risk="R1", params=email_params, allow_list=listed) is False
