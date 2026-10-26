"""BOT-APPROVAL-TIERS: tiers, plan-bound single-use grants, audited decisions, run wiring.
Shares the BOT-KILL-AUDIT throwaway DB (alembic head incl. bot_approval)."""

from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.bots import approval as ap
from app.bots import guard as gd
from app.bots.audit import AuditLog
from app.routers import bot_approvals as rt
from app.workspace_auth import WorkspaceAuth
from tests.test_nf_bot_kill_audit import (  # noqa: F401 - shared fixture
    ANCHOR,
    FP,
    OWNER,
    REH,
    Rpc,
    _clean,
    engine,
    run,
    spec,
)

CONN, MODEL, VALS = "conn-a", "res.partner.category", {"name": "x"}
TASK = "m:res.partner.category:change"
JARGON = ("lane", "grain", " ir", "rpc", "hash")


def plan(ids=(1, 2, 3), cls="R1", **kw) -> ap.Plan:
    base = dict(
        connection_id=CONN,
        db_fingerprint=FP,
        task_id=TASK,
        model=MODEL,
        ids=list(ids),
        values=VALS,
        risk_class=cls,
        requested_by="bot-1",
        summary="Rename tags",
        rehearsal_id="rh-1",
        rehearsal_passed=True,
        undo_route="before_image",
    )
    return ap.Plan(**{**base, **kw})


@pytest.fixture
def env(engine):  # noqa: F811
    _clean(engine)
    with engine.begin() as c:
        c.execute(text("DELETE FROM bot_approval"))
    sw = gd.KillSwitch(engine, lambda scope: OWNER)
    log = AuditLog(engine, anchor=ANCHOR)
    store = ap.ApprovalStore(engine, sw, log)
    sw.grant_source = store.grant_source
    gate = gd.WriteGate(sw, log, Rpc(), ap.TierRehearsals(REH, store))
    return engine, sw, log, store, gate


def go(gate, store, cls="R1", ids=(1, 2, 3), level=None, approver=None, grant=None):
    p = plan(ids, cls)
    a = store.approval_for(FP, p.hash())
    a = gd.Approval(level if level is not None else a.level, approver or a.approver, grant)
    return run(gate, spec(risk_class=cls, approval=a), list(ids))


def grants(e) -> list[tuple]:
    with e.connect() as c:
        return [
            tuple(r) for r in c.execute(text("SELECT level, n_records, used_at FROM bot_grant"))
        ]


# ------------------------------------------------------------------ classify
@pytest.mark.parametrize(
    ("kw", "tier"),
    [
        ({}, 1),
        ({"risk_class": "R3"}, 2),
        ({"outside_plan": frozenset({"write_uid_x"})}, 2),
        ({"irreversible": True, "undo_route": "snapshot", "snapshot_verified": True}, 3),
        ({"ids": list(range(1, 502))}, 3),
        ({"risk_class": "R6", "undo_route": "snapshot", "snapshot_verified": True}, 3),
    ],
)
def test_tiers_only_go_up(kw, tier) -> None:
    t = ap.classify(plan(**kw))
    assert t.tier == tier and t.refusal is None and t.reasons
    assert not any(j in r.lower() for r in t.reasons for j in JARGON)


@pytest.mark.parametrize(
    "kw",
    [
        {"rehearsal_id": None},
        {"rehearsal_passed": False},
        {"undo_route": None},
        {"irreversible": True},  # no verified backup
        {"irreversible": True, "undo_route": "snapshot"},  # backup not verified
        {"subkind": "delete"},
        {"risk_class": "R99"},
        {"ids": []},
        {"values": {}},
    ],
)
def test_missing_proof_is_refused_not_lowered(kw) -> None:
    t = ap.classify(plan(**kw))
    assert t.tier is None and t.refusal


def test_checkpoint_tightened_raises_tier() -> None:
    assert ap.classify(plan(ids=range(1, 12)), checkpoint=10).tier == 3


# ------------------------------------------------------------------ store + decisions
def test_submit_status_and_idempotent(env) -> None:
    eng, sw, log, store, gate = env
    assert store.submit(plan())["status"] == "auto"
    r = store.submit(plan(ids=(4, 5, 6), cls="R3"))
    assert r["status"] == "pending" and r["tier"] == 2 and r["n_records"] == 3
    assert "grant_id" not in r and len(r["card"]["limits"]) == 3
    # same plan resubmitted: never relaxed, only made stricter
    assert store.submit(plan(ids=(4, 5, 6), cls="R1"))["status"] == "pending"
    esc = store.submit(plan(cls="R3"))  # was auto (L1): now needs approval
    assert esc["status"] == "pending" and esc["tier"] == 2
    gone = store.submit(plan(ids=(4, 5, 6), cls="R3", rehearsal_passed=False))
    assert gone["id"] == r["id"] and gone["status"] == "refused"
    assert store.submit(plan(ids=(9,), rehearsal_id=None))["status"] == "refused"


def test_approve_issues_grant_at_stored_tier_and_audits(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    out = store.approve(CONN, r["id"], OWNER)
    assert out["status"] == "approved" and out["decided_by"] == OWNER
    assert grants(eng) == [(2, 3, None)]
    assert log.verify_chain()[0]
    with eng.connect() as c:
        d = c.execute(text("SELECT decision, approval_level FROM bot_audit")).all()
    assert [tuple(x) for x in d] == [("approved", 2)]
    with pytest.raises(ap.ApprovalError) as e:
        store.approve(CONN, r["id"], OWNER)
    assert e.value.code == "conflict"


@pytest.mark.parametrize(
    ("who", "code"), [("bot-1", "forbidden"), ("bot-2", "forbidden"), ("mallory", "forbidden")]
)
def test_only_owner_human_not_requester(env, who, code) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    with pytest.raises(ap.ApprovalError) as e:
        store.approve(CONN, r["id"], who)
    assert e.value.code == code and grants(eng) == []
    assert store.get(CONN, r["id"])["status"] == "pending"


def test_other_connection_cannot_see_or_decide(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    for fn in (
        lambda: store.get("conn-b", r["id"]),
        lambda: store.approve("conn-b", r["id"], OWNER),
    ):
        with pytest.raises(ap.ApprovalError) as e:
            fn()
        assert e.value.code == "not_found"
    assert store.list("conn-b") == []


def test_concurrent_approvals_one_wins(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    out: list[Any] = []
    barrier = threading.Barrier(4)

    def worker() -> None:
        barrier.wait()
        try:
            out.append(store.approve(CONN, r["id"], OWNER)["status"])
        except ap.ApprovalError as exc:
            out.append(exc.code)

    ts = [threading.Thread(target=worker) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(out) == ["approved", "conflict", "conflict", "conflict"]
    assert len(grants(eng)) == 1


def test_approve_vs_reject_race_one_wins(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    out: list[str] = []
    barrier = threading.Barrier(2)

    def w(fn) -> None:
        barrier.wait()
        try:
            out.append(fn(CONN, r["id"], OWNER)["status"])
        except ap.ApprovalError as exc:
            out.append(exc.code)

    ts = [threading.Thread(target=w, args=(f,)) for f in (store.approve, store.reject)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert "conflict" in out and len(out) == 2
    final = store.get(CONN, r["id"])["status"]
    assert final in out and len(grants(eng)) == (1 if final == "approved" else 0)


# ------------------------------------------------------------------ run wiring
def test_l1_auto_runs_and_l2_approved_runs(env) -> None:
    eng, sw, log, store, gate = env
    store.submit(plan())
    assert go(gate, store).status == "done"
    r = store.submit(plan(ids=(4, 5), cls="R3"))
    assert go(gate, store, "R3", (4, 5)).status == "refused"  # pending
    store.approve(CONN, r["id"], OWNER)
    assert go(gate, store, "R3", (4, 5)).written == 2
    assert store.route_approval(FP, plan((4, 5), "R3").hash()) == 2


def test_unknown_plan_rejected_pending_never_run(env) -> None:
    eng, sw, log, store, gate = env
    rpc = gate._rpc
    assert go(gate, store).status == "refused"  # no record at all (even L1)
    r = store.submit(plan(cls="R3"))
    store.reject(CONN, r["id"], OWNER)
    assert go(gate, store, "R3", level=3, approver=OWNER).status == "refused"
    store.submit(plan(cls="R3"))  # resubmitting does not revive it
    assert go(gate, store, "R3", level=3, approver=OWNER).status == "refused"
    store.submit(plan(ids=(7,), rehearsal_id=None))
    assert go(gate, store, ids=(7,)).status == "refused"
    assert rpc.calls == [] and grants(eng) == []
    assert store.route_approval(FP, plan(cls="R3").hash()) == 0


def test_forged_grant_ignored_and_grant_bound_to_plan(env) -> None:
    eng, sw, log, store, gate = env
    a = store.submit(plan(cls="R3"))
    store.submit(plan(ids=(8, 9), cls="R3"))
    store.approve(CONN, a["id"], OWNER)
    with eng.connect() as c:
        gid = c.execute(
            text("SELECT grant_id FROM bot_approval WHERE id=:i"), {"i": a["id"]}
        ).scalar()
    # plan B is pending: presenting plan A's real grant, or a forged id, gets nowhere
    for g in (gid, "f" * 32):
        assert go(gate, store, "R3", (8, 9), level=2, approver=OWNER, grant=g).status == "refused"
    plan_b = plan((8, 9), "R3").hash()
    ref = sw.open_job(FP, plan_b, 2, 2, gid, gd.Approval(2, OWNER), "bot-1", "rh-1")
    assert isinstance(ref, gd.Refusal)
    assert gate._rpc.calls == []


def test_replayed_grant_refused(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    rep = go(gate, store, "R3")
    assert rep.status == "done"
    sw.set_job(rep.job_id, "failed")  # job closed: the used grant can't open another
    before = len(gate._rpc.calls)
    assert go(gate, store, "R3").status == "refused"
    assert len(gate._rpc.calls) == before


def test_n_plus_one_refused(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    a = store.approval_for(FP, plan(cls="R3").hash())
    rep = run(gate, spec(risk_class="R3", approval=a), [1, 2, 3, 4])
    assert rep.status == "refused" and gate._rpc.calls == []
    assert grants(eng)[0][2] is None  # grant still unused


def test_tier_downgrade_refused(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    # claiming the plan is lower risk changes nothing: stored class must match
    assert go(gate, store, "R1", level=1).status == "refused"
    # a client saying level 1 still runs at the stored grant's level
    rep = go(gate, store, "R3", level=1, approver=OWNER)
    assert rep.status == "done"
    with eng.connect() as c:
        assert c.execute(text("SELECT level FROM bot_job")).scalar() == 2


def test_route_a_gets_stored_tier(env) -> None:
    eng, sw, log, store, gate = env
    store.submit(plan())
    assert store.route_approval(FP, plan().hash()) == 1  # L1: outside-plan changes trip
    assert store.route_approval(FP, "0" * 64) == 0


# ------------------------------------------------------------------ API
def _client(store, auth: WorkspaceAuth, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(rt.router, prefix="/api")
    app.dependency_overrides[rt.store_for] = lambda: lambda _actor: store
    app.dependency_overrides[rt._conn_id] = lambda connection_id: (
        connection_id if connection_id == CONN else (_ for _ in ()).throw(KeyError())
    )
    monkeypatch.setattr(rt, "get_workspace_auth", lambda _r: auth)
    return TestClient(app, raise_server_exceptions=False)


OWNER_AUTH = WorkspaceAuth(mode="accounts", email=OWNER, role="owner")


def test_api_list_card_approve(env, monkeypatch) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.submit(plan(ids=(5,), rehearsal_id=None))
    c = _client(store, OWNER_AUTH, monkeypatch)
    items = c.get(f"/api/connections/{CONN}/bot-approvals").json()["items"]
    assert items[0]["status"] == "pending" and {i["status"] for i in items} == {
        "pending",
        "refused",
    }
    card = c.get(f"/api/connections/{CONN}/bot-approvals/{r['id']}").json()["card"]
    assert card["records"] == 3 and card["undo"]["available"] and card["rehearsal"]["passed"]
    # body cannot set tier or N
    res = c.post(f"/api/connections/{CONN}/bot-approvals/{r['id']}/approve", json={"tier": 1})
    assert res.status_code == 200 and res.json()["tier"] == 2
    assert c.post(f"/api/connections/{CONN}/bot-approvals/{r['id']}/reject").status_code == 409
    assert c.get(f"/api/connections/{CONN}/bot-approvals/nope").status_code == 404


@pytest.mark.parametrize(
    "auth",
    [
        WorkspaceAuth(mode="off"),
        WorkspaceAuth(mode="api_key", email=OWNER, role="owner"),
        WorkspaceAuth(mode="accounts", email=OWNER, role="viewer"),
        WorkspaceAuth(mode="accounts", role="owner"),
    ],
)
def test_api_decider_must_be_signed_in_owner(env, monkeypatch, auth) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    c = _client(store, auth, monkeypatch)
    for act in ("approve", "reject"):
        assert c.post(f"/api/connections/{CONN}/bot-approvals/{r['id']}/{act}").status_code == 403
    assert store.get(CONN, r["id"])["status"] == "pending" and grants(eng) == []


# ------------------------------------------------------------------ review round 2
def _grant_used(eng) -> list[bool]:
    with eng.connect() as c:
        return [r[0] is not None for r in c.execute(text("SELECT used_at FROM bot_grant"))]


def test_a01_stricter_facts_after_approval_block_the_run(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    again = store.submit(plan(cls="R3", irreversible=True))  # no checked backup
    assert again["status"] == "refused" and again["tier"] is None
    assert _grant_used(eng) == [True]  # stored grant voided
    assert go(gate, store, "R3", level=2, approver=OWNER).status == "refused"
    assert gate._rpc.calls == []


def test_a01_any_fact_change_needs_reapproval(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    again = store.submit(plan(cls="R3", outside_plan=frozenset({"street"})))
    assert again["status"] == "pending" and again["tier"] == 2 and again["decided_by"] is None
    assert go(gate, store, "R3", level=2, approver=OWNER).status == "refused"
    store.approve(CONN, r["id"], OWNER)  # a person approves the new facts
    assert go(gate, store, "R3").status == "done"
    assert sorted(_grant_used(eng)) == [True, True]


def test_a01_facts_mismatch_fails_closed_in_reserve_and_grant_source(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    with eng.begin() as c:  # simulate drift between the approved and current facts
        c.execute(text("ALTER TABLE bot_approval DISABLE TRIGGER bot_approval_guard"))
        c.execute(text("ALTER TABLE bot_approval DROP CONSTRAINT ck_bot_approval"))
        c.execute(text("UPDATE bot_approval SET facts_hash=:f"), {"f": "e" * 64})
    try:
        h = plan(cls="R3").hash()
        assert store.grant_source(sw, gd.Approval(2, OWNER), FP, h, 3, "bot-1", "rh-1") is None
        assert store.route_approval(FP, h) == 0
        assert go(gate, store, "R3", level=2, approver=OWNER).status == "refused"
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM bot_approval"))
            c.execute(text("ALTER TABLE bot_approval ENABLE TRIGGER bot_approval_guard"))
            c.execute(
                text(
                    "ALTER TABLE bot_approval ADD CONSTRAINT ck_bot_approval CHECK"
                    " (status IN ('auto','pending','approved','rejected','refused')"
                    " AND n_records > 0 AND (tier IS NULL OR tier BETWEEN 1 AND 3)"
                    " AND (status <> 'refused' OR tier IS NULL)"
                    " AND (status NOT IN ('auto','pending','approved') OR tier IS NOT NULL)"
                    " AND (status <> 'auto' OR tier = 1) AND (status <> 'approved' OR"
                    " (grant_id IS NOT NULL AND decided_facts_hash = facts_hash)))"
                )
            )


def _as_bot(eng, sql: str, **p) -> None:
    with eng.begin() as c:
        c.execute(text("SET LOCAL ROLE bot_app"))
        c.execute(text(sql), p)


def test_a03_bot_role_cannot_decide_or_relax(env) -> None:
    eng, sw, log, store, gate = env
    with eng.connect() as c:
        assert not c.execute(
            text("SELECT has_table_privilege('bot_app','bot_approval','UPDATE')")
        ).scalar()
    p = store.submit(plan(cls="R3"))
    rj = store.submit(plan(ids=(4,), cls="R3"))
    store.reject(CONN, rj["id"], OWNER)
    bad = [
        ("UPDATE bot_approval SET status='rejected', decided_by='x' WHERE id=:i", p["id"]),
        ("UPDATE bot_approval SET status='auto', tier=1 WHERE id=:i", p["id"]),
        ("UPDATE bot_approval SET status='pending' WHERE id=:i", rj["id"]),
        ("UPDATE bot_approval SET n_records=1 WHERE id=:i", p["id"]),
    ]
    for sql, i in bad:
        with pytest.raises(Exception):  # noqa: B017 - permission or trigger refusal
            _as_bot(eng, sql, i=i)
    assert store.get(CONN, p["id"])["status"] == "pending"
    assert store.get(CONN, rj["id"])["status"] == "rejected"


def test_a03_trigger_freezes_decided_rows_for_everyone(env) -> None:
    eng, sw, log, store, gate = env
    a = store.submit(plan(cls="R3"))
    store.approve(CONN, a["id"], OWNER)
    for sql in (
        "UPDATE bot_approval SET tier=3 WHERE id=:i",  # approved: only escalation path
        "UPDATE bot_approval SET status='auto', tier=1, grant_id=NULL WHERE id=:i",
    ):
        with pytest.raises(Exception):  # noqa: B017
            with eng.begin() as c:
                c.execute(text(sql), {"i": a["id"]})
    # the escalation path stays open to the owner role; the bot role has no UPDATE
    with eng.begin() as c:
        c.execute(text(
        "UPDATE bot_approval SET status='pending', grant_id=NULL, decided_by=NULL,"
        " decided_at=NULL, decided_facts_hash=NULL WHERE id=:i"), {"i": a["id"]})
    assert store.get(CONN, a["id"])["status"] == "pending"


def test_a04_refused_plan_reevaluated_rejected_stays(env) -> None:
    eng, sw, log, store, gate = env
    assert store.submit(plan(rehearsal_passed=False))["status"] == "refused"
    fixed = store.submit(plan())
    assert fixed["status"] == "auto" and fixed["tier"] == 1
    assert go(gate, store).status == "done"
    r = store.submit(plan(ids=(4,), cls="R3"))
    store.reject(CONN, r["id"], OWNER)
    assert store.submit(plan(ids=(4,), cls="R3", outside_plan=frozenset({"x"})))["status"] == (
        "rejected"
    )


def test_l3_label_matches_who_can_approve() -> None:
    assert "owner or admin" in ap.TIER_LABEL[3]
    assert set(rt._DECIDERS) == {"owner", "admin"}


_FORGED = (
    "INSERT INTO bot_approval (id, connection_id, db_fingerprint, plan_hash, task_id,"
    " risk_class, n_records, tier, status, rehearsal_id, requested_by, card, grant_id,"
    " facts_hash, decided_facts_hash, decided_by) VALUES (:i, :c, :d, :p, :t, 'R3', 3, 2,"
    " 'approved', 'rh-1', 'bot-1', '{}', :g, :f, :f, 'owner@x')"
)


def test_b01_bot_cannot_mint_grant_and_self_approve(env) -> None:
    eng, sw, log, store, gate = env
    from app.bots.approval import facts_hash

    p, g = plan(cls="R3"), uuid.uuid4().hex
    with pytest.raises(Exception):  # noqa: B017 - no INSERT on bot_grant
        _as_bot(
            eng,
            "INSERT INTO bot_grant (id, db_fingerprint, plan_hash, n_records, level,"
            " approver_norm, created_by, rehearsal_id, expires_at) VALUES (:g, :d, :p, 3, 2,"
            " 'owner@x', 'owner@x', 'rh-1', now() + interval '1 hour')",
            g=g, d=FP, p=p.hash(),
        )
    with pytest.raises(Exception):  # noqa: B017 - trigger refuses a decided insert
        _as_bot(eng, _FORGED, i=uuid.uuid4().hex, c=CONN, d=FP, p=p.hash(), t=p.task_id,
                g=g, f=facts_hash(p))
    assert go(gate, store, "R3").status != "done"
    assert gate._rpc.calls == []
    with eng.connect() as c:
        assert not c.execute(
            text("SELECT has_table_privilege('bot_app','bot_grant','INSERT')")
        ).scalar()


def test_b01_forged_approved_insert_refused_even_with_real_grant(env) -> None:
    eng, sw, log, store, gate = env
    from app.bots.approval import facts_hash

    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    with eng.connect() as c:
        g = c.execute(text("SELECT grant_id FROM bot_approval WHERE id=:i"), {"i": r["id"]})
        g = g.scalar()
    q = plan(ids=(7,), cls="R3")
    for status in ("approved", "rejected"):
        with pytest.raises(Exception):  # noqa: B017
            _as_bot(eng, _FORGED.replace("'approved'", f"'{status}'"), i=uuid.uuid4().hex,
                    c=CONN, d=FP, p=q.hash(), t=q.task_id, g=g, f=facts_hash(q))
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM bot_approval WHERE plan_hash=:p"),
                      {"p": q.hash()}).scalar()
    assert n == 0


def test_void_on_resubmit_writes_audit_row(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    store.submit(plan(cls="R3", outside_plan=frozenset({"street"})))
    with eng.connect() as c:
        rows = c.execute(
            text("SELECT decision, reason FROM bot_audit WHERE idempotency_key LIKE :k"),
            {"k": f"approval:{r['id']}:void:%"},
        ).all()
    assert [tuple(x) for x in rows] == [("refused", "approval voided: plan facts changed")]


# ------------------------------------------------------------------ bot role at runtime
@pytest.fixture
def bot_env(env):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from tests.test_nf_bot_kill_audit import DB, HOST

    eng, sw, log, store, _ = env
    role, pw = f"ingenium_wt_botrt_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    with eng.begin() as c:
        c.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' IN ROLE bot_app"))
    bot = create_engine(f"postgresql+psycopg://{role}:{pw}@{HOST}/{DB}", poolclass=NullPool)
    bsw = gd.KillSwitch(bot, lambda scope: OWNER)
    bsw.grant_source = store.grant_source
    gate = gd.WriteGate(bsw, AuditLog(bot, anchor=ANCHOR), Rpc(), ap.TierRehearsals(REH, store))
    try:
        yield eng, bot, store, gate
    finally:
        bot.dispose()
        with eng.begin() as c:
            c.execute(text(f"DROP ROLE {role}"))


def _bot_sql(bot, sql: str, **p) -> None:
    with bot.begin() as c:
        c.execute(text(sql), p)


@pytest.mark.parametrize("status", ["auto", "pending", "approved", "rejected", "refused"])
def test_bot_role_cannot_insert_approval_rows(env, status) -> None:
    eng, sw, log, store, gate = env
    from app.bots.approval import facts_hash

    q = plan(ids=(8,), cls="R1")
    with pytest.raises(Exception):  # noqa: B017 - no INSERT privilege
        _as_bot(eng, _FORGED.replace("'approved'", f"'{status}'").replace(":g", "NULL"),
                i=uuid.uuid4().hex, c=CONN, d=FP, p=q.hash(), t=q.task_id, f=facts_hash(q))
    with eng.connect() as c:
        for priv in ("INSERT", "UPDATE"):
            assert not c.execute(
                text(f"SELECT has_table_privilege('bot_app','bot_approval','{priv}')")
            ).scalar()


def test_bot_runtime_honest_runs_still_work(bot_env) -> None:
    eng, bot, store, gate = bot_env
    store.submit(plan(cls="R1"))  # auto, owner-written
    assert go(gate, store, "R1").status == "done"
    r = store.submit(plan(ids=(4, 5), cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    assert go(gate, store, "R3", ids=(4, 5)).status == "done"


def test_bot_runtime_refuses_plan_without_owner_auto_row(bot_env) -> None:
    eng, bot, store, gate = bot_env
    assert run(gate, spec(risk_class="R1", approval=gd.Approval(1, None, None)),
                               [1, 2, 3]).status != "done"
    assert gate._rpc.calls == []


def test_bot_cannot_forge_live_job(bot_env) -> None:
    eng, bot, store, gate = bot_env
    p = plan(cls="R3")
    sql = ("INSERT INTO bot_job (id, db_fingerprint, plan_hash, n_records, level, grant_id,"
           " status) VALUES (:j, :d, :p, 3, :l, NULL, 'open')")
    for lvl in (1, 3):  # no auto row / no consumed grant
        with pytest.raises(Exception):  # noqa: B017
            _bot_sql(bot, sql, j=uuid.uuid4().hex, d=FP, p=p.hash(), l=lvl)
    store.submit(plan(ids=(9,), cls="R1"))
    assert go(gate, store, "R1", ids=(9,)).status == "done"
    with bot.connect() as c:
        jid = c.execute(text("SELECT id FROM bot_job WHERE n_records=1")).scalar()
    with pytest.raises(Exception):  # noqa: B017 - finished jobs never reopen
        _bot_sql(bot, "UPDATE bot_job SET status='open' WHERE id=:j", j=jid)
    with pytest.raises(Exception):  # noqa: B017 - only status is writable
        _bot_sql(bot, "UPDATE bot_job SET level=3 WHERE id=:j", j=jid)


def test_bot_cannot_disarm_switch_or_raise_caps(bot_env) -> None:
    eng, bot, store, gate = bot_env
    gd.KillSwitch(bot, lambda s: OWNER).turn_on(FP, "system", "trip")  # allowed
    for sql in (
        "UPDATE bot_kill_switch SET is_on=false",
        "DELETE FROM bot_kill_switch",
        "INSERT INTO bot_cap_override VALUES ('x', 999, 999, 'bot')",
        "UPDATE bot_cap_override SET run_cap=999",
    ):
        with pytest.raises(Exception):  # noqa: B017
            _bot_sql(bot, sql)
    with eng.connect() as c:
        assert c.execute(text("SELECT is_on FROM bot_kill_switch WHERE scope=:d"),
            {"d": FP},
        ).scalar()


def test_c03_c05_bot_cannot_move_an_on_switch(env) -> None:
    eng, sw, log, store, gate = env
    with eng.begin() as c:
        c.execute(text("DELETE FROM bot_kill_switch"))
    sw.turn_off(gd.GLOBAL, OWNER, "t")
    sw.turn_on(FP, OWNER, "t")
    for sql in (
        "UPDATE bot_kill_switch SET scope = scope || '-moved' WHERE scope = :i",
        "UPDATE bot_kill_switch SET is_on = false WHERE scope = :i",
    ):
        with pytest.raises(Exception):  # noqa: B017
            _as_bot(eng, sql, i=FP)
    assert sw.check(FP) is not None


def test_c06_used_grant_cannot_be_repointed_or_replayed(env) -> None:
    eng, sw, log, store, gate = env
    r = store.submit(plan(cls="R3"))
    store.approve(CONN, r["id"], OWNER)
    rep = go(gate, store, "R3")
    assert rep.status == "done"
    with eng.connect() as c:
        gid = c.execute(text("SELECT grant_id FROM bot_job WHERE id=:i"),
                        {"i": rep.job_id}).scalar()
    for sql, kw in (
        ("UPDATE bot_job SET status='failed' WHERE id=:i", {"i": rep.job_id}),
        ("UPDATE bot_grant SET job_id=:i WHERE id=:g", {"i": uuid.uuid4().hex, "g": gid}),
        ("UPDATE bot_grant SET used_at=NULL WHERE id=:g", {"g": gid}),
    ):
        with pytest.raises(Exception):  # noqa: B017
            _as_bot(eng, sql, **kw)
    with pytest.raises(Exception):  # noqa: B017 - a second L2 job on the used grant
        _as_bot(eng, "INSERT INTO bot_job (id, db_fingerprint, plan_hash, n_records, level,"
                " grant_id, status) SELECT :n, db_fingerprint, plan_hash, n_records, level,"
                " grant_id, 'open' FROM bot_job WHERE id=:i", n=uuid.uuid4().hex, i=rep.job_id)


@pytest.mark.parametrize("table", ["bot_kill_switch", "bot_grant", "bot_approval", "bot_job"])
def test_temp_shadow_refused_for_bot_login_role(bot_env, table) -> None:
    eng, bot, store, gate = bot_env
    with pytest.raises(Exception), bot.begin() as c:  # noqa: B017 - no TEMP privilege
        c.execute(text(f"CREATE TEMP TABLE {table} (scope text, is_on bool)"))


def test_d99_kill_switch_stays_on_for_bot_connection(bot_env) -> None:
    eng, bot, store, gate = bot_env
    sw = gd.KillSwitch(eng, lambda s: OWNER)
    sw.turn_off(gd.GLOBAL, OWNER, "t")
    sw.turn_on(FP, OWNER, "t")
    with bot.connect() as c:
        with pytest.raises(Exception):  # noqa: B017
            c.execute(text("CREATE TEMP TABLE bot_kill_switch (scope text, is_on bool)"))
        c.rollback()

        class One:  # the same pooled bot connection the shadow attempt used
            def connect(self):
                class Ctx:
                    def __enter__(s):
                        return c

                    def __exit__(s, *a):
                        return False

                return Ctx()

        assert gd.KillSwitch(One(), lambda s: OWNER).check(FP) is not None


def test_bot_login_role_cannot_set_role_or_create_large_objects(bot_env) -> None:
    eng, bot, store, gate = bot_env
    with eng.connect() as c:
        owner = c.execute(text("SELECT current_user")).scalar()
    for sql in (f'SET ROLE "{owner}"', "SELECT lo_create(0)", "SELECT lo_from_bytea(0, 'x')"):
        with pytest.raises(Exception), bot.begin() as c:  # noqa: B017
            c.execute(text(sql))
