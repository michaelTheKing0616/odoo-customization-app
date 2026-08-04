"""DEV-1 — code server action probe tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")

from app.code_studio_probe import probe_code_server_actions, probe_supported  # noqa: E402


def test_probe_supported_flag() -> None:
    assert probe_supported({"supported": True})
    assert not probe_supported({"supported": False})
    assert not probe_supported(None)


def test_probe_round_trip_success() -> None:
    client = MagicMock()
    client.capabilities.major = 19
    client.execute_kw.side_effect = [
        {"state": {"selection": [("code", "Code"), ("object_write", "Update")]}},
        [10],
        42,
        None,
        None,
    ]
    result = probe_code_server_actions(client)
    assert result["supported"] is True
    assert result["round_trip_ok"] is True
    assert result["state_in_selection"] is True
    unlink_calls = [c for c in client.execute_kw.call_args_list if c[0][1] == "unlink"]
    assert unlink_calls


def test_probe_cleans_up_when_run_fails() -> None:
    client = MagicMock()
    client.capabilities.major = 19

    def _kw(model, method, *args, **kwargs):
        if model == "ir.actions.server" and method == "fields_get":
            return {"state": {"selection": [("code", "Code")]}}
        if model == "ir.model" and method == "search":
            return [1]
        if model == "ir.actions.server" and method == "create":
            return 99
        if model == "ir.actions.server" and method == "run":
            raise RuntimeError("run blocked")
        if model == "ir.actions.server" and method == "unlink":
            return True
        return None

    client.execute_kw.side_effect = _kw
    result = probe_code_server_actions(client)
    assert result["supported"] is False
    assert "run blocked" in (result.get("error") or "")
    assert any(
        c[0][1] == "unlink" and c[0][2] == [[99]]
        for c in client.execute_kw.call_args_list
    )


def test_probe_fails_when_code_not_in_selection() -> None:
    client = MagicMock()
    client.capabilities.major = 19
    client.execute_kw.return_value = {
        "state": {"selection": [("object_write", "Update")]}
    }
    result = probe_code_server_actions(client)
    assert result["supported"] is False
    assert result["state_in_selection"] is False
