"""T8-S04. Atomicity Mode T and compensation Mode C.

Mode T: a failure drops every RESULT row for that run. The reported status
is ROLLED_BACK and the run is not verified. Mode C: COMPENSATE rows follow
the applied indexes in reverse, and that run is not verified either.

A partial apply is not reported as verified. The journal this module reads
is the in-process list. This is not durable crash recovery and it does not
close GATE-P3-03. This module does not invent an inverse and does not call
Odoo. Compensation here is the journal order. It does not undo the fake port.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.recovery import recover

pytestmark = pytest.mark.no_app_db


class FakePort:
    """In-memory create and write log. It has no rollback and no inverse."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values``. Does not open a socket.
        """
        self.created.append((model, dict(values)))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: appends copies. Does not open a socket.
        """
        self.writes.append((model, list(ids), dict(values)))


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("atomicity suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _field(name: str) -> dict[str, Any]:
    """One custom field create.

    Inputs: field name. It must already start with ``x_``.
    Outputs: a ``field.create`` op on ``x_test.model``.
    Side effects: none.
    """
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": name, "field_type": "char"},
    }


def _plan() -> list[dict[str, Any]]:
    """Three field creates, in apply order.

    Inputs: none.
    Outputs: ``x_one``, ``x_two``, ``x_three``.
    Side effects: none.
    """
    return [_field("x_one"), _field("x_two"), _field("x_three")]


def _kinds(journal: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Journal rows of one kind, in stored order.

    Inputs: journal rows and a kind name.
    Outputs: the matching rows.
    Side effects: none.
    """
    return [entry for entry in journal if entry.get("kind") == kind]


def _created_names(port: FakePort) -> list[str]:
    """Field names stored on the fake, in create order.

    Inputs: the fake port.
    Outputs: ``name`` from each stored create.
    Side effects: none.
    """
    return [str(values.get("name")) for _model, values in port.created]


def _run_is_verified(result: dict[str, Any], journal: list[dict[str, Any]], op_count: int) -> bool:
    """Whether this run reports a complete verified apply.

    Inputs: the apply result, the journal, and the plan length.
    Outputs: True only when the status is VERIFIED, the applied count is the
    whole plan, a VERIFIED row exists, every index has a RESULT, nothing was
    compensated, and the report has no missing index. A partial plan is False.
    Side effects: none.
    """
    if result.get("status") != "VERIFIED":
        return False
    if result.get("applied_count") != op_count:
        return False
    if not _kinds(journal, "VERIFIED"):
        return False
    if _kinds(journal, "COMPENSATE"):
        return False
    results = _kinds(journal, "RESULT")
    if [entry.get("index") for entry in results] != list(range(op_count)):
        return False
    missing = result.get("report", {}).get("missing")
    return missing == []


def test_mode_t_failure_rolls_the_in_memory_plan_back_and_is_not_verified() -> None:
    """Mode T failure leaves no RESULT row and is not verified.

    The same contract as ``test_mode_t_failure_rolls_back_fully``, on a fake
    port. Creates that landed before the failure stay on the fake. They are
    not a verified run, and this file does not undo them with an inverse.
    """
    port = FakePort()
    plan = [_field("x_one"), _field("x_two")]
    result = apply(plan, mode="T", fail_at=1, port=port)
    journal = get_journal()
    assert result["status"] == "ROLLED_BACK"
    assert result["mode"] == "T"
    assert result["applied_count"] == 0
    assert result["risk_bump"] == 0
    assert result["report"]["results"] == []
    assert result["report"]["missing"] == [0, 1]
    assert result["report"]["compensates"] == []
    assert _kinds(journal, "RESULT") == []
    assert _kinds(journal, "VERIFIED") == []
    assert _kinds(journal, "COMPENSATE") == []
    assert _created_names(port) == ["x_one"]
    assert port.writes == []
    assert _run_is_verified(result, journal, len(plan)) is False


def test_mode_c_compensation_runs_in_reverse_and_is_not_verified() -> None:
    """Mode C writes COMPENSATE rows from the last applied index backward.

    The same contract as ``test_mode_c_compensates_in_reverse``. The rows
    name the forward op. They are not an inverse, and the fake is not undone.
    """
    port = FakePort()
    plan = _plan()
    result = apply(plan, mode="C", fail_at=2, port=port)
    journal = get_journal()
    compensations = _kinds(journal, "COMPENSATE")
    results = _kinds(journal, "RESULT")
    assert result["status"] == "ROLLED_BACK"
    assert result["mode"] == "C"
    assert result["applied_count"] == 0
    assert result["risk_bump"] == 1
    assert [entry["index"] for entry in compensations] == [1, 0]
    assert [entry["index"] for entry in compensations] == list(
        reversed([entry["index"] for entry in results])
    )
    assert {entry["index"] for entry in compensations} == {entry["index"] for entry in results}
    assert [entry.get("type") for entry in compensations] == ["field.create", "field.create"]
    assert all("inverse" not in entry for entry in compensations)
    assert result["report"]["compensates"] == [1, 0]
    assert result["report"]["results"] == [0, 1]
    assert result["report"]["missing"] == [2]
    assert _kinds(journal, "VERIFIED") == []
    assert _created_names(port) == ["x_one", "x_two"]
    assert port.writes == []
    assert _run_is_verified(result, journal, len(plan)) is False


def test_partial_apply_is_not_reported_as_verified() -> None:
    """A plan that stops in the middle is not reported as verified.

    Mode T drops the RESULT rows. Mode C compensates the prefix in reverse.
    Either way the status stays off VERIFIED. A journal that already carries
    a VERIFIED stamp with a missing index fails closed to NEEDS_HUMAN.
    """
    for mode in ("T", "C"):
        reset_journal()
        port = FakePort()
        plan = _plan()
        result = apply(plan, mode=mode, fail_at=1, port=port)
        journal = get_journal()
        assert result["status"] != "VERIFIED"
        assert result["applied_count"] == 0
        assert _kinds(journal, "VERIFIED") == []
        assert _created_names(port) == ["x_one"]
        assert "x_three" not in _created_names(port)
        assert _run_is_verified(result, journal, len(plan)) is False
        if mode == "T":
            assert result["status"] == "ROLLED_BACK"
            assert _kinds(journal, "RESULT") == []
            assert _kinds(journal, "COMPENSATE") == []
        else:
            assert result["status"] == "ROLLED_BACK"
            assert result["risk_bump"] == 1
            assert [entry["index"] for entry in _kinds(journal, "COMPENSATE")] == [0]
            assert {entry["index"] for entry in _kinds(journal, "COMPENSATE")} == {
                entry["index"] for entry in _kinds(journal, "RESULT")
            }

    false_verified = recover(
        [{"kind": "RESULT", "index": 0}, {"kind": "VERIFIED"}],
        mode="T",
        expected_ops=3,
    )
    assert false_verified["status"] == "NEEDS_HUMAN"
    assert false_verified["status"] != "VERIFIED"
    assert false_verified["report"]["missing"] == [1, 2]

    short_compensation = recover(
        [
            {"kind": "RESULT", "index": 0},
            {"kind": "RESULT", "index": 1},
            {"kind": "COMPENSATE", "index": 1},
        ],
        mode="C",
        expected_ops=3,
    )
    assert short_compensation["status"] == "NEEDS_HUMAN"
    assert short_compensation["status"] != "VERIFIED"
    assert short_compensation["report"]["missing"] == [2]


def test_mode_c_irreversible_op_fails_closed() -> None:
    """Mode C refuses an irreversible op before any journal row or port call."""
    port = FakePort()
    error = _protocol().BridgeError
    with pytest.raises(error) as refused:
        apply([{"type": "data.merge", "params": {"model": "res.partner"}}], mode="C", port=port)
    assert refused.value.code == "mode_c_irreversible"
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []


def test_a_finished_plan_is_verified() -> None:
    """The whole plan is verified only when every op finishes.

    This is the contrast for the failure cases. A finished plan has one
    RESULT per index, a VERIFIED row, and no COMPENSATE row.
    """
    for mode in ("T", "C"):
        reset_journal()
        port = FakePort()
        plan = _plan()
        result = apply(plan, mode=mode, port=port)
        journal = get_journal()
        assert result["status"] == "VERIFIED"
        assert result["applied_count"] == len(plan)
        assert result["risk_bump"] == 0
        assert _created_names(port) == ["x_one", "x_two", "x_three"]
        assert [entry["index"] for entry in _kinds(journal, "RESULT")] == [0, 1, 2]
        assert _kinds(journal, "COMPENSATE") == []
        assert _run_is_verified(result, journal, len(plan)) is True


def test_journal_is_an_in_memory_list() -> None:
    """The journal is a process list. Clearing it does not touch a database.

    Appending VERIFIED onto the copy returned by ``get_journal`` does not
    make the run verified. This file does not claim crash recovery.
    """
    port = FakePort()
    result = apply(_plan(), mode="T", fail_at=2, port=port)
    assert result["status"] != "VERIFIED"
    snapshot = get_journal()
    assert snapshot
    snapshot.append({"kind": "VERIFIED", "run_id": "forged"})
    assert _kinds(get_journal(), "VERIFIED") == []
    assert get_journal() == [entry for entry in snapshot if entry.get("kind") != "VERIFIED"]
    reset_journal()
    assert get_journal() == []
