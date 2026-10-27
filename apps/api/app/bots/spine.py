"""BOT-SPINE-WIRE: connects the bot pieces into one guarded path. No new write path.

What it wires (each was a "BOT-SPINE-WIRE must ..." item in an earlier card):

- ``SessionAuthority``: the only place a ``Session`` is minted, by the server auth layer from a
  signed-in login and server session id. Every session carries an in-process MAC, so request
  bodies, plan data or chat text can never stand in for one (a dataclass built by hand fails
  ``verify``). Bot sessions and human sessions are distinct kinds.
- ``SpineDecisions``: ``operator_flow.Decisions`` bound to the session and ``ApprovalStore``.
  The level is never taken from the caller: approve submits one approval ``Plan`` per planned
  walker step (same plan hash the gate computes), lets the store tier it (with the walker's
  tier as a floor) and decides as the signed-in person; ``approval_for`` re-derives the plans
  from the card now and reads only the store, so an edited JSON file, a stale card, changed
  facts or a used grant give nothing to run.
- ``SpineFlow``: ``OperatorFlow`` on a walker built here: ``TierRehearsals`` + the store's
  ``grant_source`` on the kill switch (owner-signed grants), the bot's own Odoo user checked
  against the bot session (the sinkhole hold and lockout simulation key on it), ``reviewed``
  from the owner's ``ReviewedStore``, edition/installed modules read from the database
  (``caps_ctx``), and the rehearsal id routed into the base ``RunSpec``. Every card is graded
  by ``tiers.assess`` before it can run; a refusal blocks the card with the plain reason and
  is listed in ``grades`` (never dropped). Undo goes back through plan, store and gate.
- T3 (module code): ``submit_t3`` turns authoring results and owned change sets into L3
  approval items; ``apply_t3`` checks approval, ``gate_passed`` (version + module bound) and
  the approved change-set id, then the T3 switch, and only then returns the patched files
  (pure: nothing is installed or written). The switch is read, never changed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.bots import approval as ap
from app.bots import before_image as bi
from app.bots import client_doc as cd
from app.bots import guard as gd
from app.bots import module_test_gate as mtg
from app.bots import owned_change as oc
from app.bots import sinkhole as sh
from app.bots import tiers as tr
from app.bots import walker as wk
from app.bots.diff import ReadOnly
from app.bots.operator_flow import flow as fl
from app.bots.risk.rules import Refusal, a_kind

HUMAN, BOT = "human", "bot"
ENTERPRISE_MARKERS = ("web_enterprise",)


class SpineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


# ------------------------------------------------------------------ sessions
@dataclass(frozen=True)
class Session:
    kind: str
    login: str
    session_id: str
    odoo_uid: int | None
    mac: str = dataclasses.field(repr=False, default="")

    def actor(self) -> sh.SessionActor:
        return sh.SessionActor(self.login, self.session_id)


class SessionAuthority:
    """Mints and verifies sessions. Only the server auth layer holds an instance; the key lives
    in this process and is never exported, logged or derived from input."""

    def __init__(self) -> None:
        self._key = secrets.token_bytes(32)

    def _session_tag(self, kind: str, login: str, sid: str, uid: int | None) -> str:
        msg = json.dumps([kind, login, sid, uid]).encode()
        return hmac.new(self._key, msg, hashlib.sha256).hexdigest()

    def _issue(self, kind: str, login: Any, session_id: Any, uid: Any) -> Session:
        if not isinstance(login, str) or not login.strip() or login != login.strip():
            raise SpineError("unauthenticated", "a signed-in login is required")
        if not isinstance(session_id, str) or len(session_id) < 16:
            raise SpineError("unauthenticated", "a server session id is required")
        if uid is not None and (not isinstance(uid, int) or isinstance(uid, bool) or uid < 1):
            raise SpineError("unauthenticated", "bad Odoo user id")
        is_bot = gd.norm(login).startswith("bot")
        if (kind == HUMAN) == is_bot:
            raise SpineError("unauthenticated", f"{login!r} is not a {kind} login")
        return Session(
            kind, login, session_id, uid, self._session_tag(kind, login, session_id, uid)
        )

    def seal(self, rec: Mapping[str, Any]) -> str:
        """MAC over a saved record (canonical JSON); the store file can't mint or edit one."""
        msg = json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hmac.new(self._key, b"rec\0" + msg, hashlib.sha256).hexdigest()

    def unsealed(self, rec: Mapping[str, Any], tag: Any) -> bool:
        return isinstance(tag, str) and hmac.compare_digest(self.seal(rec), tag)

    def issue_human(self, *, login: str, session_id: str) -> Session:
        return self._issue(HUMAN, login, session_id, None)

    def issue_bot(self, *, login: str, session_id: str, odoo_uid: int) -> Session:
        if odoo_uid is None:
            raise SpineError("unauthenticated", "a bot session needs its Odoo user id")
        return self._issue(BOT, login, session_id, odoo_uid)

    def verify(self, s: Any, kind: str) -> Session:
        if not isinstance(s, Session) or s.kind != kind:
            raise SpineError("unauthenticated", f"a signed-in {kind} session is required")
        want = self._session_tag(s.kind, s.login, s.session_id, s.odoo_uid)
        if not hmac.compare_digest(want, s.mac or ""):
            raise SpineError("unauthenticated", "session was not issued by this server")
        return s


# ------------------------------------------------------------------ owner store
class ReviewedStore(fl._Json):
    """Custom x_ models a database owner has reviewed. Only the owner, signed in, can add one;
    the walker's ``reviewed`` comes from here, never from a caller."""

    def __init__(
        self, path: Path, authority: SessionAuthority, owner_of: Callable[[str], str | None]
    ) -> None:
        super().__init__(path)
        self.auth, self.owner_of = authority, owner_of

    def mark(self, session: Any, db: str, model: str, note: str) -> None:
        s = self.auth.verify(session, HUMAN)
        if gd.norm(self.owner_of(db)) != gd.norm(s.login) or not gd.norm(s.login):
            raise SpineError("forbidden", "only the database owner can review custom models")
        if not isinstance(model, str) or not model.startswith("x_") or not note.strip():
            raise SpineError("bad-input", "only custom x_ models, with a note, can be reviewed")
        rec = {"note": note.strip()[:200], "by": s.login, "at": fl._now()}
        self.update(lambda d: d.setdefault(db, {}).__setitem__(model, rec))

    def reviewed(self, db: str) -> dict[str, str]:
        rows = self.load().get(db, {})
        return {
            m: str(r.get("note", ""))
            for m, r in rows.items()
            if isinstance(r, dict) and m.startswith("x_")
        }


# ------------------------------------------------------------------ proofs
class Proofs(Protocol):
    """Server-side facts the approval tier depends on (clone rehearsal store, snapshot proof)."""

    rehearsal_id: str

    def rehearsal_passed(self, rehearsal_id: str) -> bool: ...

    def snapshot_verified(self, db: str, model: str, ids: Sequence[Any]) -> bool: ...


def caps_ctx(read: Any) -> dict[str, Any]:
    """Edition and installed modules, read from the database (for client_doc, flow, tiers)."""
    try:
        rows = ReadOnly(read)(
            "ir.module.module", "search_read", [[("state", "=", "installed")]], {"fields": ["name"]}
        )
        names = sorted({str(r["name"]) for r in rows if isinstance(r, Mapping) and r.get("name")})
    except Exception as exc:  # noqa: BLE001 - unreadable = refuse, never guess community
        raise SpineError("caps-unreadable", "installed modules could not be read") from exc
    if not names:
        raise SpineError("caps-unreadable", "no installed modules reported")
    ed = "enterprise" if any(m in names for m in ENTERPRISE_MARKERS) else "community"
    return {"edition": ed, "installed": names}


# ------------------------------------------------------------------ step -> approval plan
def _call_id(method: str, args: Sequence[Any]) -> str:
    """The single id ``WriteGate.call`` hashes for a button/create/unlink job."""
    return json.dumps([method, list(args), None], sort_keys=True, default=str)


def step_plan(
    p: wk.Planned, *, connection_id: str, db: str, requested_by: str, summary: str, proofs: Proofs
) -> ap.Plan:
    st = p.step
    rid = proofs.rehearsal_id
    common = dict(
        connection_id=connection_id,
        db_fingerprint=db,
        task_id=p.task_id,
        model=st.model,
        risk_class=p.cls,
        subkind=p.sub,
        requested_by=requested_by,
        summary=summary[:200],
        rehearsal_id=rid or None,
        rehearsal_passed=bool(rid) and proofs.rehearsal_passed(rid) is True,
        min_tier=p.tier if p.tier in (1, 2, 3) else 3,
    )
    if st.kind in ("write", "create"):
        # a reversible step is undone from its before-image; one that sends or posts is not,
        # and needs a checked backup (classify refuses it otherwise)
        irr = a_kind(p.cls, p.sub) == "irr"
        undo = (
            {
                "undo_route": "snapshot",
                "snapshot_verified": proofs.snapshot_verified(db, st.model, list(st.ids)) is True,
            }
            if irr
            else {"undo_route": "before_image"}
        )
        if st.kind == "write":
            return ap.Plan(ids=list(st.ids), values=dict(st.values), **undo, **common)
        return ap.Plan(
            ids=[_call_id("create", [dict(st.values)])], values={}, call=True, **undo, **common
        )
    meth = "unlink" if st.kind == "unlink" else st.method
    snap = proofs.snapshot_verified(db, st.model, list(st.ids)) is True
    return ap.Plan(
        ids=[_call_id(meth, [list(st.ids)])],
        values={},
        call=True,
        irreversible=True,
        undo_route="snapshot",
        snapshot_verified=snap,
        **common,
    )


# ------------------------------------------------------------------ decisions
class SpineDecisions(fl.Decisions):
    """Decisions whose actor is the signed-in person and whose level comes from the store."""

    def __init__(
        self,
        path: Path,
        *,
        store: ap.ApprovalStore,
        authority: SessionAuthority,
        connection_id: str,
        plans: Callable[[fl.StepCard], list[ap.Plan]],
    ) -> None:
        super().__init__(path)
        self.store, self.auth, self.conn, self._plans = store, authority, connection_id, plans

    def approve(self, plan_id: str, card: fl.StepCard, actor: Any, level: Any = None) -> None:
        """``level`` is ignored: the store decides the tier."""
        s = self.auth.verify(actor, HUMAN)
        plans = self._plans(card)
        rows = [self.store.submit(p) for p in plans]
        refused = [r for r in rows if r["status"] in ("refused", "rejected")]
        if refused:
            why = refused[0].get("card", {}).get("refusal") or refused[0]["status"]
            raise SpineError("refused", f"this step can't be approved: {why}")
        for r in rows:
            if r["status"] == "pending":
                try:
                    self.store.approve(self.conn, r["id"], s.login)
                except ap.ApprovalError as exc:
                    raise SpineError(exc.code, exc.message) from exc
        rec = {
            "decision": "approve",
            "actor": s.login,
            "session": s.session_id[:8],
            "level": max(int(r["tier"]) for r in rows),
            "plans": [p.hash() for p in plans],
        }
        rec["seal"] = self.auth.seal(self._sealed(plan_id, card, rec))
        self._put(plan_id, card, rec)

    @staticmethod
    def _sealed(plan_id: str, card: fl.StepCard, r: Mapping[str, Any]) -> dict[str, Any]:
        keys = ("decision", "actor", "session", "level", "plans")
        return {"plan": plan_id, "slot": card.slot, "hash": card.digest} | {
            k: r.get(k) for k in keys
        }

    def skip(self, plan_id: str, card: fl.StepCard, actor: Any) -> None:
        s = self.auth.verify(actor, HUMAN)
        self._put(plan_id, card, {"decision": "skip", "actor": s.login})

    def approval_for(self, plan_id: str, card: fl.StepCard) -> gd.Approval | None:
        r = self.get(plan_id, card)
        if not r or r.get("decision") != "approve" or r.get("hash") != card.digest:
            return None
        if not self.auth.unsealed(self._sealed(plan_id, card, r), r.get("seal")):
            return None  # edited or forged decision row (actor, session, level or plans)
        try:
            plans = self._plans(card)
        except SpineError:
            return None
        hashes = [p.hash() for p in plans]
        if not hashes or hashes != r.get("plans"):
            return None
        try:  # re-submit: facts that changed since the decision put the row back (never up)
            for p in plans:
                self.store.submit(p)
        except Exception:  # noqa: BLE001 - unreadable store = nothing to run
            return None
        got = [
            self.store.approval_for(p.db_fingerprint, h) for p, h in zip(plans, hashes, strict=True)
        ]
        if any(a.level < 1 for a in got):
            return None
        humans = {a.approver for a in got if a.approver}
        if len(humans) > 1 or (humans and gd.norm(next(iter(humans))) != gd.norm(r.get("actor"))):
            return None
        return gd.Approval(min(a.level for a in got), next(iter(humans), None))


# ------------------------------------------------------------------ flow
@dataclass
class Wiring:
    """Server-side pieces. None of these come from a request."""

    engine: Any
    audit: Any
    owner_of: Callable[[str], str | None]
    rehearsals: gd.Rehearsals  # the clone rehearsal store, wrapped in TierRehearsals here
    proofs: Proofs
    authority: SessionAuthority
    reviewed: ReviewedStore
    workdir: Path


class SpineFlow(fl.OperatorFlow):
    def __init__(
        self,
        spec: Any,
        rpc: Any,
        wiring: Wiring,
        bot: Any,
        *,
        connection_id: str,
        db: str,
        version: int,
        plan_id: str,
        companies: Sequence[int] | None = None,
    ) -> None:
        a = wiring.authority
        self.bot = a.verify(bot, BOT)
        self.wiring, self.conn, self.db, self.version = wiring, connection_id, db, version
        read = ReadOnly(rpc)
        _check_bot_user(read, self.bot)
        self.caps = caps_ctx(read)
        sw = gd.KillSwitch(wiring.engine, wiring.owner_of)
        self.store = ap.ApprovalStore(wiring.engine, sw, wiring.audit)
        sw.grant_source = self.store.grant_source
        d = Path(wiring.workdir)
        walker = wk.Walker(
            rpc,
            sw,
            wiring.audit,
            ap.TierRehearsals(wiring.rehearsals, self.store),
            bi.ImageStore(d / "before_images"),
            wk.Ledger(d / "walker_ledger.json"),
            db=db,
            bot_uid=int(self.bot.odoo_uid or 0),
            version=version,
            reviewed=wiring.reviewed.reviewed(db),
        )
        base = gd.RunSpec(
            db,
            "spine",
            self.bot.login,
            "R2",
            "SPINE",
            gd.Approval(0),
            f"spine:{plan_id}",
            rehearsal_id=wiring.proofs.rehearsal_id or None,
        )
        dec = SpineDecisions(
            d / "decisions.json",
            store=self.store,
            authority=a,
            connection_id=connection_id,
            plans=self.plans_for,
        )
        super().__init__(
            spec,
            walker,
            dec,
            d / "flow_state.json",
            base,
            plan_id=plan_id,
            edition=self.caps["edition"],
            installed=self.caps["installed"],
            companies=companies,
        )
        self.grades: dict[str, dict[str, Any]] = {}

    # every card graded before it can run; refusals are explained, never dropped
    def cards(self) -> list[fl.StepCard]:
        out = super().cards()
        for c in out:
            g = self._grade(c)
            self.grades[c.slot] = g
            if not g["allowed"] and not c.blocked:
                c.blocked = "not allowed: " + g["message"]
                c.seal()
        return out

    def _grade(self, c: fl.StepCard) -> dict[str, Any]:
        if c.walk is None:
            msg = c.blocked or c.noop or "no planned change"
            return {"allowed": c.noop is not None, "tier": None, "message": msg, "parts": []}
        parts = [
            tr.assess(
                p.task_id,
                version=self.version,
                edition=self.caps["edition"],
                installed_modules=self.caps["installed"],
                fields=sorted(p.step.values),
            )
            for p in c.walk.steps
        ]
        plan = tr.compose(parts)
        return {
            "allowed": plan.allowed,
            "tier": max((a.tier or 0) for a in parts) or None,
            "message": plan.message() or "",
            "parts": [{"task": a.task_id, "grade": a.grade, "reason": a.reason} for a in parts],
        }

    def plans_for(self, card: fl.StepCard, requested_by: str | None = None) -> list[ap.Plan]:
        if card.blocked or card.walk is None or not card.walk.steps:
            raise SpineError("refused", card.blocked or "this step has no safe plan to approve")
        return [
            step_plan(
                p,
                connection_id=self.conn,
                db=self.db,
                requested_by=requested_by or self.bot.login,
                summary=card.title,
                proofs=self.wiring.proofs,
            )
            for p in card.walk.steps
        ]

    # ---- client documents with the database's real edition and modules
    def handoff(self, run: Mapping[str, Any], verify: Mapping[str, Any]) -> dict[str, Any]:
        return cd.handoff(self.spec, run, verify, [c.to_dict() for c in self.cards()], self.caps)

    def clarification(self, review: Any, fit: Any) -> dict[str, Any]:
        return cd.clarification(self.spec, review, fit, self.caps)

    # ---- undo: a person asks, a different person approves, the gate runs it
    def request_undo(self, session: Any) -> dict[str, Any]:
        s = self.wiring.authority.verify(session, HUMAN)
        steps = self.undo_plan()
        if isinstance(steps, Refusal):
            return {"status": "refused", "reason": steps.reason}
        walk = self.w.plan(steps, f"{self.plan_id}:undo")
        if isinstance(walk, Refusal):
            return {"status": "refused", "reason": walk.reason}
        # undo never auto-runs: level 2 floor, so a second person always approves it
        plans = [
            dataclasses.replace(sp_, min_tier=max(UNDO_MIN_TIER, sp_.min_tier))
            for sp_ in (
                step_plan(
                    p,
                    connection_id=self.conn,
                    db=self.db,
                    requested_by=s.login,
                    summary="Undo " + self.plan_id,
                    proofs=self.wiring.proofs,
                )
                for p in walk.steps
            )
        ]
        rows = [self.store.submit(p) for p in plans]
        return {"status": "requested", "walk": walk, "plans": plans, "rows": rows}

    def approve_undo(self, req: Mapping[str, Any], session: Any) -> list[wk.Done]:
        s = self.wiring.authority.verify(session, HUMAN)
        if req.get("status") != "requested":
            raise SpineError("refused", "no undo was requested")
        asked = {gd.norm(p.requested_by) for p in req.get("plans") or ()}
        if not asked or gd.norm(s.login) in asked:  # whatever the step status
            raise SpineError("forbidden", "the person who asked for the undo can't approve it")
        for r in req["rows"]:
            if r["status"] == "pending":
                try:
                    self.store.approve(self.conn, r["id"], s.login)
                except ap.ApprovalError as exc:
                    raise SpineError(exc.code, exc.message) from exc
            else:  # undo is never auto: an "auto" row means the floor was bypassed
                raise SpineError("refused", f"undo step is {r['status']}")
        got = [self.store.approval_for(self.db, p.hash()) for p in req["plans"]]
        if not got or any(g.level < 1 for g in got):
            raise SpineError("refused", "undo is not approved")
        ap_ = gd.Approval(min(g.level for g in got), s.login)
        return self.w.apply(req["walk"], dataclasses.replace(self.base, approval=ap_))


def _check_bot_user(read: Any, bot: Session) -> None:
    """The bot session's Odoo user must be the bot login: the sinkhole hold filters on
    create_uid and lockout simulates for this uid, so a wrong uid would hold nothing."""
    try:
        rows = read(
            "res.users",
            "search_read",
            [[("id", "=", bot.odoo_uid)]],
            {"fields": ["login"], "context": {"active_test": False}},
        )
    except Exception as exc:  # noqa: BLE001
        raise SpineError("bot-identity", "the bot's Odoo user could not be read") from exc
    if len(rows) != 1 or gd.norm(rows[0].get("login")) != gd.norm(bot.login):
        raise SpineError("bot-identity", "the bot session is not this database's bot user")


UNDO_MIN_TIER = 2


# ------------------------------------------------------------------ T3 (module code)
T3_RISK = "R8"


def _t3_plan(
    *,
    connection_id: str,
    db: str,
    task: str,
    subject: str,
    values: Mapping[str, Any],
    requested_by: str,
    summary: str,
    gate_ok: bool,
    snapshot_verified: bool,
) -> ap.Plan:
    return ap.Plan(
        connection_id=connection_id,
        db_fingerprint=db,
        task_id=task,
        model="ir.module.module",
        ids=[subject],
        values=dict(values),
        risk_class=T3_RISK,
        requested_by=requested_by,
        summary=summary[:200],
        irreversible=True,
        rehearsal_id=f"gate:{subject[:40]}",
        rehearsal_passed=gate_ok,
        undo_route="snapshot",
        snapshot_verified=snapshot_verified,
        min_tier=3,
    )


def authoring_plan(
    result: Any,
    gate_report: Any,
    *,
    connection_id: str,
    db: str,
    requested_by: str,
    snapshot_verified: bool,
) -> ap.Plan:
    f = result.approval_plan()
    mh, mod, ver = f.get("module_hash") or "", f.get("module") or "", f.get("version")
    if f.get("kind") != "module_authoring" or not mh or not mod or not f.get("promotable"):
        raise SpineError("refused", "this module did not pass authoring; nothing to approve")
    ok = mtg.gate_passed(gate_report, mh, version=ver, module=mod)
    vals = {"module": mod, "version": ver, "change_set_ids": sorted(f["change_set_ids"])}
    return _t3_plan(
        connection_id=connection_id,
        db=db,
        task=f"code:{mod}",
        subject=mh,
        values=vals,
        requested_by=requested_by,
        summary=f"Install new module {mod} (Odoo {ver})",
        gate_ok=ok,
        snapshot_verified=snapshot_verified,
    )


def change_set_plan(
    cs: oc.ChangeSet,
    gate_report: Any,
    module_hash: str,
    *,
    prior_hash: str,
    connection_id: str,
    db: str,
    requested_by: str,
    snapshot_verified: bool,
) -> ap.Plan:
    """An upgrade: module_hash is the patched module the gate ran, prior_hash the installed one."""
    if not isinstance(prior_hash, str) or len(prior_hash) != 64:
        raise SpineError("refused", "an upgrade needs the installed module's hash")
    f = cs.approval_plan()
    ok = mtg.gate_passed(
        gate_report, module_hash, version=cs.version, module=cs.module, prior_hash=prior_hash
    )
    vals = {
        "module": cs.module,
        "version": cs.version,
        "module_hash": module_hash,
        "prior_hash": prior_hash,
        "files": f["files"],
    }
    return _t3_plan(
        connection_id=connection_id,
        db=db,
        task=f"code:{cs.module}:change",
        subject=cs.id,
        values=vals,
        requested_by=requested_by,
        summary=f"Change module {cs.module}: {cs.reason}",
        gate_ok=ok,
        snapshot_verified=snapshot_verified,
    )


def _t3_ready() -> bool:
    return tr.tier_ready(tr.T3)  # read only: the switch is changed in reviewed code, never here


def apply_t3(
    store: ap.ApprovalStore,
    plan: ap.Plan,
    *,
    gate_report: Any,
    module_hash: str,
    change_set: oc.ChangeSet,
    approved_id: str,
    files: Mapping[str, bytes],
) -> dict[str, bytes]:
    """Every check, in order, before any write; the first failure refuses. Returns the patched
    files only; installing them is not part of this card."""
    if not isinstance(plan, ap.Plan) or plan.task_id.split(":")[0] != "code":
        raise SpineError("refused", "not a module-code approval item")
    if plan.min_tier != 3 or plan.risk_class != T3_RISK:
        raise SpineError("refused", "not a module-code approval item")
    ref = store.switch.check(plan.db_fingerprint)
    if ref is not None:
        raise SpineError("killed", ref.text())
    a = store.approval_for(plan.db_fingerprint, plan.hash())
    if a.level != 3 or not a.approver:
        raise SpineError("not-approved", "module code needs an approved top-level decision")
    v = plan.values
    ver, mod = v.get("version"), v.get("module")
    upgrade = plan.task_id.endswith(":change")
    want_hash = v.get("module_hash") if upgrade else plan.ids[0]
    prior = v.get("prior_hash") if upgrade else None
    if upgrade and not (isinstance(prior, str) and len(prior) == 64):
        raise SpineError("gate", "upgrade item carries no installed-module hash")
    if module_hash != want_hash:
        raise SpineError("gate", "module differs from the one approved")
    if not mtg.gate_passed(gate_report, module_hash, version=ver, module=mod, prior_hash=prior):
        raise SpineError("gate", "no passing, signed test-gate report for this exact module")
    if upgrade and mtg.module_hash(files) != prior:
        raise SpineError("gate", "installed module differs from the one the gate upgraded")
    ids = [plan.ids[0]] if upgrade else list(v.get("change_set_ids") or [])
    if approved_id not in ids or not isinstance(change_set, oc.ChangeSet):
        raise SpineError("not-approved", "this change set was not approved")
    if change_set.id != approved_id or change_set.module != mod or change_set.version != ver:
        raise SpineError("not-approved", "change set differs from the approved one")
    if upgrade and list(v.get("files") or ()) != change_set.approval_plan()["files"]:
        raise SpineError("not-approved", "change set touches other files than the approved list")
    try:
        out = oc.apply_change_set(files, change_set, approved_id=approved_id)  # pure, no write
    except oc.ChangeError as exc:
        raise SpineError("refused", str(exc)[:160]) from exc
    if mtg.module_hash(out) != module_hash:
        raise SpineError("gate", "result differs from the module the gate tested")
    if not _t3_ready():
        raise SpineError("t3-off", "module-code changes are switched off in this release")
    return out


def t3_before_install(store: ap.ApprovalStore, plan: ap.Plan) -> None:
    """Call immediately before installing what ``apply_t3`` returned. ``apply_t3`` checks the
    kill switch only at its start; a switch thrown since then must still stop the write.
    Install is not wired in this release; whoever wires it calls this right before the write
    (a test fails if an install call appears in this module without it)."""
    ref = store.switch.check(plan.db_fingerprint)
    if ref is not None:
        raise SpineError("killed", ref.text())
    if not _t3_ready():
        raise SpineError("t3-off", "module-code changes are switched off in this release")
