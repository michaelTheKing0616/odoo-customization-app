"""Phase 1 remainder: stream, emulation, fallback, SSRF, scrub, registry, conformance."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.llm_gateway.adapters.anthropic import parse_anthropic
from app.llm_gateway.adapters.gemini import parse_gemini
from app.llm_gateway.adapters.openai import parse_openai
from app.llm_gateway.conformance import run_conformance
from app.llm_gateway.emulated import EmulatedRejected, parse_emulated_json
from app.llm_gateway.fallback import Endpoint, call_with_fallback
from app.llm_gateway.gateway import Gateway
from app.llm_gateway.normalize import is_minted_call_id
from app.llm_gateway.registry import TIER_C_CAPS, load_registry, lookup, model_ids_in_source
from app.llm_gateway.scrub import scrub
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.ssrf import SsrfRejected, guard_base_url
from app.llm_gateway.stream import assemble, events_from_step
from app.llm_gateway.types import LLMError, LLMResponse


def test_stream_matches_complete_and_incomplete_json_is_not_executed() -> None:
    step = {"text": "hi", "tool_calls": [{"id": "s1", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}
    assembled = assemble(events_from_step(step))
    direct = Gateway(ScriptedAdapter([step]), sleep=lambda _ms: None).complete(
        {},
        {
            "describe_model": {
                "type": "object",
                "properties": {"model": {"type": "string"}},
                "required": ["model"],
                "additionalProperties": False,
            }
        },
    )
    assert assembled.text == direct.text
    assert assembled.tool_calls[0].args == direct.tool_calls[0].args
    partial = assemble(
        [
            {"kind": "tool_call_start", "id": "x", "name": "describe_model"},
            {"kind": "tool_call_args_delta", "id": "x", "fragment": '{"model":'},
            {"kind": "stop", "reason": "end"},
        ]
    )
    assert partial.stop_reason == "malformed_tool_call"
    assert partial.tool_calls[0].args is None


def test_stream_keeps_a_supplied_id_and_mints_a_ulid_when_missing() -> None:
    events = events_from_step(
        {
            "tool_calls": [
                {"id": "fc_1", "name": "describe_model", "raw_args": "{}"},
                {"name": "describe_model", "raw_args": "{}"},
            ]
        }
    )
    ids = [event["id"] for event in events if event["kind"] == "tool_call_start"]
    assert ids[0] == "fc_1"
    assert is_minted_call_id(ids[1])
    assert ids[1] != "call_0001"
    assert ids[0] != ids[1]


def test_scripted_stream_matches_complete_on_200_calls() -> None:
    """Two hundred scripted calls, not live cassettes.

    Each call compares canonical stream assembly with ``Gateway.complete``
    and with the in-repo OpenAI, Anthropic, or Gemini parser. Nothing here
    is a recorded live cassette.
    """
    schema = {
        "type": "object",
        "properties": {"model": {"type": "string"}},
        "required": ["model"],
        "additionalProperties": False,
    }
    families = ("openai", "anthropic", "gemini")
    matched = 0
    for index in range(200):
        raw = json.dumps({"model": f"sale.order.{index}"})
        step = {
            "text": f"n{index}",
            "tool_calls": [{"id": f"s{index}", "name": "describe_model", "raw_args": raw}],
        }
        assembled = assemble(events_from_step(step))
        direct = Gateway(ScriptedAdapter([step]), sleep=lambda _ms: None).complete(
            {},
            {"describe_model": schema},
        )
        family = families[index % 3]
        parsed = _parse_scripted_family(family, index, raw)
        assert assembled.text == direct.text == f"n{index}"
        assert assembled.stop_reason == direct.stop_reason == parsed.stop_reason == "tool_calls"
        assert assembled.tool_calls[0].args == direct.tool_calls[0].args == parsed.tool_calls[0].args
        matched += 1
    assert matched == 200


def _parse_scripted_family(family: str, index: int, raw: str) -> LLMResponse:
    args = json.loads(raw)
    if family == "openai":
        return parse_openai(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": f"fc_{index}",
                        "name": "describe_model",
                        "arguments": raw,
                    }
                ],
            }
        )
    if family == "anthropic":
        return parse_anthropic(
            {
                "stop_reason": "tool_use",
                "content": [
                    {"type": "tool_use", "id": f"tu_{index}", "name": "describe_model", "input": args}
                ],
            }
        )
    return parse_gemini(
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"functionCall": {"id": f"gm_{index}", "name": "describe_model", "args": args}}
                        ]
                    },
                }
            ]
        }
    )


def test_scripted_emulated_path_accepts_at_least_95_percent_of_200_calls() -> None:
    """Two hundred scripted emulated calls, not live cassettes.

    Ten calls are partial or ambiguous and must not return an executable
    action. The other 190 parse. 190/200 is 95 percent.
    """
    accepted = 0
    rejected = 0
    for index in range(200):
        if index % 40 == 0:
            with pytest.raises(EmulatedRejected):
                parse_emulated_json('{"action": {"tool": "describe_model"}}')
            rejected += 1
            continue
        if index % 40 == 20:
            with pytest.raises(EmulatedRejected):
                parse_emulated_json(
                    '{"action": {"tool": "describe_model", "args": {}, "final": "no"}}'
                )
            rejected += 1
            continue
        parsed = parse_emulated_json(
            json.dumps({"action": {"tool": "describe_model", "args": {"model": f"m{index}"}}})
        )
        assert parsed == {"tool": "describe_model", "args": {"model": f"m{index}"}}
        accepted += 1
    assert accepted + rejected == 200
    assert rejected == 10
    assert accepted >= 190


def test_gateway_does_not_store_a_raw_provider_key() -> None:
    adapter = ScriptedAdapter([{"text": "ok"}])
    secret = "sk-abcdef123456"
    Gateway(adapter, sleep=lambda _ms: None).complete(
        {
            "api_key": secret,
            "authorization": "Bearer abcdefghij",
            "messages": [{"role": "user", "content": "hi"}],
        }
    )
    assert adapter.last_request is not None
    assert "api_key" not in adapter.last_request
    assert "authorization" not in adapter.last_request
    stored = str(adapter.last_request)
    assert secret not in stored
    assert "abcdefghij" not in stored


def test_emulated_json_rejects_partial_and_ambiguous_actions() -> None:
    parsed = parse_emulated_json('{"action": {"tool": "describe_model", "args": {"model": "sale.order"}}}')
    assert parsed["tool"] == "describe_model"
    with pytest.raises(EmulatedRejected):
        parse_emulated_json('{"action": {"tool": "describe_model"}}')
    with pytest.raises(EmulatedRejected):
        parse_emulated_json('{"action": {"tool": "describe_model", "args": {}, "final": "no"}}')


def test_fallback_degrades_when_the_next_tier_is_too_low() -> None:
    primary = Gateway(ScriptedAdapter([{"error": "server"}] * 4), sleep=lambda _ms: None)
    weak = Gateway(
        ScriptedAdapter([{"tool_calls": [{"id": "w", "name": "describe_model", "raw_args": '{"model":"sale.order"}'}]}]),
        sleep=lambda _ms: None,
    )
    response, trace = call_with_fallback(
        [Endpoint("primary", primary, "A"), Endpoint("weak", weak, "C")],
        {},
        required_tier="A",
    )
    assert response.text == "degraded to read-only"
    assert response.tool_calls == ()
    assert trace == ["primary", "weak"]
    strong = Gateway(ScriptedAdapter([{"text": "planned"}]), sleep=lambda _ms: None)
    recovered, trace = call_with_fallback(
        [
            Endpoint("primary", Gateway(ScriptedAdapter([{"error": "server"}] * 4), sleep=lambda _ms: None), "A"),
            Endpoint("strong", strong, "A"),
        ],
        {},
        required_tier="A",
    )
    assert recovered.text == "planned"
    assert trace[-1] == "strong"


def test_cancel_does_not_call_the_adapter_and_auth_does_not_fall_through() -> None:
    adapter = ScriptedAdapter([{"text": "should-not-run"}])
    paused = Gateway(adapter, sleep=lambda _ms: None).complete({"cancelled": True})
    assert paused.stop_reason == "pause"
    assert adapter.calls == 0
    primary = Gateway(ScriptedAdapter([{"error": "auth"}, {"text": "no"}]), sleep=lambda _ms: None)
    secondary = Gateway(ScriptedAdapter([{"text": "fallback"}]), sleep=lambda _ms: None)
    with pytest.raises(LLMError) as caught:
        call_with_fallback(
            [Endpoint("primary", primary, "A"), Endpoint("secondary", secondary, "A")],
            {},
            required_tier="A",
        )
    assert caught.value.kind == "auth"
    assert secondary.calls == 0


def test_ssrf_blocks_https_link_local_public_http_and_cgnat() -> None:
    with pytest.raises(SsrfRejected):
        guard_base_url("https://169.254.169.254/latest", resolve=lambda _host: ["169.254.169.254"])
    with pytest.raises(SsrfRejected):
        guard_base_url("http://api.example.com/v1", resolve=lambda _host: ["93.184.216.34"])
    with pytest.raises(SsrfRejected):
        guard_base_url(
            "https://metadata.google.internal/",
            resolve=lambda _host: ["169.254.169.254"],
            allow_private_hosts=frozenset({"metadata.google.internal"}),
        )
    with pytest.raises(SsrfRejected):
        guard_base_url("https://meta.aliyun/latest", resolve=lambda _host: ["100.100.100.200"])
    with pytest.raises(SsrfRejected):
        guard_base_url("http://169.254.169.254/latest", resolve=lambda _host: ["169.254.169.254"])
    with pytest.raises(SsrfRejected):
        guard_base_url("https://metadata.google.internal/path", resolve=lambda _host: ["169.254.169.254"])
    with pytest.raises(SsrfRejected):
        guard_base_url("https://model.internal/v1", resolve=lambda _host: ["10.0.0.8"])
    assert guard_base_url("https://api.example.com/v1", resolve=lambda _host: ["93.184.216.34"]) == "api.example.com"
    assert (
        guard_base_url(
            "http://llm.internal/v1",
            resolve=lambda _host: ["10.1.1.5"],
            allow_private_hosts=frozenset({"llm.internal"}),
        )
        == "llm.internal"
    )


def test_scrub_removes_exact_secrets_and_key_shapes() -> None:
    cleaned = scrub("key sk-abcdef123456 and Bearer abcdefghij and db-secret", ["db-secret"])
    assert "sk-abcdef123456" not in cleaned
    assert "abcdefghij" not in cleaned
    assert "db-secret" not in cleaned
    assert cleaned.count("[redacted]") == 3


def test_registry_rejects_an_invented_tier_and_a_missing_id() -> None:
    rows = load_registry([{"provider": "local", "model_id": "configured-at-runtime", "tier": None}])
    assert rows[("local", "configured-at-runtime")].tier is None
    with pytest.raises(ValueError):
        load_registry([{"provider": "local", "model_id": "x", "tier": "S"}])
    with pytest.raises(ValueError):
        load_registry([{"provider": "local"}])


def test_unknown_model_id_stays_unset_with_tier_c_caps() -> None:
    records = load_registry([{"provider": "local", "model_id": "configured-at-runtime", "tier": "C"}])
    missing = lookup(records, "local", "x")
    assert missing.record is None
    assert missing.tier is None
    assert missing.caps == TIER_C_CAPS
    assert missing.caps.read_only is True
    assert missing.caps.can_submit_changeset is False
    known = lookup(records, "local", "configured-at-runtime")
    assert known.record is not None
    assert known.tier == "C"
    assert known.caps == TIER_C_CAPS
    unset = load_registry([{"provider": "local", "model_id": "configured-at-runtime", "tier": None}])
    pending = lookup(unset, "local", "configured-at-runtime")
    assert pending.record is not None
    assert pending.tier is None
    assert pending.caps == TIER_C_CAPS
    measured = load_registry([{"provider": "local", "model_id": "configured-at-runtime", "tier": "A"}])
    ranked = lookup(measured, "local", "configured-at-runtime")
    assert ranked.tier == "A"
    assert ranked.caps.read_only is False
    assert ranked.caps.can_submit_changeset is True
    assert ("local", "x") not in records


def _literal_hits(root: Path, ids: frozenset[str], registry_path: Path) -> list[str]:
    if not ids:
        return []
    registry_resolved = registry_path.resolve()
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or path.resolve() == registry_resolved:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ids:
                hits.append(f"{path}:{node.lineno}:{node.value}")
    return hits


def test_registry_model_id_strings_do_not_appear_outside_the_registry_file(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    registry_path = api_root / "app" / "llm_gateway" / "registry.py"
    ids = model_ids_in_source(registry_path.read_text(encoding="utf-8"))
    assert model_ids_in_source('MODEL_IDS = ("configured", "configured-at-runtime")\n') == frozenset()
    assert "configured" not in ids
    assert "configured-at-runtime" not in ids
    hits = _literal_hits(api_root, ids, registry_path)
    assert hits == [], hits

    copied = "registry-scan-copy"
    registry_copy = tmp_path / "registry.py"
    registry_copy.write_text(f"MODEL_IDS = ({copied!r},)\n", encoding="utf-8")
    planted = tmp_path / "leaked.py"
    planted.write_text(f"value = {copied!r}\n", encoding="utf-8")
    copied_ids = model_ids_in_source(registry_copy.read_text(encoding="utf-8"))
    assert copied in copied_ids
    planted_hits = _literal_hits(tmp_path, copied_ids, registry_copy)
    assert planted_hits
    assert all("registry.py" not in hit for hit in planted_hits)


def test_conformance_suite_passes_every_gate_case() -> None:
    report = run_conformance()
    gates = [f"C{index:02d}" for index in range(1, 21) if index not in {11, 18, 19}]
    assert [report[case] for case in gates] == ["pass"] * len(gates)
    assert report["C11"] == "scored"
    assert report["C18"] == "scored"
    assert report["C19"] == "informational"


def test_vision_request_is_refused_when_the_model_cannot_see() -> None:
    adapter = ScriptedAdapter([{"text": "saw it"}])
    with pytest.raises(LLMError) as caught:
        Gateway(adapter, sleep=lambda _ms: None).complete({"images": ["abc"], "vision": False})
    assert caught.value.kind == "unsupported_feature"
    assert adapter.calls == 0
