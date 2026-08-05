"""Tests for LLM JSON repair helpers."""

from __future__ import annotations

import pytest

from app.llm_json import parse_llm_json_object, repair_json_text


def test_repair_trailing_comma() -> None:
    raw = '{"technical_name":"demo","models":[{"model":"x_a","fields":[],},],}'
    fixed = repair_json_text(raw)
    draft = parse_llm_json_object(fixed)
    assert draft["technical_name"] == "demo"


def test_parse_markdown_fence() -> None:
    raw = '```json\n{"technical_name":"demo","models":[{"model":"x_a","fields":[]}]}\n```'
    draft = parse_llm_json_object(raw)
    assert draft["technical_name"] == "demo"


def test_parse_friendly_error() -> None:
    with pytest.raises(ValueError, match="malformed JSON"):
        parse_llm_json_object("{not json at all")
