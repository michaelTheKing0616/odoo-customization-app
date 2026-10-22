"""GATE-L4-02: five refusals that an allow-list cannot clear. L4 stays off."""

from __future__ import annotations

import pytest

from app.changeset.ops import op_base_risk
from app.changeset.protected_registry import protection_level
from app.worker_bot.l4_policy import l4_may_apply

pytestmark = pytest.mark.no_app_db

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


def _may(
    op_type: str,
    *,
    risk: str,
    params: dict | None = None,
    allow_list: frozenset[str],
) -> bool:
    return l4_may_apply(
        risk=risk,
        op_type=op_type,
        params=params,
        allow_list=allow_list,
        **_READY,
    )


def test_l4_refuses_r3_even_when_allow_listed() -> None:
    params = {"model": "res.partner", "name": "x_acl", "group": "sales.group_sale_user"}
    listed = frozenset({"access.create", "mail_template.create"})
    assert op_base_risk("access.create", params) == "R3"
    assert _may("access.create", risk="R1", params=params, allow_list=listed) is False
    assert _may("access.create", risk="R3", params=params, allow_list=listed) is False
    assert _may("mail_template.create", risk="R3", allow_list=listed) is False


def test_l4_refuses_r4_even_when_allow_listed() -> None:
    params = {"admin": True, "group": "base.group_system"}
    listed = frozenset({"user.groups.assign", "mail_template.create"})
    assert op_base_risk("user.groups.assign", params) == "R4"
    assert _may("user.groups.assign", risk="R1", params=params, allow_list=listed) is False
    assert _may("user.groups.assign", risk="R4", params=params, allow_list=listed) is False
    assert _may("mail_template.create", risk="R4", allow_list=listed) is False


def test_l4_refuses_protected_elevate_even_when_allow_listed() -> None:
    elevated = {"model": "product.category", "name": "x_shelf"}
    plain = {"model": "sale.order", "name": "x_note"}
    listed = frozenset({"field.update"})
    assert protection_level({"type": "field.update", "params": elevated}) == "elevate"
    assert op_base_risk("field.update", elevated) == "R1"
    assert protection_level({"type": "field.update", "params": plain}) is None
    assert _may("field.update", risk="R1", params=elevated, allow_list=listed) is False
    assert _may("field.update", risk="R2", params=elevated, allow_list=listed) is False
    assert _may("field.update", risk="R1", params=plain, allow_list=listed) is True


def test_l4_refuses_module_install_upgrade_and_uninstall_even_when_allow_listed() -> None:
    params = {"module": "sale"}
    listed = frozenset({"module.install", "module.upgrade", "module.uninstall"})
    for op_type in ("module.install", "module.upgrade", "module.uninstall"):
        assert _may(op_type, risk="R1", params=params, allow_list=listed) is False
        assert _may(op_type, risk="R2", params=params, allow_list=listed) is False


def test_l4_refuses_promote_even_when_allow_listed() -> None:
    listed = frozenset({"promote", "module.promote", "mail_template.create"})
    assert _may("promote", risk="R1", allow_list=listed) is False
    assert _may("promote", risk="R2", allow_list=listed) is False
    assert _may("module.promote", risk="R1", allow_list=listed) is False
    assert _may("mail_template.create", risk="R1", allow_list=listed) is True
