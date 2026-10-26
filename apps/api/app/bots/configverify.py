"""BOT-CONFIG-VERIFY: read-only check of a configured Odoo database against a design spec.

Input: the BOT-PROCESS-DESIGN spec ``{spec_version: 1, status, odoo_major, items[]}``. Every
item is checked through a read-only caller ``call(model, method, args, kwargs)``; any method
outside ``READ_METHODS`` raises before reaching Odoo. Each item gets one status:

- ``matches``: found exactly once, every expected value and every linked item agree.
- ``missing``: readable, and no such record / module is there.
- ``differs``: found, but a value, a link, a duplicate or an archived record disagrees.
- ``cannot-read``: access error, missing model/field, partial company view, read limit hit.
- ``not designed``: the design itself said needs-custom / needs review, or the item is invalid.

Fail closed: nothing unreadable or partially read is ever ``matches``. Linked items
(``relations`` values that are refs of other items) are checked after all items: a match whose
link target is not a match, or whose field points elsewhere, becomes ``differs``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

Call = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]
READ_METHODS = frozenset({"fields_get", "search_read", "search_count", "read", "default_get"})
STATUSES = ("matches", "missing", "differs", "cannot-read", "not designed")
NOT_DESIGNED = frozenset({"needs-custom", "needs review"})
MAX_ITEMS = 2000
BATCH = 200
_X2M = ("one2many", "many2many")
_REL = ("many2one", *_X2M)


class ReadOnlyViolation(RuntimeError):
    pass


class _Unreadable(Exception):
    pass


def read_only(call: Call) -> Call:
    def ro(model: str, method: str, args: Sequence[Any], kw: dict[str, Any] | None = None) -> Any:
        if method not in READ_METHODS:
            raise ReadOnlyViolation(f"configverify is read-only; refused {model}.{method}")
        return call(model, method, args, kw)

    return ro


def _bad_num(v: Any) -> bool:
    return isinstance(v, float) and not math.isfinite(v)


def _scalar_ok(v: Any, depth: int = 0) -> bool:
    if depth > 3:
        return False
    if v is None or isinstance(v, (bool, int, str)):
        return not (isinstance(v, str) and len(v) > 2000) and not (
            isinstance(v, int) and abs(v) > 2**63
        )
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, (list, tuple)):
        return len(v) <= 1000 and all(_scalar_ok(x, depth + 1) for x in v)
    return False


class Verifier:
    def __init__(self, call: Call, *, companies: Sequence[int] | None = None) -> None:
        self.call = read_only(call)
        self.companies = [int(c) for c in companies or [] if isinstance(c, int)]
        self._fg: dict[str, dict[str, Any] | None] = {}
        self._names: dict[tuple[str, str], list[int]] = {}
        self.partial: str | None = None
        self._archived: set[tuple[str, int]] = set()
        self.truncated = False

    # ------------------------------------------------------------ reads
    def _ctx(self) -> dict[str, Any]:
        c: dict[str, Any] = {"active_test": False}
        if self.companies:
            c["allowed_company_ids"] = self.companies
        return c

    def _r(self, model: str, method: str, args: Sequence[Any], kw: dict[str, Any]) -> Any:
        try:
            return self.call(model, method, args, kw | {"context": self._ctx()})
        except ReadOnlyViolation:
            raise
        except Exception as e:  # noqa: BLE001 - access error / missing model -> cannot-read
            raise _Unreadable(f"{model}.{method}: {type(e).__name__}: {str(e)[:160]}") from e

    def fields(self, model: str) -> dict[str, Any] | None:
        if model not in self._fg:
            try:
                fg = self._r(
                    model, "fields_get", [], {"attributes": ["type", "relation", "digits"]}
                )
                self._fg[model] = fg if isinstance(fg, dict) and fg else None
            except _Unreadable:
                self._fg[model] = None
        return self._fg[model]

    def _company_view(self) -> None:
        try:
            total = self._r("res.company", "search_count", [[]], {})
        except _Unreadable as e:
            self.partial = f"companies unreadable ({e})"
            return
        seen = len(self.companies) if self.companies else 1
        if isinstance(total, int) and total > seen:
            self.partial = f"bot sees {seen} of {total} companies"

    def resolve(self, comodel: str, v: Any) -> int | None:
        """One record id for a design value, or None if absent. More than one candidate
        (archived ones included) is ambiguous => cannot-read, never an "any of" match."""
        if isinstance(v, bool):
            raise _Unreadable(f"bad reference value {v!r}")
        if isinstance(v, int):
            return v
        if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int):
            return v[0]  # Odoo [id, name]
        if not isinstance(v, str):
            raise _Unreadable(f"bad reference value {v!r}")
        k = (comodel, v)
        if k not in self._names:
            fg = self.fields(comodel)
            if fg is None:
                raise _Unreadable(f"model {comodel} not readable or absent")
            rows = self._by_name(comodel, fg, v)
            if not rows and " / " in v:  # hierarchical names: 20 searches the leaf name only
                rows = self._by_name(comodel, fg, v.rsplit(" / ", 1)[1], exact=v)
            for via in () if rows else ("product_tmpl_id", "product_id"):
                if fg.get(via, {}).get("type") == "many2one":  # e.g. a BoM named by its product
                    tid = self.resolve(fg[via].get("relation") or "", v)
                    if tid is not None:
                        rows = self._search(comodel, fg, [(via, "=", tid)], v)
                    break
            ids = sorted({r["id"] for r in rows if isinstance(r.get("id"), int)})
            if len(ids) > 1:
                raise _Unreadable(f"{comodel} '{v}' is ambiguous: {len(ids)} records {ids[:5]}")
            for r in rows:
                if r.get("active") is False:
                    self._archived.add((comodel, r["id"]))
            self._names[k] = ids[0] if ids else None
        return self._names[k]

    def archived(self, comodel: str, rid: int | None) -> bool:
        return (comodel, rid) in self._archived

    def _search(self, comodel, fg, dom, q) -> list[dict[str, Any]]:
        fields = ["display_name"] + [f for f in ("name", "default_code", "active") if f in fg]
        rows = self._r(comodel, "search_read", [dom], {"fields": fields, "limit": BATCH})
        if not isinstance(rows, list):
            raise _Unreadable(f"{comodel}: unexpected reply")
        if len(rows) >= BATCH:
            raise _Unreadable(f"{comodel} '{q}': {BATCH}+ candidate records (truncated)")
        return [r for r in rows if isinstance(r, dict)]

    def _by_name(self, comodel, fg, q: str, exact: str | None = None) -> list[dict[str, Any]]:
        """Candidates by display_name ilike / name / default_code, kept only on an exact hit
        ("=" on display_name is unreliable; products show "[CODE] Name")."""
        leaves: list[Any] = [("display_name", "ilike", q)]
        leaves += [(f, "=", q) for f in ("name", "default_code") if f in fg]
        dom = ["|"] * (len(leaves) - 1) + leaves
        rows = self._search(comodel, fg, dom, q)
        if exact is not None:
            return [r for r in rows if r.get("display_name") == exact]
        return [
            r for r in rows if q in (r.get("display_name"), r.get("name"), r.get("default_code"))
        ]

    # ------------------------------------------------------------ compare
    def _same(self, f: str, meta: Mapping[str, Any], exp: Any, got: Any) -> tuple[bool, Any]:
        t, rel = meta.get("type"), meta.get("relation") or ""
        if t == "many2one":
            gid = got[0] if isinstance(got, (list, tuple)) and got else None
            shown = list(got) if isinstance(got, (list, tuple)) else got
            if exp in (None, False):
                return gid is None, shown
            rid = self.resolve(rel, exp)
            if rid is not None and self.archived(rel, rid):
                return False, f"{shown} (expected target is archived)"
            return rid is not None and gid == rid, shown
        if t in _X2M:
            gids = sorted(got) if isinstance(got, list) else []
            want: set[int] = set()
            for e in exp if isinstance(exp, (list, tuple)) else [exp]:
                rid = self.resolve(rel, e)
                if rid is None or self.archived(rel, rid):
                    return False, gids
                want.add(rid)
            return want == set(gids), gids
        if (
            t in ("float", "monetary")
            and isinstance(exp, (int, float))
            and not isinstance(exp, bool)
        ):
            if not isinstance(got, (int, float)) or isinstance(got, bool):
                return False, got
            d = meta.get("digits")
            tol = 0.5 * 10 ** -int(d[1]) if isinstance(d, (list, tuple)) and len(d) == 2 else 1e-6
            return abs(float(got) - float(exp)) <= max(tol, 1e-9), got
        if exp is None:
            return got in (None, False), got
        return got == exp and type(got) is type(exp) or (
            isinstance(exp, int)
            and not isinstance(exp, bool)
            and isinstance(got, int)
            and not isinstance(got, bool)
            and got == exp
        ), got

    # ------------------------------------------------------------ items
    def check(self, it: Mapping[str, Any]) -> dict[str, Any]:
        kind, model = it.get("kind"), it.get("model")
        key, exp = it.get("key"), it.get("expected") or {}
        rels = it.get("relations") or {}
        res: dict[str, Any] = {"ref": it.get("ref"), "kind": kind, "model": model, "diffs": []}
        if it.get("verdict") in NOT_DESIGNED:
            return res | {"status": "not designed", "reason": it.get("reason") or it.get("verdict")}
        if (
            kind not in ("module", "record", "setting")
            or not isinstance(model, str)
            or not isinstance(key, dict)
            or not isinstance(exp, dict)
            or not isinstance(rels, dict)
            or not all(_scalar_ok(v) for v in [*key.values(), *exp.values(), *rels.values()])
            or (kind != "setting" and not key)
        ):
            return res | {"status": "not designed", "reason": "invalid item"}
        try:
            if kind == "setting":
                return self._setting(res, exp)
            return self._record(res, model, key, exp, rels, kind == "module")
        except _Unreadable as e:
            return res | {"status": "cannot-read", "reason": str(e)}

    def _setting(self, res: dict[str, Any], exp: dict[str, Any]) -> dict[str, Any]:
        model = "res.config.settings"
        fg = self.fields(model)
        if fg is None:
            return res | {"status": "cannot-read", "reason": f"{model}: no field list"}
        bad = sorted(f for f in exp if f not in fg)
        if bad or not exp:
            return res | {"status": "cannot-read", "reason": f"unknown setting(s) {bad}"}
        if self.partial:  # settings are per company; one company's view proves nothing
            return res | {"status": "cannot-read", "reason": f"settings: {self.partial}"}
        got = self._r(model, "default_get", [sorted(exp)], {})
        if not isinstance(got, dict):
            raise _Unreadable("settings: unexpected reply")
        for f, e in exp.items():
            ok, g = self._same(f, fg[f], e, got.get(f))
            if not ok:
                res["diffs"].append({"field": f, "expected": e, "found": g})
        return res | {"status": "differs" if res["diffs"] else "matches"}

    def _record(self, res, model, key, exp, rels, module) -> dict[str, Any]:
        fg = self.fields(model)
        if fg is None:
            return res | {
                "status": "cannot-read",
                "reason": f"model {model} not readable or absent",
            }
        plain_rels = {f: v for f, v in rels.items() if f != "group" and not _is_ref(v)}
        used = set(key) | set(exp) | {f for f in rels if f != "group"}
        bad = sorted(f for f in used if f not in fg)
        if bad:
            return res | {"status": "cannot-read", "reason": f"{model} has no field(s) {bad}"}
        dom: list[Any] = []
        for f, v in key.items():
            t = fg[f].get("type")
            if t in _REL and v not in (None, False):
                rel = fg[f].get("relation") or ""
                for x in v if isinstance(v, (list, tuple)) and t in _X2M else [v]:
                    rid = self.resolve(rel, x)  # ambiguous raises -> cannot-read
                    if rid is None:
                        return res | {"status": "missing", "reason": f"{f} target '{x}' not found"}
                    if self.archived(rel, rid):
                        res["diffs"].append({"field": f, "expected": x, "found": "archived"})
                    dom.append((f, "in", [rid]) if t in _X2M else (f, "=", rid))
            else:
                dom.append((f, "=", v))
        want = sorted(set(exp) | set(plain_rels) | {f for f in rels if f in fg} - {"group"})
        extra = [f for f in ("active", "company_id") if f in fg]
        rows = self._r(
            model, "search_read", [dom], {"fields": sorted(set(want + extra)), "limit": 3}
        )
        if not isinstance(rows, list):
            raise _Unreadable(f"{model}: unexpected reply")
        partial = self.partial if "company_id" in fg and not module else None
        if not rows:
            if partial:
                return res | {"status": "cannot-read", "reason": f"not seen; {partial}"}
            return res | {
                "status": "missing",
                "reason": "no record with this key (access rules may hide records)",
            }
        if len(rows) > 1:
            return res | {
                "status": "differs",
                "reason": f"{len(rows)}+ records share this key",
                "found_ids": [r.get("id") for r in rows],
            }
        row = rows[0]
        res["id"] = row.get("id")
        if "company_id" in row:
            res["company"] = row["company_id"][1] if isinstance(row["company_id"], list) else None
        if row.get("active") is False:
            res["diffs"].append({"field": "active", "expected": True, "found": False})
        for f, e in [*exp.items(), *plain_rels.items()]:
            ok, g = self._same(f, fg[f], e, row.get(f))
            if not ok:
                res["diffs"].append({"field": f, "expected": e, "found": g})
        res["_row"], res["_fg"] = row, fg
        if partial:
            return res | {"status": "cannot-read", "reason": f"found, but {partial}"}
        return res | {"status": "differs" if res["diffs"] else "matches"}


def _is_ref(v: Any) -> bool:
    """A link to another design item (``model:key=val``), or a non-empty list of them."""
    if isinstance(v, list):
        return bool(v) and all(_is_ref(x) for x in v)
    return isinstance(v, str) and ":" in v and "=" in v.split(":", 1)[1]


def verify(spec: Any, call: Call, *, companies: Sequence[int] | None = None) -> dict[str, Any]:
    """Verify a design spec against a live database. Never writes; never raises on bad input."""
    if (
        not isinstance(spec, dict)
        or spec.get("spec_version") != 1
        or not isinstance(spec.get("items"), list)
        or not spec["items"]
        or spec.get("status") == "not enough input"
    ):
        return {"status": "not enough input", "summary": {}, "groups": {}, "items": []}
    v = Verifier(call, companies=companies)
    v._company_view()
    items = [i for i in spec["items"] if isinstance(i, dict)]
    out, by_ref = [], {}
    for n, it in enumerate(items):
        ref = it.get("ref") if isinstance(it.get("ref"), str) else None
        if n >= MAX_ITEMS:
            v.truncated = True
            r = {"ref": ref, "status": "cannot-read", "reason": f"read limit {MAX_ITEMS} items hit"}
        elif ref is not None and ref in by_ref:
            r = {"ref": ref, "status": "not designed", "reason": "duplicate ref in design"}
        else:
            r = v.check(it)
            r["_rels"] = it.get("relations") if isinstance(it.get("relations"), dict) else {}
            if ref is not None:
                by_ref[ref] = r
        out.append(r)
    _links(v, out, by_ref)
    summary = {s: sum(1 for r in out if r["status"] == s) for s in STATUSES}
    for r in out:
        for k in ("_row", "_fg", "_rels"):
            r.pop(k, None)
    status = "matches" if summary["matches"] == len(out) and not v.truncated else "attention"
    return {
        "status": status,
        "summary": summary,
        "truncated": v.truncated,
        "company_view": v.partial or "full",
        "groups": {s: [r["ref"] for r in out if r["status"] == s] for s in STATUSES},
        "items": out,
    }


def _links(v: Verifier, out: list[dict[str, Any]], by_ref: dict[str, dict[str, Any]]) -> None:
    """Downgrade matches whose linked item is broken; repeat until stable (cycle-safe)."""
    for _ in range(len(out) + 1):
        changed = False
        for r in out:
            if r["status"] != "matches":
                continue
            for f, val in (r.get("_rels") or {}).items():
                for target in val if isinstance(val, list) else [val]:
                    if not _is_ref(target):
                        continue
                    t = by_ref.get(target)
                    why = None
                    if t is None:
                        why = f"link {f} -> {target}: not in design"
                    elif t["status"] != "matches":
                        why = f"link {f} -> {target}: target {t['status']}"
                    elif f in (r.get("_fg") or {}):
                        got = (r.get("_row") or {}).get(f)
                        if r["_fg"][f].get("type") == "many2one":
                            gids = [got[0]] if isinstance(got, list) and got else []
                        else:
                            gids = got if isinstance(got, list) else []
                        if t.get("id") not in gids:
                            why = f"link {f} -> {target}: points to {got!r}, not id {t.get('id')}"
                    if why:
                        r["status"] = "differs"
                        r["diffs"].append({"link": f, "target": target, "reason": why})
                        changed = True
                        break
                if r["status"] != "matches":
                    break
        if not changed:
            return
