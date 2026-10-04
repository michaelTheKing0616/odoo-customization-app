"""T8-S13. One apply per Odoo database.

``apply`` uses the in-process ``DatabaseApplyLock`` when ``odoo_database``
is set. A second apply for that database does not write while the first
apply holds the lock. An apply for a different database may write. After
the holder releases the lock, the next apply for that database may write.

The lock is in memory. Alembic revision ``s9t0u1v2w3x4`` declares the
table ``apply_database_lock``. That revision is not applied. This suite
does not insert a lock row.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from app.changeset.executor import (
    _APPLY_LOCK,
    apply,
    changeset_fingerprint,
    get_journal,
    reset_journal,
)

pytestmark = pytest.mark.no_app_db

_HOLD_WAIT_SECONDS = 5.0
_MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "s9t0u1v2w3x4_journal_wal.py"
)


class CountingPort:
    """In-memory create and write log. It has no database connection."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []

    def names(self) -> list[str]:
        """Field names recorded by ``create``, in call order.

        Inputs: none.
        Outputs: the ``name`` of each stored create.
        Side effects: none.
        """
        return [str(values.get("name")) for _model, values in self.created]

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


class HoldingPort(CountingPort):
    """Counting port that pauses inside ``create`` for selected field names."""

    def __init__(self) -> None:
        super().__init__()
        self.holding = threading.Event()
        self.may_finish = threading.Event()
        self._hold_names: set[str] = set()

    def hold_on(self, field_name: str) -> None:
        """Pause the next create of this field until ``may_finish`` is set.

        Inputs: field name stored on the create values.
        Outputs: none.
        Side effects: remembers ``field_name``. Does not open a socket.
        """
        self._hold_names.add(field_name)

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create, then wait when this field is held.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values``. A held field sets
        ``holding`` and waits. Does not open a socket.
        Raises TimeoutError when the wait exceeds ``_HOLD_WAIT_SECONDS``.
        """
        created_id = super().create(model, values)
        name = str(values.get("name") or "")
        if name in self._hold_names:
            self.holding.set()
            if not self.may_finish.wait(timeout=_HOLD_WAIT_SECONDS):
                raise TimeoutError("holding apply was not released")
        return created_id


class _InFlight:
    """One ``apply`` paused inside its port while that call holds the lock."""

    def __init__(self, database: str, plan: list[dict[str, Any]], port: HoldingPort) -> None:
        self.database = database
        self.plan = plan
        self.port = port
        self.results: list[dict[str, Any]] = []
        self.errors: list[BaseException] = []


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("lock suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _field(name: str) -> dict[str, Any]:
    """One ``field.create`` on ``x_test.model``.

    Inputs: a field name that starts with ``x_``.
    Outputs: one op dict.
    Side effects: none.
    """
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": name, "field_type": "char"},
    }


def _plan(name: str) -> list[dict[str, Any]]:
    """A one-op change-set.

    Inputs: field name.
    Outputs: a list of one ``field.create``.
    Side effects: none.
    """
    return [_field(name)]


def _assert_busy(result: dict[str, Any], database: str, port: CountingPort) -> None:
    """The apply stopped closed and did not write.

    Inputs: the apply result, the database name, and the port passed to that apply.
    Outputs: none.
    Side effects: none.
    Raises AssertionError when the apply wrote or reported success.
    """
    assert result["status"] == "NEEDS_HUMAN"
    assert result["applied_count"] == 0
    assert result["report"]["reason"] == "database_busy"
    assert result["report"]["odoo_database"] == database
    assert result["report"]["results"] == []
    assert result["report"]["missing"] == []
    assert port.created == []
    assert port.writes == []


def _assert_holder_finished(flight: _InFlight) -> None:
    """The in-flight apply finished after releasing its database.

    Inputs: the flight started by ``_apply_holding``.
    Outputs: none.
    Side effects: none.
    Raises AssertionError when that apply did not verify one create, or the
    in-process lock is still held.
    """
    assert flight.errors == []
    assert len(flight.results) == 1
    holder = flight.results[0]
    assert holder["status"] == "VERIFIED"
    assert holder["applied_count"] == 1
    assert flight.port.names() == [str(flight.plan[0]["params"]["name"])]
    assert flight.port.writes == []
    assert _APPLY_LOCK.holder(flight.database) is None


@contextmanager
def _apply_holding(database: str, field_name: str, *, mode: str) -> Iterator[_InFlight]:
    """Start one apply and yield while that call holds the database lock.

    Inputs: Odoo database name, field name, and mode T or C.
    Outputs: the in-flight apply. Its port is paused inside ``create``.
    Side effects: starts a thread that calls ``apply`` with ``odoo_database``
    set. The thread uses the process lock. On exit the port is released and
    the thread is joined, which releases that lock. Does not open a socket
    and does not insert a lock row.
    """
    port = HoldingPort()
    port.hold_on(field_name)
    plan = _plan(field_name)
    flight = _InFlight(database, plan, port)

    def _target() -> None:
        try:
            flight.results.append(apply(plan, mode=mode, port=port, odoo_database=database))
        except BaseException as exc:
            flight.errors.append(exc)

    thread = threading.Thread(target=_target, name=f"apply-{database}")
    thread.start()
    try:
        acquired = port.holding.wait(timeout=_HOLD_WAIT_SECONDS)
        if flight.errors:
            raise flight.errors[0]
        assert acquired
        assert _APPLY_LOCK.holder(database) == changeset_fingerprint(plan)
        yield flight
    finally:
        port.may_finish.set()
        thread.join(timeout=_HOLD_WAIT_SECONDS)
        if thread.is_alive():
            raise AssertionError("holding apply did not finish")
        if flight.errors:
            raise flight.errors[0]


@pytest.mark.parametrize("mode", ["T", "C"])
def test_second_apply_same_database_does_not_write(mode: str) -> None:
    """A second apply on a held database does not write and fails closed.

    The first apply is inside its port and holds the process lock. The second
    plan is a different change-set for the same database. Its port stays empty
    and the journal does not gain that plan.
    """
    second = CountingPort()
    second_plan = _plan("x_busy")
    with _apply_holding("db-a", "x_hold", mode=mode) as flight:
        journal_before = get_journal()
        blocked = apply(second_plan, mode=mode, port=second, odoo_database="db-a")
        _assert_busy(blocked, "db-a", second)
        assert get_journal() == journal_before
        assert _APPLY_LOCK.holder("db-a") == changeset_fingerprint(flight.plan)
        busy_fp = changeset_fingerprint(second_plan)
        assert not any(
            entry.get("plan_hash") == busy_fp or entry.get("run_id") == busy_fp
            for entry in get_journal()
        )
    _assert_holder_finished(flight)


@pytest.mark.parametrize("mode", ["T", "C"])
def test_different_database_may_apply_while_lock_is_held(mode: str) -> None:
    """An apply for another database writes while the first database stays held.

    The in-flight apply keeps ``db-a``. The apply for ``db-b`` verifies one
    create. ``db-a`` is still held by the first plan afterward.
    """
    side = CountingPort()
    side_plan = _plan("x_side")
    with _apply_holding("db-a", "x_hold", mode=mode) as flight:
        result = apply(side_plan, mode=mode, port=side, odoo_database="db-b")
        assert result["status"] == "VERIFIED"
        assert result["applied_count"] == 1
        assert side.names() == ["x_side"]
        assert side.writes == []
        assert flight.port.names() == ["x_hold"]
        assert _APPLY_LOCK.holder("db-a") == changeset_fingerprint(flight.plan)
        assert _APPLY_LOCK.holder("db-b") is None
    _assert_holder_finished(flight)
    side_fp = changeset_fingerprint(side_plan)
    assert any(
        entry.get("kind") == "VERIFIED" and entry.get("plan_hash") == side_fp
        for entry in get_journal()
    )


@pytest.mark.parametrize("mode", ["T", "C"])
def test_release_allows_the_next_apply(mode: str) -> None:
    """After the holder finishes, the apply that was blocked writes once.

    While the lock is held the second port stays empty. After the holder
    releases it, the same plan verifies and that port records one create.
    """
    nxt = CountingPort()
    nxt_plan = _plan("x_after")
    with _apply_holding("db-a", "x_hold", mode=mode) as flight:
        blocked = apply(nxt_plan, mode=mode, port=nxt, odoo_database="db-a")
        _assert_busy(blocked, "db-a", nxt)
    _assert_holder_finished(flight)
    assert _APPLY_LOCK.holder("db-a") is None
    released = apply(nxt_plan, mode=mode, port=nxt, odoo_database="db-a")
    assert released["status"] == "VERIFIED"
    assert released["applied_count"] == 1
    assert nxt.names() == ["x_after"]
    assert nxt.writes == []
    assert flight.port.names() == ["x_hold"]
    assert _APPLY_LOCK.holder("db-a") is None


def test_declared_lock_table_is_not_written_by_apply() -> None:
    """Revision ``s9t0u1v2w3x4`` declares ``apply_database_lock``.

    This function reads that file. It does not run Alembic upgrade. The apply
    uses the in-memory lock and leaves no lock row on the result or the journal.
    """
    text = _MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "s9t0u1v2w3x4"' in text
    assert '"apply_database_lock"' in text
    assert "op.create_table" in text
    port = CountingPort()
    result = apply(_plan("x_once"), mode="T", port=port, odoo_database="db-once")
    assert result["status"] == "VERIFIED"
    assert result["applied_count"] == 1
    assert port.names() == ["x_once"]
    assert _APPLY_LOCK.holder("db-once") is None
    assert "apply_database_lock" not in result
    assert all("apply_database_lock" not in entry for entry in get_journal())
