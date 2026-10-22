import json

import pytest

from app.ai_conversation import studio_agent as sa


def Snap():
    from app.odoo_snapshot import Snapshot
    return Snapshot(major=20, series="20.0", modules={"fleet": "20.0", "hr": "20.0", "base": "20.0"},
                    installable={"school": "uninstalled"},
                    index={"fleet.vehicle": "Vehicle", "hr.employee": "Employee", "res.partner": "Contact"})


BRIEF = "We deliver parcels. Log each delivery with the van used and the driver."
DESIGN = {"app_name": "Deliveries", "purpose": "Log deliveries",
          "new_models": [{"name": "x_delivery", "label": "Delivery", "fields": [
              {"name": "x_vehicle_id", "type": "many2one", "string": "Van", "relation": "fleet.vehicle"},
              {"name": "x_driver_id", "type": "many2one", "string": "Driver", "relation": "hr.employee"}]},
              {"name": "x_delivery_note", "label": "Delivery note", "fields": [
                  {"name": "x_delivery_id", "type": "many2one", "string": "Delivery", "relation": "x_delivery"}]}]}
FINAL = {"playback": {"wants": [{"need": "Log each delivery with van and driver",
                                 "quote": "Log each delivery with the van used"}],
                      "reuses": [{"app_or_model": "Fleet", "for": "vans", "why_it_fits": "installed"}],
                      "new": [{"thing": "Delivery log"}], "questions": [{"question": "Who logs?", "options": ["Driver", "Office"]}]},
         "requirements": [{"kind": "model", "subject": "Delivery", "origin": "stated",
                           "evidence": "Log each delivery", "decision": "metadata"}],
         "design": DESIGN}


def fake_post_factory(script):
    calls = []

    def post(provider, model, payload, timeout):
        calls.append((model, payload))
        step = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(step, Exception):
            raise step
        return step
    return post, calls


def _fc(name, args):
    return {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}, "thoughtSignature": "sig"}]}}]}


def _text(obj):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": "thinking", "thought": True}, {"text": json.dumps(obj)}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50, "thoughtsTokenCount": 20}}


def test_mode_default_is_pipeline(monkeypatch):
    monkeypatch.delenv("INGENIUM_STUDIO_MODE", raising=False)
    assert sa.mode() == "pipeline"
    monkeypatch.setenv("INGENIUM_STUDIO_MODE", "agent")
    assert sa.mode() == "agent"


def test_tools_are_read_only_and_bounded():
    t = sa.OdooTools(lambda *a: {}, Snap())
    with pytest.raises(PermissionError):
        t._rpc("res.partner", "write", [[1], {"name": "x"}], {})
    assert t.run("search_models", {"query": "vans vehicle"})["models"][0]["model"] == "fleet.vehicle"
    t.used = sa.MAX_TOOL_CALLS
    assert "budget" in t.run("list_apps", {})["error"]


def test_sample_records_mask_personal_fields():
    def call(model, method, args, kwargs):
        if method == "fields_get":
            return {"name": {"type": "char"}, "email": {"type": "char"}, "phone": {"type": "char"}}
        assert "email" not in kwargs["fields"] and "phone" not in kwargs["fields"]
        return [{"id": 1, "name": "A"}]
    t = sa.OdooTools(call, Snap(), db_key="t-mask")
    assert t.run("sample_records", {"model": "res.partner"})["rows"] == [{"name": "A"}]


def test_agent_loop_uses_tools_keeps_signatures_and_builds_design(monkeypatch):
    post, calls = fake_post_factory([_fc("search_models", {"query": "van"}), _text(FINAL)])
    design, out = sa.design_with_agent(BRIEF, snapshot=Snap(), provider=object(), post=post)
    assert out["status"] == "called" and out["tool_calls"] == 1 and calls[0][0] == sa.models()[0]
    second = calls[1][1]["contents"]
    assert second[1]["parts"][0]["thoughtSignature"] == "sig"  # model turn echoed verbatim
    assert "UNTRUSTED" in json.dumps(second[2])  # tool output fenced
    assert design.playback["reuses"][0]["app_or_model"] == "Fleet"
    assert design.playback["questions"][0]["default"] == "Driver"
    assert all(r.get("role") for r in design.intent_contract if r.get("kind") == "model")


def test_agent_falls_back_to_flash_on_error():
    post, calls = fake_post_factory([sa.AgentError("HTTP 404"), _text(FINAL)])
    design, out = sa.design_with_agent(BRIEF, snapshot=Snap(), provider=object(), post=post)
    assert out["model"] == sa.FALLBACK_MODEL and design is not None


def test_stated_needs_check_flags_invented_quote_and_gap():
    from app.ai_conversation.app_design import AppDesign
    d = AppDesign.from_dict(DESIGN)
    issues = sa.stated_needs_check({"wants": [{"need": "payroll export", "quote": "we pay monthly"}]}, d, BRIEF)
    assert any("Quote not in" in i for i in issues) and any("not covered" in i for i in issues)


def test_redesign_continues_same_conversation_and_caches():
    post, calls = fake_post_factory([_fc("search_models", {"query": "van"}), _text(FINAL)])
    design, out = sa.design_with_agent(BRIEF, snapshot=Snap(), provider=object(), post=post)
    key = design.playback["conv_key"]
    revised = json.loads(json.dumps(FINAL))
    revised["playback"]["questions"] = []
    revised["playback"]["new"] = [{"thing": "Delivery log kept by the office"}]
    post2, calls2 = fake_post_factory([_text(revised)])
    d2, o2 = sa.redesign(key, answers={"q1": "Office"}, snapshot=Snap(), provider=object(), post=post2)
    assert o2["status"] == "called" and d2.playback["new"][0]["thing"].endswith("office")
    sent = calls2[0][1]["contents"]
    assert any(p.get("thoughtSignature") == "sig" for c in sent for p in c.get("parts", []))  # history verbatim
    assert "Office" in json.dumps(sent[-1])
    assert d2.playback["conv_key"] != key
    post3, calls3 = fake_post_factory([_text(revised)])
    sa.redesign(key, answers={"q1": "Office"}, snapshot=Snap(), provider=object(), post=post3)
    assert calls3 == []  # cached


def test_redesign_without_edits_is_skipped():
    assert sa.redesign("nokey", answers={}, assumptions=[])[1]["reason"] == "no_edits"


def test_sandbox_errors_feed_the_fix_round(monkeypatch):
    monkeypatch.setenv("INGENIUM_AGENT_SANDBOX", "on")

    class Res:
        ok, message, log_tail = False, "ParseError: while parsing menus.xml | ValueError: External ID not found: x.action_y", ""
    seen = []

    def installer(zip_bytes, **kw):
        seen.append(kw)
        return Res()
    post, calls = fake_post_factory([_text(FINAL), _text(FINAL)])
    d, out = sa.design_with_agent(BRIEF, snapshot=Snap(), provider=object(), post=post, installer=installer)
    assert seen and out["sandbox"]["ok"] is False
    fix_prompt = json.dumps(calls[1][1]["contents"][-1])
    assert "Real install on a test database" in fix_prompt and "External ID" in fix_prompt
    assert out.get("sandbox_after_fix") is not None  # one bounded re-install


def test_sandbox_never_targets_shared_stack():
    for m in (16, 17, 18, 19, 20):
        assert sa._stack_is_shared(m) is False


def test_agent_mode_routes_single_model_and_extend_briefs(monkeypatch):
    from types import SimpleNamespace

    from app.ai_conversation.understand import _design_applies
    det = SimpleNamespace(grain="single_model", inherit_existing=True, needs_module=False, capability="extend",
                          gold_artifact_id=None)
    monkeypatch.setenv("INGENIUM_STUDIO_MODE", "pipeline")
    monkeypatch.setenv("INGENIUM_BRIEF_CHECKLIST", "")
    assert _design_applies("Add a delivery window to quotations.", det) is False
    monkeypatch.setenv("INGENIUM_STUDIO_MODE", "agent")
    assert _design_applies("Add a delivery window to quotations.", det) is True
    det.gold_artifact_id = "g1"
    assert _design_applies("Add a delivery window to quotations.", det) is False
