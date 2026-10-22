"""GND-STUDIO evidence: App Studio design/contract prompts carry the live schema."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_conversation.app_design import (
    DesignModel,
    _call_intent_contract,
    _llm_support,
    design_user_prompt,
    intent_contract_user_prompt,
)

pytestmark = pytest.mark.no_app_db


class _Snap:
    ok = True

    def digest(self, budget_chars: int = 7000) -> str:
        return "LIVE-DIGEST res.partner: x_tier:selection"


PACKET = SimpleNamespace(models={"res.partner": SimpleNamespace(fields={"x_tier": {"type": "selection"}})})


def test_contract_and_design_prompts_include_live_snapshot() -> None:
    assert "LIVE-DIGEST" in intent_contract_user_prompt("Track tiers.", None, PACKET, _Snap())
    assert "LIVE-DIGEST" in design_user_prompt("Track tiers.", None, PACKET, snapshot=_Snap())


def test_contract_call_sends_snapshot_and_binds_unknown_targets_out() -> None:
    seen: list[str] = []

    class P:
        name = model = "fake"

        def generate_json(self, prompt: str, *, system: str = "", **_: Any) -> str:
            seen.append(prompt)
            if system.startswith("You verify"):
                return json.dumps({"verdicts": []})
            return json.dumps({"requirements": []})

    rows, _meta = _call_intent_contract(P(), "Track tiers.", None, schema_packet=PACKET, snapshot=_Snap())
    assert rows == [] and "LIVE-DIGEST" in seen[0]


def test_supporting_model_suggestions_cannot_name_stock_relations(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.llm_provider as lp

    class P:
        name = model = "fake"

        def generate_json(self, prompt: str, **_: Any) -> str:
            return json.dumps({"models": [{"kind": "lines", "label": "Line", "fields": [
                {"name": "x_qty", "type": "float", "string": "Qty"},
                {"name": "x_invented_id", "type": "many2one", "relation": "x.invented", "string": "Bad"},
            ]}]})

    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: P())
    main = DesignModel(name="x_policy", label="Policy")
    (line,) = _llm_support("Policy file with line items.", main)
    assert all(f.relation != "x.invented" for f in line.fields)
