"""Bug 4 decision: named-residual briefs get AI-SUGGESTED supporting models (flagged, removable)."""

from __future__ import annotations

import json
from typing import Any

import pytest

import test_studio_step3_design_build as S3  # noqa: F401 — sets env defaults
from app.ai_conversation.grounding import reset_grounding, set_grounding
from app.ai_conversation.intent_llm import reset_intent_llm_override, set_intent_llm_override
from test_ai_honesty_ir_independent import POLICY_PLUS_STOCK, POS_STOCK_FIRST, _close_ai_off
from test_studio_step2a_app_design import GROUNDING

pytestmark = pytest.mark.no_app_db

POLICY = "Insurance brokerage. Custom residual is the policy file. Quotations and customer invoices."
PLAIN = "Custom residual is the policy file with a name and start date."
PREFER = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window. "
    "Do not create a new app — inherit sale.order."
)
SUGGESTIONS = {
    "models": [
        {"kind": "parties", "label": "Policy Party", "why": "Insured people and beneficiaries on the policy."},
        {"kind": "lines", "label": "Coverage Line", "why": "Each cover, limit and premium on the policy."},
        {"kind": "invoices", "label": "Parallel Invoice", "why": "must be dropped"},
    ]
}


class _Fake:
    name, model = "gemini", "gemini-2.5-flash"

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail, self.calls = fail, []

    def generate_json(self, prompt: str, *, system: str = "", **kwargs: Any) -> str:
        self.calls.append(system[:20])
        if system.startswith("You suggest"):
            if self.fail is not None:
                raise self.fail
            return json.dumps(SUGGESTIONS)
        return json.dumps({})


def _understand(monkeypatch: pytest.MonkeyPatch, prompt: str, provider: _Fake, *, llm: bool = True) -> dict[str, Any]:
    import app.llm_provider as lp
    from app.ai_conversation.understand import build_understanding, clear_enrich_cache

    clear_enrich_cache()
    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: provider)
    g, i = set_grounding(GROUNDING), set_intent_llm_override(llm)
    try:
        return build_understanding(prompt).to_dict()
    finally:
        reset_intent_llm_override(i)
        reset_grounding(g)


def _new(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m for m in draft.get("models") or []
        if isinstance(m, dict) and str(m.get("model", "")).startswith("x_") and m.get("mode", "new") != "inherit"
    }


def test_llm_suggestions_are_flagged_and_built(monkeypatch: pytest.MonkeyPatch) -> None:
    u = _understand(monkeypatch, POLICY, _Fake())
    design = u["app_design"]
    models = {m["name"]: m for m in design["new_models"]}
    assert set(models) == {"x_policy_file", "x_policy_file_party", "x_policy_file_line"}
    assert not models["x_policy_file"]["suggested"]
    assert models["x_policy_file_party"]["suggested"] and "Insured" in models["x_policy_file_party"]["why"]
    assert models["x_policy_file_line"]["suggested"]
    # suggestions never become brief-named Must-do
    assert not any("party" in c.lower() or "coverage line" in c.lower() for c in u["constraints"])
    draft = S3._generate(monkeypatch, u, prompt=POLICY)["draft"]
    built = _new(draft)
    assert set(built) == set(models)
    assert built["x_policy_file_party"].get("suggested") and not built["x_policy_file"].get("suggested")
    party_link = {f["name"]: f for f in built["x_policy_file_party"]["fields"]}["x_policy_file_id"]
    assert party_link["relation"] == "x_policy_file"


def test_llm_off_and_timeout_use_brief_implied_pattern_only(monkeypatch: pytest.MonkeyPatch) -> None:
    off = _understand(monkeypatch, POLICY_PLUS_STOCK, _Fake(), llm=False)["app_design"]
    assert [m["name"] for m in off["new_models"] if m["suggested"]] == ["x_policy_file_line"]
    assert off["source"] == "outline"
    timed = _understand(monkeypatch, POLICY_PLUS_STOCK, _Fake(fail=TimeoutError("deadline")))["app_design"]
    assert [m["name"] for m in timed["new_models"] if m["suggested"]] == ["x_policy_file_line"]
    # nothing implied -> no suggestions at all
    assert _understand(monkeypatch, PLAIN, _Fake(), llm=False).get("app_design") is None


def test_stock_only_and_prefer_get_no_suggestions(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _understand(monkeypatch, POS_STOCK_FIRST, _Fake()).get("app_design") is None
    prefer = _understand(monkeypatch, PREFER, _Fake())
    assert prefer.get("app_design") is None and prefer["inherit_existing"]
    assert not any(m.get("suggested") for m in _close_ai_off(POS_STOCK_FIRST).get("models") or [])


def test_removed_suggestions_are_not_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    import copy

    from app.ai_conversation.understand import Understanding, apply_understanding_edits

    u = _understand(monkeypatch, POLICY, _Fake())
    edited = copy.deepcopy(u["app_design"])
    edited["new_models"] = [m for m in edited["new_models"] if not m["suggested"]]
    for m in edited["new_models"]:
        m["fields"] = [f for f in m["fields"] if not str(f.get("relation") or "").startswith("x_policy_file_")]
    locked = apply_understanding_edits(Understanding.from_dict(u), {"app_design": edited}).to_dict()
    assert [m["name"] for m in locked["app_design"]["new_models"]] == ["x_policy_file"]
    from app.ai_design_compile import design_applies
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_pipeline import seed_studio_draft

    # one model left: Generate skips the design builder, and the AI-off finish
    # must not re-add what the operator removed
    assert not design_applies(locked["app_design"])
    draft = _finish_seed_draft(POLICY_PLUS_STOCK, seed_studio_draft(POLICY_PLUS_STOCK), [], locked_understanding=locked)
    assert not any(m.get("suggested") for m in draft.get("models") or [])
    assert not any(k.endswith("_line") or k.endswith("_party") for k in _new(draft))


def test_ai_off_finish_flags_suggestion_outside_brief_coverage() -> None:
    from app.ai_domain_nouns import _brief_models

    draft = _close_ai_off(POLICY_PLUS_STOCK)
    new = _new(draft)
    assert set(new) == {"x_policy_file", "x_policy_file_line"}
    assert new["x_policy_file_line"]["suggested"] and draft["_suggested_models"] == ["x_policy_file_line"]
    assert "x_policy_file_line" not in {m.get("model") for m in _brief_models(draft)}
    assert (draft.get("_generate_ir") or {}).get("admitted") is not None
