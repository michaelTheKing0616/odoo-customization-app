"""Code-side passes that keep a design on the database's real models and fields.

Run on every authorized (checklist) design, and again after a planned app is installed:
the AI's design is re-checked against the live snapshot, never trusted as is.

- map_to_stock_fields: an extension field that copies a field the stock model already has
  (same type and comodel, same name or label) is dropped and the stock field is used instead.
- retarget_automations: an automation or custom-code piece aimed at a model that does not
  exist moves to the existing record its requirement extends, or is left out with a note.
- trace_extension_fields: on an "add to an existing app" design every added field must trace
  to an approved requirement; the rest are left out.
- sane_field_names: technical names stay short and come from the field label.
"""
from __future__ import annotations

import re
from typing import Any

_REL = {"many2one", "one2many", "many2many"}
_TEXT = {"char", "text", "html"}
_DATES = {"date", "datetime"}
_MAX_NAME_WORDS = 4
_MAX_LABEL_WORDS = 5  # longer labels are sentences from the brief, not field names


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _stem(name: str) -> str:
    n = re.sub(r"^x_(studio_)?", "", (name or "").lower())
    return re.sub(r"_ids?$", "", n)


def _same_kind(a: str, b: str) -> bool:
    return a == b or (a in _TEXT and b in _TEXT) or (a in _DATES and b in _DATES)


def _stock_twin(f: Any, stock: dict[str, Any]) -> str:
    """Name of the stock field ``f`` copies, or ''."""
    label = " ".join(_words(getattr(f, "string", "") or ""))
    stem = _stem(getattr(f, "name", ""))
    ttype = str(getattr(f, "ttype", "") or "")
    hits = []
    for sname, info in stock.items():
        if sname.startswith("x_") or not getattr(info, "stored", True):
            continue
        if not _same_kind(ttype, str(getattr(info, "type", "") or "")):
            continue
        if ttype in _REL and str(getattr(info, "relation", "") or "") != str(getattr(f, "relation", "") or ""):
            continue
        if _stem(sname) == stem or (label and " ".join(_words(getattr(info, "string", "") or "")) == label):
            hits.append(sname)
    return hits[0] if len(hits) == 1 else ""


def _live_fields(snap: Any, model: str) -> dict[str, Any]:
    if snap is None or not getattr(snap, "ok", False):
        return {}
    info = snap._info(model)  # noqa: SLF001 - read-only lookup
    return dict(getattr(info, "fields", {}) or {}) if info is not None else {}


def _rename_refs(design: Any, model: str, renames: dict[str, str]) -> None:
    if not renames:
        return
    for a in design.automations:
        if not isinstance(a, dict) or a.get("target_model") != model:
            continue
        spec = a.get("automation") or {}
        for key in ("date_field", "user_field"):
            if spec.get(key) in renames:
                spec[key] = renames[spec[key]]
        spec["condition"] = [[renames.get(t[0], t[0])] + list(t[1:]) for t in spec.get("condition") or [] if t]
        if spec.get("values"):
            spec["values"] = {renames.get(k, k): v for k, v in spec["values"].items()}
        if not spec["condition"]:
            spec.pop("condition")


def map_to_stock_fields(design: Any, snap: Any) -> list[str]:
    notes: list[str] = []
    for e in design.stock_extensions:
        stock = _live_fields(snap, e.model)
        if not stock:
            continue
        kept, renames = [], {}
        for f in e.fields:
            twin = _stock_twin(f, stock)
            if twin:
                renames[f.name] = twin
                label = getattr(stock[twin], "string", "") or twin
                notes.append(f"Uses the existing {label} field instead of adding a copy ({f.string or f.name}).")
                continue
            kept.append(f)
        e.fields = kept
        _rename_refs(design, e.model, renames)
    return notes


def _exists(design: Any, snap: Any, model: str) -> bool:
    if model in {m.name for m in design.new_models}:
        return True
    return bool(snap is not None and getattr(snap, "ok", False) and model in (snap.index or {}))


def _ids(obj: Any) -> set[str]:
    return {x for x in [getattr(obj, "requirement_id", "") or ""] + list(getattr(obj, "requirement_ids", None) or []) if x}


def _host_for(design: Any, snap: Any, rid: str) -> str:
    live_ext = [e for e in design.stock_extensions if _exists(design, snap, e.model)]
    by_req = [e.model for e in live_ext if rid and any(rid in _ids(f) for f in e.fields)]
    if len(set(by_req)) == 1:
        return by_req[0]
    models = {e.model for e in live_ext}
    return next(iter(models)) if len(models) == 1 else ""


def retarget_automations(design: Any, snap: Any) -> list[str]:
    notes: list[str] = []
    if snap is None or not getattr(snap, "ok", False):
        return notes
    kept = []
    for a in design.automations:
        target = str((a or {}).get("target_model") or "")
        if not target or _exists(design, snap, target):
            kept.append(a)
            continue
        host = _host_for(design, snap, str(a.get("requirement_id") or ""))
        spec = a.get("automation") or {}
        date_field = str(spec.get("date_field") or "")
        have = set(_live_fields(snap, host)) | {f.name for e in design.stock_extensions if e.model == host for f in e.fields}
        if host and (not date_field or date_field in have):
            a["target_model"] = host
            notes.append(f"The automation '{a.get('label')}' runs on the existing {host} records.")
            kept.append(a)
            continue
        notes.append(f"Left out the automation '{a.get('label')}': the record it was meant for is not in this database.")
    design.automations = kept
    pieces = []
    for p in design.python_needed:
        models = [str(m) for m in (p or {}).get("models") or []]
        real = [m for m in models if _exists(design, snap, m)]
        if models and not real:
            host = _host_for(design, snap, str(p.get("requirement_id") or ""))
            if not host:
                notes.append(f"Left out '{p.get('label')}': the record it was meant for is not in this database.")
                continue
            real = [host]
        if models:
            p["models"] = real
        pieces.append(p)
    design.python_needed = pieces
    return notes


def _content(text: str) -> set[str]:
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in _words(text) if len(w) >= 3}


def _named_by(f: Any, r: dict[str, Any]) -> bool:
    """The requirement's own words name the field: at least half of the label's words appear."""
    want = _content(getattr(f, "string", "") or "") or _content(_stem(getattr(f, "name", "")).replace("_", " "))
    said = _content(f"{r.get('subject') or ''} {(r.get('evidence') or {}).get('quote') or ''}")
    return bool(want) and len(want & said) * 2 >= len(want)


def _traced_by_words(f: Any, contract: list[dict[str, Any]], approved: set[str]) -> list[str]:
    """Approved requirements that name this field in their own words.

    Ids copied onto every field of a host (structure) are not enough on an extension design:
    each added field must be named by an approved requirement."""
    return [str(r.get("id")) for r in contract if str((r or {}).get("id") or "") in approved and _named_by(f, r)]


def trace_extension_fields(design: Any, approved: set[str]) -> list[str]:
    """Extension-only design: every added field traces to an approved requirement that names it."""
    notes: list[str] = []
    contract = [r for r in design.intent_contract if isinstance(r, dict)]
    for e in design.stock_extensions:
        kept = []
        for f in e.fields:
            if len(_words(f.string or "")) > _MAX_LABEL_WORDS:
                notes.append(f"Left out the field '{f.string}': it reads like a sentence, not a field name.")
                continue
            ids = _traced_by_words(f, contract, approved) if contract else sorted(_ids(f) & approved)
            if ids:
                f.requirement_ids = list(dict.fromkeys(ids))
                kept.append(f)
                continue
            notes.append(f"Left out the field {f.string or f.name}: it does not trace to anything you asked for.")
        e.fields = kept
    design.stock_extensions = [e for e in design.stock_extensions if e.fields or design.automations]
    return notes


def sane_field_names(design: Any) -> list[str]:
    """Short technical names from the label (x_ + up to four words)."""
    notes: list[str] = []
    for owner, fields in [(m.name, m.fields) for m in design.new_models] + [
            (e.model, e.fields) for e in design.stock_extensions]:
        used = {f.name for f in fields}
        renames = {}
        for f in fields:
            stem = re.sub(r"^x_", "", f.name or "")
            parts = [p for p in stem.split("_") if p]
            if len(parts) <= _MAX_NAME_WORDS and len(f.name) <= 40:
                continue
            base = "_".join(_words(f.string or stem)[:_MAX_NAME_WORDS]) or "_".join(parts[:_MAX_NAME_WORDS])
            if f.ttype == "many2one" and not base.endswith("_id"):
                base += "_id"
            new, n = f"x_{base}"[:40], 2
            while new in used:
                new, n = f"x_{base}_{n}"[:40], n + 1
            used.discard(f.name); used.add(new)
            renames[f.name] = new
            f.name = new
        if renames:
            _rename_refs(design, owner, renames)
            notes.append("Shortened field names: " + ", ".join(f"{a} -> {b}" for a, b in renames.items()))
    return notes


def refresh_pass(design: Any, snap: Any) -> dict[str, list[str]]:
    """All passes, in order. Returns notes per pass (also appended to design.notes)."""
    out: dict[str, list[str]] = {"names": sane_field_names(design)}
    out["retarget"] = retarget_automations(design, snap)  # first, so field renames reach them
    out["stock_fields"] = map_to_stock_fields(design, snap)
    auth = getattr(design, "_auth", None)
    if auth is not None and not design.new_models:
        auth_ids, _declined_any, declined_ids = auth
        out["traced"] = trace_extension_fields(design, set(auth_ids) - set(declined_ids or ()))
    design.notes = list(dict.fromkeys(list(design.notes) + [n for v in out.values() for n in v]))
    return out


__all__ = ["map_to_stock_fields", "refresh_pass", "retarget_automations", "sane_field_names",
           "trace_extension_fields"]
