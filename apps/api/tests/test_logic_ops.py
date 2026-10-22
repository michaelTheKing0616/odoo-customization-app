"""T8-OP-LOGIC risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.executor import _protocol, apply, reset_journal
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.logic_ops import (
    BOMB,
    DUNDER_CLASS,
    DUNDER_GLOBALS,
    GETATTR_CHAIN,
    LOGIC_OP_TYPES,
    OBFUSCATED_IMPORT,
    STAGE_MODEL_REQUIRED,
    logic_base_raise,
    logic_target_model,
    logic_write_op,
    safe_eval_ast_issues,
    safe_eval_issues_in_params,
    safe_eval_sandbox_issues,
)
from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.policy import (
    HEAVY_GATE_BACKUP,
    HEAVY_GATE_DISTINCT,
    HEAVY_GATE_SIMULATION,
    HEAVY_GATE_WINDOW,
    risk_of,
)

pytestmark = pytest.mark.no_app_db

_SERVER = ("server_action.create", "server_action.update")
_AUTOMATION = ("automation.create", "automation.update", "automation.disable")
_CRON = ("cron.create", "cron.update", "cron.disable")
_BENIGN = (
    "record.write({'x_flag': True})",
    "getattr(record, 'name')",
    "2 ** 8",
    "'SO' * 3",
    "[0] * 10",
    "for rec in records:\n    rec.x_flag = True",
)
_RT25 = (
    (OBFUSCATED_IMPORT, 'builtins["__" + "import" + "__"]("os")'),
    (OBFUSCATED_IMPORT, "import os"),
    (OBFUSCATED_IMPORT, "__import__('os')"),
    (DUNDER_CLASS, "record.__class__"),
    (DUNDER_CLASS, "record['\\u005f\\u005fclass\\u005f\\u005f']"),
    (DUNDER_GLOBALS, "(lambda: None).__globals__"),
    (DUNDER_GLOBALS, "fn.__globals__['__builtins__']"),
    (GETATTR_CHAIN, "getattr(getattr(record, 'partner_id'), 'name')"),
    (BOMB, "2 ** 2 ** 20"),
    (BOMB, "'x' * (10 ** 6)"),
    (BOMB, "[0] * 100000"),
)


def test_server_action_code_email_sms_and_webhook_are_r3() -> None:
    channels = (
        {"code": "record.write({'x_flag': True})"},
        {"email": True},
        {"sms": True},
        {"webhook": True},
        {"state": "code"},
        {"state": "email"},
        {"state": "SMS"},
        {"state": "webhook"},
    )
    for op_type in _SERVER:
        assert OP_CATALOG[op_type].risk_base == "R2"
        for params in channels:
            op = {"type": op_type, "params": params}
            assert risk_of(op) == "R3"
            assert op_base_risk(op_type, params) == "R3"
            assert risk_of({**op, "risk": "R0"}) == "R3"
        plain = {"model": "sale.order", "name": "Set flag", "state": "object_write"}
        assert risk_of({"type": op_type, "params": plain}) == "R2"
        assert logic_base_raise(op_type, plain) is None


def test_outbound_or_mass_automation_is_r3() -> None:
    raised = (
        {"model": "sale.order", "outbound": True},
        {"model": "sale.order", "mass": True},
        {"model": "sale.order", "kind": "outbound"},
        {"model": "sale.order", "trigger": "mass"},
        {"model": "sale.order", "actions": [{"outbound": True}]},
    )
    for op_type in _AUTOMATION:
        assert OP_CATALOG[op_type].risk_base == "R2"
        plain = {"model": "sale.order", "name": "On confirm"}
        assert risk_of({"type": op_type, "params": plain, "risk": "R0"}) == "R2"
        for params in raised:
            assert risk_of({"type": op_type, "params": params}) == "R3"
            assert op_base_risk(op_type, params) == "R3"


def test_cron_is_r3() -> None:
    for op_type in _CRON:
        assert OP_CATALOG[op_type].risk_base == "R3"
        params = {"model": "sale.order", "name": "Nightly"}
        assert op_base_risk(op_type, params) == "R3"
        assert risk_of({"type": op_type, "params": params, "risk": "R0"}) == "R3"
        assert logic_base_raise(op_type, params) is None


def test_accounting_journal_or_legal_sequence_is_r4() -> None:
    raised = (
        {"code": "sale.order", "name": "Sales", "accounting": True},
        {"code": "sale.order", "name": "Contract", "legal": True},
        {"code": "sale.order", "name": "Misc", "journal": True},
        {"code": "sale.order", "name": "Misc", "kind": "journal"},
        {"code": "sale.order", "name": "Misc", "purpose": "legal"},
        {"code": "sale.order", "alias": "account.journal", "name": "Sales"},
        {"code": "account.move", "name": "Entry"},
    )
    for op_type in ("sequence.create", "sequence.update"):
        assert OP_CATALOG[op_type].risk_base == "R2"
        plain = {"code": "sale.order", "name": "Sales"}
        assert risk_of({"type": op_type, "params": plain, "risk": "R0"}) == "R2"
        assert logic_base_raise(op_type, plain) is None
        for params in raised:
            assert risk_of({"type": op_type, "params": params, "risk": "R1"}) == "R4"


def test_existing_token_scan_still_rejects_sudo_before_the_ast() -> None:
    handler = handler_for("server_action.create")
    issues = handler.issues({"code": "record.sudo().write({})"})
    assert issues == ["server action code contains forbidden token sudo("]


@pytest.mark.parametrize(("reason", "source"), _RT25)
def test_safe_eval_ast_and_sandbox_reject_rt25(reason: str, source: str) -> None:
    assert reason in safe_eval_ast_issues(source)
    assert reason in safe_eval_sandbox_issues(source)


@pytest.mark.parametrize("source", _BENIGN)
def test_safe_eval_accepts_ordinary_server_action_code(source: str) -> None:
    assert safe_eval_ast_issues(source) == []
    assert safe_eval_sandbox_issues(source) == []


def test_sandbox_does_not_execute() -> None:
    assert safe_eval_sandbox_issues("raise RuntimeError('executed')") == []
    assert BOMB in safe_eval_sandbox_issues("2 ** 2 ** 20")


def test_handler_rejects_rt25_that_the_token_scan_misses() -> None:
    handler = handler_for("server_action.update")
    hidden_class = "record['\\u005f\\u005fclass\\u005f\\u005f']"
    hidden_import = 'builtins["__" + "import" + "__"]("os")'
    chain = "getattr(getattr(record, 'partner_id'), 'name')"
    bomb = "2 ** 2 ** 20"
    assert handler.issues({"code": hidden_class}) == [DUNDER_CLASS]
    assert handler.issues({"code": hidden_import}) == [OBFUSCATED_IMPORT]
    assert handler.issues({"code": chain}) == [GETATTR_CHAIN]
    assert handler.issues({"python_code": bomb}) == [BOMB]
    assert handler.issues({"model": "sale.order", "state": "object_write"}) == []

    store: dict = {}
    for code, match in (
        (hidden_class, DUNDER_CLASS),
        (hidden_import, OBFUSCATED_IMPORT),
        (bomb, BOMB),
    ):
        with pytest.raises(ValueError, match=match):
            apply_memory(store, {"type": "server_action.create", "params": {"code": code}})
    assert store == {}
    with pytest.raises(ValueError, match=BOMB):
        apply_memory(
            store,
            {
                "type": "automation.create",
                "params": {"model": "sale.order", "actions": [{"python_code": bomb}]},
            },
        )
    assert store == {}
    apply_memory(
        store,
        {
            "type": "server_action.create",
            "params": {
                "model": "sale.order",
                "name": "Set flag",
                "state": "object_write",
                "code": "record.write({'x_flag': True})",
            },
        },
    )
    apply_memory(
        store,
        {"type": "automation.update", "params": {"model": "sale.order", "name": "On confirm"}},
    )
    apply_memory(store, {"type": "sequence.create", "params": {"code": "sale.order", "name": "Sales"}})
    assert len(store) == 3


_RANK = ("R0", "R1", "R2", "R3", "R4")
_FAMILY = LOGIC_OP_TYPES


class _Port:
    """In-memory port. A refused logic op must not call it."""

    def __init__(self, xmlids: dict[str, int] | None = None) -> None:
        self.created: list[tuple[str, dict]] = []
        self.writes: list[tuple[str, list[int], dict]] = []
        self._xmlids = dict(xmlids or {})

    def create(self, model: str, values: dict) -> int:
        self.created.append((model, dict(values)))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        self.writes.append((model, list(ids), dict(values)))

    def lookup_xmlid(self, xmlid: str) -> int | None:
        return self._xmlids.get(xmlid)

    def calls(self) -> int:
        return len(self.created) + len(self.writes)


def _logic_params(op_type: str) -> dict:
    """Benign params the executor and dispatcher accept for one logic op."""
    family = op_type.split(".", 1)[0]
    params: dict = {"model": "sale.order", "name": "x_on_confirm"}
    if family == "sequence":
        params = {"name": "x_ticket", "code": "x_ticket", "prefix": "TK/"}
    if family == "activity_type":
        params["summary"] = "Call back"
    if family == "stage":
        params = {"model": "crm.stage", "name": "Qualified", "sequence": 20}
    if op_type == "config_record.upsert":
        params = {"model": "x_settings", "values": {"name": "VIP"}}
    if logic_write_op(op_type):
        params["id"] = 7
    return params


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


@pytest.mark.parametrize("op_type", _FAMILY)
def test_logic_ops_apply_through_the_existing_executor(op_type: str) -> None:
    port = _Port()
    result = apply([{"type": op_type, "params": _logic_params(op_type)}], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls() == 1
    if op_type == "config_record.upsert":
        assert port.created[0][0] == "x_settings"
        return
    target = logic_target_model(op_type, _logic_params(op_type))
    if logic_write_op(op_type):
        assert port.writes[0][0] == target
        assert port.writes[0][1] == [7]
        assert port.created == []
    else:
        assert port.created[0][0] == target
        assert port.writes == []


def test_logic_targets_are_public_orm_models() -> None:
    expected = {
        "server_action": "ir.actions.server",
        "automation": "base.automation",
        "cron": "ir.cron",
        "sequence": "ir.sequence",
        "mail_template": "mail.template",
        "activity_type": "mail.activity.type",
        "stage": "crm.stage",
        "config_record": "x_settings",
    }
    for op_type in LOGIC_OP_TYPES:
        family = op_type.split(".", 1)[0]
        target = logic_target_model(op_type, _logic_params(op_type))
        assert target == expected[family], op_type


@pytest.mark.parametrize("op_type", _FAMILY)
def test_caller_risk_never_lowers_catalog_risk_for_logic_ops(op_type: str) -> None:
    base = OP_CATALOG[op_type].risk_base
    for caller in _RANK:
        got = risk_of({"type": op_type, "params": _logic_params(op_type), "risk": caller})
        assert _RANK.index(got) >= _RANK.index(base), (op_type, caller, got)


def test_code_server_action_needs_r3_through_the_executor() -> None:
    error = _protocol().BridgeError
    for op_type in _SERVER:
        params = {**_logic_params(op_type), "code": "record.write({'x_flag': True})"}
        op = {"type": op_type, "params": params, "risk": "R1"}
        port = _Port()
        with pytest.raises(error) as blocked:
            apply([op], mode="T", port=port, max_risk="R2")
        assert blocked.value.code == "max_risk"
        assert port.calls() == 0
        reset_journal()
        admitted = apply([op], mode="T", port=port, max_risk="R3")
        assert admitted["status"] == "VERIFIED"
        values = (port.writes[0][2] if logic_write_op(op_type) else port.created[0][1])
        assert values["state"] == "code"
        reset_journal()


@pytest.mark.parametrize("channel", ("email", "sms", "webhook"))
def test_outbound_server_action_channels_need_r3_through_the_executor(channel: str) -> None:
    error = _protocol().BridgeError
    port = _Port()
    op = {"type": "server_action.create", "params": {**_logic_params("server_action.create"), "state": channel}}
    with pytest.raises(error) as blocked:
        apply([op], mode="T", port=port, max_risk="R2")
    assert blocked.value.code == "max_risk"
    assert port.calls() == 0


@pytest.mark.parametrize("flag", ("outbound", "mass"))
def test_outbound_or_mass_automation_needs_r3_through_the_executor(flag: str) -> None:
    error = _protocol().BridgeError
    for op_type in _AUTOMATION:
        port = _Port()
        op = {"type": op_type, "params": {**_logic_params(op_type), flag: True}, "risk": "R0"}
        with pytest.raises(error) as blocked:
            apply([op], mode="T", port=port, max_risk="R2")
        assert blocked.value.code == "max_risk"
        assert port.calls() == 0
        reset_journal()


def test_cron_needs_r3_through_the_executor() -> None:
    error = _protocol().BridgeError
    for op_type in _CRON:
        port = _Port()
        op = {"type": op_type, "params": _logic_params(op_type), "risk": "R0"}
        with pytest.raises(error) as blocked:
            apply([op], mode="T", port=port, max_risk="R2")
        assert blocked.value.code == "max_risk"
        assert port.calls() == 0
        reset_journal()


def test_accounting_journal_or_legal_sequence_never_reaches_the_port() -> None:
    error = _protocol().BridgeError
    for op_type in ("sequence.create", "sequence.update"):
        for extra in ({"code": "account.move"}, {"alias": "account.journal"}, {"kind": "journal"}):
            port = _Port()
            op = {"type": op_type, "params": {**_logic_params(op_type), **extra}, "risk": "R1"}
            with pytest.raises((error, DispatchError)):
                apply([op], mode="T", port=port, max_risk="R3")
            assert port.calls() == 0
            reset_journal()
        for flag in ("accounting", "legal"):
            port = _Port()
            op = {"type": op_type, "params": {**_logic_params(op_type), flag: True}}
            with pytest.raises((error, DispatchError)):
                apply([op], mode="T", port=port, max_risk="R3")
            assert port.calls() == 0
            reset_journal()


@pytest.mark.parametrize(("reason", "source"), _RT25)
def test_rt25_code_never_reaches_the_port_through_the_executor(reason: str, source: str) -> None:
    error = _protocol().BridgeError
    for op_type in (*_SERVER, "automation.create"):
        params = {**_logic_params(op_type), "code": source}
        if op_type == "automation.create":
            params = {**_logic_params(op_type), "actions": [{"python_code": source}]}
        port = _Port()
        with pytest.raises((error, DispatchError)):
            apply([{"type": op_type, "params": params}], mode="T", port=port, max_risk="R3")
        assert port.calls() == 0
        reset_journal()
        assert reason in safe_eval_issues_in_params(params)
        assert handler_for(op_type).issues(params)
        with pytest.raises(DispatchError):
            dispatch_op(port, {"type": op_type, "params": params})
        assert port.calls() == 0


def test_logic_payload_only_writes_allowlisted_public_fields() -> None:
    port = _Port()
    dispatch_op(
        port,
        {
            "type": "server_action.create",
            "params": {
                "model": "sale.order",
                "name": "Set flag",
                "state": "object_write",
                "groups_id": [(4, 1)],
                "binding_model_id": "res.users",
            },
        },
    )
    assert port.created == [
        ("ir.actions.server", {"name": "Set flag", "state": "object_write", "model_id": "sale.order"})
    ]
    dispatch_op(
        port,
        {
            "type": "stage.upsert",
            "params": {"model": "crm.stage", "values": {"name": "Won", "fold": True, "is_won": True}},
        },
    )
    assert port.created[-1] == ("crm.stage", {"name": "Won", "fold": True})


def test_logic_create_without_model_is_refused() -> None:
    for op_type in ("server_action.create", "automation.create", "cron.create"):
        port = _Port()
        with pytest.raises(DispatchError, match="model is required"):
            dispatch_op(port, {"type": op_type, "params": {"name": "x_orphan"}})
        assert port.calls() == 0


@pytest.mark.parametrize("model", ("res.partner", "sale.order", "x_ticket"))
def test_stage_ops_refuse_a_non_stage_model(model: str) -> None:
    for op_type in ("stage.upsert", "stage.reorder", "stage.archive"):
        port = _Port()
        params = {"model": model, "name": "Done", "ids": [1, 2]}
        with pytest.raises(DispatchError, match=STAGE_MODEL_REQUIRED):
            apply([{"type": op_type, "params": params}], mode="T", port=port)
        assert port.calls() == 0
        reset_journal()


@pytest.mark.parametrize("model", ("res.users", "res.groups", "account.move"))
def test_stage_ops_on_a_protected_model_never_reach_the_port(model: str) -> None:
    error = _protocol().BridgeError
    for op_type in ("stage.upsert", "stage.reorder", "stage.archive"):
        port = _Port()
        params = {"model": model, "name": "Done", "ids": [1, 2]}
        with pytest.raises((error, DispatchError)):
            apply([{"type": op_type, "params": params}], mode="T", port=port)
        assert port.calls() == 0
        reset_journal()


def test_stage_reorder_writes_sequence_in_the_given_order() -> None:
    port = _Port()
    result = apply(
        [{"type": "stage.reorder", "params": {"model": "project.task.type", "ids": [5, 3, 9]}}],
        mode="T",
        port=port,
    )
    assert result["status"] == "VERIFIED"
    assert port.writes == [
        ("project.task.type", [5], {"sequence": 10}),
        ("project.task.type", [3], {"sequence": 20}),
        ("project.task.type", [9], {"sequence": 30}),
    ]


def test_stage_upsert_writes_the_row_found_by_xmlid() -> None:
    port = _Port(xmlids={"ingenium.stage_qualified": 42})
    dispatch_op(
        port,
        {
            "type": "stage.upsert",
            "params": {"model": "x_ticket_stage", "name": "Qualified", "xmlid": "ingenium.stage_qualified"},
        },
    )
    assert port.writes == [("x_ticket_stage", [42], {"name": "Qualified"})]
    assert port.created == []


def test_disable_and_archive_write_active_false() -> None:
    for op_type, model in (
        ("automation.disable", "base.automation"),
        ("cron.disable", "ir.cron"),
        ("stage.archive", "crm.stage"),
    ):
        port = _Port()
        dispatch_op(port, {"type": op_type, "params": _logic_params(op_type)})
        assert port.writes == [(model, [7], {"active": False})]


def test_logic_update_without_an_id_is_refused() -> None:
    for op_type in LOGIC_OP_TYPES:
        if not logic_write_op(op_type):
            continue
        port = _Port()
        params = {key: value for key, value in _logic_params(op_type).items() if key != "id"}
        with pytest.raises(DispatchError):
            dispatch_op(port, {"type": op_type, "params": params})
        assert port.calls() == 0


def test_config_record_upsert_writes_the_row_found_by_xmlid() -> None:
    port = _Port(xmlids={"ingenium.x_vip": 9})
    dispatch_op(
        port,
        {
            "type": "config_record.upsert",
            "params": {
                "model": "x_settings",
                "xmlid": "ingenium.x_vip",
                "values": {"name": "VIP"},
            },
        },
    )
    assert port.writes == [("x_settings", [9], {"name": "VIP"})]
    assert port.created == []


def test_config_record_upsert_without_model_is_refused() -> None:
    port = _Port()
    with pytest.raises(DispatchError, match="model is required"):
        dispatch_op(port, {"type": "config_record.upsert", "params": {"values": {"name": "VIP"}}})
    assert port.calls() == 0

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


def test_heavy_sequence_refused_with_only_one_approver() -> None:
    port = _Port()
    op = {
        "type": "sequence.create",
        "params": {"code": "sale.order", "name": "Misc", "journal": True},
        **_full_heavy_gate(approvals=[_heavy_person("ada")]),
    }
    assert handler_for("sequence.create").refuse_reason(op["params"], document=[op]) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, op)
    assert port.calls() == 0


def test_heavy_sequence_refused_when_same_person_or_requester_is_both() -> None:
    port = _Port()
    same = {
        "type": "sequence.create",
        "params": {"code": "sale.order", "name": "Misc", "kind": "journal"},
        **_full_heavy_gate(
            approvals=[
                _heavy_person("ada", approver_id="google-ada", provider="google"),
                _heavy_person("ada", approver_id="microsoft-ada", provider="microsoft"),
            ]
        ),
    }
    assert handler_for("sequence.create").refuse_reason(same["params"], document=[same]) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, same)
    requester_both = {
        "type": "sequence.create",
        "params": {"code": "sale.order", "name": "Misc", "purpose": "legal"},
        **_full_heavy_gate(
            approvals=[
                _heavy_person("cam", approver_id="google-cam", provider="google"),
                _heavy_person("cam", approver_id="microsoft-cam", provider="microsoft"),
            ]
        ),
    }
    assert handler_for("sequence.create").refuse_reason(
        requester_both["params"], document=[requester_both]
    ) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, requester_both)
    assert port.calls() == 0


def test_heavy_sequence_refused_without_simulation_backup_or_window() -> None:
    port = _Port()
    base_params = {"code": "sale.order", "name": "Misc", "journal": True}
    for key, value, reason in (
        ("simulation_passed", False, HEAVY_GATE_SIMULATION),
        ("backup_id", "  ", HEAVY_GATE_BACKUP),
        (
            "allowed_window",
            {"start": "2026-10-05T10:00:00+00:00", "end": "2026-10-05T14:00:00+00:00"},
            HEAVY_GATE_WINDOW,
        ),
    ):
        op = {
            "type": "sequence.create",
            "params": base_params,
            **_full_heavy_gate(**{key: value}),
        }
        assert handler_for("sequence.create").refuse_reason(op["params"], document=[op]) == reason
        with pytest.raises(DispatchError, match=reason):
            dispatch_op(port, op)
    assert port.calls() == 0


def test_heavy_sequence_applies_with_full_heavy_gate() -> None:
    reset_journal()
    port = _Port()
    op = {
        "type": "sequence.create",
        "params": {"code": "sale.order", "name": "Misc", "journal": True},
        **_full_heavy_gate(),
    }
    assert handler_for("sequence.create").refuse_reason(op["params"], document=[op]) is None
    result = apply([op], mode="T", port=port, max_risk="R4")
    assert result["status"] == "VERIFIED"
    assert port.calls() == 1
    assert port.created == [("ir.sequence", {"name": "Misc", "code": "sale.order"})]
    reset_journal()


def test_hard_stop_accounting_sequence_denied_even_with_full_heavy_gate() -> None:
    port = _Port()
    op = {
        "type": "sequence.create",
        "params": {"code": "sale.order", "name": "Sales", "accounting": True},
        **_full_heavy_gate(),
    }
    assert handler_for("sequence.create").refuse_reason(op["params"], document=[op]) == (
        "accounting sequences are prohibited"
    )
    with pytest.raises(DispatchError, match="accounting sequences are prohibited"):
        dispatch_op(port, op)
    with pytest.raises(Exception):
        apply([op], mode="T", port=port, max_risk="R4")
    assert port.calls() == 0
    reset_journal()
