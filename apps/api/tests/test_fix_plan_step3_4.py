"""Fix plan steps 3-4: design knobs (default = unchanged), evidence/folded schema, python gate, orphan audit."""
from app.ai_conversation import app_design as ad
from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel
from app.ai_conversation.model_authorizer import (
    apply_python_gate, authorize_models, authorize_python, orphan_requirements,
)


def test_default_prompt_unchanged_and_v2_replaces_licenses(monkeypatch):
    for k in ("INGENIUM_DESIGN_RULES", "INGENIUM_DESIGN_GAPFILL", "INGENIUM_DESIGN_BUDGET"):
        monkeypatch.delenv(k, raising=False)
    v1 = ad.design_system_prompt()
    assert ad.GAP_FILL_SENTENCE in v1 and "HARD RULES" not in v1
    assert "Design budget: at most 4 new models." in ad.design_user_prompt("x", budget=4)
    monkeypatch.setenv("INGENIUM_DESIGN_GAPFILL", "drop")
    assert ad.GAP_FILL_SENTENCE not in ad.design_system_prompt()
    monkeypatch.setenv("INGENIUM_DESIGN_BUDGET", "none")
    assert "Design budget" not in ad.design_user_prompt("x", budget=4)
    monkeypatch.setenv("INGENIUM_DESIGN_RULES", "v2")
    v2 = ad.design_system_prompt()
    assert "HARD RULES" in v2 and "alert rules get their own model" not in v2 and "genuinely new concepts" not in v2
    u = ad.design_user_prompt("x", budget=9, intent_contract=[{"id": "R1", "role": "record"}, {"id": "R2", "role": "attribute"}])
    assert "at most 2 new models" in u and '"evidence"' in u and '"folded"' in u


def test_evidence_and_folded_round_trip():
    d = AppDesign.from_dict({"new_models": [{"name": "x_a", "label": "A", "evidence": {"quote": "q", "owner_fields": ["f"], "role": "main_record"}}],
                             "folded": [{"concept": "type", "quote": "which type", "as": "selection", "on": "x_a"}]})
    assert d.new_models[0].evidence["role"] == "main_record" and d.folded[0]["as"] == "selection"
    assert AppDesign.from_dict(d.to_dict()).new_models[0].evidence["quote"] == "q"


def test_python_gate_keeps_scheduled_and_option_a_only():
    d = AppDesign(new_models=[], intent_contract=[{"id": "R1", "decision": "option_a"}, {"id": "R2", "decision": "metadata"}])
    d.python_needed = [{"key": "a", "label": "Nightly reminder", "kind": "cron"},
                       {"key": "b", "label": "Score", "kind": "computed", "requirement_id": "R1"},
                       {"key": "c", "label": "Total spent", "kind": "computed", "requirement_id": "R2"}]
    dec = authorize_python(d)
    assert [x["item"] for x in dec] == ["Total spent"]
    apply_python_gate(d, dec)
    assert [p["key"] for p in d.python_needed] == ["a", "b"] and d.left_out[-1]["status"] == "declined"


def test_orphan_audit():
    m = DesignModel(name="x_job", label="Job", requirement_ids=["R1"], fields=[DesignField(name="x_plate", string="Plate", requirement_ids=["R2"])])
    d = AppDesign(new_models=[m], intent_contract=[{"id": "R1", "decision": "metadata", "kind": "model"},
                                                   {"id": "R2", "decision": "metadata", "kind": "field"},
                                                   {"id": "R3", "decision": "stock_automation", "kind": "automation"},
                                                   {"id": "R4", "decision": "clarify", "kind": "field"}])
    assert [r["id"] for r in orphan_requirements(d)] == ["R3"]


def test_suggested_not_built_under_flip():
    m = DesignModel(name="x_job", label="Job card", suggested=True, fields=[DesignField(name="x_name", string="Name"),
                    DesignField(name="x_plate", string="Car plate"), DesignField(name="x_km", string="Mileage")])
    d = AppDesign(new_models=[m])
    brief = "Each job card has the car plate and the mileage."
    assert authorize_models(d, brief=brief).calls[0].verdict.startswith("keep")
    assert authorize_models(d, brief=brief, suggested_not_built=True).calls[0].verdict == "suggest"
