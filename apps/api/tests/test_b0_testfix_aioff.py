"""Pin P0-2-CL6.

AI_ASSIST off does not build a Vertex provider, so the ollama and module-generation
cases cannot pass by calling Vertex. The bulk-vs-reasoning route and CoT strip run
only when the provider mode is ollama; a cloud mode refuses an ollama-shaped ladder.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.llm_provider import (
    GeminiProvider,
    OllamaProvider,
    _looks_like_ollama_model,
    _raw_provider_for_tier,
    get_llm_provider,
    llm_routing_status,
    resolve_bulk_model,
    resolve_provider_mode,
    resolve_reasoning_model,
)
from app.settings import Settings, settings

pytestmark = pytest.mark.no_app_db

# A configured key is what used to build Vertex while assist was off.
# Without it, the gemini branch returns None for a missing key, and deleting
# the off-guard would stay green.
_DUMMY_GEMINI_KEY = "b0-aioff-dummy"
_VERTEX_PROJECT = "b0-aioff-project"


class _Resp:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = json.dumps(data).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class _FakeHTTP:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def urlopen(self, req: Any, timeout: float = 120.0) -> _Resp:
        _ = timeout
        if req.data:
            self.requests.append(json.loads(req.data.decode("utf-8")))
        return _Resp(self.responses.pop(0))


def test_ai_assist_off_does_not_build_vertex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off plus a Vertex-shaped gemini tier still returns no provider.

    Fails if the off-guard in ``_raw_provider_for_tier`` is removed
    (``llm_provider.py``, ``mode != "mock" and resolve_provider_mode() == "off"``).
    """
    assert Settings.model_fields["ai_assist"].default == "off"
    assert Settings.model_fields["ai_llm_tier_fast"].default == "gemini"

    monkeypatch.setattr(settings, "ai_assist", "off")
    monkeypatch.setattr(settings, "ai_llm_tier_fast", "gemini")
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "vertex_project", _VERTEX_PROJECT)
    monkeypatch.setattr(settings, "gemini_api_key", _DUMMY_GEMINI_KEY)
    monkeypatch.setattr(settings, "google_api_key", "")

    assert resolve_provider_mode() == "off"
    raw = _raw_provider_for_tier(tier="fast")
    assert raw is None
    assert not isinstance(raw, GeminiProvider)
    assert get_llm_provider() is None


def test_ollama_mode_routes_bulk_vs_reasoning_and_strips_cot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mode ollama posts the bulk tag, then the reasoning tag, and strips CoT.

    Fails if ``OllamaProvider.generate_json`` stops using ``resolve_bulk_model`` /
    ``resolve_reasoning_model``, or stops returning ``strip_thinking_trace``.
    """
    fake = _FakeHTTP(
        [
            {"response": 'Let me think...\n---JSON---\n{"name":"x"}'},
            {"response": 'hidden\n---JSON---\n{"name":"y"}'},
        ]
    )
    monkeypatch.setattr("app.llm_provider.request.urlopen", fake.urlopen)
    monkeypatch.setattr(
        "app.llm_provider.probe_ollama_capabilities",
        lambda **_kwargs: {
            "think_supported": False,
            "schema_format_supported": True,
            "think_param": "think",
        },
    )
    monkeypatch.setattr(settings, "ai_assist", "ollama")
    monkeypatch.setattr(settings, "ai_model_bulk", "bulk:8b")
    monkeypatch.setattr(settings, "ai_model_reasoning", "reason:14b")
    monkeypatch.setattr(settings, "ai_thinking", "auto")

    provider = OllamaProvider(base_url="http://127.0.0.1:9", model="qwen2.5:7b")
    bulk_out = provider.generate_json("list entities", system="sys", reasoning=False)
    assert bulk_out == '{"name":"x"}'
    assert fake.requests[-1]["model"] == "bulk:8b"
    assert "think" not in fake.requests[-1]
    assert fake.requests[-1]["options"]["temperature"] == 0.2

    cot_out = provider.generate_json(
        "critique", system="sys", reasoning=True, temperature=0.15
    )
    assert cot_out == '{"name":"y"}'
    assert fake.requests[-1]["model"] == "reason:14b"
    assert fake.requests[-1]["options"]["temperature"] == 0.15


def test_non_ollama_mode_refuses_ollama_shaped_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cloud mode does not adopt the ollama ladder or probe Ollama.

    Fails if ``resolve_bulk_model`` / ``resolve_reasoning_model`` drop the
    ollama-shaped rejection, or if ``llm_routing_status`` probes Ollama
    when the mode is not ollama.
    """
    monkeypatch.setattr(settings, "ai_assist", "gemini")
    monkeypatch.setattr(settings, "ai_model_bulk", "bulk:8b")
    monkeypatch.setattr(settings, "ai_model_reasoning", "reason:14b")

    assert resolve_provider_mode() == "gemini"
    bulk = resolve_bulk_model()
    reasoning = resolve_reasoning_model()
    assert bulk != "bulk:8b"
    assert reasoning != "reason:14b"
    assert _looks_like_ollama_model(bulk) is False
    assert _looks_like_ollama_model(reasoning) is False

    status = llm_routing_status()
    assert status["provider"] == "gemini"
    assert status["ollama_capabilities"] is None
