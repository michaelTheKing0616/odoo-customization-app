"""Outbound sinkhole: a bot write on production must never send anything as a side effect.

1. ``Sinkhole.scan`` (live reads only) lists every outbound channel the plan could trigger:
   automation rules on the model (and on models their actions write, depth <= 3), the server
   actions they run, mail templates (with attachments), followers, and live payment / EDI /
   carrier providers when a posting field is touched. Each server-action kind is either
   holdable (its output is a queued ``mail.mail``), quiet, recursive, or L3 (webhook, code,
   SMS: leaves at write time, cannot be held with proof). Anything unreadable = refuse.
2. ``open`` refuses a refused scan or an L3 scan without an L3 approval, takes the per-DB
   lease (unique ``ir.config_parameter`` key ``LEASE_KEY``: one window per database; it
   records hold id, bot uid, baselines and the cron ids BEFORE they are paused), then pauses
   the queue crons (``QUEUE_CRONS``). ``recover`` (owner) restores a crashed window.
   Time-based rules and ``DEFERRED_MODELS`` send later as the system user: L3, never held.
    ``quiet(rpc)`` wraps the gate's
   rpc so every write/create/unlink carries ``QUIET_CTX`` (flags Odoo 17-20 honour).
3. ``after_batch`` (compose into WriteGate readback via ``readback``) holds every new
   ``mail.mail`` / ``sms.sms`` the bot user produced (state cancel/canceled; mail carries the
   hold marker in ``failure_reason``), reads the hold back, and proves nothing left: any
   bot-produced mail or SMS already sent / failed / notified-sent = escaped -> kill switch on,
   readback False (the gate trips and undoes).
4. ``close`` restores the crons only when every bot-produced message is held (else the queue
   stays paused and the run needs a person). Held messages wait for ``release`` or
   ``discard`` by the DB owner; nothing is ever deleted. Release is one-shot.
All writes go through ``_qwrite``, pinned per purpose to model, fields and values (tests).
JSON-RPC callers only; no XML-RPC.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal

Rpc = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]
RULE = "RF-SINK"
MAX_DEPTH = 3
HOLD_PREFIX = "ingenium-hold:"
DISCARD_PREFIX = "ingenium-discarded:"
LEASE_KEY = "ingenium.sinkhole.lease"  # unique ir.config_parameter key = one window per DB
OWN_KEY_PREFIX = "ingenium."  # ingenium's own control keys: a bot plan touching one is refused
# A live run refreshes the lease heartbeat before every guarded write and after every batch, so
# the longest silent gap is ONE Odoo call (a batch is <= rules.BATCH_CAP=50 records in one
# write) plus its readback. Odoo's default limit_time_real kills a request at 120 s; 900 s is
# 7x that. recover() refuses a lease younger than this. There is NO owner force: forcing over
# a live run is exactly the failure this guards. To stop a run, turn the kill switch on (the
# run stops at its next write, the heartbeat stops) and recover after the limit.
LEASE_STALE_S = 900
SMS_DISCARDED = "error"  # Odoo-side discard marker for sms.sms (queue only sends outgoing)
log = logging.getLogger(__name__)

# context key -> (value, why Odoo 17-20 honours it)
QUIET_CTX_REASONS: dict[str, tuple[Any, str]] = {
    "tracking_disable": (True, "mail.thread skips tracking, stage templates and log notes"),
    "mail_notrack": (True, "mail.thread skips field tracking messages"),
    "mail_create_nolog": (True, "mail.thread skips the 'created' log note"),
    "mail_create_nosubscribe": (True, "creator is not auto-subscribed as follower"),
    "mail_auto_subscribe_no_notify": (True, "auto-subscribed users get no 'assigned' email"),
    "mail_notify_force_send": (False, "notifications queue in mail.mail, never sent inline"),
    "no_reset_password": (True, "auth_signup sends no invite/reset mail on res.users create"),
}
QUIET_CTX = {k: v for k, (v, _r) in QUIET_CTX_REASONS.items()}
# xmlid -> why it is paused for the write window (missing xmlid = module absent = n/a)
QUEUE_CRONS: dict[str, str] = {
    "mail.ir_cron_mail_scheduler_action": "sends queued mail.mail",
    "sms.ir_cron_sms_scheduler_action": "sends queued sms.sms",
    "base_automation.ir_cron_data_base_automation_check": "runs time-based automation rules",
    "mail.ir_cron_send_scheduled_message": "posts scheduled chatter messages (18+)",
}
# ir.actions.server state -> (kind, reason). Unknown state = l3.
ACTION_KINDS: dict[str, tuple[str, str]] = {
    "mail_post": ("hold", "email goes to the mail.mail queue, which is held"),
    "followers": ("hold", "follower notice goes to the mail.mail queue, which is held"),
    "remove_followers": ("quiet", "removes followers; sends nothing"),
    "log_note": ("quiet", "internal note (20); any email copy would be held mail.mail"),
    "next_activity": ("hold", "activity assignment email goes to mail.mail, held"),
    "object_write": ("recurse", "writes another model; its rules are scanned"),
    "object_create": ("recurse", "creates on another model; its rules are scanned"),
    "object_copy": ("recurse", "copies a record; target rules are scanned"),
    "multi": ("recurse", "runs child actions; each is scanned"),
    "sms": ("l3", "SMS can go straight to IAP; no held state can be proved"),
    "webhook": ("l3", "HTTP call leaves at write time; cannot be held"),
    "code": ("l3", "custom Python can call any outside service"),
}
# base.automation trigger -> (ops it fires on, reason). Unknown trigger = l3.
_W, _C, _U = "write", "create", "unlink"
TRIGGERS: dict[str, tuple[tuple[str, ...], str]] = {
    "on_create": ((_C,), "fires on create"),
    "on_write": ((_W,), "fires on write"),
    "on_create_or_write": ((_C, _W), "fires on create and write"),
    "on_unlink": ((_U,), "fires on delete"),
    "on_change": ((), "form onchange in the browser only; RPC writes do not run it"),
    "on_time": (
        (_C, _W),
        "date-based: sends later from the scheduler as the system user; never held",
    ),
    "on_time_created": (
        (_C,),
        "date-based on creation: sends later from the scheduler; never held",
    ),
    "on_time_updated": (
        (_C, _W),
        "date-based on update: sends later from the scheduler; never held",
    ),
    "on_stage_set": ((_C, _W), "fires when stage changes"),
    "on_state_set": ((_C, _W), "fires when state changes"),
    "on_tag_set": ((_C, _W), "fires when tags change"),
    "on_user_set": ((_C, _W), "fires when the user changes"),
    "on_priority_set": ((_C, _W), "fires when priority changes"),
    "on_archive": ((_W,), "fires on archive"),
    "on_unarchive": ((_W,), "fires on unarchive"),
    "on_message_received": ((), "inbound email only"),
    "on_message_sent": ((_C, _W), "fires when a message is posted on the record"),
    "on_webhook": ((), "inbound HTTP only"),
}
# plan model -> provider model whose live, production rows make a posting write call out
BUSINESS_OUTBOUND: dict[str, tuple[str, list, str]] = {
    "account.move": (
        "account_edi_proxy_client.user",
        [("edi_mode", "=", "prod")],
        "posting can send the e-invoice to the e-invoicing network",
    ),
    "payment.transaction": (
        "payment.provider",
        [("state", "=", "enabled")],
        "state changes can call the payment provider",
    ),
    "account.payment": (
        "payment.provider",
        [("state", "=", "enabled")],
        "posting can capture or refund through the payment provider",
    ),
    "stock.picking": (
        "delivery.carrier",
        [("prod_environment", "=", True)],
        "validating can book a real shipment with the carrier",
    ),
    "pos.order": (
        "pos.payment.method",
        [("use_payment_terminal", "!=", False)],
        "payment can reach a card terminal",
    ),
}
TIME_TRIGGERS = frozenset({"on_time", "on_time_created", "on_time_updated"})
PROVIDER_LABELS: dict[str, str] = {
    "account_edi_proxy_client.user": "e-invoicing connection(s)",
    "payment.provider": "payment provider(s)",
    "delivery.carrier": "shipping carrier(s) in production mode",
    "pos.payment.method": "card terminal(s)",
}
# plan model -> why its emails are sent later by Odoo itself (not bot-created): always L3
DEFERRED_MODELS: dict[str, str] = {
    "calendar.event": "reminder emails are sent later by Odoo's alarm scheduler, not held",
    "calendar.alarm": "reminder emails are sent later by Odoo's alarm scheduler, not held",
    "gamification.challenge": "challenge reports are sent later by Odoo's scheduler, not held",
    "gamification.goal": "goal reminders are sent later by Odoo's scheduler, not held",
}
# _qwrite purpose -> (models, allowed fields, method, pinned values)
PURPOSES: dict[str, tuple[tuple[str, ...], frozenset[str], str, dict[str, Any]]] = {
    "pause": (("ir.cron",), frozenset({"active"}), "write", {"active": False}),
    "restore": (("ir.cron",), frozenset({"active"}), "write", {"active": True}),
    "hold": (("mail.mail", "sms.sms"), frozenset({"state", "failure_reason"}), "write", {}),
    "release": (("mail.mail", "sms.sms"), frozenset({"state", "failure_reason"}), "write", {}),
    "discard": (("mail.mail", "sms.sms"), frozenset({"state", "failure_reason"}), "write", {}),
    "lease_take": (("ir.config_parameter",), frozenset({"key", "value"}), "create", {}),
    "lease_drop": (("ir.config_parameter",), frozenset(), "unlink", {}),
    "lease_beat": (("ir.config_parameter",), frozenset({"value"}), "write", {}),
}
_RA = {"context": {"active_test": False}}


@dataclass(frozen=True)
class Channel:
    kind: str  # hold | l3 | info
    source: str
    detail: str


@dataclass
class Scan:
    model: str
    op: str
    verdict: str = "ok"  # ok | l3 | refuse
    channels: list[Channel] = field(default_factory=list)
    followers: int = 0
    refusal: Refusal | None = None

    @property
    def need_tier(self) -> int:
        return 3 if self.verdict == "l3" else 0

    def facts(self) -> dict[str, Any]:
        return {
            "sinkhole": self.verdict,
            "outbound": sorted(f"{c.kind}:{c.source}" for c in self.channels),
        }

    def text(self) -> str:
        if self.refusal:
            return f"ingenium stopped: {self.refusal.reason}."
        hold = [c for c in self.channels if c.kind == "hold"]
        l3 = [c for c in self.channels if c.kind == "l3"]
        out = []
        if not hold and not l3:
            out.append("this change should not send anything outside Odoo.")
        if hold:
            out.append(
                f"{len(hold)} rule(s) could send email: "
                + "; ".join(c.detail for c in hold)
                + ". any email will be held, not sent, until you release it."
            )
        if self.followers:
            out.append(f"{self.followers} follower(s) are not emailed during this change.")
        if l3:
            out.append(
                "cannot be held, needs the highest approval: "
                + "; ".join(c.detail for c in l3)
                + "."
            )
        return " ".join(out)


@dataclass
class Ledger:
    hold_id: str
    db: str
    mail_ids: list[int] = field(default_factory=list)
    sms_ids: list[int] = field(default_factory=list)
    done: dict[str, str] = field(default_factory=dict)  # "mail:1" -> released|discarded
    paused: list[int] = field(default_factory=list)  # also persisted in the Odoo lease


@dataclass(frozen=True)
class SessionActor:
    """An authenticated person: the caller passes the session's login and session id."""

    login: str
    session_id: str

    def __post_init__(self) -> None:
        ok = isinstance(self.login, str) and self.login.strip()
        ok = ok and isinstance(self.session_id, str) and len(self.session_id.strip()) >= 8
        if not ok:
            raise ValueError("actor must be an authenticated session identity")


@dataclass
class Report:
    held_mail: list[dict] = field(default_factory=list)
    held_sms: list[dict] = field(default_factory=list)
    escaped: list[str] = field(default_factory=list)
    unheld: list[str] = field(default_factory=list)
    others_queued: int = 0
    crons_restored: bool = False

    @property
    def clean(self) -> bool:
        return not self.escaped and not self.unheld

    def text(self) -> str:
        out = []
        if self.held_mail or self.held_sms:
            att = sum(1 for m in self.held_mail if m.get("attachment_ids"))
            out.append(
                f"held {len(self.held_mail)} email(s)"
                + (f" ({att} with attachments)" if att else "")
                + f" and {len(self.held_sms)} text message(s); nothing was sent."
                " release or discard them from the approval card."
            )
        else:
            out.append("nothing was queued to send.")
        if self.escaped:
            out.append(f"already sent, cannot be recalled: {len(self.escaped)}. bots stopped.")
        if self.unheld:
            out.append(
                f"{len(self.unheld)} message(s) could not be held; the outgoing queue is"
                " still paused and needs a person."
            )
        if self.others_queued:
            out.append(
                f"{self.others_queued} message(s) from other users waited for the queue and"
                " will send normally."
            )
        return " ".join(out)


class SinkholeError(RuntimeError):
    pass


def _has(rpc: Rpc, model: str) -> bool:
    return bool(rpc("ir.model", "search_count", [[("model", "=", model)]], None))


class Sinkhole:
    def __init__(self, rpc: Rpc, switch: Any, db: str, bot_uid: int) -> None:
        self.rpc, self.switch, self.db, self.uid = rpc, switch, db, int(bot_uid)
        self.ledger = Ledger(uuid.uuid4().hex, db)
        self.paused: list[int] = []
        self.base: dict[str, int] = {}
        self.report = Report()
        self._opened = False
        self._lease_id: int | None = None
        self._rec: dict[str, Any] = {}
        self._lost = False
        self.clock: Callable[[], float] = time.time

    # ---------- scan (reads only) ----------
    def scan(self, model: str, op: str, values: dict[str, Any], ids: Sequence[int]) -> Scan:
        s = Scan(model, op)
        try:
            if model == "ir.config_parameter" and self._own_keys(values, ids):
                s.verdict = "refuse"
                s.refusal = Refusal(RULE, "outbound-own-key", "a plan may not touch ingenium keys")
                return s
            self._scan_model(s, model, op, 0, set())
            self._business(s, model, values)
            if model in DEFERRED_MODELS:
                s.channels.append(Channel("l3", "deferred", DEFERRED_MODELS[model]))
            if model in rr.MAIL_THREAD and ids and op != _C:
                s.followers = int(
                    self.rpc(
                        "mail.followers",
                        "search_count",
                        [[("res_model", "=", model), ("res_id", "in", list(ids))]],
                        None,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - unreadable = refuse
            s.verdict, s.channels = "refuse", []
            s.refusal = Refusal(RULE, "outbound-scan", f"could not read {type(exc).__name__}")
            return s
        if any(c.kind == "l3" for c in s.channels):
            s.verdict = "l3"
        return s

    def _own_keys(self, values: dict[str, Any], ids: Sequence[int]) -> bool:
        keys = [str(values.get("key") or "")]
        if ids:
            rows = self.rpc("ir.config_parameter", "read", [list(ids)], {"fields": ["key"]})
            keys += [str(r.get("key") or "") for r in rows]
        return any(k.startswith(OWN_KEY_PREFIX) for k in keys)

    def _scan_model(self, s: Scan, model: str, op: str, depth: int, seen: set) -> None:
        if (model, op) in seen:
            return
        seen.add((model, op))
        if depth > MAX_DEPTH:
            s.channels.append(Channel("l3", model, f"automation chain deeper than {MAX_DEPTH}"))
            return
        if not _has(self.rpc, "base.automation"):
            return
        rows = self.rpc(
            "base.automation",
            "search_read",
            [[("model_id.model", "=", model), ("active", "=", True)]],
            {"fields": ["name", "trigger", "action_server_ids"]},
        )
        for r in rows:
            trig = r.get("trigger")
            if trig not in TRIGGERS:
                s.channels.append(Channel("l3", "automation", f"'{r['name']}' unknown trigger"))
                continue
            if op not in TRIGGERS[trig][0]:
                continue
            aids = list(r.get("action_server_ids") or [])
            self._actions(s, r["name"], aids, depth, seen, trig in TIME_TRIGGERS)

    def _actions(
        self, s: Scan, rule: str, aids: list[int], depth: int, seen: set, later: bool = False
    ) -> None:
        if not aids:
            return
        avail = self.rpc("ir.actions.server", "fields_get", [], {"attributes": ["type"]})
        want = [f for f in ("name", "state", "child_ids", "crud_model_id", "template_id")]
        acts = self.rpc(
            "ir.actions.server", "read", [aids], {"fields": [f for f in want if f in avail]}
        )
        if len(acts) != len(set(aids)):
            raise SinkholeError("server action unreadable")
        for a in acts:
            st = a.get("state")
            kind, why = ACTION_KINDS.get(st, ("l3", f"unknown action type {st!r}"))
            label = f"'{rule}' / '{a.get('name')}'"
            if later and kind in ("hold", "recurse"):
                s.channels.append(
                    Channel("l3", "automation", f"{label}: sends later from Odoo's scheduler")
                )
            elif kind == "hold":
                s.channels.append(Channel("hold", "automation", f"{label}{self._tpl(a)}"))
            elif kind == "l3":
                s.channels.append(Channel("l3", "automation", f"{label}: {why}"))
            elif kind == "recurse":
                if st == "multi":
                    kids = list(a.get("child_ids") or [])
                    self._actions(s, rule, kids, depth + 1, seen, later)
                else:
                    crud = a.get("crud_model_id")
                    if not crud:
                        raise SinkholeError("action target unreadable")
                    tgt = self.rpc("ir.model", "read", [[crud[0]]], {"fields": ["model"]})
                    sub = _C if st in ("object_create", "object_copy") else _W
                    self._scan_model(s, tgt[0]["model"], sub, depth + 1, seen)

    def _tpl(self, a: dict) -> str:
        tpl = a.get("template_id")
        if not tpl:
            return ""
        avail = self.rpc("mail.template", "fields_get", [], {"attributes": ["type"]})
        fs = [f for f in ("attachment_ids", "report_template_ids", "report_template") if f in avail]
        t = self.rpc("mail.template", "read", [[tpl[0]]], {"fields": ["name", *fs]})
        if not t:
            raise SinkholeError("template unreadable")
        att = any(t[0].get(f) for f in fs)
        return f" (template '{t[0]['name']}'{', with attachments' if att else ''})"

    def _business(self, s: Scan, model: str, values: dict[str, Any]) -> None:
        if model not in BUSINESS_OUTBOUND:
            return
        touched = set(values) & (rr.STATE_POSTING_ALL | rr.POSTING_FIELDS | {"state"})
        if not touched and s.op != _U:
            return
        pmodel, dom, why = BUSINESS_OUTBOUND[model]
        if not _has(self.rpc, pmodel):
            return
        n = self.rpc(pmodel, "search_count", [dom], None)
        if n:
            s.channels.append(Channel("l3", pmodel, f"{n} live {PROVIDER_LABELS[pmodel]}: {why}"))

    # ---------- the one write path ----------
    def _halted(self) -> bool:
        try:
            return self.switch.check(self.db) is not None
        except Exception:  # noqa: BLE001 - unreadable switch = halted
            return True

    def _qwrite(
        self, purpose: str, model: str, ids: list[int], vals: dict[str, Any] | None = None
    ) -> Any:
        if purpose in ("release", "discard") and self._halted():
            raise PermissionError("kill switch on: release and discard refused")
        rule, vals = PURPOSES.get(purpose), dict(vals or {})
        if rule is None or model not in rule[0] or not set(vals) <= rule[1]:
            raise SinkholeError(f"refused write {purpose} on {model}")
        if any(vals.get(k) != v for k, v in rule[3].items()):
            raise SinkholeError(f"refused value for {purpose}")
        if model == "ir.config_parameter" and rule[2] != "create" and ids != [self._lease_id]:
            raise SinkholeError("refused: not this window's lease")
        ctx = {"context": {"active_test": False, **QUIET_CTX}}
        if rule[2] == "create":
            return self.rpc(model, "create", [vals], ctx)
        if rule[2] == "unlink":
            return self.rpc(model, "unlink", [list(ids)], ctx)
        return self.rpc(model, "write", [list(ids), vals], ctx)

    def quiet(self, rpc: Rpc) -> Rpc:
        """Wrap the gate's rpc: every write/create/unlink carries QUIET_CTX (plan ctx kept)."""

        def call(model: str, method: str, args: Sequence[Any], kw: dict | None = None) -> Any:
            if method in ("write", "create", "unlink"):
                if self._lease_id is not None and not self._lost and not self._guard():
                    raise SinkholeError("sinkhole lease lost: run stopped")
                kw = dict(kw or {})
                kw["context"] = {**dict(kw.get("context") or {}), **QUIET_CTX}
            return rpc(model, method, args, kw)

        return call

    # ---------- window ----------
    def _max(self, model: str) -> int:
        if not _has(self.rpc, model):
            return -1
        r = self.rpc(model, "search", [[]], {"limit": 1, "order": "id desc", **_RA})
        return int(r[0]) if r else 0

    def _cron_ids(self) -> list[int]:
        out = []
        for xid in QUEUE_CRONS:
            mod, name = xid.split(".", 1)
            r = self.rpc(
                "ir.model.data",
                "search_read",
                [[("module", "=", mod), ("name", "=", name), ("model", "=", "ir.cron")]],
                {"fields": ["res_id"]},
            )
            out += [x["res_id"] for x in r]
        return out

    def _lease(self) -> list[dict]:
        return self.rpc(
            "ir.config_parameter",
            "search_read",
            [[("key", "=", LEASE_KEY)]],
            {"fields": ["value"]},
        )

    def _own(self) -> bool:
        try:
            rows = self._lease()
            return (
                len(rows) == 1
                and rows[0]["id"] == self._lease_id
                and json.loads(rows[0]["value"]).get("hold_id") == self.ledger.hold_id
            )
        except Exception:  # noqa: BLE001 - unreadable = not provably ours
            return False

    def _guard(self) -> bool:
        """Lease still ours -> refresh heartbeat. Lost -> stop, trip the switch, report."""
        if self._own():
            try:
                self._rec["beat"] = self.clock()
                self._qwrite(
                    "lease_beat",
                    "ir.config_parameter",
                    [self._lease_id],
                    {"value": json.dumps(self._rec)},
                )
                return True
            except Exception:  # noqa: BLE001 - a run that cannot beat must not continue
                pass
        self._lost = True
        if "sinkhole lease lost" not in self.report.unheld:
            self.report.unheld.append("sinkhole lease lost")
        self._stop("sinkhole lease lost or taken mid-run")
        return False

    def open(self, scan: Scan, approval_level: int) -> Refusal | None:
        if scan.verdict == "refuse":
            return scan.refusal or Refusal(RULE, "outbound-scan", "scan refused")
        if scan.need_tier == 3 and approval_level < 3:
            return Refusal(RULE, "outbound-l3", "an outbound channel cannot be held; L3 needed")
        if self._halted():
            return Refusal(RULE, "kill-switch", "kill switch on")
        try:
            if self._lease():
                return Refusal(
                    RULE, "outbound-lease", "another bot run is holding outbound for this database"
                )
            for m in ("mail.mail", "sms.sms", "mail.notification"):
                self.base[m] = self._max(m)
            crons = self._cron_ids()
            live = (
                self.rpc(
                    "ir.cron", "search_read", [[("id", "in", crons)]], _RA | {"fields": ["active"]}
                )
                if crons
                else []
            )
            act = [c["id"] for c in live if c["active"]]
            rec = {
                "hold_id": self.ledger.hold_id,
                "uid": self.uid,
                "paused": act,
                "base": self.base,
                "beat": self.clock(),
            }
            self._rec = rec
            # persisted BEFORE the pause; the unique key makes a second window fail here
            self._lease_id = self._qwrite(
                "lease_take",
                "ir.config_parameter",
                [],
                {"key": LEASE_KEY, "value": json.dumps(rec)},
            )
            mine = self._lease()
            if len(mine) != 1 or json.loads(mine[0]["value"]).get("hold_id") != self.ledger.hold_id:
                raise SinkholeError("lease did not read back")
            self.ledger.paused = list(act)
            if act:
                self.paused = act
                self._qwrite("pause", "ir.cron", act, {"active": False})
                back = self.rpc("ir.cron", "read", [act], {"fields": ["active"]})
                if any(c["active"] for c in back) or len(back) != len(act):
                    raise SinkholeError("queue pause did not read back")
        except Exception as exc:  # noqa: BLE001
            if self._restore():
                self._drop_lease()
            return Refusal(
                RULE, "outbound-pause", f"could not pause the queue {type(exc).__name__}"
            )
        self._opened = True
        return None

    def _new(self, model: str, fields: list[str]) -> list[dict]:
        b = self.base.get(model, -1)
        if b < 0:
            return []
        dom = [("id", ">", b), ("create_uid", "=", self.uid)]
        return self.rpc(model, "search_read", [dom], {"fields": fields, **_RA})

    def after_batch(self) -> bool:
        """Hold + prove. False = escaped or unheld (switch on; the gate trips and undoes)."""
        if not self._opened:
            return False
        rep, lg = self.report, self.ledger
        if self._lost or (self._lease_id is not None and not self._guard()):
            return False
        marker = HOLD_PREFIX + lg.hold_id
        try:
            mails = self._new(
                "mail.mail", ["state", "failure_reason", "subject", "attachment_ids", "model"]
            )
            sms = self._new("sms.sms", ["state"])
            notes = self._new_notifications()
        except Exception:  # noqa: BLE001 - cannot prove = not clean
            rep.unheld.append("outbound records unreadable")
            self._stop("outbound proof unreadable")
            return False
        todo_m = [m["id"] for m in mails if m["state"] == "outgoing"]
        todo_s = [x["id"] for x in sms if x["state"] == "outgoing"]
        for m in mails:
            mine = m["state"] == "cancel" and m.get("failure_reason") == marker
            key = f"mail:{m['id']}"
            if m["state"] != "outgoing" and not mine and key not in rep.escaped:
                rep.escaped.append(key)
        for x in sms:
            if x["state"] not in ("outgoing", "canceled") and f"sms:{x['id']}" not in rep.escaped:
                rep.escaped.append(f"sms:{x['id']}")
        rep.escaped += [n for n in notes if n not in rep.escaped]
        self._hold("mail.mail", todo_m, {"state": "cancel", "failure_reason": marker}, lg.mail_ids)
        self._hold("sms.sms", todo_s, {"state": "canceled"}, lg.sms_ids)
        rep.held_mail = [m for m in mails if m["id"] in lg.mail_ids]
        rep.held_sms = [x for x in sms if x["id"] in lg.sms_ids]
        if not rep.clean:
            self._stop("outbound message escaped or unheld")
            return False
        return True

    def _new_notifications(self) -> list[str]:
        b = self.base.get("mail.notification", -1)
        if b < 0:
            return []
        dom = [
            ("id", ">", b),
            ("mail_message_id.create_uid", "=", self.uid),
            ("notification_status", "in", ["sent", "bounce", "exception"]),
        ]
        rows = self.rpc("mail.notification", "search_read", [dom], {"fields": ["id"], **_RA})
        return [f"notification:{r['id']}" for r in rows]

    def _hold(self, model: str, ids: list[int], vals: dict, into: list[int]) -> None:
        if not ids:
            return
        try:
            self._qwrite("hold", model, ids, vals)
            back = self.rpc(model, "read", [ids], {"fields": list(vals)})
            ok = {r["id"] for r in back if all(r.get(k) == v for k, v in vals.items())}
        except Exception:  # noqa: BLE001 - demoted / locked: not held
            ok = set()
        into += [i for i in ids if i in ok and i not in into]
        self.report.unheld += [f"{model}:{i}" for i in ids if i not in ok]

    def _stop(self, why: str) -> None:
        try:
            self.switch.turn_on(self.db, "system", f"sinkhole: {why}")
        except Exception:  # noqa: BLE001 - already failing closed
            pass

    def readback(self, inner: Callable[[Sequence[Any]], bool]) -> Callable[[Sequence[Any]], bool]:
        """Compose with the plan's readback for WriteGate.run: both must pass."""
        return lambda chunk: bool(inner(chunk)) and self.after_batch()

    def close(self) -> Report:
        rep = self.report
        if self._opened:
            self.after_batch()
            others = self.base.get("mail.mail", -1)
            if others >= 0:
                try:
                    dom = [("id", ">", others), ("create_uid", "!=", self.uid)]
                    dom.append(("state", "=", "outgoing"))
                    rep.others_queued = int(self.rpc("mail.mail", "search_count", [dom], None))
                except Exception:  # noqa: BLE001 - informational only
                    rep.others_queued = 0
        if self._lost or (self._lease_id is not None and not self._own()):
            self._lost = True  # not ours: never unpause or drop what another window owns
            if "sinkhole lease lost" not in rep.unheld:
                rep.unheld.append("sinkhole lease lost")
            self._stop("sinkhole lease lost before close")
        elif not rep.unheld:  # unheld = queue + lease stay: blocks every run until recovery
            rep.crons_restored = self._restore()
            if rep.crons_restored:
                self._drop_lease()
        self._opened = False
        return rep

    def _restore(self) -> bool:
        if not self.paused:
            return True
        try:
            self._qwrite("restore", "ir.cron", self.paused, {"active": True})
            back = self.rpc("ir.cron", "read", [self.paused], {"fields": ["active"]})
            ok = len(back) == len(self.paused) and all(c["active"] for c in back)
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.paused = []
        else:
            self._stop("queue cron restore failed")
        return ok

    def _drop_lease(self) -> None:
        if self._lease_id is None:
            return
        try:
            self._qwrite("lease_drop", "ir.config_parameter", [self._lease_id])
            self._lease_id = None
        except Exception:  # noqa: BLE001 - lease stays: runs refused until recovery
            self._stop("lease release failed")

    # ---------- human decision ----------
    def _owner_ok(self, actor: SessionActor) -> bool:
        if not isinstance(actor, SessionActor):
            raise TypeError("actor must be a SessionActor from the authenticated session")
        try:
            owner = self.switch.owner_of(self.db)
        except Exception:  # noqa: BLE001
            return False
        return bool(owner) and str(owner).strip().casefold() == actor.login.strip().casefold()

    def recover(self, actor: SessionActor) -> dict[str, Any]:
        """Owner-only, idempotent: after a crash, hold any bot mail left since the baseline,
        restore exactly the crons the lease recorded, then drop the lease."""
        if not self._owner_ok(actor):
            raise PermissionError("only the database owner may recover a sinkhole window")
        if self._halted():
            raise PermissionError("kill switch on: clear it before recovery")
        rows = self._lease()
        if not rows:
            return {"status": "nothing to recover"}
        rec = json.loads(rows[0]["value"])
        age = self.clock() - float(rec.get("beat") or 0)
        if age < LEASE_STALE_S:
            out0 = {"status": "refused: the run holding the lease is alive", "age_s": int(age)}
            out0 |= {"limit_s": LEASE_STALE_S, "by": actor.login}
            log.warning("sinkhole recovery %s", out0)
            return out0
        self._rec = rec
        self._lease_id, self.uid = rows[0]["id"], int(rec["uid"])
        self.ledger.hold_id, self.base = rec["hold_id"], dict(rec["base"])
        self.paused = list(rec["paused"])
        self.ledger.paused = list(self.paused)
        self._opened = True
        self.after_batch()
        rep = self.report
        out: dict[str, Any] = {
            "hold_id": rec["hold_id"],
            "held_mail": list(self.ledger.mail_ids),
            "escaped": list(rep.escaped),
            "by": actor.login,
        }
        self._opened = False
        if rep.unheld:
            out["status"] = "blocked: messages could not be held; queue left paused"
        elif self._restore():
            self._drop_lease()
            out["status"] = "recovered" if self._lease_id is None else "lease not released"
        else:
            out["status"] = "queue restore failed"
        log.warning("sinkhole recovery %s", out)
        return out

    def decide(self, ledger: Ledger, actor: SessionActor, release: bool) -> dict[str, list[str]]:
        """Owner releases (sends) or discards (keeps cancelled, marked) held messages. One-shot
        per message: a second decision on the same id is refused. Both need the switch off."""
        if ledger.db != self.db or not self._owner_ok(actor):
            raise PermissionError("only the database owner may release or discard held messages")
        if self._halted():
            raise PermissionError("kill switch on: release and discard refused")
        verb = "released" if release else "discarded"
        marker = HOLD_PREFIX + ledger.hold_id
        out: dict[str, list[str]] = {"done": [], "refused": list(ledger.done)}
        pend_m = [i for i in ledger.mail_ids if f"mail:{i}" not in ledger.done]
        pend_s = [i for i in ledger.sms_ids if f"sms:{i}" not in ledger.done]
        if pend_m:
            rows = self.rpc("mail.mail", "read", [pend_m], {"fields": ["state", "failure_reason"]})
            ok = [r["id"] for r in rows if r["state"] == "cancel" and r["failure_reason"] == marker]
            out["refused"] += [f"mail:{i}" for i in pend_m if i not in ok]
            if ok:
                vals = (
                    {"state": "outgoing", "failure_reason": False}
                    if release
                    else {"failure_reason": f"{DISCARD_PREFIX}{ledger.hold_id} by {actor.login}"}
                )
                self._qwrite("release" if release else "discard", "mail.mail", ok, vals)
                for i in ok:
                    ledger.done[f"mail:{i}"] = verb
                    out["done"].append(f"mail:{i}")
        if pend_s:
            rows = self.rpc("sms.sms", "read", [pend_s], {"fields": ["state"]})
            ok = [r["id"] for r in rows if r["state"] == "canceled"]
            out["refused"] += [f"sms:{i}" for i in pend_s if i not in ok]
            if ok:
                vals = {"state": "outgoing" if release else SMS_DISCARDED}
                self._qwrite("release" if release else "discard", "sms.sms", ok, vals)
            for i in ok:
                ledger.done[f"sms:{i}"] = verb
                out["done"].append(f"sms:{i}")
        return out


_WIZ = "send wizard: sends only on an explicit button (risk classifier, per button)"
_STAGE = "stage email template: runs via tracking, off under tracking_disable; held anyway"
_CFG = "configuration pointer to a template; sends only through a held queue or a button"
# Every 17-20 model with a stored field pointing at mail/sms templates or queues, or holding a
# webhook, and why the sinkhole covers it (drift test: tests/test_nf_bot_sinkhole.py).
REVIEWED_OUTBOUND_MODELS: dict[str, str] = {
    "base.automation": "scanned live: rules on the plan model and their actions",
    "ir.actions.server": "scanned live: action kind decides hold / quiet / L3",
    "mail.mail": "the email queue: bot rows are held (state cancel + marker)",
    "mail.message": "chatter rows; email copies go through mail.mail (held)",
    "mail.notification": "read for proof: a bot notification marked sent = escaped",
    "mailing.mailing": "mass mailing sends only on its send button or its own cron",
    "mailing.trace": "mass mailing log row; mail goes through mail.mail (held)",
    "ir.mail_server": "outgoing server config; nothing sends without a queued mail.mail",
    "fetchmail.server": "inbound mail fetch; no send",
    "mail.template.preview": "transient preview; renders, never sends",
    "mail.template.reset": "transient reset wizard; no send",
    "sms.template.preview": "transient preview; renders, never sends",
    "sms.template.reset": "transient reset wizard; no send",
    "mail.composer.mixin": "abstract mixin for composers (send wizards)",
    "mail.compose.message": _WIZ,
    "sms.composer": _WIZ,
    "account.move.send": _WIZ,
    "account.move.send.wizard": _WIZ,
    "applicant.get.refuse.reason": _WIZ,
    "applicant.refuse.single": _WIZ,
    "applicant.send.mail": _WIZ,
    "candidate.send.mail": _WIZ,
    "fleet.vehicle.send.mail": _WIZ,
    "calendar.popover.delete.wizard": _WIZ,
    "slide.channel.invite": _WIZ,
    "survey.invite": _WIZ,
    "sale.order.cancel": _WIZ,
    "project.task.type": _STAGE,
    "project.project.stage": _STAGE,
    "hr.recruitment.stage": _STAGE,
    "hr.applicant.refuse.reason": _CFG,
    "mail.activity.type": _CFG,
    "calendar.alarm": (
        "deferred: reminders come later from the alarm scheduler as the system user; L3"
    ),
    "gamification.challenge": (
        "deferred: reports come later from its scheduler as the system user; L3"
    ),
    "loyalty.mail": "coupon emails are created in the bot's own call (bot-created mail.mail, held)",
    "pos.config": _CFG,
    "pos.preset": _CFG,
    "res.company": _CFG,
    "res.config.settings": "transient settings wizard; stored values elsewhere",
    "sale.order": "confirmation email is queued mail.mail (held); payment is BUSINESS_OUTBOUND",
    "sale.order.template": _CFG,
    "slide.channel": "enrol emails are created in the bot's own call (bot-created mail.mail, held)",
    "survey.survey": (
        "config: certification mail is sent when a participant finishes, not on a bot write"
    ),
    "website": "browser-side settings; no server send on a write",
}
