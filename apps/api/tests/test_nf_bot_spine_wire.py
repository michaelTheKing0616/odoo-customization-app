"""BOT-SPINE-WIRE: session-bound decisions, store tiers, graded refusals, T3 approval items."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from app.bot_verify import targets as tg
from app.bots import approval as ap
from app.bots import guard as gd
from app.bots import module_test_gate as mtg
from app.bots import owned_change as oc
from app.bots import spine as sp
from app.bots import tiers as tr
from app.bots import versioncaps as vc
from app.bots.audit import AuditLog
from app.bots.operator_flow import flow as fl
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    FP,
    OWNER,
    REH,
    _clean,
    engine,
    rpc_write_calls,
)
from tests.test_nf_bot_lockout_sim import BOT
from tests.test_nf_bot_operator_flow import LEAD, PART, design, item
from tests.test_nf_bot_walker import Odoo, Store

pytestmark = pytest.mark.no_app_db
VS = (17, 20)
BOT_LOGIN, OTHER = "bot-1", "alice"
SID = "s" * 24


class Rpc:
    """Odoo stand-in plus the two reads the spine adds (installed modules, bot login)."""

    def __init__(self, o: Odoo, mods: list[str], bot_login: str = BOT_LOGIN) -> None:
        self.o, self.mods, self.bot_login, self.fail_mods = o, mods, bot_login, False

    def __call__(self, model: str, method: str, args: Any = (), kw: dict | None = None) -> Any:
        kw = kw or {}
        if model == "ir.module.module" and method == "search_read":
            if self.fail_mods:
                raise RuntimeError("no access")
            return [{"name": m} for m in self.mods]
        if model == "res.users" and method == "search_read" and kw.get("fields") == ["login"]:
            uid = args[0][0][2]
            return [{"login": self.bot_login}] if uid == BOT else []
        return self.o(model, method, list(args), kw)


class Proofs:
    rehearsal_id = "rh-1"

    def __init__(self) -> None:
        self.ok, self.snap = True, True

    def rehearsal_passed(self, rid: str) -> bool:
        return self.ok and rid == self.rehearsal_id

    def snapshot_verified(self, db: str, model: str, ids: Any) -> bool:
        return self.snap


@pytest.fixture
def S(engine, tmp_path, monkeypatch):  # noqa: F811, N802
    _clean(engine)
    with engine.begin() as c:
        c.execute(text("DELETE FROM bot_approval"))
    monkeypatch.setattr(tg, "_STORE", Store())
    auth = sp.SessionAuthority()
    owner_of = lambda scope: OWNER  # noqa: E731
    reviewed = sp.ReviewedStore(tmp_path / "reviewed.json", auth, owner_of)
    proofs = Proofs()

    def make(v: int, spec: dict, *, rpc: Rpc | None = None, bot=None, wd: str = "w"):
        o = Odoo(v)
        r = rpc or Rpc(o, sorted(vc.load(v).modules))
        wiring = sp.Wiring(
            engine,
            AuditLog(engine, anchor=ANCHOR),
            owner_of,
            REH,
            proofs,
            auth,
            reviewed,
            tmp_path / wd,
        )
        b = bot or auth.issue_bot(login=BOT_LOGIN, session_id=SID, odoo_uid=BOT)
        flow = sp.SpineFlow(
            spec, r, wiring, b, connection_id="conn-a", db=FP, version=v, plan_id="p1"
        )
        return flow, (r.o if isinstance(r, Rpc) else o)

    make.auth, make.proofs, make.reviewed, make.engine = auth, proofs, reviewed, engine
    return make


def owner(S):  # noqa: N803
    return S.auth.issue_human(login=OWNER, session_id=SID)


def leads(o: Odoo) -> int:
    return sum(r.get("name") == "Guided one" for r in o.rows.get("crm.lead", {}).values())


# ------------------------------------------------------------------ happy path
@pytest.mark.parametrize("v", VS)
def test_runs_only_after_signed_in_owner_approves_and_only_once(v, S) -> None:
    flow, o = S(v, design(v, item(*LEAD), item(*PART)))
    assert flow.run()["counts"][fl.PENDING] == 2 and leads(o) == 0
    for c in flow.cards():
        flow.dec.approve("p1", c, owner(S))
    rep = flow.run()
    st = rep["steps"]
    assert [s["status"] for s in st] == [fl.EXECUTED, fl.EXECUTED], st
    assert st[0]["by"] == OWNER and leads(o) == 1
    assert flow.run()["steps"][0].get("resumed") and leads(o) == 1
    with S.engine.connect() as c:
        rows = c.execute(text("SELECT status, decided_by, requested_by FROM bot_approval")).all()
    assert rows and all(r[1] in (OWNER, None) and r[2] == BOT_LOGIN for r in rows)
    assert all(g["allowed"] for g in flow.grades.values())


def test_caller_level_is_ignored_store_decides(S) -> None:
    flow, _ = S(17, design(17, item(*PART)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S), level=1)
    rec = flow.dec.get("p1", c)
    assert rec["level"] >= c.tier and rec["actor"] == OWNER


# ------------------------------------------------------------------ sessions
def test_forged_and_wrong_kind_sessions_refused(S) -> None:
    flow, _ = S(17, design(17, item(*PART)))
    (c,) = flow.cards()
    forged = sp.Session("human", OWNER, SID, None, "0" * 64)
    other = sp.SessionAuthority().issue_human(login=OWNER, session_id=SID)
    bot = S.auth.issue_bot(login=BOT_LOGIN, session_id=SID, odoo_uid=BOT)
    for actor in (OWNER, {"login": OWNER}, forged, other, bot, None):
        with pytest.raises(sp.SpineError) as e:
            flow.dec.approve("p1", c, actor, 3)
        assert e.value.code == "unauthenticated"
        with pytest.raises(sp.SpineError):
            flow.dec.skip("p1", c, actor)
    assert flow.run()["steps"][0]["status"] == fl.PENDING
    tampered = dataclasses.replace(owner(S), login="owner-2")
    with pytest.raises(sp.SpineError):
        flow.dec.approve("p1", c, tampered)


@pytest.mark.parametrize(
    ("kind", "login", "sid"),
    [("human", "bot-x", SID), ("human", "", SID), ("human", OWNER, "short"), ("bot", OWNER, SID)],
)
def test_issue_refuses_bad_identities(kind, login, sid) -> None:
    a = sp.SessionAuthority()
    with pytest.raises(sp.SpineError):
        if kind == "human":
            a.issue_human(login=login, session_id=sid)
        else:
            a.issue_bot(login=login, session_id=sid, odoo_uid=BOT)


def test_bot_session_must_be_the_databases_bot_user(S) -> None:
    o = Odoo(17)
    mods = sorted(vc.load(17).modules)
    with pytest.raises(sp.SpineError) as e:
        S(17, design(17, item(*PART)), rpc=Rpc(o, mods, bot_login="someone"))
    assert e.value.code == "bot-identity"
    wrong = S.auth.issue_bot(login=BOT_LOGIN, session_id=SID, odoo_uid=BOT + 1)
    with pytest.raises(sp.SpineError):
        S(17, design(17, item(*PART)), bot=wrong)
    with pytest.raises(sp.SpineError):
        S(17, design(17, item(*PART)), bot=S.auth.issue_human(login=OWNER, session_id=SID))


def test_caps_ctx_read_from_db_and_fail_closed(S) -> None:
    o = Odoo(17)
    r = Rpc(o, sorted(vc.load(17).modules) + ["web_enterprise"])
    flow, _ = S(17, design(17, item(*PART)), rpc=r)
    assert flow.caps["edition"] == "enterprise" and flow.edition == "enterprise"
    assert flow.installed == flow.caps["installed"]
    r2 = Rpc(Odoo(17), [])
    r2.fail_mods = True
    with pytest.raises(sp.SpineError) as e:
        S(17, design(17, item(*PART)), rpc=r2)
    assert e.value.code == "caps-unreadable"
    with pytest.raises(sp.SpineError):
        S(17, design(17, item(*PART)), rpc=Rpc(Odoo(17), []))


# ------------------------------------------------------------------ bypass / stale / replay
def test_self_approval_refused(S) -> None:
    flow, _ = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    assert flow.run()["steps"][0]["status"] == fl.EXECUTED
    req = flow.request_undo(owner(S))
    assert req["status"] == "requested"
    with pytest.raises(sp.SpineError) as e:
        flow.approve_undo(req, owner(S))  # same person asked and approves
    assert e.value.code == "forbidden"


def test_undo_requested_by_one_person_approved_by_owner(S, monkeypatch) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.run()
    assert leads(o) == 1
    req = flow.request_undo(S.auth.issue_human(login=OTHER, session_id=SID))
    assert req["status"] == "requested", req
    done = flow.approve_undo(req, owner(S))
    assert done and done[-1].status == "done" and leads(o) == 0


def test_undo_without_backup_proof_is_refused(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.run()
    S.proofs.snap = False  # undo of a create is an unlink: needs a checked backup
    req = flow.request_undo(S.auth.issue_human(login=OTHER, session_id=SID))
    assert all(r["status"] == "refused" for r in req["rows"])
    with pytest.raises(sp.SpineError):
        flow.approve_undo(req, owner(S))
    assert leads(o) == 1


def test_bypassing_decisions_hits_the_gate_refusal(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    forged = dataclasses.replace(flow.base, approval=gd.Approval(3, OWNER))
    done = flow.w.apply(c.walk, forged)  # straight to the walker, no store row
    assert done[-1].status == "refused" and leads(o) == 0


def test_tampered_decision_file_gives_nothing_to_run(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    path = Path(flow.dec.path)
    d = json.loads(path.read_text()) if path.exists() else {}
    d.setdefault("p1", {})[c.slot] = {
        "decision": "approve",
        "actor": OWNER,
        "level": 3,
        "hash": c.digest,
        "plans": [p.hash() for p in flow.plans_for(c)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d))
    st = flow.run()["steps"][0]
    assert st["status"] == fl.BLOCKED and leads(o) == 0, st


def test_stale_facts_after_approval_block_the_run(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    S.proofs.ok = False  # the practice run is no longer valid
    st = flow.run()["steps"][0]
    assert st["status"] == fl.BLOCKED and leads(o) == 0, st


def test_changed_card_after_approval_blocks(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.spec = design(17, item("crm.lead", {"name": "Guided one"}, {"priority": "1"}))
    st = flow.run()["steps"][0]
    assert st["status"] == fl.BLOCKED and leads(o) == 0


def test_replayed_grant_is_refused(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    assert flow.run()["steps"][0]["status"] == fl.EXECUTED
    p = c.walk.steps[0]
    a = flow.dec.approval_for("p1", c)
    s = dataclasses.replace(
        flow.base, task_id=p.task_id, risk_class=p.cls, idempotency_key="replay", approval=a
    )
    # the plan's job is done: the gate resumes it and writes nothing; the grant stays spent
    assert flow.w.gate.call(s, p.step.model, "create", [dict(p.step.values)]) is None
    assert leads(o) == 1
    with S.engine.connect() as cx:
        assert (
            cx.execute(text("SELECT count(*) FROM bot_grant WHERE used_at IS NULL")).scalar() == 0
        )


def test_rejected_or_pending_store_rows_never_run(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    rows = [flow.store.submit(p) for p in flow.plans_for(c)]
    for r in rows:
        if r["status"] == "pending":
            flow.store.reject("conn-a", r["id"], OWNER)
    with pytest.raises(sp.SpineError):
        flow.dec.approve("p1", c, owner(S))
    assert flow.run()["steps"][0]["status"] != fl.EXECUTED and leads(o) == 0


# ------------------------------------------------------------------ tiers grading
def test_every_card_graded_and_refusals_explained(S, monkeypatch) -> None:
    real = tr.assess

    def deny(task_id, **kw):
        a = real(task_id, **kw)
        return dataclasses.replace(a, grade=tr.NOT_BUILT_YET, reason="Not built yet for this.")

    monkeypatch.setattr(tr, "assess", deny)
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    assert c.blocked and "Not built yet" in c.blocked
    g = flow.grades[c.slot]
    assert not g["allowed"] and g["parts"] and g["message"]
    with pytest.raises(sp.SpineError):
        flow.dec.approve("p1", c, owner(S))
    st = flow.run()["steps"][0]
    assert st["status"] == fl.BLOCKED and "Not built yet" in st["reason"] and leads(o) == 0


# ------------------------------------------------------------------ reviewed from the owner store
def test_reviewed_comes_only_from_owner_store(S) -> None:
    with pytest.raises(sp.SpineError):
        S.reviewed.mark(S.auth.issue_human(login=OTHER, session_id=SID), FP, "x_probe", "ok")
    with pytest.raises(sp.SpineError):
        S.reviewed.mark(owner(S), FP, "res.partner", "ok")
    with pytest.raises(sp.SpineError):
        S.reviewed.mark({"login": OWNER}, FP, "x_probe", "ok")
    flow, _ = S(17, design(17, item(*PART)))
    assert flow.w.reviewed == {}
    S.reviewed.mark(owner(S), FP, "x_probe", "checked fields")
    flow2, _ = S(17, design(17, item(*PART)), wd="w2")
    assert flow2.w.reviewed == {"x_probe": "checked fields"}
    assert "reviewed" not in sp.SpineFlow.__init__.__code__.co_varnames[:10]


def test_documents_use_database_caps(S) -> None:
    flow, _ = S(17, design(17, item(*PART)))
    doc = flow.handoff(flow.run(), {"status": "ok", "items": []})
    assert isinstance(doc, dict) and doc


# ------------------------------------------------------------------ T3 approval items
MOD, OLD, NEW = "x_spine_mod", b"a = 1\n", b"a = 2\n"
KEY = "k" * 40


def report(mh: str, version: int = 17, module: str = MOD, prior_hash: str | None = None) -> dict:
    up = mtg.PASS if prior_hash else mtg.NA
    body = {
        "schema": mtg.SCHEMA,
        "module": module,
        "module_hash": mh,
        "version": version,
        "prior_hash": prior_hash,
        "checks": {c: {"status": up if c == "upgrade" else mtg.PASS} for c in mtg.CHECKS},
        "verdict": mtg.PASS,
    }
    return body | {"signature": mtg._sign(body)}


def change_set(reason: str = "fix") -> oc.ChangeSet:
    p = "models/m.py"
    return oc.ChangeSet(
        MOD,
        17,
        reason,
        {p: oc.sha(OLD)},
        {p: oc.sha(NEW)},
        {p: oc.make_patch(p, OLD, NEW)},
        {p: oc.make_patch(p, NEW, OLD)},
        {},
        {},
    )


class Result:
    def __init__(self, mh: str, cs_ids: list[str], promotable: bool = True) -> None:
        self.mh, self.ids, self.promotable = mh, cs_ids, promotable

    def approval_plan(self) -> dict:
        return {
            "kind": "module_authoring",
            "module": MOD,
            "version": 17,
            "module_hash": self.mh,
            "promotable": self.promotable,
            "change_set_ids": self.ids,
        }


@pytest.fixture
def T3(S, monkeypatch):  # noqa: N802
    monkeypatch.setenv(mtg.KEY_ENV, KEY)
    flow, _ = S(17, design(17, item(*PART)))
    cs = change_set()
    mh = mtg.module_hash({"models/m.py": NEW})  # the gated module is what gets written
    plan = sp.authoring_plan(
        Result(mh, [cs.id]),
        report(mh),
        connection_id="conn-a",
        db=FP,
        requested_by=BOT_LOGIN,
        snapshot_verified=True,
    )
    return flow.store, plan, cs, mh


def _apply(store, plan, cs, mh, **kw):
    args = dict(gate_report=report(mh), module_hash=mh, change_set=cs, approved_id=cs.id)
    return sp.apply_t3(store, plan, files={"models/m.py": OLD}, **(args | kw))


def test_t3_item_is_l3_pending_and_never_applies_with_switch_off(T3) -> None:
    store, plan, cs, mh = T3
    row = store.submit(plan)
    assert row["tier"] == 3 and row["status"] == "pending"
    with pytest.raises(sp.SpineError) as e:
        _apply(store, plan, cs, mh)
    assert e.value.code == "not-approved"
    store.approve("conn-a", row["id"], OWNER)
    with pytest.raises(sp.SpineError) as e:
        _apply(store, plan, cs, mh)
    assert e.value.code == "t3-off" and not tr.tier_ready(tr.T3)
    assert tr.MODULE_AUTHORING_REVIEWED is False
    assert tr._CAPABILITIES["module-authoring"] is False


def test_t3_apply_checks_gate_and_change_set_binding(T3, monkeypatch) -> None:
    store, plan, cs, mh = T3
    store.approve("conn-a", store.submit(plan)["id"], OWNER)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)  # test-only: the real switch stays off
    out = _apply(store, plan, cs, mh)
    assert out["models/m.py"] == NEW
    bad = [
        ({"gate_report": report(mh, version=19)}, "gate"),
        ({"gate_report": report(mh, module="x_other")}, "gate"),
        ({"gate_report": report(mh) | {"verdict": "fail"}}, "gate"),
        ({"module_hash": "0" * 64}, "gate"),
        ({"change_set": change_set("edited")}, "not-approved"),
        ({"approved_id": "f" * 64}, "not-approved"),
    ]
    for kw, code in bad:
        with pytest.raises(sp.SpineError) as e:
            _apply(store, plan, cs, mh, **kw)
        assert e.value.code == code, kw


def test_t3_without_passing_gate_is_refused_at_submit(S, monkeypatch) -> None:
    monkeypatch.setenv(mtg.KEY_ENV, KEY)
    flow, _ = S(17, design(17, item(*PART)))
    mh = "a" * 64
    p = sp.authoring_plan(
        Result(mh, []),
        report(mh, version=19),
        connection_id="conn-a",
        db=FP,
        requested_by=BOT_LOGIN,
        snapshot_verified=True,
    )
    assert flow.store.submit(p)["status"] == "refused"
    with pytest.raises(sp.SpineError):
        sp.authoring_plan(
            Result(mh, [], promotable=False),
            report(mh),
            connection_id="conn-a",
            db=FP,
            requested_by=BOT_LOGIN,
            snapshot_verified=True,
        )


PRIOR = mtg.module_hash({"models/m.py": OLD})


def _cs_plan(cs, mh, rep=None, prior=PRIOR):
    return sp.change_set_plan(
        cs,
        rep if rep is not None else report(mh, prior_hash=prior),
        mh,
        prior_hash=prior,
        connection_id="conn-a",
        db=FP,
        requested_by=BOT_LOGIN,
        snapshot_verified=True,
    )


def test_owned_change_item_bound_to_change_set(T3, monkeypatch) -> None:
    store, _plan, cs, mh = T3
    p = _cs_plan(cs, mh)
    assert p.values["prior_hash"] == PRIOR
    row = store.submit(p)
    assert row["tier"] == 3
    with pytest.raises(ap.ApprovalError):
        store.approve("conn-a", row["id"], BOT_LOGIN)
    store.approve("conn-a", row["id"], OWNER)
    up = report(mh, prior_hash=PRIOR)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)
    assert _apply(store, p, cs, mh, gate_report=up)["models/m.py"] == NEW
    other = change_set("other")
    bad = [
        ({"change_set": other, "approved_id": other.id}, "not-approved"),
        ({"gate_report": report(mh)}, "gate"),  # fresh-install report used for an upgrade
        ({"gate_report": report(mh, prior_hash="e" * 64)}, "gate"),  # other prior version
    ]
    for kw, code in bad:
        with pytest.raises(sp.SpineError) as e:
            _apply(store, p, cs, mh, **({"gate_report": up} | kw))
        assert e.value.code == code, kw
    with pytest.raises(sp.SpineError) as e:  # installed files drifted from the gated prior
        sp.apply_t3(
            store,
            p,
            files={"models/m.py": OLD + b"#x"},
            gate_report=up,
            module_hash=mh,
            change_set=cs,
            approved_id=cs.id,
        )
    assert e.value.code == "gate"


def test_upgrade_plan_needs_prior_hash_and_bound_report(T3) -> None:
    store, _plan, cs, mh = T3
    with pytest.raises(sp.SpineError):
        _cs_plan(cs, mh, prior=None)
    assert store.submit(_cs_plan(cs, mh, rep=report(mh)))["status"] == "refused"


def test_t3_result_must_hash_to_gated_module(T3, monkeypatch) -> None:
    store, _plan, cs, _mh = T3
    wrong = mtg.module_hash({"models/m.py": OLD})  # gate ran on the pre-patch code
    p = sp.authoring_plan(
        Result(wrong, [cs.id]),
        report(wrong),
        connection_id="conn-a",
        db=FP,
        requested_by=BOT_LOGIN,
        snapshot_verified=True,
    )
    store.approve("conn-a", store.submit(p)["id"], OWNER)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)
    with pytest.raises(sp.SpineError) as e:
        _apply(store, p, cs, wrong)
    assert e.value.code == "gate"


def test_t3_apply_refused_when_kill_switch_on(T3, monkeypatch) -> None:
    store, plan, cs, mh = T3
    store.approve("conn-a", store.submit(plan)["id"], OWNER)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)
    monkeypatch.setattr(store.switch, "check", lambda db: gd.refusal_kill(db))
    with pytest.raises(sp.SpineError) as e:
        _apply(store, plan, cs, mh)
    assert e.value.code == "killed"


def test_t3_apply_refuses_non_plan_and_lower_tier(T3, monkeypatch) -> None:
    store, plan, cs, mh = T3
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)

    for p in (
        plan.__dict__,
        dataclasses.replace(plan, min_tier=2),
        dataclasses.replace(plan, risk_class="R1"),
    ):
        with pytest.raises(sp.SpineError) as e:
            sp.apply_t3(
                store,
                p,
                files={"models/m.py": OLD},
                gate_report=report(mh),
                module_hash=mh,
                change_set=cs,
                approved_id=cs.id,
            )
        assert e.value.code == "refused"


# ------------------------------------------------------------------ no side doors
def test_spine_has_no_raw_write_path() -> None:
    src = Path(sp.__file__).read_text()
    assert rpc_write_calls(src) == [] and "execute_kw" not in src
    assert ".rpc(" not in src and "gate.run" not in src and "gate.call" not in src
    assert "tier_ready(" in src and "_CAPABILITIES[" not in src and "REQUIRED[" not in src


# ------------------------------------------------------------------ review: undo approval
def test_undo_plans_never_auto(S) -> None:
    flow, _ = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.run()
    req = flow.request_undo(S.auth.issue_human(login=OTHER, session_id=SID))
    assert req["plans"] and all(p.min_tier >= sp.UNDO_MIN_TIER for p in req["plans"])
    assert all(r["status"] != "auto" for r in req["rows"])


def test_undo_self_approval_refused_whatever_status(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.run()
    req = flow.request_undo(owner(S))
    forged = {**req, "rows": [{**r, "status": "auto"} for r in req["rows"]]}
    for r in (req, forged):
        with pytest.raises(sp.SpineError) as e:
            flow.approve_undo(r, owner(S))
        assert e.value.code == "forbidden"
    assert leads(o) == 1


def test_undo_auto_row_refused(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    flow.run()
    req = flow.request_undo(S.auth.issue_human(login=OTHER, session_id=SID))
    forged = {**req, "rows": [{**r, "status": "auto"} for r in req["rows"]]}
    with pytest.raises(sp.SpineError):
        flow.approve_undo(forged, owner(S))
    assert leads(o) == 1


# ------------------------------------------------------------------ review: sealed decisions
@pytest.mark.parametrize(
    "edit",
    [
        {"actor": OTHER},
        {"session": "deadbeef"},
        {"actor": OTHER, "session": "deadbeef"},
        {"level": 9},
        {"seal": "0" * 64},
        {"seal": None},
    ],
)
def test_edited_saved_decision_gives_nothing_to_run(S, edit) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    path = Path(flow.dec.path)
    d = json.loads(path.read_text())
    d["p1"][c.slot].update(edit)
    path.write_text(json.dumps(d))
    st = flow.run()["steps"][0]
    assert st["status"] == fl.BLOCKED and leads(o) == 0, st


def test_sealed_decision_still_runs(S) -> None:
    flow, o = S(17, design(17, item(*LEAD)))
    (c,) = flow.cards()
    flow.dec.approve("p1", c, owner(S))
    assert json.loads(Path(flow.dec.path).read_text())["p1"][c.slot]["seal"]
    assert flow.run()["steps"][0]["status"] == fl.EXECUTED and leads(o) == 1


# ------------------------------------------------------------------ review 4: approved file list
@pytest.mark.parametrize("files", [[], ["models/other.py"], ["models/m.py", "models/x.py"]])
def test_upgrade_file_list_must_match_change_set(T3, monkeypatch, files) -> None:
    store, _plan, cs, mh = T3
    p = dataclasses.replace(_cs_plan(cs, mh), values={**_cs_plan(cs, mh).values, "files": files})
    store.approve("conn-a", store.submit(p)["id"], OWNER)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)
    with pytest.raises(sp.SpineError) as e:
        _apply(store, p, cs, mh, gate_report=report(mh, prior_hash=PRIOR))
    assert e.value.code == "not-approved" and "files" in str(e.value.message)


# ------------------------------------------------------------------ review 3: kill recheck
def test_kill_thrown_after_apply_stops_install(T3, monkeypatch) -> None:
    store, plan, cs, mh = T3
    store.approve("conn-a", store.submit(plan)["id"], OWNER)
    monkeypatch.setattr(sp, "_t3_ready", lambda: True)
    assert _apply(store, plan, cs, mh)
    sp.t3_before_install(store, plan)  # nothing thrown yet
    monkeypatch.setattr(store.switch, "check", lambda db: gd.refusal_kill(db))
    with pytest.raises(sp.SpineError) as e:
        sp.t3_before_install(store, plan)
    assert e.value.code == "killed"


def test_before_install_refuses_with_switch_off(T3) -> None:
    store, plan, _cs, _mh = T3
    with pytest.raises(sp.SpineError) as e:
        sp.t3_before_install(store, plan)
    assert e.value.code == "t3-off"


def test_install_call_requires_kill_recheck() -> None:
    """Guard for when install is wired: every install call in spine follows t3_before_install."""
    import inspect
    import re

    src = inspect.getsource(sp)
    calls = [
        m.start()
        for m in re.finditer(r"button_immediate_install|button_install|\.install\(|-i ", src)
    ]
    for pos in calls:
        assert "t3_before_install(store" in src[max(0, pos - 2000) : pos], src[pos - 80 : pos + 40]
