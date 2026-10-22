"""Stock-first rework for curated domain packs (Oct 20 pack review).

A pack model that duplicates a stock Odoo model is dropped and every link to it is repointed to the
stock model. Inverse many2one fields that one2many fields or smart buttons rely on move onto the stock
model as an inherit extension. Automations owned by a dropped model are removed (stock owns that flow).
Nothing new is invented: every field kept comes from the pack's own declarations.
"""
from __future__ import annotations

import copy
from typing import Any


# Fields the stock model already has, by the pack field name without its "x_" prefix
# (synonyms included). A dropped model's other fields are carried onto the stock model.
_STOCK_HAS: dict[str, set[str]] = {
    "_all": {"name", "company_id", "active", "currency_id", "display_name"},
    "hr.employee": {"user_id", "partner_id", "department_id", "phone", "email", "notes", "job_title"},
    "hr.department": set(),
    "account.payment": {"partner_id", "amount", "status", "state", "date", "code"},
    "account.move": {"partner_id", "amount", "status", "state", "invoice_ref", "ref", "date"},
    "account.analytic.line": {"hours", "note", "date", "employee_id"},
    "maintenance.request": {"status", "state", "description", "reported_at", "employee_id", "date_start", "date_end", "code", "asset_id"},
    "maintenance.equipment": {"status", "notes", "tag", "employee_id", "partner_id"},
}


def _stock_has(stock: str, fname: str) -> bool:
    bare = fname[2:] if fname.startswith("x_") else fname
    return bare in _STOCK_HAS["_all"] or bare in _STOCK_HAS.get(stock, set())


def stock_first_rework(
    pack: dict[str, Any],
    mapping: dict[str, str],
    *,
    depends: list[str] | tuple[str, ...] = (),
    reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    out = copy.deepcopy(pack)
    models: list[dict[str, Any]] = [m for m in out.get("models") or [] if isinstance(m, dict)]
    dropped = {m["model"]: m for m in models if m.get("model") in mapping}
    kept = [m for m in models if m.get("model") not in mapping]
    by_id = {m["model"]: m for m in kept}

    def stock_entry(model: str) -> dict[str, Any]:
        if model not in by_id:
            entry = {"model": model, "description": model, "mode": "inherit", "fields": []}
            kept.append(entry)
            by_id[model] = entry
        return by_id[model]

    def add_inverse(stock: str, fname: str, relation: str) -> None:
        entry = stock_entry(stock)
        if any(f.get("name") == fname for f in entry["fields"]):
            return
        src_model = next((d for s, d in ((k, v) for k, v in dropped.items()) if mapping[s] == stock and any(f.get("name") == fname for f in d.get("fields") or [])), None)
        src = next((f for f in (src_model or {}).get("fields") or [] if f.get("name") == fname), None)
        field = copy.deepcopy(src) if src else {"name": fname, "ttype": "many2one", "string": fname[2:].replace("_id", "").replace("_", " ").title()}
        field["ttype"] = "many2one"
        field["relation"] = relation
        field.pop("required", None)  # never make a stock record require a pack link
        entry["fields"].append(field)

    for m in list(kept):
        for f in m.get("fields") or []:
            rel = f.get("relation")
            if rel in mapping:
                f["relation"] = mapping[rel]
                if f.get("ttype") == "one2many" and f.get("relation_field"):
                    add_inverse(mapping[rel], f["relation_field"], m["model"])
            if f.get("ttype") == "one2many" and f.get("relation") in mapping.values() and f.get("relation_field"):
                add_inverse(f["relation"], f["relation_field"], m["model"])

    # Carry each dropped model's own fields (e.g. doctor specialty) onto the stock model, as declared
    # x_ fields. Skip what stock already has, self-links, and links into the dropped set.
    for old_id, d in dropped.items():
        stock = mapping[old_id]
        entry_fields = stock_entry(stock)["fields"]
        for f in d.get("fields") or []:
            fname = str(f.get("name") or "")
            rel = f.get("relation")
            if not fname.startswith("x_") or _stock_has(stock, fname):
                continue
            if rel and (mapping.get(rel, rel) == stock or rel == stock):
                continue  # self-link or link to what is now the same stock model
            if f.get("ttype") == "one2many" and (rel in mapping or rel not in by_id):
                continue
            if any(g.get("name") == fname for g in entry_fields):
                continue
            g = copy.deepcopy(f)
            g.pop("required", None)
            if rel in mapping:
                g["relation"] = mapping[rel]
            entry_fields.append(g)

    buttons = []
    for b in out.get("smart_buttons") or []:
        b = dict(b)
        b["on_model"] = mapping.get(b.get("on_model"), b.get("on_model"))
        if b.get("related_model") in mapping:
            b["related_model"] = mapping[b["related_model"]]
            if b.get("relation_field"):
                add_inverse(b["related_model"], b["relation_field"], b["on_model"])
        buttons.append(b)
    out["smart_buttons"] = buttons
    out["automations"] = [a for a in out.get("automations") or [] if a.get("model") not in mapping]
    out["models"] = kept
    deps = list(out.get("depends") or [])
    out["depends"] = deps + [d for d in depends if d not in deps]
    hints = list(out.get("reuse_hints") or [])
    for old, stock in mapping.items():
        why = (reasons or {}).get(old) or f"Stock {stock}, never a parallel {old}"
        hints.append({"model": stock, "reason": why})
    out["reuse_hints"] = hints
    return out
