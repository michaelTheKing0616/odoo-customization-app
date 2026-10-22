"""Pin the test host guard (handover L179 / REG-HOSTGUARD)."""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[3]
_GUARD_MARK = "# --- Host guard"
# Space around the comma pins strip(); mixed case pins lower().
_ENV_HOSTS = " Pinned-Client.Example , second-client.internal "
_CONFTESTS = (
    _REPO / "apps/api/tests/conftest.py",
    _REPO / "packages/odoo-client/tests/conftest.py",
)
_READERS = (
    ("test_odoo20_version_table.py", ("live_tip",)),
    ("test_odoo20_drift_cells.py", ("tip",)),
)
_BLOCKED_HOSTS = (
    "aonb.odoo.com",
    "aonb-only.example",
    "acme.odoo.com",
    "odoo.com",
    "client.odoo.sh",
    "odoo.sh",
    "Aonb.Example.NET",
    "acme.odoo.com.",
    "pinned-client.example",
    "second-client.internal",
)


class _Node:
    def __init__(self, filename: str, fixturenames: tuple[str, ...] = ()) -> None:
        self.path = Path(filename)
        self.fixturenames = fixturenames
        self.markers: list[object] = []

    def add_marker(self, marker: object) -> None:
        self.markers.append(marker)


def _install(conftest: Path, blocked_hosts: str) -> dict[str, Any]:
    """Execute one conftest host-guard section (below the api fixtures)."""
    text = conftest.read_text(encoding="utf-8")
    start = text.index(_GUARD_MARK)
    previous = os.environ.get("INGENIUM_BLOCKED_HOSTS")
    os.environ["INGENIUM_BLOCKED_HOSTS"] = blocked_hosts
    namespace: dict[str, Any] = {"os": os, "pytest": pytest}
    try:
        exec(compile(text[start:], str(conftest), "exec"), namespace)
    finally:
        if previous is None:
            os.environ.pop("INGENIUM_BLOCKED_HOSTS", None)
        else:
            os.environ["INGENIUM_BLOCKED_HOSTS"] = previous
    return namespace


def _refuses(host: str) -> None:
    message = re.escape(f"test host guard: refusing {host}")
    with pytest.raises(ConnectionRefusedError, match=message):
        socket.getaddrinfo(host, 443)
    with pytest.raises(ConnectionRefusedError, match=message):
        socket.create_connection((host, 443), timeout=1)


def _is_skipped(node: _Node) -> bool:
    for marker in node.markers:
        mark = getattr(marker, "mark", marker)
        if getattr(mark, "name", None) != "skip":
            continue
        reason = str(getattr(mark, "kwargs", {}).get("reason", ""))
        return "INGENIUM_LIVE_CLIENT_TESTS=1" in reason
    return False


@pytest.mark.parametrize("conftest", _CONFTESTS, ids=["api", "odoo-client"])
@pytest.mark.parametrize("host", _BLOCKED_HOSTS)
def test_socket_refuses_blocked_hosts(conftest: Path, host: str) -> None:
    namespace = _install(conftest, _ENV_HOSTS)
    assert socket.getaddrinfo is namespace["_guarded_getaddrinfo"]
    assert socket.create_connection is namespace["_guarded_create_connection"]
    _refuses(host)


@pytest.mark.parametrize("conftest", _CONFTESTS, ids=["api", "odoo-client"])
def test_socket_allows_loopback(conftest: Path) -> None:
    _install(conftest, _ENV_HOSTS)
    assert socket.getaddrinfo("127.0.0.1", 80)


@pytest.mark.parametrize("conftest", _CONFTESTS, ids=["api", "odoo-client"])
@pytest.mark.parametrize(("filename", "fixturenames"), _READERS)
def test_env_json2_readers_skip_unless_live_flag(
    conftest: Path,
    filename: str,
    fixturenames: tuple[str, ...],
) -> None:
    hook = _install(conftest, "")["pytest_collection_modifyitems"]
    previous = os.environ.pop("INGENIUM_LIVE_CLIENT_TESTS", None)
    try:
        blocked = _Node(filename, fixturenames)
        hook(None, [blocked])
        assert _is_skipped(blocked)
        os.environ["INGENIUM_LIVE_CLIENT_TESTS"] = "1"
        allowed = _Node(filename, fixturenames)
        hook(None, [allowed])
        assert not _is_skipped(allowed)
    finally:
        if previous is None:
            os.environ.pop("INGENIUM_LIVE_CLIENT_TESTS", None)
        else:
            os.environ["INGENIUM_LIVE_CLIENT_TESTS"] = previous
