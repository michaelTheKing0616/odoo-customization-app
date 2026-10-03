"""Synthetic C01–C20 replays. These bodies were not recorded from a live provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.llm_gateway.adapters.anthropic import parse_anthropic
from app.llm_gateway.adapters.gemini import parse_gemini
from app.llm_gateway.adapters.openai import parse_openai
from app.llm_gateway.types import LLMResponse

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "llm_gateway"
FAMILIES = ("anthropic", "openai", "gemini")
PARSERS = {
    "anthropic": parse_anthropic,
    "openai": parse_openai,
    "gemini": parse_gemini,
}
BLOCKING = tuple(f"C{index:02d}" for index in range(1, 21) if index not in {11, 18, 19})
SCORED_IDS = ("C11", "C18", "C19")
REPLAYED = {
    "anthropic": (
        "C01",
        "C02",
        "C03",
        "C04",
        "C05",
        "C06",
        "C09",
        "C12",
        "C15",
        "C20",
    ),
    "openai": ("C01", "C02", "C03", "C04", "C05", "C06", "C09", "C12", "C15"),
    "gemini": (
        "C01",
        "C02",
        "C03",
        "C04",
        "C05",
        "C06",
        "C09",
        "C12",
        "C15",
        "C20",
    ),
}
# Response parsers cannot express these. A skip is not a pass.
GLOBAL_SKIP = {
    "C07": (
        "tool_choice is applied before a response exists. parse_anthropic, "
        "parse_openai, and parse_gemini do not read it."
    ),
    "C08": (
        "Strict schema over N=200 is a generation trial, not one response body. "
        "parse_anthropic and parse_gemini copy objects. parse_openai rejects "
        "unparseable JSON only, not a schema violation."
    ),
    "C10": (
        "Streaming equality compares assemble(events) with a non-stream complete. "
        "parse_* reads one finished body."
    ),
    "C13": (
        "Error kinds are mapped from HTTP status by anthropic_error, openai_error, "
        "and gemini_error. parse_* does not see that status."
    ),
    "C14": "None of the three parsers copy reasoning onto LLMResponse.reasoning.",
    "C16": "Cancel mid-stream is an in-flight abort. A finished body has no cancel signal.",
    "C17": (
        "Ten parallel requests are ten transports. One parsed body is not that run. "
        "Left skipped so a single canned completion cannot fake a pass."
    ),
}
FAMILY_SKIP = {
    "openai": {
        "C20": (
            "parse_openai returns tool_calls, max_tokens, or end. It does not read "
            "refusal or content_filter from the body."
        ),
    },
}


def _end(text: str) -> dict[str, Any]:
    return {"stop_reason": "end", "text": text, "tool_calls": []}


def _stop(reason: str, text: str) -> dict[str, Any]:
    return {"stop_reason": reason, "text": text, "tool_calls": []}


def _call(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"id": call_id, "name": "describe_model", "args": args}


def _tools(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stop_reason": "tool_calls", "text": "", "tool_calls": calls}


_MODEL = {"model": "sale.order"}
_NESTED = {
    "model": "sale.order",
    "nested": {"name": "x"},
    "tags": ["draft", "sent"],
    "state": "sale",
    "choice": {"kind": "partner", "id": "res.partner"},
}
_UNICODE = {"model": "販売 🚀", "note": 'quote:"x"'}
_SHARED = {
    "C01": [_end("hello")],
    "C02": [_tools([_call("c2", _MODEL)])],
    "C03": [_tools([_call("c3", _NESTED)])],
    "C04": [_tools([_call("c4", _MODEL)]), _end("done")],
    "C05": [_end("step-0"), _end("step-1"), _end("step-2")],
    "C06": [_tools([_call("p1", {"model": "a"}), _call("p2", {"model": "b"})])],
    "C09": [_end('{"ok": true}')],
    "C12": [_stop("max_tokens", "cut")],
    "C15": [_tools([_call("u", _UNICODE)])],
}


def expected_views(family: str, case_id: str) -> list[dict[str, Any]]:
    if case_id == "C20" and family == "anthropic":
        return [_stop("refusal", "no"), _stop("content_filter", "")]
    if case_id == "C20" and family == "gemini":
        return [_stop("content_filter", "")]
    return _SHARED[case_id]


def _load(family: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / f"{family}.json").read_text(encoding="utf-8"))
    assert payload["label"] == "synthetic replay"
    assert payload["provenance"] == "synthetic_replay"
    assert payload["recorded_from_live_provider"] is False
    assert payload["parser"] == f"parse_{family}"
    return payload


def _view(parsed: LLMResponse) -> dict[str, Any]:
    return {
        "stop_reason": parsed.stop_reason,
        "text": parsed.text,
        "tool_calls": [
            {"id": call.id, "name": call.name, "args": call.args} for call in parsed.tool_calls
        ],
    }


def compare_bodies(
    family: str,
    case_id: str,
    bodies: list[dict[str, Any]],
    expects: list[dict[str, Any]],
) -> list[str]:
    if len(bodies) != len(expects):
        return [f"{family} {case_id}: {len(bodies)} bodies, {len(expects)} expects"]
    parser = PARSERS[family]
    failures: list[str] = []
    for index, (body, expect) in enumerate(zip(bodies, expects, strict=True)):
        actual = _view(parser(body))
        if actual != expect:
            failures.append(f"{family} {case_id}[{index}]: {actual!r} != {expect!r}")
    return failures


def replay_failures() -> list[str]:
    failures: list[str] = []
    for family in FAMILIES:
        payload = _load(family)
        assert set(payload["cases"]) == set(REPLAYED[family])
        for case_id in REPLAYED[family]:
            failures.extend(
                compare_bodies(
                    family,
                    case_id,
                    payload["cases"][case_id]["bodies"],
                    expected_views(family, case_id),
                )
            )
    return failures


def scored_case_report() -> dict[str, dict[str, Any]]:
    """Scores only. Callers must not treat a low score as a suite failure."""
    return {
        "C11": {
            "score": 0,
            "blocks": False,
            "reason": (
                "Long-context needle at 50% of the window needs a live context window. "
                "A short synthetic body that contains the needle would fake a hit."
            ),
        },
        "C18": {
            "score": 0,
            "blocks": False,
            "reason": (
                "Vision needs image input and a model that can see. "
                "parse_* does not read image parts."
            ),
        },
        "C19": {
            "score": 0,
            "blocks": False,
            "status": "informational",
            "reason": (
                "Injection inside a tool result is model behavior. The parsers do not score it."
            ),
        },
    }


def test_fixtures_are_labeled_synthetic_replay_not_a_live_recording() -> None:
    names = {FIXTURE_DIR / f"{family}.json" for family in FAMILIES}
    assert set(FIXTURE_DIR.glob("*.json")) == names
    for family in FAMILIES:
        payload = _load(family)
        assert "live provider" in payload["note"]
        assert "Not a cassette recorded" in payload["note"]


def test_synthetic_replays_match_parse_anthropic_openai_and_gemini() -> None:
    assert replay_failures() == []


def test_a_blocking_replay_miss_fails_the_check() -> None:
    payload = _load("anthropic")
    bodies = payload["cases"]["C01"]["bodies"]
    missed = [{"stop_reason": "end", "text": "goodbye", "tool_calls": []}]
    assert compare_bodies("anthropic", "C01", bodies, missed)


def test_blocking_cases_are_replayed_or_skipped_with_a_reason() -> None:
    """Replay parse_anthropic, parse_openai, and parse_gemini over synthetic bodies.

    The fixtures are hand-authored. They are not cassettes recorded from a live
    provider. Cassette recording stays a manual operator step.

    A blocking case fails this suite when its replay is present and the parser
    output misses the expected view. A case that cannot be expressed as a
    response body is skipped with a reason. A skip is not a pass.

    Skipped on every family:
    C07 tool_choice is applied before a response exists. The parsers ignore it.
    C08 Strict schema over N=200 is a generation trial, not one body.
        parse_anthropic and parse_gemini copy objects. parse_openai rejects
        unparseable JSON only, not a schema violation.
    C10 Streaming equality is assemble(events) against a non-stream complete.
        parse_* reads one finished body.
    C13 Error kinds come from HTTP status helpers, not from parse_*.
    C14 None of the parsers copy reasoning onto LLMResponse.reasoning.
    C16 Cancel mid-stream is an in-flight abort. A finished body has no cancel.
    C17 Ten parallel requests are ten transports. One parsed body is not that.
        Left skipped. Not faked as a pass.

    Skipped on OpenAI only:
    C20 parse_openai returns tool_calls, max_tokens, or end. It does not read
        refusal or content_filter.

    Scored, and a low score does not fail the suite:
    C11 Long-context needle at 50% of the window needs a live context window.
        The recorded score is 0. A short body containing the needle would fake a hit.
    C18 Vision needs image input and a model that can see. parse_* does not
        read image parts. The recorded score is 0.
    C19 Injection inside a tool result is model behavior. Recorded as
        informational with score 0.

    Partial replays, not full case claims:
    C01 is a plain completion body. System adherence is not claimed.
    C03 keeps a nested object, an array, an enum string, and a union-shaped
        object. It does not run a schema validator.
    C04 and C05 are ordered synthetic bodies, not a live tool loop.
    Gemini C20 replays the SAFETY filter surface only. A distinct refusal stop
        is not a Gemini finish reason in the parser map.
    """
    assert replay_failures() == []
    for family in FAMILIES:
        skips = {**GLOBAL_SKIP, **FAMILY_SKIP.get(family, {})}
        for case_id in BLOCKING:
            replayed = case_id in REPLAYED[family]
            if replayed:
                assert case_id not in skips
            else:
                assert skips[case_id]
        assert set(REPLAYED[family]).isdisjoint(SCORED_IDS)
        assert set(_load(family)["cases"]).isdisjoint(SCORED_IDS)


def test_scored_cases_record_a_score_and_a_low_score_does_not_fail() -> None:
    """C11, C18, and C19 record a score. This test has no minimum score.

    C11 stays at 0 because a long-context needle at 50% of the window needs a
    live recording. C17 is blocking in the table and is skipped, not scored,
    because ten parallel requests are not one response body.
    """
    scores = scored_case_report()
    assert set(scores) == set(SCORED_IDS)
    for case_id in SCORED_IDS:
        assert scores[case_id]["blocks"] is False
        assert scores[case_id]["score"] == 0
    assert scores["C19"]["status"] == "informational"
