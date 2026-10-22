"""S12 follow-up: design refresh after install, day offsets, traced extension fields,
read-only install step, /stock-app under the preview rule."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.ai_conversation.app_design import AppDesign, DesignField, StockExtension
from app.ai_conversation.design_refresh import (
    map_to_stock_fields,
    refresh_pass,
    retarget_automations,
    sane_field_names,
    trace_extension_fields,
)
from app.ai_conversation.intent_contract import stated_day_offset
from app.odoo_snapshot import FieldInfo, ModelInfo, Snapshot

BRIEF = ("In our existing CRM, add to each opportunity a field for 'Source event' and a 'Decision date', "
         "and remind the salesperson a week before the decision date.")


def _crm_snap() -> Snapshot:
    fields = {
        "partner_id": FieldInfo(type="many2one", string="Customer", relation="res.partner"),
        "user_id": FieldInfo(type="many2one", string="Salesperson", relation="res.users"),
        "date_deadline": FieldInfo(type="date", string="Expected Closing"),
        "name": FieldInfo(type="char", string="Opportunity"),
    }
    return Snapshot(major=18, modules={"crm": "installed"}, index={"crm.lead": "Lead/Opportunity", "res.partner": "Contact"},
                    models={"crm.lead": ModelInfo(name="crm.lead", label="Lead/Opportunity", fields=fields)})


# ---- 2) reminder offset ------------------------------------------------------------------

@pytest.mark.parametrize("text,want", [
    ("remind the salesperson a week before the decision date", -7),
    ("3 days after go-live", 3),
    ("two weeks prior to expiry", -14),
    ("a 7-day before notice", -7),
    ("no timing here", None),
    ("1 day before and 2 days after", None),  # two different offsets: not guessed
])
def test_stated_day_offset(text: str, want: int | None) -> None:
    assert stated_day_offset(text) == want


def test_compile_keeps_negative_offset_as_before_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_design_compile import compile_design_draft

    monkeypatch.setattr("app.odoo_snapshot.current_snapshot", _crm_snap)

    design = {
        "app_name": "CRM decision date",
        "new_models": [],
        "stock_extensions": [{"model": "crm.lead", "fields": [
            {"name": "x_decision_date", "ttype": "date", "string": "Decision date"}]}],
        "automations": [{"target_model": "crm.lead", "label": "Remind before decision", "requirement_id": "r1",
                         "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date",
                                        "offset_days": -7, "summary": "Decision in a week"}}],
    }
    draft = compile_design_draft(design)
    [auto] = draft["automations"]
    assert auto["trg_date_range"] == 7 and auto["trg_date_range_mode"] == "before"
    assert auto["trg_date_field_name"] == "x_decision_date"
    assert draft["menus"] == []  # extension-only: no empty top menu


@pytest.mark.parametrize("mod", ["automation_v17", "automation_v18"])
def test_pre19_adapters_write_negative_range(mod: str) -> None:
    import importlib

    m = importlib.import_module(f"odoo_client.compat.adapters.{mod}")
    vals = m.build_automation_record_vals(name="r", model_id=1, trigger="on_time", active=True, server_vals={},
                                          trg_date_id=5, trg_date_range=7, trg_date_range_type="day",
                                          trg_date_range_mode="before")
    assert vals["trg_date_range"] == -7 and "trg_date_range_mode" not in vals


def test_v19_adapter_writes_mode() -> None:
    from odoo_client.compat.adapters.automation_v19 import build_automation_record_vals

    vals = build_automation_record_vals(name="r", model_id=1, trigger="on_time", active=True, server_vals={},
                                        trg_date_id=5, trg_date_range=7, trg_date_range_type="day",
                                        trg_date_range_mode="before")
    assert vals["trg_date_range"] == 7 and vals["trg_date_range_mode"] == "before"


def test_field_pack_date_activity_uses_stated_offset() -> None:
    from app.ai_senior_shape import _ensure_date_activity

    draft = {"_user_prompt": BRIEF, "models": [{"model": "crm.lead", "mode": "inherit", "fields": [
        {"name": "x_decision_date", "ttype": "date", "string": "Decision date"}]}]}
    _ensure_date_activity(draft)
    [auto] = draft["automations"]
    assert (auto["trg_date_range"], auto["trg_date_range_mode"], auto["trg_date_range_type"]) == (7, "before", "day")


# ---- 1/3) refresh passes -----------------------------------------------------------------

def _ext_design() -> AppDesign:
    d = AppDesign(app_name="CRM decision date")
    d.stock_extensions = [StockExtension(model="crm.lead", fields=[
        DesignField(name="x_partner_id", ttype="many2one", string="Customer", relation="res.partner", requirement_id="r1"),
        DesignField(name="x_salesperson", ttype="many2one", string="Salesperson", relation="res.users", requirement_id="r1"),
        DesignField(name="x_source_event", ttype="char", string="Source event", requirement_id="r1"),
        DesignField(name="x_decision_date", ttype="date", string="Decision date", requirement_id="r2"),
    ])]
    d.automations = [{"target_model": "x_crm_opportunity", "label": "Remind before decision", "requirement_id": "r2",
                      "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date",
                                     "offset_days": -7, "user_field": "x_salesperson"}}]
    return d


def test_copies_of_stock_fields_map_to_the_stock_field() -> None:
    d = _ext_design()
    d.automations[0]["target_model"] = "crm.lead"
    notes = map_to_stock_fields(d, _crm_snap())
    assert [f.name for f in d.stock_extensions[0].fields] == ["x_source_event", "x_decision_date"]
    assert d.automations[0]["automation"]["user_field"] == "user_id"
    assert any("existing Customer field" in n for n in notes)


def test_automation_on_missing_model_moves_to_the_real_record() -> None:
    d = _ext_design()
    retarget_automations(d, _crm_snap())
    assert d.automations[0]["target_model"] == "crm.lead"


def test_automation_with_no_real_host_is_left_out_with_a_note() -> None:
    d = _ext_design()
    d.stock_extensions = []
    notes = retarget_automations(d, _crm_snap())
    assert d.automations == [] and "not in this database" in notes[0]


def test_extension_fields_must_trace_to_approved_requirements() -> None:
    d = _ext_design()
    d.stock_extensions[0].fields.append(
        DesignField(name="x_to_each_opportunity_a_field_for_source", ttype="char", string="To each opportunity a field for source"))
    d.intent_contract = [{"id": "r1", "subject": "Source event field", "evidence": {"quote": "a field for 'Source event'"}},
                         {"id": "r2", "subject": "Decision date reminder", "evidence": {"quote": "a 'Decision date'"}}]
    notes = trace_extension_fields(d, {"r1", "r2"})
    names = [f.name for f in d.stock_extensions[0].fields]
    assert "x_to_each_opportunity_a_field_for_source" not in names and "x_decision_date" in names
    assert any("does not trace" in n for n in notes)


def test_untraced_field_named_by_a_requirement_is_traced_by_code() -> None:
    d = AppDesign()
    d.stock_extensions = [StockExtension(model="crm.lead", fields=[DesignField(name="x_source_event", string="Source event")])]
    d.intent_contract = [{"id": "r1", "subject": "Source event on opportunities", "evidence": {"quote": "a field for 'Source event'"}}]
    trace_extension_fields(d, {"r1"})
    assert d.stock_extensions[0].fields[0].requirement_ids == ["r1"]


def test_sentence_shaped_names_are_shortened_from_the_label() -> None:
    d = AppDesign()
    d.stock_extensions = [StockExtension(model="crm.lead", fields=[
        DesignField(name="x_remind_the_salesperson_a_week_before_t", ttype="date", string="Decision date")])]
    d.automations = [{"target_model": "crm.lead", "label": "r", "automation": {
        "when": "on_time", "action": "activity", "date_field": "x_remind_the_salesperson_a_week_before_t"}}]
    sane_field_names(d)
    assert d.stock_extensions[0].fields[0].name == "x_decision_date"
    assert d.automations[0]["automation"]["date_field"] == "x_decision_date"


def test_refresh_pass_traces_only_on_extension_designs() -> None:
    d = _ext_design()
    d._auth = ({"r1", "r2"}, False, set())  # type: ignore[attr-defined]
    d.intent_contract = []
    out = refresh_pass(d, _crm_snap())
    assert d.automations[0]["target_model"] == "crm.lead"
    assert d.automations[0]["automation"]["user_field"] == "user_id"
    assert {f.name for f in d.stock_extensions[0].fields} == {"x_source_event", "x_decision_date"}
    assert "traced" in out


def test_cached_contract_reuses_the_stored_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_conversation import app_design as ad
    from app.ai_conversation import diagnosis_decision as dd

    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")
    answers: dict = {}
    dd.persist(answers, dd.from_checklist({"items": 2, "stock_checks": [{"id": "r1", "choice": "stock",
                                                                        "use": {"model": "crm.lead"}}]}))
    chk = ad.stored_checklist(answers)
    assert chk and chk["stock_checks"][0]["use"]["model"] == "crm.lead"
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "0")
    assert ad.stored_checklist(answers) is None


def test_extension_flow_only_under_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_conversation import understand as u

    det = SimpleNamespace(inherit_existing=True, host_model="crm.lead", needs_module=False, gold_artifact_id=None)
    monkeypatch.setattr(u, "intent_llm_enabled", lambda: True)
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")
    assert u._extension_flow(BRIEF, det)
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "0")
    assert not u._extension_flow(BRIEF, det)


# ---- refresh step + gate -----------------------------------------------------------------

def _row(resolved: dict) -> SimpleNamespace:
    return SimpleNamespace(id="s1", connection_id="c1", prompt_original=BRIEF, prompt_resolved=BRIEF,
                           resolved_answers_json=json.dumps(resolved))


def test_gate_stays_closed_until_the_refresh_is_done(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from app.routers import ai_studio as r

    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda db, cid: SimpleNamespace(id=cid, write_mode="standard"))
    monkeypatch.setattr(r, "snapshot_for_connection", lambda conn, prompt: _crm_snap())
    pending = {r.DESIGN_REFRESH_KEY: "1"}
    with pytest.raises(HTTPException) as exc:
        r._install_gate(None, _row(pending), pending)
    assert exc.value.status_code == 409 and exc.value.detail["install_step"]["refresh"] is True
    r._install_gate(None, _row({}), {})  # refreshed: no gate


def test_refresh_refuses_new_requirements_and_keeps_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import ai_studio as r

    resolved = {"_intent_contract_json": json.dumps([{"id": "r1"}]), r.DESIGN_REFRESH_KEY: "1"}
    fake = SimpleNamespace(app_design={"intent_contract": [{"id": "r1"}, {"id": "new"}], "stock_extensions": []})
    monkeypatch.setattr(r, "build_understanding", lambda prompt, resolved_answers=None: fake)
    monkeypatch.setattr(r, "_studio_schema_packet", lambda conn, prompt="": None)
    msg = r._refresh_design_after_install(None, _row(resolved), SimpleNamespace(id="c1"), resolved, _crm_snap())
    assert "something new" in msg and resolved[r.DESIGN_REFRESH_KEY] == "1"


def test_refresh_success_stores_the_design_and_clears_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import ai_studio as r

    resolved = {"_intent_contract_json": json.dumps([{"id": "r1"}]), r.DESIGN_REFRESH_KEY: "1"}
    fake = SimpleNamespace(app_design={"intent_contract": [{"id": "r1"}], "stock_extensions": [{"model": "crm.lead"}]})
    stored: dict = {}
    monkeypatch.setattr(r, "build_understanding", lambda prompt, resolved_answers=None: fake)
    monkeypatch.setattr(r, "dump_understanding", lambda res, u: stored.setdefault("u", u))
    monkeypatch.setattr(r, "_studio_schema_packet", lambda conn, prompt="": None)
    assert r._refresh_design_after_install(None, _row(resolved), SimpleNamespace(id="c1"), resolved, _crm_snap()) == ""
    assert r.DESIGN_REFRESH_KEY not in resolved and stored["u"] is fake


# ---- 4) read-only ------------------------------------------------------------------------

def test_read_only_connection_disables_install_with_plain_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import ai_studio as r

    step = {"title": "t", "message": "m", "apps": [{"module": "crm", "label": "CRM", "installable": True}],
            "can_install": True, "install_label": "Install CRM", "blocked_message": "b"}
    out = r.mark_read_only(step, SimpleNamespace(write_mode="observer"))
    assert out["read_only"] and out["can_install"] is False
    assert "Switch the connection to Standard" in out["read_only_message"]
    assert r.mark_read_only(step, SimpleNamespace(write_mode="standard")) is step


# ---- 5) /stock-app under the preview rule ------------------------------------------------

def test_stock_app_route_needs_a_preview() -> None:
    from app.dry_run_middleware import is_write_capable

    assert is_write_capable("POST", "/api/ai/sessions/abc/stock-app")
    assert is_write_capable("POST", "/api/ai/sessions/abc/install-apps")


# ---- live-check fixes ---------------------------------------------------------------------

def test_fields_not_named_by_any_requirement_are_left_out() -> None:
    d = AppDesign()
    d.stock_extensions = [StockExtension(model="crm.lead", fields=[
        DesignField(name="x_source_event", string="Source Event", requirement_ids=["r1", "r2"]),
        DesignField(name="x_expected_revenue", ttype="float", string="Expected Revenue", requirement_ids=["r1", "r2"]),
        DesignField(name="x_stage", ttype="selection", string="Stage", requirement_ids=["r1", "r2"])])]
    d.intent_contract = [{"id": "r1", "subject": "Source event", "evidence": {"quote": "a field for 'Source event'"}},
                         {"id": "r2", "subject": "Decision date reminder", "evidence": {"quote": "remind the salesperson"}}]
    trace_extension_fields(d, {"r1", "r2"})
    assert [f.name for f in d.stock_extensions[0].fields] == ["x_source_event"]


def test_stored_contract_keeps_verifier_stamps_only_when_sealed() -> None:
    from app.ai_conversation import app_design as ad

    row = {"kind": "automation", "subject": "Decision date reminder", "decision": "stock_automation", "origin": "stated",
           "verified": True, "trigger": "time", "target_model": "crm.lead",
           "evidence": {"quote": "remind the salesperson a week before the decision date"},
           "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date", "offset_days": -7}}
    raw = json.dumps([row])
    sealed = ad._stored_intent_contract({"_intent_contract_json": raw, "_intent_contract_seal": ad._contract_seal(raw)}, BRIEF)
    forged = ad._stored_intent_contract({"_intent_contract_json": raw, "_intent_contract_seal": "0" * 64}, BRIEF)
    assert sealed and sealed[0].get("verified") is True
    assert forged is not None and not forged[0].get("verified")


def test_clarify_refuses_server_only_keys() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post("/api/ai/sessions/nope/clarify", json={"merge_key": "_intent_contract_json", "answer_id": "[]"})
    assert r.status_code == 422 and "can't be saved" in json.dumps(r.json())


def test_reminders_plan_the_automation_app() -> None:
    from app.ai_conversation.install_step import install_step, session_plans

    snap = Snapshot(major=17, modules={"crm": "17.0"}, installable={"base_automation": "uninstalled"},
                    index={"crm.lead": "Lead/Opportunity"})
    u = SimpleNamespace(host_model="crm.lead", inherit_existing=True, app_design={
        "intent_contract": [{"id": "r2", "decision": "stock_automation"}]})
    step = install_step({}, snap, session_plans(u, None, snap))
    assert step and [a["module"] for a in step["apps"]] == ["base_automation"]
    assert step["apps"][0]["why"] == "Your reminders and follow-ups run as automation rules."
    snap.modules["base_automation"] = "17.0"
    assert install_step({}, snap, session_plans(u, None, snap)) is None


def test_code_authorized_reminder_becomes_a_stock_automation() -> None:
    from app.ai_conversation.app_design import promote_code_authorized_automations
    from app.ai_conversation.intent_contract import normalize_intent_contract

    row = {"id": "requirement_x", "kind": "automation", "subject": "Decision date reminder", "decision": "clarify",
           "origin": "stated", "trigger": "time", "target_model": "crm.lead", "question": "", "options": [],
           "evidence": {"quote": "remind the salesperson a week before the decision date"},
           "downgrade_reason": "The code lane was not independently verified.",
           "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date", "offset_days": -7}}
    chk = {"stock_checks": [{"id": "chk_1", "requirement_ids": ["requirement_x"]}],
           "capability": [{"id": "chk_1", "shape": "record_automation", "decision": "authorize"}]}
    [out] = promote_code_authorized_automations([row], chk)
    assert out["decision"] == "stock_automation"
    # not authorized as a record automation -> stays a question
    chk["capability"][0]["decision"] = "ask"
    assert promote_code_authorized_automations([row], chk)[0]["decision"] == "clarify"
    # a real question is never promoted
    chk["capability"][0]["decision"] = "authorize"
    assert promote_code_authorized_automations([dict(row, question="Who gets it?")], chk)[0]["decision"] == "clarify"


def test_confirm_keeps_the_extension_design() -> None:
    from app.ai_conversation.understand import Understanding, apply_understanding_edits

    base = Understanding(capability="residual_app", grain="field_pack", host_model="crm.lead", inherit_existing=True,
                         title="CRM decision date", app_design={"_extension_flow": True, "stock_extensions": [
                             {"model": "crm.lead", "fields": [{"name": "x_decision_date", "ttype": "date"}]}]})
    out = apply_understanding_edits(base, {"title": "CRM decision date"})
    assert out.app_design and out.app_design.get("_extension_flow")
    plain = Understanding(capability="residual_app", grain="field_pack", host_model="crm.lead", inherit_existing=True,
                          title="t", app_design={"stock_extensions": []})
    assert apply_understanding_edits(plain, {"title": "t"}).app_design is None


def test_record_automation_never_becomes_custom_code() -> None:
    from app.ai_conversation.app_design import promote_code_authorized_automations
    from app.ai_conversation.intent_contract import normalize_intent_contract

    row = {"id": "requirement_y", "kind": "automation", "subject": "Salesperson reminder", "decision": "option_a",
           "origin": "stated", "trigger": "time", "target_model": "crm.lead", "question": "", "options": [],
           "evidence": {"quote": "remind the salesperson a week before the decision date."}, "automation": {}}
    chk = {"stock_checks": [{"id": "chk_2", "requirement_ids": ["requirement_y"]}],
           "capability": [{"id": "chk_2", "shape": "record_automation", "decision": "authorize"}]}
    [out] = promote_code_authorized_automations([row], chk)
    assert out["decision"] == "stock_automation"
    assert out["automation"]["offset_days"] == -7 and out["automation"]["when"] == "on_time"
    assert out["automation"]["date_field"] == "the decision date"
    # survives the trusted re-normalization done inside validate_and_repair
    [again] = normalize_intent_contract([out], BRIEF, trusted=True)
    assert again["decision"] == "stock_automation" and again["automation"]["offset_days"] == -7


def test_rule_on_a_stock_model_can_use_a_date_field_the_design_adds() -> None:
    from app.odoo_snapshot import clear_snapshot_cache, get_snapshot, validate_design
    from tests.test_odoo_snapshot import fake_call

    clear_snapshot_cache()
    snap = get_snapshot(fake_call(), "s12-ext-date", "partner renewal")
    design = {
        "stock_extensions": [{"model": "res.partner", "fields": [{"name": "x_decision_date", "ttype": "date"}]}],
        "automations": [
            {"requirement_id": "r1", "label": "Reminder", "target_model": "res.partner",
             "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date"}},
            {"requirement_id": "r2", "label": "Ghost", "target_model": "res.partner",
             "automation": {"when": "on_time", "action": "activity", "date_field": "x_nowhere"}},
        ],
    }
    errors = {f["ref"] for f in validate_design(design, snap) if f["severity"] == "error"}
    assert "r1" not in errors and "r2" in errors


def test_responsible_user_skips_audit_columns_and_follows_the_brief() -> None:
    from app.ai_design_compile import pick_user_field

    users = [("user_id", "Salesperson"), ("x_reviewer_id", "Reviewer")]
    assert pick_user_field(users, "remind the salesperson a week before") == "user_id"
    assert pick_user_field(users, "tell the reviewer") == "x_reviewer_id"
    assert pick_user_field(users, "remind someone") == "user_id"
    assert pick_user_field([], "x") == ""


def test_compiled_reminder_keeps_pinned_user_without_a_snapshot() -> None:
    from app.ai_design_compile import compile_design_draft

    design = {"app_name": "CRM extras", "new_models": [],
              "stock_extensions": [{"model": "crm.lead", "fields": [{"name": "x_decision_date", "ttype": "date"}]}],
              "automations": [{"requirement_id": "requirement_y", "label": "Reminder", "target_model": "crm.lead",
                               "automation": {"when": "on_time", "action": "activity", "date_field": "x_decision_date",
                                              "offset_days": -7, "user_field": "user_id"}}]}
    draft = compile_design_draft(design, prompt="p")
    [auto] = draft["automations"]
    assert auto["trg_date_range"] == 7 and auto["trg_date_range_mode"] == "before"
    assert auto["safe_actions"][0]["user_field_name"] == "user_id"


def test_installed_app_host_comes_from_the_approved_decision(monkeypatch) -> None:
    import json as _json
    from types import SimpleNamespace

    from app.ai_conversation import brief_checklist as bc
    from app.ai_conversation.understand import _host_from_approved_decision
    from app.odoo_snapshot import _SNAPSHOT

    monkeypatch.setattr(bc, "enabled", lambda: True)
    use = {"module": "maintenance", "model": "maintenance.request"}
    answers = {"_diagnosis_decision_json": _json.dumps({"stock_checks": [
        {"choice": "stock", "use": use}, {"choice": "stock", "use": use}]})}
    tok = _SNAPSHOT.set(SimpleNamespace(ok=True, index={"res.partner": "Contact"}))
    try:
        assert _host_from_approved_decision(answers) == ""  # app not installed yet
    finally:
        _SNAPSHOT.reset(tok)
    tok = _SNAPSHOT.set(SimpleNamespace(ok=True, index={"maintenance.request": "Maintenance Request"}))
    try:
        assert _host_from_approved_decision(answers) == "maintenance.request"
        two = {"_diagnosis_decision_json": _json.dumps({"stock_checks": [
            {"choice": "stock", "use": use}, {"choice": "stock", "use": {"model": "crm.lead"}}]})}
        assert _host_from_approved_decision(two) == ""  # two stock records: no single host
    finally:
        _SNAPSHOT.reset(tok)


def test_stated_date_phrase() -> None:
    from app.ai_conversation.intent_contract import stated_date_phrase

    assert stated_date_phrase("remind the technician 2 days before the scheduled date.") == "the scheduled date"
    assert stated_date_phrase("no timing here") == ""


def test_refreshed_design_that_needs_automation_shows_the_next_install(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.routers import ai_studio as r
    from tests.test_s11_install_step import DESIGN, _snap

    state = {"snap": _snap("community", installable=("crm", "base_automation")), "refreshed": False}
    row = SimpleNamespace(connection_id="c1", prompt_original="x", resolved_answers_json="{}")
    pend = {"kind": "diagnosis", "install_step": {"apps": [{"module": "crm"}]}}
    monkeypatch.setattr(r, "get_session", lambda _db, _sid: row)
    monkeypatch.setattr(r, "_session_design", lambda _res: DESIGN)
    plans = lambda _res, _snap: ([{"module": "base_automation", "app": "", "models": [],
                                    "why": "Your reminders and follow-ups run as automation rules."}]
                                 if state["refreshed"] else [])
    monkeypatch.setattr(r, "_session_plans", plans)
    monkeypatch.setattr("app.odoo_service.get_connection_or_404",
                        lambda _db, _cid: SimpleNamespace(id="c1", write_mode="standard"))
    monkeypatch.setattr(r, "snapshot_for_connection", lambda *_a, **_k: state["snap"])
    monkeypatch.setattr(r, "_open_stock_app_port", lambda _c: object())
    monkeypatch.setattr(r, "append_turn", lambda *a, **k: None)
    monkeypatch.setattr(r, "clear_snapshot_cache", lambda *_a: None)
    monkeypatch.setattr(r, "session_to_dict", lambda _row: {"pending_clarification": pend})
    monkeypatch.setattr(r, "update_session", lambda *_a, **_k: None)
    monkeypatch.setattr(r, "_refresh_design_after_install",
                        lambda *_a, **_k: state.update(refreshed=True) or "")
    monkeypatch.setattr(r, "_attach_diagnosis", lambda *_a, **_k: {"kind": "diagnosis"})
    monkeypatch.setattr(r, "assess_intent", lambda *_a, **_k: None)

    def fake_install(_port, module, label):
        state["snap"] = _snap("community", installed=("crm",), installable=("base_automation",))
        return True, f"{label} is installed."

    monkeypatch.setattr("app.ai_conversation.install_step.install_planned_module", fake_install)
    out = r.install_apps_route("s1", db=None)
    assert state["refreshed"]
    assert [a["module"] for a in out["install_step"]["apps"]] == ["base_automation"]


def test_authorized_record_automation_plans_automation_before_any_design() -> None:
    from types import SimpleNamespace

    from app.ai_conversation import install_step as ist

    snap = SimpleNamespace(index={}, major=20)
    u = SimpleNamespace(host_model=None, inherit_existing=True, app_design=None)
    decision = {"capability": [{"shape": "record_automation", "decision": "authorize"}]}
    assert any(p["module"] == "base_automation" for p in ist.session_plans(u, decision, snap))
    refused = {"capability": [{"shape": "record_automation", "decision": "refuse"}]}
    assert not any(p["module"] == "base_automation" for p in ist.session_plans(u, refused, snap))


def test_extension_view_on_stock_model_gives_no_refusing_warning() -> None:
    from types import SimpleNamespace

    from app.spec_apply_ui import _apply_explicit_views

    result = SimpleNamespace(warnings=[], skipped=[], views_created=0, views_updated=0)
    spec = {"views": [
        {"model": "crm.lead", "type": "form", "name": "crm.lead.form.extension", "mode": "extension", "arch": "<xpath expr='//sheet' position='inside'/>"},
        {"model": "crm.lead", "type": "form", "name": "crm.lead.form", "arch": "<form/>"},
    ]}
    _apply_explicit_views(object(), spec, result)
    assert not any("extension" in w for w in result.warnings)
    assert any("refusing to rewrite stock model crm.lead" in w for w in result.warnings)  # a real primary rewrite still refused
