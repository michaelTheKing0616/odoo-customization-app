"""Unit tests for sandbox extra-module settings and helpers (no Docker)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.settings import Settings
from app.sandbox import (
    _ensure_modules_installed,
    _resolve_extra_modules,
    resolve_sandbox_major,
    sandbox_image_for_major,
)


def test_resolve_sandbox_major_defaults_and_bounds() -> None:
    assert resolve_sandbox_major(None) == 19
    assert resolve_sandbox_major(18) == 18
    assert resolve_sandbox_major(16) == 16
    with pytest.raises(ValueError, match="unsupported"):
        resolve_sandbox_major(15)


def test_sandbox_image_for_major() -> None:
    assert sandbox_image_for_major(19) == "odoo:19"
    assert sandbox_image_for_major(16) == "odoo:16"


def test_settings_parse_sandbox_extra_modules_empty() -> None:
    s = Settings(sandbox_extra_modules="")
    assert s.sandbox_extra_module_list() == []


def test_settings_parse_sandbox_extra_modules_csv() -> None:
    s = Settings(sandbox_extra_modules="sale, account,  contacts")
    assert s.sandbox_extra_module_list() == ["sale", "account", "contacts"]


def test_resolve_extra_modules_explicit_overrides_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SANDBOX_EXTRA_MODULES", "sale,account")
    # Explicit list wins (including empty list meaning "install nothing")
    assert _resolve_extra_modules(["crm"]) == ["crm"]
    assert _resolve_extra_modules([]) == []


def test_resolve_extra_modules_none_reads_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import settings as settings_mod

    monkeypatch.setattr(
        settings_mod.settings, "sandbox_extra_modules", "sale,account"
    )
    assert _resolve_extra_modules(None) == ["sale", "account"]


def test_ensure_modules_installed_skips_already_installed() -> None:
    models = MagicMock()
    # update_list
    models.execute_kw.side_effect = [
        None,  # update_list
        [{"id": 10, "state": "installed"}],  # search_read sale
        [{"id": 11, "state": "uninstalled"}],  # search_read account
        None,  # button_immediate_install
        [{"state": "installed"}],  # read after install
    ]
    with patch("app.sandbox._sandbox_rpc", return_value=(2, models)):
        newly = _ensure_modules_installed(["sale", "account"], odoo_major=19)
    assert newly == ["account"]
    # update_list + 2 search_read + install + read
    assert models.execute_kw.call_count == 5


def test_ensure_modules_installed_empty() -> None:
    assert _ensure_modules_installed([]) == []
    assert _ensure_modules_installed(["", "  "]) == []
