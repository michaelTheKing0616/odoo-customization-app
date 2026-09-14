"""Unit tests for LLM provider routing, thinking trace strip, and settings matrix."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.llm_provider import (
    FORMAT_SCHEMA_FIELDS,
    AnthropicProvider,
    GeminiProvider,
    LLMError,
    OllamaProvider,
    OpenAICompatibleProvider,
    OPENAI_DEFAULT_BASE,
    _is_unavailable_error,
    _kwargs_for_fallback,
    _ollama_local_model,
    generate_json_with_timeout_retry,
    get_llm_provider,
    probe_ollama_capabilities,
    resolve_bulk_model,
    resolve_provider_mode,
    resolve_reasoning_model,
    resolve_thinking_enabled,
    strip_thinking_trace,
)
from app.settings import settings

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _tier_follows_ai_assist(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI defaults AI_LLM_TIER_FAST=gemini; these tests assert AI_ASSIST routing."""
    monkeypatch.setattr(settings, "ai_llm_tier_fast", "auto")
    monkeypatch.setattr(settings, "ai_llm_tier_refine", "auto")


def test_strip_thinking_trace_discards_before_marker() -> None:
    raw = "Let me think...\n---JSON---\n{\"ok\": true}"
    assert strip_thinking_trace(raw) == '{"ok": true}'


def test_strip_thinking_trace_passthrough_without_marker() -> None:
    assert strip_thinking_trace('{"a":1}') == '{"a":1}'


def test_resolve_thinking_matrix() -> None:
    assert resolve_thinking_enabled(reasoning=False, model_supports_think=True) is False
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=False) is False

    settings.ai_thinking = "off"
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=True) is False

    settings.ai_thinking = "on"
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=True) is True
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=False) is False

    settings.ai_thinking = "auto"
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=True) is True
    assert resolve_thinking_enabled(reasoning=True, model_supports_think=False) is False


def test_model_ladder_fallback_and_override() -> None:
    settings.ai_assist = "ollama"
    settings.ollama_model = "legacy:7b"
    settings.ai_model_bulk = ""
    settings.ai_model_reasoning = ""
    assert resolve_bulk_model() == "legacy:7b"
    assert resolve_reasoning_model() == "legacy:7b"

    settings.ai_model_bulk = "qwen3:8b"
    settings.ai_model_reasoning = "qwen3:14b"
    assert resolve_bulk_model() == "qwen3:8b"
    assert resolve_reasoning_model() == "qwen3:14b"


class _FakeHTTP:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def urlopen(self, req, timeout=120.0):  # noqa: ANN001, ARG002
        payload = None
        if req.data:
            payload = json.loads(req.data.decode("utf-8"))
            self.requests.append(payload)
        body = self.responses.pop(0)
        return _Resp(body)


class _Resp:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = json.dumps(data).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):  # noqa: ANN002
        return False


def test_ollama_routes_bulk_vs_reasoning_and_strips_cot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeHTTP(
        [
            {"response": '{"name":"x"}'},
            {"response": '{"name":"y"}'},
        ]
    )
    monkeypatch.setattr("app.llm_provider.request.urlopen", fake.urlopen)
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {
            "think_supported": False,
            "schema_format_supported": True,
            "think_param": "think",
        },
    )

    provider = OllamaProvider(base_url="http://fake", model="qwen2.5:7b")
    settings.ai_model_bulk = "bulk:8b"
    settings.ai_model_reasoning = "reason:14b"
    settings.ai_thinking = "auto"

    bulk_out = provider.generate_json("list entities", system="sys", reasoning=False)
    assert bulk_out == '{"name":"x"}'
    assert fake.requests[-1]["model"] == "bulk:8b"
    assert "think" not in fake.requests[-1]
    assert fake.requests[-1]["options"]["temperature"] == 0.2
    assert fake.requests[-1]["options"]["temperature"] == 0.2

    cot_out = provider.generate_json("critique", system="sys", reasoning=True, temperature=0.15)
    assert cot_out == '{"name":"y"}'
    assert fake.requests[-1]["model"] == "reason:14b"
    assert fake.requests[-1]["options"]["temperature"] == 0.15


def test_ollama_native_think_param_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeHTTP([{"response": '{"ok":true}', "thinking": "hidden trace"}])
    monkeypatch.setattr("app.llm_provider.request.urlopen", fake.urlopen)
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {
            "think_supported": True,
            "schema_format_supported": False,
            "think_param": "think",
        },
    )
    provider = OllamaProvider(base_url="http://fake", model="qwen3:14b")
    settings.ai_thinking = "auto"
    out = provider.generate_json("plan", reasoning=True)
    assert out == '{"ok":true}'
    assert fake.requests[-1].get("think") is True


def test_ollama_schema_format_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeHTTP([{"response": '[{"name":"x_field","ttype":"char"}]'}])
    monkeypatch.setattr("app.llm_provider.request.urlopen", fake.urlopen)
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {
            "think_supported": False,
            "schema_format_supported": True,
        },
    )
    provider = OllamaProvider(base_url="http://fake", model="bulk:8b")
    provider.generate_json("fields", reasoning=False, format_schema=FORMAT_SCHEMA_FIELDS)
    assert fake.requests[-1]["format"] == FORMAT_SCHEMA_FIELDS


def test_openai_compatible_manual_cot_and_reasoning_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _urlopen(req, timeout=120.0):  # noqa: ANN001, ARG002
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp(
            {
                "choices": [
                    {"message": {"content": '---JSON---\n{"models":[]}'}}
                ]
            }
        )

    monkeypatch.setattr("app.llm_provider.request.urlopen", _urlopen)
    settings.openai_compatible_base_url = "http://fake/v1"
    settings.ai_model_bulk = "bulk"
    settings.ai_model_reasoning = "reason"
    provider = OpenAICompatibleProvider()
    out = provider.generate_json("repair", reasoning=True)
    assert out == '{"models":[]}'
    assert captured["payload"]["model"] == "reason"
    assert captured["payload"].get("reasoning_effort") == "medium"
    assert "---JSON---" in captured["payload"]["messages"][-1]["content"]


def test_probe_ollama_capabilities_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import llm_provider as lp

    lp._caps_cache.clear()
    calls = {"n": 0}

    def _fake_http(url, payload=None, *, method="GET", timeout_s=5.0, headers=None):  # noqa: ARG001
        calls["n"] += 1
        if url.endswith("/api/version"):
            return {"version": "0.31.1"}
        if payload and payload.get("think"):
            return {"error": "no thinking"}
        return {"response": '{"name":"ok"}'}

    monkeypatch.setattr(lp, "_http_json", _fake_http)
    first = probe_ollama_capabilities(base_url="http://x", model="m", force_refresh=True)
    second = probe_ollama_capabilities(base_url="http://x", model="m")
    assert first["schema_format_supported"] is True
    assert first["think_supported"] is False
    assert second == first
    assert calls["n"] == 3  # version + think + schema once


def test_auto_prefers_anthropic_then_openai_then_gemini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_assist", "auto")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "openai_api_key", "sk-openai-test")
    monkeypatch.setattr(settings, "gemini_api_key", "gem-test")
    monkeypatch.setattr(settings, "google_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "")
    assert resolve_provider_mode() == "anthropic"
    assert get_llm_provider().name == "anthropic"

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert resolve_provider_mode() == "openai"
    provider = get_llm_provider()
    assert provider.name == "openai"
    assert provider.base_url == OPENAI_DEFAULT_BASE

    monkeypatch.setattr(settings, "openai_api_key", "")
    assert resolve_provider_mode() == "gemini"
    assert get_llm_provider().name == "gemini"

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "google_api_key", "")
    assert resolve_provider_mode() == "off"
    assert get_llm_provider() is None


def test_claude_alias_and_cloud_skips_ollama_shaped_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_assist", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "anthropic_model", "claude-sonnet-4-5")
    monkeypatch.setattr(settings, "ai_model_bulk", "qwen3:8b")
    monkeypatch.setattr(settings, "ai_model_reasoning", "qwen3:14b")
    assert resolve_provider_mode() == "anthropic"
    assert resolve_bulk_model() == "claude-sonnet-4-5"
    assert resolve_reasoning_model() == "claude-sonnet-4-5"

    monkeypatch.setattr(settings, "ai_assist", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_model", "gpt-4.1")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "https://api.x.ai/v1")
    assert resolve_bulk_model() == "gpt-4.1"
    native = get_llm_provider()
    assert native is not None
    assert native.name == "openai"
    assert native.base_url == OPENAI_DEFAULT_BASE


def test_anthropic_generate_json_extracts_text_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _urlopen(req, timeout=120.0):  # noqa: ANN001, ARG002
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp(
            {
                "content": [
                    {"type": "thinking", "thinking": "hidden"},
                    {"type": "text", "text": '{"models":[]}'},
                ]
            }
        )

    monkeypatch.setattr("app.llm_provider.request.urlopen", _urlopen)
    monkeypatch.setattr(settings, "ai_assist", "claude")
    monkeypatch.setattr(settings, "ai_model_bulk", "qwen3:8b")
    monkeypatch.setattr(settings, "ai_model_reasoning", "qwen3:14b")
    out = AnthropicProvider(api_key="sk-ant-test").generate_json("repair", reasoning=False)
    assert out == '{"models":[]}'
    assert captured["url"].endswith("/v1/messages")
    assert captured["payload"]["model"] == "claude-sonnet-4-5"


def test_gemini_generate_json_extracts_candidate_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _urlopen(req, timeout=120.0):  # noqa: ANN001, ARG002
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return _Resp(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '{"ok":'},
                                {"text": " true}"},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.llm_provider.request.urlopen", _urlopen)
    monkeypatch.setattr(settings, "gemini_model", "gemini-2.5-flash")
    out = GeminiProvider(api_key="gem-test").generate_json("hello", reasoning=False)
    assert out == '{"ok": true}'
    assert "generateContent" in captured["url"]
    assert "key=" not in captured["url"]
    header_vals = " ".join(f"{k}:{v}" for k, v in captured["headers"].items())
    assert "gem-test" in header_vals


def test_get_llm_provider_openai_uses_api_openai_com(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_assist", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "")
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    monkeypatch.setattr(settings, "ai_llm_tier_fast", "auto")
    provider = get_llm_provider()
    assert provider is not None
    assert provider.name == "openai"
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.api_key == "sk-test"


def test_cloud_mode_without_key_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_assist", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    assert get_llm_provider() is None
    monkeypatch.setattr(settings, "ai_assist", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert get_llm_provider() is None
    monkeypatch.setattr(settings, "ai_assist", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "google_api_key", "")
    assert get_llm_provider() is None


def test_ollama_local_model_ignores_gemini_bulk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_assist", "gemini")
    monkeypatch.setattr(settings, "ai_model_bulk", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "ai_model_reasoning", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "ollama_model", "qwen3:8b")
    assert _ollama_local_model(None) == "qwen3:8b"
    assert _ollama_local_model("gemini-2.5-flash") == "qwen3:8b"
    provider = OllamaProvider(base_url="http://fake")
    assert provider.model == "qwen3:8b"

    fake = _FakeHTTP([{"response": '{"ok":true}'}])
    monkeypatch.setattr("app.llm_provider.request.urlopen", fake.urlopen)
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **kwargs: {
            "think_supported": False,
            "schema_format_supported": True,
        },
    )
    provider.generate_json("list entities")
    assert fake.requests[-1]["model"] == "qwen3:8b"

    kwargs = _kwargs_for_fallback(
        provider,
        {"prompt": "x", "model": "gemini-2.5-flash", "system": None},
    )
    assert kwargs["model"] == "qwen3:8b"


def test_ollama_http_404_is_not_unavailable() -> None:
    exc = LLMError("Ollama HTTP 404: Not Found", status_code=404)
    assert not _is_unavailable_error(exc)


def test_ollama_timeout_retry_uses_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_assist", "gemini")
    monkeypatch.setattr(settings, "ai_model_bulk", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "ollama_model", "qwen3:8b")
    models: list[str | None] = []

    class _Ollama(OllamaProvider):
        def generate_json(self, prompt: str, **kwargs: object) -> str:  # noqa: ARG002
            models.append(kwargs.get("model") if isinstance(kwargs.get("model"), str) else None)  # type: ignore[arg-type]
            if len(models) == 1:
                raise LLMError("Ollama request timed out")
            return '{"ok": true}'

    raw = generate_json_with_timeout_retry(_Ollama(base_url="http://fake"), "hi")
    assert raw == '{"ok": true}'
    assert models[1] == "qwen3:8b"


