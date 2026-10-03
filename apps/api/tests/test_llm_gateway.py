"""Phase 1 gateway. No live provider and no Odoo."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.normalize import ArgsRejected, parse_tool_args, synthesize_call_id
from app.llm_gateway.retries import delay_ms, is_retryable, should_stop
from app.llm_gateway.schema_lowering import canonical_issues, canonical_tool_issues, to_gemini, to_openai_strict
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.types import LLMError


SCHEMA = {
    "type": "object",
    "properties": {
        "model": {"type": "string"},
        "limit": {"type": "integer"},
        "note": {"type": "string"},
    },
    "required": ["model"],
    "additionalProperties": False,
}


def test_openai_lowerer_requires_every_property() -> None:
    lowered = to_openai_strict(SCHEMA)
    assert lowered["required"] == ["model", "limit", "note"]
    assert lowered["additionalProperties"] is False
    assert "anyOf" in lowered["properties"]["note"]


def test_gemini_lowerer_turns_const_into_enum() -> None:
    lowered = to_gemini({"type": "string", "const": "field.create", "pattern": "x_"})
    assert lowered["enum"] == ["field.create"]
    assert "pattern" not in lowered
    assert "const" not in lowered


def test_malformed_nan_and_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ArgsRejected):
        parse_tool_args('{"a": NaN}')
    with pytest.raises(ArgsRejected):
        parse_tool_args('{"a": 1, "a": 2}')
    with pytest.raises(ArgsRejected):
        parse_tool_args("{" + " ".join(f'"k{i}": {{' for i in range(14)) + "1" + "}" * 14 + "}")
    assert parse_tool_args('{"model": "sale.order"}') == {"model": "sale.order"}


def test_missing_call_id_is_synthesized_and_schema_failure_does_not_execute() -> None:
    adapter = ScriptedAdapter(
        [
            {"text": "ok"},
            {"tool_calls": [{"name": "describe_model", "raw_args": '{"model": "sale.order"}'}]},
            {"tool_calls": [{"name": "describe_model", "raw_args": '{"limit": "no"}'}]},
        ]
    )
    gateway = Gateway(adapter)
    assert gateway.complete({}).stop_reason == "end"
    good = gateway.complete({}, {"describe_model": SCHEMA})
    assert good.stop_reason == "tool_calls"
    assert good.tool_calls[0].id == synthesize_call_id(20)
    assert good.tool_calls[0].args == {"model": "sale.order"}
    bad = gateway.complete({}, {"describe_model": SCHEMA})
    assert bad.stop_reason == "malformed_tool_call"
    assert bad.tool_calls[0].args is None
    assert adapter.calls == 3


def test_retry_policy_honors_retry_after_and_stops_on_auth() -> None:
    assert is_retryable("rate_limit") is True
    assert is_retryable("auth") is False
    assert delay_ms(1, retry_after_ms=1500) == 1500
    assert delay_ms(1, retry_after_ms=None) == 500
    assert should_stop(1, "auth") is True
    assert should_stop(4, "timeout") is True
    assert should_stop(2, "timeout") is False


def test_budget_stops_before_another_provider_call() -> None:
    adapter = ScriptedAdapter([{"text": "one"}, {"text": "two"}])
    gateway = Gateway(adapter, max_calls=1)
    assert gateway.complete({}).text == "one"
    with pytest.raises(LLMError) as caught:
        gateway.complete({})
    assert caught.value.kind == "budget"
    assert adapter.calls == 1


def test_canonical_validator_rejects_extra_fields() -> None:
    assert canonical_issues({"model": "sale.order", "sql": "drop"}, SCHEMA)


def test_adapter_bodies_reject_a_bad_tool_name() -> None:
    from app.llm_gateway.adapters.anthropic import anthropic_body
    from app.llm_gateway.adapters.gemini import gemini_body
    from app.llm_gateway.adapters.openai import openai_body

    request = {
        "model_id": "configured",
        "max_output_tokens": 8,
        "tools": [{"name": "1abc", "description": "ok", "input_schema": SCHEMA}],
    }
    for builder in (openai_body, anthropic_body, gemini_body):
        with pytest.raises(LLMError) as caught:
            builder(request)
        assert caught.value.kind == "invalid_request"


def test_tool_name_and_description_limits() -> None:
    assert canonical_tool_issues("ab", "ok")
    assert canonical_tool_issues("1abc", "ok")
    too_long_name = "a" + ("b" * 41)
    assert len(too_long_name) == 42
    assert canonical_tool_issues(too_long_name, "ok")
    assert canonical_tool_issues("abc", "d" * 1024) == []
    assert canonical_tool_issues("a" + ("b" * 40), "d" * 1024) == []
    assert canonical_tool_issues("abc", "d" * 1025)


def test_gateway_package_does_not_import_odoo_or_changeset() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "llm_gateway"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                assert "odoo" not in module
                assert "changeset" not in module
                assert "llm_provider" not in module
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec"}


def _containers(count: int) -> str:
    raw = '{"x": 1}'
    for _index in range(count - 1):
        raw = '{"k": ' + raw + "}"
    return raw


def test_depth_boundary_and_recursion_keep_the_raw_string() -> None:
    parse_tool_args(_containers(12))
    rejected = _containers(13)
    with pytest.raises(ArgsRejected) as caught:
        parse_tool_args(rejected)
    assert caught.value.reason == "depth"
    assert caught.value.raw == rejected
    bomb = '{"a":' + ("[" * 2000) + "1" + ("]" * 2000) + "}"
    with pytest.raises(ArgsRejected) as deep:
        parse_tool_args(bomb)
    assert deep.value.reason == "depth"
    assert deep.value.raw == bomb
    raw_nan = '{"a": NaN}'
    with pytest.raises(ArgsRejected) as nan:
        parse_tool_args(raw_nan)
    assert nan.value.raw == raw_nan


def test_lowerers_walk_nested_items_and_unions() -> None:
    array_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
            "required": ["name"],
        },
    }
    lowered = to_openai_strict(array_schema)
    assert lowered["items"]["additionalProperties"] is False
    assert "note" in lowered["items"]["required"]
    union = to_openai_strict(
        {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
                    "required": ["name"],
                }
            ]
        }
    )
    assert union["anyOf"][0]["additionalProperties"] is False
    assert "note" in union["anyOf"][0]["required"]
    gemini = to_gemini({"anyOf": [{"const": "x", "pattern": "y"}]})
    assert gemini["anyOf"][0]["enum"] == ["x"]
    assert "pattern" not in gemini["anyOf"][0]


def test_validator_rejects_bool_as_integer_and_bad_boolean() -> None:
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean"}, "count": {"type": "integer"}},
        "required": ["flag", "count"],
        "additionalProperties": False,
    }
    boolean_issues = canonical_issues({"flag": "yes", "count": 1}, schema)
    integer_issues = canonical_issues({"flag": True, "count": True}, schema)
    assert any("flag" in issue for issue in boolean_issues)
    assert any("count" in issue for issue in integer_issues)


def test_unparseable_and_unknown_tools_are_not_executed() -> None:
    adapter = ScriptedAdapter(
        [
            {"tool_calls": [{"name": "describe_model", "raw_args": "{"}]},
            {"tool_calls": [{"name": "unknown_tool", "raw_args": '{"model":"sale.order"}'}]},
        ]
    )
    gateway = Gateway(adapter)
    broken = gateway.complete({}, {"describe_model": SCHEMA})
    assert broken.stop_reason == "malformed_tool_call"
    assert broken.tool_calls[0].args is None
    unknown = gateway.complete({}, {"describe_model": SCHEMA})
    assert unknown.stop_reason == "malformed_tool_call"
    assert unknown.tool_calls[0].args is None


def test_retryable_kinds_and_retry_after_cap() -> None:
    for kind in ("rate_limit", "overloaded", "timeout", "network", "server"):
        assert is_retryable(kind) is True
    for kind in ("auth", "invalid_request", "content_filter", "refusal"):
        assert is_retryable(kind) is False
    assert delay_ms(1, retry_after_ms=999_999) == 20_000
    with pytest.raises(LLMError):
        delay_ms(1, retry_after_ms=-5)


def test_gateway_retries_timeout_and_stops_on_auth() -> None:
    slept: list[int] = []
    retrying = ScriptedAdapter([{"error": "timeout", "retry_after_ms": 100}, {"text": "recovered"}])
    gateway = Gateway(retrying, sleep=slept.append)
    assert gateway.complete({}).text == "recovered"
    assert slept == [100]
    assert retrying.calls == 2
    capped: list[int] = []
    capping = ScriptedAdapter([{"error": "rate_limit", "retry_after_ms": 999_999}, {"text": "later"}])
    assert Gateway(capping, sleep=capped.append).complete({}).text == "later"
    assert capped == [20_000]
    negative = ScriptedAdapter([{"error": "timeout", "retry_after_ms": -5}, {"text": "no"}])
    with pytest.raises(LLMError) as bad_delay:
        Gateway(negative, sleep=lambda _ms: None).complete({})
    assert bad_delay.value.kind == "invalid_request"
    assert negative.calls == 1
    auth = ScriptedAdapter([{"error": "auth"}, {"text": "should-not-run"}])
    with pytest.raises(LLMError) as caught:
        Gateway(auth, sleep=lambda _ms: None).complete({})
    assert caught.value.kind == "auth"
    assert auth.calls == 1
    exhausted = ScriptedAdapter([{"error": "timeout"}, {"error": "timeout"}, {"error": "timeout"}, {"error": "timeout"}])
    with pytest.raises(LLMError) as give_up:
        Gateway(exhausted, sleep=lambda _ms: None).complete({})
    assert give_up.value.kind == "timeout"
    assert exhausted.calls == 4
