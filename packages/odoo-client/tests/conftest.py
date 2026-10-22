from __future__ import annotations

import os

import pytest

# --- Host guard (Tope, Oct 20): tests never reach aonb or client Odoo hosts. ---------------
import socket as _socket

_LIVE_CLIENT_FILES = {"test_odoo20_version_table.py", "test_odoo20_drift_cells.py"}
_BLOCKED_SUFFIXES = (".odoo.com", ".odoo.sh")
_BLOCKED_EXTRA = {h.strip().lower() for h in os.environ.get("INGENIUM_BLOCKED_HOSTS", "").split(",") if h.strip()}


def _host_blocked(host: object) -> bool:
    h = str(host or "").strip().lower().rstrip(".")
    return "aonb" in h or h.endswith(_BLOCKED_SUFFIXES) or h in {"odoo.com", "odoo.sh"} or h in _BLOCKED_EXTRA


_real_getaddrinfo = _socket.getaddrinfo
_real_create_connection = _socket.create_connection


def _guarded_getaddrinfo(host, *a, **k):  # type: ignore[no-untyped-def]
    if _host_blocked(host):
        raise ConnectionRefusedError(f"test host guard: refusing {host} (aonb/client hosts are never reached from tests)")
    return _real_getaddrinfo(host, *a, **k)


def _guarded_create_connection(address, *a, **k):  # type: ignore[no-untyped-def]
    if isinstance(address, tuple) and _host_blocked(address[0]):
        raise ConnectionRefusedError(f"test host guard: refusing {address[0]}")
    return _real_create_connection(address, *a, **k)


_socket.getaddrinfo = _guarded_getaddrinfo
_socket.create_connection = _guarded_create_connection


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    if os.environ.get("INGENIUM_LIVE_CLIENT_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live client test: set INGENIUM_LIVE_CLIENT_TESTS=1 (still never reaches aonb/client hosts)")
    for item in items:
        # Only checks that use the real-host fixtures are live; offline checks in these files run.
        if item.path.name in _LIVE_CLIENT_FILES and {"live_tip", "tip"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(skip)
