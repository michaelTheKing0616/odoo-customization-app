"""Phase 1 gateway. No live provider and no Odoo."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.normalize import ArgsRejected, parse_tool_args, synthesize_call_id
from app.llm_gateway.retries import MAX_ARG_REPAIRS, arg_repair_stopped, delay_ms, is_retryable, should_stop
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


def test_parse_tool_args_rejects_payloads_over_256_kb() -> None:
    raw = '{"k":"' + ("a" * (256 * 1024)) + '"}'
    assert len(raw.encode("utf-8")) > 256 * 1024
    with pytest.raises(ArgsRejected) as caught:
        parse_tool_args(raw)
    assert caught.value.reason == "size"
    assert caught.value.raw == raw


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


def test_rule_3_parallel_reads_share_a_batch_and_writes_stay_sequential() -> None:
    adapter = ScriptedAdapter(
        [
            {
                "tool_calls": [
                    {"id": "r1", "name": "describe_model", "raw_args": '{"model":"sale.order"}'},
                    {"id": "r2", "name": "describe_field", "raw_args": '{"model":"sale.order"}'},
                    {"id": "w1", "name": "changeset_add_op", "raw_args": '{"model":"sale.order"}'},
                    {"id": "w2", "name": "field_create", "raw_args": '{"model":"sale.order"}'},
                    {"id": "r3", "name": "schema_search", "raw_args": '{"model":"sale.order"}'},
                ]
            }
        ]
    )
    response = Gateway(adapter, sleep=lambda _ms: None).complete(
        {
            "tools": [
                {"name": "describe_model", "class": "read"},
                {"name": "describe_field", "class": "read"},
                {"name": "changeset_add_op", "class": "write"},
                {"name": "field_create", "class": "write"},
                {"name": "schema_search", "class": "read"},
            ]
        },
        {
            "describe_model": SCHEMA,
            "describe_field": SCHEMA,
            "changeset_add_op": SCHEMA,
            "field_create": SCHEMA,
            "schema_search": SCHEMA,
        },
    )
    assert response.stop_reason == "tool_calls"
    assert response.tool_batches == (("r1", "r2"), ("w1",), ("w2",), ("r3",))


def test_rule_4_repair_roles_maps_aliases_and_orphan_tools() -> None:
    adapter = ScriptedAdapter([{"text": "ok"}])
    Gateway(adapter, sleep=lambda _ms: None).complete(
        {
            "messages": [
                {"role": "function", "content": "orphan"},
                {"role": "developer", "content": "plan"},
                {"role": "human", "content": "hello"},
                {"role": "model", "content": "ok"},
                {"role": "tool_result", "content": "1"},
            ]
        }
    )
    assert adapter.last_request is not None
    assert adapter.last_request["messages"] == [
        {"role": "user", "content": "orphan"},
        {"role": "system", "content": "plan"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "ok"},
        {"role": "tool", "content": "1"},
    ]


def test_rule_6_maps_provider_stop_reasons() -> None:
    expected = {
        "end_turn": "end",
        "stop_sequence": "end",
        "STOP": "end",
        "tool_use": "tool_calls",
        "MAX_TOKENS": "max_tokens",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "MALFORMED_FUNCTION_CALL": "malformed_tool_call",
        "pause_turn": "pause",
        "refusal": "refusal",
        "not-a-reason": "error",
    }
    for raw, canonical in expected.items():
        response = Gateway(ScriptedAdapter([{"text": "x", "stop_reason": raw}]), sleep=lambda _ms: None).complete({})
        assert response.stop_reason == canonical


def test_rule_7_records_provider_usage() -> None:
    response = Gateway(
        ScriptedAdapter([{"text": "ok", "usage": {"promptTokenCount": 4, "candidatesTokenCount": 2}}]),
        sleep=lambda _ms: None,
    ).complete({})
    assert response.usage == {"input_tokens": 4, "output_tokens": 2}


def test_rule_8_reasoning_stays_opaque_and_drops_on_provider_switch() -> None:
    trace = 'do-not-parse {"tool": "secret"}'
    same = Gateway(
        ScriptedAdapter([{"text": "visible", "reasoning": trace}]),
        sleep=lambda _ms: None,
    ).complete({"provider": "anthropic"})
    assert same.reasoning == trace
    assert trace not in same.text
    switched_adapter = ScriptedAdapter([{"text": "next", "reasoning": trace}])
    switched = Gateway(switched_adapter, sleep=lambda _ms: None).complete(
        {
            "provider": "openai",
            "reasoning_provider": "anthropic",
            "reasoning": trace,
            "messages": [{"role": "assistant", "content": "visible", "reasoning": trace}],
        }
    )
    assert switched.reasoning == ""
    assert switched_adapter.last_request is not None
    assert "secret" not in str(switched_adapter.last_request)


def test_rule_9_unicode_text_and_args_are_nfc() -> None:
    decomposed = "e\u0301"
    raw = '{"model": "' + decomposed + '"}'
    adapter = ScriptedAdapter(
        [
            {
                "text": decomposed,
                "tool_calls": [{"id": "u9", "name": "describe_model", "raw_args": raw}],
            }
        ]
    )
    response = Gateway(adapter, sleep=lambda _ms: None).complete(
        {"messages": [{"role": "user", "content": decomposed}]},
        {
            "describe_model": {
                "type": "object",
                "properties": {"model": {"type": "string"}},
                "required": ["model"],
                "additionalProperties": False,
            }
        },
    )
    assert response.text == "\u00e9"
    assert response.tool_calls[0].args == {"model": "\u00e9"}
    assert response.tool_calls[0].raw_args == raw
    assert adapter.last_request is not None
    assert adapter.last_request["messages"][0]["content"] == "\u00e9"


def test_idle_timeout_defaults_to_30_seconds() -> None:
    from app.llm_gateway.stream import assemble

    gateway = Gateway(ScriptedAdapter([{"text": "ok"}]), sleep=lambda _ms: None)
    assert gateway.idle_timeout_ms == 30_000
    assert gateway.complete({}).text == "ok"
    stalled = assemble(
        [
            {"kind": "text_delta", "text": "a", "at_ms": "0"},
            {"kind": "text_delta", "text": "b", "at_ms": "30001"},
        ]
    )
    assert stalled.stop_reason == "error"
    assert stalled.text == "a"


def test_stream_tools_false_falls_back_to_non_stream() -> None:
    adapter = ScriptedAdapter(
        [
            {
                "text": "hi",
                "tool_calls": [{"id": "s1", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}],
            }
        ]
    )
    response = Gateway(adapter, sleep=lambda _ms: None).complete(
        {"stream": True, "stream_tools": False},
        {"describe_model": SCHEMA},
    )
    assert adapter.last_request is not None
    assert adapter.last_request["stream"] is False
    assert adapter.last_request["stream_tools"] is False
    assert response.text == "hi"
    assert response.stop_reason == "tool_calls"
    assert response.tool_calls[0].args == {"model": "sale.order"}


def test_arg_repair_stops_at_2_and_budget_defaults_to_40() -> None:
    """Argument repair allows two follow-up calls. The default call budget is 40.

    Retry stopping at 4 is already asserted by
    ``test_gateway_retries_timeout_and_stops_on_auth`` (``exhausted.calls == 4``)
    and ``test_retry_policy_honors_retry_after_and_stops_on_auth``.
    """
    assert MAX_ARG_REPAIRS == 2
    assert arg_repair_stopped(1) is False
    assert arg_repair_stopped(2) is True
    bad = {"tool_calls": [{"id": "b", "name": "describe_model", "raw_args": '{"limit": "no"}'}]}
    adapter = ScriptedAdapter([bad, bad, bad, {"text": "must-not-run"}])
    rejected = Gateway(adapter, sleep=lambda _ms: None).complete(
        {"allow_arg_repair": True},
        {"describe_model": SCHEMA},
    )
    assert rejected.stop_reason == "malformed_tool_call"
    assert rejected.tool_calls[0].args is None
    # Original call plus two repairs. The fourth scripted step is not sent.
    assert adapter.calls == 3
    leftover = Gateway(adapter, sleep=lambda _ms: None).complete({})
    assert leftover.text == "must-not-run"
    repaired = ScriptedAdapter(
        [
            bad,
            bad,
            {"tool_calls": [{"id": "g", "name": "describe_model", "raw_args": '{"model": "sale.order"}'}]},
        ]
    )
    accepted = Gateway(repaired, sleep=lambda _ms: None).complete(
        {"allow_arg_repair": True},
        {"describe_model": SCHEMA},
    )
    assert accepted.stop_reason == "tool_calls"
    assert accepted.tool_calls[0].args == {"model": "sale.order"}
    assert repaired.calls == 3
    budget = Gateway(ScriptedAdapter([{"text": "ok"}] * 41), sleep=lambda _ms: None)
    for _index in range(40):
        assert budget.complete({}).text == "ok"
    with pytest.raises(LLMError) as caught:
        budget.complete({})
    assert caught.value.kind == "budget"
    assert budget.calls == 40
