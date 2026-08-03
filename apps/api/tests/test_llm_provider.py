"""Unit tests for LLM provider routing, thinking trace strip, and settings matrix."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.llm_provider import (
    FORMAT_SCHEMA_FIELDS,
    OllamaProvider,
    OpenAICompatibleProvider,
    probe_ollama_capabilities,
    resolve_bulk_model,
    resolve_reasoning_model,
    resolve_thinking_enabled,
    strip_thinking_trace,
)
from app.settings import settings


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
