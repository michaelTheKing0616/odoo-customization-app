"""TRUST-6 parametrized execution of settings-gated code paths."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.ai_pipeline import run_staged_pipeline  # noqa: E402
from app.ai_self_consistency import self_consistency_enabled  # noqa: E402
from app.db import init_db  # noqa: E402
from app.llm_provider import llm_routing_status, resolve_thinking_enabled  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation  # noqa: E402
from app.write_mode_service import normalize_write_mode  # noqa: E402
from odoo_client.write_mode import is_rpc_blocked_in_observer  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    "auth_mode,headers,expect_status",
    [
        ("off", {}, 200),
    ],
)
def test_auth_mode_matrix_status_endpoint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    auth_mode: str,
    headers: dict[str, str],
    expect_status: int,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", auth_mode)
    monkeypatch.setattr(settings, "app_api_key", "matrix-test-key")
    res = client.get("/api/auth/status", headers=headers)
    assert res.status_code == expect_status


def test_auth_mode_matrix_api_key_denied_without_bearer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", "matrix-test-key")
    res = client.get("/api/connections")
    assert res.status_code == 401


@pytest.mark.parametrize(
    "write_mode,method,blocked",
    [
        ("observer", "write", True),
        ("observer", "search_read", False),
        ("standard", "write", False),
        ("production", "unlink", False),
    ],
)
def test_write_mode_rpc_matrix(write_mode: str, method: str, blocked: bool) -> None:
    assert normalize_write_mode(write_mode) == write_mode
    assert is_rpc_blocked_in_observer(write_mode, method) is blocked


@pytest.mark.parametrize("thinking", ["off", "on", "auto"])
def test_ai_thinking_mode_matrix(thinking: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_thinking", thinking)
    enabled = resolve_thinking_enabled(reasoning=True, model_supports_think=True)
    if thinking == "off":
        assert enabled is False
    elif thinking == "on":
        assert enabled is True
    else:
        assert enabled is True


@pytest.mark.parametrize("enabled", ["off", "on"])
def test_ai_self_consistency_matrix(enabled: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_self_consistency", enabled)
    assert self_consistency_enabled() is (enabled == "on")


def test_schema_format_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_assist", "ollama")
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {"schema_format_supported": True, "think_supported": False},
    )
    assert llm_routing_status()["schema_in_format_active"] is True
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {"schema_format_supported": False, "think_supported": False},
    )
    assert llm_routing_status()["schema_in_format_active"] is False


def test_staged_pipeline_mode_executes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.protected_modules import build_manifest
    from tests.test_ai_staged_pipeline import _RecordingProvider

    monkeypatch.setattr(settings, "ai_pipeline_mode", "staged")
    monkeypatch.setattr("app.ai_pipeline.retrieve_domain_pack", lambda *a, **k: None)
    provider = _RecordingProvider()
    draft, trace, warnings = run_staged_pipeline(
        "matrix smoke",
        provider=provider,
        protected_manifest=build_manifest(["account"], "19.0"),
    )
    assert draft.get("_pipeline", {}).get("mode") == "staged"
    assert trace
    assert isinstance(warnings, list)
    assert provider.calls


def test_auth_mode_matrix_api_key_allows_with_bearer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", "matrix-test-key")
    res = client.get(
        "/api/connections",
        headers={"Authorization": "Bearer matrix-test-key"},
    )
    assert res.status_code == 200


def test_confirm_phrase_gate_matrix() -> None:
    with pytest.raises(ConfirmationRequired):
        require_advanced_confirmation(
            confirm_advanced=False,
            confirm_phrase=None,
            warning="test",
            risks=["r1"],
        )
    require_advanced_confirmation(
        confirm_advanced=True,
        confirm_phrase=CONFIRM_PHRASE,
        warning="test",
        risks=["r1"],
    )
