from app.ai_conversation.intent_contract import (
    apply_verifier_verdicts,
    automations_from_contract,
    bind_automation_targets,
    normalize_intent_contract,
    pending_contract_clarification,
    resolve_contract_answers,
)
from app.ai_conversation.automation_records import build_automation_records, substitute_refs

RUNGS = [
    {"rung": "metadata", "mechanism": "date field", "sufficient": False, "why": "Nothing fires on its own."},
    {"rung": "stock_automation", "mechanism": "automated action", "sufficient": False, "why": "Needs a custom calculation."},
]


def _row(**kw):
    base = {"kind": "automation", "subject": "Renewal reminder", "decision": "stock_automation",
            "evidence": "remind the owner a week before", "trigger": "time",
            "target_model": "x_renewal", "rungs": RUNGS[:1]}
    base.update(kw)
    return base


def test_scheduled_date_field_is_metadata_without_verifier():
    prompt = "Each renewal has a Scheduled date."
    rows = normalize_intent_contract(
        [_row(subject="Scheduled date", decision="option_a", evidence="Scheduled date",
              trigger="user_entry", rungs=RUNGS)], prompt)
    assert rows[0]["decision"] == "metadata"


def test_paraphrase_reaches_stock_automation_when_verified():
    prompt = "Please remind the owner a week before each renewal date."
    rows = normalize_intent_contract([_row()], prompt)
    assert rows[0]["decision"] == "stock_automation"
    rows = apply_verifier_verdicts(rows, {rows[0]["id"]: "supports"})
    assert rows[0]["verified"] and rows[0]["decision"] == "stock_automation"


def test_verifier_can_only_demote_never_promote():
    prompt = "Please remind the owner a week before each renewal date."
    rows = normalize_intent_contract([_row()], prompt)
    assert apply_verifier_verdicts(rows, {rows[0]["id"]: "not_supported"})[0]["decision"] == "metadata"
    assert apply_verifier_verdicts(rows, {})[0]["decision"] == "clarify"
    meta = normalize_intent_contract([_row(decision="metadata", trigger="none")], prompt)
    assert apply_verifier_verdicts(meta, {meta[0]["id"]: "supports"})[0]["decision"] == "metadata"


def test_incomplete_ladder_becomes_question():
    prompt = "Run a custom nightly calculation of risk."
    rows = normalize_intent_contract(
        [_row(decision="option_a", evidence="custom nightly calculation", rungs=RUNGS[:1])], prompt)
    assert rows[0]["decision"] == "clarify"


def test_inferred_code_lane_needs_operator_ok_and_skip_declines():
    prompt = "Track customer renewals."
    rows = normalize_intent_contract(
        [_row(origin="inferred", evidence="", subject="Auto-reminders")], prompt)
    assert rows[0]["origin"] == "inferred" and rows[0]["decision"] == "clarify"
    q = pending_contract_clarification(rows, None, {})
    assert q["default_id"] == "skip" and q["options"][0]["id"] == "skip"
    skipped = resolve_contract_answers(rows, {f"intent_contract:{rows[0]['id']}": "skip"})
    assert skipped[0]["decision"] == "declined"
    assert automations_from_contract(skipped) == []


def test_model_output_cannot_forge_trust_flags():
    prompt = "Please remind the owner a week before each renewal date."
    rows = normalize_intent_contract(
        [_row(verified=True, operator_confirmed=True, decision="declined")], prompt)
    assert rows[0]["verified"] is False and rows[0]["operator_confirmed"] is False


def test_target_binding_is_conservative():
    prompt = "Please remind the owner a week before each renewal date."
    rows = normalize_intent_contract([_row(target_model="x_old_name")], prompt)
    bound = bind_automation_targets(rows, {"x_renewal_plan": "Renewal Plan", "x_note": "Note"})
    assert bound[0]["target_model"] == "x_renewal_plan"
    ambiguous = bind_automation_targets(rows, {"x_renewal_plan": "Renewal", "x_renewal_log": "Renewal Log"})
    assert ambiguous[0]["target_model"] == ""


from app.ai_conversation.automation_records import build_automation_records, substitute_refs

AUTO = {"label": "Renewal reminder", "target_model": "x_renewal",
        "automation": {"when": "on_time", "action": "activity", "date_field": "x_date",
                       "offset_days": -7, "summary": "Renewal due"}}
FIELDS = {
    "base.automation": {"name", "model_id", "trigger", "trg_date_id", "trg_date_range",
                        "trg_date_range_type", "action_server_ids"},
    "ir.actions.server": {"name", "model_id", "state", "activity_summary",
                          "activity_user_type", "activity_user_field_name"},
    "x_renewal": {"activity_ids", "x_user_id"},
}
SEL = {("ir.actions.server", "state"): {"next_activity"},
       ("base.automation", "trigger"): {"on_time", "on_create", "on_write"},
       ("base.automation", "trg_date_range_type"): {"day"}}


def _build(auto=AUTO, fields=FIELDS, sel=SEL):
    return build_automation_records(
        auto, model_ids={"x_renewal": 5}, field_ids={("x_renewal", "x_date"): 9},
        fields_of=lambda m: fields.get(m, set()), selection_of=lambda m, f: sel.get((m, f), set()))


def test_builder_links_server_action_and_probes_version():
    steps, problem = _build()
    assert not problem and [s[2] for s in steps] == ["server", "automation"]
    assert steps[1][1]["trg_date_range"] == -7
    assert substitute_refs(steps[1][1], {"server": 42})["action_server_ids"] == [(6, 0, [42])]


def test_builder_refuses_instead_of_guessing():
    assert _build(auto={**AUTO, "automation": {}})[1]
    assert "base_automation" in _build(fields={**FIELDS, "base.automation": set()})[1]
    assert "to-do" in _build(sel={**SEL, ("ir.actions.server", "state"): set()})[1]
    assert "chatter" in _build(fields={**FIELDS, "x_renewal": {"x_user_id"}})[1]
    assert "responsible" in _build(fields={**FIELDS, "x_renewal": {"activity_ids"}})[1]