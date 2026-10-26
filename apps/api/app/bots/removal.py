"""BOT-R6-DELETE-MERGE: guarded archive, delete and record merge (R6). Writes only via the gate.

plan_remove(): archive first. A model with ``active`` is archived (reversible write through the
walker: before-image, proof, undo). Deleting needs ``allow_delete=True`` and is planned from the
live cascade preview (``blast.preview``): restrict FKs, uncountable graphs and any posted /
locked / reconciled / done row anywhere in the cascade or set-null set refuse it.

plan_merge(): partners (and contacts, which are partners) only, through Odoo's own merge wizard
(``base.partner.merge.automatic.wizard``); every other model (products included) has no stock
merge wizard and is refused. The plan stores a full before-image of every partner and every
row the wizard will relink (many2one/many2many fields and res_model/res_id pointers); rows that
are posted/locked/reconciled, or partners with users, refuse the merge.

Delete and merge are L3: typed exact count + a verified snapshot of THIS database
(``blast.confirm``), and the gate re-derives the plan when the job opens (``StaleGuard``): any
change in the counted rows refuses. Outbound effects go through the walker's Sinkhole.
undo_merge(): recreates the merged-away partners from the image (new ids: Odoo cannot reuse an
id over RPC) and relinks the image's rows to them, as ordinary walker plans.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.bots import blast as bl
from app.bots import diff as df
from app.bots import guard as gd
from app.bots import walker as wk
from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal

RF, MISS = "RF-R6", "delete-merge"
PARTNER, WIZ = "res.partner", "base.partner.merge.automatic.wizard"
RA = {"context": {"active_test": False}}
ALL_CO = {"context": {"active_test": False, "allowed_company_ids": []}}  # no company filter
MAX_MERGE = 3  # Odoo's wizard refuses more without superuser
REF_MODELS_FIELD = ("res_model", "res_id")
_FLAGS = {  # beyond walker.IRRECOVERABLE: boolean "final" markers
    "account.move.line": ("reconciled", "reconciled journal item"),
    "account.partial.reconcile": ("id", "reconciliation"),
    "account.full.reconcile": ("id", "reconciliation"),
}
_RESTORE = {"char", "text", "html", "boolean", "selection", "integer", "float", "monetary", "date"}


def _no(reason: str) -> Refusal:
    return Refusal(RF, MISS, reason[:300])


@dataclass
class Plan:
    kind: str  # archive | delete | merge
    model: str
    ids: tuple[int, ...]
    walk: wk.Walk | None = None
    preview: bl.Preview | None = None
    dst: int | None = None
    image_ref: str | None = None
    image: dict[str, Any] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return self.preview.tier.blast_count if self.preview else len(self.ids)

    @property
    def tier(self) -> int:
        return 3 if self.kind != "archive" else (self.walk.tier if self.walk else 3)


@dataclass
class Result:
    status: str  # done | refused | mismatch | needs-human | tripped | partial | duplicate
    plan: Plan
    refusal: Refusal | None = None
    done: list[wk.Done] = field(default_factory=list)


class Removal:
    def __init__(self, walker: wk.Walker) -> None:
        self.w = walker
        self.read = walker.read

    # ---------- final-state check over any set of rows
    def final_rows(self, rows: dict[str, Sequence[int]]) -> list[str]:
        out: list[str] = []
        for model, ids in sorted(rows.items()):
            if not ids:
                continue
            meta = self.read(model, "fields_get", [[]], {"attributes": ["type"]}) or {}
            spec, flag = wk.IRRECOVERABLE.get(model), _FLAGS.get(model)
            want = [f for f in (spec and spec[0], flag and flag[0], "parent_state") if f in meta]
            if model in _FLAGS and flag[0] == "id":
                out.append(f"{model}: {len(ids)} {flag[1]} row(s) touched")
                continue
            if not want:
                continue
            for r in self.read(model, "read", [sorted(ids), want], RA) or []:
                if spec and spec[0] in r and str(r[spec[0]]) in spec[1]:
                    out.append(f"{model} #{r['id']}: {spec[2]}")
                elif flag and r.get(flag[0]):
                    out.append(f"{model} #{r['id']}: {flag[1]}")
                elif r.get("parent_state") == "posted":
                    out.append(f"{model} #{r['id']}: line of a posted entry")
        return out

    # ---------- archive / delete
    def plan_remove(
        self, model: str, ids: Sequence[int], plan_id: str, *, allow_delete: bool = False
    ) -> Plan | Refusal:
        ids = tuple(sorted(set(int(i) for i in ids)))
        if not ids:
            return _no("nothing to remove")
        try:
            meta = self.w.meta(model)
        except wk.Refused as exc:
            return exc.refusal
        except Exception as exc:  # noqa: BLE001
            return _no(f"{model}: metadata unreadable ({type(exc).__name__})")
        if "active" in meta and not allow_delete:
            walk = self.w.plan([wk.Step("write", model, ids, {"active": False})], plan_id)
            if isinstance(walk, Refusal):
                return walk
            return Plan("archive", model, ids, walk, lines=[f"archive {len(ids)} {model}"])
        if not allow_delete:
            return _no(f"{model} cannot be archived; deleting must be asked for explicitly")
        pv = self._preview(model, ids)
        if isinstance(pv, Refusal):
            return pv
        walk = self.w.plan([wk.Step("unlink", model, ids)], plan_id)
        if isinstance(walk, Refusal):
            return walk
        low = pv.blast["low_count"]
        lines = [f"COUNT MAY BE LOW ({len(low)} reasons below): " if low else ""]
        lines[0] += f"delete {pv.tier.blast_count} rows (type this): {pv.blast['per_model']}"
        lines += [f"set empty: {pv.blast['nulled']}"] if pv.blast["nulled"] else []
        lines += [
            f"will be removed or orphaned with them: {k} x{n}"
            for k, n in pv.blast["pointers"].items()
        ]
        lines += [f"count may be low: {r}" for r in pv.blast["low_count"]]
        lines += ["no automatic undo: restore needs the snapshot"]
        return Plan("delete", model, ids, walk, pv, lines=lines)

    def _preview(self, model: str, ids: Sequence[int]) -> bl.Preview | Refusal:
        pv = bl.preview(
            self.read,
            model,
            list(ids),
            None,
            op="unlink",
            cls="R6",
            subkind="delete",
            route=self.w.route,
        )
        if isinstance(pv, Refusal):
            return pv
        try:
            refs = self.pointer_rows(pv.blast["ids"])
        except Exception as exc:  # noqa: BLE001 - uncounted pointers = refused
            return _no(f"res_model/res_id rows uncountable ({type(exc).__name__})")
        n = sum(refs.values())
        blast = {**pv.blast, "pointers": dict(sorted(refs.items())), "pointer_total": n}
        tier = dataclasses.replace(pv.tier, blast_count=pv.tier.blast_count + n)
        pv = bl.Preview(pv.diff, blast, tier, df.canonical_hash([pv.payload_hash, blast]))
        touched = {m: v for m, v in pv.blast["ids"].items()}
        for m, v in pv.blast["nulled_ids"].items():
            touched[m] = sorted(set(touched.get(m, [])) | set(v))
        try:
            fin = self.final_rows(touched)
        except Exception as exc:  # noqa: BLE001
            return _no(f"final-state check unreadable ({type(exc).__name__})")
        return _no(f"delete touches final records: {fin[:5]}") if fin else pv

    def pointer_rows(self, ids_by_model: dict[str, Sequence[int]]) -> dict[str, int]:
        """Rows pointing at the targets via res_model/res_id (messages, followers,
        attachments, activities ...): Odoo removes or orphans them in Python, unseen by FKs."""
        out: dict[str, int] = {}
        for m in self._ref_models():
            for model, ids in sorted(ids_by_model.items()):
                if not ids:
                    continue
                dom = [("res_model", "=", model), ("res_id", "in", sorted(ids))]
                if n := int(self.read(m, "search_count", [dom], RA) or 0):
                    out[f"{m}<-{model}"] = n
        return out

    def _ref_models(self) -> list[str]:
        refs = self.read(
            "ir.model.fields",
            "search_read",
            [[("name", "=", "res_id"), ("store", "=", True)]],
            {"fields": ["model"], "order": "model"},
        )
        out = []
        for f in refs or []:
            mm = self.read(
                f["model"], "fields_get", [list(REF_MODELS_FIELD)], {"attributes": ["type"]}
            )
            if all(k in (mm or {}) for k in REF_MODELS_FIELD):
                out.append(f["model"])
        return sorted(set(out))

    # ---------- merge
    def plan_merge(self, model: str, ids: Sequence[int], dst: int, plan_id: str) -> Plan | Refusal:
        if model != PARTNER:
            return _no(f"{model}: no stock Odoo merge wizard; only contacts/partners merge")
        ids = tuple(sorted(set(int(i) for i in ids)))
        if not 2 <= len(ids) <= MAX_MERGE or dst not in ids:
            return _no(f"merge needs 2-{MAX_MERGE} partners including the one kept")
        try:
            self.w._version_check()  # same server-shape check the walker runs (17-20)
            return self._merge_plan(ids, int(dst), plan_id)
        except wk.Refused as exc:
            return exc.refusal
        except Exception as exc:  # noqa: BLE001 - unreadable = refused
            return _no(f"merge preview unreadable ({type(exc).__name__}: {exc})"[:200])

    def _merge_plan(self, ids: tuple[int, ...], dst: int, plan_id: str) -> Plan | Refusal:
        if not self.read("ir.model", "search_count", [[("model", "=", WIZ)]], RA):
            return _no("partner merge wizard not installed on this database")
        meta = self.w.meta(PARTNER)
        keep = sorted(
            f for f, m in meta.items() if m.get("store", True) and m["type"] != "one2many"
        )
        partners = self.read(PARTNER, "read", [list(ids), keep], RA) or []
        if len(partners) != len(ids):
            return _no("some partners do not exist")
        src = [i for i in ids if i != dst]
        if self.read("res.users", "search", [[("partner_id", "in", src)]], RA):
            return _no("a merged-away partner belongs to a user: refused")
        if not next(p for p in partners if p["id"] == dst).get("active", True):
            return _no("the kept partner is archived: unarchive it first or keep another")
        cos = self._companies()
        if isinstance(cos, Refusal):
            return cos
        if set(src) & set(cos.values()):
            return _no("a merged-away partner is a company's own contact: refused")
        dom = [("model", "=", PARTNER), ("res_id", "in", src)]
        if self.read("ir.model.data", "search", [dom], RA):
            return _no("a merged-away partner is referenced by module data (xmlid): refused")
        rel: list[dict[str, Any]] = []
        fields = self.read(
            "ir.model.fields",
            "search_read",
            [[("relation", "=", PARTNER), ("ttype", "in", ["many2one", "many2many"])]],
            {"fields": ["model", "name", "ttype", "store"], "order": "model,name"},
        )
        tmp = {
            m["model"]
            for m in self.read(
                "ir.model", "search_read", [[("transient", "=", True)]], {"fields": ["model"]}
            )
            or []
        } | {WIZ}  # wizard rows (incl. the merge wizard itself) are not data being relinked
        for f in fields or []:
            if not f.get("store", True) or f["model"] in tmp:
                continue
            rows = self.read(f["model"], "search", [[(f["name"], "in", src)]], RA) or []
            if f["model"] == PARTNER:
                rows = [r for r in rows if r not in src]
            if not rows:
                continue
            entry = {"model": f["model"], "field": f["name"], "ttype": f["ttype"], "ids": rows}
            if f["ttype"] == "many2many":
                got = self.read(f["model"], "read", [rows, [f["name"]]], RA) or []
                entry["values"] = {str(r["id"]): sorted(r[f["name"]] or []) for r in got}
            else:
                got = self.read(f["model"], "read", [rows, [f["name"]]], RA) or []
                entry["values"] = {
                    str(r["id"]): df.norm_read("many2one", r[f["name"]]) for r in got
                }
            rel.append(entry)
        for m in self._ref_models():
            dom = [("res_model", "=", PARTNER), ("res_id", "in", src)]
            rows = self.read(m, "search", [dom], RA) or []
            if rows:
                got = self.read(m, "read", [rows, ["res_id"]], RA) or []
                vals = {str(r["id"]): r["res_id"] for r in got}
                rel.append(
                    {"model": m, "field": "res_id", "ttype": "integer", "ids": rows, "values": vals}
                )
        fin = self.final_rows(_group(rel))
        if fin:
            return _no(f"merge would rewrite final records: {fin[:5]}")
        image = {
            "dst": dst,
            "src": src,
            "partners": partners,
            "relinked": rel,
            "company_partners": sorted({c for c in cos.values() if c}),
        }
        count = len(src) + sum(len(e["ids"]) for e in rel)
        t = rr.plan_tier("R6", "merge", self.w.route, rr.DEFAULT_POLICY, count, ["merge"])
        if isinstance(t, Refusal):
            return t
        body = {"model": PARTNER, "op": "merge", "image": image, "tier": t.tier}
        pv = bl.Preview(None, {"total": count}, t, df.canonical_hash(body))
        ref = self.w.store.put({"kind": "merge", **image})
        lines = [f"merge {src} into {dst}: {count} rows relinked or removed"]
        lines += [f"{e['model']}.{e['field']}: {len(e['ids'])}" for e in rel]
        return Plan("merge", PARTNER, ids, None, pv, dst, ref, image, lines)

    def _companies(self) -> dict[int, int] | Refusal:
        """Every company -> its contact, or refused when the bot cannot prove it sees all.
        RPC has no rule-free read, so: multi-company in use => the bot must belong to every
        company, and ids around the visible ones are probed (AccessError = a hidden company)."""
        try:
            got = self.read(
                "res.company", "search_read", [[]], {**ALL_CO, "fields": ["partner_id"]}
            )
            cos = {r["id"]: df.norm_read("many2one", r["partner_id"]) for r in got or []}
            me = self.read("res.users", "read", [[self.w.bot], ["company_ids"]], RA) or []
            mine = set(me[0]["company_ids"]) if me else set()
            gid = self.read(
                "ir.model.data",
                "search_read",
                [[("module", "=", "base"), ("name", "=", "group_multi_company")]],
                {"fields": ["res_id"]},
            )
            fg = self.read("res.users", "fields_get", [["group_ids", "groups_id"]], {}) or {}
            gfield = "group_ids" if "group_ids" in fg else "groups_id"
            multi_grp = bool(gid) and bool(
                self.read(
                    "res.users",
                    "search_count",
                    [[(gfield, "in", [gid[0]["res_id"]])]],
                    RA,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _no(f"companies unreadable ({type(exc).__name__}): merge refused")
        if not cos:
            return _no("no company visible: merge refused")
        probe = [i for i in range(1, max(cos) + 6) if i not in cos]
        for i in probe:
            try:
                if not self.read("res.company", "read", [[i], ["name"]], ALL_CO):
                    continue  # nothing there
            except Exception as exc:  # noqa: BLE001 - only "does not exist" is fine
                if "MissingError" not in f"{type(exc).__name__} {exc}":
                    return _no(f"company #{i} exists but is hidden from the bot: merge refused")
                continue
            return _no(f"company #{i} visible only by id: merge refused")
        if (len(cos) > 1 or multi_grp) and not set(cos) <= mine:
            return _no("multi-company database: the bot must belong to every company to merge")
        return cos

    # ---------- apply
    def apply(
        self, plan: Plan, spec: gd.RunSpec, *, typed: str | None = None, snapshot: Any = None
    ) -> Result:
        if plan.kind == "archive":
            return self._walk(plan, spec)
        ref = bl.confirm(
            plan.preview,
            approval=spec.approval.level,
            typed=typed,
            snapshot=snapshot,
            fingerprint=self.w.db,
        )
        if ref is not None:
            return Result("refused", plan, ref)
        sid = getattr(getattr(snapshot, "snap", None), "id", None)
        if spec.snapshot_id != sid:
            return Result("refused", plan, _no("run is not bound to the verified snapshot"))
        gate = self.w.gate
        inner = gate.rehearsals
        gate.rehearsals = bl.StaleGuard(inner, plan.preview.payload_hash, self._recompute(plan))
        try:
            if plan.kind == "delete":
                return self._delete_readback(plan, spec, self._walk(plan, spec))
            return self._merge(plan, spec)
        finally:
            gate.rehearsals = inner

    def _recompute(self, plan: Plan):
        def again(*_a: Any) -> bl.Preview | Refusal:
            if plan.kind == "delete":
                return self._preview(plan.model, plan.ids)
            p = self.plan_merge(plan.model, plan.ids, plan.dst or 0, "recheck")
            return p if isinstance(p, Refusal) else p.preview

        return again

    def _walk(self, plan: Plan, spec: gd.RunSpec) -> Result:
        done = self.w.apply(plan.walk, spec)
        last = done[-1] if done else None
        st = last.status if last else "refused"
        return Result(st, plan, last.refusal if last else _no("nothing applied"), done)

    def _merge(self, plan: Plan, spec: gd.RunSpec) -> Result:
        src, dst = plan.image["src"], plan.dst
        scan = self.w.sink.scan(PARTNER, op="unlink", values={}, ids=src)  # read-only scan
        if scan.verdict == "refuse":
            return Result("refused", plan, scan.refusal or _no("outbound scan refused"))
        opened = False
        try:
            if scan.channels:
                if (r := self.w.sink.open(scan, spec.approval.level)) is not None:
                    return Result("refused", plan, r)
                opened = True
            vals = {"partner_ids": [(6, 0, list(plan.ids))], "dst_partner_id": dst}
            wid = self.w.gate.call(self._spec(spec, "wizard"), WIZ, "create", [vals])
            if wid is None:
                return Result("needs-human", plan, _no("gate saw this merge already"))
            wid = wid[0] if isinstance(wid, list) else wid
            try:
                self.w.gate.call(self._spec(spec, "merge"), WIZ, "action_merge", [[wid]])
            except PermissionError:
                raise
            except Exception as exc:  # noqa: BLE001
                # Some servers (seen on 20) commit the merge, then fail building the reply.
                # Readback decides: nothing gone -> stop for a person; else verify or kill.
                try:
                    left = self.read(PARTNER, "search_count", [[("id", "in", src)]], RA)
                except Exception:  # noqa: BLE001 - may have committed and cannot tell
                    return self._kill(plan, spec, "merge outcome unreadable after an error")
                if left == len(src):
                    return Result("needs-human", plan, _no(f"merge failed ({type(exc).__name__})"))
            if opened and not self.w.sink.after_batch():
                return Result("tripped", plan, _no("outbound effects not proven held"))
        except PermissionError as exc:
            return Result("refused", plan, _no(str(exc)))
        except Exception as exc:  # noqa: BLE001 - incl. AuditError: stop, a person checks
            return Result("needs-human", plan, _no(f"merge failed ({type(exc).__name__})"))
        finally:
            if opened:
                self.w.sink.close()
        return self._merge_readback(plan, spec)

    def _spec(self, spec: gd.RunSpec, step: str) -> gd.RunSpec:
        return dataclasses.replace(
            spec,
            task_id="r6:merge:res.partner",
            risk_class="R6",
            idempotency_key=f"{spec.idempotency_key}:{step}",
            approval=dataclasses.replace(spec.approval),
        )

    def _merge_readback(self, plan: Plan, spec: gd.RunSpec) -> Result:
        src, dst, bad = plan.image["src"], plan.dst, []
        try:
            if self.read(PARTNER, "search_count", [[("id", "in", src)]], RA):
                bad.append("merged-away partners still exist")
            if not self.read(PARTNER, "search_count", [[("id", "=", dst)]], RA):
                bad.append("kept partner is gone")
            cps = plan.image.get("company_partners", [])
            if cps and self.read(PARTNER, "search_count", [[("id", "in", cps)]], RA) != len(cps):
                bad.append("a company's contact is gone")
            got_co = self.read(
                "res.company", "search_read", [[]], {**ALL_CO, "fields": ["partner_id"]}
            )
            if any(df.norm_read("many2one", r["partner_id"]) in src for r in got_co or []):
                bad.append("a company now points at a merged-away partner")
            for e in plan.image["relinked"]:
                got = self.read(e["model"], "read", [e["ids"], [e["field"]]], RA) or []
                for r in got:
                    v = r[e["field"]]
                    ok = (
                        dst in (v or [])
                        if e["ttype"] == "many2many"
                        else (df.norm_read("many2one", v) if e["ttype"] == "many2one" else v) == dst
                    )
                    if not ok:
                        bad.append(f"{e['model']} #{r['id']}.{e['field']} not relinked")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"readback unreadable ({type(exc).__name__})")
        if bad:
            return self._kill(plan, spec, "; ".join(bad[:5]))
        return Result("done", plan)

    def _kill(self, plan: Plan, spec: gd.RunSpec, why: str) -> Result:
        try:
            self.w.gate.switch.turn_on(
                spec.db_fingerprint, "system", f"R6 {plan.kind}: {why}"[:200]
            )
        except Exception:  # noqa: BLE001, S110 - result already says stop
            pass
        return Result("mismatch", plan, _no(why))

    def _delete_readback(self, plan: Plan, spec: gd.RunSpec, res: Result) -> Result:
        """Rows actually gone (targets, cascades, res_model/res_id rows) must equal typed."""
        if res.status != "done":
            return res
        pv = plan.preview
        try:
            left = sum(
                int(self.read(m, "search_count", [[("id", "in", sorted(ids))]], RA) or 0)
                for m, ids in pv.blast["ids"].items()
                if ids
            )
            left += sum(self.pointer_rows(pv.blast["ids"]).values())
        except Exception as exc:  # noqa: BLE001 - possibly committed, cannot verify
            return self._kill(plan, spec, f"delete readback unreadable ({type(exc).__name__})")
        gone = pv.tier.blast_count - left
        if gone != pv.tier.blast_count:
            return self._kill(plan, spec, f"deleted {gone} rows, typed {pv.tier.blast_count}")
        return res

    # ---------- undo
    def undo_merge(self, res: Result, spec: gd.RunSpec, plan_id: str) -> Result:
        """Recreate merged-away partners (new ids) and relink the image's rows to them."""
        plan = res.plan
        if res.status != "done" or plan.kind != "merge":
            return Result("refused", plan, _no("only a completed merge can be undone"))
        try:
            image = self.w.store.get(plan.image_ref or "")
        except Exception as exc:  # noqa: BLE001 - tampered/missing image = refused
            return Result("refused", plan, _no(f"before-image unusable ({type(exc).__name__})"))
        meta = self.w.meta(PARTNER)
        new: dict[int, int] = {}
        for p in image["partners"]:
            if p["id"] == image["dst"]:
                continue
            vals = {
                f: (df.norm_read("many2one", v) if meta[f]["type"] == "many2one" else v)
                for f, v in p.items()
                if f in meta and _restorable(meta[f]) and v not in (False, None, "")
            }
            walk = self.w.plan([wk.Step("create", PARTNER, (), vals)], f"{plan_id}:p{p['id']}")
            if isinstance(walk, Refusal):
                return Result("refused", plan, walk)
            d = self.w.apply(walk, spec)
            if not d or d[-1].status != "done":
                return Result(d[-1].status if d else "refused", plan, d[-1].refusal if d else None)
            new[p["id"]] = d[-1].record_ids[0]
        left: list[str] = []
        done: list[wk.Done] = []
        for i, st in enumerate(_relink_steps(image, new)):  # each relink planned on its own
            walk = self.w.plan([st], f"{plan_id}:relink{i}")
            if isinstance(walk, Refusal):
                left.append(f"{st.model} {list(st.ids)}: {walk.reason}")
                continue
            d = self.w.apply(walk, spec)
            done += d
            if not d or d[-1].status != "done":
                left.append(f"{st.model} {list(st.ids)}: {d[-1].status if d else 'refused'}")
        if left:  # those rows stay on the kept partner; a person decides
            return Result("partial", plan, _no(f"not relinked: {left[:5]}"), done)
        return Result("done", plan, None, done)


def _restorable(m: dict[str, Any]) -> bool:
    return (
        m.get("store", True)
        and not m.get("readonly")
        and not m.get("related")
        and not m.get("compute")
        and not m.get("company_dependent")
        and (m["type"] in _RESTORE or m["type"] == "many2one")
    )


def _group(rel: list[dict[str, Any]]) -> dict[str, list[int]]:
    out: dict[str, set[int]] = {}
    for e in rel:
        out.setdefault(e["model"], set()).update(e["ids"])
    return {m: sorted(v) for m, v in out.items()}


def _relink_steps(image: dict[str, Any], new: dict[int, int]) -> list[wk.Step]:
    steps: list[wk.Step] = []
    for e in image["relinked"]:
        groups: dict[Any, list[int]] = {}
        for rid, old in e["values"].items():
            if e["ttype"] == "many2many":
                key = tuple(new.get(x, x) for x in old)
            else:
                if old not in new:
                    continue
                key = new[old]
            groups.setdefault(key, []).append(int(rid))
        for key, rows in sorted(groups.items(), key=lambda kv: str(kv[0])):
            val = [(6, 0, list(key))] if e["ttype"] == "many2many" else key
            steps.append(wk.Step("write", e["model"], tuple(sorted(rows)), {e["field"]: val}))
    return steps
