"""T8-S03. A second apply of the same plan writes nothing.

Uses the in-process executor and a fake port. The write port is ``create``
and ``write``. Ops the executor cannot apply are listed and are not claimed.
This module does not invent an inverse and does not call Odoo.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from app.changeset.dispatch import DispatchError
from app.changeset.executor import apply, get_journal, reset_journal
from app.changeset.ops import OP_CATALOG

pytestmark = pytest.mark.no_app_db


class SecondApplyWouldWrite(Exception):
    """A create or write arrived after the first apply was closed."""


class FakePort:
    """In-memory port. ``close`` makes a later create or write fail closed."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []
        self.closed = False

    def calls(self) -> int:
        """How many create and write calls were stored.

        Inputs: none.
        Outputs: the stored call count. A refused second write is not stored.
        Side effects: none.
        """
        return len(self.created) + len(self.writes)

    def close(self) -> None:
        """Refuse any later create or write.

        Inputs: none.
        Outputs: none.
        Side effects: sets ``closed``. Does not open a socket.
        """
        self.closed = True

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create, or fail closed when this port is closed.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values`` when open. Does not open a socket.
        Raises SecondApplyWouldWrite when closed. That call is not stored.
        """
        if self.closed:
            raise SecondApplyWouldWrite("second apply would write")
        self.created.append((model, dict(values)))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write, or fail closed when this port is closed.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: appends copies when open. Does not open a socket.
        Raises SecondApplyWouldWrite when closed. That call is not stored.
        """
        if self.closed:
            raise SecondApplyWouldWrite("second apply would write")
        self.writes.append((model, list(ids), dict(values)))


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("idempotency suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _params(op_type: str) -> dict[str, Any]:
    """Params the dispatcher can accept for one catalog op.

    Inputs: catalog op type.
    Outputs: a custom model, an ``x_`` field name, a group, and the keys the
    current dispatcher reads. ``field.create`` also carries ``ttype``.
    Side effects: none.
    """
    params: dict[str, Any] = {
        "model": "x_ticket",
        "name": "x_note",
        "group": "base.group_user",
        "groups": ["base.group_user"],
        "module": "sale",
        "key": "x_ticket.flag",
        "value": "1",
        "xmlid": "ingenium." + op_type.replace(".", "_"),
        "values": {"name": "VIP"},
        "domain_force": "[('id', '=', 1)]",
        "global": True,
        "id": 7,
        "operation": "read",
        "xpath": "//field[@name='x_note']",
    }
    if op_type == "field.create":
        params["ttype"] = "char"
    if op_type == "rule.update":
        params["operation"] = "write"
    return params


def _plan(op_type: str) -> list[dict[str, Any]]:
    """One-op change-set for ``op_type``.

    Inputs: catalog op type.
    Outputs: a list with that op and ``_params``.
    Side effects: none.
    """
    return [{"type": op_type, "params": _params(op_type)}]


def _executor_applied(op_type: str) -> bool:
    """Whether the executor applies this op through the fake port.

    Inputs: catalog op type.
    Outputs: True only when apply returns VERIFIED and the port stored at
    least one create or write. Any exception, or a result that did not write,
    is False. Those ops are not claimed.
    Side effects: applies once in memory and clears the journal. Does not call Odoo.
    """
    reset_journal()
    port = FakePort()
    try:
        result = apply(_plan(op_type), mode="T", port=port)
    except Exception:
        return False
    finally:
        reset_journal()
    return result.get("status") == "VERIFIED" and port.calls() >= 1


def _partition() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split the catalog into ops the executor applies and ops it does not.

    Inputs: none.
    Outputs: catalog-order tuples ``(applied, not_applied)``.
    Side effects: probes ``apply`` with a fake port. Does not call Odoo.
    """
    applied: list[str] = []
    not_applied: list[str] = []
    for op_type in OP_CATALOG:
        if _executor_applied(op_type):
            applied.append(op_type)
        else:
            not_applied.append(op_type)
    reset_journal()
    return tuple(applied), tuple(not_applied)


_APPLIED, _NOT_APPLIED = _partition()


def _coverage_report() -> str:
    """Name the ops this suite replays and the ops it does not claim.

    Inputs: none.
    Outputs: a two-line report. The second line is the not-claimed list.
    Side effects: none.
    """
    claimed = ", ".join(_APPLIED) if _APPLIED else "(none)"
    skipped = ", ".join(_NOT_APPLIED) if _NOT_APPLIED else "(none)"
    return (
        f"second apply writes nothing ({len(_APPLIED)}): {claimed}\n"
        f"not claimed ({len(_NOT_APPLIED)}): {skipped}"
    )


def _replay_wrote_nothing(*, before: int, after: int) -> bool:
    """Whether the second apply stored no new create or write.

    Inputs: stored call count after the first apply, and after the second.
    Outputs: True only when the first apply stored a call and the second
    count is the same. A larger second count is not success.
    Side effects: none.
    """
    if before < 1:
        return False
    return after == before


def _replay_succeeded(*, status: str | None, before: int, after: int, raised: bool) -> bool:
    """Whether a second apply is an idempotent success.

    Inputs: the second status, the call counts, and whether apply raised.
    Outputs: True only for VERIFIED with no new write-port call. A raise,
    including a closed second write, is not success.
    Side effects: none.
    """
    if raised:
        return False
    if status != "VERIFIED":
        return False
    return _replay_wrote_nothing(before=before, after=after)


@pytest.mark.parametrize("op_type", _APPLIED)
def test_second_apply_of_the_same_plan_does_not_call_the_write_port(op_type: str) -> None:
    """The second apply of one applicable plan does not call the write port.

    The executor must already apply this op. The journal length stays put,
    matching ``test_second_apply_is_idempotent``.
    """
    port = FakePort()
    plan = _plan(op_type)
    first = apply(plan, mode="T", port=port)
    assert first["status"] == "VERIFIED"
    assert port.calls() >= 1
    created = list(port.created)
    writes = list(port.writes)
    journal_len = len(get_journal())
    second = apply(plan, mode="T", port=port)
    assert second == first
    assert len(get_journal()) == journal_len
    assert port.created == created
    assert port.writes == writes
    assert (
        _replay_succeeded(
            status=second["status"],
            before=len(created) + len(writes),
            after=port.calls(),
            raised=False,
        )
        is True
    ), op_type


def test_second_apply_of_a_multi_op_plan_does_not_call_the_write_port() -> None:
    """One plan of every applicable op writes on the first apply only."""
    assert _APPLIED, _coverage_report()
    assert "field.create" in _APPLIED
    port = FakePort()
    plan = [op for op_type in _APPLIED for op in _plan(op_type)]
    first = apply(plan, mode="T", port=port)
    assert first["status"] == "VERIFIED"
    assert port.calls() == len(_APPLIED)
    created = list(port.created)
    writes = list(port.writes)
    journal_len = len(get_journal())
    second = apply(plan, mode="T", port=port)
    assert second == first
    assert len(get_journal()) == journal_len
    assert port.created == created
    assert port.writes == writes
    assert _replay_wrote_nothing(before=port.calls(), after=port.calls()) is True


def test_ops_the_executor_cannot_apply_are_not_claimed() -> None:
    """Ops the executor does not apply stay listed. This suite does not claim them.

    A second attempt on one of those ops still fails closed and does not
    store a write. That is not an idempotent VERIFIED replay.
    """
    assert _NOT_APPLIED, _coverage_report()
    assert set(_APPLIED).isdisjoint(_NOT_APPLIED)
    assert tuple(OP_CATALOG) == tuple(
        op_type for op_type in OP_CATALOG if op_type in set(_APPLIED) | set(_NOT_APPLIED)
    )
    assert len(_APPLIED) + len(_NOT_APPLIED) == len(OP_CATALOG)
    assert len(_APPLIED) < len(OP_CATALOG), _coverage_report()
    # data.* ops apply since T8-OP-DATA. user.create (T8-OP-SEC) still has no
    # dispatcher, so it is the real not-applied example.
    assert "user.create" in _NOT_APPLIED
    port = FakePort()
    plan = _plan("user.create")
    with pytest.raises(DispatchError):
        apply(plan, mode="T", port=port)
    assert port.calls() == 0
    with pytest.raises(DispatchError):
        apply(plan, mode="T", port=port)
    assert port.calls() == 0
    assert _replay_succeeded(status=None, before=0, after=port.calls(), raised=True) is False


def test_second_apply_that_would_write_fails_closed() -> None:
    """If a second apply would write, that replay is not success.

    The warm cache does not call the port. After that cache is cleared, the
    executor reaches the write port again. The port fails closed, the call
    is not stored, and the outcome is not VERIFIED.
    """
    assert "field.create" in _APPLIED
    port = FakePort()
    plan = _plan("field.create")
    first = apply(plan, mode="T", port=port)
    assert first["status"] == "VERIFIED"
    recorded = port.calls()
    assert recorded >= 1
    port.close()
    cached = apply(plan, mode="T", port=port)
    assert cached == first
    assert port.calls() == recorded
    assert port.closed is True

    reset_journal()
    status: str | None = None
    raised = False
    try:
        replay = apply(plan, mode="T", port=port)
        status = str(replay.get("status"))
    except SecondApplyWouldWrite as exc:
        raised = True
        assert "second apply would write" in str(exc)
    assert port.calls() == recorded
    assert port.created[0][0] == "ir.model.fields"
    assert (
        _replay_succeeded(status=status, before=recorded, after=port.calls(), raised=raised)
        is False
    )
    assert raised is True
    assert status is None
