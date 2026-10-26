"""Variance control for any process in any Odoo area. Never writes to Odoo.

Compares ACTUAL (read live: ``fields_get`` + ``search_read``) against EXPECTED (record field,
caller standard, or a BOT-PROCESS-DESIGN spec item) per metric from the data-driven
``metrics.json``. Statuses: within / warn / breach / cannot-measure / no-data. Follow-ups are
plan steps only (``needs_approval``, L2/L3 from the risk classifier) for the Bots write spine.

Fail closed: missing model/field/tolerance, bad numbers, zero expected, unit or currency
mismatch, failed or truncated reads never produce a green result.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from app.bots.risk import classifier, rules

METRICS = Path(__file__).with_name("metrics.json")
ROUTE = "bots-write-spine"
STATUSES = ("within", "warn", "breach", "cannot-measure", "no-data")
MAX_ABS = 1e15
DEFAULT_LIMIT = 2000
EVIDENCE_CAP = 50
Call = Callable[..., Any]


def load_metrics(path: Path = METRICS) -> dict[str, dict]:
    data = json.loads(path.read_text())
    return {m["id"]: m for m in data["metrics"]}


# ---------------------------------------------------------------- values


def num(v: Any) -> float | None:
    """A finite, sane number or None. Bools, strings, NaN, inf and huge values are rejected."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) and abs(f) <= MAX_ABS else None


def _rid(v: Any) -> Any:
    if isinstance(v, (list, tuple)) and v:
        return v[0]
    return None if v is False else v


def _date(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v[:19] if " " in v else v[:10], fmt)
        except ValueError:
            continue
    return None


def _period(v: Any, period: str) -> str | None:
    d = _date(v)
    if d is None:
        return None
    return {"day": d.strftime("%Y-%m-%d"), "month": d.strftime("%Y-%m"), "year": str(d.year)}.get(
        period
    )


# ---------------------------------------------------------------- tolerance


def _tol(raw: Any) -> dict | None:
    """Validated tolerance or None (=> review needed). Keys: abs, pct, over{}, under{}."""
    if not isinstance(raw, Mapping):
        return None
    out: dict[str, Any] = {"breach_factor": 2.0}
    bf = raw.get("breach_factor")
    if bf is not None:
        if num(bf) is None or bf < 1:
            return None
        out["breach_factor"] = float(bf)
    for side in ("base", "over", "under"):
        src = raw if side == "base" else raw.get(side, {})
        if not isinstance(src, Mapping):
            return None
        lim = {}
        for k in ("abs", "pct"):
            if k in src:
                n = num(src[k])
                if n is None or n < 0:
                    return None
                lim[k] = n
        out[side] = lim
    if not any(out[s] for s in ("base", "over", "under")):
        return None
    return out


def evaluate(expected: Any, actual: Any, tol: dict | None, direction: str = "both") -> dict:
    e, a = num(expected), num(actual)
    r: dict[str, Any] = {"expected": e, "actual": a, "delta": None, "delta_pct": None}
    if a is None or e is None:
        r.update(status="no-data", reason="no actual value" if a is None else "no expected value")
        return r
    d = a - e
    pct = d / abs(e) * 100 if e != 0 else None
    r.update(delta=round(d, 6), delta_pct=None if pct is None else round(pct, 4))
    if direction not in ("both", "over", "under"):
        r.update(status="cannot-measure", reason=f"bad direction {direction!r}")
        return r
    side = "over" if d > 0 else "under"
    good = d != 0 and direction != "both" and side != direction
    if good:
        r["favourable"] = True
    if tol is None:
        r.update(status="warn", review_needed=True, reason="no tolerance set: review needed")
        return r
    lim = {**tol["base"], **tol[side]}
    if not lim:
        r.update(status="warn", review_needed=True, reason=f"no {side} tolerance: review needed")
        return r

    def ok(f: float) -> bool:
        for k, v in lim.items():
            if k == "abs" and abs(d) > v * f:
                return False
            if k == "pct" and (abs(d) > 0 if pct is None else abs(pct) > v * f):
                return False
        return True

    if ok(1.0):
        r["status"] = "within"
    elif ok(tol["breach_factor"]):
        r["status"] = "warn"
    else:
        r["status"] = "breach"
    if good and r["status"] != "within":
        r.update(status="warn", reason=f"favourable {side} deviation beyond tolerance")
        return r
    if pct is None and d != 0:
        r["reason"] = "expected is zero: percent undefined"
    return r


# ---------------------------------------------------------------- shared inputs


def split_shared(total: Any, consumers: Mapping[str, Mapping], tol: Any = None) -> list[dict]:
    """Split one shared input (e.g. a utility) across consumers by weight; variance per consumer.

    ``consumers``: {key: {"weight": w, "expected": e}}. Invalid total/weights -> cannot-measure.
    """
    t = num(total)
    ws = {k: num((c or {}).get("weight")) for k, c in consumers.items()}
    bad = t is None or not ws or t < 0 or any(w is None or w <= 0 for w in ws.values())
    s = 0.0 if bad else sum(ws.values())
    out = []
    for k in sorted(consumers, key=str):
        if bad or s <= 0:
            out.append(
                {"consumer": k, "status": "cannot-measure", "reason": "bad total or weights"}
            )
            continue
        alloc = t * ws[k] / s
        r = evaluate(consumers[k].get("expected"), alloc, _tol(tol))
        out.append({"consumer": k, "allocated": round(alloc, 6), **r})
    return out


# ---------------------------------------------------------------- standards


def _design_value(spec: Any, src: Mapping) -> tuple[float | None, str]:
    if not isinstance(spec, Mapping) or spec.get("spec_version") != 1:
        return None, "design spec missing or unsupported version"
    if spec.get("status") not in (None, "ok", "ready", "draft", "designed"):
        return None, f"design status {spec.get('status')!r}"
    vals = []
    for it in spec.get("items") or []:
        if not isinstance(it, Mapping) or it.get("kind") != src.get("kind"):
            continue
        if src.get("ref") and it.get("ref") != src["ref"]:
            continue
        exp = it.get("expected")
        if isinstance(exp, Mapping) and src.get("field") in exp:
            vals.append(exp[src["field"]])
    if not vals:
        return None, "no design standard"
    if len(set(map(repr, vals))) > 1:
        return None, "ambiguous design standard (several items; give ref)"
    n = num(vals[0])
    return (n, "") if n is not None else (None, "design standard not a number")


def _standard(std: Any, gkey: str) -> tuple[Any, Any, Any]:
    """(value, uom, currency) from a caller standard: scalar, {value,uom,currency}, or {by:{}}."""
    if isinstance(std, Mapping) and "by" in std:
        by = std["by"] if isinstance(std["by"], Mapping) else {}
        alt = gkey.split("|", 1)[1] if "|" in gkey else gkey
        std = by.get(gkey, by.get(alt, std.get("default")))
    if isinstance(std, Mapping):
        return std.get("value"), std.get("uom"), std.get("currency")
    return std, None, None


# ---------------------------------------------------------------- reads


class _Uom:
    """Unit conversion to a common root unit, probed per Odoo shape.

    17/18: ``category_id`` + ``factor`` (units per reference): to_root = q / factor.
    19+:   ``relative_uom_id`` chain + absolute ``factor``: to_root = q * factor, root = chain top.
    Unknown shape, unreadable unit, bad factor or a cyclic chain -> unit unknown (fail closed).
    """

    MAX_DEPTH = 12

    def __init__(self, call: Call) -> None:
        self.call, self.cache, self.raw, self.shape = call, {}, {}, None

    def _probe(self) -> str:
        if self.shape is None:
            try:
                f = self.call("uom.uom", "fields_get", [], {"attributes": ["type"]})
            except Exception:  # noqa: BLE001 - fail closed
                f = {}
            f = f if isinstance(f, Mapping) else {}
            if "factor" in f and "category_id" in f:
                self.shape = "category"
            elif "factor" in f and "relative_uom_id" in f:
                self.shape = "relative"
            else:
                self.shape = "none"
        return self.shape

    def _read(self, ids: list[int]) -> None:
        link = "category_id" if self.shape == "category" else "relative_uom_id"
        try:
            rows = self.call("uom.uom", "read", [ids], {"fields": ["factor", link]})
        except Exception:  # noqa: BLE001 - fail closed
            return
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, Mapping) and isinstance(r.get("id"), int):
                f = num(r.get("factor"))
                if f is not None and f > 0:
                    self.raw[r["id"]] = (f, _rid(r.get(link)))

    def load(self, ids: Iterable[Any]) -> bool:
        need = sorted({i for i in ids if isinstance(i, int)} - set(self.cache))
        if not need:
            return True
        shape = self._probe()
        if shape == "none":
            return False
        todo = [i for i in need if i not in self.raw]
        for _ in range(self.MAX_DEPTH):
            if todo:
                self._read(todo)
            if shape == "category":
                break
            todo = sorted(
                {p for f, p in self.raw.values() if isinstance(p, int) and p not in self.raw}
            )
            if not todo:
                break
        for i in need:
            if i not in self.raw:
                continue
            f, link = self.raw[i]
            if shape == "category":
                if link is not None:
                    self.cache[i] = (1.0 / f, ("c", link))
                continue
            cur, seen = i, set()
            while isinstance(self.raw.get(cur, (0, None))[1], int) and cur not in seen:
                seen.add(cur)
                cur = self.raw[cur][1]
            if cur in self.raw and self.raw[cur][1] is None and len(seen) < self.MAX_DEPTH:
                self.cache[i] = (f, ("r", cur))
        return all(i in self.cache for i in need)

    def conv(self, q: float | None, uom: Any, per_unit: bool = False) -> float | None:
        if q is None or uom not in self.cache:
            return None
        mult = self.cache[uom][0]
        return q / mult if per_unit else q * mult


DOMAIN_OPS = frozenset({"&", "|", "!"})
MAX_LIMIT = 20000
PERIODS = ("day", "month", "year")


def _dom_fields(dom: Any) -> set[str] | None:
    """Field names used by a domain, or None when the domain is malformed."""
    if not isinstance(dom, (list, tuple)):
        return None
    out = set()
    for c in dom:
        if isinstance(c, str) and c in DOMAIN_OPS:
            continue
        if not (isinstance(c, (list, tuple)) and len(c) == 3 and isinstance(c[0], str) and c[0]):
            return None
        out.add(c[0].split(".", 1)[0])
    return out


def _needed(m: Mapping, period: str | None, gb: list[str]) -> set[str]:
    a, e = m.get("actual") or {}, m.get("expected") or {}
    f = {a.get("field"), a.get("days_from"), e.get("field")}
    f |= {m.get("currency_field"), (a.get("ratio_filter") or {}).get("field")}
    f |= {g for g in gb if g != "id"}
    if period:
        f.add(m.get("date_field"))
    return {x for x in f if x}


def _cm(mid: str, reason: str, **kw: Any) -> dict:
    return {
        "metric": mid,
        "group": "*",
        "status": "cannot-measure",
        "reason": reason,
        "expected": None,
        "actual": None,
        "delta": None,
        "delta_pct": None,
        "evidence": [],
        **kw,
    }


def _bad_args(limit: Any, period: Any, rolling: Any) -> str:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        return f"bad limit (1..{MAX_LIMIT})"
    if period is not None and period not in PERIODS:
        return f"bad period {period!r}"
    if rolling is not None and (
        isinstance(rolling, bool) or not isinstance(rolling, int) or rolling < 1 or not period
    ):
        return "bad rolling window (positive int, needs period)"
    return ""


# ---------------------------------------------------------------- analyse


def analyse(
    call: Call,
    metric_ids: Iterable[str] | None = None,
    *,
    standards: Mapping[str, Any] | None = None,
    design: Any = None,
    tolerances: Mapping[str, Any] | None = None,
    domains: Mapping[str, list] | None = None,
    group_by: Mapping[str, list[str]] | None = None,
    recirculated: Mapping[str, Iterable[int]] | None = None,
    period: str | None = None,
    rolling: int | None = None,
    limit: int = DEFAULT_LIMIT,
    metrics: Mapping[str, Mapping] | None = None,
) -> dict:
    cat = dict(metrics) if metrics is not None else load_metrics()
    ids = sorted(set(metric_ids) if metric_ids is not None else cat)
    standards, tolerances = standards or {}, tolerances or {}
    rows: list[dict] = []
    truncated: list[str] = []
    uom = _Uom(call)
    bad = _bad_args(limit, period, rolling)
    for mid in ids:
        m = cat.get(mid)
        if bad:
            rows.append(_cm(mid, bad))
            continue
        if (
            not isinstance(m, Mapping)
            or not m.get("model")
            or not (m.get("actual") or {}).get("field")
        ):
            rows.append(_cm(mid, "unknown or incomplete metric definition"))
            continue
        res = _one(
            mid,
            m,
            call,
            uom,
            standards.get(mid),
            design,
            tolerances,
            domains,
            group_by,
            recirculated,
            period,
            rolling,
            limit,
        )
        if any(r.get("truncated") for r in res):
            truncated.append(mid)
        rows.extend(res)
    rows.sort(key=lambda r: (r["metric"], str(r["group"])))
    counts = {s: sum(r["status"] == s for r in rows) for s in STATUSES}
    roll = [r["rolling"]["status"] for r in rows if isinstance(r.get("rolling"), Mapping)]
    plan = _plan(rows, cat)
    return {
        "writes": 0,
        "route": ROUTE,
        "rows": rows,
        "summary": {
            **counts,
            "metrics": len(ids),
            "truncated": truncated,
            "review_needed": sum(bool(r.get("review_needed")) for r in rows),
            "rolling": {s: roll.count(s) for s in STATUSES},
        },
        "ok": bool(rows)
        and counts["within"] == len(rows)
        and not truncated
        and all(s == "within" for s in roll),
        "plan": plan,
    }


def _read_all(call, model, dom, fields, limit, m, fg) -> tuple[list, bool, str]:
    """search_read; with ``company_context`` one read per company in that company's context."""
    kw = {"fields": fields, "limit": limit + 1, "order": "id"}
    if not m.get("company_context"):
        recs = call(model, "search_read", [dom], kw)
        if not isinstance(recs, list) or not all(isinstance(r, Mapping) for r in recs):
            return [], False, "unreadable result"
        return recs[:limit], len(recs) > limit, ""
    comps = call("res.company", "search_read", [[]], {"fields": ["currency_id"], "order": "id"})
    if not isinstance(comps, list) or not comps:
        return [], False, "companies unreadable"
    out, trunc = [], False
    for c in comps:
        cid = c.get("id") if isinstance(c, Mapping) else None
        cur = _rid(c.get("currency_id")) if isinstance(c, Mapping) else None
        if not isinstance(cid, int) or cur is None:
            return [], False, "company or company currency unreadable"
        ctx = {"allowed_company_ids": [cid], "force_company": cid}
        recs = call(model, "search_read", [dom], {**kw, "context": ctx})
        if not isinstance(recs, list) or not all(isinstance(r, Mapping) for r in recs):
            return [], False, "unreadable result"
        trunc |= len(recs) > limit
        out += [{**r, "__company": cid, "__currency": cur} for r in recs[:limit]]
    return out, trunc, ""


def _one(
    mid, m, call, uom, std, design, tolerances, domains, group_by, recirc, period, rolling, limit
) -> list[dict]:
    model = m["model"]
    a, e = m["actual"], m.get("expected") or {}
    gb = list((group_by or {}).get(mid) or m.get("group_by") or [])
    if period and not m.get("date_field"):
        return [_cm(mid, "metric has no date_field for period grouping")]
    try:
        fg = call(model, "fields_get", [], {"attributes": ["type", "relation"]})
    except Exception:  # noqa: BLE001
        return [_cm(mid, f"model {model} not readable")]
    if not isinstance(fg, Mapping) or not fg:
        return [_cm(mid, f"model {model} missing")]
    dom = list(m.get("domain") or []) + list((domains or {}).get(mid) or [])
    dfields = _dom_fields(dom)
    if dfields is None:
        return [_cm(mid, "malformed domain")]
    need = _needed(m, period, gb) | dfields
    missing = sorted(need - set(fg))
    if missing:
        return [_cm(mid, f"missing fields on {model}: {', '.join(missing)}")]
    cand = m.get("uom_field")
    cand = [cand] if isinstance(cand, str) else list(cand or [])
    uf = next((c for c in cand if c in fg), None)
    if cand and not uf:
        return [_cm(mid, f"unit mismatch: no unit field on {model} ({', '.join(cand)})")]
    if m.get("company_context"):
        comp, cf = "__company", "__currency"
    else:
        comp = "company_id" if "company_id" in fg else None
        cf = m.get("currency_field")
    fields = sorted(need | {x for x in (uf, comp) if x and not x.startswith("__")})
    try:
        recs, trunc, why = _read_all(call, model, dom, fields, limit, m, fg)
    except Exception:  # noqa: BLE001
        return [_cm(mid, f"read failed on {model}")]
    if why:
        return [_cm(mid, why)]
    skip = set(recirc.get(mid, ()) if recirc else ())
    loop_n = sum(r.get("id") in skip for r in recs)
    recs = [r for r in recs if r.get("id") not in skip]
    if not recs:
        return [
            {
                **_cm(mid, "no records"),
                "status": "no-data",
                "truncated": trunc,
                "recirculated_excluded": loop_n,
            }
        ]
    if uf and not uom.load(_rid(r.get(uf)) for r in recs):
        return [_cm(mid, "unit mismatch: units unreadable", truncated=trunc)]
    groups: dict[str, list] = {}
    undated = []
    for r in recs:
        key = [f"company={_rid(r.get(comp))}"] if comp else []
        key += [f"{g}={r.get('id') if g == 'id' else _rid(r.get(g))}" for g in gb]
        if period:
            p = _period(r.get(m["date_field"]), period)
            if p is None:
                undated.append(r.get("id"))
                continue
            key.append(f"period={p}")
        groups.setdefault("|".join(key) or "all", []).append(r)
    tol = _tol(tolerances.get(mid, m.get("tolerance")))
    out = []
    for gk in sorted(groups):
        out.append(_group(mid, m, gk, groups[gk], std, design, tol, uom, uf, cf, a, e))
    if undated:
        ev = sorted(i for i in undated if isinstance(i, int))
        out.append(
            {
                **_cm(mid, "records without a date under period grouping"),
                "group": "period=undated",
                "evidence": ev[:EVIDENCE_CAP],
                "evidence_count": len(undated),
            }
        )
    for r in out:
        r["truncated"] = trunc
        r["recirculated_excluded"] = loop_n
        if trunc and r["status"] == "within":
            r.update(status="warn", reason="read truncated: not all records seen")
    if period and rolling:
        _rolling(
            [r for r in out if r["group"] != "period=undated"],
            rolling,
            tol,
            m.get("direction", "both"),
        )
    return out


def _group(mid, m, gk, recs, std, design, tol, uom, uf, cf, a, e) -> dict:
    ev = sorted(r.get("id") for r in recs if isinstance(r.get("id"), int))
    base = {
        "metric": mid,
        "group": gk,
        "unit": m.get("unit"),
        "evidence": ev[:EVIDENCE_CAP],
        "evidence_count": len(ev),
    }

    def cm(reason: str, status: str = "cannot-measure") -> dict:
        return {
            **base,
            "status": status,
            "reason": reason,
            "expected": None,
            "actual": None,
            "delta": None,
            "delta_pct": None,
        }

    curs = {_rid(r.get(cf)) for r in recs} if cf else set()
    if len(curs) > 1:
        return cm("currency mismatch within group")
    if cf and None in curs:
        return cm("currency mismatch: record without currency")
    uoms = {_rid(r.get(uf)) for r in recs} if uf else set()
    if uf and (None in uoms or not all(u in uom.cache for u in uoms)):
        return cm("unit mismatch: record without a known unit")
    if uf and len({uom.cache[u][1] for u in uoms}) > 1:
        return cm("unit mismatch: incompatible units")
    per_unit = m.get("uom_kind") == "per_unit"
    ru = next(iter(uoms)) if len(uoms) == 1 else None

    # expected from a caller standard is resolved first: its unit decides normalisation
    src = "field" if e.get("field") else ("design" if e.get("design") and std is None else "std")
    su = None
    if src == "std":
        v, su, sc = _standard(std, gk)
        expected = num(v)
        if v is not None and expected is None:
            return cm("standard is not a number")
        if expected is None:
            return cm("no standard given", "no-data")
        if cf and sc is None:
            return cm("currency mismatch: standard has no currency")
        if cf and sc != next(iter(curs), None):
            return cm("currency mismatch: standard vs records")
        if uf and su is None and ru is None:
            return cm("unit mismatch: mixed record units and standard has no unit")
        if uf and su is not None and su != ru:
            if not uom.load([su]) or uom.cache[su][1] != uom.cache[next(iter(uoms))][1]:
                return cm("unit mismatch: standard unit not convertible")
    norm = bool(uf) and (ru is None or (su is not None and su != ru))

    def val(r: Mapping, field: str | None, days_from: str | None = None) -> float | None:
        if days_from:
            d1, d0 = _date(r.get(field)), _date(r.get(days_from))
            return None if not d1 or not d0 else (d1 - d0).total_seconds() / 86400
        v = num(r.get(field))
        return uom.conv(v, _rid(r.get(uf)), per_unit) if norm else v

    act = [val(r, a["field"], a.get("days_from")) for r in recs]
    if any(x is None for x in act):
        return cm("bad or missing actual value (non-number, NaN, huge, bool or date)")
    agg = m.get("aggregate", "sum")
    rf = a.get("ratio_filter")
    if rf:
        tot = sum(act)
        part = sum(x for x, r in zip(act, recs, strict=True) if bool(_rid(r.get(rf["field"]))))
        if tot == 0:
            return cm("ratio denominator is zero", "no-data")
        actual = part / tot
    else:
        actual = sum(act) / len(act) if agg == "avg" else sum(act)
    if src == "field":
        ex = [val(r, e["field"]) for r in recs]
        if any(x is None for x in ex):
            return cm("bad or missing expected value on record")
        expected = sum(ex) / len(ex) if agg == "avg" else sum(ex)
    elif src == "design":
        expected, why = _design_value(design, e["design"])
        if expected is None:
            return cm(why, "no-data" if why == "no design standard" else "cannot-measure")
    else:
        if norm:
            expected = uom.conv(expected, su if su is not None else ru, per_unit)
        if agg == "sum" and not rf and m.get("standard_per") == "record":
            expected *= len(recs)
    if expected is not None and "scale" in e and num(e["scale"]) is not None:
        expected *= e["scale"]
    r = evaluate(expected, actual, tol, m.get("direction", "both"))
    if norm and not r.get("reason"):
        r["reason"] = "normalised to a common unit"
    return {**base, **r}


def _rolling(out: list[dict], n: int, tol, direction) -> None:
    series: dict[str, list[dict]] = {}
    for r in out:
        series.setdefault(r["group"].rsplit("|period=", 1)[0], []).append(r)
    for rs in series.values():
        rs.sort(key=lambda r: r["group"])
        for i, r in enumerate(rs):
            win = rs[max(0, i - n + 1) : i + 1]
            if any(w["status"] in ("cannot-measure", "no-data") for w in win):
                r["rolling"] = {"status": "cannot-measure", "window": len(win)}
                continue
            ev = evaluate(
                sum(w["expected"] for w in win), sum(w["actual"] for w in win), tol, direction
            )
            r["rolling"] = {"window": len(win), **ev}


# ---------------------------------------------------------------- plan


def _level(task: str, fields: Iterable[str] | None) -> int:
    try:
        fl = classifier.task_floor(task, frozenset(fields) if fields else None)
    except Exception:  # noqa: BLE001 - unclassifiable -> highest tier
        return 3
    return 3 if fl and fl[0] in rules.IRRECOVERABLE else 2


def _plan(rows: list[dict], cat: Mapping[str, Mapping]) -> list[dict]:
    flagged: dict[str, list[str]] = {}
    for r in rows:
        rs = r.get("rolling") if isinstance(r.get("rolling"), Mapping) else {}
        if r["status"] in ("warn", "breach") or rs.get("status") in ("warn", "breach"):
            flagged.setdefault(r["metric"], []).append(str(r["group"]))
    steps = []
    for mid in sorted(flagged):
        for f in (cat.get(mid) or {}).get("followups") or []:
            if not isinstance(f, Mapping) or not f.get("action") or not f.get("task"):
                continue
            steps.append(
                {
                    "metric": mid,
                    "action": f["action"],
                    "task_id": f["task"],
                    "groups": sorted(flagged[mid]),
                    "needs_approval": True,
                    "level": _level(f["task"], f.get("fields")),
                    "route": ROUTE,
                    "writes": 0,
                }
            )
    return steps
