from pathlib import Path

from app.ai_conversation.app_design import AppDesign, DesignModel, SecurityGroup
from app.ai_conversation.design_quality import _f, ensure_jobs, ensure_rules, scope_and_limits
from app.ai_conversation.intent_contract import _automation_spec
from app.ai_design_compile import _arch
from app.ai_stock_catalog import suggest_stock_apps

FX = Path(__file__).parent / "fixtures"


def test_no_score_job_without_a_score_in_the_brief():
    d = AppDesign(app_name="R")
    ensure_jobs(d, (FX / "rental_structured.md").read_text())
    assert not any("score" in p["label"].lower() for p in d.python_needed)


def test_stock_apps_suggested_from_brief_words():
    names = [a["name"] for a in suggest_stock_apps((FX / "rental_casual.md").read_text(), {"maintenance"}, "enterprise")]
    assert names[0] == "Rental" and "Maintenance" in names
    assert next(a for a in suggest_stock_apps("we handle customer complaints", set(), "community"))["available"] is False


def test_new_automation_types_are_bounded():
    assert _automation_spec({"when": "untouched", "action": "notify", "offset_days": 5, "group": "Managers"})["group"] == "Managers"
    assert _automation_spec({"when": "untouched", "action": "activity", "offset_days": 0}) == {}
    spec = _automation_spec({"when": "on_write", "action": "set_fields", "values": {"x_state": "done", "bad key": 1},
                             "condition": [["x_damage", "=", True], ["x", "eval", "os.system"]]})
    assert spec["values"] == {"x_state": "done"} and spec["condition"] == [["x_damage", "=", True]]
    assert _automation_spec({"when": "on_write", "action": "set_fields", "values": {"x": {"a": 1}}}) == {}


def test_hide_field_and_cancel_by_group_and_scope_limits():
    b = DesignModel(name="x_booking", label="Booking", fields=[_f("Name", "char", name="x_name"), _f("Rental Price", "float")])
    d = AppDesign(app_name="R", new_models=[b], security_groups=[SecurityGroup("Rental User"), SecurityGroup("Rental Manager")])
    ensure_rules(d, "Only managers can cancel a booking. Only managers can see the rental price.")
    scopes = {r["scope"] for r in d.record_rules}
    assert {"cancel", "hide_field"} <= scopes and any(f.name == "x_state" for f in b.fields)
    spec = {"model": "x_booking", "fields": [f.__dict__ for f in b.fields],
            "_hidden_fields": {"x_rental_price": "g_m"}, "_cancel_group": "g_m"}
    arch = _arch(spec, "form")
    assert 'groups="!g_m"' in arch and 'statusbar_visible="draft,confirmed,done"' in arch
    assert '<field name="x_rental_price" groups="g_m"/>' in arch
    assert scope_and_limits(d, "We want a website and payroll too.") and "Payroll" in d.out_of_scope
    assert not scope_and_limits(AppDesign(), "We do not want a website.")


def test_group_notice_reaches_every_member_and_falls_back_to_owner():
    from app.spec_apply_ui import expand_group_notices

    acts, warn = expand_group_notices([{"kind": "notify_group", "group": "Rental Manager", "summary": "Check"}],
                                      lambda g: [7, 9])
    assert [a["user_id"] for a in acts] == [7, 9] and all(a["user_type"] == "specific" for a in acts) and not warn
    acts, warn = expand_group_notices([{"kind": "notify_group", "group": "Nobody"}], lambda g: [])
    assert acts[0]["kind"] == "next_activity" and "user_id" not in acts[0] and warn


def test_edited_choice_flows_into_the_rebuilt_design():
    from app.ai_conversation.app_design import apply_design_edits

    row = {"id": "requirement_abc", "kind": "automation", "subject": "Booking reminder", "decision": "stock_automation",
           "origin": "stated", "evidence": {"quote": "q", "start": 0, "end": 1}, "trigger": "time",
           "target_model": "x_booking", "verified": True, "assumption": "Assumed 'Fully automatic'",
           "alternatives": ["Manual reminder by staff"]}
    from app.ai_conversation.intent_contract import normalize_intent_contract

    row = normalize_intent_contract([row], "", trusted=True)[0]
    rid = row["id"]
    base = {"app_name": "R", "intent_contract": [row],
            "new_models": [{"name": "x_booking", "label": "Booking", "fields": [{"name": "x_name", "string": "Name", "ttype": "char"}]}]}
    edited = dict(base, assumptions=[{"text": "Assumed", "requirement_id": rid, "chosen": "Manual reminder by staff"}])
    out = apply_design_edits(base, edited)
    r = next(x for x in out["intent_contract"] if x["id"] == rid)
    assert r["decision"] == "metadata" and r["operator_confirmed"] is True
    assert out["assumptions"][0]["chosen"] == "Manual reminder by staff"
    assert any("Your choice" in n for n in out["notes"])


def test_open_build_way_question_is_settled_after_verification():
    from app.ai_conversation.intent_contract import settle_open_questions

    brief = (FX / "rental_structured.md").read_text()
    q = "When a booking moves to Returned, set the assets to Returned"
    row = {"id": "r1", "kind": "automation", "subject": "Booking Out - Update Asset Status", "decision": "clarify",
           "origin": "stated", "evidence": {"quote": q}, "target_model": "x_booking",
           "automation": {"when": "on_write", "action": "activity"}, "options": [], "question": ""}
    out = settle_open_questions([row], brief)
    assert out[0]["decision"] == "stock_automation" and out[0]["assumption"]
    code = dict(row, id="r2", kind="python")
    assert settle_open_questions([code], brief)[0]["decision"] == "clarify"


def test_at_most_three_questions_each_with_a_recommended_default() -> None:
    from app.ai_conversation import stock_routing as sr

    t = sorted(sr.RISKY_TYPES)[0]
    items = [{"id": f"r{i}", "item": f"Part {i}", "type": t,
              "decision": {"source": "ask", "question": f"Which way for part {i}?", "options": ["Simple", "Detailed"],
                           "value": "Detailed" if i == 0 else ""}} for i in range(5)]
    reg = sr.register(items, lambda q: False)
    assert len(reg["questions"]) == 3
    assert reg["questions"][0]["recommended"] == "Detailed" and reg["questions"][0]["options"][0] == "Detailed"
    assert all(q["recommended"] for q in reg["questions"])
    assert {d["id"] for d in reg["defaults"]} >= {"r3", "r4"} and all(d["value"] for d in reg["defaults"] if d["id"] in {"r3", "r4"})


def test_parallel_design_calls_keep_the_ai_scope() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.ai_client.ai_scope import ai_scope, current_scope
    from app.ai_conversation.app_design import _in_scope

    with ai_scope(db="dbX", consent_cloud=False):
        with ThreadPoolExecutor(max_workers=1) as pool:
            got = pool.submit(_in_scope(lambda: (current_scope().db, current_scope().consent_cloud))).result()
    assert got == ("dbX", False)


def test_negative_see_and_only_edit_become_field_group_rules() -> None:
    from app.ai_conversation.app_design import AppDesign, DesignModel
    from app.ai_conversation.design_quality import ensure_rules

    m = DesignModel(name="x_job", label="Delivery Job", fields=[_f("Delivery Fee", "float", name="x_fee"), _f("Rider", "char", name="x_rider")])
    d = AppDesign(app_name="C", new_models=[m])
    ensure_rules(d, "Riders shouldn't see the fee.")
    r = [x for x in d.record_rules if x["scope"] == "hide_field"]
    assert r and r[0]["field"] == "x_fee" and r[0]["negate"] and any(g.name == "Rider" for g in d.security_groups)

    p = DesignModel(name="x_pledge", label="Pledge", fields=[_f("Amount Pledged", "float", name="x_amt"), _f("Total Paid Amount", "float", name="x_paid")])
    d2 = AppDesign(app_name="P", new_models=[p])
    ensure_rules(d2, "Ushers record payments but they should not see the total pledged amount, only the pastor.")
    hid = [x["field"] for x in d2.record_rules if x["scope"] == "hide_field"]
    assert hid == ["x_amt"] and any("Usher" in g.name for g in d2.security_groups)

    lab = DesignModel(name="x_lab", label="Lab Request", fields=[_f("Result", "text", name="x_result")])
    d3 = AppDesign(app_name="L", new_models=[lab])
    ensure_rules(d3, "only lab staff edit results. no billing.")
    assert [x["scope"] for x in d3.record_rules] == ["edit_field"]


def test_edit_field_arch_is_readonly_for_others_and_negated_hide() -> None:
    from app.ai_design_compile import _arch

    spec = {"model": "x_lab", "fields": [{"name": "x_result", "string": "Result", "ttype": "text"}, {"name": "x_fee", "string": "Fee", "ttype": "float"}],
            "_hidden_fields": {"x_result": "edit:g_lab", "x_fee": "!g_rider"}, "_cancel_group": ""}
    arch = _arch(spec, "form")
    assert '<field name="x_result" groups="g_lab"/>' in arch and 'readonly="1" groups="!g_lab"' in arch
    assert 'name="x_fee" groups="!g_rider"' in arch


def test_terse_conditional_duty_is_stated_and_automatic() -> None:
    from app.ai_conversation.intent_contract import _AUTO_CUE, duty_match

    assert duty_match("lab requests per patient. alert doctor if result abnormal. no billing.", "Alert Doctor on Abnormal Result")
    assert _AUTO_CUE.search("If someone hasn't paid anything in 60 days on a monthly pledge, the welfare secretary should get a to-do to call them.")


def test_terse_automation_clause_is_quoted_without_labeller_flags() -> None:
    from app.ai_conversation.clause_grounding import per_type_problem

    clauses = [{"id": "c1", "text": "alert doctor if result abnormal."}]
    ev = {"clause_ids": ["c1"], "snippet": "alert doctor if result abnormal."}
    assert per_type_problem("automation", {"subject": "Alert doctor"}, ev, {"c1": {}}, clauses) == ""
    assert per_type_problem("automation", {"subject": "x"}, {"clause_ids": ["c2"], "snippet": "x"},
                            {"c2": {}}, [{"id": "c2", "text": "lab requests per patient."}]) != ""
