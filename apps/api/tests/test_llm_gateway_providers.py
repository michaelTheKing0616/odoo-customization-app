"""T4-LLM3: three-tier provider abstraction. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.providers import (
    BINDINGS,
    QWEN_GATEWAY_PROVIDER,
    ProviderReplayAdapter,
    default_active_providers,
    is_frontier_provider,
    require_provider,
)
from app.llm_gateway.registry import model_ids_in_source
from app.llm_gateway.types import LLMError

SCHEMA = {
    "type": "object",
    "properties": {"model": {"type": "string"}},
    "required": ["model"],
    "additionalProperties": False,
}

BASE_REQUEST = {
    "model_id": "configured",
    "max_output_tokens": 32,
    "messages": [{"role": "user", "content": "plan one model"}],
    "tools": [{"name": "describe_model", "description": "look", "input_schema": SCHEMA}],
}

CANONICAL_ARGS = {"model": "sale.order"}


def _complete_via_gateway(provider: str, payload: dict[str, Any], *, allow_frontier: bool = False):
    adapter = ProviderReplayAdapter(provider, [payload], allow_frontier=allow_frontier)
    return Gateway(adapter, sleep=lambda _ms: None).complete(BASE_REQUEST, {"describe_model": SCHEMA})


def test_swappable_provider_changes_only_the_gateway_binding() -> None:
    openai_payload = {
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "fc_swap",
                "name": "describe_model",
                "arguments": json.dumps(CANONICAL_ARGS),
            }
        ],
    }
    gemini_payload = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [{"functionCall": {"name": "describe_model", "args": dict(CANONICAL_ARGS)}}]
                },
            }
        ]
    }
    openai_response = _complete_via_gateway("openai", openai_payload)
    gemini_response = _complete_via_gateway("gemini", gemini_payload)
    assert openai_response.stop_reason == gemini_response.stop_reason == "tool_calls"
    assert openai_response.tool_calls[0].args == gemini_response.tool_calls[0].args == CANONICAL_ARGS


def test_frontier_adapter_is_inactive_by_default() -> None:
    assert "anthropic" in BINDINGS
    assert is_frontier_provider("anthropic") is True
    assert "anthropic" not in default_active_providers()
    with pytest.raises(LLMError) as caught:
        require_provider("anthropic")
    assert caught.value.kind == "invalid_request"
    with pytest.raises(LLMError) as caught_adapter:
        ProviderReplayAdapter("anthropic", [{"stop_reason": "end_turn", "content": []}])
    assert caught_adapter.value.kind == "invalid_request"


def test_frontier_adapter_runs_when_explicitly_opted_in() -> None:
    payload = {
        "stop_reason": "tool_use",
        "content": [
            {"type": "tool_use", "id": "tu_frontier", "name": "describe_model", "input": dict(CANONICAL_ARGS)}
        ],
    }
    response = _complete_via_gateway("anthropic", payload, allow_frontier=True)
    assert response.stop_reason == "tool_calls"
    assert response.tool_calls[0].args == CANONICAL_ARGS


def test_gemini_and_qwen_production_paths_stay_available() -> None:
    from app.llm_provider import GeminiProvider, OllamaProvider, _ollama_local_model

    provider_source = Path(__file__).resolve().parents[1] / "app" / "llm_provider.py"
    assert "llm_gateway" not in provider_source.read_text(encoding="utf-8")
    assert GeminiProvider().name == "gemini"
    assert OllamaProvider().name == "ollama"
    assert _ollama_local_model("gemini-2.5-flash") == "qwen3:8b"
    assert QWEN_GATEWAY_PROVIDER == "openai"
    assert "gemini" in default_active_providers()
    assert "openai" in default_active_providers()


def test_registry_model_id_strings_do_not_leak_outside_registry_file() -> None:
    api_root = Path(__file__).resolve().parents[1]
    registry_path = api_root / "app" / "llm_gateway" / "registry.py"
    ids = model_ids_in_source(registry_path.read_text(encoding="utf-8"))
    hits: list[str] = []
    registry_resolved = registry_path.resolve()
    for path in sorted(api_root.rglob("*.py")):
        if "__pycache__" in path.parts or path.resolve() == registry_resolved:
            continue
        text = path.read_text(encoding="utf-8")
        for model_id in ids:
            if model_id in text:
                hits.append(f"{path}:{model_id}")
    assert hits == [], hits
