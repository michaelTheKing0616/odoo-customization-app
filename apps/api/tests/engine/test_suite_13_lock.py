"""T8-S13 / 5C-04. One apply per Odoo database (queued, no interleave).

``apply`` uses the in-process ``DatabaseApplyLock`` when ``odoo_database``
is set. A second apply for that database waits until the first releases
the lock; port calls for the two change-sets do not interleave. An apply
for a different database may run concurrently. After the holder releases
the lock (or a recovery reclaim), the next apply for that database runs.

The lock is in memory. Alembic revision ``s9t0u1v2w3x4`` declares the
table ``apply_database_lock``. That revision is not applied. This suite
does not insert a lock row.
"""

from __future__ import annotations

import socket
import threading
import time
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
        self._log: list[str] = []
        self._guard = threading.Lock()

    def names(self) -> list[str]:
        """Field names recorded by ``create``, in call order."""
        return [str(values.get("name")) for _model, values in self.created]

    def call_log(self) -> list[str]:
        with self._guard:
            return list(self._log)

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values``. Does not open a socket.
        """
        with self._guard:
            self.created.append((model, dict(values)))
            self._log.append(f"create:{values.get('name')}")
            return len(self.created)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: appends copies. Does not open a socket.
        """
        with self._guard:
            self.writes.append((model, list(ids), dict(values)))
            self._log.append(f"write:{model}")


class HoldingPort(CountingPort):
    """Counting port that pauses inside ``create`` for selected field names."""

    def __init__(self) -> None:
        super().__init__()
        self.holding = threading.Event()
        self.may_finish = threading.Event()
        self._hold_names: set[str] = set()

    def hold_on(self, field_name: str) -> None:
        """Pause the next create of this field until ``may_finish`` is set."""
        self._hold_names.add(field_name)

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create, then wait when this field is held."""
        created_id = super().create(model, values)
        name = str(values.get("name") or "")
        if name in self._hold_names:
            self.holding.set()
            if not self.may_finish.wait(timeout=_HOLD_WAIT_SECONDS):
                raise TimeoutError("holding apply was not released")
        return created_id


class SlowSharedPort(CountingPort):
    """Shared port that sleeps briefly on each create so order is observable."""

    def __init__(self, delay: float = 0.05) -> None:
        super().__init__()
        self.delay = delay

    def create(self, model: str, values: dict[str, Any]) -> int:
        time.sleep(self.delay)
        return super().create(model, values)


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
    """One ``field.create`` on ``x_test.model``."""
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": name, "field_type": "char"},
    }


def _plan(name: str) -> list[dict[str, Any]]:
    """A one-op change-set."""
    return [_field(name)]


def _plan_two(a: str, b: str) -> list[dict[str, Any]]:
    return [_field(a), _field(b)]


def _assert_holder_finished(flight: _InFlight) -> None:
    """The in-flight apply finished after releasing its database."""
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
    """Start one apply and yield while that call holds the database lock."""
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
def test_second_apply_same_database_queues_without_interleave(mode: str) -> None:
    """Two applies on one database: second waits; port log is not interleaved.

    Each change-set has two ops. A shared slow port records creates. The
    first change-set's two creates finish before the second change-set's
    first create. Both applies verify.
    """
    port = SlowSharedPort(delay=0.04)
    first_plan = _plan_two("x_a1", "x_a2")
    second_plan = _plan_two("x_b1", "x_b2")
    results: dict[str, dict[str, Any]] = {}
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _run(label: str, plan: list[dict[str, Any]]) -> None:
        try:
            barrier.wait(timeout=2.0)
            results[label] = apply(plan, mode=mode, port=port, odoo_database="db-a")
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_run, args=("first", first_plan))
    t2 = threading.Thread(target=_run, args=("second", second_plan))
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)
    assert errors == []
    assert not t1.is_alive() and not t2.is_alive()
    assert results["first"]["status"] == "VERIFIED"
    assert results["second"]["status"] == "VERIFIED"
    log = port.call_log()
    assert log.count("create:x_a1") == 1
    assert log.count("create:x_a2") == 1
    assert log.count("create:x_b1") == 1
    assert log.count("create:x_b2") == 1
    # One change-set fully before the other (no interleave).
    a_block = ["create:x_a1", "create:x_a2"]
    b_block = ["create:x_b1", "create:x_b2"]
    assert log == a_block + b_block or log == b_block + a_block
    assert _APPLY_LOCK.holder("db-a") is None


@pytest.mark.parametrize("mode", ["T", "C"])
def test_different_database_may_apply_while_lock_is_held(mode: str) -> None:
    """An apply for another database writes while the first database stays held."""
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
def test_queued_apply_runs_after_holder_releases(mode: str) -> None:
    """A second apply started while the lock is held completes after release."""
    nxt = CountingPort()
    nxt_plan = _plan("x_after")
    queued: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def _queued() -> None:
        try:
            queued.append(apply(nxt_plan, mode=mode, port=nxt, odoo_database="db-a"))
        except BaseException as exc:
            errors.append(exc)

    with _apply_holding("db-a", "x_hold", mode=mode) as flight:
        thread = threading.Thread(target=_queued)
        thread.start()
        # Queued apply must not have written yet while holder is mid-port.
        time.sleep(0.05)
        assert nxt.created == []
        assert _APPLY_LOCK.holder("db-a") == changeset_fingerprint(flight.plan)
    thread.join(timeout=_HOLD_WAIT_SECONDS)
    assert errors == []
    assert not thread.is_alive()
    _assert_holder_finished(flight)
    assert len(queued) == 1
    assert queued[0]["status"] == "VERIFIED"
    assert queued[0]["applied_count"] == 1
    assert nxt.names() == ["x_after"]
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
