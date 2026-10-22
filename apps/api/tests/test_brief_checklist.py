"""Brief checklist (INGENIUM_BRIEF_CHECKLIST): two reads must agree before anything is left out."""
from __future__ import annotations

import json

import pytest

from app.ai_conversation import brief_checklist as bc
from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel, _call_intent_contract
from app.llm_provider import LLMError

B = ("abeg we be bakery, i need to record each order and if dem don pay deposit. "
     "payroll is another story. skip website for now. maybe loyalty points?")


def _items():
    return bc.parse_checklist({"checklist": [
        {"item": "Orders", "status": "build", "quote": "record each order"},
        {"item": "Payroll", "status": "dont_build", "quote": "Payroll  is another story"},
        {"item": "Website", "status": "later", "quote": "skip website for now"},
        {"item": "Loyalty points", "status": "unclear", "quote": "maybe loyalty points"},
        {"item": "Inventory", "status": "dont_build", "quote": "we have inventory sorted"},  # not in brief
        {"item": "x", "status": "bogus", "quote": "record"},
    ]}, B)


def test_quotes_any_length_located_by_normalized_match():
    items = {i["item"]: i for i in _items()}
    assert set(items) == {"Orders", "Payroll", "Website", "Loyalty points", "Inventory"}
    assert items["Payroll"]["located"] and items["Payroll"]["quote"] == "payroll is another story"
    assert not items["Inventory"]["located"]
    long = bc.locate(B, "i need to record each order and if dem don pay deposit payroll is another story")
    assert long is not None


def test_second_look_sees_only_no_and_later_quotes():
    rows = bc.second_look_items(_items(), seed=3)
    assert {r["item"] for r in rows} == {"Payroll", "Website", "Inventory"}
    assert all(set(r) == {"id", "item", "quote"} for r in rows)


@pytest.mark.parametrize("answer,final", [("yes", "excluded"), ("no", "choice"), ("unsure", "choice"), (None, "choice")])
def test_exclusion_needs_both_reads(answer, final):
    items = _items()
    ans = {i["id"]: answer for i in items} if answer else {}
    d = {i["item"]: i["final"] for i in bc.decide(items, ans)}
    assert d["Payroll"] == final and d["Website"] == final
    assert d["Inventory"] == "choice"  # unlocated quote is never an exclusion
    assert d["Loyalty points"] == "choice" and d["Orders"] == "build"


def test_failed_second_look_leaves_choices_and_put_back_wins():
    items = _items()
    assert all(i["final"] != "excluded" for i in bc.decide(items, None))
    pay = next(i for i in items if i["item"] == "Payroll")
    d = {i["item"]: i["final"] for i in bc.decide(items, {i["id"]: "yes" for i in items}, {pay["id"]})}
    assert d["Payroll"] == "choice" and d["Website"] == "excluded"


def test_filter_contract_drops_excluded_and_ticks_choices():
    decided = bc.decide(_items(), {i["id"]: "yes" for i in _items()})
    s = B.index("payroll")
    m = B.index("maybe")
    rows = [{"subject": "Payroll run", "evidence": {"start": s, "end": s + 7}},
            {"subject": "Points", "evidence": {"start": m, "end": m + 5}},
            {"subject": "Order", "evidence": {"start": 0, "end": 5}},
            {"subject": "Inferred", "evidence": {"start": 0, "end": 0}}]
    kept, left = bc.filter_contract(rows, decided)
    assert [r["subject"] for r in left] == ["Payroll run"]
    assert next(r for r in kept if r["subject"] == "Points")["choice_ticked"] is True
    assert {r["subject"] for r in kept} == {"Points", "Order", "Inferred"}  # unquoted kept, never dropped


def test_enforced_on_whole_design_and_put_back():
    d = AppDesign(app_name="Bakery", new_models=[
        DesignModel(name="x_payroll_run", label="Payroll Run"),
        DesignModel(name="x_order", label="Order", fields=[DesignField(name="x_website_url", string="Website URL"),
                                                           DesignField(name="x_deposit", string="Deposit")])],
        automations=[{"label": "Payroll reminder"}, {"label": "Deposit chase"}],
        python_needed=[{"label": "Nightly payroll job", "key": "payroll_cron"}],
        menus=["Payroll", "Orders"], intent_contract=[{"subject": "Payroll"}],
        left_out=[{"id": "a", "item": "Payroll", "quote": "payroll is another story"},
                  {"id": "b", "item": "Website", "quote": "skip website for now", "put_back": True}],
        checklist_choices=[{"id": "c", "item": "Deposit", "quote": "x", "ticked": True}])
    bc.enforce_on_design(d)
    assert [m.label for m in d.new_models] == ["Order"]
    assert [f.string for f in d.new_models[0].fields] == ["Website URL", "Deposit"]  # website put back
    assert [a["label"] for a in d.automations] == ["Deposit chase"]
    assert d.python_needed == [] and d.menus == ["Orders"] and d.intent_contract == []
    d.checklist_choices[0]["ticked"] = False  # unticked choice is left out too
    bc.enforce_on_design(d)
    assert [f.string for f in d.new_models[0].fields] == ["Website URL"]
    back = AppDesign.from_dict(d.to_dict())
    assert back.left_out[1]["put_back"] is True and back.checklist_choices[0]["ticked"] is False
    assert bc.left_out_rows([{"id": "a", "item": "P", "quote": "q", "status": "later", "final": "excluded"}])[0][
        "message"] == 'Left out because you said: "q"'


class _P:
    def __init__(self, second="yes", fail=False):
        self.second, self.fail, self.calls = second, fail, []

    def generate_json(self, prompt, *, system=None, **_):
        kind = "second" if system == bc.SECOND_LOOK_SYSTEM else "verify" if "verify one narrow" in (system or "") else "contract"
        self.calls.append(kind)
        if kind == "second":
            if self.fail:
                raise LLMError("x")
            return json.dumps({"answers": [{"id": r["id"], "answer": self.second} for r in json.loads(prompt)]})
        if kind == "verify":
            return json.dumps({"verdicts": []})
        assert "checklist" in prompt
        return json.dumps({"requirements": [
            {"kind": "model", "subject": "Payroll", "decision": "metadata", "origin": "stated", "evidence": "payroll is another story"},
            {"kind": "model", "subject": "Order", "decision": "metadata", "origin": "stated", "evidence": "record each order"}],
            "checklist": [{"item": "Payroll", "status": "dont_build", "quote": "payroll is another story"},
                          {"item": "Orders", "status": "build", "quote": "record each order"}]})


@pytest.mark.parametrize("second,fail,left", [("yes", False, ["Payroll"]), ("no", False, []), ("yes", True, [])])
def test_flow(monkeypatch, second, fail, left):
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")
    monkeypatch.setenv("INGENIUM_CLAUSE_GROUNDING", "1")  # checklist replaces it
    p = _P(second, fail)
    rows, meta = _call_intent_contract(p, B, None, answers={})
    assert [r["item"] for r in meta["checklist"]["left_out"]] == left
    assert ("Payroll" in {r["subject"] for r in rows}) == (not left)
    assert "grounding" not in meta and p.calls.count("contract") in (1, 2, 3) and p.calls.count("second") == 1  # S7: +1 conflict look
    if not left:
        assert [c["item"] for c in meta["checklist"]["choices"]] == ["Payroll"]


def test_put_back_answer_keeps_item(monkeypatch):
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")
    first = _call_intent_contract(_P(), B, None, answers={})[1]["checklist"]["left_out"][0]["id"]
    rows, meta = _call_intent_contract(_P(), B, None, answers={f"checklist_put_back:{first}": "1"})
    assert meta["checklist"]["left_out"] == [] and "Payroll" in {r["subject"] for r in rows}


def test_checklist_only_for_non_design_routes(monkeypatch):
    import app.llm_provider as lp
    from app.ai_conversation import app_design as ad

    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")

    class P(_P):
        def generate_json(self, prompt, *, system=None, **kw):
            if system == bc.SECOND_LOOK_SYSTEM:
                return super().generate_json(prompt, system=system, **kw)
            assert "few" not in system and "payroll is another story" in system  # few-shot present
            return json.dumps({"checklist": [{"item": "Payroll", "status": "dont_build", "quote": "payroll is another story"}]})

    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier="fast": P())
    chk = ad.checklist_only(B)
    assert [r["item"] for r in chk["left_out"]] == ["Payroll"]
    monkeypatch.delenv("INGENIUM_BRIEF_CHECKLIST")
    assert ad.checklist_only(B) is None


def test_cannot_status_declines_and_enforces():
    from app.ai_conversation import brief_checklist as bc
    from app.ai_conversation.app_design import AppDesign
    brief = "Build a model that forecasts my cash flow for 12 months."
    items = bc.parse_checklist({"checklist": [{"item": "Cash flow forecast", "status": "cannot", "quote": "forecasts my cash flow",
                                               "reason": "forecasting is analysis, not records"}]}, brief)
    dec = bc.decide(items, {}, set())
    assert dec[0]["final"] == "declined"
    rows = bc.left_out_rows(dec)
    assert rows[0]["message"].startswith("Not built here")
    d = AppDesign.from_dict({"app_name": "X", "new_models": [{"name": "x_cash_flow_forecast", "label": "Cash Flow Forecast", "fields": []}],
                             "record_rules": [{"model": "x_cash_flow_forecast", "label": "Cash flow forecast owner only"}]})
    d.left_out = rows
    bc.enforce_on_design(d)
    assert not d.new_models and not d.record_rules


def test_admission_repair_currency_and_automation_fields():
    from app.ai_conversation.app_design import AppDesign, _admission_repair
    d = AppDesign.from_dict({"app_name": "X", "new_models": [{"name": "x_job", "label": "Job", "fields": [
        {"name": "x_fee", "ttype": "monetary"}, {"name": "x_state", "ttype": "char"}]}],
        "automations": [{"label": "A", "target_model": "x_job", "automation": {"when": "on_create", "action": "set_fields",
                         "values": {"x_state": "new", "x_ghost": 1}, "condition": [["x_state", "=", "a"]]}},
                        {"label": "B", "target_model": "x_job", "automation": {"when": "on_create", "action": "set_fields", "values": {"x_ghost": 1}}}]})
    _admission_repair(d, None)
    assert any(f.relation == "res.currency" for f in d.new_models[0].fields)
    assert [a["label"] for a in d.automations] == ["A"] and d.automations[0]["automation"]["values"] == {"x_state": "new"}

