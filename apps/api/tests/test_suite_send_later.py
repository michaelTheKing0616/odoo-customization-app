"""Send later for the Send a message tool: scheduled, cancellable before it fires, money guard unchanged."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app import suite_change as sc
from app.routers import suite_change as rsc
from tests.test_suite_stage2 import _batch, env  # noqa: F401


def _iso(**d):
    return (datetime.now(UTC) + timedelta(**d)).isoformat()


def _wire(o):
    o.meta["res.partner"]["message_ids"] = {"type": "one2many", "store": True}
    o.posted = []
    inner = o.execute_kw

    def ex(model, method, args, kw):
        if method == "message_post":
            o.posted.append((args[0], kw.get("body"))); return 500 + len(o.posted)
        return inner(model, method, args, kw)
    o.execute_kw = ex


def test_refuse_validates_send_at():
    fm = {"message_ids": {}}
    b = {"tool": "message", "model": "res.partner", "change": {"body": "Hi", "send_at": _iso(hours=2)}}
    assert sc.refuse(b, fm) is None
    assert "future" in sc.refuse({**b, "change": {"body": "Hi", "send_at": _iso(hours=-1)}}, fm)
    assert "30 days" in sc.refuse({**b, "change": {"body": "Hi", "send_at": _iso(days=31)}}, fm)
    assert "valid" in sc.refuse({**b, "change": {"body": "Hi", "send_at": "soon"}}, fm)
    assert sc.refuse({"tool": "edit", "model": "res.partner", "change": {"field": "name", "value": "x", "send_at": _iso(hours=1)}}, {"name": {}}) == "Only messages can be sent later."
    assert sc.refuse({**b, "model": "account.move"}, fm).startswith("Refused by the money guard")


def test_scheduled_then_fires_when_due(env):  # noqa: F811
    db, o = env
    _wire(o)
    ids = [o.add("res.partner", name=f"P{i}", email=f"p{i}@x.io") for i in range(3)]
    bid = _batch(db, tool="message", model="res.partner", ids=ids, change={"body": "Hello", "kind": "note", "send_at": _iso(hours=1)})
    rsc.batch_check("c1", bid, db)
    run = rsc.batch_run("c1", bid, None, db)
    assert run["payload"]["state"] == "scheduled" and not o.posted
    tray = rsc.change_runs("c1", db)["runs"][0]
    assert tray["state"] == "scheduled" and tray["fire_at"]
    assert rsc.fire_due(db) == []
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(hours=2)) == [run["id"]]
    assert len(o.posted) == 3 and rsc.change_run_get("c1", run["id"], db)["payload"]["counts"]["done"] == 3
    with pytest.raises(HTTPException) as e:
        rsc.change_run_cancel("c1", run["id"], db)
    assert e.value.status_code == 409


def test_cancel_before_it_fires_sends_nothing(env):  # noqa: F811
    db, o = env
    _wire(o)
    ids = [o.add("res.partner", name="P", email="p@x.io")]
    bid = _batch(db, tool="message", model="res.partner", ids=ids, change={"body": "Hello", "send_at": _iso(minutes=30)})
    rsc.batch_check("c1", bid, db)
    rid = rsc.batch_run("c1", bid, None, db)["id"]
    assert rsc.change_run_stop("c1", rid, db)["state"] == "cancelled"
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(days=1)) == [] and not o.posted


def test_next_send_and_repeat_validation():
    d = datetime(2026, 1, 31, 9, 0, tzinfo=UTC)
    assert sc.next_send(d, "monthly") == datetime(2026, 2, 28, 9, 0, tzinfo=UTC)
    assert sc.next_send(datetime(2026, 12, 15, tzinfo=UTC), "monthly") == datetime(2027, 1, 15, tzinfo=UTC)
    assert sc.next_send(d, "weekly") == datetime(2026, 2, 7, 9, 0, tzinfo=UTC)
    fm = {"message_ids": {}}
    b = {"tool": "message", "model": "res.partner", "change": {"body": "Hi", "send_at": _iso(hours=1), "repeat": {"every": "daily", "until": _iso(days=3)}}}
    assert sc.refuse(b, fm) is None
    assert "end date" in sc.refuse({**b, "change": {**b["change"], "repeat": {"every": "daily", "until": _iso(minutes=5)}}}, fm)
    assert "daily" in sc.refuse({**b, "change": {**b["change"], "repeat": {"every": "hourly", "until": _iso(days=3)}}}, fm)
    assert "first send" in sc.refuse({**b, "change": {"body": "Hi", "repeat": {"every": "daily", "until": _iso(days=3)}}}, fm)


def test_repeat_queues_next_until_end_and_cancel_ends_series(env):  # noqa: F811
    db, o = env
    _wire(o)
    ids = [o.add("res.partner", name="P", email="p@x.io")]
    bid = _batch(db, tool="message", model="res.partner", ids=ids, change={"body": "Daily", "send_at": _iso(hours=1), "repeat": {"every": "daily", "until": _iso(days=2, hours=2)}})
    rsc.batch_check("c1", bid, db)
    first = rsc.batch_run("c1", bid, None, db)["id"]
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(hours=2)) == [first] and len(o.posted) == 1
    pend = [r for r in rsc.change_runs("c1", db)["runs"] if r["state"] == "scheduled"]
    assert len(pend) == 1 and pend[0]["occurrence"] == 2
    second = pend[0]["id"]
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(days=1, hours=2)) == [second] and len(o.posted) == 2
    third = [r for r in rsc.change_runs("c1", db)["runs"] if r["state"] == "scheduled"][0]["id"]
    rsc.change_run_cancel("c1", third, db)
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(days=5)) == [] and len(o.posted) == 2
    assert not [r for r in rsc.change_runs("c1", db)["runs"] if r["state"] == "scheduled"]


def test_reschedule_moves_time_only(env):  # noqa: F811
    db, o = env
    _wire(o)
    ids = [o.add("res.partner", name="P", email="p@x.io")]
    bid = _batch(db, tool="message", model="res.partner", ids=ids, change={"body": "Later", "send_at": _iso(hours=1)})
    rsc.batch_check("c1", bid, db)
    rid = rsc.batch_run("c1", bid, None, db)["id"]
    out = rsc.change_run_reschedule("c1", rid, rsc.RescheduleBody(send_at=_iso(hours=5)), db)
    assert out["state"] == "scheduled"
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(hours=2)) == [] and not o.posted
    assert rsc.fire_due(db, now=datetime.now(UTC) + timedelta(hours=6)) == [rid] and len(o.posted) == 1
    with pytest.raises(HTTPException) as e:
        rsc.change_run_reschedule("c1", rid, rsc.RescheduleBody(send_at=_iso(hours=9)), db)
    assert e.value.status_code == 409
    with pytest.raises(HTTPException) as e:
        rsc.change_run_reschedule("c1", rid, rsc.RescheduleBody(send_at=_iso(hours=-1)), db)
    assert e.value.status_code == 422


def test_move_one_send_keeps_series_times(env):  # noqa: F811
    db, o = env
    _wire(o)
    ids = [o.add("res.partner", name="P", email="p@x.io")]
    start = datetime.now(UTC) + timedelta(hours=1)
    bid = _batch(db, tool="message", model="res.partner", ids=ids, change={"body": "W", "send_at": start.isoformat(), "repeat": {"every": "weekly", "until": (start + timedelta(days=30)).isoformat()}})
    rsc.batch_check("c1", bid, db)
    rid = rsc.batch_run("c1", bid, None, db)["id"]
    rsc.change_run_reschedule("c1", rid, rsc.RescheduleBody(send_at=(start + timedelta(hours=3)).isoformat()), db)
    rsc.fire_due(db, now=start + timedelta(hours=4))
    nxt = [r for r in rsc.change_runs("c1", db)["runs"] if r["state"] == "scheduled"][0]
    assert datetime.fromisoformat(nxt["fire_at"]) == start + timedelta(days=7)  # not shifted by the 3 hours
    rsc.change_run_reschedule("c1", nxt["id"], rsc.RescheduleBody(send_at=(start + timedelta(days=7, hours=5)).isoformat(), move="series"), db)
    rsc.fire_due(db, now=start + timedelta(days=7, hours=6))
    third = [r for r in rsc.change_runs("c1", db)["runs"] if r["state"] == "scheduled"][0]
    assert datetime.fromisoformat(third["fire_at"]) == start + timedelta(days=14, hours=5)  # series shifted
