"""Code authorizes design scope: every new model must trace to an authorized requirement id.

Ids are attached deterministically where the design structure proves them (automations name
their requirement_id and target model; line models inherit their parent's ids). A design with
no authorized requirement left (everything declined) builds nothing. Untraced models stay as
optional suggestions, never silent builds."""
from __future__ import annotations

from typing import Any


def _ids(m: Any) -> set[str]:
    return {x for x in [getattr(m, "requirement_id", "") or ""] + list(getattr(m, "requirement_ids", None) or []) if x}


def attach_ids(design: Any) -> int:
    """Fill missing model ids from structure. Returns how many models got ids."""
    by_name = {m.name: m for m in design.new_models}
    got = 0
    for a in design.automations:
        rid, tgt = str(a.get("requirement_id") or ""), a.get("target_model")
        m = by_name.get(tgt)
        if rid and m is not None and rid not in _ids(m):
            had = bool(_ids(m))
            m.requirement_ids = list(m.requirement_ids or []) + [rid]
            got += 0 if had else 1
    # Fields on an existing record inherit the ids of the requirements code routed to that host
    # (stock checks) and of automations that target it.
    host_ids: dict[str, set[str]] = {}
    for c in getattr(design, "stock_checks", None) or []:
        h = (c.get("use") or {}).get("model") if c.get("choice") == "stock" else None
        if h:
            host_ids.setdefault(h, set()).update(str(x) for x in c.get("requirement_ids") or [] if x)
    for a in design.automations:
        if a.get("requirement_id") and a.get("target_model"):
            host_ids.setdefault(a["target_model"], set()).add(str(a["requirement_id"]))
    for e in design.stock_extensions:
        ids = sorted(host_ids.get(e.model, ()))
        for f in e.fields:
            if ids and not _ids(f):
                f.requirement_ids = list(ids)
                got += 1
    changed = True
    while changed:  # lines inherit their parent's ids (many2one to an id'd model)
        changed = False
        for m in design.new_models:
            if _ids(m):
                continue
            for f in m.fields:
                p = by_name.get(f.relation) if f.ttype == "many2one" else None
                if p is not None and p is not m and _ids(p):
                    m.requirement_ids = sorted(_ids(p))
                    got += 1; changed = True
                    break
    return got


def authorize(design: Any, authorized_ids: set[str], declined_any: bool,
              declined_ids: set[str] | None = None) -> dict[str, Any]:
    """Every model must trace to an approved, non-declined requirement id. With declines in
    play an untraced model is dropped; otherwise it stays as an optional suggestion."""
    attached = attach_ids(design)
    out = {"attached": attached, "dropped": [], "suggested": []}
    declined_ids = set(declined_ids or ()) - set(authorized_ids)
    approved = set(authorized_ids) - declined_ids
    if not authorized_ids and declined_any:
        out["dropped"] = [m.label or m.name for m in design.new_models]
        out["dropped_fields"] = [f"{e.model}.{f.name}" for e in design.stock_extensions for f in e.fields
                                 if not (_ids(f) & approved)]
        for e in design.stock_extensions:
            e.fields = [f for f in e.fields if _ids(f) & approved]
        design.stock_extensions = [e for e in design.stock_extensions if e.fields]
        design.new_models, design.automations, design.python_needed = [], [], []
        design.record_rules, design.menus = [], []
        design.notes = list(dict.fromkeys(list(design.notes) + [
            "Nothing was built: everything you asked for is outside what an Odoo app can do here (see Not built)."]))
        return out
    keep = []
    for m in design.new_models:
        ids = _ids(m)
        traced = bool(ids & approved)
        if not traced and (declined_any or (ids and ids <= declined_ids)):
            out["dropped"].append(m.label or m.name)  # declined context: no untraced build
            continue
        if not traced:
            m.suggested = True
            out["suggested"].append(m.label or m.name)
        keep.append(m)
    if out["dropped"]:
        gone = {m.name for m in design.new_models} - {m.name for m in keep}
        design.new_models = keep
        design.automations = [a for a in design.automations if a.get("target_model") not in gone]
        design.record_rules = [r for r in design.record_rules if (r or {}).get("model") not in gone]
        for m in keep:
            m.fields = [f for f in m.fields if f.relation not in gone]
    # Fields added to existing records follow the same rule as models.
    for e in design.stock_extensions:
        kept_f = []
        for f in e.fields:
            fids = _ids(f)
            traced = bool(fids & approved)
            if not traced and (declined_any or (fids and fids <= declined_ids)):
                out.setdefault("dropped_fields", []).append(f"{e.model}.{f.name}")
                continue
            kept_f.append(f)
        e.fields = kept_f
    design.stock_extensions = [e for e in design.stock_extensions if e.fields or not declined_any]
    if not design.new_models and not any(e.fields for e in design.stock_extensions) and declined_any:
        design.automations, design.python_needed, design.menus = [], [], []
    return out


def ensure_install_suggestions(design: Any, snap: Any, major: int | None = None) -> list[str]:
    """Extended stock models missing on the database whose app can be installed get an install
    suggestion (code-verified, version-aware module names)."""
    from app.ai_conversation.app_design import Integration
    from app.compat.odoo_versions import module_for_model

    if snap is None:
        return []
    index = getattr(snap, "index", None) or {}
    installable = getattr(snap, "installable", None) or {}
    added = []
    for e in design.stock_extensions:
        mod = module_for_model(e.model, major)
        if not e.model or e.model in index or not mod or mod not in installable:
            continue
        it = next((i for i in design.integrations if i.module == mod), None)
        if it is None:
            it = Integration(app=mod, module=mod, models=[], required=False, installed=False, status="available",
                             note="Install this Odoo app; the design builds on it.")
            design.integrations.append(it)
        it.installed, it.status, it.required = False, "available", False
        it.models = list(dict.fromkeys(list(it.models) + [e.model]))
        added.append(mod)
    return added
