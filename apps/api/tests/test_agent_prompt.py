"""T8-PROMPT: runtime context budgets, compaction, and prefix scrubbing.

Turns are recorded on the agent runtime. ``build_context`` compacts that
transcript. This file does not call a model provider, and it does not mark
GATE-P4-07 in the progress log.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.agent_runtime.prompt import (
    SHIPPED_OVERLAYS,
    STATIC_PREFIX_TARGET,
    Exchange,
    ExplorerTierDenied,
    PromptRejected,
    ToolExchange,
)
from app.agent_runtime.runtime import AgentRuntime

pytestmark = pytest.mark.no_app_db

_WINDOW = 4_000
_SECRET = "db-secret-value"
_EMAIL = "ada@example.com"
_PHONE = "415-555-0199"
_SSN = "123-45-6789"
_KEY = "sk-abcdef1234567890"
_SENTINEL = "payload-sentinel"


def _len_tokens(text: str) -> int:
    """Fake counter: one token per character. Not a provider tokenizer."""
    return len(text)


def _plan(runtime: AgentRuntime):
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    runtime.complete_phase(state, "PLAN")
    state.facts.append({"evidence_id": "evidence-run", "assumption": "stated-in-run-state"})
    return state


def _assert_pairs(messages: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> None:
    pending: list[str] | None = None
    for message in messages:
        role = message.get("role")
        calls = message.get("tool_calls")
        if role == "assistant" and calls:
            assert pending is None
            pending = [str(call["id"]) for call in calls]
            continue
        if role == "tool":
            assert pending, "tool result has no matching call"
            assert message["tool_call_id"] == pending.pop(0)
            if not pending:
                pending = None
            continue
        assert pending is None, "a message split a tool-call pair"
    assert pending is None


def test_thirty_turn_context_keeps_tool_pairs_and_run_state() -> None:
    """Thirty recorded turns compact without splitting a tool-call pair.

    Evidence, assumptions, and phase stay on the state card. The cacheable
    prefix is not that card. Budgets use the fake character counter.
    """
    runtime = AgentRuntime()
    state = _plan(runtime)
    for index in range(29):
        runtime.record_exchange(
            state,
            Exchange(
                user="u" * 80,
                assistant="a" * 40,
                tools=(
                    ToolExchange(
                        call_id=f"call_{index:04d}",
                        name="schema_search",
                        args={"query": f"q{index}"},
                        result={"body": "r" * 80},
                    ),
                ),
                assumption=f"a{index:02d}",
                evidence_id=f"e{index:02d}",
            ),
        )
    runtime.record_exchange(
        state,
        Exchange(
            user="u" * 80,
            assistant="a" * 40,
            tools=(
                ToolExchange(
                    call_id="call_0029a",
                    name="schema_search",
                    args={"query": "last"},
                    result={"body": "r" * 80, "marker": _SENTINEL},
                ),
                ToolExchange(
                    call_id="call_0029b",
                    name="describe_model",
                    args={"model": "sale.order"},
                    result={"body": "r" * 80},
                ),
            ),
            assumption="a29",
            evidence_id="e29",
        ),
    )
    context = runtime.build_context(
        state,
        window_tokens=_WINDOW,
        count_tokens=_len_tokens,
        tools=(
            {"name": "schema_search", "description": "find models"},
            {"name": "describe_model", "description": "read fields"},
        ),
        skills="s" * 2_000,
        memory="TENANT-MEMORY-MARKER " + ("m" * 500),
        overlay="Prefer stock fields when one already exists.",
        secrets=(_SECRET,),
    )

    soft = _WINDOW * 60 // 100
    hard = _WINDOW * 90 // 100
    prefix_cap = min(STATIC_PREFIX_TARGET, _WINDOW * 15 // 100)
    assert context.pre_compact_tokens > soft
    assert context.compacted is True
    assert context.dropped_turns > 0
    assert 1 <= context.kept_turns < 30
    assert context.total_tokens <= soft
    assert context.total_tokens <= hard
    assert context.system_tools_tokens <= _WINDOW * 15 // 100
    assert context.skills_tokens <= _WINDOW * 15 // 100
    assert context.memory_tokens <= _WINDOW * 5 // 100
    assert context.history_tokens <= _WINDOW * 40 // 100
    assert context.tool_result_tokens <= _WINDOW * 25 // 100
    assert context.overlay_tokens <= prefix_cap * 10 // 100
    assert "call_0000" not in context.kept_call_ids
    assert context.kept_call_ids[-2:] == ("call_0029a", "call_0029b")
    _assert_pairs(context.messages)

    rendered = json.dumps(context.messages)
    assert "call_0000" not in rendered
    assert "call_0029a" in rendered
    assert "call_0029b" in rendered
    state_text = next(
        message["content"] for message in context.messages if message.get("layer") == "state"
    )
    for index in range(30):
        assert f"a{index:02d}" in state_text
        assert f"e{index:02d}" in state_text
    assert "phase: PLAN" in state_text
    assert "status: running" in state_text
    assert "stated-in-run-state" in state_text
    assert "evidence-run" in state_text
    assert "stated-in-run-state" not in context.cached_prefix
    assert "evidence-run" not in context.cached_prefix
    assert _SENTINEL not in context.cached_prefix
    assert "TENANT-MEMORY-MARKER" not in context.cached_prefix
    assert "TENANT-MEMORY-MARKER" in rendered
    prefix = next(message for message in context.messages if message.get("cache") is True)
    assert prefix["content"] == context.cached_prefix
    assert prefix["layer"] == "prefix"
    assert [message.get("cache") for message in context.messages].count(True) == 1
    describe_at = context.cached_prefix.index("describe_model:")
    search_at = context.cached_prefix.index("schema_search:")
    assert describe_at < search_at
    for message in context.messages:
        if message["role"] == "system":
            assert "untrusted_data" not in message["content"]
            assert _SENTINEL not in message["content"]
    tool_body = next(
        message["content"]
        for message in context.messages
        if message["role"] == "tool" and message["tool_call_id"] == "call_0029a"
    )
    assert _SENTINEL in tool_body
    assert "untrusted_data" in tool_body


def test_cached_prefix_scrubs_secrets_and_pii() -> None:
    runtime = AgentRuntime()
    state = _plan(runtime)
    runtime.record_exchange(
        state,
        Exchange(
            user="look up the contact",
            assistant="reading the tool result",
            tools=(
                ToolExchange(
                    call_id="call_pii",
                    name="schema_search",
                    args={"query": "partner"},
                    result={"note": f"customer {_EMAIL}"},
                ),
            ),
            assumption="a00",
            evidence_id="e00",
        ),
    )
    overlay = (
        f"Reach {_EMAIL} at {_PHONE}. ssn {_SSN} key {_KEY} secret {_SECRET} "
        + ("padding " * 40)
    )
    context = runtime.build_context(
        state,
        window_tokens=_WINDOW,
        count_tokens=_len_tokens,
        tools=({"name": "schema_search", "description": "find models"},),
        overlay=overlay,
        secrets=(_SECRET,),
    )
    prefix = context.cached_prefix
    for planted in (_EMAIL, _PHONE, _SSN, _KEY, _SECRET):
        assert planted not in prefix
    assert "[redacted]" in prefix
    tool_body = next(
        message["content"] for message in context.messages if message["role"] == "tool"
    )
    assert _EMAIL in tool_body
    assert _EMAIL not in prefix
    cached = [message for message in context.messages if message.get("cache") is True]
    assert len(cached) == 1
    assert cached[0]["content"] == prefix


def test_production_refuses_a_runtime_edited_prompt_before_counting() -> None:
    runtime = AgentRuntime()
    state = runtime.start()
    calls = {"n": 0}

    def count(text: str) -> int:
        calls["n"] += 1
        return len(text)

    with pytest.raises(PromptRejected):
        runtime.build_context(
            state,
            window_tokens=_WINDOW,
            count_tokens=count,
            overlay="edited at runtime",
            production=True,
        )
    assert calls["n"] == 0
    assert "edited at runtime" not in SHIPPED_OVERLAYS


def test_explorer_subrun_requires_tier_a_before_counting() -> None:
    runtime = AgentRuntime()
    state = runtime.start()
    calls = {"n": 0}

    def count(text: str) -> int:
        calls["n"] += 1
        return len(text)

    with pytest.raises(ExplorerTierDenied):
        runtime.build_context(
            state,
            window_tokens=_WINDOW,
            count_tokens=count,
            explorer=True,
            tier="B",
        )
    assert calls["n"] == 0
    context = runtime.build_context(
        state,
        window_tokens=_WINDOW,
        count_tokens=count,
        explorer=True,
        tier="A",
    )
    assert context.kept_turns == 0
    assert calls["n"] > 0
