"""Q6 — map sketch regions to stock Odoo first.

Order of preference for every region: reuse an existing field on the chosen model, then add a new
``x_`` field. The model itself is a stock model when the sketch title matches one well enough
(extend it), otherwise a new custom model. Close-but-unsure matches become questions (max 3).
Reads metadata only (ir.model, fields_get); never reads business records.
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from app.ai_client.guards import Redactor, heuristic_injection
from app.wireframe.reader import Sketch

Call = Callable[[str, str, list, dict], Any]

SURE = 0.86
MAYBE = 0.62
MAX_QUESTIONS = 3
# Synonyms people write on sketches for stock labels.
SYNONYMS: dict[str, str] = {
    "client": "customer",
    "customer name": "customer",
    "mobile": "phone",
    "telephone": "phone",
    "e-mail": "email",
    "mail": "email",
    "due": "deadline",
    "due date": "deadline",
    "owner": "salesperson",
    "assigned to": "assignees",
    "notes": "description",
    "comments": "description",
    "amount": "total",
    "qty": "quantity",
}
_SKIP_FIELD_TYPES = {"one2many", "many2many_binary"}


def _norm(text: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()
    t = re.sub(r"\s+", " ", t)
    return SYNONYMS.get(t, t)


def _ratio(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    # "Vehicle inspection" vs "Vehicle": one side's words all inside the other is a likely match, not a sure one.
    wa, wb = set(a.split()), set(b.split())
    if wa and wb and (wa <= wb or wb <= wa):
        seq = max(seq, 0.75)
    return seq


def guard_sketch(sketch: Sketch) -> dict[str, Any]:
    """PII redaction and injection screening on the text the vision model read off the sketch."""
    red = Redactor()
    flagged: list[str] = []
    for region in sketch.regions:
        for attr in ("label", "hint"):
            value = getattr(region, attr) or ""
            if not value:
                continue
            if heuristic_injection(value).flagged:
                flagged.append(region.id)
                setattr(region, attr, "")
                region.misread = True
                continue
            setattr(region, attr, red.redact(value))
    if sketch.title and heuristic_injection(sketch.title).flagged:
        flagged.append("title")
        sketch.title = "Custom app"
    sketch.title = red.redact(sketch.title or "Custom app")
    return {"redacted": dict(red.kinds), "flagged_regions": flagged}


def pick_model(call: Call, title: str) -> dict[str, Any]:
    rows = call("ir.model", "search_read", [[["transient", "=", False]]], {"fields": ["model", "name"], "limit": 2000})
    best: tuple[float, dict[str, Any]] | None = None
    for r in rows or []:
        model = str(r.get("model") or "")
        if model.startswith("ir.") or model.startswith("base.") or model.startswith("x_"):
            continue
        score = max(_ratio(title, str(r.get("name") or "")), _ratio(title, model.replace(".", " ")))
        if best is None or score > best[0]:
            best = (score, r)
    if best and best[0] >= SURE:
        return {"action": "extend", "model": best[1]["model"], "name": best[1].get("name"), "score": round(best[0], 2)}
    slug = re.sub(r"[^a-z0-9]+", "_", (title or "custom app").lower()).strip("_") or "custom_app"
    out: dict[str, Any] = {"action": "new", "model": f"x_{slug}"[:60], "name": title or "Custom app", "score": 0.0}
    if best and best[0] >= MAYBE:
        out["maybe"] = {"model": best[1]["model"], "name": best[1].get("name"), "score": round(best[0], 2)}
    return out


def map_regions(sketch: Sketch, call: Call) -> dict[str, Any]:
    target = pick_model(call, sketch.title)
    fields: dict[str, Any] = {}
    if target["action"] == "extend":
        fields = call(target["model"], "fields_get", [], {"attributes": ["string", "type", "relation", "readonly"]}) or {}
    rows: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    if target.get("maybe"):
        m = target["maybe"]
        questions.append({
            "id": "model",
            "text": f"Is \u201c{sketch.title}\u201d the same thing as Odoo\u2019s \u201c{m['name']}\u201d? If yes, we add to it instead of making a new app.",
            "options": [{"id": "extend", "label": f"Yes, add to {m['name']}"}, {"id": "new", "label": "No, make a new app"}],
        })
    for region in sketch.regions:
        best_name, best_score = None, 0.0
        for fname, meta in fields.items():
            if meta.get("type") in _SKIP_FIELD_TYPES or meta.get("readonly"):
                continue
            score = max(_ratio(region.label, str(meta.get("string") or "")), _ratio(region.label, fname.replace("_", " ")))
            if score > best_score:
                best_name, best_score = fname, score
        row: dict[str, Any] = {"region": region.id, "label": region.label, "hint": region.hint, "box": list(region.box) if region.box else None}
        if best_name and best_score >= SURE:
            meta = fields[best_name]
            row.update(action="reuse", field=best_name, field_label=meta.get("string"), type=meta.get("type"))
        else:
            row.update(action="new", field=None, type=region.hint or "char")
            if best_name and best_score >= MAYBE and len(questions) < MAX_QUESTIONS:
                meta = fields[best_name]
                questions.append({
                    "id": f"field:{region.id}",
                    "text": f"Is \u201c{region.label}\u201d the same as Odoo\u2019s \u201c{meta.get('string')}\u201d?",
                    "options": [{"id": f"reuse:{best_name}", "label": f"Yes, use {meta.get('string')}"}, {"id": "new", "label": "No, add a new field"}],
                })
        if region.needs_clarify():
            row["unclear"] = True
        rows.append(row)
    for region in sketch.regions:
        if region.needs_clarify() and len(questions) < MAX_QUESTIONS:
            questions.append({"id": f"label:{region.id}", "text": f"We couldn\u2019t read box {region.id}. What should it be called?", "options": []})
    reuse = sum(1 for r in rows if r["action"] == "reuse")
    return {
        "target": target,
        "rows": rows,
        "questions": questions[:MAX_QUESTIONS],
        "summary": f"{reuse} of {len(rows)} boxes use fields Odoo already has; {len(rows) - reuse} would be new.",
    }
