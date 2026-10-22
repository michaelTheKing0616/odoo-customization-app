"""Bridge delivery engine, second approver with sign-in off, trace stations, publish log, token refresh."""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.bridge import delivery as dl
from app.bridge import flows as fl
from app.bridge import live_probe as lp
from app.bridge import tokens as tk
from app.code_runner import store
from app.db_models import Base, IntegrationEvent


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path, raising=False)
    monkeypatch.setenv("INGENIUM_CODE_RUNNER_STORE", str(tmp_path))
    data: dict = {}
    monkeypatch.setattr(store, "load", lambda kind, key, default=None: json.loads(json.dumps(data.get((kind, key), default))))
    monkeypatch.setattr(store, "save", lambda kind, key, value: data.__setitem__((kind, key), json.loads(json.dumps(value))))


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    IntegrationEvent.__table__.create(eng)
    return sessionmaker(bind=eng)()


def _ev(db, key, ok="F|r1", n=0):
    e = IntegrationEvent(id=f"e{key}", connection_id="b1", idempotency_key=key, payload_json=json.dumps({"n": n}),
                         status="queued", attempts=0, ordering_key=ok)
    db.add(e); db.flush()
    return e


def test_same_record_goes_in_order_and_waits_for_retry(db):
    a, b, c = _ev(db, "a", n=1), _ev(db, "b", n=2), _ev(db, "c", ok="F|r2", n=3)
    seen = []

    def h(ev, p):
        seen.append(p["n"])
        if p["n"] == 1:
            raise TimeoutError("timed out")
        return {"odoo_id": 7}

    out = dl.deliver_due(db, h, sleep=lambda s: None)
    assert seen == [1, 3] and a.status == "retrying" and b.status == "queued" and c.status == "done"
    assert out["waiting"] == 1 and a.next_attempt_at is not None
    later = a.next_attempt_at + timedelta(seconds=1)
    seen.clear()
    dl.deliver_due(db, lambda ev, p: seen.append(p["n"]) or {}, now=later, sleep=lambda s: None)
    assert seen == [1, 2] and a.status == "done" and b.status == "done"


def test_backoff_grows_and_dead_after_max(db):
    assert dl.backoff_s(1, rnd=lambda: 0.5) == 2.0 and dl.backoff_s(3, rnd=lambda: 0.5) == 8.0
    assert dl.backoff_s(30, rnd=lambda: 0.5) == dl.MAX_DELAY_S
    e = _ev(db, "x")
    for _ in range(dl.MAX_ATTEMPTS):
        e.next_attempt_at = None
        dl.deliver_due(db, lambda ev, p: (_ for _ in ()).throw(ConnectionError("down")), sleep=lambda s: None)
    assert e.status == "dead" and e.attempts == dl.MAX_ATTEMPTS and "down" in e.last_error


def test_permanent_goes_straight_to_dead_letters(db):
    e = _ev(db, "p")
    dl.deliver_due(db, lambda ev, p: (_ for _ in ()).throw(dl.Permanent("bad data")), sleep=lambda s: None)
    assert e.status == "dead" and e.attempts == 1


def test_trace_records_station_status_and_timing(db):
    _ev(db, "t", ok="F|r9")
    dl.deliver_due(db, lambda ev, p: {"odoo_id": 3, "steps": [{"step": "Mapped with version 1", "station": "ingenium", "ms": 4}]},
                   sleep=lambda s: None)
    tr = fl.get_trace(None, "F", "r9")
    assert [(t["station"], t["status"]) for t in tr] == [("ingenium", "ok"), ("odoo", "ok")]
    assert tr[-1]["station_label"] == "Odoo" and tr[-1]["ms"] is not None and "record 3" in tr[-1]["detail"]


def _money_flow():
    return {"odoo_model": "account.move", "mapping": [{"remote": "amount", "odoo": "amount_total"}]}


def test_money_flow_with_sign_in_off_needs_two_different_names():
    fl.propose(None, "M", _money_flow(), "name:Ada", True)
    h = fl.get_flow(None, "M")["versions"][0]["hash"]
    with pytest.raises(PermissionError, match="type"):
        fl.approve(None, "M", 1, None, h, verified=False)
    with pytest.raises(PermissionError, match="second person"):
        fl.approve(None, "M", 1, "name:ada", h, verified=False)
    out = fl.approve(None, "M", 1, "name:Tunde", h, verified=False)
    assert out["approved_by"] == "name:Tunde" and out["verified"] is False


def test_money_flow_without_proposer_name_cannot_be_approved():
    fl.propose(None, "M2", _money_flow(), None, True)
    h = fl.get_flow(None, "M2")["versions"][0]["hash"]
    with pytest.raises(PermissionError, match="without a name"):
        fl.approve(None, "M2", 1, "name:Tunde", h, verified=False)


def test_publish_log_has_steps_timings_and_approver():
    fl.propose(None, "P", {"odoo_model": "res.partner", "mapping": []}, "u1", True)
    v = fl.get_flow(None, "P")["versions"][0]
    fl.approve(None, "P", 1, "u2", v["hash"])
    fl.set_rollout(None, "P", 1, 25, by="u2")
    fl.set_rollout(None, "P", 1, 100, by="u2")
    log = fl.get_flow(None, "P")["versions"][0]["log"]
    assert [x["step"] for x in log] == ["Proposed", "Approved", "Rolled out to 25%", "Live for everyone"]
    assert log[1]["by"] == "u2" and log[1]["verified"] is True and log[1]["since_prev_s"] is not None


def test_token_refresh_uses_stored_token_until_near_expiry_and_saves_rotation(monkeypatch):
    sec = {"refresh_token": "R1", "access_token": "A0", "expires_at": "1000"}
    monkeypatch.setattr(lp, "_secrets", lambda ws, key: dict(sec))
    saved = {}
    monkeypatch.setattr(tk, "_save", lambda ws, key, v: (saved.update(v), sec.update(v)))
    assert tk.access_token_for(None, "xero", now=500)["refreshed"] is False
    calls = []

    def post(url, data, headers, timeout):
        calls.append(data)
        return httpx.Response(200, json={"access_token": "A1", "expires_in": 1800, "refresh_token": "R2"})

    out = tk.access_token_for(None, "xero", now=950, post=post)
    assert out["refreshed"] and out["rotated"] and saved["refresh_token"] == "R2" and calls[0]["refresh_token"] == "R1"
    with pytest.raises(tk.SignInAgain):
        tk.access_token_for(None, "xero", now=99999, post=lambda *a, **k: httpx.Response(400, json={"error": "invalid_grant"}))
