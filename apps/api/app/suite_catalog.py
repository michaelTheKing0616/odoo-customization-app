"""Configuration Suite: the setup catalog (stage 1).

Parses ``suite_data/odoo_config_catalog.md`` (the verified catalog of Odoo
configuration tasks) into task rows, resolves the mechanism that applies to a
given Odoo major version, and filters by what the live database has. Code owns
this registry; the AI never picks a mechanism.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).parent / "suite_data" / "odoo_config_catalog.md"
SUPPORTED = (17, 18, 19, 20)

# Section -> dependency rank (catalog section 4). Lower runs first.
_SECTION_RANK: dict[str, int] = {
    "2.1": 1, "2.2": 1, "2.5": 2, "2.3": 3, "2.17": 3, "2.4": 4, "2.6": 5, "2.7": 6,
    "2.8": 7, "2.9": 7, "2.10": 7, "2.11": 7, "2.12": 7, "2.13": 7, "2.14": 7, "2.16": 7,
    "2.19": 7, "2.20": 7, "2.15": 8, "2.18": 9, "2.21": 9,
}
# Tasks with their own rank inside a section.
_TASK_RANK: dict[str, int] = {"2.1#1": 0, "2.1#5": 2, "2.4#27": 2}
RANK_LABEL: dict[int, str] = {
    0: "Install apps", 1: "Apps and company", 2: "Country package and currencies",
    3: "Users, access and languages", 4: "Accounting from the package", 5: "Units, categories and products",
    6: "Warehouses and routes", 7: "App settings, mail, layouts", 8: "Automations", 9: "Imports and opening balances",
}

_MECH_KIND = {"S": "setting", "W": "wizard", "M": "records", "F": "button", "I": "import", "D": "data", "OB": "onboarding"}
_RISK = {"L": "low", "M": "medium", "H": "high", "G": "guarded"}

# Tasks whose mechanism changes between versions (catalog section 0.2), resolved by code.
VERSION_MECHANISMS: dict[str, dict[int, dict[str, Any]]] = {
    "2.6#65": {
        17: {"kind": "records", "models": ["uom.category", "uom.uom"], "note": "Units sit in a category with a reference unit."},
        18: {"kind": "records", "models": ["uom.category", "uom.uom"], "note": "Units sit in a category with a reference unit."},
        19: {"kind": "records", "models": ["uom.uom"], "note": "Units point to a reference unit with a factor (relative_uom_id, relative_factor)."},
        20: {"kind": "records", "models": ["uom.uom"], "note": "Units point to a reference unit with a factor (relative_uom_id, relative_factor)."},
    },
    "2.6#70": {
        17: {"kind": "setting", "fields": ["group_stock_packaging"], "models": ["product.packaging"], "note": "Turn on packagings, then add them per product."},
        18: {"kind": "setting", "fields": ["group_stock_packaging"], "models": ["product.packaging"], "note": "Turn on packagings, then add them per product."},
        19: {"kind": "records", "models": ["product.uom"], "note": "Packagings are units on the product."},
        20: {"kind": "records", "models": ["product.uom"], "note": "Packagings are units on the product."},
    },
    "2.3#access": {
        17: {"kind": "records", "models": ["ir.model.access", "ir.rule"]},
        18: {"kind": "records", "models": ["ir.model.access", "ir.rule"]},
        19: {"kind": "records", "models": ["ir.model.access", "ir.rule"]},
        20: {"kind": "records", "models": ["ir.access"], "note": "Odoo 20 joins access lists and record rules into ir.access."},
    },
}
# Models that no longer exist on some versions (catalog 0.2). A task naming one is unavailable there.
GONE_IN: dict[str, int] = {
    "uom.category": 19, "hr.contract": 19, "account.group": 20, "ir.model.access": 20, "ir.rule": 20,
    "res.bank": 20, "hr.leave.type": 20,
}
ADDED_IN: dict[str, int] = {"hr.version": 19, "ir.access": 20, "product.uom": 19}


@dataclass
class Mechanism:
    kind: str
    raw: str
    models: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)


@dataclass
class Task:
    id: str
    section: str
    section_title: str
    num: str
    title: str
    mechanisms: list[Mechanism]
    bulk: str
    risk: str
    risk_note: str
    versions: str
    edition: str
    rank: int
    extra: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["rank_label"] = RANK_LABEL.get(self.rank, "")
        return out


_TICKS = re.compile(r"`([^`]+)`")


def _parse_mechanisms(cell: str) -> list[Mechanism]:
    out: list[Mechanism] = []
    for part in re.split(r";\s*(?=(?:S|W|M|F|I|D|OB):)", cell):
        m = re.match(r"\s*(S|W|M|F|I|D|OB):\s*(.*)", part, re.S)
        if not m:
            continue
        prefix, rest = m.group(1), m.group(2).strip()
        mech = Mechanism(kind=_MECH_KIND[prefix], raw=rest)
        for tok in _TICKS.findall(rest):
            tok = tok.strip()
            if prefix == "S":
                mech.fields.append(tok.split(".", 1)[1] if "." in tok and not tok.startswith("res.") else tok)
            elif prefix == "D":
                mech.modules.append(tok)
            elif prefix == "F" and "." in tok:
                model, _, meth = tok.rpartition(".")
                if model.count(".") >= 1:
                    mech.models.append(model)
                    mech.methods.append(meth)
                else:
                    mech.models.append(tok)
            elif re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", tok):
                # `res.company.currency_id` -> model res.company, field currency_id
                parts = tok.split(".")
                if prefix == "M" and len(parts) >= 3 and parts[-1] in {"active", "currency_id", "property_cost_method", "property_valuation"}:
                    mech.models.append(".".join(parts[:-1]))
                    mech.fields.append(parts[-1])
                else:
                    mech.models.append(tok)
        out.append(mech)
    return out


def _versions_ok(spec: str, major: int) -> bool:
    m = re.match(r"\s*(\d{2})\s*-\s*(\d{2})", spec)
    if m:
        return int(m.group(1)) <= major <= int(m.group(2))
    m = re.match(r"\s*(\d{2})\+", spec)
    if m:
        return major >= int(m.group(1))
    return True  # "changed in 19" style: resolved through VERSION_MECHANISMS


@lru_cache(maxsize=1)
def load_catalog() -> tuple[Task, ...]:
    text = CATALOG_PATH.read_text(encoding="utf-8")
    tasks: list[Task] = []
    section = title = ""
    header: list[str] = []
    for line in text.splitlines():
        h = re.match(r"^### (2\.\d+)\s+(.*)", line)
        if h:
            section, title, header = h.group(1), h.group(2).strip(), []
            continue
        if line.startswith("## "):
            section = "" if not line.startswith("## 2") else section
            continue
        if not section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "#":
            header = [c.lower() for c in cells]
            continue
        if not header or not cells or not cells[0].isdigit() or len(cells) < len(header):
            continue
        row = dict(zip(header, cells, strict=False))
        tid = f"{section}#{cells[0]}"
        if "mechanism" in row:
            mechs = _parse_mechanisms(row["mechanism"])
            name = row.get("task", "")
        else:  # 2.21 documents table
            mechs = [Mechanism(kind="records", raw=row.get("target in live db (code decides)", ""),
                               models=[t for t in _TICKS.findall(row.get("target in live db (code decides)", "")) if "." in t])]
            name = row.get("document (examples)", "")
        risk_cell = row.get("risk", "")
        rk = re.match(r"\s*([LMHG])", risk_cell)
        tasks.append(Task(
            id=tid, section=section, section_title=title, num=cells[0], title=re.sub(r"\*\*", "", name),
            mechanisms=mechs, bulk=row.get("bulk", ""), risk=_RISK.get(rk.group(1) if rk else "", "medium"),
            risk_note=risk_cell, versions=row.get("versions", ""), edition=row.get("ed.", ""),
            rank=_TASK_RANK.get(tid, _SECTION_RANK.get(section, 7)),
            extra={k: v for k, v in row.items() if k not in {"#", "task", "mechanism", "bulk", "risk", "versions", "ed."}},
        ))
    return tuple(tasks)


def get_task(task_id: str) -> Task | None:
    return next((t for t in load_catalog() if t.id == task_id), None)


def rank_of(task_id: str | None, default: int = 7) -> int:
    if not task_id:
        return default
    t = get_task(task_id)
    return t.rank if t else _TASK_RANK.get(task_id, default)


def task_for_model(model: str) -> Task | None:
    """First catalog task whose records mechanism names this model."""
    for t in load_catalog():
        for m in t.mechanisms:
            if m.kind in {"records", "import"} and model in m.models:
                return t
    return None


def resolve_for_version(task: Task, major: int) -> dict[str, Any]:
    """The mechanism code will use on this major version."""
    vm = VERSION_MECHANISMS.get(task.id, {}).get(major)
    if vm:
        return {"source": "version_table", **vm}
    models: list[str] = []
    fields_: list[str] = []
    kinds: list[str] = []
    for m in task.mechanisms:
        kinds.append(m.kind)
        models += [x for x in m.models if not (GONE_IN.get(x) and major >= GONE_IN[x]) and not (ADDED_IN.get(x) and major < ADDED_IN[x])]
        fields_ += m.fields
    return {"source": "catalog", "kind": kinds[0] if kinds else "unknown", "kinds": kinds,
            "models": sorted(set(models)), "fields": sorted(set(fields_))}


def availability(task: Task, major: int, *, models: set[str], settings_fields: set[str], edition: str) -> tuple[str, str]:
    """('available'|'not_here', plain reason). Code decides from the live database."""
    if major not in SUPPORTED:
        return "not_here", f"Odoo {major} is not supported."
    if not _versions_ok(task.versions, major):
        return "not_here", f"This task is not in Odoo {major}."
    if task.edition.strip().upper().startswith("EE") and edition != "enterprise":
        return "not_here", "This needs Odoo Enterprise."
    res = resolve_for_version(task, major)
    named = [x for m in task.mechanisms for x in m.models]
    if named and not res.get("models") and res.get("kind") == "records":
        return "not_here", f"Odoo {major} changed how this works and the old records do not exist here."
    need_models = [m for m in res.get("models", []) if m not in models]
    if res.get("kind") == "records" and res.get("models") and len(need_models) == len(res["models"]):
        return "not_here", "The app this needs is not installed."
    if res.get("kind") == "setting" and res.get("fields") and not any(f in settings_fields for f in res["fields"]):
        return "not_here", "This setting is not on this database (its app may not be installed)."
    return "available", ""


def catalog_for(major: int, *, models: set[str], settings_fields: set[str], edition: str) -> list[dict[str, Any]]:
    out = []
    for t in load_catalog():
        state, reason = availability(t, major, models=models, settings_fields=settings_fields, edition=edition)
        d = t.as_dict()
        d.update(mechanism=resolve_for_version(t, major), state=state, reason=reason)
        out.append(d)
    return out


def document_targets() -> list[str]:
    """Models the catalog lists as upload targets (2.21) plus every M:/I: model."""
    seen: list[str] = []
    for t in load_catalog():
        for m in t.mechanisms:
            if m.kind in {"records", "import"}:
                for x in m.models:
                    if x not in seen and re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", x):
                        seen.append(x)
    return seen
