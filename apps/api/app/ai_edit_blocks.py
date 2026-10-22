"""Edit with AI for reports and emails (SPEC 20.1).

The AI proposes typed block ops only. Code applies them to a copy of the current draft and the
normal validator (view_engine_report_blocks.validate_placements) authorizes the result. Nothing is
written: the caller shows the draft (PDF / email preview) and publishing keeps the usual fidelity
check, approvals and revert.
"""
from __future__ import annotations

import copy
from typing import Any

from app import view_engine_ai as vai
from app import view_engine_report_blocks as rb
from app.view_engine import EngineError

SYSTEM_PROMPT = (
    "You turn one request about an Odoo document (a printed report or an email) into block operations. You receive "
    "the places where blocks can go (slots, with ids and labels), the blocks already placed, the record's field list, "
    "and the block types allowed. Return only JSON matching the schema. Use only slot ids, field names and block types "
    "from the input. Never invent fields or facts. Prefer the smallest change that does what was asked. If the request "
    "could mean two or three different things, return no ops, a one-sentence question in \"unclear\" and up to three "
    "short rewordings in \"choices\" that each mean one thing. If it needs something not in the input, return no ops "
    "and explain in \"unclear\" in plain words."
)
OPS = ("add", "remove", "edit", "move")
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ops": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {
            "op": {"type": "string", "enum": list(OPS)},
            "slot": {"type": "string"}, "index": {"type": "integer"},
            "to_slot": {"type": "string"}, "to_index": {"type": "integer"},
            "block": {"type": "object"},
        }, "required": ["op", "slot"]}},
        "unclear": {"type": ["string", "null"]},
        "choices": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
    },
    "required": ["ops", "unclear"],
}
MAX_OPS = 12
# What each block needs, sent with the request so answers use the validator's own keys.
BLOCK_SHAPES = {
    "text": {"type": "text", "text": "words"}, "heading": {"type": "heading", "text": "words", "level": 3},
    "field": {"type": "field", "field": "field_name"}, "label_field": {"type": "label_field", "field": "field_name", "label": "optional"},
    "divider": {"type": "divider"}, "spacer": {"type": "spacer", "size": "small|medium|large"},
    "line_table": {"type": "line_table", "field": "one2many_field", "columns": [{"field": "line_field", "sum": False}]},
    "qr": {"type": "qr", "field": "char_field"}, "barcode": {"type": "barcode", "field": "char_field"},
    "image_field": {"type": "image_field", "field": "image_field"}, "signature": {"type": "signature", "field": "binary_field"},
    "watermark": {"type": "watermark", "text": "words", "colour": "red|grey|blue|green"},
}
_TEXT_ALIASES = ("text", "content", "label", "value", "title")


def _normal_block(b: dict[str, Any]) -> dict[str, Any]:
    """Map common synonyms onto the validator's keys; the validator still decides."""
    b = dict(b)
    if b.get("type") in {"text", "heading", "watermark"} and not b.get("text"):
        b["text"] = next((b[k] for k in _TEXT_ALIASES if isinstance(b.get(k), str) and b[k].strip()), "")
    if not b.get("field") and isinstance(b.get("field_name"), str):
        b["field"] = b.pop("field_name")
    return b


def _clean_choices(raw: Any) -> list[str]:
    out = []
    for c in raw if isinstance(raw, list) else []:
        s = str(c).strip()[:120]
        if s and s not in out:
            out.append(s)
    return out[:3]


def shape_ops(raw: Any, slots: list[dict[str, Any]], types: frozenset[str]) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    """Structural check of the AI's answer. Field-level checks come from the block validator."""
    if not isinstance(raw, dict) or not isinstance(raw.get("ops"), list):
        raise EngineError("The assistant's answer couldn't be read.")
    if len(raw["ops"]) > MAX_OPS:
        raise EngineError("The assistant proposed too many changes at once. Ask for something smaller.")
    slot_ids = {s["id"] for s in slots}
    unclear = raw.get("unclear") if isinstance(raw.get("unclear"), str) and raw["unclear"].strip() else None
    clean: list[dict[str, Any]] = []
    for op in raw["ops"]:
        if not isinstance(op, dict) or op.get("op") not in OPS:
            raise EngineError("The assistant proposed a kind of change Ingenium doesn't allow.")
        if op.get("slot") not in slot_ids or (op["op"] == "move" and op.get("to_slot", op["slot"]) not in slot_ids):
            raise EngineError("The assistant pointed at a place that isn't on this layout. Nothing was changed.")
        o = {"op": op["op"], "slot": op["slot"]}
        if op["op"] in {"remove", "edit", "move"}:
            if not isinstance(op.get("index"), int):
                raise EngineError("The assistant's change didn't say which block.")
            o["index"] = op["index"]
        if op["op"] in {"add", "edit"}:
            b = op.get("block")
            if not isinstance(b, dict) or str(b.get("type") or "") not in types:
                raise EngineError("The assistant proposed a block type that isn't available here.")
            o["block"] = _normal_block(b)
            if op["op"] == "add" and isinstance(op.get("index"), int):
                o["index"] = op["index"]
        if op["op"] == "move":
            o["to_slot"] = op.get("to_slot") or op["slot"]
            o["to_index"] = op["to_index"] if isinstance(op.get("to_index"), int) else None
        clean.append(o)
    if not clean and not unclear:
        unclear = "The assistant couldn't tell what to change. Try naming the field and where it should go."
    return clean, (unclear[:300] if unclear else None), _clean_choices(raw.get("choices"))


def apply_ops(placements: list[dict[str, Any]], ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure: ops applied in order to a copy. Indexes refer to the draft as each op sees it."""
    by_slot: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for p in copy.deepcopy(placements or []):
        by_slot.setdefault(p["slot"], []).extend(p.get("blocks") or [])
        if p["slot"] not in order:
            order.append(p["slot"])

    def blocks(slot: str) -> list[dict[str, Any]]:
        if slot not in by_slot:
            by_slot[slot] = []
            order.append(slot)
        return by_slot[slot]

    for op in ops:
        bl = blocks(op["slot"])
        i = op.get("index")
        if op["op"] != "add" and not (isinstance(i, int) and 0 <= i < len(bl)):
            raise EngineError("A proposed change points at a block that isn't there. Nothing was changed.")
        if op["op"] == "add":
            bl.insert(len(bl) if i is None else max(0, min(i, len(bl))), dict(op["block"]))
        elif op["op"] == "remove":
            bl.pop(i)
        elif op["op"] == "edit":
            bl[i] = {**bl[i], **op["block"]}
        elif op["op"] == "move":
            b = bl.pop(i)
            dest = blocks(op["to_slot"])
            j = op.get("to_index")
            dest.insert(len(dest) if j is None else max(0, min(j, len(dest))), b)
    return [{"slot": s, "blocks": by_slot[s]} for s in order if by_slot[s]]


def describe(op: dict[str, Any], slots: list[dict[str, Any]], fields: dict[str, Any]) -> str:
    label = {s["id"]: s.get("label") or s["id"] for s in slots}
    b = op.get("block") or {}
    what = b.get("text") or (fields.get(str(b.get("field") or "").split(".")[0]) or {}).get("string") or b.get("type") or "block"
    where = label.get(op["slot"], op["slot"])
    return {"add": f"Add {what} to {where}", "remove": f"Remove block {op.get('index', 0) + 1} from {where}",
            "edit": f"Change block {op.get('index', 0) + 1} in {where}",
            "move": f"Move block {op.get('index', 0) + 1} from {where} to {label.get(op.get('to_slot'), op.get('to_slot'))}"}[op["op"]]


def propose(text: str, placements: list[dict[str, Any]], slots: list[dict[str, Any]], fields: dict[str, Any], *, email: bool) -> dict[str, Any]:
    text = (text or "").strip()
    if not text or len(text) > 500:
        raise EngineError("Describe the change in up to 500 characters.")
    types = rb.EMAIL_BLOCK_TYPES if email else rb.BLOCK_TYPES
    payload = {"request": text, "document": "email" if email else "report",
               "slots": [{"id": s["id"], "label": s.get("label") or s["id"]} for s in slots][:80],
               "placed": placements or [], "fields": vai.field_list(fields), "block_types": sorted(types),
               "block_shapes": {t: BLOCK_SHAPES[t] for t in sorted(types) if t in BLOCK_SHAPES}}
    raw = vai._call(SYSTEM_PROMPT, payload, SCHEMA, "email_edit" if email else "report_edit")
    ops, unclear, choices = shape_ops(raw, slots, types)
    return {"ops": ops, "unclear": unclear, "choices": choices if not ops else [],
            "descriptions": [describe(o, slots, fields) for o in ops]}
