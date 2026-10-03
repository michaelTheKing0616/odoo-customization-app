"""Conformance C01–C20 against the scripted adapter. Live providers are not called."""

from __future__ import annotations

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.stream import assemble, events_from_step
from app.llm_gateway.types import LLMError

_SCHEMA = {
    "type": "object",
    "properties": {
        "model": {"type": "string"},
        "nested": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    },
    "required": ["model"],
    "additionalProperties": False,
}


def run_conformance() -> dict[str, str]:
    report: dict[str, str] = {}
    report["C01"] = _pass(Gateway(ScriptedAdapter([{"text": "hello"}])).complete({}).text == "hello")
    report["C02"] = _pass(
        Gateway(ScriptedAdapter([{"tool_calls": [{"id": "c1", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}]))
        .complete({}, {"describe_model": _SCHEMA})
        .stop_reason
        == "tool_calls"
    )
    nested = Gateway(
        ScriptedAdapter(
            [{"tool_calls": [{"id": "c3", "name": "describe_model", "raw_args": '{"model":"sale.order","nested":{"name":"x"}}'}]}]
        )
    ).complete({}, {"describe_model": _SCHEMA})
    report["C03"] = _pass(nested.tool_calls[0].args == {"model": "sale.order", "nested": {"name": "x"}})
    first = Gateway(ScriptedAdapter([{"tool_calls": [{"id": "c4", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}])).complete(
        {}, {"describe_model": _SCHEMA}
    )
    second = Gateway(ScriptedAdapter([{"text": "done"}])).complete({"tool_result": first.tool_calls[0].id})
    report["C04"] = _pass(first.stop_reason == "tool_calls" and second.text == "done")
    steps = [{"text": f"step-{index}"} for index in range(3)]
    gateway = Gateway(ScriptedAdapter(steps))
    seen = [gateway.complete({}).text for _ in range(3)]
    report["C05"] = _pass(seen == ["step-0", "step-1", "step-2"])
    parallel = Gateway(
        ScriptedAdapter(
            [
                {
                    "tool_calls": [
                        {"id": "p1", "name": "describe_model", "raw_args": '{"model":"a"}'},
                        {"id": "p2", "name": "describe_model", "raw_args": '{"model":"b"}'},
                    ]
                }
            ]
        )
    ).complete({}, {"describe_model": _SCHEMA})
    report["C06"] = _pass([call.id for call in parallel.tool_calls] == ["p1", "p2"])
    forced_off = Gateway(
        ScriptedAdapter([{"tool_calls": [{"id": "z", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}])
    ).complete({"tool_choice": "none"})
    report["C07"] = _pass(forced_off.tool_calls == ())
    invalid = Gateway(
        ScriptedAdapter([{"tool_calls": [{"id": "bad", "name": "describe_model", "raw_args": '{"sql":"x"}'}]}])
    ).complete({}, {"describe_model": _SCHEMA})
    report["C08"] = _pass(invalid.stop_reason == "malformed_tool_call")
    structured = Gateway(ScriptedAdapter([{"text": '{"ok": true}'}])).complete({})
    report["C09"] = _pass(structured.text == '{"ok": true}')
    step = {"text": "streamed", "tool_calls": [{"id": "s1", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}
    streamed = assemble(events_from_step(step))
    direct = Gateway(ScriptedAdapter([step])).complete({}, {"describe_model": _SCHEMA})
    report["C10"] = _pass(streamed.text == direct.text and streamed.tool_calls[0].args == direct.tool_calls[0].args)
    report["C11"] = "scored" if Gateway(ScriptedAdapter([{"text": "needle-42"}])).complete({}).text == "needle-42" else "fail"
    report["C12"] = _pass(Gateway(ScriptedAdapter([{"text": "cut", "stop_reason": "max_tokens"}])).complete({}).stop_reason == "max_tokens")
    try:
        Gateway(ScriptedAdapter([{"error": "auth"}])).complete({})
        report["C13"] = "fail"
    except LLMError as exc:
        report["C13"] = _pass(exc.kind == "auth")
    report["C14"] = _pass(
        Gateway(ScriptedAdapter([{"text": "ok"}])).complete({"echo_reasoning": True, "reasoning": "sig"}).reasoning == "sig"
    )
    unicode_call = Gateway(
        ScriptedAdapter([{"tool_calls": [{"id": "u", "name": "describe_model", "raw_args": '{"model":"販売"}'}]}])
    ).complete({}, {"describe_model": _SCHEMA})
    report["C15"] = _pass(unicode_call.tool_calls[0].args == {"model": "販売"})
    report["C16"] = _pass(Gateway(ScriptedAdapter([{"text": "should-not"}])).complete({"cancelled": True}).stop_reason == "pause")
    left = Gateway(ScriptedAdapter([{"text": "left"}])).complete({}).text
    right = Gateway(ScriptedAdapter([{"text": "right"}])).complete({}).text
    report["C17"] = _pass(left == "left" and right == "right")
    vision = ScriptedAdapter([{"text": "saw"}])
    try:
        Gateway(vision).complete({"images": ["abc"], "vision": False})
        report["C18"] = "fail"
    except LLMError as exc:
        report["C18"] = "scored" if exc.kind == "unsupported_feature" and vision.calls == 0 else "fail"
    report["C19"] = "informational"
    report["C20"] = _pass(Gateway(ScriptedAdapter([{"text": "no", "stop_reason": "refusal"}])).complete({}).stop_reason == "refusal")
    return report


def _pass(ok: bool) -> str:
    return "pass" if ok else "fail"
