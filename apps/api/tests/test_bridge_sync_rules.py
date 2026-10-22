from app.bridge.sync_rules import (
    FieldRule,
    RetryPolicy,
    TokenBucket,
    check_trigger,
    idempotency_key,
    match_record,
    order_batch,
    resolve,
)

C = [
    {"id": 1, "name": "Ada Obi", "email": "ada@x.ng"},
    {"id": 2, "name": "Ada Obi Ltd", "email": "a@y.ng"},
    {"id": 3, "name": "Bayo", "phone": "+234 803 111 2222"},
]


def test_matching():
    assert match_record({"email": "ADA@x.ng "}, C) == {
        "action": "link",
        "id": 1,
        "by": "email",
        "score": 1.0,
    }
    assert match_record({"phone": "08031112222"}, C)["id"] == 3
    assert match_record({"name": "Ada Obi"}, C)["action"] == "review"  # never auto-links on name
    assert match_record({"name": "Zainab Musa"}, C)["action"] == "create"
    assert (
        match_record({"email": "x@z"}, C + [{"id": 4, "email": "x@z"}, {"id": 5, "email": "x@z"}])[
            "action"
        ]
        == "review"
    )


def test_conflicts_and_money_guard():
    r = FieldRule("phone", "both", "newest")
    assert resolve(r, "1", "2", odoo_ts=5, app_ts=9, last_synced="0")["target"] == "odoo"
    assert (
        resolve(r, "1", "2", odoo_ts=5, app_ts=9, last_synced="1")["action"] == "set"
    )  # only app moved
    m = FieldRule("amount", "both", "app_wins", money=True)
    assert m.conflict == "ask" and resolve(m, 10, 12, 1, 2, last_synced=9)["action"] == "review"
    assert resolve(FieldRule("x", "out"), 1, 2, 1, 2)["action"] == "skip"


def test_triggers_delivery():
    assert check_trigger({"kind": "schedule", "cron": "*/15 * * * *"}) == []
    assert check_trigger({"kind": "schedule", "cron": "*/1 * * * *"}) and check_trigger(
        {"kind": "webhook"}
    )
    p = RetryPolicy()
    assert (
        p.classify(200, 1) == "done"
        and p.classify(429, 1) == "retry"
        and p.classify(400, 1) == "dead"
        and p.classify(503, 8) == "dead"
    )
    assert p.next_delay(3, rnd=lambda: 0.5) == 8.0 and p.next_delay(1, retry_after=30) == 30
    t = [0.0]
    b = TokenBucket(2, 2, clock=lambda: t[0])
    assert b.take() == 0 and b.take() == 0 and b.take() > 0
    t[0] = 1.0
    assert b.take() == 0
    assert idempotency_key("c", "o", 1, {"a": 1, "b": 2}) == idempotency_key(
        "c", "o", 1, {"b": 2, "a": 1}
    )
    w = order_batch(
        [
            {"entity": "o", "remote_id": 1, "seq": 2},
            {"entity": "o", "remote_id": 1, "seq": 1},
            {"entity": "o", "remote_id": 2, "seq": 1},
        ]
    )
    assert [e["seq"] for e in w[0]] == [1, 1] and w[1][0]["seq"] == 2
