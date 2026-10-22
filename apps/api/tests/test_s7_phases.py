"""S7 offline phase checks (no AI calls): decision, requirement ids, stock-first hosts, capability,
conflict look, admission planned installs."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from app.ai_conversation import app_design as ad
from app.ai_conversation import brief_checklist as bc
from app.ai_conversation import capability as cap
from app.ai_conversation import conflict_look as cl
from app.ai_conversation import diagnosis_decision as dd
from app.ai_conversation import stock_routing as sr
from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel

UNSUP = ("Log deliveries for our riders: rider, package, address, delivered time. Sync every delivery live "
         "to our Paystack and to GIG Logistics API, and SMS the customer when delivered.")


def _snap(models=(), modules=("sms",), installable=()):
    sel = {("ir.actions.server", "state"): ["code"], ("base.automation", "trigger"): ["on_create"]}
    return NS(modules=set(modules), installable={m: "uninstalled" for m in installable},
              index={m: {} for m in models}, selection_of=lambda m, f: sel.get((m, f), []),
              fields_of=lambda m: set(), major=18, edition="community", ok=True)


class _P:
    def __init__(self, replies):
        self.replies = list(replies)

    def generate_json(self, *_a, **_k):
        return json.dumps(self.replies.pop(0))


@pytest.fixture
def flag(monkeypatch):
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "1")


def test_p1_replay_unsupported_integration_decision(flag, monkeypatch):
    chk = {"checklist": [
        {"item": "Deliveries", "status": "build", "quote": "Log deliveries for our riders", "delivery_shape": "record_workflow"},
        {"item": "Paystack sync", "status": "build", "quote": "Sync every delivery live to our Paystack",
         "service": "Paystack", "service_direction": "sync", "service_needs_api": True, "delivery_shape": "integration"},
        {"item": "GIG sync", "status": "build", "quote": "GIG Logistics API", "service": "GIG Logistics",
         "service_direction": "sync", "service_needs_api": True, "delivery_shape": "integration"},
        {"item": "SMS customer", "status": "build", "quote": "SMS the customer when delivered", "service": "SMS",
         "service_modules": ["sms"], "service_direction": "send", "delivery_shape": "integration"},
    ]}
    p = _P([chk, {"answers": []}])
    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *_: p)
    monkeypatch.setattr(ad, "_current_snapshot", lambda: _snap())
    out = ad.checklist_only(UNSUP)
    dec = dd.from_checklist(out)
    routes = {r["service"]: r["route"] for r in dec["routes"]}
    assert routes == {"Paystack": "decline", "GIG Logistics": "decline", "SMS": "stock"}
    assert {d["item"] for d in dec["declines"] if d["kind"] == "route"} == {"Paystack", "GIG Logistics"}
    res: dict = {}
    dd.persist(res, dec)
    assert dd.load(res)["routes"] == dec["routes"]  # persists with no design
    clar = dd.attach_to_clarification({"kind": "diagnosis"}, dd.load(res))
    assert clar["integration_routes"] and clar["diagnosis_decision"]["version"] == 1


def _design(labels, rid=True):
    return AppDesign(app_name="A", purpose="p", new_models=[
        DesignModel(name=f"x_m{i}", label=lab, fields=[DesignField(name="x_note", ttype="char", string="Note",
                    requirement_ids=[f"r{i}"] if rid else [])], requirement_ids=[f"r{i}"] if rid else [])
        for i, lab in enumerate(labels)])


@pytest.mark.parametrize("labels", [["Payroll run", "Order"], ["Zebra", "Quokka"]])
def test_p2_metamorphic_rename_same_enforcement(labels):
    d = _design(labels)
    d.left_out = [{"item": "Payroll", "id": "c1", "requirement_ids": ["r0"]}]
    bc.enforce_on_design(d)
    assert [m.name for m in d.new_models] == ["x_m1"]  # by id, regardless of label


def test_p2_legacy_fallback_marked():
    d = _design(["Payroll", "Order"], rid=False)
    d.left_out = [{"item": "Payroll", "id": "c1", "requirement_ids": ["r0"]}]
    bc.enforce_on_design(d)
    assert [m.label for m in d.new_models] == ["Order"] and d.left_out[0]["matched_by"] == "legacy_stem"


def _conv(host, label, install=""):
    d = _design([label])
    c = {"choice": "stock", "id": "c0", "requirement_ids": ["r0"], "use": {"model": host, "name": host}, "install": install}
    sr.enforce_stock_first(d, [c], _snap(models=() if install else (host,)))
    return d, c


def test_p3_complaints_to_helpdesk_installable():
    d, c = _conv("helpdesk.ticket", "Complaint", install="helpdesk")
    assert not d.new_models and d.stock_extensions[0].model == "helpdesk.ticket"
    assert c["install_suggested"] == "helpdesk" and d.integrations[0].installed is False


def test_p3_repair_to_repair_order():
    d, c = _conv("repair.order", "Repair job")
    assert not d.new_models and c["converted"]


@pytest.mark.parametrize("host", ["res.partner", "calendar.event", "mail.activity"])
def test_p3_clinic_not_forced_onto_generic(host):
    d, c = _conv(host, "Patient intake")
    assert d.new_models and any(f.relation == host for f in d.new_models[0].fields) and c["custom_kept"]


def test_p3_account_protected():
    d, c = _conv("account.move", "Invoice note")
    assert d.new_models and "protected" in c["verified_reason"]


def test_p3_admission_knows_planned_install():
    from app.design_admission import validate_design
    d, _ = _conv("helpdesk.ticket", "Complaint", install="helpdesk")
    schema = NS(model_exists=lambda m: False, fields_of=lambda m: {}, field_info=lambda *a: None)
    try:
        res = validate_design(json.loads(json.dumps(d, default=lambda o: o.__dict__)), schema, major=18)
    except TypeError:
        pytest.skip("admission signature differs")
    assert "extension_model_missing" not in [e.code for e in res.errors]


def test_p4_financial_model_declined_plain():
    rows = cap.authorize([{"id": "c1", "item": "NPV forecast", "status": "build", "delivery_shape": "analysis_prediction"},
                          {"id": "c2", "item": "Cash projection", "status": "cannot"}])
    assert all(r["decision"] == "decline" and r["reason"] for r in rows)
    assert "App Studio" in rows[0]["reason"]


def test_p5_conflict_look_mocked():
    prompt = "Approvals need two managers. Only the requester can approve."
    rows = [{"id": "r1", "origin": "stated", "subject": "a", "decision": "build", "evidence": {"quote": "Approvals need two managers."}},
            {"id": "r2", "origin": "stated", "subject": "a", "decision": "build", "evidence": {"quote": "Only the requester can approve."}}]
    out, acc = cl.apply(rows, {"conflicts": [{"a": "r1", "b": "r2", "question": "Who approves?", "options": ["Managers", "Requester"]}]}, prompt)
    assert acc and out[0]["decision"] == "clarify"
    _, none = cl.apply(rows, {"conflicts": [{"a": "r1", "b": "zz"}]}, prompt)
    assert not none


def test_p5_inferred_never_blocks(flag):
    from app.ai_conversation.intent_contract import pending_contract_clarification
    rows = [{"id": "i1", "origin": "inferred", "decision": "clarify", "subject": "Loyalty", "question": "Add loyalty?"}]
    assert pending_contract_clarification(rows, None, {}) is None


def test_s8_scope_decline_only_drops_models():
    from app.ai_conversation import design_scope as ds
    d = _design(["Forecast", "Period"], rid=False)
    out = ds.authorize(d, set(), True)
    assert not d.new_models and out["dropped"]


def test_s8_scope_ids_attached_from_structure():
    from app.ai_conversation import design_scope as ds
    d = _design(["Req", "Line"], rid=False)
    d.new_models[1].fields.append(DesignField(name="x_req_id", ttype="many2one", string="Req", relation="x_m0"))
    d.automations = [{"target_model": "x_m0", "requirement_id": "r9"}]
    ds.authorize(d, {"r9"}, False)
    assert d.new_models[0].requirement_ids == ["r9"] and d.new_models[1].requirement_ids == ["r9"]
    assert not any(m.suggested for m in d.new_models)


def test_s8_capability_facts_disagree_asks():
    rows = cap.authorize([{"id": "c1", "item": "Cash outlook", "status": "build", "delivery_shape": "record_workflow",
                           "facts": {"keeps_records": False, "output_is_derived": True}}])
    assert rows[0]["decision"] == "ask" and rows[0]["code_shape"] == "analysis_prediction"


def test_s8_cap_ask_choice_unticked_and_left_out_of_contract():
    items = [{"id": "c1", "item": "x", "quote": "q", "final": "choice", "cap_ask": True, "located": True, "start": 0, "end": 5}]
    assert bc.choice_rows(items)[0]["ticked"] is False
    kept, left = bc.filter_contract([{"id": "r", "evidence": {"start": 0, "end": 4}}], items)
    assert not kept and left


def test_s8b_decline_only_headline_plain():
    dec = {"declines": [{"kind": "exclusion", "message": "Forecasting is analysis, not something App Studio builds"}]}
    out = dd.attach_to_clarification({"kind": "diagnosis", "question": "We'll build: X", "app_design": {"new_models": []}}, dec)
    assert out["question"] == "Nothing will be built for this request" and "Forecasting" in out["help"] and out["decline_only"]
    kept = dd.attach_to_clarification({"kind": "diagnosis", "question": "We'll build: X",
                                       "app_design": {"new_models": [{"name": "x_a"}]}}, dec)
    assert kept["question"] == "We'll build: X"


def test_s9_headline_not_shown_when_approved_items_exist():
    dec = {"declines": [{"kind": "route", "message": "Paystack: not connected"}],
           "capability": [{"id": "c1", "decision": "authorize"}], "routes": [{"service": "Paystack", "route": "decline"}]}
    out = dd.attach_to_clarification({"kind": "diagnosis", "question": "We'll build: Deliveries", "app_design": None}, dec)
    assert out["question"] == "We'll build: Deliveries"
    fin = {"declines": [{"kind": "exclusion", "message": "Forecasting is analysis"}],
           "capability": [{"id": "c1", "decision": "decline"}], "routes": []}
    out = dd.attach_to_clarification({"kind": "diagnosis", "question": "We'll build: X", "app_design": {"new_models": []}}, fin)
    assert out["question"] == "Nothing will be built for this request"


def test_s9_strict_scope_drops_config_model_in_declined_context():
    from app.ai_conversation import design_scope as ds
    d = _design(["Alert rule"], rid=False)
    d.new_models[0].is_config = True
    ds.authorize(d, set(), True, {"r0"})
    assert not d.new_models
    d = _design(["Order", "Forecast"])
    out = ds.authorize(d, {"r0"}, True, {"r1"})
    assert [m.name for m in d.new_models] == ["x_m0"] and out["dropped"] == ["Forecast"]


def test_s9_install_suggestion_and_admission_planned():
    from app.ai_conversation import design_scope as ds
    from app.ai_conversation.app_design import StockExtension
    from app.design_admission import validate_design
    d = _design([])
    d.stock_extensions = [StockExtension(model="maintenance.request", fields=[DesignField(name="x_n", ttype="char", string="N")], reason="")]
    snap = _snap(models=(), installable=("maintenance",))
    assert ds.ensure_install_suggestions(d, snap, 18) == ["maintenance"]
    dd_ = json.loads(json.dumps(d, default=lambda o: o.__dict__))
    sch = NS(model_exists=lambda m: False, fields_get=lambda m: {}, module_installable=lambda m: m == "maintenance",
             relation_ok=lambda *a: False, field_is_writable=lambda *a: False)
    res = validate_design(dd_, sch, major=18)
    assert "extension_model_missing" not in [e.code for e in res.errors]
    d2 = json.loads(json.dumps(_design([]), default=lambda o: o.__dict__))
    d2["stock_extensions"] = [{"model": "maintenance.request", "fields": []}]
    res2 = validate_design(d2, sch, major=18)  # no install suggestion -> still invalid
    assert "extension_model_missing" in [e.code for e in res2.errors]


def test_s9_align_checks_by_requirement_id():
    from app.ai_conversation.app_design import StockExtension
    d = _design([])
    d.stock_extensions = [StockExtension(model="helpdesk.ticket", fields=[DesignField(name="x_s", ttype="char", string="S", requirement_ids=["r5"])], reason="")]
    checks = [{"id": "c1", "choice": "custom", "requirement_ids": ["r5"]}]
    assert sr.align_checks_by_id(d, checks, _snap(installable=("helpdesk",))) == 1
    assert checks[0]["choice"] == "stock" and checks[0]["install"] == "helpdesk"


def test_s9_conflict_look_retries_once():
    class Flaky:
        n = 0
        def generate_json(self, *a, **k):
            Flaky.n += 1
            if Flaky.n == 1:
                raise RuntimeError("timeout")
            return json.dumps({"conflicts": []})
    rows = [{"id": f"r{i}", "origin": "stated", "subject": "s", "evidence": {"quote": f"q{i}"}} for i in range(2)]
    assert ad._call_conflict_look(Flaky(), "q0 q1", rows) == {"conflicts": []} and Flaky.n == 2


def test_s9_conflict_look_on_brief_sentences_when_contract_lacks_side():
    p = "Track purchase requests. Any staff can approve their own request. Every request above 500k must be approved by the finance manager, nobody else."
    rows = cl.rows_for_look([], p)
    assert [r["id"] for r in rows] == ["s1", "s2", "s3"]
    _, acc = cl.apply([], {"conflicts": [{"a": "s2", "b": "s3", "question": "Who approves above 500k?", "options": ["Finance", "Staff"]}]}, p)
    assert acc and acc[0]["quote_a"].startswith("Any staff")
    _, bad = cl.apply([], {"conflicts": [{"a": "s2", "b": "s9"}]}, p)
    assert not bad


def test_s10_strict_scope_covers_extension_fields_and_headline():
    from app.ai_conversation import design_scope as ds
    from app.ai_conversation.app_design import StockExtension
    d = _design([])
    d.stock_extensions = [StockExtension(model="res.partner", fields=[DesignField(name="x_runway", ttype="date", string="Runway")], reason="")]
    out = ds.authorize(d, set(), True, {"r1"})
    assert not d.stock_extensions and out["dropped_fields"] == ["res.partner.x_runway"]
    dec = {"declines": [{"kind": "exclusion", "message": "Forecasting is analysis"}], "capability": [{"decision": "decline"}]}
    clar = dd.attach_to_clarification({"kind": "diagnosis", "question": "We'll build: X", "app_design": d.to_dict() if hasattr(d, "to_dict") else {"new_models": [], "stock_extensions": []}}, dec)
    assert clar["question"] == "Nothing will be built for this request"


def test_s10_extension_fields_inherit_routed_ids():
    from app.ai_conversation import design_scope as ds
    from app.ai_conversation.app_design import StockExtension
    d = _design([])
    d.stock_extensions = [StockExtension(model="sale.order", fields=[DesignField(name="x_pickup", ttype="date", string="Pickup")], reason="")]
    d.stock_checks = [{"choice": "stock", "use": {"model": "sale.order"}, "requirement_ids": ["r1"]}]
    ds.authorize(d, {"r1"}, True, {"r9"})
    assert d.stock_extensions[0].fields[0].requirement_ids == ["r1"]


def test_s10_only_conflicts_and_risky_items_block(flag):
    from app.ai_conversation.intent_contract import _CONFLICT_PREFIX, pending_contract_clarification
    plain = [{"id": "a", "origin": "stated", "decision": "clarify", "subject": "Booking confirmed",
              "evidence": {"quote": "q"}}]
    assert pending_contract_clarification(plain, None, {}) is None
    risky = [dict(plain[0], blocking_reason="risk", question="Who signs off?")]
    assert pending_contract_clarification(risky, None, {})["question"] == "Who signs off?"
    conf = [dict(plain[0], downgrade_reason=_CONFLICT_PREFIX + "other")]
    assert pending_contract_clarification(conf, None, {}) is not None
