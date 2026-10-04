"""Cassette tests for provider adapters. No network."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.llm_gateway.adapters.anthropic import anthropic_body, anthropic_error, parse_anthropic
from app.llm_gateway.adapters.gemini import gemini_body, parse_gemini
from app.llm_gateway.adapters.openai import openai_body, openai_error, parse_openai
from app.llm_gateway.normalize import is_minted_call_id
from app.llm_gateway.types import LLMError


SCHEMA = {
    "type": "object",
    "properties": {"model": {"type": "string"}, "note": {"type": "string"}},
    "required": ["model"],
}


def test_no_adapter_accepts_an_api_key_or_opens_a_socket() -> None:
    request = {"model_id": "configured", "max_output_tokens": 8, "api_key": "secret"}
    for builder in (anthropic_body, openai_body, gemini_body):
        with pytest.raises(LLMError):
            builder(request)
    root = Path(__file__).resolve().parents[1] / "app" / "llm_gateway" / "adapters"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert "socket" not in name
                assert "httpx" not in name
                assert "urllib" not in name
                assert "requests" not in name
    with pytest.raises(LLMError):
        anthropic_body({"model_id": "configured", "max_output_tokens": 20, "api_key": "secret"})
    body = anthropic_body(
        {
            "model_id": "configured",
            "max_output_tokens": 20,
            "system": "You plan.",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"name": "describe_model", "description": "look", "input_schema": SCHEMA}],
        }
    )
    assert "secret" not in str(body)
    assert body["system"] == "You plan."
    assert "note" in body["tools"][0]["input_schema"]["required"]
    parsed = parse_anthropic(
        {
            "stop_reason": "tool_use",
            "content": [
                {"type": "text", "text": "looking"},
                {"type": "tool_use", "id": "tu_1", "name": "describe_model", "input": {"model": "sale.order"}},
            ],
        }
    )
    assert parsed.stop_reason == "tool_calls"
    assert parsed.tool_calls[0].args == {"model": "sale.order"}
    assert anthropic_error(429).kind == "rate_limit"
    assert anthropic_error(401).kind == "auth"


def test_openai_body_is_stateless_and_arguments_stay_a_string() -> None:
    body = openai_body(
        {
            "model_id": "configured",
            "max_output_tokens": 30,
            "messages": [],
            "tools": [{"name": "describe_model", "input_schema": SCHEMA}],
        }
    )
    assert body["store"] is False
    parsed = parse_openai(
        {
            "status": "completed",
            "output": [
                {"type": "function_call", "call_id": "fc_1", "name": "describe_model", "arguments": '{"model":"sale.order"}'}
            ],
        }
    )
    assert parsed.tool_calls[0].args == {"model": "sale.order"}
    assert parsed.tool_calls[0].raw_args == '{"model":"sale.order"}'
    broken = parse_openai({"output": [{"type": "function_call", "name": "describe_model", "arguments": "{"}]})
    assert broken.stop_reason == "malformed_tool_call"
    assert broken.tool_calls[0].args is None
    assert openai_error(429, retry_after_ms=100).retry_after_ms == 100


def test_gemini_synthesizes_a_missing_call_id_and_maps_malformed() -> None:
    body = gemini_body(
        {
            "model_id": "configured",
            "max_output_tokens": 10,
            "system": "plan",
            "tools": [{"name": "describe_model", "input_schema": {"type": "string", "const": "sale.order"}}],
        }
    )
    assert body["tools"][0]["functionDeclarations"][0]["parameters"]["enum"] == ["sale.order"]
    parsed = parse_gemini(
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"functionCall": {"name": "describe_model", "args": {"model": "sale.order"}}}]},
                }
            ]
        }
    )
    assert is_minted_call_id(parsed.tool_calls[0].id)
    assert parsed.tool_calls[0].id != "call_0000"
    malformed = parse_gemini({"candidates": [{"finishReason": "MALFORMED_FUNCTION_CALL", "content": {"parts": []}}]})
    assert malformed.stop_reason == "malformed_tool_call"


def test_gemini_builtin_tools_are_not_mixed_with_functions() -> None:
    with pytest.raises(LLMError) as caught:
        gemini_body(
            {
                "model_id": "configured",
                "max_output_tokens": 8,
                "builtin_tools": ["google_search"],
                "tools": [{"name": "describe_model", "input_schema": SCHEMA}],
            }
        )
    assert caught.value.kind == "invalid_request"
    body = gemini_body(
        {
            "model_id": "configured",
            "max_output_tokens": 8,
            "tools": [{"name": "describe_model", "input_schema": SCHEMA}],
        }
    )
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "describe_model"
    assert "googleSearch" not in str(body)
    assert "codeExecution" not in str(body)
