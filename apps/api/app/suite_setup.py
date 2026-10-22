"""Configuration Suite: Bulk Setup engine (stage 1).

A plan is a change set of steps. Code orders the steps (catalog dependency
rank, then explicit and implied dependencies; installs are their own first
wave), Check reads the database without writing and gives every step a
verdict plus a receipt, Apply runs wave by wave re-checking each step right
before it writes, and Undo is a new plan built from what a run changed, run in
reverse order through the same Check and Apply.

The AI never decides any of this; it may only propose steps. Money guard
rules live here too (catalog 7.4 and spec 20.11).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app import suite_catalog as cat

STEP_TYPES = ("install", "country_package", "setting", "create", "update", "units", "import", "remove", "access")
REVERSIBILITY = {"install": "one_way", "country_package": "one_way", "setting": "revert", "create": "remove",
                 "update": "revert", "units": "remove", "import": "remove", "remove": "one_way", "access": "remove"}
DEFAULT_TASK = {"install": "2.1#1", "country_package": "2.1#5", "units": "2.6#65"}
APPROVAL_THRESHOLD = 200  # D3 default; each database can change it

# ---------------------------------------------------------------- money guard
GUARDED_MODELS = frozenset({
    "account.account", "account.tax", "account.tax.group", "account.tax.repartition.line", "account.fiscal.position",
    "account.fiscal.position.tax", "account.fiscal.position.account", "account.journal", "account.move",
    "account.move.line", "account.payment", "account.payment.term", "account.payment.term.line", "account.group",
    "account.bank.statement", "account.bank.statement.line", "account.partial.reconcile", "account.full.reconcile",
    "account.reconcile.model", "account.analytic.line", "stock.valuation.layer", "account.chart.template",
})
# Allowed only while the database has no posted entries and no done stock moves.
CONDITIONAL_FIELDS = {("res.company", "currency_id"), ("product.category", "property_cost_method"),
                      ("product.category", "property_valuation")}
_GUARDED_SETTING = re.compile(r"(chart_template|currency_id|^tax|_tax|account_|fiscal|journal|lock_date|income_|expense_)")
_ROUTE = {
    "account.tax": "Taxes come from the country package. Load the package, then adjust taxes on Odoo's Taxes screen.",
    "account.account": "Accounts come from the country package's chart. Add accounts on Odoo's Chart of Accounts screen.",
    "account.move": "Entries are made in Odoo's Accounting screens. Opening balances are a separate, last step.",
}


def money_guard(step: dict[str, Any], *, posted_entries: int, done_moves: int) -> str | None:
    """A plain reason when the money guard refuses this step, else None."""
    t = step.get("type")
    inp = step.get("inputs") or {}
    if t in {"create", "update", "remove", "import"}:
        model = str(inp.get("model") or "")
        if model in GUARDED_MODELS or (t == "import" and model.startswith("account.")):
            return _ROUTE.get(model, "This is accounting data. The suite never writes it in bulk; use Odoo's own screen.")
        for f in (inp.get("values") or {}):
            if (model, f) in CONDITIONAL_FIELDS and (posted_entries or done_moves):
                return ("This can only change before the first posted entry and the first stock move. "
                        f"This database has {posted_entries} posted entries and {done_moves} done stock moves.")
    if t == "setting":
        for f in (inp.get("values") or {}):
            if str(f).startswith("module_"):
                return f"'{f}' installs an app. Add an install step instead so it runs first and on its own."
            if _GUARDED_SETTING.search(str(f)) and not str(f).startswith("group_"):
                return f"'{f}' is an accounting setting. Change it on Odoo's Accounting settings screen."
    if t in {"install", "country_package"} and posted_entries:
        return (f"This database has {posted_entries} posted entries. Installs and country packages run only on "
                "databases with no posted entries (decision D4).")
    return None


def needs_approval_step(step: dict[str, Any]) -> bool:
    if step.get("type") == "country_package":
        return True
    model = str((step.get("inputs") or {}).get("model") or "")
    if model.startswith("account.") or (model, "") in CONDITIONAL_FIELDS:
        return True
    return any((model, f) in CONDITIONAL_FIELDS for f in ((step.get("inputs") or {}).get("values") or {}))


# ---------------------------------------------------------------- plan shape
def normalise_steps(steps: list[dict[str, Any]], *, kind: str = "setup") -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for i, raw in enumerate(steps):
        s = dict(raw)
        s["id"] = str(s.get("id") or f"s{i + 1}")
        if s["id"] in seen:
            errors.append(f"Two steps share the id {s['id']}.")
        seen.add(s["id"])
        t = s.get("type")
        if t not in STEP_TYPES:
            errors.append(f"Step {s['id']}: unknown step type {t!r}.")
            continue
        if t == "remove" and kind != "undo":
            errors.append(f"Step {s['id']}: removing records only happens in an undo plan.")
        s["inputs"] = dict(s.get("inputs") or {})
        if t == "access" and not (s["inputs"].get("role") and s["inputs"].get("model")):
            errors.append(f"Step {s['id']}: say which role and which kind of record.")
        if t in {"create", "update", "remove", "import"} and not s["inputs"].get("model"):
            errors.append(f"Step {s['id']}: say which kind of record (model).")
        task = s.get("task") or DEFAULT_TASK.get(t)
        if not task and s["inputs"].get("model"):
            tk = cat.task_for_model(str(s["inputs"]["model"]))
            task = tk.id if tk else None
        if not task and t == "setting":
            task = _task_for_setting(list((s["inputs"].get("values") or {}).keys()))
        s["task"] = task
        s["depends_on"] = [str(d) for d in (s.get("depends_on") or [])]
        s.setdefault("company_id", None)
        s["source"] = s.get("source") or {"kind": "typed"}
        s["reversibility"] = REVERSIBILITY[t]
        s["cs_op"], s["cs_risk"] = changeset_op(s)
        tk = cat.get_task(task) if task else None
        s["risk"] = tk.risk if tk else ("guarded" if t == "country_package" else "medium")
        s["rank"] = 0 if t == "install" else (9 if t == "access" else cat.rank_of(task, 7))
        s.setdefault("label", _label(s))
        out.append(s)
    ids = {s["id"] for s in out}
    for s in out:
        for d in s["depends_on"]:
            if d not in ids:
                errors.append(f"Step {s['id']} waits for {d}, which is not in this plan.")
    return out, errors


def _task_for_setting(fields_: list[str]) -> str | None:
    for t in cat.load_catalog():
        for m in t.mechanisms:
            if m.kind == "setting" and any(f in m.fields for f in fields_):
                return t.id
    return None


def _label(s: dict[str, Any]) -> str:
    inp = s["inputs"]
    t = s["type"]
    if t == "install":
        return "Install " + ", ".join(inp.get("modules") or [])
    if t == "country_package":
        return f"Load the country package for {str(inp.get('country_code') or '').upper()}"
    if t == "setting":
        return "Change settings: " + ", ".join(list((inp.get("values") or {}).keys())[:4])
    if t == "units":
        return f"Add unit {inp.get('name')}"
    if t == "access":
        can = [k for k in ("read", "write", "create", "delete") if (inp.get("can") or {}).get(k)]
        return f"Let {inp.get('role')} {', '.join(can) or 'see nothing on'} {inp.get('model')}"
    if t == "import":
        return f"Import {len(inp.get('rows') or [])} rows into {inp.get('model')}"
    name = (inp.get("values") or {}).get("name") or (inp.get("match") or {}).get("name") or inp.get("id") or ""
    verb = {"create": "Add", "update": "Change", "remove": "Remove"}[t]
    return f"{verb} {inp.get('model')} {name}".strip()


def implied_deps(steps: list[dict[str, Any]]) -> dict[str, set[str]]:
    """A step that points at a record another step makes waits for it."""
    makes: dict[tuple[str, str], str] = {}
    for s in steps:
        inp = s["inputs"]
        if s["type"] == "create" and (inp.get("values") or {}).get("name"):
            makes[(str(inp["model"]), str(inp["values"]["name"]))] = s["id"]
        if s["type"] == "units" and inp.get("name"):
            makes[("uom.uom", str(inp["name"]))] = s["id"]
    deps: dict[str, set[str]] = {s["id"]: set(s["depends_on"]) for s in steps}
    for s in steps:
        inp = s["inputs"]
        for v in (inp.get("values") or {}).values():
            if isinstance(v, dict) and v.get("ref") and v.get("model"):
                maker = makes.get((str(v["model"]), str(v["ref"])))
                if maker and maker != s["id"]:
                    deps[s["id"]].add(maker)
            if isinstance(v, dict) and v.get("step"):
                deps[s["id"]].add(str(v["step"]))
        if s["type"] == "access" and inp.get("role"):
            maker = makes.get(("res.groups", str(inp["role"])))
            if maker and maker != s["id"]:
                deps[s["id"]].add(maker)
        if s["type"] == "units" and inp.get("reference"):
            maker = makes.get(("uom.uom", str(inp["reference"])))
            if maker and maker != s["id"]:
                deps[s["id"]].add(maker)
    return deps


def order_waves(steps: list[dict[str, Any]]) -> tuple[list[list[str]], list[str]]:
    """Waves of step ids. Installs first on their own; then by rank, then by dependencies."""
    deps = implied_deps(steps)
    by_id = {s["id"]: s for s in steps}
    wave: dict[str, int] = {}
    errors: list[str] = []
    visiting: set[str] = set()

    def place(sid: str, floor: int) -> int:
        if sid in wave:
            return wave[sid]
        if sid in visiting:
            errors.append(f"Steps wait for each other in a circle around {sid}.")
            return floor
        visiting.add(sid)
        w = floor
        for d in sorted(deps.get(sid, ())):
            if d in by_id:
                w = max(w, place(d, rank_start.get(by_id[d]["rank"], 0)) + 1)
        visiting.discard(sid)
        wave[sid] = w
        return w

    ranks = sorted({s["rank"] for s in steps})
    rank_start: dict[int, int] = {}
    nxt = 0
    for r in ranks:
        rank_start[r] = nxt
        for s in [x for x in steps if x["rank"] == r]:
            place(s["id"], nxt)
        nxt = max([wave[x["id"]] for x in steps if x["id"] in wave] + [nxt - 1]) + 1
    if errors:
        return [], sorted(set(errors))
    n = max(wave.values()) + 1 if wave else 0
    waves = [[s["id"] for s in steps if wave.get(s["id"]) == i] for i in range(n)]
    return [w for w in waves if w], []


def plan_hash(steps: list[dict[str, Any]]) -> str:
    keep = [{k: s.get(k) for k in ("id", "type", "task", "inputs", "depends_on", "company_id")} for s in steps]
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:24]


def receipt_args(connection_id: str, plan_id: str, phash: str) -> dict[str, Any]:
    return {"connection_id": connection_id, "plan_id": plan_id, "plan_hash": phash}


RECEIPT_TOOL = "suite.setup.apply"


# ---------------------------------------------------------------- live helpers
def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


def _try_x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    try:
        return _x(client, model, method, args, kw)
    except Exception:  # noqa: BLE001
        return None


def fault_line(exc: Exception) -> str:
    """The last meaningful line of an Odoo fault, not the traceback header."""
    raw = str(getattr(exc, "faultString", "") or exc).strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return (lines[-1] if lines else raw)[:240]


def _ctx(step: dict[str, Any]) -> dict[str, Any]:
    cid = step.get("company_id")
    return {"context": {"allowed_company_ids": [int(cid)]}} if cid else {}


def _access_model(client: Any) -> str:
    """Odoo 17-19 keep access rules in ir.model.access; Odoo 20 in ir.access."""
    major = int(getattr(getattr(client, "capabilities", None), "major", 0) or 0)
    return "ir.access" if major >= 20 else "ir.model.access"


def _plain_model(client: Any, model: str) -> str:
    """Odoo's own name for a record type ("Product Category"), lower-cased; the technical name only as a fallback."""
    try:
        rows = _x(client, "ir.model", "search_read", [[("model", "=", model)]], {"fields": ["name"], "limit": 1})
        if rows and rows[0].get("name"):
            return str(rows[0]["name"]).lower()
    except Exception:  # noqa: BLE001
        pass
    return model


def db_facts(client: Any) -> dict[str, Any]:
    """Counts the money guard and D4 need. Missing apps count as zero."""
    def count(model: str, dom: list[Any]) -> int:
        try:
            return int(_x(client, model, "search_count", [dom]))
        except Exception:  # noqa: BLE001  model not installed
            return 0
    return {"posted_entries": count("account.move", [("state", "=", "posted")]),
            "done_moves": count("stock.move", [("state", "=", "done")])}


def _fields(client: Any, model: str, cache: dict[str, Any]) -> dict[str, Any] | None:
    if model not in cache:
        try:
            cache[model] = _x(client, model, "fields_get", [], {"attributes": ["type", "relation", "required", "readonly", "string", "store"]})
        except Exception:  # noqa: BLE001
            cache[model] = None
    return cache[model]


def _find_by_name(client: Any, model: str, name: str) -> list[int]:
    try:
        ids = _x(client, model, "search", [[("name", "=", name)]], {"limit": 2})
        if not ids:
            ids = _x(client, model, "search", [[("name", "=ilike", name)]], {"limit": 2})
        return list(ids)
    except Exception:  # noqa: BLE001
        return []


def _norm(v: Any) -> Any:
    if isinstance(v, list | tuple) and len(v) == 2 and isinstance(v[0], int):
        return v[0]
    if v is None:
        return False
    return v


def resolve_values(client: Any, model: str, values: dict[str, Any], fmeta: dict[str, Any],
                   made: dict[str, int] | None = None) -> tuple[dict[str, Any], list[str], list[str]]:
    """Turn {'categ_id': {'ref': 'Office'}} into ids. Returns (values, missing refs, problems)."""
    out: dict[str, Any] = {}
    missing: list[str] = []
    problems: list[str] = []
    for f, v in values.items():
        meta = fmeta.get(f)
        if meta is None:
            problems.append(f"'{f}' is not a field on {model} here.")
            continue
        if isinstance(v, dict) and ("ref" in v or "step" in v):
            if v.get("step") and made and str(v["step"]) in made:
                out[f] = made[str(v["step"])]
                continue
            rel = meta.get("relation") or v.get("model")
            ids = _find_by_name(client, rel, str(v.get("ref"))) if rel and v.get("ref") else []
            if len(ids) == 1:
                out[f] = ids[0]
            elif len(ids) > 1:
                problems.append(f"More than one {rel} is called '{v.get('ref')}'. Say which one.")
            else:
                missing.append(f"{rel}:{v.get('ref') or v.get('step')}")
            continue
        out[f] = v
    return out, missing, problems


def _settings_current(client: Any, fields_: list[str], step: dict[str, Any]) -> dict[str, Any]:
    kw = {**_ctx(step)}
    vals = _x(client, "res.config.settings", "default_get", [fields_], kw)
    return {f: _norm(vals.get(f)) for f in fields_}


def _uom_major_fields(fmeta: dict[str, Any]) -> str:
    return "relative" if "relative_uom_id" in fmeta else "category"


# ---------------------------------------------------------------- check
# Each step's matching op in the shared change-set catalog (app/changeset/ops.py, read only),
# so plans can move into the shared store as-is once that store's files are free.
CS_OP = {"install": "module.install", "country_package": "module.install", "setting": "setting.set",
         "create": "data.create_batch", "units": "data.create_batch", "update": "data.update_batch",
         "import": "data.import_upsert", "remove": "data.unlink", "access": "access.create"}


def changeset_op(step: dict[str, Any]) -> tuple[str, str]:
    from app.changeset.ops import op_base_risk
    op = CS_OP.get(str(step.get("type")), "data.update_batch")
    return op, op_base_risk(op, dict(step.get("inputs") or {}))


def check_step(client: Any, step: dict[str, Any], *, facts: dict[str, Any], fcache: dict[str, Any],
               planned: set[tuple[str, str]], installing: list[str] | None = None) -> dict[str, Any]:
    """Look only. Never calls execute, create, write or a button.

    ``installing`` lists apps an earlier wave of the same plan installs. A step whose record type
    only appears after those installs is Ready "after install" and is checked again right before
    it runs (execute_run), so a fresh database can be set up in one plan."""
    r = _check_step(client, step, facts=facts, fcache=fcache, planned=planned)
    if installing and r["verdict"] == "blocked" and r["message"].endswith(
            ("is not on this database.", "Units are not installed here.")):
        model = "uom.uom" if step["type"] == "units" else str((step.get("inputs") or {}).get("model") or "")
        if _could_come_from(model, installing):
            return {**r, "verdict": "ready", "after_install": True,
                    "message": f"Checked again after {', '.join(installing)} {'is' if len(installing) == 1 else 'are'} installed, just before it runs."}
    return r


_MODEL_APPS = {"product.": {"product", "sale", "sale_management", "purchase", "stock", "account", "point_of_sale", "mrp"},
               "uom.": {"uom", "product", "sale", "sale_management", "purchase", "stock", "account", "mrp"},
               "account.": {"account", "sale", "sale_management", "purchase", "point_of_sale"},
               "stock.": {"stock", "mrp", "point_of_sale"}, "sale.": {"sale", "sale_management"},
               "crm.": {"crm"}, "hr.": {"hr", "hr_contract", "hr_holidays"}, "mrp.": {"mrp"},
               "purchase.": {"purchase"}, "project.": {"project"}, "fleet.": {"fleet"}}


def _could_come_from(model: str, installing: list[str]) -> bool:
    for prefix, apps in _MODEL_APPS.items():
        if model.startswith(prefix):
            return bool(apps & set(installing)) or any(a.startswith("l10n_") for a in installing) and prefix == "account."
    return bool(installing)  # unknown record type: an app being installed may bring it; re-checked at run


def _check_step(client: Any, step: dict[str, Any], *, facts: dict[str, Any], fcache: dict[str, Any],
                planned: set[tuple[str, str]]) -> dict[str, Any]:
    t = step["type"]
    inp = step["inputs"]
    res: dict[str, Any] = {"id": step["id"], "verdict": "ready", "message": "", "before": {}, "changes": {}}
    refused = money_guard(step, **facts)
    if refused:
        return {**res, "verdict": "blocked", "message": refused}
    try:
        if t == "import":
            from app import suite_import as si

            fm = _fields(client, str(inp["model"]), fcache)
            if fm is None:
                return {**res, "verdict": "blocked", "message": "This record type is not on this database."}
            return {**res, **si.check_import(client, step, fm)}
        if t == "remove" and inp.get("xmlids"):
            return {**res, "changes": {"remove": len(inp["xmlids"])}, "message": f"Will remove the {len(inp['xmlids'])} imported record(s) (or archive any in use)."}
        if t in {"install", "country_package"}:
            mods = list(inp.get("modules") or []) if t == "install" else [f"l10n_{str(inp.get('country_code') or '').lower()}"]
            rows = _x(client, "ir.module.module", "search_read", [[("name", "in", mods)]], {"fields": ["name", "state"]})
            found = {r["name"]: r["state"] for r in rows}
            unknown = [m for m in mods if m not in found]
            if unknown:
                return {**res, "verdict": "blocked", "message": "Odoo here has no app called " + ", ".join(unknown) + "."}
            todo = [m for m in mods if found[m] != "installed"]
            if not todo:
                return {**res, "verdict": "no_change", "message": "Already installed."}
            return {**res, "changes": {"install": todo}, "message": "Will install " + ", ".join(todo) + ". This cannot be undone here."}
        if t == "setting":
            values = dict(inp.get("values") or {})
            fmeta = _fields(client, "res.config.settings", fcache) or {}
            unknown = [f for f in values if f not in fmeta]
            if unknown:
                return {**res, "verdict": "blocked", "message": "These settings are not on this database: " + ", ".join(unknown) + "."}
            now = _settings_current(client, list(values), step)
            changes = {f: v for f, v in values.items() if now.get(f) != v}
            if not changes:
                return {**res, "verdict": "no_change", "message": "Already set this way.", "before": now}
            return {**res, "before": {f: now.get(f) for f in changes}, "changes": changes,
                    "message": f"{len(changes)} setting(s) will change."}
        if t == "access":
            model = str(inp["model"])
            if _fields(client, model, fcache) is None:
                return {**res, "verdict": "blocked", "message": f"{model} is not on this database."}
            role = str(inp.get("role") or "")
            gids = _find_by_name(client, "res.groups", role)
            if not gids and ("res.groups", role) not in planned:
                return {**res, "verdict": "needs_input", "message": f"There is no role called '{role}'. Add it first or pick an existing one."}
            can = {k: bool((inp.get("can") or {}).get(k)) for k in ("read", "write", "create", "delete")}
            name = f"ingenium {role} {model}"
            if _access_model(client) and _x(client, _access_model(client), "search_count", [[("name", "=", name)]]):
                return {**res, "verdict": "no_change", "message": f"{role} already has an access rule on {model}."}
            words = ", ".join(k for k, v in can.items() if v) or "nothing"
            return {**res, "changes": {"role": role, "model": model, **can},
                    "message": f"{role} will be able to: {words} on {_plain_model(client, model)}."}
        if t == "units":
            fmeta = _fields(client, "uom.uom", fcache)
            if fmeta is None:
                return {**res, "verdict": "blocked", "message": "Units are not installed here."}
            name, ref, factor = inp.get("name"), inp.get("reference"), inp.get("factor")
            if not name or not ref or not isinstance(factor, int | float) or factor <= 0:
                return {**res, "verdict": "needs_input", "message": "Give the unit a name, its reference unit and a factor above zero."}
            if _find_by_name(client, "uom.uom", str(name)):
                return {**res, "verdict": "no_change", "message": f"A unit called '{name}' already exists."}
            ref_ids = _find_by_name(client, "uom.uom", str(ref))
            if not ref_ids and ("uom.uom", str(ref)) not in planned:
                return {**res, "verdict": "needs_input", "message": f"There is no unit called '{ref}' to measure against."}
            how = _uom_major_fields(fmeta)
            return {**res, "changes": {"name": name, "reference": ref, "factor": factor, "mechanism": how},
                    "message": f"Will add {name} = {factor} x {ref}."}
        if t == "create":
            model = str(inp["model"])
            fmeta = _fields(client, model, fcache)
            if fmeta is None:
                return {**res, "verdict": "blocked", "message": f"{model} is not on this database."}
            values = dict(inp.get("values") or {})
            vals, missing, problems = resolve_values(client, model, values, fmeta)
            missing = [m for m in missing if tuple(m.split(":", 1)) not in planned]
            if problems or missing:
                msg = " ".join(problems + [f"Nothing called '{m.split(':', 1)[1]}' exists for {m.split(':', 1)[0]}." for m in missing])
                return {**res, "verdict": "needs_input", "message": msg}
            match = str(inp.get("match_field") or "name")
            if values.get(match) and _x(client, model, "search_count", [[(match, "=", values[match])]]):
                return {**res, "verdict": "no_change", "message": f"'{values[match]}' is already there."}
            # Only plain text fields count as "Odoo needs"; relational and choice fields usually get a
            # default or a computed value on create, so they are a note, and Odoo still decides at Run.
            req = [f for f, m in fmeta.items() if m.get("required") and not m.get("readonly") and f not in values
                   and m.get("type") not in {"one2many", "many2many", "boolean"}]
            if req:
                dflt = _try_x(client, model, "default_get", [req]) or {}
                req = [f for f in req if f not in dflt]
            hard = [f for f in req if fmeta[f].get("type") in {"char", "text", "html"}]
            if hard:
                return {**res, "verdict": "needs_input", "message": "Odoo needs: " + ", ".join(fmeta[f].get("string", f) for f in hard) + "."}
            soft = [fmeta[f].get("string", f) for f in req if f not in hard]
            note = f" Odoo fills in {', '.join(soft)} itself or refuses at Run." if soft else ""
            return {**res, "changes": values, "message": (f"Will add {_plain_model(client, model)} '{values['name']}'." if values.get("name") else f"Will add 1 {_plain_model(client, model)}.") + note}
        if t in {"update", "remove"}:
            model = str(inp["model"])
            fmeta = _fields(client, model, fcache)
            if fmeta is None:
                return {**res, "verdict": "blocked", "message": f"{model} is not on this database."}
            if inp.get("id"):
                ids = _x(client, model, "search", [[("id", "=", int(inp["id"]))]], {"context": {"active_test": False}})
            else:
                ids = _x(client, model, "search", [[(k, "=", v) for k, v in (inp.get("match") or {}).items()]], {"limit": 2})
            if not ids:
                if t == "remove":
                    return {**res, "verdict": "no_change", "message": "Already gone."}
                name = (inp.get("match") or {}).get("name")
                if name and (model, str(name)) in planned:
                    return {**res, "verdict": "ready", "after_create": True,
                            "message": f"Changes '{name}' once an earlier step adds it. Checked again just before it runs."}
                return {**res, "verdict": "needs_input", "message": "No record matches."}
            if len(ids) > 1:
                return {**res, "verdict": "needs_input", "message": "More than one record matches. Narrow it down."}
            if t == "remove":
                return {**res, "before": {"id": ids[0]}, "changes": {"remove": ids[0]}, "message": f"Will remove {model} #{ids[0]} (or archive it if something uses it)."}
            values = dict(inp.get("values") or {})
            vals, missing, problems = resolve_values(client, model, values, fmeta)
            if problems or missing:
                return {**res, "verdict": "needs_input", "message": " ".join(problems + [f"Missing {m}." for m in missing])}
            cur = _x(client, model, "read", [ids, list(vals)])[0]
            now = {f: _norm(cur.get(f)) for f in vals}
            changes = {f: v for f, v in vals.items() if now.get(f) != v}
            if not changes:
                return {**res, "verdict": "no_change", "message": "Already this way.", "before": {"id": ids[0]}}
            return {**res, "before": {"id": ids[0], **{f: now[f] for f in changes}}, "changes": changes,
                    "message": f"Will change {len(changes)} field(s) on {model} #{ids[0]}."}
    except Exception as exc:  # noqa: BLE001  Odoo refused a read
        return {**res, "verdict": "blocked", "message": f"Odoo refused the check: {fault_line(exc)}"}
    return {**res, "verdict": "blocked", "message": "Unknown step."}


def check_plan(client: Any, steps: list[dict[str, Any]], *, threshold: int = APPROVAL_THRESHOLD) -> dict[str, Any]:
    facts = db_facts(client)
    waves, errs = order_waves(steps)
    planned: set[tuple[str, str]] = set()
    for s in steps:
        inp = s["inputs"]
        if s["type"] == "create" and (inp.get("values") or {}).get("name"):
            planned.add((str(inp["model"]), str(inp["values"]["name"])))
        if s["type"] == "units" and inp.get("name"):
            planned.add(("uom.uom", str(inp["name"])))
    fcache: dict[str, Any] = {}
    results: dict[str, dict[str, Any]] = {}
    deps = implied_deps(steps)
    by_id = {s["id"]: s for s in steps}
    installing: list[str] = []
    for w in waves:
        wave_installs: list[str] = []
        for sid in w:
            r = check_step(client, by_id[sid], facts=facts, fcache=fcache, planned=planned, installing=list(installing))
            bad = [d for d in deps.get(sid, ()) if results.get(d, {}).get("verdict") in {"blocked", "needs_input", "waiting"}]
            if bad and r["verdict"] in {"ready", "needs_input"}:
                r = {**r, "verdict": "waiting", "message": "Waits for " + ", ".join(sorted(bad)) + ", which can't run yet."}
            results[sid] = r
            if r["verdict"] == "ready":
                wave_installs += list((r.get("changes") or {}).get("install") or [])
        installing += wave_installs
    counts = {k: sum(1 for r in results.values() if r["verdict"] == k) for k in ("ready", "no_change", "needs_input", "blocked", "waiting")}
    hard = sum(1 for s in steps if results.get(s["id"], {}).get("verdict") == "ready" and s["reversibility"] == "one_way")
    records = sum(1 for s in steps if results.get(s["id"], {}).get("verdict") == "ready" and s["type"] in {"create", "units", "update"})
    approval = any(needs_approval_step(s) and results.get(s["id"], {}).get("verdict") == "ready" for s in steps) or (hard + records) > threshold
    return {"facts": facts, "waves": waves, "errors": errs, "steps": results, "counts": counts,
            "can_apply": not errs and counts["blocked"] == 0 and counts["needs_input"] == 0 and counts["waiting"] == 0 and counts["ready"] > 0,
            "needs_approval": approval, "threshold": threshold}


# ---------------------------------------------------------------- apply one step
class StepChanged(Exception):
    """Odoo changed since the check; the step pauses instead of writing."""


def apply_step(client: Any, step: dict[str, Any], checked: dict[str, Any], made: dict[str, int]) -> dict[str, Any]:
    """Re-check, then write. Returns {'state', 'message', 'undo'}."""
    t = step["type"]
    inp = step["inputs"]
    facts = db_facts(client)
    refused = money_guard(step, **facts)
    if refused:
        raise StepChanged(refused)
    if t == "access":
        role, model = str(inp["role"]), str(inp["model"])
        gids = _find_by_name(client, "res.groups", role)
        if not gids:
            raise StepChanged(f"The role '{role}' is gone.")
        can = inp.get("can") or {}
        row = client.create_access_right({"name": f"ingenium {role} {model}", "model": model, "group_id": int(gids[0]),
                                          "perm_read": bool(can.get("read")), "perm_write": bool(can.get("write")),
                                          "perm_create": bool(can.get("create")), "perm_unlink": bool(can.get("delete"))})
        rid = int(getattr(row, "id", row))
        return {"state": "done", "message": f"{role} now has its access rule on {_plain_model(client, model)}.",
                "undo": {"model": _access_model(client), "id": rid}}
    if t in {"install", "country_package"}:
        mods = list(inp.get("modules") or []) if t == "install" else [f"l10n_{str(inp.get('country_code') or '').lower()}"]
        ids = _x(client, "ir.module.module", "search", [[("name", "in", mods), ("state", "!=", "installed")]])
        if not ids:
            return {"state": "no_change", "message": "Already installed.", "undo": None}
        _x(client, "ir.module.module", "button_immediate_install", [ids])
        return {"state": "done", "message": "Installed " + ", ".join(mods) + ".", "undo": {"one_way": True, "modules": mods}}
    if t == "setting":
        values = dict(inp.get("values") or {})
        now = _settings_current(client, list(values), step)
        for f, old in (checked.get("before") or {}).items():
            if now.get(f) != old and now.get(f) != values.get(f):
                raise StepChanged(f"'{f}' changed in Odoo after the check.")
        changes = {f: v for f, v in values.items() if now.get(f) != v}
        if not changes:
            return {"state": "no_change", "message": "Already set this way.", "undo": None}
        wid = _x(client, "res.config.settings", "create", [changes], _ctx(step))
        _x(client, "res.config.settings", "execute", [[wid]], _ctx(step))
        after = _settings_current(client, list(changes), step)
        off = [f for f, v in changes.items() if after.get(f) != v]
        if off:
            return {"state": "failed", "message": "Odoo did not keep: " + ", ".join(off) + ".", "undo": {"settings": {f: now.get(f) for f in changes}}}
        return {"state": "done", "message": f"Changed {len(changes)} setting(s).", "undo": {"settings": {f: now.get(f) for f in changes}}}
    if t == "units":
        fmeta = _x(client, "uom.uom", "fields_get", [], {"attributes": ["type"]})
        if _find_by_name(client, "uom.uom", str(inp["name"])):
            return {"state": "no_change", "message": "That unit already exists.", "undo": None}
        ref_ids = _find_by_name(client, "uom.uom", str(inp["reference"]))
        if not ref_ids:
            raise StepChanged(f"The unit '{inp['reference']}' is gone.")
        factor = float(inp["factor"])
        if "relative_uom_id" in fmeta:
            vals = {"name": inp["name"], "relative_uom_id": ref_ids[0], "relative_factor": factor}
        else:
            ref = _x(client, "uom.uom", "read", [[ref_ids[0]], ["category_id", "factor"]])[0]
            ref_ratio = float(ref.get("factor") or 1.0)  # units of ref per category reference
            vals = {"name": inp["name"], "category_id": _norm(ref["category_id"])}
            ratio = ref_ratio / factor  # this unit per category reference
            if abs(ratio - 1.0) < 1e-9:
                vals.update(uom_type="reference")
                raise StepChanged("A second reference unit can't be added to the same category.")
            if ratio < 1:
                vals.update(uom_type="bigger", factor_inv=1.0 / ratio)
            else:
                vals.update(uom_type="smaller", factor=ratio)
        new_id = _x(client, "uom.uom", "create", [vals])
        made[step["id"]] = int(new_id)
        return {"state": "done", "message": f"Added {inp['name']}.", "undo": {"model": "uom.uom", "id": int(new_id)}}
    if t == "create":
        model = str(inp["model"])
        fmeta = _x(client, model, "fields_get", [], {"attributes": ["type", "relation"]})
        values = dict(inp.get("values") or {})
        match = str(inp.get("match_field") or "name")
        if values.get(match) and _x(client, model, "search_count", [[(match, "=", values[match])]]):
            return {"state": "no_change", "message": f"'{values[match]}' is already there.", "undo": None}
        vals, missing, problems = resolve_values(client, model, values, fmeta, made)
        if missing or problems:
            raise StepChanged(" ".join(problems) or "Something it points at is missing: " + ", ".join(missing))
        new_id = _x(client, model, "create", [vals], _ctx(step))
        made[step["id"]] = int(new_id)
        label = (inp.get("values") or {}).get("name")
        return {"state": "done", "message": f"Added {_plain_model(client, model)} '{label}'." if label else f"Added 1 {_plain_model(client, model)}.", "undo": {"model": model, "id": int(new_id)}}
    if t == "update":
        model = str(inp["model"])
        before = dict(checked.get("before") or {})
        rid = int(before.get("id") or 0)
        if not rid:
            return {"state": "no_change", "message": "Nothing to change.", "undo": None}
        fmeta = _x(client, model, "fields_get", [], {"attributes": ["type", "relation"]})
        vals, missing, problems = resolve_values(client, model, dict(inp.get("values") or {}), fmeta, made)
        if missing or problems:
            raise StepChanged(" ".join(problems) or "Something it points at is missing.")
        cur = _x(client, model, "read", [[rid], list(vals)])[0]
        now = {f: _norm(cur.get(f)) for f in vals}
        for f, old in before.items():
            if f != "id" and now.get(f) != old and now.get(f) != vals.get(f):
                raise StepChanged(f"'{f}' changed in Odoo after the check.")
        changes = {f: v for f, v in vals.items() if now.get(f) != v}
        if not changes:
            return {"state": "no_change", "message": "Already this way.", "undo": None}
        _x(client, model, "write", [[rid], changes], _ctx(step))
        return {"state": "done", "message": f"Changed {model} #{rid}.", "undo": {"model": model, "id": rid, "values": {f: now[f] for f in changes}}}
    if t == "import":
        from app import suite_import as si

        return si.apply_import(client, step)
    if t == "remove" and inp.get("xmlids"):
        from app import suite_import as si

        return si.remove_imported(client, str(inp["model"]), list(inp["xmlids"]))
    if t == "remove":
        model = str(inp["model"])
        rid = int(inp.get("id") or 0)
        if not _x(client, model, "search", [[("id", "=", rid)]], {"context": {"active_test": False}}):
            return {"state": "no_change", "message": "Already gone.", "undo": None}
        try:
            _x(client, model, "unlink", [[rid]])
            return {"state": "done", "message": f"Removed {model} #{rid}.", "undo": {"one_way": True}}
        except Exception:  # noqa: BLE001  in use: archive instead
            fmeta = _x(client, model, "fields_get", [["active"]], {"attributes": ["type"]})
            if "active" in fmeta:
                _x(client, model, "write", [[rid], {"active": False}])
                return {"state": "done", "message": f"Archived {model} #{rid} because something uses it.", "undo": {"one_way": True}}
            raise
    raise StepChanged("Unknown step.")


# ---------------------------------------------------------------- undo
def undo_steps(plan_steps: list[dict[str, Any]], run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Reverse plan from what a run changed. One-way steps are listed, not undone."""
    by_id = {s["id"]: s for s in plan_steps}
    done = [r for w in run.get("waves", []) for r in w["steps"] if r.get("state") == "done" and r.get("undo")]
    out: list[dict[str, Any]] = []
    cannot: list[str] = []
    prev: str | None = None
    for r in reversed(done):
        src = by_id.get(r["id"], {})
        u = r["undo"]
        if u.get("one_way"):
            cannot.append(f"{src.get('label', r['id'])}: cannot be undone here.")
            continue
        sid = f"u_{r['id']}"
        if u.get("import"):
            s = {"id": sid, "type": "remove", "task": src.get("task"), "company_id": src.get("company_id"),
                 "inputs": {"model": u["model"], "xmlids": u["xmlids"]}, "label": f"Remove what this imported: {src.get('label', r['id'])}"}
        elif "settings" in u:
            s = {"id": sid, "type": "setting", "task": src.get("task"), "company_id": src.get("company_id"),
                 "inputs": {"values": u["settings"]}, "label": f"Put back: {src.get('label', r['id'])}"}
        elif "values" in u:
            s = {"id": sid, "type": "update", "task": src.get("task"), "company_id": src.get("company_id"),
                 "inputs": {"model": u["model"], "id": u["id"], "values": u["values"]}, "label": f"Put back: {src.get('label', r['id'])}"}
        else:
            s = {"id": sid, "type": "remove", "task": src.get("task"), "company_id": src.get("company_id"),
                 "inputs": {"model": u["model"], "id": u["id"]}, "label": f"Remove what this made: {src.get('label', r['id'])}"}
        s["depends_on"] = [prev] if prev else []
        s["source"] = {"kind": "undo", "ref": run.get("id")}
        out.append(s)
        prev = sid
    return out, cannot
