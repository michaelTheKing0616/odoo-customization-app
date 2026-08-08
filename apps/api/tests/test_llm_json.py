"""Tests for LLM JSON repair helpers."""

from __future__ import annotations

import pytest

from app.llm_json import parse_llm_json_object, repair_json_text


def test_repair_trailing_comma() -> None:
    raw = '{"technical_name":"demo","models":[{"model":"x_a","fields":[],},],}'
    fixed = repair_json_text(raw)
    draft = parse_llm_json_object(fixed)
    assert draft["technical_name"] == "demo"


def test_repair_missing_comma_between_properties() -> None:
    raw = (
        '{"missing_models":[{"model":"x_a","description":"A" "fields":[]}]'
        ' "missing_fields":[{"model":"x_b","name":"x_name","ttype":"char"}]}'
    )
    draft = parse_llm_json_object(raw)
    assert draft["missing_models"][0]["model"] == "x_a"
    assert draft["missing_fields"][0]["model"] == "x_b"


def test_parse_markdown_fence() -> None:
    raw = '```json\n{"technical_name":"demo","models":[{"model":"x_a","fields":[]}]}\n```'
    draft = parse_llm_json_object(raw)
    assert draft["technical_name"] == "demo"


def test_parse_friendly_error() -> None:
    with pytest.raises(ValueError, match="malformed JSON"):
        parse_llm_json_object("{not json at all")


def test_strip_thinking_preamble_before_json() -> None:
    from app.llm_provider import strip_thinking_trace

    raw = 'Here is the draft:\n{"technical_name":"demo","models":[{"model":"x_a","fields":[]}]}'
    assert strip_thinking_trace(raw).startswith("{")
