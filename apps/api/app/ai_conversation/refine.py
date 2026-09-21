"""ModuleSpec refinement — catalog-driven patches, then an allowlisted LLM fallback.

Deterministic path reads the *current* draft (labels, technical names, models).
It does not hard-code Priority, Deposit, or any other field. The LLM path may
only emit allowlisted ops; those are validated against the same catalog.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.ai_conversation.intent_lexicon import (
    classify_utterances,
    extract_remainder,
    fix_typos,
    is_pronoun_remainder,
    similar,
    split_field_list,
    strip_chat_fluff,
)

logger = logging.getLogger(__name__)

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "field",
        "fields",
        "from",
        "on",
        "of",
        "to",
        "as",
        "and",
        "or",
        "please",
        "can",
        "you",
        "we",
        "i",
        "want",
        "need",
        "make",
        "set",
        "add",
        "remove",
        "delete",
        "drop",
        "hide",
        "show",
        "required",
        "optional",
        "it",
        "this",
        "that",
        "form",
        "draft",
        "app",
        "ticket",
        "tickets",
        "model",
        "back",
        "restore",
    }
)
_WORKFLOW_FIELD_NAMES = frozenset({"x_status", "x_state", "state"})
_ALLOWED_OPS = frozenset(
    {
        "remove_field",
        "add_field",
        "set_attr",
        "rename_label",
        "hide_field",
        "show_field",
        "stamp_approval",
        "set_slot",
    }
)
_REMOVED_KEY = "_refine_removed_fields"
_UNDO_KEY = "_refine_undo"
_LAST_FIELD_KEY = "_refine_last_field"
_ALLOWED_ATTRS = frozenset(
    {
        "required",
        "invisible",
        "string",
        "help",
        "ttype",
        "relation",
        "selection",
        "default",
        "tracking",
    }
)
_TTYPES = frozenset(
    {
        "char",
        "text",
        "boolean",
        "integer",
        "float",
        "date",
        "datetime",
        "selection",
        "many2one",
        "one2many",
        "many2many",
        "binary",
        "html",
        "monetary",
    }
)
_REFINE_SCHEMA = {
    "type": "object",
    "properties": {
        "ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string"},
                    "model": {"type": "string"},
                    "field": {"type": "string"},
                    "name": {"type": "string"},
                    "string": {"type": "string"},
                    "ttype": {"type": "string"},
                    "attr": {"type": "string"},
                    "value": {},
                    "required": {"type": "boolean"},
                    "help": {"type": "string"},
                    "slot": {"type": "string"},
                },
                "required": ["op"],
            },
        },
        "summary": {"type": "string"},
        "impossible": {"type": "boolean"},
    },
    "required": ["ops", "summary"],
}


@dataclass(frozen=True)
class FieldRef:
    model_id: str
    name: str
    string: str
    field: dict[str, Any]
    is_line: bool
    is_workflow_state: bool


@dataclass
class Intent:
    verb: str
    remainder: str
    model_hint: str = ""
    extra: str = ""


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.split(r"[^a-z0-9]+", (text or "").lower())
        if t and t not in _STOP and len(t) > 1
    ]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _leaf(name: str) -> str:
    return str(name or "").lower().removeprefix("x_")


def _field_preview_id(model: str, field_name: str) -> str:
    return f"{model}.{field_name}"


def _is_line(model_id: str) -> bool:
    mid = str(model_id or "")
    return mid.endswith("_line") or mid.endswith("_lines")


def _iter_models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]


def catalog_fields(draft: dict[str, Any]) -> list[FieldRef]:
    out: list[FieldRef] = []
    for model in _iter_models(draft):
        mid = str(model.get("model") or "")
        state = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        state_name = str(state.get("field") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            if not fname:
                continue
            out.append(
                FieldRef(
                    model_id=mid,
                    name=fname,
                    string=str(field.get("string") or fname),
                    field=field,
                    is_line=_is_line(mid),
                    is_workflow_state=fname == state_name
                    or fname in _WORKFLOW_FIELD_NAMES,
                )
            )
    return out


def _header_model(draft: dict[str, Any]) -> dict[str, Any] | None:
    for model in _iter_models(draft):
        mid = str(model.get("model") or "")
        if mid.startswith("x_") and not _is_line(mid) and str(model.get("mode") or "new") != "inherit":
            return model
    for model in _iter_models(draft):
        if str(model.get("model") or "").startswith("x_"):
            return model
    return _iter_models(draft)[0] if _iter_models(draft) else None


def resolve_model(draft: dict[str, Any], needle: str) -> dict[str, Any] | None:
    n = _norm(needle)
    if not n:
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    for model in _iter_models(draft):
        mid = str(model.get("model") or "")
        desc = str(model.get("description") or model.get("name") or "")
        leaf = _leaf(mid)
        score = 0
        if n == _norm(mid) or n == _norm(leaf) or n == _norm(desc):
            score = 8
        elif n in _norm(mid) or n in _norm(leaf) or n in _norm(desc):
            score = 4
        elif any(tok in leaf or tok in _norm(desc) for tok in n.split()):
            score = 2
        if score:
            scored.append((score, model))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], _is_line(str(row[1].get("model") or ""))))
    return scored[0][1]


def resolve_field(
    draft: dict[str, Any],
    needle: str,
    *,
    model_hint: str = "",
) -> FieldRef | None:
    n = _norm(fix_typos(needle))
    if not n or is_pronoun_remainder(n):
        return None
    scoped = catalog_fields(draft)
    if model_hint:
        model = resolve_model(draft, model_hint)
        if model:
            mid = str(model.get("model") or "")
            scoped = [f for f in scoped if f.model_id == mid] or scoped

    exact: list[FieldRef] = []
    fuzzy: list[tuple[int, FieldRef]] = []
    for ref in scoped:
        labels = {
            _norm(ref.name),
            _norm(ref.string),
            _norm(_leaf(ref.name)),
            _norm(ref.string.replace(" ", "_")),
        }
        if n in labels:
            exact.append(ref)
            continue
        score = 0
        for tok in _tokens(n):
            if tok == _norm(ref.string) or tok == _norm(_leaf(ref.name)):
                score += 4
            elif tok in _norm(ref.string) or tok in _norm(ref.name):
                score += 2
            if tok in _norm(ref.model_id):
                score += 1
            leaf = _norm(_leaf(ref.name))
            label = _norm(ref.string)
            if len(tok) >= 4 and (
                similar(tok, leaf) >= 0.82 or similar(tok, label) >= 0.82
            ):
                score += 4
        if n in _norm(ref.name) or n in _norm(ref.string):
            score += 3
        if len(n) >= 3:
            sim = max(
                similar(n, _norm(ref.string)),
                similar(n, _norm(_leaf(ref.name))),
                similar(n, _norm(ref.name)),
            )
            if sim >= 0.78:
                score = max(score, int(sim * 10))
        if score:
            fuzzy.append((score, ref))

    def _rank(ref: FieldRef) -> tuple[int, int, int, str]:
        status_boost = 1 if (ref.is_workflow_state and "status" in n) else 0
        return (status_boost, 0 if not ref.is_line else 1, 0 if ref.model_id.startswith("x_") else 1, ref.name)

    if exact:
        exact.sort(key=_rank)
        return exact[0]
    if not fuzzy:
        return None
    fuzzy.sort(key=lambda row: (-row[0], _rank(row[1])))
    if fuzzy[0][0] < 2:
        return None
    return fuzzy[0][1]


def fields_mentioned(draft: dict[str, Any], text: str) -> list[FieldRef]:
    blob = f" {_norm(fix_typos(text))} "
    hits: list[FieldRef] = []
    for ref in catalog_fields(draft):
        for label in (_norm(ref.string), _norm(_leaf(ref.name)), _norm(ref.name)):
            if label and f" {label} " in blob:
                hits.append(ref)
                break
            if label and len(label) >= 4 and similar(_norm(fix_typos(text)), label) >= 0.86:
                hits.append(ref)
                break
    return hits


def _strip_chat_fluff(text: str) -> str:
    return strip_chat_fluff(text)


def classify_intents(text: str) -> list[Intent]:
    return [
        Intent(verb=verb, remainder=remainder, model_hint=model_hint, extra=extra)
        for verb, remainder, model_hint, extra in classify_utterances(text)
    ]


def classify_intent(text: str) -> Intent | None:
    intents = classify_intents(text)
    return intents[0] if intents else None

def _slug_field(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")[:32] or "extra"
    return slug if slug.startswith("x_") else f"x_{slug}"


def _guess_ttype(label: str) -> str:
    try:
        from app.ai_field_ir import infer_date_or_datetime

        temporal = infer_date_or_datetime(label)
        if temporal:
            return temporal
    except Exception:  # noqa: BLE001
        pass
    low = (label or "").lower()
    if any(tok in low for tok in ("date", "due", "when")):
        return "date"
    if any(tok in low for tok in ("note", "description", "comment", "memo")):
        return "text"
    if any(tok in low for tok in ("amount", "hours", "qty", "quantity", "count", "price")):
        return "float"
    if any(tok in low for tok in ("done", "active", "flag")):
        return "boolean"
    return "char"


def _add_label(remainder: str) -> str:
    cleaned = extract_remainder(fix_typos(remainder or ""), "add")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned.lower() in {"extra", "x extra", "field", "a field"}:
        return ""
    return cleaned


def _restore_label(remainder: str) -> str:
    cleaned = extract_remainder(fix_typos(remainder or ""), "restore")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    cleaned = re.sub(
        r"(?i)\s+(tickets?|form|app|model|request)$",
        "",
        cleaned,
    ).strip()
    if cleaned.lower() in {"extra", "x extra"}:
        return ""
    return cleaned


def _remember_removed_field(draft: dict[str, Any], model_id: str, field: dict[str, Any]) -> None:
    fname = str(field.get("name") or "")
    if not fname:
        return
    ledger = [
        row
        for row in (draft.get(_REMOVED_KEY) or [])
        if isinstance(row, dict)
        and not (
            str(row.get("model") or "") == model_id
            and str((row.get("field") or {}).get("name") or "") == fname
        )
    ]
    ledger.append({"model": model_id, "field": copy.deepcopy(field)})
    draft[_REMOVED_KEY] = ledger[-40:]


def _match_removed_field(
    draft: dict[str, Any], needle: str, *, model_hint: str = ""
) -> dict[str, Any] | None:
    label = _restore_label(needle)
    n = _norm(fix_typos(label)) or _norm(fix_typos(needle))
    scoped = [row for row in (draft.get(_REMOVED_KEY) or []) if isinstance(row, dict)]
    if model_hint:
        model = resolve_model(draft, model_hint)
        if model:
            mid = str(model.get("model") or "")
            hinted = [row for row in scoped if str(row.get("model") or "") == mid]
            if hinted:
                scoped = hinted
    if not n or is_pronoun_remainder(n):
        return scoped[-1] if scoped else None
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in scoped:
        field = row.get("field") if isinstance(row.get("field"), dict) else {}
        fname = str(field.get("name") or "")
        string = str(field.get("string") or fname)
        labels = {_norm(fname), _norm(string), _norm(_leaf(fname))}
        score = 0
        if n in labels:
            score = 8
        elif any(n in x or x in n for x in labels if x):
            score = 5
        else:
            toks = _tokens(n)
            hits = sum(
                1
                for tok in toks
                if tok in _norm(string) or tok in _norm(fname) or tok == _leaf(fname)
            )
            if toks and hits == len(toks):
                score = 6
            elif hits:
                score = 2 * hits
        if len(n) >= 3:
            sim = max(
                similar(n, _norm(string)),
                similar(n, _norm(_leaf(fname))),
                similar(n, _norm(fname)),
            )
            if sim >= 0.78:
                score = max(score, int(sim * 10))
        if score:
            scored.append((score, row))
    if not scored:
        return None
    scored.sort(key=lambda item: -item[0])
    return scored[0][1]


def _model_by_id(draft: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    for model in _iter_models(draft):
        if str(model.get("model") or "") == model_id:
            return model
    return None


def _cleanup_workflow(draft: dict[str, Any], model_id: str, field_name: str) -> None:
    model = _model_by_id(draft, model_id)
    if not model:
        return
    state = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    state_name = str(state.get("field") or "x_status")
    if field_name != state_name and field_name not in _WORKFLOW_FIELD_NAMES:
        return
    model.pop("state_field", None)
    model["is_workflow"] = False
    try:
        from app.ai_odoo_app_bar import demote_workflows_missing_status

        demote_workflows_missing_status(draft)
    except Exception:  # noqa: BLE001
        pass


def _drop_field(draft: dict[str, Any], model_id: str, field_name: str) -> None:
    model = _model_by_id(draft, model_id)
    if model:
        current = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == field_name
            ),
            None,
        )
        if current:
            _remember_removed_field(draft, model_id, current)
    try:
        from app.ai_odoo_app_bar import _drop_named_fields

        _drop_named_fields(draft, model_id, {field_name})
    except Exception:  # noqa: BLE001
        model = _model_by_id(draft, model_id)
        if model:
            model["fields"] = [
                f
                for f in (model.get("fields") or [])
                if not (isinstance(f, dict) and str(f.get("name") or "") == field_name)
            ]
    _cleanup_workflow(draft, model_id, field_name)


def apply_ops(draft: dict[str, Any], ops: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Apply allowlisted ops. Returns (summaries, highlighted ids)."""
    summaries: list[str] = []
    highlighted: list[str] = []
    undo: list[dict[str, Any]] = []

    def _remember_touch(model: str, field_name: str, inverse: dict[str, Any]) -> None:
        undo.append(inverse)
        draft[_LAST_FIELD_KEY] = {"model": model, "field": field_name}

    for raw in ops:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "").strip()
        if op not in _ALLOWED_OPS:
            continue
        model_id = str(raw.get("model") or "")
        model = _model_by_id(draft, model_id) if model_id else None
        if op == "stamp_approval":
            from app.ai_approval_flow import apply_approval_flow

            notes = apply_approval_flow(draft, force=True)
            if notes:
                summaries.extend(notes)
                highlighted.append("approval")
            continue
        if op == "add_field":
            target = model or _header_model(draft)
            if not target:
                continue
            label = str(raw.get("string") or "").strip()
            fname = str(raw.get("name") or "").strip()
            payload = raw.get("field") if isinstance(raw.get("field"), dict) else {}
            if payload:
                label = label or str(payload.get("string") or "").strip()
                fname = fname or str(payload.get("name") or "").strip()
            if not label and not fname:
                continue
            if not fname:
                fname = _slug_field(label)
            if not fname.startswith("x_"):
                fname = _slug_field(fname)
            if not label:
                label = _leaf(fname).replace("_", " ").title()
            if label.lower() in {"extra", "x extra"} and not payload:
                continue
            existing = {
                str(f.get("name") or "")
                for f in (target.get("fields") or [])
                if isinstance(f, dict)
            }
            if fname in existing:
                continue
            ttype = str(raw.get("ttype") or payload.get("ttype") or _guess_ttype(label))
            if ttype not in _TTYPES:
                ttype = "char"
            row = dict(payload) if payload else {}
            row.update(
                {
                    "name": fname,
                    "ttype": ttype,
                    "string": label.title() if label == label.lower() else label,
                    "required": bool(raw.get("required", payload.get("required"))),
                }
            )
            if raw.get("help") or payload.get("help"):
                row["help"] = str(raw.get("help") or payload.get("help"))
            if (raw.get("relation") or payload.get("relation")) and ttype in {
                "many2one",
                "one2many",
                "many2many",
            }:
                row["relation"] = str(raw.get("relation") or payload.get("relation"))
            if payload.get("selection") and "selection" not in row:
                row["selection"] = payload["selection"]
            target.setdefault("fields", []).append(row)
            mid = str(target.get("model") or "")
            highlighted.append(_field_preview_id(mid, fname))
            summaries.append(f"Added {row['string']} on {mid}.")
            ledger = [
                item
                for item in (draft.get(_REMOVED_KEY) or [])
                if not (
                    isinstance(item, dict)
                    and str(item.get("model") or "") == mid
                    and str((item.get("field") or {}).get("name") or "") == fname
                )
            ]
            draft[_REMOVED_KEY] = ledger
            _remember_touch(
                mid,
                fname,
                {"op": "remove_field", "model": mid, "field": fname},
            )
            continue

        if not model:
            continue
        fname = str(raw.get("field") or raw.get("name") or "")
        field = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == fname
            ),
            None,
        )
        if op == "remove_field":
            if not field:
                continue
            label = str(field.get("string") or fname)
            snapshot = copy.deepcopy(field)
            _drop_field(draft, model_id, fname)
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Removed {label} from {model_id}.")
            _remember_touch(
                model_id,
                fname,
                {
                    "op": "add_field",
                    "model": model_id,
                    "name": fname,
                    "string": label,
                    "ttype": str(snapshot.get("ttype") or snapshot.get("type") or "char"),
                    "field": snapshot,
                },
            )
            continue
        if not field:
            continue
        if op == "hide_field":
            field["invisible"] = True
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Hid {field.get('string') or fname} on {model_id}.")
            _remember_touch(
                model_id,
                fname,
                {"op": "show_field", "model": model_id, "field": fname},
            )
        elif op == "show_field":
            field["invisible"] = False
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Showed {field.get('string') or fname} on {model_id}.")
            _remember_touch(
                model_id,
                fname,
                {"op": "hide_field", "model": model_id, "field": fname},
            )
        elif op == "rename_label":
            label = str(raw.get("string") or raw.get("value") or "").strip()
            if not label:
                continue
            previous = str(field.get("string") or fname)
            field["string"] = label
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Renamed field to {label} on {model_id}.")
            _remember_touch(
                model_id,
                fname,
                {
                    "op": "rename_label",
                    "model": model_id,
                    "field": fname,
                    "string": previous,
                },
            )
        elif op == "set_slot":
            from app.ai_form_slots import SLOT_IDS, slot_catalog

            slot = str(raw.get("slot") or "").strip()
            if slot not in SLOT_IDS:
                continue
            stored = draft.get("_form_slots")
            if not isinstance(stored, dict):
                stored = {}
                draft["_form_slots"] = stored
            fields_map = stored.get("fields")
            if not isinstance(fields_map, dict):
                fields_map = {}
                stored["fields"] = fields_map
            previous = str(fields_map.get(fname) or "")
            fields_map[fname] = slot
            host = str(model.get("model") or model_id)
            stored.setdefault("catalog", slot_catalog(host))
            stored.setdefault("host", host)
            label = str(field.get("string") or fname)
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Placed {label} in the {slot.replace('_', ' ')} slot.")
            _remember_touch(
                model_id,
                fname,
                {
                    "op": "set_slot",
                    "model": model_id,
                    "field": fname,
                    "slot": previous or slot,
                },
            )
        elif op == "set_attr":
            attr = str(raw.get("attr") or "").strip()
            if attr not in _ALLOWED_ATTRS:
                continue
            value = raw.get("value")
            if attr == "ttype" and str(value) not in _TTYPES:
                continue
            previous = field.get(attr)
            field[attr] = value
            highlighted.append(_field_preview_id(model_id, fname))
            summaries.append(f"Updated {field.get('string') or fname} ({attr}) on {model_id}.")
            _remember_touch(
                model_id,
                fname,
                {
                    "op": "set_attr",
                    "model": model_id,
                    "field": fname,
                    "attr": attr,
                    "value": previous,
                },
            )
    if summaries and undo:
        draft[_UNDO_KEY] = list(reversed(undo))
    return summaries, highlighted


def _hints_from_draft(draft: dict[str, Any]) -> list[str]:
    refs = [f for f in catalog_fields(draft) if not f.is_line]
    if not refs:
        refs = catalog_fields(draft)
    hints: list[str] = []
    for ref in refs[:2]:
        hints.append(f"remove {ref.string}")
    optional = next((f for f in refs if f.field.get("required") is not True), None)
    if optional:
        hints.append(f"make {optional.string} required")
    if not any(h.startswith("add ") for h in hints):
        hints.append("add a due date")
    # unique, keep order
    seen: set[str] = set()
    out: list[str] = []
    for hint in hints:
        if hint not in seen:
            seen.add(hint)
            out.append(hint)
    return out[:3]


def _unmap_error(draft: dict[str, Any], *, detail: str = "") -> dict[str, Any]:
    hints = " · ".join(_hints_from_draft(draft))
    extra = f" {detail.strip()}" if detail else ""
    return {
        "ok": False,
        "error": (
            "Could not apply that to this draft."
            f"{extra} "
            f"You can remove, add, hide, rename, or require any field on the preview"
            f"{f' — try: {hints}' if hints else '.'}"
        ).strip(),
        "draft": draft,
        "patch_summary": "",
        "highlighted_field_ids": [],
    }


def _restore_ops(draft: dict[str, Any], intent: Intent, text: str) -> list[dict[str, Any]]:
    needle = intent.remainder or text
    if is_pronoun_remainder(intent.remainder):
        needle = ""
    hit = _match_removed_field(draft, needle, model_hint=intent.model_hint)
    model = (
        resolve_model(draft, intent.model_hint)
        if intent.model_hint
        else _header_model(draft)
    )
    if hit:
        field = hit.get("field") if isinstance(hit.get("field"), dict) else {}
        mid = str(hit.get("model") or (model or {}).get("model") or "")
        if field.get("name") and mid:
            existing = _model_by_id(draft, mid)
            names = {
                str(f.get("name") or "")
                for f in ((existing or {}).get("fields") or [])
                if isinstance(f, dict)
            }
            fname = str(field.get("name") or "")
            if fname in names:
                return [{"op": "show_field", "model": mid, "field": fname}]
            return [
                {
                    "op": "add_field",
                    "model": mid,
                    "name": fname,
                    "string": str(field.get("string") or fname),
                    "ttype": str(field.get("ttype") or field.get("type") or "char"),
                    "field": field,
                }
            ]
    label = _restore_label(needle)
    if not label or is_pronoun_remainder(label) or not model:
        return []
    mid = str(model.get("model") or "")
    fname = _slug_field(label)
    if _leaf(fname) in {"extra", ""}:
        return []
    existing = {
        str(f.get("name") or "")
        for f in (model.get("fields") or [])
        if isinstance(f, dict)
    }
    present = resolve_field(draft, label, model_hint=mid)
    if present:
        return [{"op": "show_field", "model": present.model_id, "field": present.name}]
    if fname in existing:
        return [{"op": "show_field", "model": mid, "field": fname}]
    return [
        {
            "op": "add_field",
            "model": mid,
            "string": label,
            "name": fname,
            "ttype": _guess_ttype(label),
        }
    ]


def _undo_ops(draft: dict[str, Any]) -> list[dict[str, Any]]:
    stacked = [op for op in (draft.get(_UNDO_KEY) or []) if isinstance(op, dict)]
    if stacked:
        return stacked
    return _restore_ops(draft, Intent(verb="restore", remainder=""), "")


def _pronoun_target(draft: dict[str, Any]) -> FieldRef | None:
    last = draft.get(_LAST_FIELD_KEY)
    if isinstance(last, dict):
        fname = str(last.get("field") or "")
        mid = str(last.get("model") or "")
        if fname:
            hit = resolve_field(draft, fname, model_hint=mid)
            if hit:
                return hit
    return None


def _resolve_targets(draft: dict[str, Any], intent: Intent, text: str) -> list[FieldRef]:
    if is_pronoun_remainder(intent.remainder):
        hit = _pronoun_target(draft)
        return [hit] if hit else []
    needles = split_field_list(intent.remainder) if intent.remainder else []
    if not needles:
        mentioned = fields_mentioned(draft, text)
        return mentioned[:1]
    out: list[FieldRef] = []
    seen: set[tuple[str, str]] = set()
    for needle in needles:
        ref = resolve_field(draft, needle, model_hint=intent.model_hint)
        if ref and (ref.model_id, ref.name) not in seen:
            seen.add((ref.model_id, ref.name))
            out.append(ref)
    if not out:
        mentioned = fields_mentioned(draft, text)
        for ref in mentioned:
            if (ref.model_id, ref.name) not in seen:
                seen.add((ref.model_id, ref.name))
                out.append(ref)
    return out


def _ops_from_intent(draft: dict[str, Any], intent: Intent, text: str) -> list[dict[str, Any]]:
    if intent.verb == "approval":
        return [{"op": "stamp_approval"}]
    if intent.verb == "undo":
        return _undo_ops(draft)
    if intent.verb == "restore":
        return _restore_ops(draft, intent, text)
    if intent.verb == "add":
        model = resolve_model(draft, intent.model_hint) if intent.model_hint else _header_model(draft)
        if not model:
            return []
        labels = split_field_list(_add_label(intent.remainder)) or (
            [_add_label(intent.remainder)] if _add_label(intent.remainder) else []
        )
        ops: list[dict[str, Any]] = []
        required = bool(re.search(r"(?i)\brequired\b", text))
        for label in labels:
            if not label or is_pronoun_remainder(label):
                continue
            slug = _slug_field(label)
            if _leaf(slug) in {"extra", ""}:
                continue
            ops.append(
                {
                    "op": "add_field",
                    "model": str(model.get("model") or ""),
                    "string": label,
                    "name": slug,
                    "ttype": _guess_ttype(label),
                    "required": required,
                }
            )
        return ops

    targets = _resolve_targets(draft, intent, text)
    if not targets:
        return []

    ops: list[dict[str, Any]] = []
    if intent.verb == "place":
        from app.ai_form_slots import SLOT_IDS, slot_from_location

        slot = intent.extra.strip() if intent.extra else ""
        if slot not in SLOT_IDS:
            slot = slot_from_location(intent.remainder) or slot_from_location(text) or ""
        if slot not in SLOT_IDS:
            return []
        return [
            {
                "op": "set_slot",
                "model": target.model_id,
                "field": target.name,
                "slot": slot,
            }
            for target in targets
        ]
    for target in targets:
        if intent.verb == "remove":
            ops.append({"op": "remove_field", "model": target.model_id, "field": target.name})
        elif intent.verb == "hide":
            ops.append({"op": "hide_field", "model": target.model_id, "field": target.name})
        elif intent.verb == "show":
            ops.append({"op": "show_field", "model": target.model_id, "field": target.name})
        elif intent.verb == "require":
            ops.append(
                {
                    "op": "set_attr",
                    "model": target.model_id,
                    "field": target.name,
                    "attr": "required",
                    "value": True,
                }
            )
        elif intent.verb == "optional":
            ops.append(
                {
                    "op": "set_attr",
                    "model": target.model_id,
                    "field": target.name,
                    "attr": "required",
                    "value": False,
                }
            )
        elif intent.verb == "rename":
            new_label = intent.extra.strip()
            if not new_label:
                match = re.search(r"(?i)\b(?:to|as)\s+(.+)$", intent.remainder)
                new_label = (match.group(1) if match else "").strip()
            if not new_label:
                continue
            ops.append(
                {
                    "op": "rename_label",
                    "model": target.model_id,
                    "field": target.name,
                    "string": new_label,
                }
            )
    return ops


def _catalog_prompt(draft: dict[str, Any]) -> str:
    lines: list[str] = []
    for model in _iter_models(draft):
        mid = str(model.get("model") or "")
        mode = str(model.get("mode") or "new")
        lines.append(f"MODEL {mid} mode={mode}")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            lines.append(
                f"  - {fname} | {field.get('string') or fname} | "
                f"{field.get('ttype') or field.get('type') or 'char'}"
                f"{' required' if field.get('required') else ''}"
            )
    return "\n".join(lines[:200])


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def llm_propose_ops(
    draft: dict[str, Any],
    instruction: str,
    *,
    provider: Any | None,
    prompt: str = "",
) -> dict[str, Any] | None:
    if provider is None:
        return None
    system = (
        "You edit an Odoo Community ModuleSpec already on screen. "
        "Return JSON only. Use only allowlisted ops: remove_field, add_field, "
        "set_attr, rename_label, hide_field, show_field, stamp_approval. "
        "Infer messy English, typos, and synonyms: remove/delete/drop/yeet/"
        "get rid of/don't need/without; restore/undo/oops/bring back/put back; "
        "require/mandatory; optional; rename/call it. "
        "model and field must be copied exactly from the catalog. "
        "If the user restores a removed field, add_field MUST include both name "
        "and string (e.g. x_asset_tag / Asset Tag). Never emit add_field without "
        "string — never invent a field named Extra. "
        "If they say undo/oops with no field name, restore the last removed field. "
        "If one message has several commands (remove X and restore Y), emit ops "
        "for every command in order. "
        "If they ask for an approval flow, emit stamp_approval. "
        "If the ask is theme/color/pixel CSS, OWL, or something this no-code "
        "draft cannot do, set ops=[] and impossible=true with a one-line reason. "
        "Never invent stock apps or Project/Purchase hosts the brief forbade."
    )
    user = (
        f"Original brief:\n{(prompt or draft.get('_user_prompt') or '')[:1200]}\n\n"
        f"Catalog:\n{_catalog_prompt(draft)}\n\n"
        f"User refinement:\n{instruction}\n"
    )
    try:
        raw = provider.generate_json(
            user,
            system=system,
            timeout_s=45.0,
            temperature=0.0,
            format_schema=_REFINE_SCHEMA,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Refine LLM skipped: %s", exc)
        return None
    return _parse_llm_json(raw)


def _restamp_preview(working: dict[str, Any], prompt: str) -> None:
    from app.ai_draft_scorecard import attach_scorecard

    user_prompt = prompt or str(working.get("_user_prompt") or "")
    try:
        from app.ai_enrich import sync_form_archs_to_models

        sync_form_archs_to_models(working)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_odoo_app_bar import rebuild_form_transition_headers

        rebuild_form_transition_headers(working)
    except Exception:  # noqa: BLE001
        pass
    attach_scorecard(working, user_prompt=user_prompt)
    try:
        from app.ai_generation_engine import attach_generation_engine

        attach_generation_engine(working, user_prompt, user_phase="review")
    except Exception:  # noqa: BLE001
        pass



_STRUCTURAL_REPAIR_RE = re.compile(
    r"(?i)\b("
    r"surface\s+findings?|ground(?:\s+the)?\s+(?:app\s+)?title|"
    r"inherit[- ]only|no\s+new\s+(?:home[- ]?screen\s+)?app|"
    r"reshape|structural\s+repair|placeholder\s+like|"
    r"contact\s+extras|contacts?\s+extension|never\s+a\s+placeholder|"
    r"fix\s+surface|block(?:s|ing)?\s+install"
    r")\b"
)


def wants_structural_repair(instruction: str) -> bool:
    """True when Expert must reshape title/grain — not field chrome."""
    return bool(_STRUCTURAL_REPAIR_RE.search(instruction or ""))


def _infer_host_from_draft_or_prompt(
    draft: dict[str, Any], prompt: str
) -> tuple[str, str]:
    """Return (model, label) for inherit-only reshape."""
    try:
        from app.ai_grain import HOST_LABELS, preferred_inherit_host

        host = preferred_inherit_host(prompt) or ""
        if host:
            return host, HOST_LABELS.get(host, host)
    except Exception:  # noqa: BLE001
        pass
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        mode = str(model.get("mode") or "new")
        if mode == "inherit" and mid and not mid.startswith("x_"):
            try:
                from app.ai_grain import HOST_LABELS

                return mid, HOST_LABELS.get(mid, mid)
            except Exception:  # noqa: BLE001
                return mid, mid
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("ttype") or field.get("type") or "") == "many2one":
                rel = str(field.get("relation") or "")
                if rel in {"res.partner", "sale.order", "stock.picking", "account.move"}:
                    try:
                        from app.ai_grain import HOST_LABELS

                        return rel, HOST_LABELS.get(rel, rel)
                    except Exception:  # noqa: BLE001
                        return rel, rel
    return "res.partner", "Contacts"


def _reuse_fields_from_prompt(prompt: str) -> list[dict[str, Any]]:
    """Fields the operator said already exist — Prefer for delivery + Delivery notes."""
    text = prompt or ""
    fields: list[dict[str, Any]] = []
    if re.search(r"(?i)\bprefer(?:red)?\s+for\s+delivery\b", text):
        fields.append(
            {
                "name": "x_prefer_for_delivery",
                "ttype": "boolean",
                "string": "Prefer for delivery",
            }
        )
    if re.search(r"(?i)\bdelivery\s+notes?\b", text):
        fields.append(
            {
                "name": "x_delivery_notes",
                "ttype": "text",
                "string": "Delivery notes",
            }
        )
    return fields


def apply_structural_repair(
    draft: dict[str, Any],
    instruction: str,
    *,
    prompt: str = "",
) -> dict[str, Any] | None:
    """Reshape residual chrome into inherit-only + grounded title when asked.

    Returns a result dict on success, or None when this instruction is not
    structural (caller should fall through to field chrome).
    """
    if not wants_structural_repair(instruction):
        return None

    working = copy.deepcopy(draft)
    user_prompt = (
        prompt
        or str(working.get("_user_prompt") or working.get("prompt") or "")
    ).strip()
    summaries: list[str] = []

    host_model, host_label = _infer_host_from_draft_or_prompt(working, user_prompt)

    # Ground title — never keep Contact extras / Contacts extension chrome.
    display = str(working.get("display_name") or "").strip()
    try:
        from app.ai_component_builder import inherit_only_display_name
        from app.ai_grain import is_inherit_only_ops
        from app.ai_surface_invariants import title_is_grounded

        inherit_only = is_inherit_only_ops(user_prompt) or wants_structural_repair(
            instruction
        )
        target_title = (
            inherit_only_display_name(user_prompt, host_label)
            if inherit_only
            else display
        )
        if (
            not display
            or not title_is_grounded(display, user_prompt)
            or re.search(r"(?i)^\w+\s+(?:extras|extension)$", display)
        ):
            if target_title and (
                title_is_grounded(target_title, user_prompt) or inherit_only
            ):
                working["display_name"] = target_title
                summaries.append(f"Grounded app title to {target_title!r}.")
    except Exception:  # noqa: BLE001
        if re.search(r"(?i)^\w+\s+(?:extras|extension)$", display):
            working["display_name"] = f"{host_label} delivery preferences"
            summaries.append(
                f"Grounded app title to {working['display_name']!r}."
            )

    # Reshape residual new models → inherit host when inherit-only.
    models = [m for m in (working.get("models") or []) if isinstance(m, dict)]
    residual_new = [
        m
        for m in models
        if str(m.get("mode") or "new") != "inherit"
        and str(m.get("model") or "").startswith("x_")
    ]
    try:
        from app.ai_grain import is_inherit_only_ops

        must_reshape = is_inherit_only_ops(user_prompt) or bool(residual_new)
    except Exception:  # noqa: BLE001
        must_reshape = bool(residual_new)

    if must_reshape and (
        residual_new
        or any(str(m.get("mode") or "") != "inherit" for m in models)
        or not any(
            str(m.get("model") or "") == host_model
            and str(m.get("mode") or "") == "inherit"
            for m in models
        )
    ):
        reuse = _reuse_fields_from_prompt(user_prompt)
        # Keep any non-chrome fields already on residual that look like delivery prefs.
        for m in residual_new:
            for f in m.get("fields") or []:
                if not isinstance(f, dict):
                    continue
                label = str(f.get("string") or f.get("name") or "").lower()
                # Only keep fields that are clearly the delivery prefs — not bare Notes/Name.
                keep = bool(
                    re.search(r"prefer(?:red)?\s+for\s+delivery", label)
                    or re.search(r"delivery\s+notes?", label)
                )
                if keep and not any(
                    str(x.get("name")) == str(f.get("name")) for x in reuse
                ):
                    reuse.append(copy.deepcopy(f))
        if not reuse:
            reuse = [
                {
                    "name": "x_prefer_for_delivery",
                    "ttype": "boolean",
                    "string": "Prefer for delivery",
                },
                {
                    "name": "x_delivery_notes",
                    "ttype": "text",
                    "string": "Delivery notes",
                },
            ]
        working["models"] = [
            {
                "model": host_model,
                "mode": "inherit",
                "inherit": host_model,
                "description": f"Extend {host_label}",
                "fields": reuse,
            }
        ]
        working["menus"] = []
        working["actions"] = []
        working["grain"] = "field_pack"
        summaries.append(
            f"Reshaped residual into inherit-only on {host_label} ({host_model})."
        )

    if not summaries:
        return None

    working["grain"] = working.get("grain") or "field_pack"
    working["_user_prompt"] = user_prompt or working.get("_user_prompt")
    try:
        from app.ai_form_slots import apply_form_slots

        apply_form_slots(working, prompt=user_prompt)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_studio_contract import stamp_studio_contract_pipeline

        stamp_studio_contract_pipeline(working, user_prompt)
    except Exception:  # noqa: BLE001
        pass
    _restamp_preview(working, user_prompt)
    validators = (working.get("_scorecard") or {}).get("validators") or {}
    return {
        "ok": True,
        "draft": working,
        "patch_summary": " ".join(summaries),
        "highlighted_field_ids": [],
        "validators": validators,
        "structural": True,
    }


def apply_refinement(
    draft: dict[str, Any],
    instruction: str,
    *,
    prompt: str = "",
    provider: Any | None = None,
) -> dict[str, Any]:
    """Apply a natural-language refinement against the current draft catalog."""
    from app.ai_conversation.clarify import vague_refinement_needs_followup

    text = (instruction or "").strip()
    vague = vague_refinement_needs_followup(text)
    if vague:
        return {
            "ok": False,
            "needs_clarification": vague,
            "draft": draft,
            "patch_summary": "",
            "highlighted_field_ids": [],
        }

    from app.ai_generation_engine import is_gold_option_a_draft
    from app.ai_operator_brief import is_cbn_currency_rates_prompt, is_pos_receipt_prompt

    if (
        is_cbn_currency_rates_prompt(text) or is_pos_receipt_prompt(text)
    ) and not is_gold_option_a_draft(draft):
        return {
            "ok": False,
            "error": (
                "That ask is Option A (module zip with Python/cron), not a field on this form. "
                "Click Start new app and paste it as a new prompt — do not Install it onto "
                "Purchase Requests. Live Install cannot fetch CBN rates."
            ),
            "draft": draft,
            "patch_summary": "",
            "highlighted_field_ids": [],
        }

    structural = apply_structural_repair(draft, text, prompt=prompt)
    if structural is not None:
        return structural

    working = copy.deepcopy(draft)
    summaries: list[str] = []
    highlighted: list[str] = []
    undo_acc: list[dict[str, Any]] = []
    for intent in classify_intents(text):
        clause_ops = _ops_from_intent(working, intent, intent.remainder or text)
        chunk_summaries, chunk_ids = apply_ops(working, clause_ops)
        summaries.extend(chunk_summaries)
        highlighted.extend(chunk_ids)
        stacked = [op for op in (working.get(_UNDO_KEY) or []) if isinstance(op, dict)]
        if stacked:
            undo_acc = stacked + undo_acc

    if not summaries and provider is not None:
        proposed = llm_propose_ops(
            working,
            text,
            provider=provider,
            prompt=prompt or str(working.get("_user_prompt") or ""),
        )
        if proposed and proposed.get("impossible"):
            return _unmap_error(draft, detail=str(proposed.get("summary") or ""))
        if proposed and isinstance(proposed.get("ops"), list):
            chunk_summaries, chunk_ids = apply_ops(
                working, [op for op in proposed["ops"] if isinstance(op, dict)]
            )
            summaries.extend(chunk_summaries)
            highlighted.extend(chunk_ids)
            stacked = [op for op in (working.get(_UNDO_KEY) or []) if isinstance(op, dict)]
            if stacked:
                undo_acc = stacked + undo_acc

    if not summaries:
        return _unmap_error(draft)
    if undo_acc:
        working[_UNDO_KEY] = undo_acc

    user_prompt = prompt or str(working.get("_user_prompt") or "")
    try:
        from app.ai_form_slots import apply_form_slots

        apply_form_slots(working, prompt=user_prompt)
    except Exception:  # noqa: BLE001
        pass
    _restamp_preview(working, user_prompt)
    validators = (working.get("_scorecard") or {}).get("validators") or {}
    return {
        "ok": True,
        "draft": working,
        "patch_summary": " ".join(summaries),
        "highlighted_field_ids": highlighted,
        "validators": validators,
    }


def artifact_hash(draft: dict[str, Any]) -> str:
    """Stable hash for session resume consistency checks."""
    import hashlib

    blob = json.dumps(draft, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "apply_ops",
    "apply_refinement",
    "apply_structural_repair",
    "wants_structural_repair",
    "artifact_hash",
    "catalog_fields",
    "classify_intent",
    "resolve_field",
]
