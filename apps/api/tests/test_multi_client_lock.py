"""5C-04 Multi-client lock: per-database queue, heartbeat reclaim, release on raise."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.changeset.executor import apply, reset_journal
from app.changeset.recovery import (
    HEARTBEAT_INTERVAL,
    STALE_DETECT_SLO,
    STALE_HEARTBEAT,
    DatabaseApplyLock,
    recover_stale_applying,
)

pytestmark = pytest.mark.no_app_db

_NOW = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_journal()
    yield
    reset_journal()


def _field(name: str) -> dict[str, Any]:
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": name, "field_type": "char"},
    }


def _plan(*names: str) -> list[dict[str, Any]]:
    return [_field(name) for name in names]


class LoggingPort:
    """Thread-safe port that records create call order; optional per-name delay."""

    def __init__(self, *, delay: float = 0.0, hold_names: set[str] | None = None) -> None:
        self.delay = delay
        self.hold_names = set(hold_names or ())
        self.holding = threading.Event()
        self.may_finish = threading.Event()
        self._log: list[str] = []
        self._guard = threading.Lock()

    def call_log(self) -> list[str]:
        with self._guard:
            return list(self._log)

    def create(self, model: str, values: dict[str, Any]) -> int:
        name = str(values.get("name") or "")
        if self.delay:
            time.sleep(self.delay)
        if name in self.hold_names:
            self.holding.set()
            if not self.may_finish.wait(timeout=5.0):
                raise TimeoutError("port hold not released")
        with self._guard:
            self._log.append(name)
            return len(self._log)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        return None


def test_same_database_two_threads_no_interleave() -> None:
    """Two threads, same database, slow fake port: one change-set fully before the other."""
    lock = DatabaseApplyLock(
        heartbeat_interval=timedelta(milliseconds=20),
        stale_after=timedelta(seconds=30),
        wait_timeout=timedelta(seconds=5),
    )
    port = LoggingPort(delay=0.04)
    plan_a = _plan("x_a1", "x_a2")
    plan_b = _plan("x_b1", "x_b2")
    results: dict[str, dict[str, Any]] = {}
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _run(label: str, plan: list[dict[str, Any]]) -> None:
        try:
            barrier.wait(timeout=2.0)
            results[label] = apply(
                plan,
                mode="T",
                port=port,
                odoo_database="client-db",
                apply_lock=lock,
            )
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_run, args=("a", plan_a))
    t2 = threading.Thread(target=_run, args=("b", plan_b))
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)
    assert errors == []
    assert results["a"]["status"] == "VERIFIED"
    assert results["b"]["status"] == "VERIFIED"
    log = port.call_log()
    assert log == ["x_a1", "x_a2", "x_b1", "x_b2"] or log == ["x_b1", "x_b2", "x_a1", "x_a2"]
    assert lock.holder("client-db") is None


def test_different_databases_run_concurrently() -> None:
    """Two threads on different databases overlap in time (not serialized)."""
    lock = DatabaseApplyLock(
        heartbeat_interval=timedelta(milliseconds=20),
        stale_after=timedelta(seconds=30),
        wait_timeout=timedelta(seconds=5),
    )
    started = threading.Event()
    both_inside = threading.Event()
    release = threading.Event()
    inside = 0
    inside_guard = threading.Lock()

    class GatePort(LoggingPort):
        def create(self, model: str, values: dict[str, Any]) -> int:
            nonlocal inside
            with inside_guard:
                inside += 1
                if inside >= 2:
                    both_inside.set()
            started.set()
            if not release.wait(timeout=2.0):
                raise TimeoutError("concurrent gate not released")
            return super().create(model, values)

    port_a = GatePort()
    port_b = GatePort()
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def _run(database: str, port: GatePort, name: str) -> None:
        try:
            results.append(
                apply(
                    _plan(name),
                    mode="T",
                    port=port,
                    odoo_database=database,
                    apply_lock=lock,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_run, args=("db-1", port_a, "x_one"))
    t2 = threading.Thread(target=_run, args=("db-2", port_b, "x_two"))
    t1.start()
    t2.start()
    assert both_inside.wait(timeout=2.0), "different databases did not overlap"
    release.set()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)
    assert errors == []
    assert len(results) == 2
    assert {row["status"] for row in results} == {"VERIFIED"}
    assert lock.holder("db-1") is None
    assert lock.holder("db-2") is None


def test_crashed_holder_reclaimed_then_queued_apply_proceeds() -> None:
    """Holder stops heartbeating; recovery reclaims; queued apply proceeds."""
    stale_after = timedelta(milliseconds=80)
    lock = DatabaseApplyLock(
        heartbeat_interval=timedelta(milliseconds=20),
        stale_after=stale_after,
        wait_timeout=timedelta(seconds=2),
    )
    # Simulate a killed holder: acquire without a heartbeat thread, then age out.
    assert lock.acquire("crash-db", "dead-run", now=_NOW, wait=False) is True
    # Freeze heartbeat in the past so reclaim sees it as stale.
    with lock._cond:
        lock._held["crash-db"]["heartbeat"] = _NOW - stale_after - timedelta(milliseconds=10)

    assert HEARTBEAT_INTERVAL <= timedelta(seconds=5)
    assert STALE_HEARTBEAT < STALE_DETECT_SLO

    port = LoggingPort()
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def _queued() -> None:
        try:
            results.append(
                apply(
                    _plan("x_after_crash"),
                    mode="T",
                    port=port,
                    odoo_database="crash-db",
                    apply_lock=lock,
                    lock_wait=2.0,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=_queued)
    thread.start()
    # Recovery job: reclaim stale lock (and journal path with empty journal).
    time.sleep(0.05)
    reclaimed = lock.reclaim_stale(now=datetime.now(timezone.utc))
    assert "crash-db" in reclaimed or lock.holder("crash-db") is None
    # Also exercise the journal recovery entry point with injectable stale.
    recover_stale_applying([], now=datetime.now(timezone.utc), locks=lock, stale_after=stale_after)
    thread.join(timeout=3.0)
    assert errors == []
    assert not thread.is_alive()
    assert len(results) == 1
    assert results[0]["status"] == "VERIFIED"
    assert port.call_log() == ["x_after_crash"]
    assert lock.holder("crash-db") is None


def test_lock_released_when_apply_raises() -> None:
    """Lock is released in finally when the port raises mid-apply."""
    lock = DatabaseApplyLock(
        heartbeat_interval=timedelta(milliseconds=20),
        stale_after=timedelta(seconds=30),
        wait_timeout=timedelta(seconds=2),
    )

    class BoomPort(LoggingPort):
        def create(self, model: str, values: dict[str, Any]) -> int:
            raise RuntimeError("port boom")

    port = BoomPort()
    with pytest.raises(RuntimeError, match="port boom"):
        apply(
            _plan("x_boom"),
            mode="T",
            port=port,
            odoo_database="raise-db",
            apply_lock=lock,
        )
    assert lock.holder("raise-db") is None

    # A following apply can acquire and succeed.
    ok = apply(
        _plan("x_ok"),
        mode="T",
        port=LoggingPort(),
        odoo_database="raise-db",
        apply_lock=lock,
    )
    assert ok["status"] == "VERIFIED"
    assert lock.holder("raise-db") is None


def test_lock_wait_exceeded_returns_clear_error() -> None:
    """Bounded wait returns lock_wait_exceeded when the holder never releases."""
    lock = DatabaseApplyLock(
        heartbeat_interval=timedelta(milliseconds=10),
        stale_after=timedelta(seconds=60),
        wait_timeout=timedelta(milliseconds=50),
    )
    assert lock.acquire("busy-db", "holder", now=_NOW, wait=False) is True
    # Keep heartbeat fresh so reclaim does not free it during the short wait.
    lock.heartbeat("busy-db", "holder", now=datetime.now(timezone.utc))
    result = apply(
        _plan("x_wait"),
        mode="T",
        port=LoggingPort(),
        odoo_database="busy-db",
        apply_lock=lock,
        lock_wait=0.05,
    )
    assert result["status"] == "NEEDS_HUMAN"
    assert result["report"]["reason"] == "lock_wait_exceeded"
    assert result["applied_count"] == 0
    assert lock.holder("busy-db") == "holder"
    lock.release("busy-db", "holder")
