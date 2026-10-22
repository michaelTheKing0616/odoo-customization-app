"""Known platform limits never become a clarify question; questions are never cut mid-sentence."""
from pathlib import Path

from app.ai_conversation.intent_contract import (
    normalize_intent_contract,
    pending_contract_clarification,
)

BRIEF = (Path(__file__).parent / "fixtures" / "customer_health_brief.md").read_text()


def _row(**kw):
    base = {"kind": "other", "decision": "clarify", "subject": "x", "quote": ""}
    base.update(kw)
    return base


def test_online_python_conflict_is_not_asked():
    q = ("The live instance is hosted on Odoo Online, which strictly disallows custom Python modules, "
         "but the brief requests a full custom module with Python models. Would you like to proceed?")
    rows = normalize_intent_contract([_row(kind="host", subject="Hosting vs custom Python", question=q)], BRIEF)
    assert rows == []
    assert pending_contract_clarification(rows, [], {}) is None


def test_long_question_is_cut_at_a_sentence_never_mid_sentence():
    q = "Should alerts be activities or emails? " + "Detail " * 80 + "Would you like"
    rows = normalize_intent_contract([_row(subject="Alert delivery channel", question=q)], BRIEF)
    assert rows and rows[0]["question"] == "Should alerts be activities or emails?"


def test_subject_named_in_a_heading_is_stated_not_a_suggestion():
    rows = normalize_intent_contract(
        [_row(subject="Proactive Alerts for At-Risk Customers", quote="not in brief verbatim")], BRIEF)
    assert rows[0]["origin"] == "stated" and "Automated Alerts" in rows[0]["evidence"]["quote"]
    # The brief makes alerts automatic, so this is decided rather than asked (and never a "suggestion").
    assert rows[0]["decision"] == "stock_automation"
    assert pending_contract_clarification(rows, [], {}) is None


def test_real_suggestion_keeps_label():
    rows = normalize_intent_contract([_row(subject="Mobile push notifications")], BRIEF)
    # An App Studio suggestion is listed on the diagnosis to keep or remove; it never blocks with a question.
    assert rows[0]["origin"] == "inferred" and pending_contract_clarification(rows, [], {}) is None


def test_heading_evidence_never_creates_a_conflict():
    from app.ai_conversation.intent_contract import detect_contract_conflicts

    a = {"id": "a", "subject": "Alert on critical health drop", "decision": "stock_automation", "trigger": "event",
         "evidence": {"quote": "## 10. Automated Alerts", "from_heading": True}}
    b = {"id": "b", "subject": "Critical health alert", "decision": "metadata",
         "evidence": {"quote": "Create a complete custom Odoo application"}}
    out = detect_contract_conflicts([a, b], BRIEF)
    assert out[0]["decision"] == "stock_automation"


def test_optional_module_handling_is_resolved_by_code_not_asked():
    rows = normalize_intent_contract(
        [_row(kind="integration", subject="Graceful Fallback for Non-Installed CRM and Helpdesk")], BRIEF)
    assert rows == []
    for subj in ("Clean install and uninstall", "Multi-company support", "Module dependency declaration"):
        assert normalize_intent_contract([_row(subject=subj)], BRIEF) == []


def test_paraphrase_matches_a_brief_sentence():
    from app.ai_conversation.intent_contract import subject_in_brief

    hit = subject_in_brief(BRIEF, "Graceful Fallback for Non-Installed CRM and Helpdesk")
    assert hit and "gracefully" in hit["quote"].lower()
    assert subject_in_brief(BRIEF, "Slack integration") is None


def test_question_caused_by_missing_app_is_not_asked():
    q = ("CRM is currently not installed in your database snapshot. Would you like expansion recommendations "
         "stored in a dedicated model with a deferred bridge to CRM until CRM is installed?")
    assert normalize_intent_contract([_row(kind="model", subject="Expansion Opportunities", question=q)], BRIEF) == []
    keep = normalize_intent_contract([_row(subject="Expansion score", question="Should it be entered or computed?")], BRIEF)
    assert keep


def test_field_and_its_automation_are_not_a_conflict():
    from app.ai_conversation.intent_contract import detect_contract_conflicts

    auto = {"id": "a", "kind": "automation", "subject": "Inspection damage flag updates asset and alerts manager",
            "decision": "stock_automation", "trigger": "event",
            "evidence": {"quote": "When an inspection is saved with Damage noted = yes"}}
    field = {"id": "b", "kind": "field", "subject": "Inspection damage noted flag", "decision": "metadata",
             "evidence": {"quote": "damage noted (yes/no)"}}
    assert detect_contract_conflicts([auto, field], "")[0]["decision"] == "stock_automation"
    same = {"id": "c", "kind": "automation", "subject": "Inspection damage flag alerts manager",
            "decision": "metadata", "trigger": "user_entry", "evidence": {"quote": "managers note damage by hand"}}
    assert detect_contract_conflicts([auto, same], "")[0]["decision"] == "clarify"


def test_brief_named_automatic_alert_is_decided_not_asked():
    rows = normalize_intent_contract([_row(kind="automation", subject="Automated Risk Activity Notification",
                                           quote="Create configurable automated alerts.",
                                           question="Should it be a value people enter, or something Odoo does automatically?")], BRIEF)
    assert rows and rows[0]["decision"] == "stock_automation"
    assert pending_contract_clarification(rows, [], {}) is None
    # a real business question with its own answers is still asked
    rows = normalize_intent_contract([_row(kind="automation", subject="Automated alert recipient",
                                           quote="Create configurable automated alerts.",
                                           question="Who should get the alert?",
                                           options=[{"label": "Account owner"}, {"label": "Any manager"}])], BRIEF)
    assert rows[0]["decision"] == "clarify"
