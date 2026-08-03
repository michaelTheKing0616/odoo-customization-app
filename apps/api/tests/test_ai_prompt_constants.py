"""Tests for Doc 4 prompt constants — temperatures, exemplar adjacency, anti-patterns."""

from __future__ import annotations

from app.ai_prompt_constants import (
    ANTI_PATTERN_BLOCK,
    FEW_SHOT_EXEMPLAR_SOURCE_PACK,
    STEP_TEMPERATURES,
    append_prompt_blocks,
    few_shot_exemplar_block,
    output_only_json_line,
)


def test_step_temperature_table_has_expected_keys() -> None:
    assert STEP_TEMPERATURES["pipeline.entities"] == 0.6
    assert STEP_TEMPERATURES["pipeline.fields"] == 0.15
    assert STEP_TEMPERATURES["pipeline.automations"] == 0.6
    assert STEP_TEMPERATURES["single_pipeline"] == 0.3
    assert STEP_TEMPERATURES["critique"] == 0.15


def test_append_prompt_blocks_includes_json_and_vocab() -> None:
    out = append_prompt_blocks("Base system.", guardrail="PROTECTED MODULES")
    assert "Base system." in out
    assert output_only_json_line() in out
    assert "Allowed ttypes" in out
    assert ANTI_PATTERN_BLOCK.splitlines()[0] in out
    assert "PROTECTED MODULES" in out


def test_few_shot_exemplar_skips_matched_car_rental_pack() -> None:
    assert FEW_SHOT_EXEMPLAR_SOURCE_PACK == "car_rental"
    assert few_shot_exemplar_block("car_rental") is None
    blob = few_shot_exemplar_block("law_firm")
    assert blob and "x_ex_staff" in blob
