"""Generic record-change walker (BOT-GENERIC-WALKER): any model, no per-task handler.

``Walker.plan(steps)`` checks every step against live metadata (``fields_get`` / ``ir.model``,
Odoo 17-20) and the existing machinery: field and value validation, catalogue class
(``classifier.classify``: unknown model or button = refused), named irrecoverable states,
blast / diff / recompute (``blast.preview``), a dry ``onchange``, DB constraints, outbound
(``Sinkhole.scan``), lockout where the risk layer asks for it. ``Walker.apply`` runs each step
only through ``WriteGate`` (writes: ``run`` + ``before_image.RouteA``; create / unlink / button:
``call``), over ``Sinkhole.quiet``. A per-step ledger plus the gate's audit claim make a
re-run after a crash safe: a done step is replayed from the ledger, a half-done one is
reconciled from live state or refused for a person. ``Walker.undo_plan`` builds the inverse
steps (create -> unlink, write -> restore) and they go through the same plan + apply path.
Everything unreadable, unknown or unsupported refuses (fail closed).
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.bots import access as ac
from app.bots import before_image as bi
from app.bots import blast as bl
from app.bots import diff as df
from app.bots import guard as gd
from app.bots import lockout as lk
from app.bots import sinkhole as sh
from app.bots.risk import classifier as cl
from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal

RF, MISS = "RF-ANY", "generic-walker"
KINDS = ("create", "write", "unlink", "call")
VERB = {"create": "create", "write": "change", "unlink": "delete"}
META = [
    "type",
    "string",
    "required",
    "readonly",
    "store",
    "selection",
    "relation",
    "translate",
    "company_dependent",
    "related",
    "depends",
]
X2M = ("one2many", "many2many")
BINARY_CAP = 10 * 2**20
INT4 = (-(2**31), 2**31 - 1)
DRY_METHODS = frozenset({"default_get", "onchange"})  # computed in memory, never stored
RA = {"context": {"active_test": False}}

# Access writes refused in the walker itself (defence in depth over lockout's handlers).
ACCESS_FIELDS = frozenset({("ir.ui.menu", "groups_id"), ("ir.ui.menu", "group_ids")})

# Reviewed, append-only: models the walker never changes, with the reason shown to the owner.
REFUSED_MODELS: dict[str, str] = {
    "mail.mail": "outgoing email: sending is a send flow behind the sinkhole, not a record edit",
    "mail.message": "message history: posted messages are the audit trail",
    "mail.notification": "delivery records of sent messages",
    "sms.sms": "outgoing SMS: leaves Odoo as soon as it is queued",
    "ir.config_parameter": "system parameters: auth, URLs and ingenium keys, reviewed per key",
    "res.users": "users and their access: use the access layer (app.bots.access)",
    "res.groups": "groups: use the access layer (app.bots.access)",
    "ir.model.access": "access rows: use the access layer (app.bots.access)",
    "ir.rule": "record rules: use the access layer (app.bots.access)",
    "ir.access": "Odoo 20 access rows: use the access layer (app.bots.access)",
    "res.users.apikeys": "API keys are credentials",
    "ir.cron": "scheduled jobs run code as the system user",
    "ir.actions.server": "server actions run code",
    "base.automation": "automation rules run code on other people's changes",
    "ir.module.module": "modules: install / uninstall is a module task, not a record edit",
    "ir.model": "data model definition",
    "ir.model.fields": "data model definition",
    "ir.ui.view": "views: a broken view locks users out of screens",
    "ir.mail_server": "outgoing mail servers",
    "ir.sequence": "document numbering: gaps and duplicates are legal problems",
    "res.company": "company settings (lock dates, fiscal country)",
    "payment.provider": "payment provider credentials",
}

# Reviewed, append-only: record states after which nothing can be undone by an edit.
# model -> (field, states, reason). Anything in these states: write / unlink / call refused.
IRRECOVERABLE: dict[str, tuple[str, frozenset[str], str]] = {
    "account.move": (
        "state",
        frozenset({"posted", "cancel"}),
        "posted or cancelled journal entry: only a reversal or credit note can undo it",
    ),
    "account.payment": (
        "state",
        frozenset({"posted", "paid", "in_process", "reconciled", "canceled", "cancel"}),
        "posted payment: undo needs a reversal, not an edit",
    ),
    "stock.picking": (
        "state",
        frozenset({"done", "cancel"}),
        "validated transfer: stock moves and valuation are final",
    ),
    "stock.move": ("state", frozenset({"done", "cancel"}), "done stock move: quantities are final"),
    "stock.move.line": ("state", frozenset({"done", "cancel"}), "done stock move line"),
    "mrp.production": ("state", frozenset({"done", "cancel"}), "finished manufacturing order"),
    "pos.order": ("state", frozenset({"paid", "done", "invoiced"}), "paid point-of-sale order"),
    "sale.order": ("locked", frozenset({"True"}), "locked sales order"),
    "purchase.order": (
        "state",
        frozenset({"done", "cancel"}),
        "locked or cancelled purchase order",
    ),
}
LOCK_DATES = (
    "fiscalyear_lock_date",
    "period_lock_date",
    "tax_lock_date",
    "sale_lock_date",
    "purchase_lock_date",
    "hard_lock_date",
)
EDI = re.compile(r"(edi|einvoice|e_invoice|peppol|cfdi|sii|fe_)\w*(state|status)$")
EDI_OPEN = frozenset({"", "to_send", "draft", "new", "pending_send", "False"})


class Refused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.refusal = Refusal(RF, MISS, reason[:300])


def _no(reason: str) -> Refused:
    return Refused(reason)


# ---------------------------------------------------------------- data
@dataclass(frozen=True)
class Step:
    kind: str  # create | write | unlink | call
    model: str
    ids: tuple[int, ...] = ()
    values: Mapping[str, Any] = field(default_factory=dict)
    method: str = ""  # call only


@dataclass
class Planned:
    step: Step
    task_id: str
    cls: str
    sub: str | None
    tier: int
    reasons: list[str]
    lines: list[str]
    before: dict[int, dict] | None  # write: stored values of the planned fields, per id
    preview_hash: str
    undo: str  # how this step is undone, or why it cannot be
    key: str = ""
    scan: Any = None


@dataclass
class Walk:
    plan_id: str
    steps: list[Planned]

    @property
    def tier(self) -> int:
        return max(p.tier for p in self.steps)


@dataclass
class Done:
    status: str  # done | refused | tripped | mismatch | needs-human
    step: Planned
    record_ids: tuple[int, ...] = ()
    after: dict[int, dict] | None = None
    refusal: Refusal | None = None
    replayed: bool = False


class Ledger:
    """Per-step results on disk (atomic replace). Key = sha256(db, plan, index, step)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, dict]:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, key: str) -> dict | None:
        return self.load().get(key)

    def put(self, key: str, rec: dict) -> None:
        d = self.load()
        d[key] = rec
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w") as fh:
            json.dump(d, fh, sort_keys=True, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)


# ---------------------------------------------------------------- walker
class Walker:
    def __init__(
        self,
        rpc: Any,
        switch: gd.KillSwitch,
        audit: Any,
        rehearsals: Any,
        store: bi.ImageStore,
        ledger: Ledger,
        *,
        db: str,
        bot_uid: int,
        version: int,
        route: rr.Route = "A",
        reviewed: Mapping[str, str] | None = None,
    ) -> None:
        if version not in rr.SUPPORTED_VERSIONS:
            raise _no(f"Odoo {version} outside 17-20")
        self.rpc, self.read = rpc, df.ReadOnly(rpc)
        self._held: list = []  # per-step approvals stay alive for the grant source
        self.db, self.bot, self.version, self.route = db, int(bot_uid), version, route
        self.sink = sh.Sinkhole(rpc, switch, db, bot_uid)
        self.quiet = self.sink.quiet(rpc)
        self._nest: list[tuple[str, dict]] = []
        self.gate = gd.WriteGate(switch, audit, self.quiet, rehearsals)
        self.store, self.ledger = store, ledger
        bad = [m for m in (reviewed or {}) if not m.startswith("x_")]
        if bad:
            raise _no(f"only custom x_ models can be reviewed here: {bad}")
        self.reviewed = dict(reviewed or {})
        self._meta: dict[str, dict] = {}
        self._checked = False

    # ---------- metadata
    def _version_check(self) -> None:
        if self._checked:
            return
        vm = ac.detect(self.read)
        want = "20" if self.version >= 20 else "19" if self.version == 19 else "17-18"
        if vm.key != want:
            raise _no(f"server looks like Odoo {vm.key}, plan says {self.version}: not walked")
        self._checked = True

    def meta(self, model: str) -> dict[str, dict]:
        if model not in self._meta:
            if not self.read("ir.model", "search_count", [[("model", "=", model)]], RA):
                raise _no(f"model {model} is not installed")
            m = self.read(model, "fields_get", [[]], {"attributes": META})
            if not isinstance(m, dict) or not m:
                raise _no(f"{model} metadata unreadable")
            self._meta[model] = m
        return self._meta[model]

    def _dry(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        if method not in DRY_METHODS:
            raise _no(f"{method} is not a dry method")
        return self.rpc(model, method, args, kw or {})

    def _exist(self, model: str, ids: Sequence[int]) -> None:
        ids = sorted(set(ids))
        if any(not isinstance(i, int) or isinstance(i, bool) or i < 1 for i in ids):
            raise _no(f"{model}: ids must be positive integers")
        n = self.read(model, "search_count", [[("id", "in", ids)]], RA)
        if n != len(ids):
            raise _no(f"{model}: {len(ids) - n} of {ids[:5]} do not exist")

    def _model_ok(self, model: str) -> None:
        """Model-level refusal, applied to steps, nested lines, x2many targets and references."""
        if model in REFUSED_MODELS:
            raise _no(f"{model}: {REFUSED_MODELS[model]}")
        if model.startswith("x_") and model not in self.reviewed:
            raise _no(f"{model} is a custom model nobody has reviewed: needs a person")

    # ---------- (a) field and value validation
    def check_values(
        self, model: str, values: Mapping[str, Any], kind: str, depth: int = 0, inverse: str = ""
    ) -> tuple[list[str], int]:
        """Returns (reasons, nested creates). Raises Refused on the first bad field."""
        meta, why, nested = self.meta(model), [], 0
        if not isinstance(values, Mapping):
            raise _no("values must be a dict")
        for f, v in values.items():
            m = meta.get(f)
            if m is None:
                raise _no(f"{model}.{f} does not exist on this Odoo")
            if f in rr.MAGIC_FIELDS:
                raise _no(f"{model}.{f} is managed by Odoo")
            if m.get("store") is False:
                raise _no(f"{model}.{f} is computed and not stored: set what it is computed from")
            if m.get("related"):
                raise _no(f"{model}.{f} is related to another record: change that record instead")
            if m.get("readonly") is True:
                raise _no(f"{model}.{f} is read-only")
            if m.get("relation") == "res.groups" or (model, f) in ACCESS_FIELDS:
                raise _no(f"{model}.{f} grants access: use the access layer (app.bots.access)")
            if df.secret(model, f, v):
                raise _no(f"{model}.{f} looks like a credential")
            nested += self._value(model, f, m, v, kind, depth)
            if m.get("translate"):
                why.append(f"{f} is translated: only the current language is written")
            if m.get("company_dependent"):
                why.append(f"{f} is company-dependent: set for the current company only")
            if m.get("depends") and m.get("readonly") is False:
                why.append(f"{f} is computed with an inverse: Odoo writes its source fields")
        if kind == "create":
            req = sorted(
                f
                for f, m in meta.items()
                if m.get("required")
                and f not in values
                and f != inverse  # a line's parent link is set by its parent's create
                and m.get("store", True)
                and not m.get("related")
            )
            if req:
                dflt = self._dry(model, "default_get", [req])
                miss = [f for f in req if f not in (dflt or {})]
                if miss:
                    raise _no(f"{model}: required field(s) missing and no default: {miss}")
        return why, nested

    def _value(self, model: str, f: str, m: dict, v: Any, kind: str, depth: int) -> int:
        t, name = m.get("type"), f"{model}.{f}"
        if v is False or v is None:
            if m.get("required") and t not in ("boolean",) + X2M:
                raise _no(f"{name} is required")
            return 0
        if t in ("char", "text", "html"):
            ok = isinstance(v, str)
        elif t == "boolean":
            ok = isinstance(v, bool)
        elif t == "integer":
            ok = isinstance(v, int) and not isinstance(v, bool) and INT4[0] <= v <= INT4[1]
        elif t in ("float", "monetary"):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
        elif t in ("date", "datetime"):
            fmt = "%Y-%m-%d" if t == "date" else "%Y-%m-%d %H:%M:%S"
            try:
                ok = isinstance(v, str) and bool(datetime.strptime(v, fmt))
            except ValueError:
                ok = False
        elif t == "selection":
            sel = m.get("selection")
            if not isinstance(sel, list):
                raise _no(f"{name}: selection values unreadable")
            ok = v in {k for k, _ in sel}
        elif t == "many2one":
            ok = isinstance(v, int) and not isinstance(v, bool)
            if ok:
                self._exist(m["relation"], [v])
        elif t == "binary":
            ok = isinstance(v, str) and len(v) <= BINARY_CAP * 4 // 3 + 4
            try:
                ok = ok and bool(base64.b64decode(v, validate=True) or True)
            except (binascii.Error, ValueError):
                ok = False
        elif t == "reference":
            mod, _, rid = str(v).partition(",")
            ok = rid.isdigit()
            if ok:
                self._model_ok(mod)
                self._exist(mod, [int(rid)])
        elif t in X2M:
            return self._x2m(model, f, m, v, kind, depth)
        else:
            raise _no(f"{name}: type {t} is not supported by the walker")
        if not ok:
            raise _no(f"{name}: {type(v).__name__} value does not fit a {t} field")
        return 0

    def _x2m(self, model: str, f: str, m: dict, v: Any, kind: str, depth: int) -> int:
        name, rel, nested = f"{model}.{f}", m["relation"], 0
        if not isinstance(v, list) or not all(isinstance(c, (list, tuple)) and c for c in v):
            raise _no(f"{name}: x2many values must be a list of commands")
        for c in v:
            op = c[0]
            if op == 0 and m["type"] == "one2many" and kind == "create" and depth == 0:
                if len(c) != 3 or not isinstance(c[2], Mapping):
                    raise _no(f"{name}: bad create command")
                self._model_ok(rel)  # a nested line never creates a refused model
                if m.get("relation_field") in c[2]:
                    raise _no(f"{name}: a line cannot name its own parent")
                self.check_values(rel, c[2], "create", depth + 1, m.get("relation_field") or "")
                self._nest.append((rel, dict(c[2])))
                nested += 1
            elif op == 6 and m["type"] == "many2many" and len(c) == 3:
                self._exist(rel, list(c[2]))
            else:
                raise _no(
                    f"{name}: command {op} not allowed here (lines are created with their parent "
                    "or changed as their own records; deletes are unlink steps)"
                )
        return nested

    # ---------- (d) irrecoverable states
    def irrecoverable(self, model: str, ids: Sequence[int], values: Mapping[str, Any]) -> list[str]:
        meta, why = self.meta(model), []
        spec = IRRECOVERABLE.get(model)
        edi = [f for f in meta if EDI.search(f)]
        locks = model == "account.move" and "date" in meta and "company_id" in meta
        want = ([spec[0]] if spec and spec[0] in meta else []) + edi
        want += ["date", "company_id"] if locks else []
        want += ["is_move_sent"] if model == "account.move" and "is_move_sent" in meta else []
        if spec and spec[0] in values and str(values[spec[0]]) in spec[1]:
            raise _no(f"{model}: setting {spec[0]}={values[spec[0]]!r}: {spec[2]}")
        if not ids or not want:
            return why
        rows = self.read(model, "read", [list(ids), sorted(set(want))], RA)
        if len(rows) != len(set(ids)):
            raise _no(f"{model}: records unreadable")
        cmeta = self.meta("res.company") if locks else {}
        lock_f = [f for f in LOCK_DATES if f in cmeta]
        for r in rows:
            if spec and spec[0] in r and str(r[spec[0]]) in spec[1]:
                raise _no(f"{model} #{r['id']}: {spec[2]}")
            for f in edi:
                if str(r.get(f) or "") not in EDI_OPEN:
                    raise _no(
                        f"{model} #{r['id']}: e-invoice {f}={r[f]!r}: sent documents are final"
                    )
            if r.get("is_move_sent"):
                why.append(f"{model} #{r['id']} was already sent to the customer")
            if locks and lock_f and r.get("date"):
                cid = r["company_id"][0] if isinstance(r["company_id"], list) else r["company_id"]
                c = self.read("res.company", "read", [[cid], lock_f], RA)[0]
                hit = [f for f in lock_f if c.get(f) and str(r["date"]) <= str(c[f])]
                if hit:
                    raise _no(f"{model} #{r['id']} dated {r['date']} is in a locked period ({hit})")
        return why

    # ---------- plan
    def plan(self, steps: Sequence[Step], plan_id: str) -> Walk | Refusal:
        try:
            self._version_check()
            if not steps:
                raise _no("empty plan")
            out = [self._plan1(s) for s in steps]
        except Refused as exc:
            return exc.refusal
        except cl.RiskAuditUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - unreadable = refuse
            return Refusal(RF, MISS, f"metadata unreadable: {type(exc).__name__}: {exc}"[:200])
        for i, p in enumerate(out):
            p.key = hashlib.sha256(
                json.dumps(
                    [self.db, plan_id, i, dataclasses.asdict(p.step)], sort_keys=True, default=str
                ).encode()
            ).hexdigest()[:40]
        return Walk(plan_id, out)

    def _plan1(self, s: Step) -> Planned:
        if s.kind not in KINDS:
            raise _no(f"unknown step kind {s.kind!r}")
        self._model_ok(s.model)
        self._nest = []
        meta = self.meta(s.model)
        vals = dict(s.values)
        ids = tuple(s.ids)
        if s.kind == "create" and ids or s.kind != "create" and not ids:
            raise _no(f"{s.kind} step has the wrong ids")
        if s.kind in ("unlink", "call") and vals:
            raise _no(f"{s.kind} steps carry no values")
        if s.kind == "write" and not vals or s.kind == "create" and not vals:
            raise _no(f"{s.kind} step needs values")
        if s.kind == "call" and not re.fullmatch(r"(action|button)_[a-z0-9_]+", s.method or ""):
            raise _no(f"only button_* / action_* methods can be called, not {s.method!r}")
        if ids:
            self._exist(s.model, ids)
        why, nested = self.check_values(s.model, vals, s.kind) if vals else ([], 0)
        why += self.irrecoverable(s.model, ids if s.kind != "create" else (), vals)
        task = f"b:{s.model}:{s.method}" if s.kind == "call" else f"m:{s.model}:{VERB[s.kind]}"
        fields = frozenset(vals) if s.kind == "write" else None
        if s.model in self.reviewed:
            cls, sub, tier = "R8", "reviewed-custom", 3
            why.append(f"custom model reviewed ({self.reviewed[s.model]}): no catalogue row, L3")
        else:
            d = cl.classify(
                task,
                cl.ClassifyCtx(
                    self.version, self.route, db_name=self.db, port=_Port(self.read), fields=fields
                ),
            )
            if isinstance(d, Refusal):
                raise _no(f"{task}: {d.reason}")
            cls, sub, tier = d.cls, d.subkind, d.tier
            if d.mitigation_refusal:
                raise _no(f"{task}: {d.mitigation_refusal}")
            if s.kind == "call" and task in _irreversible():
                tier = 3
                why.append(f"catalogue marks {s.method} irreversible")
        lines: list[str] = []
        before = None
        if s.kind in ("write", "unlink"):
            pv = bl.preview(
                self.read,
                s.model,
                ids,
                vals or None,
                op=s.kind,
                cls=cls,
                subkind=sub,
                route=self.route,
            )
            if isinstance(pv, Refusal):
                raise _no(pv.reason)
            tier = max(tier, pv.tier.tier)
            phash = pv.payload_hash
            if pv.diff:
                lines += [
                    f"{e['model']} #{e['id']} {e['field']}: {e['old']!r} -> {e['new']!r}"
                    for e in pv.diff["entries"][:50]
                ]
                why += [f"recomputes {r}" for r in pv.diff["recompute"][:10]]
                if not pv.diff["entries"]:
                    raise _no("nothing would change")
            if s.kind == "unlink":
                lines.append(f"deletes {pv.blast['per_model']}, clears {pv.blast['nulled']}")
                why += list(pv.blast["low_count"])
            if s.kind == "write":
                before = self._snap(s.model, ids, sorted(vals))
        else:
            t = rr.plan_tier(cls, sub, self.route, rr.DEFAULT_POLICY, max(1, len(ids)) + nested)
            if isinstance(t, Refusal):
                raise _no(t.reason)
            tier = max(tier, t.tier)
            phash = df.canonical_hash({"step": dataclasses.asdict(s)})
            lines.append(
                f"{s.kind} {s.model} {s.method or ''} {ids or ''}".strip()
                + (f" with {nested} line(s)" if nested else "")
            )
        if s.kind in ("create", "write"):
            why += self._onchange(s.model, ids, vals, meta)
            n = self.read(
                "ir.model.constraint",
                "search_count",
                [[("model.model", "=", s.model), ("type", "=", "u")]],
                {},
            )
            why.append(
                f"{n} database constraint(s) + Python constraints run at write; "
                "a violation writes nothing"
            )
        changes = []
        if lk.needs_simulation(s.model, fields, VERB.get(s.kind)):
            changes.append(lk.Change(s.model, s.kind if s.kind != "call" else "write", ids, vals))
        # nested lines exist on creates only, so s.kind is "create" here
        for nm, nv in self._nest:  # each nested line gets its own lockout check and R8 floor
            if lk.needs_simulation(nm, frozenset(nv), "create"):
                changes.append(lk.Change(nm, s.kind, (), nv))
                tier = 3
                why.append(f"creates {nm} lines: lockout-sensitive, L3")
        if changes:
            sim = lk.simulate(self.read, changes, bot_uid=self.bot)
            if isinstance(sim, Refusal):
                raise _no(sim.reason)
            tier = max(tier, sim.tier)
            lines += sim.card_lines()
        # buttons are scanned as writes on their model and always run inside a proven hold
        scan = self.sink.scan(s.model, "write" if s.kind == "call" else s.kind, vals, list(ids))
        if scan.verdict == "refuse":
            raise _no(scan.refusal.reason if scan.refusal else "outbound scan refused")
        tier = max(tier, scan.need_tier)
        lines.append(scan.text())
        if s.kind == "call":
            tier = 3
            why.append("button: Odoo runs its own logic; no automatic undo, L3")
            lines.append("any email or SMS the button queues is held; if the hold fails it stops")
        if s.kind == "unlink":
            tier = 3
            why.append("delete: no automatic undo (records come back with new ids), L3")
        if any(w.startswith("onchange preview unavailable") for w in why):
            tier = 3
        undo = {
            "create": "delete the created record(s)",
            "write": "write the before-values back",
            "unlink": "none: needs a snapshot restore",
            "call": "none: button effects are Odoo's",
        }[s.kind]
        return Planned(
            s, task, cls, sub, tier, sorted(set(why)), lines, before, phash, undo, scan=scan
        )

    def _snap(self, model: str, ids: Sequence[int], fields: list[str]) -> dict[int, dict]:
        meta = self.meta(model)
        rows = self.read(model, "read", [list(ids), fields], RA)
        out = {}
        for r in rows:
            out[r["id"]] = {f: _plain(meta[f]["type"], r.get(f)) for f in fields}
        if set(out) != set(ids):
            raise _no(f"{model}: records unreadable")
        return out

    def _onchange(
        self, model: str, ids: Sequence[int], vals: Mapping[str, Any], meta: dict
    ) -> list[str]:
        if len(ids) > 1:
            return [
                "onchange not previewed for multi-record writes (Odoo runs none over RPC either)"
            ]
        spec = {f: {} for f, m in meta.items() if m.get("store", True) and m.get("type") not in X2M}
        try:
            res = self._dry(model, "onchange", [list(ids), dict(vals), sorted(vals), spec])
        except Exception as exc:  # noqa: BLE001 - shown, and floors the tier to L3
            return [f"onchange preview unavailable ({type(exc).__name__}): side effects unverified"]
        got = (res or {}).get("value") or {}
        extra = sorted(f for f in got if f not in vals)
        return [f"the form would also set {extra[:10]} (not applied over RPC)"] if extra else []

    # ---------- apply
    def apply(self, walk: Walk, spec: gd.RunSpec) -> list[Done]:
        """Runs the steps in order; stops at the first one that is not done."""
        out: list[Done] = []
        for p in walk.steps:
            d = self._apply1(p, spec)
            out.append(d)
            if d.status != "done":
                break
        return out

    def _apply1(self, p: Planned, spec: gd.RunSpec) -> Done:
        rec = self.ledger.get(p.key)
        if rec and rec["status"] == "done":
            return Done("done", p, tuple(rec["ids"]), _ikeys(rec.get("after")), replayed=True)
        if spec.approval.level < p.tier:
            return Done("refused", p, refusal=Refusal(RF, MISS, f"needs L{p.tier} approval"))
        # a fresh copy per step: grants are single-use and bound to this step's plan hash
        ap = dataclasses.replace(spec.approval)
        self._held.append(ap)
        s = dataclasses.replace(
            spec, task_id=p.task_id, risk_class=p.cls, idempotency_key=p.key, approval=ap
        )
        st = p.step
        try:
            if rec:  # crashed mid-step: reconcile from live state, never re-apply blind
                return self._reconcile(p, rec)
            if st.kind == "write" and self._snap(st.model, st.ids, sorted(st.values)) != p.before:
                raise _no("changed since the preview: plan again")
            if st.kind in ("unlink", "call") or st.kind == "write":
                self.irrecoverable(st.model, st.ids, st.values)
            top = self._top(st.model)
            self.ledger.put(p.key, {"status": "started", "top": top, "ids": list(st.ids)})
            opened = self._open(p, spec.approval.level)
            try:
                d = self._exec(p, s)
            finally:
                if opened:
                    self.sink.close()
        except Refused as exc:
            return Done("refused", p, refusal=exc.refusal)
        except PermissionError as exc:
            return Done("refused", p, refusal=Refusal(RF, MISS, str(exc)[:200]))
        if d.status == "done":
            self.ledger.put(p.key, {"status": "done", "ids": list(d.record_ids), "after": d.after})
        return d

    def _open(self, p: Planned, level: int) -> bool:
        if p.scan is None or not p.scan.channels and p.step.kind != "call":
            return False
        ref = self.sink.open(p.scan, level)
        if ref is not None:
            raise _no(ref.reason)
        return True

    def _top(self, model: str) -> int:
        r = self.read(
            model, "search_read", [[]], {**RA, "fields": ["id"], "order": "id desc", "limit": 1}
        )
        return r[0]["id"] if r else 0

    def _exec(self, p: Planned, s: gd.RunSpec) -> Done:
        st = p.step
        if st.kind == "create":
            new = self.gate.call(s, st.model, "create", [dict(st.values)])
            if new is None:
                raise _no("the gate saw this step already: reconcile needed")
            ids = tuple(new if isinstance(new, list) else [new])
            return Done("done", p, ids, self._snap(st.model, ids, sorted(st.values)))
        if st.kind in ("unlink", "call"):
            meth = "unlink" if st.kind == "unlink" else st.method
            self.gate.call(s, st.model, meth, [list(st.ids)])
            if st.kind == "call" and not self.sink.after_batch():
                raise _no("button effects could not be proven held: stopped (kill switch on)")
            if st.kind == "unlink":
                left = self.read(st.model, "search_count", [[("id", "in", list(st.ids))]], RA)
                return Done("done" if not left else "mismatch", p, st.ids)
            return Done("done", p, st.ids)
        ra = bi.RouteA(
            self.read,
            self.quiet,
            self.store,
            plan=gd.plan_hash(s.db_fingerprint, s.task_id, st.model, dict(st.values), list(st.ids)),
            model=st.model,
            ids=list(st.ids),
            values=dict(st.values),
            switch_check=lambda: self.gate.switch.check(s.db_fingerprint),
            approval=s.approval.level,
        )
        hooks = ra.hooks()
        if p.scan is not None and p.scan.channels:
            inner = hooks["readback"]  # both must pass: the plan's proof and the sinkhole hold
            hooks["readback"] = lambda chunk: bool(inner(chunk)) and self.sink.after_batch()
        rep = self.gate.run(s, st.model, list(st.ids), dict(st.values), **hooks)
        self.last_log = list(ra.log)
        if rep.status != "done":
            return Done(rep.status, p, st.ids, refusal=rep.refusal)
        after = self._snap(st.model, st.ids, sorted(st.values))
        want = {
            i: {
                f: _plain(self.meta(st.model)[f]["type"], v, new=True) for f, v in st.values.items()
            }
            for i in st.ids
        }
        return Done("done" if _sub(want, after) else "mismatch", p, st.ids, after)

    def _reconcile(self, p: Planned, rec: dict) -> Done:
        st = p.step
        if st.kind == "create":
            simple = {f: v for f, v in st.values.items() if not isinstance(v, (list, dict))}
            dom = [("id", ">", rec["top"]), ("create_uid", "=", self.bot)]
            dom += [(f, "=", v) for f, v in simple.items()]
            got = self.read(st.model, "search", [dom], RA)
            if len(got) == 1:
                d = Done("done", p, (got[0],), self._snap(st.model, got, sorted(st.values)))
                self.ledger.put(p.key, {"status": "done", "ids": [got[0]], "after": d.after})
                return d
            if got:
                return Done(
                    "needs-human",
                    p,
                    tuple(got),
                    refusal=Refusal(RF, MISS, f"crash recovery found {len(got)} candidates"),
                )
            raise _no("crash recovery: create not visible; the gate holds the key: needs a person")
        if st.kind == "write":
            now = self._snap(st.model, st.ids, sorted(st.values))
            want = {
                i: {
                    f: _plain(self.meta(st.model)[f]["type"], v, new=True)
                    for f, v in st.values.items()
                }
                for i in st.ids
            }
            if _sub(want, now):
                self.ledger.put(p.key, {"status": "done", "ids": list(st.ids), "after": now})
                return Done("done", p, st.ids, now)
        if st.kind == "unlink":
            if not self.read(st.model, "search_count", [[("id", "in", list(st.ids))]], RA):
                self.ledger.put(p.key, {"status": "done", "ids": list(st.ids), "after": None})
                return Done("done", p, st.ids)
        return Done(
            "needs-human",
            p,
            st.ids,
            refusal=Refusal(
                RF, MISS, "crashed mid-step and live state is in between: needs a person"
            ),
        )

    # ---------- undo
    def undo_steps(self, done: Sequence[Done]) -> list[Step] | Refusal:
        """Inverse steps, newest first. Plan and apply them like any plan (same checks)."""
        out: list[Step] = []
        for d in reversed(done):
            st = d.step.step
            if d.status != "done":
                continue
            if st.kind == "create":
                out.append(Step("unlink", st.model, tuple(d.record_ids)))
            elif st.kind == "write":
                now = self._snap(st.model, st.ids, sorted(st.values))
                if now != d.after:
                    return Refusal(
                        RF, MISS, f"{st.model} {st.ids} changed since it was applied: undo refused"
                    )
                for i, vals in (d.step.before or {}).items():
                    out.append(
                        Step("write", st.model, (int(i),), _as_values(self.meta(st.model), vals))
                    )
            else:
                return Refusal(RF, MISS, f"{st.kind} on {st.model} has no automatic undo")
        return out


# ---------------------------------------------------------------- helpers
class _Port:
    """buttons.RpcPort over the read-only wrapper (classifier's live lookups)."""

    def __init__(self, read: df.ReadOnly) -> None:
        self.read = read

    def call(self, model: str, method: str, args: Any = (), kwargs: dict | None = None) -> Any:
        return self.read(model, method, list(args), kwargs or {})


def _irreversible() -> frozenset[str]:
    return _IRR or _load_irr()


_IRR: frozenset[str] = frozenset()


def _load_irr() -> frozenset[str]:
    global _IRR
    _IRR = frozenset(json.loads(cl.ROWS_FILE.read_text())["irreversible"])
    return _IRR


def _plain(t: str, v: Any, new: bool = False) -> Any:
    """One comparable shape for read values and planned values."""
    if t == "many2one":
        return (v[0] if isinstance(v, (list, tuple)) else v) or False
    if t in X2M:
        if new:  # planned commands -> resulting id set is unknown for 4/3; keep (6) only
            sixes = [c for c in v or [] if c and c[0] == 6]
            return sorted(sixes[-1][2]) if sixes else None
        return sorted(v or [])
    if t in ("float", "monetary") and isinstance(v, (int, float)) and not isinstance(v, bool):
        return round(float(v), 6)
    return v if v is not None else False


def _sub(want: dict[int, dict], got: dict[int, dict]) -> bool:
    return all(
        w is None or got.get(i, {}).get(f) == w for i, vals in want.items() for f, w in vals.items()
    )


def _ikeys(d: Any) -> Any:
    return {int(k): v for k, v in d.items()} if isinstance(d, dict) else d


def _as_values(meta: dict, vals: Mapping[str, Any]) -> dict[str, Any]:
    return {f: [(6, 0, list(v))] if meta[f]["type"] == "many2many" else v for f, v in vals.items()}
