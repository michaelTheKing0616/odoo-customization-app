"""T8-OP-LOGIC risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

import pytest

from app.changeset.handlers import apply_memory, handler_for
from app.changeset.logic_ops import (
    BOMB,
    DUNDER_CLASS,
    DUNDER_GLOBALS,
    GETATTR_CHAIN,
    OBFUSCATED_IMPORT,
    logic_base_raise,
    safe_eval_ast_issues,
    safe_eval_sandbox_issues,
)
from app.changeset.ops import OP_CATALOG, op_base_risk
from app.changeset.policy import risk_of

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
