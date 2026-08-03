"""Tests for AI-3 self-consistency vote/merge (deterministic fakes, no live LLM)."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.ai_domain_packs import retrieve_domain_pack  # noqa: E402
from app.ai_self_consistency import (  # noqa: E402
    merge_workflow_states,
    self_consistency_enabled,
    vote_pack_id,
)
from app.settings import settings  # noqa: E402


def test_self_consistency_off_by_default() -> None:
    settings.ai_self_consistency = "off"
    assert self_consistency_enabled() is False


def test_vote_pack_id_majority() -> None:
    winner, warnings = vote_pack_id(
        ["law_firm", "law_firm", "clinic"],
        {"law_firm": 0.9, "clinic": 0.4},
    )
    assert winner == "law_firm"
    assert any("split" in w for w in warnings)


def test_vote_pack_id_tie_breaks_on_score() -> None:
    winner, warnings = vote_pack_id(
        ["law_firm", "clinic", "law_firm", "clinic"],
        {"law_firm": 0.95, "clinic": 0.2},
    )
    assert winner == "law_firm"
    assert any("tie" in w for w in warnings)


def test_merge_workflow_states_keeps_majority_and_transitions() -> None:
    samples = [
        {
            "states": [
                {"value": "draft", "label": "Draft"},
                {"value": "open", "label": "Open"},
                {"value": "done", "label": "Done"},
            ],
            "transitions": [["draft", "open"], ["open", "done"]],
        },
        {
            "states": [
                {"value": "draft", "label": "Draft"},
                {"value": "open", "label": "Open"},
                {"value": "cancelled", "label": "Cancelled"},
            ],
            "transitions": [["draft", "open"], ["open", "cancelled"]],
        },
        {
            "states": [
                {"value": "draft", "label": "Draft"},
                {"value": "open", "label": "Open"},
                {"value": "done", "label": "Done"},
            ],
            "transitions": [["draft", "open"], ["open", "done"]],
        },
    ]
    merged, warnings = merge_workflow_states(samples)
    values = [s["value"] for s in merged["states"]]
    assert values[:2] == ["draft", "open"]
    assert "done" in values
    assert ["draft", "open"] in merged["transitions"]
    assert warnings


def test_retrieve_domain_pack_unchanged_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.ai_self_consistency = "off"

    class _ShouldNotCall:
        def generate_json(self, *args: Any, **kwargs: Any) -> str:
            raise AssertionError("LLM should not run when self_consistency=off")

    hit = retrieve_domain_pack("car rental fleet management", provider=_ShouldNotCall())
    assert hit is not None
    assert hit[0] == "car_rental"


def test_llm_vote_domain_pack_seeded(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_self_consistency import llm_vote_domain_pack

    settings.ai_self_consistency = "on"
    responses = [
        '{"pack_id":"law_firm"}',
        '{"pack_id":"clinic"}',
        '{"pack_id":"law_firm"}',
    ]

    class _FakeProvider:
        name = "fake"

        def __init__(self) -> None:
            self.i = 0

        def generate_json(self, *args: Any, **kwargs: Any) -> str:
            out = responses[self.i % len(responses)]
            self.i += 1
            assert kwargs.get("temperature") == 0.5
            return out

    winner, warnings = llm_vote_domain_pack(
        "legal matter management",
        _FakeProvider(),
        pack_ids=["law_firm", "clinic", "car_rental"],
        pack_summaries=["law", "clinic", "cars"],
        retrieval_scores={"law_firm": 0.5, "clinic": 0.9},
    )
    assert winner == "law_firm"
    assert warnings
