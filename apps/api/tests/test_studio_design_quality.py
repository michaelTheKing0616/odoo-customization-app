"""Design quality repair + honest fallback for the Customer Health brief (no network)."""
from pathlib import Path

from app.ai_conversation.app_design import _fallback_reason, build_app_design

BRIEF = (Path(__file__).parent / "fixtures" / "customer_health_brief.md").read_text()


def _design():
    return build_app_design(BRIEF, use_llm=False, title="Customer Health & Retention Intelligence")


def test_lists_are_not_free_text_and_records_added():
    d = _design()
    by = {m.name: m for m in d.new_models}
    rule = {f.name: f.ttype for f in by["x_health_score_rule"].fields}
    assert rule["x_signal"] == "selection" and rule["x_operator"] == "selection"
    assert rule["x_window_days"] == "integer" and "x_conditions" not in rule
    assert "x_health_score_factor" in by and "x_recommended_action" in by and "x_alert_rule" in by
    plan = {f.name: (f.ttype, f.relation) for f in by["x_customer_success_plan"].fields}
    assert plan["x_owner_ids"] == ("many2many", "res.users") and "x_milestones" not in plan
    renewal = {f.name: (f.ttype, f.relation) for f in by["x_renewal"].fields}
    assert renewal["x_sale_order_id"] == ("many2one", "sale.order")
    partner = next(e for e in d.stock_extensions if e.model == "res.partner")
    names = {f.name for f in partner.fields}
    assert {"x_health_score", "x_health_status", "x_success_manager_id", "x_renewal_date"} <= names
    assert len(d.new_models) <= 12
    assert not [f for m in d.new_models for f in m.fields if f.ttype == "text" and f.string.lower() in {"conditions", "operators", "owners", "milestones", "tasks"}]


def test_fallback_reason_is_plain():
    assert "usage limit" in _fallback_reason({"status": "failed", "error": "Gemini HTTP 429 quota"})
    assert "too long" in _fallback_reason({"status": "timed_out"})
    assert "busy" in _fallback_reason({"status": "failed", "error": "HTTP 503 high demand"})


def test_duplicate_fields_same_meaning_are_dropped():
    from app.ai_conversation.app_design import AppDesign, DesignField, StockExtension
    from app.ai_conversation.design_quality import dedupe_fields

    ext = StockExtension(model="res.partner", fields=[
        DesignField(name="x_success_manager_id", string="Success manager", ttype="many2one", relation="res.users"),
        DesignField(name="x_csm_user_id", string="CSM", ttype="many2one", relation="res.users"),
        DesignField(name="x_renewal_date", string="Renewal date", ttype="date"),
        DesignField(name="x_next_renewal_date", string="Next renewal date", ttype="date"),
        DesignField(name="x_health_previous_score", string="Previous score", ttype="float"),
        DesignField(name="x_previous_health_score", string="Previous health score", ttype="float"),
        DesignField(name="x_health_score", string="Health score", ttype="float"),
    ])
    d = AppDesign(stock_extensions=[ext])
    notes = dedupe_fields(d)
    assert [f.name for f in ext.fields] == [
        "x_success_manager_id", "x_renewal_date", "x_health_previous_score", "x_health_score"]
    assert len(notes) == 3


def test_section_record_ai_missed_is_added_not_dropped():
    from app.ai_conversation.app_design import (
        AppDesign, DesignField, DesignModel, _cover_sections, outline_from_brief)

    ai = AppDesign(source="llm", new_models=[
        DesignModel(name="x_health_rule", label="Health Rule", fields=[DesignField(name="x_name", string="Name", ttype="char")]),
        DesignModel(name="x_health_history", label="Health History", fields=[DesignField(name="x_name", string="Name", ttype="char")]),
    ])
    out = _cover_sections(ai, outline_from_brief(BRIEF), None, packet=None, prompt=BRIEF)
    names = out.model_names
    assert "x_renewal" in names and "x_health_score_history" not in names
    assert any("missed" in n for n in out.notes)


def test_expansion_words_do_not_add_templated_records():
    """Holdout root cause: 'alerts'/'customer form' came from the AI expansion of a terse brief, not the owner."""
    from app.ai_conversation.brief_checklist import reset_original, set_original
    from app.ai_conversation.design_quality import strengthen_design
    from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel

    def design():
        return AppDesign(app_name="Stock", new_models=[DesignModel(name="x_count", label="Count",
                                                                   fields=[DesignField(name="x_name", string="Name", ttype="char")])])
    expanded = "Weekly stock count in 3 shops. Shortage alerts to managers. Add a section to the customer form."
    tok = set_original("count stock in 3 shops weekly, flag shortages.")
    try:
        d = design(); strengthen_design(d, expanded)
        assert not any(m.label == "Alert Rule" for m in d.new_models)
        assert not any(e.model == "res.partner" for e in d.stock_extensions)
    finally:
        reset_original(tok)
    tok = set_original(expanded)  # the owner really asked: the repair still happens
    try:
        d = design(); strengthen_design(d, expanded)
        assert any(m.label == "Alert Rule" for m in d.new_models)
    finally:
        reset_original(tok)
