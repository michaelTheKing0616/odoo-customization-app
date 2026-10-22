from pathlib import Path

from app.ai_conversation.app_design import AppDesign, DesignModel
from app.ai_conversation.design_quality import _f, ensure_brief_duties
from app.ai_conversation.intent_contract import (
    detect_contract_conflicts, normalize_intent_contract, pending_contract_clarification, subject_in_brief)

FX = Path(__file__).parent / "fixtures"


def test_model_metadata_label_alone_is_not_a_conflict():
    brief = (FX / "rental_structured.md").read_text()
    q = "When an inspection is saved with Damage noted = yes, set the asset condition to Needs repair"
    auto = {"id": "a", "kind": "automation", "decision": "stock_automation", "trigger": "event",
            "subject": "Inspection damage alerts and asset status update", "evidence": {"quote": q}}
    field = {"id": "b", "kind": "other", "decision": "metadata", "trigger": "user_entry",
             "subject": "Inspection damage and asset status", "evidence": {"quote": "damage noted (yes/no)"}}
    rows = detect_contract_conflicts([auto, field], brief)
    assert rows[0]["decision"] == "stock_automation"
    manual = dict(field, evidence={"quote": "Staff enter the asset status by hand after each inspection"})
    assert detect_contract_conflicts([auto, manual], brief)[0]["decision"] == "clarify"


def test_technical_subject_matches_its_heading_and_suggestions_do_not_block():
    brief = (FX / "customer_health_brief.md").read_text()
    assert subject_in_brief(brief, "Customer 360 Health Fields on res.partner")["quote"].endswith("Customer 360 Health View")
    rows = normalize_intent_contract([{"kind": "other", "decision": "clarify", "origin": "inferred",
                                       "subject": "Mobile push notifications", "quote": ""}], brief)
    assert pending_contract_clarification(rows, [], {}) is None


def test_casual_brief_duties_become_records_and_automations():
    brief = (FX / "rental_casual.md").read_text()
    eq = DesignModel(name="x_equipment_item", label="Equipment Item", fields=[_f("Name", "char", name="x_name")])
    bk = DesignModel(name="x_rental_booking", label="Rental Booking", fields=[_f("Name", "char", name="x_name")])
    d = AppDesign(app_name="Equipment Rental", new_models=[eq, bk])
    ensure_brief_duties(d, brief)
    assert any(m.label == "Maintenance Log" for m in d.new_models)
    assert any(f.string == "Return Condition" for f in bk.fields)
    assert d.automations and d.automations[0]["automation"]["when"] == "on_write"
    assert any(p["key"] == "service_due_reminder" for p in d.python_needed)


def test_brief_named_duty_authorizes_the_automatic_step():
    brief = (FX / "rental_casual.md").read_text()
    rows = normalize_intent_contract([{"kind": "automation", "decision": "stock_automation", "origin": "inferred",
                                       "subject": "Equipment Service Reminder Activity", "quote": "",
                                       "trigger": "time", "target_model": "x_equipment_item"}], brief)
    assert rows[0]["origin"] == "stated" and "forget" in rows[0]["evidence"]["quote"]
    assert pending_contract_clarification(rows, [], {}) is None


def test_auto_vs_manual_question_is_settled_by_code_as_an_assumption():
    brief = (FX / "rental_structured.md").read_text()
    opts = [{"label": "Fully automatic"}, {"label": "Manual status change during equipment hand-off"}]
    rows = normalize_intent_contract([{"kind": "automation", "decision": "clarify", "subject": "Booking asset status",
                                       "quote": "When a booking moves to Returned, set the assets to Returned",
                                       "question": "Should it update automatically or will staff confirm?",
                                       "options": opts}], brief)
    assert rows[0]["decision"] == "stock_automation" and rows[0]["assumption"].startswith("Assumed 'Fully")
    assert pending_contract_clarification(rows, [], {}) is None
    rows = normalize_intent_contract([{"kind": "other", "decision": "clarify", "subject": "Category list",
                                       "quote": "Configuration", "question": "Automatic or manual?",
                                       "options": opts}], brief)
    assert rows[0]["decision"] == "metadata" and "Manual" in rows[0]["assumption"]
    real = normalize_intent_contract([{"kind": "other", "decision": "clarify", "subject": "Alert recipient",
                                       "quote": "Configuration", "question": "Who gets it?",
                                       "options": [{"label": "Account owner"}, {"label": "Any manager"}]}], brief)
    assert real[0]["decision"] == "clarify"


def _q(question, opts, subject="Booking cancel"):
    return {"kind": "other", "decision": "clarify", "subject": subject, "quote": "", "origin": "stated",
            "question": question, "options": opts}


def test_brief_answered_question_is_assumed_not_asked():
    brief = (FX / "rental_casual.md").read_text()
    rows = normalize_intent_contract([_q("How strictly should non-managers be prevented from cancelling a booking?",
        [{"label": "Hide the cancel button for non-managers using user groups"},
         {"label": "Require manager approval via a formal confirmation workflow", "decision": "stock_automation"}])], brief)
    assert rows[0]["decision"] == "metadata" and "only managers" in rows[0]["assumption"]
    assert pending_contract_clarification(rows, [], {}) is None


def test_recommended_default_and_unsafe_block_and_budget():
    brief = "Track equipment loans."
    rec = normalize_intent_contract([_q("Who gets the to-do?", [{"label": "The loan owner", "recommended": True},
                                                                {"label": "Nobody"}], "Loan follow up")], brief)
    assert rec[0]["decision"] == "metadata" and "usual safe choice" in rec[0]["assumption"]
    unsafe = [_q(f"What happens to old loans {i}?", [{"label": "Delete them", "recommended": True},
                                                      {"label": "Archive them"}], f"Old loan cleanup {i}") for i in range(5)]
    rows = normalize_intent_contract(unsafe, brief)
    assert sum(r["decision"] == "clarify" for r in rows) == 3
    assert all(r["decision"] == "declined" for r in rows[3:])
