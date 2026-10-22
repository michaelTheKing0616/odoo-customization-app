"""B0-DBGUARD: a bad database target fails before getaddrinfo or create_connection."""

from __future__ import annotations

import socket

import pytest

import tests.conftest as harness

pytestmark = pytest.mark.no_app_db

_REFUSED = (
    ("postgresql+psycopg://u:p@10.0.0.8:5432/odoo_custom", "does not start with ingenium_"),
    ("postgresql+psycopg://u:p@127.0.0.1:5433/odoo_custom", "does not start with ingenium_"),
    ("postgresql+psycopg://u:p@127.0.0.1:5433/ingenium", "does not start with ingenium_"),
    ("postgresql+psycopg://u:p@10.0.0.8:5432/ingenium_b0_dbguard", "not loopback"),
    ("postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_x?host=10.0.0.8", "not loopback"),
    ("postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_x?hostaddr=10.0.0.8", "not loopback"),
    (
        "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_x?dbname=odoo_custom",
        "does not start with ingenium_",
    ),
    (
        "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_x?host=127.0.0.1&hostaddr=10.0.0.8",
        "not loopback",
    ),
    (
        "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_x?host=10.0.0.8&hostaddr=127.0.0.1",
        "not loopback",
    ),
)

_ALLOWED = (
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_dbguard",
    "postgresql+psycopg://u:p@localhost:5433/ingenium_b0_dbguard",
    "postgresql+psycopg://u:p@[::1]:5433/ingenium_b0_dbguard",
    (
        "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_dbguard"
        "?host=127.0.0.1&dbname=ingenium_b0_dbguard"
    ),
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_dbguard?host=localhost&hostaddr=::1",
    "postgresql+psycopg://u:p@[::1]:5433/ingenium_b0_dbguard?hostaddr=127.0.0.1",
)


def _seal_socket(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace getaddrinfo and create_connection so a real socket call fails the test."""
    calls: list[str] = []

    def _getaddrinfo(*_a: object, **_k: object) -> None:
        calls.append("getaddrinfo")
        raise AssertionError("getaddrinfo")

    def _create_connection(*_a: object, **_k: object) -> None:
        calls.append("create_connection")
        raise AssertionError("create_connection")

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", _create_connection)
    monkeypatch.setattr(harness, "_real_getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(harness, "_real_create_connection", _create_connection)
    return calls


@pytest.mark.parametrize(("url", "reason"), _REFUSED)
def test_ac1_refuses_before_socket(url: str, reason: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _seal_socket(monkeypatch)
    with pytest.raises(ConnectionRefusedError, match=reason):
        harness.guard_db_target(url)
    assert calls == []


@pytest.mark.parametrize("url", _ALLOWED)
def test_ac1_ingenium_loopback_is_not_refused(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _seal_socket(monkeypatch)
    assert harness.guard_db_target(url) is None
    assert calls == []
