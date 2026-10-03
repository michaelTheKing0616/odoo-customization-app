"""T8-VERIFY. Deterministic checks on fake evidence. No live view, mail, or Odoo."""

from __future__ import annotations

import socket

import pytest

from app.changeset.data_ops import SAMPLE_LIMIT
from app.changeset.verify import (
    CHECKS,
    REQUIRED_SMOKE,
    RUNBOOK_VERIFY_FAILED,
    postconditions_for,
    recorded_rollbacks,
    reset_verification_log,
    verify,
)

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _isolated_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_verification_log()

    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("verification opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _field() -> dict:
    return {
        "type": "field.create",
        "params": {"model": "sale.order", "name": "x_note", "field_type": "char"},
    }


def _menu() -> dict:
    return {"type": "menu.create", "params": {"model": "ir.ui.menu"}}


def _passing_observation(ops: list[dict]) -> dict:
    posts: dict[str, dict[str, bool]] = {}
    for index, op in enumerate(ops):
        posts[str(index)] = {name: True for name in postconditions_for(op)}
    return {
        "postconditions": posts,
        "fingerprint": {
            "before": "fp-before",
            "after": "fp-after",
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
        "mail": {"before": 2, "after": 2},
        "data": {
            "counts": {"sale.order": {"expected": 4, "actual": 4}},
            "samples": {"sale.order": [{"id": "row-1"}]},
        },
    }


def _fail(observation: dict, check: str) -> None:
    if check == "postconditions":
        slot = observation["postconditions"]["0"]
        name = next(iter(slot))
        slot[name] = False
        return
    if check == "fingerprint_diff":
        observation["fingerprint"]["after"] = "fp-other"
        return
    if check == "view_render_requester":
        observation["views"]["requester"]["rendered"] = False
        return
    if check == "view_render_low_privilege":
        observation["views"]["low_privilege"]["rendered"] = False
        return
    if check == "view_render_portal":
        observation["views"]["portal"]["error"] = "portal trace"
        return
    if check == "smoke_probes":
        observation["smoke"][0]["passed"] = False
        return
    if check == "access_regression":
        observation["access"]["after"] = {"sales": {"sale.order": []}}
        return
    if check == "outbound_mail":
        observation["mail"]["after"] = observation["mail"]["before"] + 1
        return
    if check == "data_counts_and_samples":
        observation["data"]["counts"]["sale.order"]["actual"] = 3
        return
    raise AssertionError(check)


def test_passing_fakes_verify_without_a_live_view_or_mail() -> None:
    ops = [_field()]
    result = verify(ops, _passing_observation(ops), model_success=False)
    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert result["failed"] == []
    assert result["rolled_back"] is False
    assert result["runbook"] is None
    assert result["compensations"] == []
    assert [item["name"] for item in result["checks"]] == list(CHECKS)
    assert all(item["passed"] is True for item in result["checks"])
    assert result["live_view"] is False
    assert result["mail_sent"] == 0
    assert result["contacted_odoo"] is False
    assert result["model_success_ignored"] is True
    assert recorded_rollbacks() == []


@pytest.mark.parametrize("check", CHECKS)
def test_each_check_fails_on_fake_evidence(check: str) -> None:
    ops = [_field()]
    observation = _passing_observation(ops)
    _fail(observation, check)
    result = verify(ops, observation)
    failed = {item["name"]: item["passed"] for item in result["checks"]}
    assert failed[check] is False
    assert result["verified"] is False
    assert result["status"] != "VERIFIED"
    assert check in result["failed"]
    assert result["live_view"] is False
    assert result["mail_sent"] == 0
    assert result["contacted_odoo"] is False


def test_data_sample_over_the_cap_fails_the_data_check() -> None:
    ops = [_menu()]
    observation = _passing_observation(ops)
    observation["data"]["samples"]["sale.order"] = [{"id": index} for index in range(SAMPLE_LIMIT + 1)]
    result = verify(ops, observation)
    data = next(item for item in result["checks"] if item["name"] == "data_counts_and_samples")
    assert data["passed"] is False
    assert result["verified"] is False
    assert result["mail_sent"] == 0
    assert result["live_view"] is False


def test_a_live_view_claim_is_not_accepted() -> None:
    ops = [_menu()]
    observation = _passing_observation(ops)
    observation["views"]["requester"]["live"] = True
    observation["views"]["requester"]["rendered"] = True
    result = verify(ops, observation)
    view = next(item for item in result["checks"] if item["name"] == "view_render_requester")
    assert view["passed"] is False
    assert result["live_view"] is False
    assert result["verified"] is False
    assert result["contacted_odoo"] is False


@pytest.mark.parametrize(
    ("op", "risk", "status"),
    [
        ({"type": "menu.create", "params": {"model": "ir.ui.menu"}}, "R1", "NEEDS_HUMAN"),
        ({"type": "translation.upsert", "params": {"model": "sale.order"}}, "R1", "NEEDS_HUMAN"),
        (
            {"type": "field.create", "params": {"model": "sale.order", "name": "x_note"}},
            "R2",
            "ROLLED_BACK",
        ),
        (
            {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}},
            "R3",
            "ROLLED_BACK",
        ),
        ({"type": "data.delete", "params": {"model": "res.partner"}}, "R4", "ROLLED_BACK"),
    ],
)
def test_failed_check_rolls_back_at_r2_otherwise_needs_human(op: dict, risk: str, status: str) -> None:
    ops = [op]
    observation = _passing_observation(ops)
    _fail(observation, "fingerprint_diff")
    result = verify(ops, observation)
    assert result["risk"] == risk
    assert result["status"] == status
    assert result["verified"] is False
    if status == "ROLLED_BACK":
        assert result["rolled_back"] is True
        assert result["runbook"] is None
        assert result["compensations"] == [{"index": 0, "type": op["type"]}]
        assert recorded_rollbacks() == [
            {"risk": risk, "compensations": [{"index": 0, "type": op["type"]}], "status": "ROLLED_BACK"}
        ]
    else:
        assert result["rolled_back"] is False
        assert result["compensations"] == []
        assert result["runbook"] == RUNBOOK_VERIFY_FAILED
        assert recorded_rollbacks() == []
    assert result["mail_sent"] == 0
    assert result["live_view"] is False


def test_r2_rollback_compensates_in_reverse() -> None:
    ops = [
        {"type": "field.create", "params": {"model": "sale.order", "name": "x_note"}},
        {"type": "report.inherit", "params": {"model": "sale.order"}},
    ]
    observation = _passing_observation(ops)
    _fail(observation, "smoke_probes")
    result = verify(ops, observation)
    assert result["risk"] == "R2"
    assert result["status"] == "ROLLED_BACK"
    assert result["rolled_back"] is True
    assert result["compensations"] == [
        {"index": 1, "type": "report.inherit"},
        {"index": 0, "type": "field.create"},
    ]
    assert result["live_view"] is False
    assert result["mail_sent"] == 0


def test_model_claim_cannot_mark_a_failed_check_as_success() -> None:
    ops = [_field()]
    observation = _passing_observation(ops)
    _fail(observation, "postconditions")
    observation["status"] = "VERIFIED"
    observation["verified"] = True
    result = verify(ops, observation, model_success=True)
    assert result["model_success"] is True
    assert result["model_success_ignored"] is True
    assert result["verified"] is False
    assert result["status"] == "ROLLED_BACK"
    assert result["status"] != "VERIFIED"
