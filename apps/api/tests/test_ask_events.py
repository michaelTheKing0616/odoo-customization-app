from app.routers import suite_upkeep as su


def _patch(monkeypatch, raw, plan_ok=True):
    monkeypatch.setattr(su, "_client", lambda cid, db: object())
    monkeypatch.setattr(su, "_cloud", lambda db, cid: False)
    monkeypatch.setattr(su.sa, "money_route_for", lambda t: None)
    monkeypatch.setattr(su.sa, "packet", lambda c: {"record_types": [{"fields": [1, 2, 3]}, {"fields": [4]}]})
    monkeypatch.setattr(su.sa, "ai_json", lambda *a, **k: raw)
    monkeypatch.setattr(su.sa, "read_request", lambda t, pk: {"reader": True})
    monkeypatch.setattr(su.sa, "validate_plan", lambda r, pk: {"plan": {"p": 1} if plan_ok else None, "unclear": "?", "dropped": ["x"]})


def test_steps_come_from_real_stages(monkeypatch):
    _patch(monkeypatch, raw=None)
    evs = list(su.ask_events("c", "archive old leads", None))
    steps = [e["text"] for e in evs if e["type"] == "step"]
    assert steps[0] == "Read 4 fields on 2 record types"
    assert "plain code reader" in steps[1]
    assert "dropped 1 unknown part" in steps[2]
    assert evs[-1]["type"] == "result" and evs[-1]["data"]["kind"] == "plan"


def test_ask_returns_same_result(monkeypatch):
    _patch(monkeypatch, raw={"ok": 1}, plan_ok=False)
    out = su.ask("c", su.AskBody(text="hmm"), None)
    assert out["kind"] == "unclear" and out["source"] == "ai (checked by code)"
