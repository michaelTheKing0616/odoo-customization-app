"""Executor reads freeze, domain owner, and verify. No live view and no Odoo."""

from __future__ import annotations

import socket

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.policy import apply_blocked, policy_for_op
from app.changeset.verify import (
    REQUIRED_SMOKE,
    RUNBOOK_VERIFY_FAILED,
    postconditions_for,
    recorded_rollbacks,
    reset_verification_log,
    verify,
)

pytestmark = pytest.mark.no_app_db


class _Port:
    def __init__(self) -> None:
        self.created: list[str] = []

    def create(self, model: str, values: dict) -> int:
        self.created.append(model)
        return 1

    def write(self, model: str, ids: list[int], values: dict) -> None:
        return None


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_journal()
    reset_verification_log()

    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("executor gate opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)
    yield
    reset_journal()
    reset_verification_log()


def _field(name: str = "x_note", model: str = "sale.order") -> dict:
    return {"type": "field.create", "params": {"model": model, "name": name, "field_type": "char"}}


def _menu() -> dict:
    return {"type": "menu.create", "params": {"model": "ir.ui.menu"}}


def _observation(ops: list[dict], *, fail: bool) -> dict:
    posts: dict[str, dict[str, bool]] = {}
    for index, op in enumerate(ops):
        posts[str(index)] = {name: True for name in postconditions_for(op)}
    observation = {
        "postconditions": posts,
        "fingerprint": {
            "before": "fp-before",
            "after": "fp-other" if fail else "fp-after",
            "expected_after": "fp-after",
        },
        "views": {
            "requester": {"rendered": True, "error": None, "live": False},
            "low_privilege": {"rendered": True, "error": None, "live": False},
            "portal": {"rendered": True, "error": None, "live": False},
        },
        "smoke": [{"name": name, "passed": True} for name in REQUIRED_SMOKE],
        "access": {
            "before": {"sales": {"sale.order": ["read"]}},
            "after": {"sales": {"sale.order": ["read"]}},
        },
        "mail": {"before": 1, "after": 1},
        "data": {
            "counts": {"sale.order": {"expected": 1, "actual": 1}},
            "samples": {"sale.order": [{"id": "row-1"}]},
        },
    }
    return observation


def test_frozen_apply_is_refused_before_any_write(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    real = apply_blocked

    def _spy(decision: dict, *, frozen: bool) -> bool:
        calls.append(frozen)
        return real(decision, frozen=frozen)

    monkeypatch.setattr("app.changeset.executor.apply_blocked", _spy)
    port = _Port()
    op = _field()
    error = _protocol().BridgeError
    with pytest.raises(error) as frozen:
        apply([op], mode="T", port=port, frozen=True)
    assert frozen.value.code == "frozen"
    assert calls == [True]
    assert port.created == []
    assert get_journal() == []

    admitted = apply([op], mode="T", port=port, frozen=False)
    assert admitted["status"] == "VERIFIED"
    assert port.created == ["ir.model.fields"]
    assert any(entry.get("kind") == "RESULT" for entry in get_journal())


def test_failed_verify_rolls_back_at_r2_and_needs_human_below(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    real = verify

    def _spy(changeset: list[dict], observation: dict, *, model_success: bool | None = None) -> dict:
        calls.append({"ops": list(changeset), "live": observation.get("views")})
        return real(changeset, observation, model_success=model_success)

    monkeypatch.setattr("app.changeset.executor.verify", _spy)

    low = [_menu()]
    low_result = apply([_menu()], mode="T", observation=_observation(low, fail=True), model_success=True)
    assert low_result["status"] == "NEEDS_HUMAN"
    assert low_result["status"] != "VERIFIED"
    assert low_result["verification"]["verified"] is False
    assert low_result["verification"]["rolled_back"] is False
    assert low_result["verification"]["risk"] == "R1"
    assert low_result["verification"]["runbook"] == RUNBOOK_VERIFY_FAILED
    assert low_result["verification"]["live_view"] is False
    assert low_result["verification"]["mail_sent"] == 0
    assert low_result["verification"]["contacted_odoo"] is False
    assert any(entry.get("kind") == "RESULT" for entry in get_journal())
    assert not any(entry.get("kind") == "VERIFIED" for entry in get_journal())
    assert recorded_rollbacks() == []

    reset_journal()
    reset_verification_log()
    port = _Port()
    high = [_field()]
    high_result = apply(
        high,
        mode="T",
        port=port,
        observation=_observation(high, fail=True),
        model_success=True,
    )
    assert high_result["status"] == "ROLLED_BACK"
    assert high_result["status"] != "VERIFIED"
    assert high_result["verification"]["verified"] is False
    assert high_result["verification"]["rolled_back"] is True
    assert high_result["verification"]["risk"] == "R2"
    assert high_result["verification"]["live_view"] is False
    assert high_result["verification"]["mail_sent"] == 0
    assert high_result["verification"]["contacted_odoo"] is False
    assert high_result["verification"]["model_success"] is True
    assert high_result["applied_count"] == 0
    assert port.created == ["ir.model.fields"]
    assert not any(entry.get("kind") == "RESULT" for entry in get_journal())
    assert not any(entry.get("kind") == "VERIFIED" for entry in get_journal())
    assert [entry.get("index") for entry in get_journal() if entry.get("kind") == "COMPENSATE"] == [0]
    assert recorded_rollbacks()
    assert calls[0]["live"]["requester"]["live"] is False
    assert calls[1]["live"]["requester"]["live"] is False


def test_missing_domain_owner_is_refused_before_any_write(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    real = apply_blocked

    def _spy(decision: dict, *, frozen: bool) -> bool:
        calls.append(bool(decision.get("domain_owner")))
        return real(decision, frozen=frozen)

    monkeypatch.setattr("app.changeset.executor.apply_blocked", _spy)
    op = _field(model="product.category")
    decision = policy_for_op(op, "staging")
    assert decision["domain_owner"] is True
    port = _Port()
    error = _protocol().BridgeError
    with pytest.raises(error) as missing:
        apply(
            [op],
            mode="T",
            port=port,
            environment="staging",
            approvers=[{"approver_id": "ada", "role": "operator"}],
        )
    assert missing.value.code == "domain_owner_required"
    assert calls == [True]
    assert port.created == []
    assert get_journal() == []

    admitted = apply(
        [op],
        mode="T",
        port=port,
        environment="staging",
        approvers=[{"approver_id": "mina", "domain_owner": True}],
    )
    assert admitted["status"] == "VERIFIED"
    assert port.created == ["ir.model.fields"]
    assert any(entry.get("kind") == "RESULT" for entry in get_journal())
