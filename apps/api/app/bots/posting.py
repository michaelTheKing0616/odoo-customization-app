"""Guarded posting / validation of accounting and stock documents (BOT-R4-POSTING).

Posting is hard to reverse, so every op here is L3, bound to the approved plan's exact
record count, previewed (ledger lines / stock moves / quant deltas), run as a ``Walker``
call step (``WriteGate`` + proven ``Sinkhole`` hold), checked after the fact, and undone
only by Odoo's counter-documents: credit note / reversal, payment reset+cancel, return
transfer, counter inventory adjustment. Never an unlink. A lock date on or after the
document or undo date, a sent / e-invoiced / reconciled document, lot or serial tracking,
partial quantities (backorder wizard), unknown versions or unreadable data: refused.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.bots import guard as gd
from app.bots import sinkhole as sh
from app.bots import walker as wk
from app.bots.risk.rules import Refusal

RF, MISS = "RF-R4", "posting"
RA = wk.RA
DEFER = ("deferred_start_date", "deferred_end_date")
CHAIN = ("move_dest_ids", "move_orig_ids", "procure_method", "created_production_id")
CAP_LINES = 60
SCAN_AS = "write"  # Sinkhole.scan kind for the undo (a scan, not an RPC write)


@dataclass(frozen=True)
class Op:
    model: str
    method: str
    pre: Callable[[int, dict], bool]  # record may be posted by this op
    post: Callable[[int, dict], bool]  # op took effect
    fields: tuple[str, ...]
    counter: str


def _st(*s: str) -> Callable[[int, dict], bool]:
    return lambda v, r: r.get("state") in s


def _pay_done(v: int, r: dict) -> bool:  # 17: posted; 18+: in_process / paid
    return r.get("state") in (("posted",) if v < 18 else ("in_process", "paid"))


OPS: dict[str, Op] = {
    "move_post": Op(
        "account.move",
        "action_post",
        _st("draft"),
        _st("posted"),
        ("state", "date", "company_id", "journal_id", "move_type", "name"),
        "credit note / reversal entry (account.move.reversal), posted; never a delete",
    ),
    "payment_post": Op(
        "account.payment",
        "action_post",
        _st("draft"),
        _pay_done,
        ("state", "date", "company_id", "journal_id", "amount", "payment_type", "partner_id"),
        "reset to draft and cancel (Odoo's payment undo); refused once matched or reconciled",
    ),
    "picking_validate": Op(
        "stock.picking",
        "button_validate",
        _st("assigned", "confirmed"),
        _st("done"),
        ("state", "company_id", "name", "picking_type_id"),
        "return transfer (stock.return.picking), validated; never a delete",
    ),
    "inventory_apply": Op(
        "stock.quant",
        "action_apply_inventory",
        lambda v, r: bool(r.get("inventory_quantity_set")),
        lambda v, r: not r.get("inventory_quantity_set"),
        (
            "company_id",
            "product_id",
            "location_id",
            "quantity",
            "inventory_quantity",
            "inventory_quantity_set",
        ),
        "counter adjustment back to the counted-before quantity; refused if stock moved since",
    ),
}
EDI_FIELDS_RE = wk.EDI
# l10n e-invoice data on a move (MX CFDI, IT SDI, ES SII/TBAI, IN, SA ZATCA, ...)
L10N_EI = re.compile(r"l10n_[a-z]{2}\w*_(edi|einvoice|e_invoice|cfdi|sdi|sii|tbai|zatca)\w*$")
EI_IDLE = (None, False, "", 0, [], "False", "to_send")
# to_send is idle only here: the module check above has already refused any install that
# could send it (l10n e-invoice module) and journal formats are refused separately.
# Localisations that transmit inside action_post or by cron after it: refused by name.
EI_MODULE = re.compile(
    r"^(l10n_[a-z0-9]+_(edi|einvoice|e_invoice|cfdi|sdi|sii|tbai|zatca|nilvera|eta|dte|fe|ubl)"
    r"\w*|l10n_tr_nilvera\w*|l10n_dk_nemhandel\w*|l10n_eg_edi_eta|l10n_\w*_edi_\w*)$"
)
PEPPOL_CO = re.compile(r"\w*proxy_state$|peppol_\w*state$")  # peppol, nemhandel, ...
PEPPOL_OFF = frozenset({"", "False", "not_registered", "rejected", "canceled"})


class PostRefused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.refusal = Refusal(RF, MISS, reason[:300])


def _no(reason: str) -> PostRefused:
    return PostRefused(reason)


def _nm(v: Any) -> Any:
    return v[1] if isinstance(v, (list, tuple)) else v


def _id(v: Any) -> Any:
    return v[0] if isinstance(v, (list, tuple)) else v


@dataclass
class PostPlan:
    op: str
    ids: tuple[int, ...]
    approved_count: int
    walk: wk.Walk
    preview: list[str]
    reasons: list[str]
    before: dict[int, dict]  # pre-post facts the undo is bound to
    phash: str
    counter: str

    @property
    def tier(self) -> int:
        return 3


@dataclass
class PostDone:
    status: str  # done | refused | mismatch | needs-human
    plan: PostPlan
    refusal: Refusal | None = None
    after: dict[int, dict] = field(default_factory=dict)
    undo_ids: tuple[int, ...] = ()
    extra: dict[str, list[int]] = field(default_factory=dict)  # side records the run created


class Poster:
    def __init__(self, walker: wk.Walker, today: date | None = None) -> None:
        self.w, self.read, self.v = walker, walker.read, walker.version
        self.today = (today or date.today()).isoformat()

    # ---------- checks
    def _rows(self, op: Op, ids: Sequence[int]) -> list[dict]:
        meta = self.w.meta(op.model)
        want = [f for f in op.fields if f in meta] + [f for f in meta if EDI_FIELDS_RE.search(f)]
        if op.model == "account.move":
            want += [
                f
                for f in (
                    "is_move_sent",
                    "restrict_mode_hash_table",
                    "payment_state",
                    "inalterable_hash",
                )
                if f in meta
            ]
        if op.model == "account.payment":
            want += [
                f for f in ("is_reconciled", "is_matched", "is_sent", "is_move_sent") if f in meta
            ]
        rows = self.read(op.model, "read", [list(ids), sorted(set(want))], RA)
        if len(rows) != len(ids):
            raise _no(f"{op.model}: {len(ids) - len(rows)} record(s) unreadable or gone")
        return sorted(rows, key=lambda r: r["id"])

    def _locks(self, company: Any, on: str, what: str) -> None:
        cid = _id(company)
        if not cid:
            raise _no(f"{what}: no company, lock dates cannot be checked")
        lf = [f for f in wk.LOCK_DATES if f in self.w.meta("res.company")]
        if not lf:
            raise _no("res.company has no lock-date fields here: lock check impossible")
        c = self.read("res.company", "read", [[cid], lf], RA)
        if not c:
            raise _no(f"company {cid} unreadable")
        hit = sorted(f for f in lf if c[0].get(f) and str(c[0][f]) >= str(on)[:10])
        if hit:
            raise _no(f"{what}: {on} is inside a locked period ({', '.join(hit)})")

    def _check(self, op: Op, rows: list[dict]) -> list[str]:
        why: list[str] = []
        for r in rows:
            tag = f"{op.model} #{r['id']}"
            if not op.pre(self.v, r):
                raise _no(f"{tag} ({r.get('state', 'no count set')}) is not ready for {op.method}")
            for f in [f for f in r if EDI_FIELDS_RE.search(f)]:
                if str(r.get(f) or "") not in wk.EDI_OPEN:
                    raise _no(f"{tag}: e-invoice {f}={r[f]!r}: sent documents are final")
            if r.get("is_move_sent") or r.get("is_sent"):
                raise _no(f"{tag} was already sent: posting it would be final to the customer")
            if r.get("is_reconciled") or r.get("is_matched"):
                raise _no(f"{tag} is already matched/reconciled")
            if r.get("inalterable_hash"):
                raise _no(f"{tag} carries an inalterability hash")
            doc_date = str(r.get("date") or self.today)
            self._locks(r.get("company_id"), doc_date, tag)  # posting date
            self._locks(r.get("company_id"), self.today, f"{tag} undo")  # counter-doc date
            if r.get("restrict_mode_hash_table"):
                why.append(f"{tag}: journal is hash-locked; only a credit note can undo it")
        return why

    def _has(self, model: str) -> bool:
        return bool(self.read("ir.model", "search_count", [[("model", "=", model)]], RA))

    def _outbound(self, op: Op, ids: Sequence[int]) -> None:
        """Live payment / carrier / e-invoice reach: refused, whatever the plan values say
        (a button carries no values, so the sinkhole's value-based check never fires)."""
        final = "it would charge / ship / e-file, which cannot be held or undone: refused"
        got = sh.BUSINESS_OUTBOUND.get(op.model)
        if got and self._has(got[0]):
            dom, pm = list(got[1]), self.w.meta(got[0])
            if any(c[0] not in pm for c in dom if isinstance(c, (list, tuple))):
                # the live flag moved (e.g. no payment.provider.state on 20): count
                # every installed/active provider instead; any = refuse (fail closed)
                dom = [(f, "=", v) for f, v in (("module_state", "installed"),) if f in pm]
            n = self.read(got[0], "search_count", [dom], RA)
            if n:
                raise _no(f"{n} live {sh.PROVIDER_LABELS[got[0]]} ({got[2]}): {final}")
        if op.model in ("account.move", "account.payment"):
            self._einvoice(ids, final, op.model)
        meta = self.w.meta(op.model)
        refs = {
            "account.payment": ("payment_token_id", "payment_transaction_id"),
            "stock.picking": ("carrier_id",),
        }.get(op.model, ())
        refs = tuple(f for f in refs if f in meta)
        if not refs:
            return
        for r in self.read(op.model, "read", [list(ids), list(refs)], RA):
            if r.get("payment_token_id") or r.get("payment_transaction_id"):
                raise _no(f"{op.model} #{r['id']} uses a saved card/payment token: {final}")
            cid = _id(r.get("carrier_id"))
            if cid:
                c = self.read("delivery.carrier", "read", [[cid], ["prod_environment"]], RA)
                if not c or c[0].get("prod_environment") is not False:
                    raise _no(f"{op.model} #{r['id']} ships with a production carrier: {final}")

    def _einvoice(self, ids: Sequence[int], final: str, model: str = "account.move") -> None:
        """E-invoice routes that transmit after posting, outside the proxy-user check:
        17 account_edi (journal edi_format_ids -> edi documents the cron sends), Peppol
        (company registered with the proxy), l10n_* e-invoice fields on the move."""
        try:
            mods = self.read(
                "ir.module.module",
                "search_read",
                [[("state", "=", "installed")]],
                {**RA, "fields": ["name"]},
            )
            names = sorted(m["name"] for m in mods)
        except Exception as exc:  # noqa: BLE001 - unreadable = refuse
            raise _no(f"installed modules unreadable ({type(exc).__name__}): refused") from exc
        if not names:
            raise _no("installed modules unreadable (empty list): refused")
        hit = [n for n in names if EI_MODULE.match(n)]
        if hit:
            raise _no(
                f"e-invoice module {hit[0]} is installed: posting can transmit to the tax "
                f"authority / network ({final}); a human posts it"
            )
        mm = self.w.meta(model)
        l10n = [f for f in mm if L10N_EI.match(f)] if model == "account.move" else []
        rec = [f for f in ("reconciled_invoice_ids", "reconciled_bill_ids") if f in mm]
        moves = self.read(model, "read", [list(ids), ["journal_id", "company_id", *l10n, *rec]], RA)
        if len(moves) != len(ids):
            raise _no(f"{model} unreadable for the e-invoice check")
        inv = sorted({i for r in moves for f in rec for i in (r.get(f) or [])})
        extra_j = set()
        if inv:  # a payment receipt e-invoice follows the paid invoices' journals too
            got = self.read("account.move", "read", [inv, ["journal_id"]], RA)
            if len(got) != len(inv):
                raise _no("reconciled invoices unreadable for the e-invoice check")
            extra_j = {_id(x.get("journal_id")) for x in got}
        for r in moves:
            hit = [f"{f}={r[f]!r}" for f in l10n if r.get(f) not in EI_IDLE]
            if hit:
                raise _no(f"{model} #{r['id']} has e-invoice data {hit[:3]}: {final}")
        jids = sorted(({_id(r.get("journal_id")) for r in moves} | extra_j) - {None})
        jm = self.w.meta("account.journal") if self._has("account.journal") else {}
        if self._has("account.edi.format") or "edi_format_ids" in jm:
            if "edi_format_ids" not in jm:
                raise _no("e-invoice formats installed but journal formats unreadable: refused")
            for j in self.read("account.journal", "read", [jids, ["edi_format_ids"]], RA):
                if j.get("edi_format_ids"):
                    raise _no(f"journal #{j['id']} has active e-invoice formats: {final}")
            if len(self.read("account.journal", "read", [jids, ["id"]], RA)) != len(jids):
                raise _no("journal unreadable for the e-invoice check")
        cm = self.w.meta("res.company")
        pf = [f for f in cm if PEPPOL_CO.match(f)]
        if pf:
            cids = sorted({_id(r.get("company_id")) for r in moves} - {None})
            for c in self.read("res.company", "read", [cids, pf], RA):
                on = [f for f in pf if str(c.get(f) or "") not in PEPPOL_OFF]
                if on:
                    raise _no(f"company #{c['id']} is registered for Peppol ({on[0]}): {final}")

    def _tops(self) -> dict[str, int]:
        return {m: self.w._top(m) for m in ("account.move", "stock.picking") if self._has(m)}

    def _side(self, op: Op, pp: PostPlan, tops: dict[str, int]) -> dict[str, list[int]]:
        """New records the bot's run created beyond what the op itself is allowed to make:
        a payment's own entry, a validated move's valuation entry. Anything else is listed."""
        mv = {x for v in pp.before.values() for x in v.get("move_ids", [])}

        def expected(m: str, r: dict) -> bool:
            if m != "account.move":
                return False
            if op.model == "account.payment":
                return any(_id(r.get(f)) in pp.ids for f in ("origin_payment_id", "payment_id"))
            return op.model == "stock.picking" and _id(r.get("stock_move_id")) in mv

        out: dict[str, list[int]] = {}
        for m, top in tops.items():
            meta = self.w.meta(m)
            link = [f for f in ("origin_payment_id", "payment_id", "stock_move_id") if f in meta]
            new = self.read(
                m,
                "search_read",
                [[("id", ">", top), ("create_uid", "=", self.w.bot)]],
                {**RA, "fields": link},
            )
            for r in new:
                out.setdefault(("expected " if expected(m, r) else "") + m, []).append(r["id"])
        return out

    def _preview(self, op: Op, rows: list[dict]) -> tuple[list[str], dict[int, dict]]:
        ids = [r["id"] for r in rows]
        out, before = [], {r["id"]: {k: _id(v) for k, v in r.items()} for r in rows}
        if op.model == "account.move":
            ls = self.read(
                "account.move.line",
                "search_read",
                [[("move_id", "in", ids)]],
                {
                    **RA,
                    "fields": ["move_id", "account_id", "debit", "credit", "partner_id"]
                    + [f for f in DEFER if f in self.w.meta("account.move.line")],
                },
            )
            if any(x.get(f) for x in ls for f in DEFER):
                raise _no("lines carry deferral dates: Odoo would create deferral entries")
            if not ls:
                raise _no("no journal items: nothing to post")
            for mid in ids:
                mine = [x for x in ls if _id(x["move_id"]) == mid]
                dr = round(sum(x["debit"] for x in mine), 2)
                cr = round(sum(x["credit"] for x in mine), 2)
                if dr != cr:
                    raise _no(f"account.move #{mid} is unbalanced ({dr} vs {cr})")
                out.append(f"entry #{mid}: {len(mine)} line(s), debit {dr} = credit {cr}")
                before[mid]["lines"] = sorted(
                    [_id(x["account_id"]), x["debit"], x["credit"], _id(x.get("partner_id"))]
                    for x in mine
                )
            out += [
                f"  {_nm(x['account_id'])} Dr {x['debit']} Cr {x['credit']}" for x in ls[:CAP_LINES]
            ]
        elif op.model == "account.payment":
            out += [
                f"payment #{r['id']}: {r.get('payment_type')} {r.get('amount')} "
                f"journal {_id(r.get('journal_id'))} partner {_id(r.get('partner_id'))} "
                f"on {r.get('date')}"
                for r in rows
            ]
        elif op.model == "stock.picking":
            mv = self.read(
                "stock.move",
                "search_read",
                [[("picking_id", "in", ids)]],
                {
                    **RA,
                    "fields": [
                        "picking_id",
                        "product_id",
                        "product_uom_qty",
                        "quantity",
                        "location_id",
                        "location_dest_id",
                        "state",
                    ]
                    + [f for f in CHAIN if f in self.w.meta("stock.move")],
                },
            )
            if not mv:
                raise _no("no stock moves: nothing to validate")
            for m in mv:
                if (
                    m.get("move_dest_ids")
                    or m.get("move_orig_ids")
                    or m.get("created_production_id")
                    or m.get("procure_method") == "make_to_order"
                ):
                    raise _no(
                        f"stock.move #{m['id']} is chained (dropship / multi-step / MRP): "
                        "validating would move other documents: refused for now"
                    )
                before.setdefault(_id(m["picking_id"]), {}).setdefault("move_ids", []).append(
                    m["id"]
                )
            prods = sorted({_id(m["product_id"]) for m in mv})
            tr = self.read("product.product", "read", [prods, ["tracking"]], RA)
            if len(tr) != len(prods):
                raise _no("products unreadable")
            if any((t.get("tracking") or "none") != "none" for t in tr):
                raise _no("lot/serial-tracked products: not handled by the bot (needs a person)")
            for m in mv:
                if m.get("state") in ("done", "cancel"):
                    continue
                if round(float(m.get("quantity") or 0), 6) != round(float(m["product_uom_qty"]), 6):
                    raise _no(
                        f"stock.move #{m['id']}: quantity {m.get('quantity')} != demand "
                        f"{m['product_uom_qty']}: Odoo would ask about a backorder"
                    )
                out.append(
                    f"move #{m['id']} {_nm(m['product_id'])}"
                    f" x{m['product_uom_qty']}: {_id(m['location_id'])} -> "
                    f"{_id(m['location_dest_id'])}"
                )
                before.setdefault(_id(m["picking_id"]), {}).setdefault("moves", []).append(
                    [_id(m["product_id"]), m["product_uom_qty"], _id(m["location_dest_id"])]
                )
            out.append("stock valuation entries (if automated) are dated today")
        else:
            for r in rows:
                d = round(float(r["inventory_quantity"]) - float(r["quantity"]), 6)
                out.append(
                    f"quant #{r['id']} product {_id(r['product_id'])} at "
                    f"{_id(r['location_id'])}: {r['quantity']} -> "
                    f"{r['inventory_quantity']} ({d:+})"
                )
        return out[: CAP_LINES + 10], before

    # ---------- plan
    def plan(
        self, op_name: str, ids: Sequence[int], plan_id: str, approved_count: int
    ) -> PostPlan | Refusal:
        try:
            op = OPS.get(op_name)
            if op is None:
                raise _no(f"unknown posting op {op_name!r}")
            ids = tuple(int(i) for i in ids)
            if not ids or len(set(ids)) != len(ids):
                raise _no("ids must be non-empty and distinct")
            if len(ids) != int(approved_count):
                raise _no(f"{len(ids)} record(s) != approved plan's {approved_count}")
            self.w._version_check()
            rows = self._rows(op, ids)
            why = self._check(op, rows)
            self._outbound(op, ids)
            lines, before = self._preview(op, rows)
            walk = self.w.plan([wk.Step("call", op.model, ids, method=op.method)], plan_id)
            if isinstance(walk, Refusal):
                return walk
            p = walk.steps[0]
            p.tier = 3
            why += p.reasons + ["posting: L3, exact count bound to the approved plan"]
            phash = hashlib.sha256(
                json.dumps(
                    [op_name, ids, before, p.preview_hash], sort_keys=True, default=str
                ).encode()
            ).hexdigest()
            return PostPlan(
                op_name,
                ids,
                int(approved_count),
                walk,
                lines + p.lines,
                sorted(set(why)),
                before,
                phash,
                op.counter,
            )
        except PostRefused as exc:
            return exc.refusal
        except wk.Refused as exc:
            return exc.refusal
        except Exception as exc:  # noqa: BLE001 - unreadable = refuse
            return Refusal(RF, MISS, f"unreadable: {type(exc).__name__}: {exc}"[:200])

    # ---------- apply
    def apply(self, pp: PostPlan, spec: gd.RunSpec) -> PostDone:
        op = OPS[pp.op]
        try:
            if spec.approval.level < 3:
                raise _no("posting needs L3 approval")
            if len(pp.ids) != pp.approved_count:
                raise _no("record count differs from the approved plan")
            rows = self._rows(op, pp.ids)  # fresh: anything changed since the preview refuses
            self._check(op, rows)
            self._outbound(op, pp.ids)
            _, before = self._preview(op, rows)
            if json.dumps(before, sort_keys=True, default=str) != json.dumps(
                {int(k): v for k, v in pp.before.items()}, sort_keys=True, default=str
            ):
                raise _no("documents changed since the preview: plan again")
            tops = self._tops()
        except PostRefused as exc:
            return PostDone("refused", pp, exc.refusal)
        except Exception as exc:  # noqa: BLE001
            return PostDone("refused", pp, Refusal(RF, MISS, f"unreadable: {exc}"[:200]))
        d = self.w.apply(pp.walk, spec)[0]
        if d.status != "done":
            return PostDone(d.status, pp, d.refusal)
        try:
            extra = self._side(op, pp, tops)
        except Exception as exc:  # noqa: BLE001 - side effects unknown = stop
            extra = {f"unreadable ({type(exc).__name__})": []}
        if any(not k.startswith("expected ") for k in extra):
            why = f"posting created unexpected records {extra}: kill switch on, needs a person"
            self.w.gate.switch.turn_on(spec.db_fingerprint, "system", why[:200])
            return PostDone("needs-human", pp, Refusal(RF, MISS, why[:300]), extra=extra)
        rows = self._rows(op, pp.ids)
        bad = [r["id"] for r in rows if not op.post(self.v, r)]
        after = {r["id"]: {k: _id(v) for k, v in r.items()} for r in rows}
        if bad:  # e.g. a wizard came back (backorder / immediate transfer): nothing assumed
            return PostDone(
                "mismatch", pp, Refusal(RF, MISS, f"not posted after the call: {bad}"), after
            )
        return PostDone("done", pp, after=after, extra=extra)

    # ---------- undo (counter-documents only)
    def _gate(
        self, spec: gd.RunSpec, n: str, model: str, method: str, args: list, kw: dict | None = None
    ) -> Any:
        s = dataclasses.replace(
            spec,
            task_id=f"undo:{model}:{method}",
            risk_class="R4",
            idempotency_key=f"{spec.idempotency_key}:u{n}",
            approval=dataclasses.replace(spec.approval),
        )
        return self.w.gate.call(s, model, method, args, kw)

    def undo(self, pd: PostDone, spec: gd.RunSpec) -> PostDone:
        pp, op = pd.plan, OPS[pd.plan.op]
        try:
            if pd.status != "done":
                raise _no("only a completed posting can be undone")
            if spec.approval.level < 3:
                raise _no("undoing a posting needs L3 approval")
            rows = self._rows(op, pp.ids)
            if {r["id"]: {k: _id(v) for k, v in r.items()} for r in rows} != pd.after:
                raise _no("documents changed since they were posted: undo needs a person")
            for r in rows:
                self._locks(r.get("company_id"), self.today, f"{op.model} #{r['id']} undo")
            scan = self.w.sink.scan(op.model, SCAN_AS, {}, list(pp.ids))
            if scan.verdict == "refuse":
                raise _no("outbound scan refused the undo")
            ref = self.w.sink.open(scan, 3)
            if ref is not None:
                raise _no(ref.reason)
            try:
                made = getattr(self, f"_undo_{pd.plan.op}")(pp, rows, spec)
                if not self.w.sink.after_batch():
                    raise _no("undo effects could not be proven held: stopped")
            finally:
                self.w.sink.close()
        except PostRefused as exc:
            return PostDone("refused", pp, exc.refusal)
        except (PermissionError, wk.Refused) as exc:
            r = getattr(exc, "refusal", None) or Refusal(RF, MISS, str(exc)[:200])
            return PostDone("needs-human", pp, r)
        return PostDone("done", pp, undo_ids=tuple(made))

    def _undo_move_post(self, pp: PostPlan, rows: list[dict], spec: gd.RunSpec) -> list[int]:
        for r in rows:
            if r.get("payment_state") not in (None, False, "not_paid", "invoicing_legacy"):
                raise _no(f"account.move #{r['id']} is {r['payment_state']}: unreconcile first")
        ids = list(pp.ids)
        ctx = {"context": {"active_model": "account.move", "active_ids": ids}}
        vals = {"move_ids": [(6, 0, ids)], "date": self.today, "reason": "Bot undo of posting"}
        if "journal_id" in self.w.meta("account.move.reversal"):
            vals["journal_id"] = _id(rows[0]["journal_id"])
        wid = self._gate(spec, "w", "account.move.reversal", "create", [vals], ctx)
        self._gate(spec, "r", "account.move.reversal", "refund_moves", [[_id(wid)]], ctx)
        rev = self.read(
            "account.move",
            "search_read",
            [[("reversed_entry_id", "in", ids)]],
            {**RA, "fields": ["state"]},
        )
        if len(rev) != len(ids):
            raise _no(f"expected {len(ids)} reversal(s), found {len(rev)}: needs a person")
        drafts = [x["id"] for x in rev if x["state"] == "draft"]
        if drafts:
            self._einvoice(drafts, "a credit note would be transmitted too")
            self._gate(spec, "p", "account.move", "action_post", [drafts])
        return [x["id"] for x in rev]

    def _undo_payment_post(self, pp: PostPlan, rows: list[dict], spec: gd.RunSpec) -> list[int]:
        for r in rows:
            if r.get("is_reconciled") or r.get("is_matched"):
                raise _no(f"account.payment #{r['id']} is reconciled: unreconcile first")
        self._einvoice(
            pp.ids, "a cancelled payment receipt would be transmitted too", "account.payment"
        )
        self._gate(spec, "d", "account.payment", "action_draft", [list(pp.ids)])
        self._gate(spec, "c", "account.payment", "action_cancel", [list(pp.ids)])
        return list(pp.ids)

    def _undo_picking_validate(self, pp: PostPlan, rows: list[dict], spec: gd.RunSpec) -> list[int]:
        made = []
        for pid in pp.ids:
            for prod, qty, loc in pp.before[pid].get("moves", []):
                q = self.read(
                    "stock.quant",
                    "search_read",
                    [[("product_id", "=", prod), ("location_id", "=", loc)]],
                    {**RA, "fields": ["quantity"]},
                )
                if sum(float(x["quantity"]) for x in q) < float(qty):
                    raise _no(f"product {prod} already left location {loc}: return needs a person")
            ctx = {
                "context": {"active_model": "stock.picking", "active_id": pid, "active_ids": [pid]}
            }
            wid = self._gate(
                spec, f"{pid}.w", "stock.return.picking", "create", [{"picking_id": pid}], ctx
            )
            meth = "create_returns" if self.v < 18 else "action_create_returns"
            res = self._gate(spec, f"{pid}.r", "stock.return.picking", meth, [[_id(wid)]], ctx)
            rid = (res or {}).get("res_id") if isinstance(res, dict) else None
            if not rid:
                raise _no(f"return for picking #{pid} not created: needs a person")
            mv = self.read(
                "stock.move",
                "search_read",
                [[("picking_id", "=", rid)]],
                {**RA, "fields": ["product_uom_qty"]},
            )
            for m in mv:
                self._gate(
                    spec,
                    f"{pid}.m{m['id']}",
                    "stock.move",
                    "write",
                    [[m["id"]], {"quantity": m["product_uom_qty"]}],
                )
            self._gate(spec, f"{pid}.v", "stock.picking", "button_validate", [[rid]])
            st = self.read("stock.picking", "read", [[rid], ["state"]], RA)
            if not st or st[0]["state"] != "done":
                raise _no(f"return #{rid} created but not validated: needs a person")
            made.append(rid)
        return made

    def _undo_inventory_apply(self, pp: PostPlan, rows: list[dict], spec: gd.RunSpec) -> list[int]:
        for r in rows:
            b = pp.before[r["id"]]
            if round(float(r["quantity"]), 6) != round(float(b["inventory_quantity"]), 6):
                raise _no(f"quant #{r['id']} moved since the adjustment: needs a person")
        for r in rows:
            self._gate(
                spec,
                f"q{r['id']}",
                "stock.quant",
                "write",
                [[r["id"]], {"inventory_quantity": pp.before[r["id"]]["quantity"]}],
            )
        self._gate(spec, "apply", "stock.quant", "action_apply_inventory", [list(pp.ids)])
        return list(pp.ids)
