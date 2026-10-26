"""Odoo-native design of a multi-step business process. Never writes to Odoo.

Input: a business description (structured steps) and, optionally, the BOT-FITGAP result
(``FitGap`` or its ``to_dict()``) for the same flow. Output: a design spec that
BOT-CONFIG-VERIFY consumes (``items``: kind, model, key, expected, relations) plus a plan of
steps that can only run later through the Bots write spine (guard + approval).

Grounding is the live inventory of the target database (installed modules, ``fields_get``),
never a fixed keyword table. Fail closed: unknown model/field -> "needs review" or
"needs-custom" with the exact reason; nothing is silently dropped; empty input ->
"not enough input".
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.bots.risk import classifier

SPEC_VERSION = 1
TEMPLATES = Path(__file__).with_name("templates.json")
Verdict = Literal["stock", "stock-install", "needs-custom", "needs review"]
ROUTE = "bots-write-spine"
_FG = json.loads((Path(__file__).parents[1] / "fitgap" / "fitgap_table.json").read_text())
ENTERPRISE_ONLY = frozenset(_FG["enterprise_modules"])
ENTERPRISE_MARKER = "web_enterprise"
MFG_CONCEPTS = {
    "manufacturing",
    "workorder",
    "by_product",
    "quality_point",
    "quality_measure",
    "quality_passfail",
    "subcontracting",
}


# ---------------------------------------------------------------- inventory


@dataclass(frozen=True)
class Inventory:
    """What the target database really has. ``models`` maps model -> its field names."""

    major: int
    installed: frozenset[str]
    installable: frozenset[str]
    models: Mapping[str, frozenset[str]]


def read_inventory(call: Callable[..., Any], models: Iterable[str]) -> Inventory:
    """Read-only: module list, then ``fields_get`` per model. A failed read = model absent."""
    from app.bots.fitgap.fitgap import read_env

    env = read_env(call)
    out: dict[str, frozenset[str]] = {}
    for m in sorted(set(models)):
        try:
            fg = call(m, "fields_get", [], {"attributes": ["type"]})
        except Exception:  # noqa: BLE001 - absent model on this database
            continue
        if isinstance(fg, dict) and fg:
            out[m] = frozenset(fg)
    return Inventory(env.major, env.installed, env.installable, out)


# ---------------------------------------------------------------- spec


@dataclass
class Item:
    kind: str  # module | record | setting
    model: str
    key: dict[str, Any]
    expected: dict[str, Any]
    relations: dict[str, Any] = field(default_factory=dict)
    module: str = ""
    step_ids: list[str] = field(default_factory=list)
    role: str = ""  # bom | bom_line | by_product | co_product | operation | ...
    verdict: Verdict = "needs review"
    reason: str = ""
    risk: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ref(self) -> str:
        return f"{self.model}:" + ",".join(f"{k}={v}" for k, v in sorted(self.key.items()))


@dataclass
class Design:
    status: Literal["designed", "not enough input"]
    items: list[Item]
    plan: list[dict[str, Any]]
    review: list[str]
    major: int | None

    def to_spec(self) -> dict[str, Any]:
        """The BOT-CONFIG-VERIFY contract."""
        return {
            "spec_version": SPEC_VERSION,
            "status": self.status,
            "odoo_major": self.major,
            "items": [{k: v for k, v in asdict(i).items()} | {"ref": i.ref} for i in self.items],
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_spec() | {"plan": self.plan, "review": self.review, "writes": 0}


def _load_templates() -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(TEMPLATES.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _fit_concepts(fit: Any) -> dict[str, list[tuple[str, str]]]:
    """step_id -> [(concept, status)] from a FitGap or its dict (absent -> {})."""
    if fit is None:
        return {}
    d = fit.to_dict() if hasattr(fit, "to_dict") else fit
    out: dict[str, list[tuple[str, str]]] = {}
    for s in d.get("steps", []) or []:
        out[str(s.get("step_id"))] = [
            (str(c.get("concept")), str(c.get("status"))) for c in s.get("concepts", []) or []
        ]
    return out


def _fmt(v: Any, step: str, seq: int) -> Any:
    if v == "{seq}":
        return seq
    if v == "{code}":
        return _code(step)
    return v.replace("{step}", step) if isinstance(v, str) else v


class _Builder:
    def __init__(self) -> None:
        self.items: list[Item] = []
        self.by_ref: dict[str, Item] = {}
        self.review: list[str] = []

    def add(self, item: Item) -> Item:
        prev = self.by_ref.get(item.ref)
        if prev:  # shared record (shared input, shared work center): one item, many steps
            for mine, theirs, what in (
                (prev.expected, item.expected, "value"),
                (prev.relations, item.relations, "relation"),
            ):
                for k, v in theirs.items():
                    if k in mine and mine[k] != v:
                        msg = (
                            f"conflict on {prev.ref}: {what} {k} = {mine[k]!r} "
                            f"(steps {', '.join(prev.step_ids)}) vs {v!r} "
                            f"(steps {', '.join(item.step_ids)})"
                        )
                        prev.notes.append(msg)
                        prev.verdict, prev.reason = (
                            "needs review",
                            "conflicting values across steps",
                        )
                        self.review.append(msg)
                    else:
                        mine.setdefault(k, v)
            prev.step_ids += [s for s in item.step_ids if s not in prev.step_ids]
            prev.notes += [n for n in item.notes if n not in prev.notes]
            return prev
        self.items.append(item)
        self.by_ref[item.ref] = item
        return item


def _float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _num(
    v: Any,
    what: str,
    b: _Builder,
    sid: str,
    lo: float = 0.0,
    hi: float = math.inf,
    lo_ok: bool = False,
) -> float | None:
    """Validated number in range (lo, hi] (or [lo, hi] with lo_ok); else a review entry."""
    n = _float(v)
    if n is None:
        b.review.append(f"step {sid}: {what} {v!r} is not a finite number")
        return None
    if n > hi or n < lo or (n == lo and not lo_ok):
        rng = f"{'[' if lo_ok else '('}{lo:g}, {hi:g}]"
        b.review.append(f"step {sid}: {what} must be in {rng} (got {v!r})")
        return None
    return n


def _manufacturing(steps: list[dict[str, Any]], b: _Builder) -> None:
    b.add(
        Item(
            "module",
            "ir.module.module",
            {"name": "mrp"},
            {"state": "installed"},
            module="mrp",
            role="module",
        )
    )
    produced: dict[str, str] = {}  # product -> step producing it as main output
    for st in steps:
        for o in st.get("outputs", []) or []:
            if o.get("role", "main") == "main" and o.get("product"):
                produced[str(o["product"])] = str(st["id"])
    consumers: dict[str, list[str]] = {}
    for st in steps:
        for i in st.get("inputs", []) or []:
            consumers.setdefault(str(i.get("product")), []).append(str(st["id"]))
    for seq, st in enumerate(steps, 1):
        sid, name = str(st["id"]), str(st.get("name") or st["id"])
        mains = [o for o in st.get("outputs", []) or [] if o.get("role", "main") == "main"]
        wc_name = st.get("work_center")
        utilities = st.get("utilities", []) or []
        if wc_name:
            cost = 0.0
            for u in utilities:
                n = _num(
                    u.get("cost_per_hour"), f"utility {u.get('name')} cost", b, sid, lo_ok=True
                )
                cost += n or 0.0
            wc = Item(
                "record",
                "mrp.workcenter",
                {"name": wc_name},
                {"name": wc_name} | ({"costs_hour": round(cost, 4)} if utilities else {}),
                module="mrp",
                step_ids=[sid],
                role="work_center",
            )
            if utilities:
                wc.notes.append(
                    "shared utilities as work-center hourly cost: "
                    + ", ".join(str(u.get("name")) for u in utilities)
                )
            b.add(wc)
        elif utilities:
            b.review.append(f"step {sid}: utilities given but no work center to carry their cost")
        if not mains:
            if st.get("inputs") or st.get("checks"):
                b.review.append(
                    f"step {sid}: no main output, so no bill of materials; "
                    "say what the step produces"
                )
            continue
        if len(mains) > 1:
            b.review.append(
                f"step {sid}: {len(mains)} main outputs; Odoo BoMs have one "
                "main product, mark the others as co_product"
            )
        main = str(mains[0].get("product"))
        qty = _num(mains[0].get("qty", 1), "output qty", b, sid) or 1.0
        bom = b.add(
            Item(
                "record",
                "mrp.bom",
                {"product_tmpl_id": main},
                {"product_qty": qty, "type": "normal"},
                module="mrp",
                step_ids=[sid],
                role="bom",
            )
        )
        dur = None
        if st.get("duration_min") is not None:
            dur = _num(st["duration_min"], "duration (min)", b, sid)
        op = None
        if wc_name:
            op = b.add(
                Item(
                    "record",
                    "mrp.routing.workcenter",
                    {"bom_id": main, "name": name},
                    {"sequence": seq * 10} | ({"time_cycle_manual": dur} if dur else {}),
                    relations={
                        "bom_id": bom.ref,
                        "workcenter_id": f"mrp.workcenter:name={wc_name}",
                    },
                    module="mrp",
                    step_ids=[sid],
                    role="operation",
                )
            )
        for i in st.get("inputs", []) or []:
            p = str(i.get("product"))
            if i.get("utility"):
                if not wc_name:
                    b.review.append(
                        f"step {sid}: utility input {p} needs a work center to carry its cost"
                    )
                continue
            line = Item(
                "record",
                "mrp.bom.line",
                {"bom_id": main, "product_id": p},
                {"product_qty": _num(i.get("qty", 1), f"input {p} qty", b, sid) or 1.0},
                relations={"bom_id": bom.ref} | ({"operation_id": op.ref} if op else {}),
                module="mrp",
                step_ids=[sid],
                role="bom_line",
            )
            if len(set(consumers.get(p, []))) > 1:
                line.notes.append(
                    "shared input: consumed by steps " + ", ".join(sorted(set(consumers[p])))
                )
            if p in produced and produced[p] != sid:
                line.notes.append(f"made by step {produced[p]} (multi-level BoM)")
            b.add(line)
        for o in st.get("outputs", []) or []:
            role = o.get("role", "main")
            if role == "main":
                continue
            if role not in ("by_product", "co_product"):
                b.review.append(
                    f"step {sid}: output role {role!r} unknown (main | by_product | co_product)"
                )
                continue
            p = str(o.get("product"))
            exp: dict[str, Any] = {
                "product_qty": _num(o.get("qty", 1), f"{role} {p} qty", b, sid) or 1.0
            }
            if role == "co_product":
                share = o.get("cost_share")
                if share is not None:
                    share = _num(share, f"co-product {p} cost share", b, sid, 0, 100, lo_ok=True)
                if share is None:
                    b.review.append(f"step {sid}: co-product {p} needs a cost share (%)")
                else:
                    exp["cost_share"] = share
            bp = Item(
                "record",
                "mrp.bom.byproduct",
                {"bom_id": main, "product_id": p},
                exp,
                relations={"bom_id": bom.ref} | ({"operation_id": op.ref} if op else {}),
                module="mrp",
                step_ids=[sid],
                role=role,
            )
            if consumers.get(p) and p not in produced:
                bp.notes.append(
                    "recirculated: consumed by steps " + ", ".join(sorted(set(consumers[p])))
                )
            b.add(bp)
        for c in st.get("checks", []) or []:
            _check(c, sid, main, op, b)
    _loops(steps, produced, b)


def _check(c: Mapping[str, Any], sid: str, main: str, op: Item | None, b: _Builder) -> None:
    kind = c.get("type", "passfail")
    if kind not in ("passfail", "measure"):
        b.review.append(f"step {sid}: check type {kind!r} unknown (passfail | measure)")
        return
    title = str(c.get("name") or f"{sid} check")
    exp: dict[str, Any] = {"title": title, "test_type": kind}
    if kind == "measure":
        lo, hi = _float(c.get("min")), _float(c.get("max"))
        if lo is None or hi is None or lo > hi:
            b.review.append(f"step {sid}: measure check {title!r} needs min <= max")
        else:
            exp |= {
                "norm": (lo + hi) / 2,
                "tolerance_min": lo,
                "tolerance_max": hi,
            }
    b.add(
        Item(
            "record",
            "quality.point",
            {"title": title, "product_ids": main},
            exp,
            relations={"product_ids": [main]} | ({"operation_id": op.ref} if op else {}),
            module="quality_control",
            step_ids=[sid],
            role="quality_point",
        )
    )


def _loops(steps: list[dict[str, Any]], produced: dict[str, str], b: _Builder) -> None:
    """Recirculation: allowed as by-product -> component; a main-product cycle is refused."""
    graph: dict[str, set[str]] = {}
    for st in steps:
        mains = [
            str(o["product"])
            for o in st.get("outputs", []) or []
            if o.get("role", "main") == "main" and o.get("product")
        ]
        for m in mains[:1]:
            graph[m] = {
                str(i.get("product")) for i in st.get("inputs", []) or [] if not i.get("utility")
            }
        if st.get("loop_to") and str(st["loop_to"]) not in {str(s["id"]) for s in steps}:
            b.review.append(f"step {st['id']}: loop_to {st['loop_to']!r} is not a step")

    colour: dict[str, int] = {}  # 0 white, 1 on stack, 2 done
    cycles: list[list[str]] = []
    for root in graph:
        if colour.get(root):
            continue
        stack: list[tuple[str, list[str]]] = [(root, sorted(d for d in graph[root] if d in graph))]
        path = [root]
        colour[root] = 1
        while stack:
            node, todo = stack[-1]
            if not todo:
                colour[node] = 2
                stack.pop()
                path.pop()
                continue
            d = todo.pop()
            c = colour.get(d, 0)
            if c == 1:
                cycles.append(path[path.index(d) :] + [d])
            elif c == 0:
                colour[d] = 1
                path.append(d)
                stack.append((d, sorted(x for x in graph[d] if x in graph)))
    for r in cycles:
        b.review.append(
            "BoM cycle " + " -> ".join(r) + ": Odoo rejects recursive BoMs; "
            "model the recirculated stream as a separate by-product"
        )
        for i in b.items:
            if i.model == "mrp.bom" and i.key.get("product_tmpl_id") in r:
                i.verdict, i.reason = "needs review", "part of a BoM cycle"


def _generic(
    steps: list[dict[str, Any]], fitc: dict[str, list[tuple[str, str]]], b: _Builder
) -> None:
    tpl = _load_templates()
    for seq, st in enumerate(steps, 1):
        sid, name = str(st["id"]), str(st.get("name") or st["id"])
        status = dict(fitc.get(sid, []))
        concepts = list(status) + list(st.get("concepts", []) or [])
        mapped = False
        for c in dict.fromkeys(concepts):
            if c in MFG_CONCEPTS:
                if not _is_mfg_step(st):
                    b.review.append(
                        f"step {sid}: manufacturing concept {c!r} but no inputs, outputs, "
                        "work center or checks to design from"
                    )
                continue
            for t in tpl.get(c, []):
                mapped = True
                exp = {k: _fmt(v, name, seq) for k, v in t["fields"].items()}
                rel = {k: _fmt(v, name, seq) for k, v in t.get("relations", {}).items()}
                kind = "setting" if t["model"] == "res.config.settings" else "record"
                key_v = exp.get(t["key"], rel.get(t["key"], name))
                it = b.add(
                    Item(
                        kind,
                        t["model"],
                        {t["key"]: key_v},
                        exp,
                        relations=rel,
                        module=t["module"],
                        step_ids=[sid],
                        role=c,
                    )
                )
                if t.get("needs"):
                    it.verdict = "needs review"
                    it.reason = "needs values not in the description: " + ", ".join(t["needs"])
                    b.review.append(f"step {sid}: {it.ref} {it.reason}")
                st_c = status.get(c)
                if st_c is not None and st_c not in ("ready", "install"):
                    it.verdict = "needs review"
                    it.reason = f"fit-gap concept {c!r} is {st_c!r} on this database"
                    b.review.append(f"step {sid}: {it.reason}")
            if c not in tpl and c not in MFG_CONCEPTS:
                b.review.append(f"step {sid}: concept {c!r} has no design template")
        appr = st.get("approval")
        amin = None
        if appr:
            mapped = True
            amin = _num(appr.get("min", 1), "approval min", b, sid, 1, 50, lo_ok=True)
            if amin is not None and amin != int(amin):
                b.review.append(f"step {sid}: approval min must be a whole number")
                amin = None
        if appr and amin is not None:
            grp = str(appr.get("group") or "")
            b.add(
                Item(
                    "record",
                    "approval.category",
                    {"name": f"{name} approval"},
                    {"name": f"{name} approval", "approval_minimum": int(amin)},
                    relations={"user_ids": appr.get("users", [])} | ({"group": grp} if grp else {}),
                    module="approvals",
                    step_ids=[sid],
                    role="approval",
                )
            )
        auto = st.get("automation")
        if auto:
            mapped = True
            m = str(auto.get("model") or "")
            if not m:
                b.review.append(f"step {sid}: automation needs a model")
            else:
                b.add(
                    Item(
                        "record",
                        "base.automation",
                        {"name": f"{name}: {auto.get('trigger', 'on_create_or_write')}"},
                        {"trigger": auto.get("trigger", "on_create_or_write")},
                        relations={"model_id": m},
                        module="base_automation",
                        step_ids=[sid],
                        role="automation",
                    )
                )
        if not mapped and not _is_mfg_step(st):
            b.review.append(f"step {sid} ({name}): no Odoo-native mapping found; needs review")


def _code(name: str) -> str:
    """Short journal code (max 5) derived from the step name; confirmed in review."""
    words = "".join(ch if ch.isalnum() else " " for ch in name).split()
    code = "".join(w[0] for w in words) if len(words) > 1 else "".join(words)
    return code.upper()[:5] or "JRNL"


def _is_mfg_step(st: Mapping[str, Any]) -> bool:
    return bool(st.get("inputs") or st.get("outputs") or st.get("work_center") or st.get("checks"))


# ---------------------------------------------------------------- grounding


def _ground(i: Item, inv: Inventory | None) -> None:
    if i.reason:  # already set fail-closed (e.g. BoM cycle)
        return
    if inv is None:
        i.verdict, i.reason = "needs review", "no live inventory read; nothing verified"
        return
    if i.kind == "module":
        name = i.key["name"]
        if name in inv.installed:
            i.verdict, i.reason = "stock", f"module {name} installed"
        elif name in inv.installable:
            i.verdict, i.reason = "stock-install", f"module {name} available, not installed"
        else:
            i.verdict, i.reason = "needs-custom", _absent(name, inv)
        return
    fields = inv.models.get(i.model)
    if fields is None:
        if i.module and i.module in inv.installable:
            i.verdict, i.reason = (
                "stock-install",
                (
                    f"model {i.model} comes with module {i.module} (available, not installed); "
                    "fields verified after install"
                ),
            )
        elif i.module and i.module in inv.installed:
            i.verdict, i.reason = (
                "needs review",
                (f"module {i.module} installed but model {i.model} not readable"),
            )
        elif i.module in ENTERPRISE_ONLY:
            i.verdict, i.reason = "needs-custom", f"model {i.model}: " + _absent(i.module, inv)
        elif not _caps(i, inv, ()):
            i.verdict, i.reason = (
                "needs review",
                (f"model {i.model} unknown on this database (module {i.module or '?'} absent)"),
            )
        return
    used = (set(i.key) | set(i.expected) | set(i.relations)) - {"group"}
    missing = sorted(f for f in used if f not in fields)
    if missing and not _caps(i, inv, missing):
        i.verdict, i.reason = (
            "needs-custom",
            (f"field(s) {', '.join(missing)} missing on {i.model} (Odoo {inv.major})"),
        )
    else:
        i.verdict, i.reason = "stock", f"{i.model} has all {len(used)} field(s) used"


def _caps(i: Item, inv: Inventory, fields: Iterable[str]) -> bool:
    """Version catalogue: stock Odoo N via a not-installed module? Sets verdict if decisive."""
    try:
        from app.bots.versioncaps import availability, load

        ed = "enterprise" if ENTERPRISE_MARKER in inv.installed else "community"
        v = availability(inv.major, ed, inv.installed, i.model, list(fields), i.module or None)
        c = load(inv.major)
        blocked = bool(c is None or c.blocked)
    except Exception:  # noqa: BLE001 - catalogue fault: keep the existing wording
        return False
    if v.status == "available-needs-install":
        chain = (
            f" (depends to install: {', '.join(v.missing_depends)})" if v.missing_depends else ""
        )
        i.verdict, i.reason = "stock-install", f"{i.model}: {v.reason}{chain}"
        return True
    if v.status == "not-in-this-version" and not fields and not blocked:
        i.verdict, i.reason = "needs-custom", f"{v.reason}"
        return True
    return False  # installed-ok/enterprise-only/unknown: keep existing fail-closed wording


def _absent(module: str, inv: Inventory) -> str:
    if module in ENTERPRISE_ONLY:
        ent = ENTERPRISE_MARKER in inv.installed | inv.installable
        return f"module {module} is Enterprise-only" + (
            "; not found on this Enterprise database" if ent else "; this is a Community database"
        )
    return f"module {module} not available on Odoo {inv.major}"


def _risk(i: Item) -> None:
    if i.kind == "module":
        tid = f"mod:{i.key['name']}:install"
    elif i.kind == "setting":
        tid = f"s:{next(iter(i.key))}"
    else:
        tid = f"m:{i.model}:create"
    try:
        fl = classifier.task_floor(
            tid, None if i.kind != "record" else frozenset(i.expected) | frozenset(i.relations)
        )
    except Exception:  # noqa: BLE001 - fail closed
        i.risk = "unclassified"
        return
    i.risk = fl[0] if fl else "R0"


def design(
    description: Mapping[str, Any] | None, fit: Any = None, inventory: Inventory | None = None
) -> Design:
    steps = list((description or {}).get("steps") or [])
    steps = [s for s in steps if isinstance(s, Mapping) and str(s.get("id") or "").strip()]
    if not steps:
        return Design(
            "not enough input",
            [],
            [],
            ["no process steps given"],
            inventory.major if inventory else None,
        )
    ids = [str(s["id"]) for s in steps]
    b = _Builder()
    if len(set(ids)) != len(ids):
        b.review.append(
            "duplicate step ids: " + ", ".join(sorted({x for x in ids if ids.count(x) > 1}))
        )
    fitc = _fit_concepts(fit)
    mfg = [s for s in steps if _is_mfg_step(s)]
    if mfg:
        _manufacturing(mfg, b)
    _generic(steps, fitc, b)
    for i in b.items:
        _ground(i, inventory)
        _risk(i)
    for sid in dict.fromkeys(ids):  # invariant: every step yields an item or a review entry
        if not any(sid in i.step_ids for i in b.items) and not any(
            r.startswith((f"step {sid}:", f"step {sid} (")) for r in b.review
        ):
            b.review.append(f"step {sid}: step produced nothing; needs review")
    plan = [
        {
            "seq": n,
            "ref": i.ref,
            "action": "install" if i.kind == "module" else "ensure",
            "route": ROUTE,
            "requires_approval": True,
            "risk": i.risk,
            "blocked": i.verdict in ("needs review", "needs-custom")
            or i.risk in (None, "unclassified"),
            "reason": i.reason,
        }
        for n, i in enumerate(b.items, 1)
    ]
    return Design("designed", b.items, plan, b.review, inventory.major if inventory else None)
