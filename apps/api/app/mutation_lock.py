"""TRUST-5 per-connection mutation lock — one apply/bulk run at a time."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionMutationBusy(Exception):
    connection_id: str
    holder: str

    def __str__(self) -> str:
        return (
            f"Connection {self.connection_id!r} already has mutation in progress "
            f"({self.holder!r})"
        )


_meta = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_holders: dict[str, str] = {}


def mutation_holder(connection_id: str) -> str | None:
    key = connection_id.strip()
    with _meta:
        return _holders.get(key)


def try_acquire_connection_mutation_lock(connection_id: str, operation: str) -> bool:
    key = connection_id.strip()
    if not key:
        raise ValueError("connection_id required")
    op = (operation or "mutation").strip() or "mutation"
    with _meta:
        if key in _holders:
            return False
        lock = _locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        return False
    with _meta:
        if key in _holders:
            lock.release()
            return False
        _holders[key] = op
    return True


def release_connection_mutation_lock(connection_id: str) -> None:
    key = connection_id.strip()
    with _meta:
        _holders.pop(key, None)
    lock = _locks.get(key)
    if lock is not None and lock.locked():
        lock.release()


@contextmanager
def connection_mutation_lock(connection_id: str, operation: str = "mutation"):
    if not try_acquire_connection_mutation_lock(connection_id, operation):
        holder = mutation_holder(connection_id) or "unknown"
        raise ConnectionMutationBusy(connection_id.strip(), holder)
    try:
        yield
    finally:
        release_connection_mutation_lock(connection_id)


def reset_mutation_locks_for_tests() -> None:
    """Clear lock state between tests."""
    with _meta:
        _holders.clear()
    for lock in _locks.values():
        if lock.locked():
            try:
                lock.release()
            except RuntimeError:
                pass
