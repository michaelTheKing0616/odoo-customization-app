"""T8-ROLLBACK. Undo with fakes. No live Odoo and no row delete."""

from __future__ import annotations

import copy
import socket

import pytest

from app.changeset.handlers import apply_memory, handler_for
from app.changeset.inbox import Inbox
from app.changeset.policy import policy_decision
from app.changeset.rollback import (
    PIPELINE,
    approve_field_data_deletion,
    snapshots_match,
    undo,
)
from app.changeset.validate import STAGE_NAMES, validate

pytestmark = pytest.mark.no_app_db

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("undo opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _field(name: str = "x_note", model: str = "sale.order") -> dict:
    return {"type": "field.create", "params": {"model": model, "name": name, "ttype": "char"}}


def _approve(approver_id: str = "requester") -> dict[str, str]:
    return {"approver_id": approver_id, "decision": "approve"}


def _snapshot() -> dict:
    return {
        "models": ["sale.order"],
        "fields": [
            {"name": "x_note", "model": "sale.order"},
            {"name": "x_ref", "model": "sale.order"},
        ],
    }


def _store_with(*ops: dict) -> dict:
    store: dict = {}
    for op in ops:
        apply_memory(store, op)
    return store


def _memory_key(op: dict) -> str:
    params = op["params"]
    return handler_for(op["type"]).memory_key(params)


def test_undo_runs_validate_policy_and_approval() -> None:
    op = _field()
    store = _store_with(op)
    inbox = Inbox()
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[_approve()],
        inbox=inbox,
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    direct = validate(result["changeset"], known_models={"sale.order"})
    assert result["pipeline"] == list(PIPELINE)
    assert result["validation"] == direct
    assert [stage["name"] for stage in result["validation"]["stages"]] == list(STAGE_NAMES)
    assert result["policy"] == policy_decision(direct["max_risk"], "staging")
    assert result["policy"] == result["approval"]["card"]["risk"]["policy"]
    assert result["approval"]["status"] == "approved"
    assert result["approval"]["card"]["plan_hash"] in inbox.cards
    assert result["status"] == "ROLLED_BACK"
    assert result["applied"] is True
    assert store == {}


def test_undo_without_approval_does_not_change_memory_or_claim_rollback() -> None:
    op = _field()
    store = _store_with(op)
    before = copy.deepcopy(store)
    inbox = Inbox()
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        inbox=inbox,
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    assert result["pipeline"] == list(PIPELINE)
    assert result["status"] == "PENDING_APPROVAL"
    assert result["applied"] is False
    assert result["snapshot_match"] is None
    assert store == before
    assert len(inbox.cards) == 1


def test_denied_undo_does_not_hide_or_compensate() -> None:
    op = _field()
    store = _store_with(op)
    before = copy.deepcopy(store)
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[{"approver_id": "approver-a", "decision": "deny"}],
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    assert result["status"] == "REJECTED"
    assert result["applied"] is False
    assert result["snapshot_match"] is None
    assert store == before


def test_snapshot_mismatch_is_needs_human() -> None:
    op = _field()
    store = _store_with(op)
    observed = _snapshot()
    observed["fields"] = [{"model": "sale.order", "name": "x_other"}]
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[_approve()],
        expected_snapshot=_snapshot(),
        observed_snapshot=observed,
    )
    assert result["status"] == "NEEDS_HUMAN"
    assert result["snapshot_match"] is False
    assert result["applied"] is True
    assert store == {}


def test_reordered_snapshot_matches() -> None:
    expected = _snapshot()
    observed = {
        "fields": [
            {"model": "sale.order", "name": "x_ref"},
            {"model": "sale.order", "name": "x_note"},
        ],
        "models": ["sale.order"],
    }
    assert snapshots_match(expected, observed) is True
    op = _field()
    store = _store_with(op)
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[_approve()],
        expected_snapshot=expected,
        observed_snapshot=observed,
    )
    assert result["snapshot_match"] is True
    assert result["status"] == "ROLLED_BACK"


def test_invalid_undo_stops_before_approval() -> None:
    op = _field()
    store = _store_with(op)
    before = copy.deepcopy(store)
    inbox = Inbox()
    result = undo(
        [op],
        known_models=set(),
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[_approve()],
        inbox=inbox,
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    assert result["status"] == "INVALID"
    assert result["pipeline"] == ["validate"]
    assert result["policy"] is None
    assert result["approval"] is None
    assert result["applied"] is False
    assert inbox.cards == {}
    assert store == before


def test_irreversible_op_is_needs_human_without_compensate() -> None:
    op = {"type": "module.install", "params": {"module": "sale"}}
    store = _store_with(op)
    before = copy.deepcopy(store)
    result = undo(
        [op],
        known_models=set(),
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        approvals=[_approve()],
    )
    assert result["status"] == "NEEDS_HUMAN"
    assert result["pipeline"] == []
    assert result["applied"] is False
    assert store == before


def test_soft_inverse_hides_field_and_keeps_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid_compensate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compensate_memory")

    monkeypatch.setattr("app.changeset.rollback.compensate_memory", _forbid_compensate)
    op = _field()
    store = _store_with(op)
    key = _memory_key(op)
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    store[key]["rows"] = rows
    field_rows = {"sale.order:x_note": 3}
    result = undo(
        [op],
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        field_rows=field_rows,
        approvals=[_approve()],
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    hide = result["changeset"][0]
    approved_types = [change["type"] for change in result["approval"]["card"]["changes"]]
    assert result["pipeline"] == list(PIPELINE)
    assert result["status"] == "ROLLED_BACK"
    assert hide["type"] == "view.inherit.create"
    assert hide["params"]["invisible"] is True
    assert hide["params"]["remaining_rows"] == 3
    assert hide["type"] not in {"field.delete", "data.delete", "data.unlink"}
    assert approved_types == ["view.inherit.create"]
    assert result["remaining_rows"] == 3
    assert result["remaining_by_field"] == [{"model": "sale.order", "name": "x_note", "count": 3}]
    assert result["deletes_rows"] is False
    assert field_rows == {"sale.order:x_note": 3}
    assert store[key]["hidden"] is True
    assert store[key]["remaining_rows"] == 3
    assert store[key]["rows"] == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert rows == [{"id": 1}, {"id": 2}, {"id": 3}]
    deletion = result["data_deletion"]
    assert deletion["submitted"] is False
    assert deletion["applied"] is False
    assert deletion["deletes_rows"] is False
    assert deletion["changeset"][0]["type"] == "field.delete"
    assert "field.delete" not in approved_types


def test_data_deletion_is_a_separate_higher_risk_approval() -> None:
    op = _field()
    store = _store_with(op)
    key = _memory_key(op)
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    store[key]["rows"] = list(rows)
    hidden = undo(
        [op],
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        field_rows={"sale.order:x_note": 3},
        approvals=[_approve()],
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    deletion_ops = hidden["data_deletion"]["changeset"]
    partial = approve_field_data_deletion(
        deletion_ops,
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        approvals=[{"approver_id": "approver-a", "decision": "approve"}],
    )
    assert partial["status"] == "PENDING_APPROVAL"
    assert partial["applied"] is False
    assert partial["deletes_rows"] is False
    assert store[key]["rows"] == rows

    deletion = approve_field_data_deletion(
        deletion_ops,
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        approvals=[
            {"approver_id": "approver-a", "decision": "approve"},
            {"approver_id": "approver-b", "decision": "approve"},
        ],
    )
    assert deletion["pipeline"] == list(PIPELINE)
    assert deletion["status"] == "APPROVED"
    assert deletion["applied"] is False
    assert deletion["deletes_rows"] is False
    assert deletion["validation"]["max_risk"] == "R3"
    assert hidden["validation"]["max_risk"] == "R1"
    assert _RISK_ORDER.index(deletion["validation"]["max_risk"]) > _RISK_ORDER.index(
        hidden["validation"]["max_risk"]
    )
    assert deletion["policy"]["approvers"] > hidden["policy"]["approvers"]
    assert deletion["approval"]["card"]["plan_hash"] != hidden["approval"]["card"]["plan_hash"]
    deletion_types = [change["type"] for change in deletion["approval"]["card"]["changes"]]
    assert deletion_types == ["field.delete"]
    assert store[key]["rows"] == rows
    assert store[key]["hidden"] is True


def test_requester_cannot_approve_field_data_deletion() -> None:
    op = _field()
    store = _store_with(op)
    key = _memory_key(op)
    store[key]["rows"] = [{"id": 1}]
    hidden = undo(
        [op],
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        field_rows={"sale.order:x_note": 1},
        approvals=[_approve()],
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    deletion = approve_field_data_deletion(
        hidden["data_deletion"]["changeset"],
        known_models={"sale.order"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        approvals=[_approve("requester")],
    )
    assert deletion["status"] == "REJECTED"
    assert deletion["applied"] is False
    assert deletion["deletes_rows"] is False
    assert store[key]["rows"] == [{"id": 1}]


def test_sensitive_field_deletion_is_denied_and_rows_remain() -> None:
    op = _field(model="account.move")
    store = _store_with(op)
    key = _memory_key(op)
    rows = [{"id": 11}, {"id": 12}]
    store[key]["rows"] = list(rows)
    hidden = undo(
        [op],
        known_models={"account.move"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        field_rows={"account.move:x_note": 2},
        approvals=[_approve()],
        expected_snapshot={"fields": [{"model": "account.move", "name": "x_note"}]},
        observed_snapshot={"fields": [{"name": "x_note", "model": "account.move"}]},
    )
    assert hidden["status"] == "ROLLED_BACK"
    assert hidden["changeset"][0]["type"] == "view.inherit.create"
    deletion = approve_field_data_deletion(
        hidden["data_deletion"]["changeset"],
        known_models={"account.move"},
        environment="production",
        requester_id="requester",
        connection_id="conn-fake",
        approvals=[
            {"approver_id": "approver-a", "decision": "approve"},
            {"approver_id": "approver-b", "decision": "approve"},
        ],
    )
    assert deletion["pipeline"] == list(PIPELINE)
    assert deletion["validation"]["max_risk"] == "R4"
    assert deletion["policy"]["deny"] is True
    assert deletion["status"] == "REJECTED"
    assert deletion["applied"] is False
    assert deletion["deletes_rows"] is False
    assert deletion["approval"]["card"] is None
    assert store[key]["rows"] == rows


def test_mixed_undo_hides_only_the_field_that_has_rows() -> None:
    empty = _field("x_empty")
    filled = _field("x_note")
    store = _store_with(empty, filled)
    filled_key = _memory_key(filled)
    store[filled_key]["rows"] = [{"id": 7}]
    result = undo(
        [empty, filled],
        known_models={"sale.order"},
        environment="staging",
        requester_id="requester",
        connection_id="conn-fake",
        store=store,
        field_rows={"sale.order:x_note": 4, "sale.order:x_empty": 0},
        approvals=[_approve()],
        expected_snapshot=_snapshot(),
        observed_snapshot=_snapshot(),
    )
    assert result["status"] == "ROLLED_BACK"
    assert [op["type"] for op in result["changeset"]] == ["view.inherit.create", "field.deprecate"]
    assert _memory_key(empty) not in store
    assert store[filled_key]["hidden"] is True
    assert store[filled_key]["rows"] == [{"id": 7}]
    assert result["remaining_rows"] == 4
    assert all(op["type"] != "field.delete" for op in result["changeset"])
