"""T8-OP-SET risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

import pytest
from odoo_client.rpc_policy import PROTECTED_PARAMS

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.plan_card import render_plan_card
from app.changeset.policy import policy_decision, risk_of
from app.changeset.setting_ops import (
    INSTALL_REVERSAL_WARNING,
    PROTECTED_CONFIG_KEYS,
    may_be_billable,
)

pytestmark = pytest.mark.no_app_db

_PAID = ("enterprise", "online", "odoo.sh", "Odoo.sh")
_COMMUNITY = ("community", "Community", "")


class _Port:
    """In-memory port. A settings refusal must not call it."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create(self, model: str, values: dict) -> int:
        self.calls.append(("create", model, dict(values)))
        return len(self.calls)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        self.calls.append(("write", model, list(ids), dict(values)))


def _assert_r4(op: dict) -> None:
    assert op_base_risk(op["type"], op["params"]) == "R4"
    assert risk_of(op) == "R4"
    assert risk_of({**op, "risk": "R0"}) == "R4"
    for environment in ("production", "staging"):
        decision = policy_decision(risk_of(op), environment)
        assert decision["deny"] is True
        assert decision["allow"] is False


def test_protected_key_list_matches_the_rpc_policy() -> None:
    assert PROTECTED_CONFIG_KEYS == PROTECTED_PARAMS


def test_module_install_and_upgrade_are_r3_and_may_be_billable() -> None:
    for op_type in ("module.install", "module.upgrade"):
        assert OP_CATALOG[op_type].risk_base == "R3"
        params = {"module": "sale"}
        op = {"type": op_type, "params": params}
        assert op_base_risk(op_type, params) == "R3"
        assert risk_of(op) == "R3"
        assert risk_of({**op, "risk": "R0"}) == "R3"
        for edition in _COMMUNITY:
            assert may_be_billable(op_type, params, edition=edition) is False
        for edition in _PAID:
            assert may_be_billable(op_type, params, edition=edition) is True
    assert may_be_billable("module.uninstall", {"module": "sale"}, edition="enterprise") is False


def test_module_setting_key_is_r3_and_may_be_billable() -> None:
    params = {"key": " Module_sale ", "value": True}
    op = {"type": "setting.set", "params": params}
    assert op_base_risk("setting.set", params) == "R3"
    assert risk_of({**op, "risk": "R0"}) == "R4"
    for edition in _COMMUNITY:
        assert may_be_billable("setting.set", params, edition=edition) is False
    for edition in _PAID:
        assert may_be_billable("setting.set", params, edition=edition) is True
    plain = {"key": "sale.auto", "value": True}
    assert op_base_risk("setting.set", plain) == "R2"
    assert may_be_billable("setting.set", plain, edition="enterprise") is False


def test_protected_config_keys_are_forbidden_before_any_port_call() -> None:
    handler = handler_for("config_param.set")
    port = _Port()
    for key in sorted(PROTECTED_CONFIG_KEYS):
        params = {"key": key, "value": "x"}
        op = {"type": "config_param.set", "params": params}
        _assert_r4(op)
        assert handler.refuse_reason(params) == "protected parameter"
        assert handler.issues(params) == ["protected parameter"]
        with pytest.raises(PermissionError, match="protected parameter"):
            apply_memory({}, op)
        with pytest.raises(DispatchError, match="protected parameter"):
            dispatch_op(port, op)
    nested = {"values": {"key": "database.expiration_date", "value": "x"}}
    assert handler.refuse_reason(nested) == "protected parameter"
    with pytest.raises(DispatchError, match="protected parameter"):
        dispatch_op(port, {"type": "config_param.set", "params": nested})
    allowed = {"key": "web.theme", "value": "dark"}
    assert handler.refuse_reason(allowed) is None
    assert handler.issues(allowed) == []
    assert op_base_risk("config_param.set", allowed) == "R2"
    assert port.calls == []


def test_lock_dates_fiscal_year_currency_and_chart_are_r4() -> None:
    handler = handler_for("company.update")
    port = _Port()
    cases = (
        ({"lock_date": "2026-01-01"}, "lock dates are prohibited", "lock dates are refused"),
        (
            {"values": {"fiscalyear_lock_date": "2026-01-01"}},
            "lock dates are prohibited",
            "lock dates are refused",
        ),
        ({"period_lock_date": "2026-01-01"}, "lock dates are prohibited", "lock dates are refused"),
        ({"tax_lock_date": "2026-01-01"}, "lock dates are prohibited", "lock dates are refused"),
        ({"hard_lock_date": "2026-01-01"}, "lock dates are prohibited", "lock dates are refused"),
        (
            {"fiscalyear_last_month": 12, "fiscalyear_last_day": 31},
            "fiscal year changes are prohibited",
            "fiscal year changes are refused",
        ),
        ({"fiscal_year": 2026}, "fiscal year changes are prohibited", "fiscal year changes are refused"),
        ({"values": {"currency_id": 1}}, "currency changes are prohibited", "currency changes are refused"),
        ({"currency": "NGN"}, "currency changes are prohibited", "currency changes are refused"),
        (
            {"chart_template_id": "ng"},
            "chart of accounts changes are prohibited",
            "chart of accounts changes are refused",
        ),
        (
            {"chart_of_accounts": "l10n_ng"},
            "chart of accounts changes are prohibited",
            "chart of accounts changes are refused",
        ),
    )
    for params, refusal, issue in cases:
        op = {"type": "company.update", "params": params}
        _assert_r4(op)
        assert handler.refuse_reason(params) == refusal
        assert issue in handler.issues(params)
        with pytest.raises(PermissionError):
            apply_memory({}, op)
        with pytest.raises(DispatchError, match=refusal):
            dispatch_op(port, op)
    benign = {"name": "Acme"}
    assert handler.refuse_reason(benign) is None
    assert handler.issues(benign) == []
    assert op_base_risk("company.update", benign) == "R2"
    assert risk_of({"type": "company.update", "params": benign, "risk": "R0"}) == "R2"
    assert port.calls == []


def test_module_install_warns_reversal_is_uninstall() -> None:
    handler = handler_for("module.install")
    params = {"module": "sale"}
    assert handler.refuse_reason(params) is None
    assert handler.inverse(params) is None
    assert INSTALL_REVERSAL_WARNING in handler.describe(params)
    assert "uninstall" in INSTALL_REVERSAL_WARNING
    card = render_plan_card(
        [{"type": "module.install", "params": params}],
        goal="Install Sales",
        assumptions=["The module name is sale"],
        environment="staging",
    )
    assert INSTALL_REVERSAL_WARNING in card["changes"][0]["description"]
    assert handler_for("module.upgrade").describe({"module": "sale"}).endswith("ddl False")


def test_module_uninstall_is_r4_and_refuses_before_any_port_call() -> None:
    handler = handler_for("module.uninstall")
    port = _Port()
    params = {"module": "sale"}
    op = {"type": "module.uninstall", "params": params}
    assert OP_CATALOG["module.uninstall"].risk_base == "R4"
    _assert_r4(op)
    assert handler.refuse_reason(params) == "module.uninstall is prohibited"
    assert handler.inverse(params) is None
    with pytest.raises(PermissionError, match="prohibited"):
        apply_memory({}, op)
    with pytest.raises(DispatchError, match="refused"):
        dispatch_op(port, op)
    assert port.calls == []


def test_module_install_still_reaches_the_port() -> None:
    port = _Port()
    created = dispatch_op(port, {"type": "module.install", "params": {"module": "sale"}})
    assert created == 1
    assert port.calls == [("create", "ir.module.module", {"name": "sale", "state": "to install"})]
