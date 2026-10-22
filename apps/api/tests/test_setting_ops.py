"""T8-OP-SET risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from odoo_client.rpc_policy import PROTECTED_PARAMS

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.executor import _protocol, apply, reset_journal
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.plan_card import copy_sections_for_card, render_plan_card
from app.changeset.policy import (
    HEAVY_GATE_BACKUP,
    HEAVY_GATE_DISTINCT,
    HEAVY_GATE_SIMULATION,
    HEAVY_GATE_WINDOW,
    policy_decision,
    risk_of,
)
from app.changeset.setting_ops import (
    BILLABLE_WARNING,
    INSTALL_REVERSAL_WARNING,
    PROTECTED_CONFIG_KEYS,
    SETTING_OP_TYPES,
    billable_warning,
    may_be_billable,
)

SETTING_FAMILY = SETTING_OP_TYPES | {"module.uninstall"}

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
            HEAVY_GATE_DISTINCT,
            "fiscal year changes are refused",
        ),
        ({"fiscal_year": 2026}, HEAVY_GATE_DISTINCT, "fiscal year changes are refused"),
        ({"values": {"currency_id": 1}}, HEAVY_GATE_DISTINCT, "currency changes are refused"),
        ({"currency": "NGN"}, HEAVY_GATE_DISTINCT, "currency changes are refused"),
        (
            {"chart_template_id": "ng"},
            HEAVY_GATE_DISTINCT,
            "chart of accounts changes are refused",
        ),
        (
            {"chart_of_accounts": "l10n_ng"},
            HEAVY_GATE_DISTINCT,
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
    port = _CallPort({"sale": (41, "uninstalled")})
    installed = dispatch_op(port, {"type": "module.install", "params": {"module": "sale"}})
    assert installed == 41
    assert port.calls == [
        (
            "execute_kw",
            "ir.module.module",
            "search_read",
            [[("name", "=", "sale")]],
            {"fields": ["id", "state"], "limit": 1},
        ),
        ("execute_kw", "ir.module.module", "button_immediate_install", [[41]], None),
    ]
    assert not any(call[0] == "create" for call in port.calls)


class _CallPort(_Port):
    """In-memory port that can also call a model method."""

    def __init__(self, modules: dict[str, tuple[int, str]] | None = None) -> None:
        super().__init__()
        self._modules = dict(modules or {})

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        self.calls.append(("execute_kw", model, method, args, kwargs))
        if model == "ir.module.module" and method == "search_read":
            name = args[0][0][2]
            found = self._modules.get(name)
            return [{"id": found[0], "state": found[1]}] if found else []
        return True


_RANK = ("R0", "R1", "R2", "R3", "R4")
_APPLY_CASES = {
    "setting.set": {"key": "group_multi_currency", "value": True},
    "config_param.set": {"key": "web.theme", "value": "dark"},
    "company.update": {"id": 1, "values": {"name": "Acme", "phone": "+234 1 000"}},
    "module.install": {"module": "sale"},
    "module.upgrade": {"module": "sale"},
}


@pytest.fixture()
def _clean_journal():
    reset_journal()
    yield
    reset_journal()


@pytest.mark.parametrize("op_type", sorted(_APPLY_CASES))
def test_settings_ops_apply_through_the_existing_executor(op_type: str, _clean_journal) -> None:
    state = "installed" if op_type == "module.upgrade" else "uninstalled"
    port = _CallPort({"sale": (41, state)})
    result = apply([{"type": op_type, "params": _APPLY_CASES[op_type]}], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert result["applied_count"] == 1
    expected = {
        "setting.set": [
            ("create", "res.config.settings", {"group_multi_currency": True}),
            ("execute_kw", "res.config.settings", "execute", [[1]], None),
        ],
        "config_param.set": [
            ("execute_kw", "ir.config_parameter", "set_param", ["web.theme", "dark"], None),
        ],
        "company.update": [
            ("write", "res.company", [1], {"name": "Acme", "phone": "+234 1 000"}),
        ],
        "module.install": [
            ("execute_kw", "ir.module.module", "button_immediate_install", [[41]], None),
        ],
        "module.upgrade": [
            ("execute_kw", "ir.module.module", "button_immediate_upgrade", [[41]], None),
        ],
    }[op_type]
    effects = [call for call in port.calls if call[2:3] != ("search_read",)]
    assert effects == expected


def test_module_uninstall_never_applies_through_the_executor(_clean_journal) -> None:
    error = _protocol().BridgeError
    port = _CallPort({"sale": (41, "installed")})
    op = {"type": "module.uninstall", "params": {"module": "sale"}}
    for max_risk, escalated, reason in (
        ("R3", False, "prohibited_op"),
        ("R4", False, "prohibited_op"),
        ("R4", True, "system_escalation"),
    ):
        with pytest.raises(error) as blocked:
            apply([op], mode="T", port=port, max_risk=max_risk, escalated=escalated)
        assert blocked.value.code == reason
    with pytest.raises(DispatchError, match="module.uninstall is refused"):
        dispatch_op(port, op)
    assert port.calls == []


@pytest.mark.parametrize("op_type", sorted(SETTING_FAMILY))
def test_caller_risk_never_lowers_catalog_risk_for_settings_ops(op_type: str) -> None:
    params = _APPLY_CASES.get(op_type, {"module": "sale"})
    base = op_base_risk(op_type, params)
    assert _RANK.index(base) >= _RANK.index(OP_CATALOG[op_type].risk_base)
    for caller in _RANK:
        got = risk_of({"type": op_type, "params": params, "risk": caller})
        assert _RANK.index(got) >= _RANK.index(base), (op_type, caller, got)


def test_module_setting_carries_a_billable_warning_on_the_plan_card() -> None:
    ops = [
        {"type": "setting.set", "params": {"key": "module_sale", "value": True}},
        {"type": "module.install", "params": {"module": "sale"}},
        {"type": "setting.set", "params": {"key": "group_multi_currency", "value": True}},
    ]
    assert billable_warning("setting.set", ops[0]["params"]) == BILLABLE_WARNING
    assert billable_warning("module.uninstall", {"module": "sale"}) is None
    card = render_plan_card(ops, goal="Turn on Sales", assumptions=[], environment="staging")
    first, second, plain = card["changes"]
    assert first["billable"] is True and first["billable_warning"] == BILLABLE_WARNING
    assert second["billable"] is True
    assert "billable" not in plain and "billable_warning" not in plain
    body = card["sections"][1]["body"]
    assert body.count(BILLABLE_WARNING) == 2
    assert copy_sections_for_card(card)[1]["body"] == body


def test_settings_methods_need_a_port_that_can_call_them() -> None:
    port = _Port()
    for op_type in ("setting.set", "config_param.set", "module.install", "module.upgrade"):
        with pytest.raises(DispatchError, match="call model methods"):
            dispatch_op(port, {"type": op_type, "params": _APPLY_CASES[op_type]})
    assert port.calls == []


@pytest.mark.parametrize(
    ("op_type", "params", "reason"),
    (
        ("setting.set", {"key": "sale.auto", "value": True}, "field name"),
        ("setting.set", {"key": "group_multi_currency"}, "requires a value"),
        ("setting.set", {"key": "group_multi_currency", "value": {"a": 1}}, "scalar"),
        ("config_param.set", {"key": "web.theme", "value": False}, "delete the parameter"),
        ("config_param.set", {"key": "web.theme"}, "delete the parameter"),
        ("config_param.set", {"key": "web.theme", "value": ["x"]}, "scalar"),
        ("company.update", {"values": {"name": "Acme"}}, "company id"),
        ("company.update", {"id": 1, "values": {}}, "requires values"),
        ("company.update", {"id": 1, "values": {"name; drop": "x"}}, "field names"),
        ("module.install", {"module": "Sale Pro"}, "technical name"),
        ("module.install", {"module": "ghost"}, "not on this database"),
        ("module.upgrade", {"module": "sale"}, "not installed"),
    ),
)
def test_bad_settings_payloads_refuse_before_any_write(
    op_type: str, params: dict, reason: str
) -> None:
    port = _CallPort({"sale": (41, "uninstalled")})
    with pytest.raises(DispatchError, match=reason):
        dispatch_op(port, {"type": op_type, "params": params})
    assert not any(call[0] in {"create", "write"} for call in port.calls)
    assert not any(call[2:3] != ("search_read",) for call in port.calls if call[0] == "execute_kw")


def test_installed_module_is_not_installed_again() -> None:
    port = _CallPort({"sale": (41, "installed")})
    assert dispatch_op(port, {"type": "module.install", "params": {"module": "sale"}}) == 41
    assert [call[2] for call in port.calls] == ["search_read"]

# --- T8-HEAVY-R4 -----------------------------------------------------------

_HEAVY_NOW = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
_HEAVY_WINDOW = {
    "start": "2026-10-05T14:00:00+00:00",
    "end": "2026-10-05T16:00:00+00:00",
}


def _heavy_person(user_id: str, **extra: object) -> dict:
    record = {"approver_id": user_id, "user_id": user_id, "decision": "approve"}
    record.update(extra)
    return record


def _full_heavy_gate(**overrides: object) -> dict:
    gate = {
        "environment": "production",
        "requester_id": "cam",
        "approvals": [_heavy_person("ada"), _heavy_person("ben")],
        "simulation_passed": True,
        "backup_id": "backup-1",
        "allowed_window": _HEAVY_WINDOW,
        "now": _HEAVY_NOW.isoformat(),
    }
    gate.update(overrides)
    return gate


def test_heavy_fiscal_currency_chart_refused_with_only_one_approver() -> None:
    port = _Port()
    for params in (
        {"id": 1, "fiscalyear_last_month": 12},
        {"id": 1, "currency_id": 1},
        {"id": 1, "chart_template_id": "ng"},
    ):
        op = {"type": "company.update", "params": params, **_full_heavy_gate(approvals=[_heavy_person("ada")])}
        assert handler_for("company.update").refuse_reason(params, document=[op]) == HEAVY_GATE_DISTINCT
        with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
            dispatch_op(port, op)
    assert port.calls == []


def test_heavy_company_refused_when_same_person_or_requester_is_both() -> None:
    port = _Port()
    same = {
        "type": "company.update",
        "params": {"id": 1, "fiscal_year": 2026},
        **_full_heavy_gate(
            approvals=[
                _heavy_person("ada", provider="google"),
                _heavy_person("ada", provider="microsoft"),
            ]
        ),
    }
    assert handler_for("company.update").refuse_reason(same["params"], document=[same]) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, same)
    both = {
        "type": "company.update",
        "params": {"id": 1, "currency": "NGN"},
        **_full_heavy_gate(
            approvals=[
                _heavy_person("cam", provider="google"),
                _heavy_person("cam", provider="microsoft"),
            ]
        ),
    }
    assert handler_for("company.update").refuse_reason(both["params"], document=[both]) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, both)
    assert port.calls == []


def test_heavy_company_refused_without_simulation_backup_or_window() -> None:
    port = _Port()
    params = {"id": 1, "fiscalyear_last_month": 12, "fiscalyear_last_day": 31}
    for key, value, reason in (
        ("simulation_passed", False, HEAVY_GATE_SIMULATION),
        ("backup_id", "", HEAVY_GATE_BACKUP),
        (
            "allowed_window",
            {"start": "2026-10-05T10:00:00+00:00", "end": "2026-10-05T14:00:00+00:00"},
            HEAVY_GATE_WINDOW,
        ),
    ):
        op = {"type": "company.update", "params": params, **_full_heavy_gate(**{key: value})}
        assert handler_for("company.update").refuse_reason(params, document=[op]) == reason
        with pytest.raises(DispatchError, match=reason):
            dispatch_op(port, op)
    assert port.calls == []


def test_heavy_fiscal_currency_chart_apply_with_full_heavy_gate(_clean_journal) -> None:
    for params, values in (
        ({"id": 1, "values": {"fiscalyear_last_month": 12}}, {"fiscalyear_last_month": 12}),
        ({"id": 1, "values": {"currency_id": 2}}, {"currency_id": 2}),
        ({"id": 1, "values": {"chart_template_id": "ng"}}, {"chart_template_id": "ng"}),
    ):
        reset_journal()
        port = _Port()
        op = {"type": "company.update", "params": params, **_full_heavy_gate()}
        assert handler_for("company.update").refuse_reason(params, document=[op]) is None
        result = apply([op], mode="T", port=port, max_risk="R4")
        assert result["status"] == "VERIFIED"
        assert port.calls == [("write", "res.company", [1], values)]
    reset_journal()


def test_hard_stop_lock_dates_and_posted_entries_denied_with_full_heavy_gate() -> None:
    port = _Port()
    lock = {
        "type": "company.update",
        "params": {"id": 1, "lock_date": "2026-01-01"},
        **_full_heavy_gate(),
    }
    assert handler_for("company.update").refuse_reason(lock["params"], document=[lock]) == (
        "lock dates are prohibited"
    )
    with pytest.raises(DispatchError, match="lock dates are prohibited"):
        dispatch_op(port, lock)
    posted = {
        "type": "data.update_batch",
        "params": {
            "model": "account.move",
            "ids": [1],
            "domain": [["id", "=", 1]],
            "values": {"state": "posted"},
        },
        **_full_heavy_gate(),
    }
    # Posted accounting is a hard stop at policy / protected paths; apply must not write.
    with pytest.raises(Exception):
        apply([posted], mode="T", port=port, max_risk="R4")
    assert port.calls == []
    reset_journal()
