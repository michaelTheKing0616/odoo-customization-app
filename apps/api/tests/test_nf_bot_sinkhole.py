"""BOT-SINKHOLE: outbound side effects of a bot write are held, proved, or refused."""

from __future__ import annotations

import ast
import copy
import csv
import json
from pathlib import Path
from typing import Any

import pytest

from app.bots import guard as gd
from app.bots import sinkhole as sk
from app.bots.clone import neutralize as nz
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    FP,
    OWNER,
    REH,
    Undo,
    _clean,
    engine,
    env,
    fake_owner,
    spec,
)

pytestmark = pytest.mark.no_app_db
SRC = Path(__file__).resolve().parents[1] / "app" / "bots" / "sinkhole.py"
INVENTORY = Path.home() / ".ingenium_nf/taxonomy/fields_inventory.csv"
UID = 7
DB = FP
ME = sk.SessionActor(OWNER, "sess-0123456789")


class Switch:
    def __init__(self) -> None:
        self.on: str | None = None

    def check(self, db):
        return gd.refusal_kill(db) if self.on else None

    def turn_on(self, scope, actor, reason):
        self.on = reason

    def owner_of(self, scope):
        return OWNER


def _match(rec: dict, dom: list) -> bool:
    for f, op, v in dom:
        x = rec.get(f)
        ops = {
            "=": x == v,
            "!=": x != v,
            "in": op.endswith("in") and x in v,
            ">": op == ">" and x is not None and x > v,
        }
        ok = (not ops["in"]) if op == "not in" else ops[op]
        if not ok:
            return False
    return True


class Odoo:
    """Tiny Odoo stand-in: automation side effects follow Odoo's context flags."""

    def __init__(self) -> None:
        self.installed = {
            "base.automation",
            "mail.mail",
            "sms.sms",
            "mail.notification",
            "mail.followers",
            "ir.cron",
            "crm.lead",
            "res.users",
            "payment.provider",
            "account.payment",
            "ir.config_parameter",
        }
        self.db: dict[str, dict[int, dict]] = {m: {} for m in self.installed}
        self.db["ir.actions.server"] = {}
        self.db["mail.template"] = {}
        self.db["ir.model.data"] = {}
        self.db["ir.model"] = {}
        self.seq = 100
        self.demoted = False
        self.fail: set[str] = set()
        self.sent: list[int] = []
        self.webhooks: list[str] = []
        for xid, active in [
            ("mail.ir_cron_mail_scheduler_action", True),
            ("sms.ir_cron_sms_scheduler_action", True),
        ]:
            cid = self.add("ir.cron", active=active)
            mod, name = xid.split(".", 1)
            self.add("ir.model.data", module=mod, name=name, model="ir.cron", res_id=cid)
        self.lead = self.add("crm.lead", name="L")

    def add(self, _m: str, /, **vals) -> int:
        self.seq += 1
        self.db.setdefault(_m, {})[self.seq] = {"id": self.seq, **vals}
        return self.seq

    def mail(self, state="outgoing", uid=UID, **kw) -> int:
        return self.add(
            "mail.mail",
            state=state,
            failure_reason=False,
            create_uid=uid,
            subject="s",
            attachment_ids=kw.pop("att", []),
            model="crm.lead",
            **kw,
        )

    def rule(self, state: str, trigger="on_create_or_write", model="crm.lead", **act) -> int:
        aid = self.add(
            "ir.actions.server",
            name=f"act-{state}",
            state=state,
            child_ids=[],
            crud_model_id=act.pop("crud", False),
            template_id=act.pop("tpl", False),
        )
        self.add(
            "base.automation",
            name=f"rule-{state}",
            trigger=trigger,
            action_server_ids=[aid],
            active=True,
            **{"model_id.model": model},
        )
        return aid

    def tick(self) -> None:
        """Queue cron: sends outgoing mail if the mail cron is active."""
        cron = next(
            r for r in self.db["ir.model.data"].values() if r["name"].startswith("ir_cron_mail")
        )
        if self.db["ir.cron"][cron["res_id"]]["active"]:
            for m in self.db["mail.mail"].values():
                if m["state"] == "outgoing":
                    m["state"] = "sent"
                    self.sent.append(m["id"])

    def _effects(self, model: str, op: str, ctx: dict) -> None:
        force = ctx.get("mail_notify_force_send") is not False
        for r in list(self.db["base.automation"].values()):
            if not r["active"] or r["model_id.model"] != model:
                continue
            if op not in sk.TRIGGERS[r["trigger"]][0]:
                continue
            for aid in r["action_server_ids"]:
                a = self.db["ir.actions.server"][aid]
                if a["state"] == "mail_post":
                    att = (
                        self.db["mail.template"]
                        .get((a["template_id"] or [0])[0], {})
                        .get("attachment_ids", [])
                    )
                    mid = self.mail(state="sent" if force else "outgoing", att=att)
                    if force:
                        self.sent.append(mid)
                elif a["state"] == "followers" and not ctx.get("mail_auto_subscribe_no_notify"):
                    self.mail()
                elif a["state"] in ("webhook", "code"):
                    self.webhooks.append(a["name"])

    def __call__(self, model, method, args, kw=None) -> Any:
        kw = dict(kw or {})
        ctx = kw.pop("context", {}) or {}
        if model in self.fail:
            raise RuntimeError("AccessError")
        if model == "ir.model" and method == "search_count":
            return int(args[0][0][2] in self.installed)
        if model == "ir.model" and method == "read":
            return [{"id": args[0][0], "model": self.db["ir.model"][args[0][0]]["model"]}]
        rows = self.db.setdefault(model, {})
        if method == "fields_get":
            keys = set().union(*[r.keys() for r in rows.values()]) if rows else set()
            return {
                k: {"type": "x"}
                for k in keys | {"name", "state", "child_ids", "crud_model_id", "template_id"}
            }
        if method in ("search", "search_read", "search_count"):
            hit = sorted((r for r in rows.values() if _match(r, args[0])), key=lambda r: r["id"])
            if kw.get("order") == "id desc":
                hit = hit[::-1]
            if kw.get("limit"):
                hit = hit[: kw["limit"]]
            if method == "search_count":
                return len(hit)
            if method == "search":
                return [r["id"] for r in hit]
            return [copy.deepcopy(r) for r in hit]
        if method == "read":
            return [copy.deepcopy(rows[i]) for i in args[0] if i in rows]
        if method == "write":
            if self.demoted and model in ("mail.mail", "sms.sms", "ir.cron"):
                raise RuntimeError("AccessError")
            for i in args[0]:
                rows[i].update(args[1])
            self._effects(model, "write", ctx)
            return True
        if method == "unlink":
            for i in args[0]:
                rows.pop(i)
            return True
        if method == "create":
            if model == "ir.config_parameter" and any(
                r["key"] == args[0]["key"] for r in rows.values()
            ):
                raise RuntimeError("duplicate key value violates unique constraint")
            if model == "res.users" and not ctx.get("no_reset_password"):
                self.sent.append(self.mail(state="sent"))  # signup invite, force_send=True
            self._effects(model, "create", ctx)
            return self.add(model, **args[0])
        raise AssertionError((model, method))


def mk(o: Odoo | None = None) -> tuple[Odoo, Switch, sk.Sinkhole]:
    o = o or Odoo()
    sw = Switch()
    return o, sw, sk.Sinkhole(o, sw, DB, UID)


def window(o, sw, h, model="crm.lead", values=None, level=1, op="write"):
    s = h.scan(model, op, values or {"name": "x"}, [o.lead])
    assert h.open(s, level) is None
    return s


# ---------- scan ----------
def test_scan_clean_model_says_nothing_sends() -> None:
    o, sw, h = mk()
    s = h.scan("crm.lead", "write", {"name": "x"}, [o.lead])
    assert s.verdict == "ok" and not s.channels and "should not send" in s.text()


def test_template_with_attachments_is_reported_and_held() -> None:
    o, sw, h = mk()
    t = o.add("mail.template", name="Quote", attachment_ids=[5])
    o.rule("mail_post", tpl=[t, "Quote"])
    s = window(o, sw, h)
    assert s.verdict == "ok" and "with attachments" in s.text()
    o(*["crm.lead", "write", [[o.lead], {"name": "y"}]], {"context": sk.QUIET_CTX})
    assert h.after_batch()
    rep = h.close()
    assert len(rep.held_mail) == 1 and rep.held_mail[0]["attachment_ids"] == [5]
    assert "1 with attachments" in rep.text() and not o.sent


@pytest.mark.parametrize("state", ["webhook", "code", "sms", "brand_new_kind"])
def test_unholdable_actions_need_l3(state) -> None:
    o, sw, h = mk()
    o.rule(state)
    s = h.scan("crm.lead", "write", {"name": "x"}, [o.lead])
    assert s.verdict == "l3" and s.need_tier == 3 and "highest approval" in s.text()
    assert h.open(s, 2).missing == "outbound-l3"
    assert h.open(s, 3) is None


def test_trigger_not_matching_op_is_ignored_and_unknown_trigger_is_l3() -> None:
    o, sw, h = mk()
    o.rule("webhook", trigger="on_unlink")
    o.rule("code", trigger="on_change")
    assert h.scan("crm.lead", "write", {}, [o.lead]).verdict == "ok"
    o.rule("mail_post", trigger="on_something_new")
    assert h.scan("crm.lead", "write", {}, [o.lead]).verdict == "l3"


def test_recursive_object_write_reaches_webhook() -> None:
    o, sw, h = mk()
    o.installed.add("res.partner")
    mid = o.add("ir.model", model="res.partner")
    o.db["ir.model"][mid] = {"id": mid, "model": "res.partner"}
    o.rule("object_write", crud=[mid, "Contact"])
    o.rule("webhook", model="res.partner")
    s = h.scan("crm.lead", "write", {}, [o.lead])
    assert s.verdict == "l3" and any("act-webhook" in c.detail for c in s.channels)


def test_unreadable_scan_refuses() -> None:
    o, sw, h = mk()
    o.fail.add("base.automation")
    s = h.scan("crm.lead", "write", {}, [o.lead])
    assert s.verdict == "refuse" and h.open(s, 3).missing == "outbound-scan"


def test_payment_provider_live_is_l3_disabled_is_ok() -> None:
    o, sw, h = mk()
    pid = o.add("payment.provider", state="enabled")
    assert h.scan("account.payment", "write", {"state": "posted"}, []).verdict == "l3"
    assert h.scan("account.payment", "write", {"memo": "x"}, []).verdict == "ok"
    o.db["payment.provider"][pid]["state"] = "disabled"
    assert h.scan("account.payment", "write", {"state": "posted"}, []).verdict == "ok"


# ---------- window ----------
def test_quiet_wrapper_adds_flags_keeps_plan_ctx_and_reads_untouched() -> None:
    seen = []
    q = sk.Sinkhole(None, Switch(), DB, UID).quiet(lambda *a: seen.append(a))
    q("crm.lead", "write", [[1], {}], {"context": {"lang": "fr_FR"}})
    q("crm.lead", "read", [[1]], None)
    assert seen[0][3]["context"] == {"lang": "fr_FR", **sk.QUIET_CTX}
    assert seen[1][3] is None


def test_followers_auto_subscribe_quiet_sends_nothing_raw_is_held() -> None:
    o, sw, h = mk()
    o.rule("followers")
    window(o, sw, h)
    q = h.quiet(o)
    q("crm.lead", "write", [[o.lead], {"user_id": 2}], None)
    assert h.after_batch() and not h.report.held_mail
    o("crm.lead", "write", [[o.lead], {"user_id": 3}], None)  # no flags: mail is created
    assert h.after_batch() and len(h.report.held_mail) == 1


def test_scheduled_action_mid_run_and_mail_queued_before_run() -> None:
    o, sw, h = mk()
    before = o.mail(uid=2)
    o.rule("mail_post")
    window(o, sw, h)
    h.quiet(o)("crm.lead", "write", [[o.lead], {"name": "y"}], None)
    o.tick()  # queue cron fires mid-run: it is paused
    assert not o.sent
    assert h.after_batch()
    rep = h.close()
    assert rep.crons_restored and len(rep.held_mail) == 1
    assert o.db["mail.mail"][before]["state"] == "outgoing"  # not ours: not held
    o.tick()
    assert o.sent == [before]  # the earlier mail sends; ours stays held


def test_partner_portal_invite_on_user_create() -> None:
    o, sw, h = mk()
    window(o, sw, h, model="res.users", op="create")
    h.quiet(o)("res.users", "create", [{"login": "p"}], None)
    assert h.after_batch() and not o.sent
    o("res.users", "create", [{"login": "q"}], None)  # unflagged: invite sent inline
    assert not h.after_batch() and h.report.escaped and sw.on


def test_force_send_escape_trips() -> None:
    o, sw, h = mk()
    o.rule("mail_post")
    window(o, sw, h)
    o("crm.lead", "write", [[o.lead], {"name": "y"}], None)
    assert not h.after_batch() and "already sent" in h.report.text() and sw.on


def test_notification_sent_counts_as_escaped() -> None:
    o, sw, h = mk()
    window(o, sw, h)
    o.add("mail.notification", notification_status="sent", **{"mail_message_id.create_uid": UID})
    assert not h.after_batch() and h.report.escaped[0].startswith("notification:")


def test_bot_demoted_mid_run_keeps_queue_paused() -> None:
    o, sw, h = mk()
    o.rule("mail_post")
    window(o, sw, h)
    h.quiet(o)("crm.lead", "write", [[o.lead], {"name": "y"}], None)
    o.demoted = True
    assert not h.after_batch() and h.report.unheld and sw.on
    rep = h.close()
    assert not rep.crons_restored and "still paused" in rep.text()
    o.tick()
    assert not o.sent


def test_pause_failure_refuses_before_any_write() -> None:
    o, sw, h = mk()
    o.demoted = True
    s = h.scan("crm.lead", "write", {}, [o.lead])
    assert h.open(s, 1).missing == "outbound-pause"


def test_held_mail_released_once_owner_only() -> None:
    o, sw, h = mk()
    o.rule("mail_post")
    window(o, sw, h)
    h.quiet(o)("crm.lead", "write", [[o.lead], {"name": "y"}], None)
    h.close()
    lg = h.ledger
    fresh = copy.deepcopy(lg)
    with pytest.raises(PermissionError):
        h.decide(lg, sk.SessionActor("someone-else", "sess-0123456789"), True)
    with pytest.raises(TypeError):
        h.decide(lg, OWNER, True)  # a bare string is not an authenticated identity
    sw.on = "x"
    with pytest.raises(PermissionError):
        h.decide(lg, ME, True)
    sw.on = None
    first = h.decide(lg, ME, True)
    assert len(first["done"]) == 1
    assert h.decide(lg, ME, True)["done"] == []  # same ledger: refused
    assert h.decide(fresh, ME, True)["done"] == []  # stale copy: Odoo marker gone
    o.tick()
    assert len(o.sent) == 1


def test_discard_keeps_record_marked_never_deletes() -> None:
    o, sw, h = mk()
    o.rule("mail_post")
    window(o, sw, h)
    h.quiet(o)("crm.lead", "write", [[o.lead], {"name": "y"}], None)
    h.close()
    mid = h.ledger.mail_ids[0]
    h.decide(h.ledger, ME, False)
    m = o.db["mail.mail"][mid]
    assert m["state"] == "cancel" and m["failure_reason"].startswith(sk.DISCARD_PREFIX)


def test_after_batch_without_open_fails_closed() -> None:
    o, sw, h = mk()
    assert h.after_batch() is False


# ---------- through the real WriteGate ----------
def test_gate_run_holds_and_trips_on_escape(env) -> None:  # noqa: F811
    _engine, sw, audit = env
    o = Odoo()
    o.rule("mail_post")
    h = sk.Sinkhole(o, sw, FP, UID)
    s = h.scan("crm.lead", "write", {"name": "y"}, [o.lead])
    assert h.open(s, 1) is None
    gate = gd.WriteGate(sw, audit, h.quiet(o), REH)
    kw = dict(before_image=lambda c: ("bi", list(c)), undo=Undo())
    rep = gate.run(
        spec(), "crm.lead", [o.lead], {"name": "y"}, readback=h.readback(lambda c: True), **kw
    )
    assert rep.status == "done" and len(h.close().held_mail) == 1 and not o.sent
    h2 = sk.Sinkhole(o, sw, FP, UID)
    assert h2.open(h2.scan("crm.lead", "write", {}, [o.lead]), 1) is None
    raw = gd.WriteGate(sw, audit, o, REH)  # not wrapped: force-send escapes
    rep = raw.run(
        spec(), "crm.lead", [o.lead], {"name": "z"}, readback=h2.readback(lambda c: True), **kw
    )
    assert rep.status == "tripped" and sw.check(FP) is not None


# ---------- pins and drift ----------
def test_single_pinned_write_path() -> None:
    from tests.test_nf_bot_kill_audit import rpc_write_calls

    tree = ast.parse(SRC.read_text())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    owners = {n: rpc_write_calls(ast.unparse(f)) for n, f in fns.items()}
    owners = {n: v for n, v in owners.items() if v}
    assert set(owners) == {"_qwrite"} and len(owners["_qwrite"]) == 3  # create/write/unlink
    lits = {
        c.args[1].value
        for c in ast.walk(fns["_qwrite"])
        if isinstance(c, ast.Call) and len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
    }
    assert lits == {"create", "write", "unlink"}
    first = fns["_qwrite"].body[0]
    assert isinstance(first, ast.If) and "self._halted()" in ast.unparse(first.test)
    assert "release" in ast.unparse(first.test)
    callers = {
        n
        for n, f in fns.items()
        for c in ast.walk(f)
        if isinstance(c, ast.Attribute) and c.attr == "_qwrite" and n != "_qwrite"
    }
    assert callers == {"open", "_hold", "_restore", "decide", "_drop_lease", "_guard"}
    for name, (models, fields, meth, pins) in sk.PURPOSES.items():
        assert meth in ("write", "create", "unlink") and models, name
        if "ir.cron" in models:
            assert fields == {"active"} and set(pins) == {"active"}
        if meth != "write":
            assert models == ("ir.config_parameter",)
        assert "res.users" not in models and "ir.model.access" not in models
    for p in (SRC.parents[1]).rglob("*.py"):  # nothing outside sinkhole.py reaches _qwrite
        if p != SRC:
            assert "_qwrite" not in p.read_text(), p


def test_every_list_entry_has_a_reason() -> None:
    for d in (
        sk.QUIET_CTX_REASONS,
        sk.QUEUE_CRONS,
        sk.ACTION_KINDS,
        sk.TRIGGERS,
        sk.BUSINESS_OUTBOUND,
        sk.REVIEWED_OUTBOUND_MODELS,
    ):
        for k, v in d.items():
            why = v if isinstance(v, str) else v[-1]
            assert isinstance(why, str) and len(why) > 10, (k, v)
    for m, why in sk.REVIEWED_OUTBOUND_MODELS.items():  # deferred = not bot-created = L3
        if why.startswith("deferred:"):
            assert m in sk.DEFERRED_MODELS, m
    assert all(len(v) > 10 for v in sk.DEFERRED_MODELS.values())
    assert set(sk.PROVIDER_LABELS) == {p for p, _d, _w in sk.BUSINESS_OUTBOUND.values()}
    ruled = {r.model for r in nz.RULES}
    assert {p for p, _d, _w in sk.BUSINESS_OUTBOUND.values()} <= ruled  # same as neutralize


def test_outbound_inventory_drift() -> None:
    if not INVENTORY.exists():
        pytest.skip("fields_inventory.csv not on this machine")
    rel = {"mail.template", "sms.template", "mail.mail", "sms.sms"}
    scope, states = set(), {}
    with INVENTORY.open() as fh:
        for r in csv.DictReader(fh):
            if r["store"] == "True" and (r["relation"] in rel or "webhook" in r["field"]):
                scope.add(r["model"])
            if (r["model"], r["field"]) in {
                ("mail.mail", "failure_reason"),
                ("mail.mail", "state"),
            }:
                states.setdefault(r["version"], set()).add(r["field"])
    missing = sorted(scope - set(sk.REVIEWED_OUTBOUND_MODELS))
    assert not missing, missing
    assert all(states.get(v) == {"failure_reason", "state"} for v in ("17", "18", "19", "20"))


# ---------- review round 2 ----------
def test_overlapping_runs_second_window_refused_no_mail_escapes() -> None:
    o, sw, a = mk()
    b = sk.Sinkhole(o, sw, DB, UID)
    o.rule("mail_post")
    window(o, sw, a)
    ref = b.open(b.scan("crm.lead", "write", {}, [o.lead]), 1)
    assert ref.missing == "outbound-lease" and b.paused == []
    a.quiet(o)("crm.lead", "write", [[o.lead], {"name": "z"}], None)
    o.tick()
    assert not o.sent
    a.close()
    assert not o.db["ir.config_parameter"]  # lease dropped after restore
    assert b.open(b.scan("crm.lead", "write", {}, [o.lead]), 1) is None  # now free


def test_crash_mid_window_owner_recovery_restores_and_is_idempotent() -> None:
    o, sw, a = mk()
    o.rule("mail_post")
    window(o, sw, a)
    a.quiet(o)("crm.lead", "write", [[o.lead], {"name": "z"}], None)
    paused = list(a.ledger.paused)
    assert paused and a.paused == paused
    del a  # crash: process gone, nothing in memory
    lease = next(iter(o.db["ir.config_parameter"].values()))
    assert sorted(__import__("json").loads(lease["value"])["paused"]) == sorted(paused)
    _o, _sw, r = mk(o)
    r.switch = sw
    with pytest.raises(PermissionError):
        r.recover(sk.SessionActor("intruder", "sess-0123456789"))
    assert r.recover(ME)["status"].startswith("refused")  # heartbeat still fresh
    r.clock = lambda: __import__("time").time() + sk.LEASE_STALE_S + 1
    out = r.recover(ME)
    assert out["status"] == "recovered" and len(out["held_mail"]) == 1
    assert all(o.db["ir.cron"][c]["active"] for c in paused)
    assert r.recover(ME)["status"] == "nothing to recover"
    o.tick()
    assert not o.sent  # the crashed run's mail stayed held


def test_lease_create_refused_means_no_pause() -> None:
    o, sw, h = mk()
    o.fail.add("ir.config_parameter")
    assert h.open(h.scan("crm.lead", "write", {}, [o.lead]), 1).missing == "outbound-pause"
    assert all(c["active"] for c in o.db["ir.cron"].values())


@pytest.mark.parametrize("trig", sorted(sk.TIME_TRIGGERS))
def test_time_based_mail_rule_is_l3_not_held(trig) -> None:
    o, sw, h = mk()
    o.rule("mail_post", trigger=trig)
    s = h.scan("crm.lead", sk.TRIGGERS[trig][0][-1], {"name": "x"}, [o.lead])
    assert s.verdict == "l3" and "will be held" not in s.text()
    assert "scheduler" in s.text()


def test_deferred_models_are_l3() -> None:
    o, sw, h = mk()
    s = h.scan("calendar.event", "write", {"start": "x"}, [])
    assert s.verdict == "l3" and "will be held" not in s.text()


def test_qwrite_pinned_to_model_fields_values() -> None:
    o, sw, h = mk()
    for bad in [
        ("pause", "mail.mail", [1], {"active": False}),
        ("pause", "ir.cron", [1], {"active": True}),
        ("pause", "ir.cron", [1], {"active": False, "code": "x"}),
        ("hold", "res.partner", [1], {"state": "cancel"}),
        ("hold", "mail.mail", [1], {"body_html": "x"}),
        ("lease_drop", "ir.config_parameter", [99], None),
        ("anything", "ir.cron", [1], {}),
    ]:
        with pytest.raises(sk.SinkholeError):
            h._qwrite(*bad)


def test_discard_refused_while_switch_on_and_sms_discard_is_marked() -> None:
    o, sw, h = mk()
    window(o, sw, h)
    sid = o.add("sms.sms", state="outgoing", create_uid=UID)
    assert h.after_batch() and h.ledger.sms_ids == [sid]
    h.close()
    fresh = copy.deepcopy(h.ledger)
    sw.on = "x"
    with pytest.raises(PermissionError):
        h.decide(h.ledger, ME, False)
    sw.on = None
    assert h.decide(h.ledger, ME, False)["done"] == [f"sms:{sid}"]
    assert o.db["sms.sms"][sid]["state"] == sk.SMS_DISCARDED
    assert h.decide(fresh, ME, True)["done"] == []  # stale copy cannot release it


def test_session_actor_validated() -> None:
    for login, sess in [("", "sess-0123456789"), ("a", "short"), (None, "sess-0123456789")]:
        with pytest.raises(ValueError):
            sk.SessionActor(login, sess)


def test_report_lines_have_no_model_names() -> None:
    o, sw, h = mk()
    o.add("payment.provider", state="enabled")
    t = h.scan("account.payment", "write", {"state": "posted"}, []).text()
    assert "payment.provider" not in t and "payment provider" in t


def _lease_row(o):
    return next(iter(o.db["ir.config_parameter"].values()))


def test_recover_during_live_window_refused_and_queue_stays_paused() -> None:
    o, sw, a = mk()  # review probe test_probe_sink_lease, kept permanent
    o.rule("mail_post")
    window(o, sw, a)
    r = sk.Sinkhole(o, sw, DB, UID).recover(ME)
    assert r["status"].startswith("refused") and r["limit_s"] == sk.LEASE_STALE_S
    assert a.paused and not any(o.db["ir.cron"][c]["active"] for c in a.paused)
    a.quiet(o)("crm.lead", "write", [[o.lead], {"name": "z"}], None)
    o.tick()
    assert not o.sent and a.after_batch() and a.close().crons_restored


def test_heartbeat_refreshed_on_every_guarded_write_and_batch() -> None:
    o, sw, a = mk()
    window(o, sw, a)
    t = [1000.0]
    a.clock = lambda: t[0]
    for step in (1, 2):
        t[0] += step
        a.quiet(o)("crm.lead", "write", [[o.lead], {"name": "z"}], None)
        assert json.loads(_lease_row(o)["value"])["beat"] == t[0]
    t[0] += 5
    assert a.after_batch() and json.loads(_lease_row(o)["value"])["beat"] == t[0]


def test_live_run_whose_lease_was_taken_stops_and_trips() -> None:
    o, sw, a = mk()
    window(o, sw, a)
    row = _lease_row(o)
    row["value"] = json.dumps({**json.loads(row["value"]), "hold_id": "someone-else"})
    with pytest.raises(sk.SinkholeError):
        a.quiet(o)("crm.lead", "write", [[o.lead], {"name": "z"}], None)
    assert sw.on and "sinkhole lease lost" in a.report.unheld
    assert not a.after_batch()
    rep = a.close()
    assert not rep.crons_restored and _lease_row(o)["value"] == row["value"]
    assert not any(o.db["ir.cron"][c]["active"] for c in a.paused)


def test_lease_dropped_mid_run_close_unpauses_nothing() -> None:
    o, sw, a = mk()
    window(o, sw, a)
    o.db["ir.config_parameter"].clear()  # e.g. dropped by someone else mid-run
    rep = a.close()
    assert not rep.crons_restored and sw.on and "sinkhole lease lost" in rep.unheld
    assert a.paused and not any(o.db["ir.cron"][c]["active"] for c in a.paused)


def test_plans_touching_ingenium_keys_are_refused() -> None:
    o, sw, a = mk()
    window(o, sw, a)
    lid = next(iter(o.db["ir.config_parameter"]))
    h = sk.Sinkhole(o, sw, DB, UID)
    for op, vals, ids in (
        ("write", {"value": "{}"}, [lid]),
        ("unlink", {}, [lid]),
        ("create", {"key": "ingenium.anything", "value": "1"}, []),
    ):
        sc = h.scan("ir.config_parameter", op, vals, ids)
        assert sc.verdict == "refuse" and sc.refusal.missing == "outbound-own-key", op


def test_risk_rules_put_config_parameter_writes_at_l3() -> None:
    from app.bots.risk import classifier as rc
    from app.bots.risk import rules as rr

    for t in (
        f"param:{sk.LEASE_KEY}",
        "param:ingenium.other",
        "m:ir.config_parameter:write",
        "m:ir.config_parameter:delete",
    ):
        cls, sub = rc.task_floor(t)
        for route in ("A", "B"):  # a policy cannot lower it below the hard floor
            assert rr.required_tier(cls, sub, route, rr.Policy(tiers={cls: 1})) == 3, t
