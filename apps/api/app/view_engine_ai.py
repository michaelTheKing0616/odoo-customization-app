"""AI steps of the View Designer (SPEC 3.1 and 3.2). Proposal only.

The model returns a proposal object; code here validates every node id, field,
operator and value, and the router compiles it like any other edit. AI never
calls compile or publish. Prompts are the SPEC's, word for word.
"""

from __future__ import annotations

import json
from typing import Any

from app import view_engine_logic as vl
from app.view_engine import EngineError

BUILDER_MODEL = "gemini-3.8-flash"

# SPEC 3.1, verbatim.
EDIT_SYSTEM_PROMPT = (
    "You turn one request about an Odoo screen into edit operations. You receive the screen as a JSON tree of nodes "
    "with ids, and the model's field list with names, labels and types. Return only JSON matching the schema. Use only "
    "node ids and field names that appear in the input. Never invent fields, groups, records or facts not in the input. "
    "If the request needs something that is not in the input, return no ops and explain in \"unclear\" in one plain "
    "sentence a non-technical person understands. Prefer the smallest change that does what was asked. Do not change "
    "anything the request did not mention."
)

# SPEC 3.2, verbatim.
CONDITION_SYSTEM_PROMPT = (
    "You turn one sentence about when a field should be shown, hidden, required or read-only into a condition tree. You "
    "receive the sentence and the model's field list with names, labels, types and selection values. Return only JSON "
    "matching the schema. Use only fields and values from the input. Never invent facts not in the input. If the "
    "sentence is ambiguous, return the two most likely readings, each with a one-line plain description, and no others."
)

ALLOWED_EDIT_OPS = ("move", "insert_field", "hide", "set_attr", "wrap", "set_condition")

EDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": list(ALLOWED_EDIT_OPS)},
                    "node": {"type": "string"},
                    "target": {"type": "string"},
                    "position": {"type": "string", "enum": ["before", "after", "inside"]},
                    "field": {"type": "string"},
                    "attr": {"type": "string"},
                    "value": {"type": "string"},
                    "nodes": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["group", "page", "notebook"]},
                    "label": {"type": "string"},
                },
                "required": ["op"],
            },
        },
        "unclear": {"type": ["string", "null"]},
        "choices": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
    },
    "required": ["ops", "unclear"],
}
# Attributes the AI may set; anything else is refused by code (SPEC 20.1: AI proposes, code authorizes).
ATTR_ALIASES = {"label": "string", "title": "string", "caption": "string"}
EDIT_ATTRS = frozenset({"string", "required", "readonly", "invisible", "groups", "placeholder", "help", "nolabel"})
AMBIGUITY_NOTE = ("If the request could mean two or three different things, return no ops, a one-sentence question in "
                  "\"unclear\" and up to three short rewordings in \"choices\", each meaning one thing. Groups go on the "
                  "field or button itself, never on the whole screen, and use only ids listed in \"groups\". To rename, set attr \"string\". Allowed attrs: "
                  "string, required, readonly, invisible, groups, placeholder, help, nolabel.")

RULE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "field": {"type": "string"},
        "op": {"type": "string", "enum": sorted({o for ops in vl.OPS_BY_TYPE.values() for o in ops})},
        "value": {},
    },
    "required": ["field", "op"],
}
CONDITION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "readings": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "sense": {"type": "string", "enum": ["show", "hide"]},
                    "match": {"type": "string", "enum": ["all", "any"]},
                    "rules": {"type": "array", "items": RULE_SCHEMA},
                },
                "required": ["description", "match", "rules"],
            },
        },
        "unclear": {"type": ["string", "null"]},
    },
    "required": ["readings"],
}


class AIUnavailable(RuntimeError):
    """No AI provider is configured or it failed. Message is plain language."""


def _provider() -> Any:
    from app.llm_provider import get_llm_provider_for_tier

    prov = get_llm_provider_for_tier("fast")
    if prov is None:
        raise AIUnavailable("Writing changes from a sentence isn't switched on for this workspace. Use the panels instead.")
    return prov


def designer_json(system: str, payload: dict[str, Any], schema: dict[str, Any], step: str) -> dict[str, Any]:
    from app.llm_json import parse_llm_json_object
    from app.llm_provider import LLMError, generate_json_with_timeout_retry

    prov = _provider()
    # Some providers (Gemini here) only honour "reply in JSON", not the schema
    # itself, so the schema also travels with the input. The system prompt stays
    # the SPEC's wording.
    payload = {**payload, "answer_schema": schema}
    model = BUILDER_MODEL if getattr(prov, "name", "") == "gemini" else None
    try:
        text = generate_json_with_timeout_retry(
            prov, json.dumps(payload, ensure_ascii=False), system=system, timeout_s=45.0,
            temperature=0.0, format_schema=schema, model=model, log_step=step,
        )
    except LLMError as exc:
        if model:
            try:
                text = generate_json_with_timeout_retry(
                    prov, json.dumps(payload, ensure_ascii=False), system=system, timeout_s=45.0,
                    temperature=0.0, format_schema=schema, model=None, log_step=step,
                )
            except LLMError as exc2:
                raise AIUnavailable(f"The assistant didn't answer ({str(exc2)[:120]}). Use the panels instead.") from exc2
        else:
            raise AIUnavailable(f"The assistant didn't answer ({str(exc)[:120]}). Use the panels instead.") from exc
    try:
        return parse_llm_json_object(text)
    except Exception as exc:  # noqa: BLE001
        raise AIUnavailable("The assistant's answer couldn't be read. Try rewording, or use the panels.") from exc


def slim_tree(tree: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    node: dict[str, Any] = {"id": tree["id"], "tag": tree["tag"], "label": tree.get("label") or ""}
    if tree.get("name"):
        node["name"] = tree["name"]
    if not tree.get("anchor"):
        node["locked"] = True
    kids = [slim_tree(c, depth + 1) for c in tree.get("children") or []]
    if kids:
        node["children"] = kids
    return node


def field_list(fields: dict[str, Any], values: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    out = []
    for name, meta in sorted(fields.items()):
        if name.startswith("__"):
            continue
        row: dict[str, Any] = {"name": name, "label": meta.get("string") or name, "type": meta.get("type")}
        if meta.get("selection"):
            row["values"] = [{"value": k, "label": lbl} for k, lbl in meta["selection"]][:40]
        elif values and name in values:
            row["values"] = values[name]
        out.append(row)
    return out


# ----------------------------------------------------------------------------
# 3.1 Plain-English edit
# ----------------------------------------------------------------------------

def validate_edit_proposal(raw: Any, tree_ids: set[str], fields: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Reject the whole proposal if any id, field or op is not in the input."""
    if not isinstance(raw, dict):
        raise EngineError("The assistant's answer couldn't be read.")
    unclear = raw.get("unclear")
    unclear = str(unclear).strip()[:300] if isinstance(unclear, str) and unclear.strip() else None
    ops = raw.get("ops")
    if not isinstance(ops, list):
        raise EngineError("The assistant's answer couldn't be read.")
    if len(ops) > 20:
        raise EngineError("The assistant proposed too many changes at once. Ask for something smaller.")
    clean: list[dict[str, Any]] = []
    for op in ops:
        if not isinstance(op, dict) or op.get("op") not in ALLOWED_EDIT_OPS:
            raise EngineError("The assistant proposed a kind of change Ingenium doesn't allow.")
        kind = op["op"]
        out: dict[str, Any] = {"op": kind}
        for key in ("node", "target"):
            if key in op and op[key] is not None:
                if str(op[key]) not in tree_ids:
                    raise EngineError(f"The assistant pointed at something that isn't on this screen ({op[key]}). Nothing was changed.")
                out[key] = str(op[key])
        if kind in {"move", "hide", "set_attr", "set_condition"} and "node" not in out:
            raise EngineError("The assistant's change didn't say what to change.")
        if kind in {"move", "insert_field"}:
            if "target" not in out:
                raise EngineError("The assistant's change didn't say where.")
            pos = op.get("position") or "after"
            if pos not in {"before", "after", "inside"}:
                raise EngineError("The assistant's change used a place Ingenium doesn't allow.")
            out["position"] = pos
        if kind == "insert_field":
            f = str(op.get("field") or "")
            if f not in fields:
                raise EngineError(f"The assistant suggested a field that doesn't exist here ('{f}'). Nothing was changed.")
            out["field"] = f
        if kind == "set_attr":
            out["attr"] = ATTR_ALIASES.get(str(op.get("attr") or ""), str(op.get("attr") or ""))
            if out["attr"] not in EDIT_ATTRS:
                raise EngineError(f"The assistant tried to change '{out['attr']}', which Ingenium doesn't allow from a sentence. Nothing was changed.")
            out["value"] = str(op.get("value") if op.get("value") is not None else "")
        if kind == "wrap":
            nodes = op.get("nodes") or []
            if not isinstance(nodes, list) or not nodes or any(str(n) not in tree_ids for n in nodes):
                raise EngineError("The assistant pointed at something that isn't on this screen. Nothing was changed.")
            out["nodes"] = [str(n) for n in nodes]
            out["kind"] = op.get("kind") if op.get("kind") in {"group", "page", "notebook"} else "group"
            out["label"] = str(op.get("label") or "")[:80]
        if kind == "set_condition":
            cond = op.get("condition")
            if isinstance(cond, dict):
                for r in cond.get("rules") or []:
                    if not isinstance(r, dict) or str(r.get("field") or "") not in fields:
                        raise EngineError("The assistant used a field that doesn't exist here. Nothing was changed.")
            out.update({k: op[k] for k in ("attr", "sense", "condition") if k in op})
        clean.append(out)
    if not clean and not unclear:
        unclear = "The assistant couldn't tell what to change. Try naming the field and what should happen to it."
    return clean, unclear


def propose_edit(text: str, tree: dict[str, Any], fields: dict[str, Any], groups: list[dict[str, str]] | None = None,
                 choices_out: list[str] | None = None) -> tuple[list[dict[str, Any]], str | None]:
    text = (text or "").strip()
    if not text or len(text) > 500:
        raise EngineError("Describe the change in up to 500 characters.")
    payload = {"request": text, "screen": slim_tree(tree), "fields": field_list(fields), "note": AMBIGUITY_NOTE}
    if groups:
        payload["groups"] = groups
    raw = designer_json(EDIT_SYSTEM_PROMPT, payload, EDIT_SCHEMA, "view_designer_edit")
    if choices_out is not None and isinstance(raw, dict) and isinstance(raw.get("choices"), list):
        choices_out.extend(c for c in (str(x).strip()[:120] for x in raw["choices"][:3]) if c)
    ids: set[str] = set()

    def walk(n: dict[str, Any]) -> None:
        ids.add(n["id"])
        for c in n.get("children") or []:
            walk(c)

    walk(tree)
    return validate_edit_proposal(raw, ids, fields)


# ----------------------------------------------------------------------------
# 3.2 Condition from words
# ----------------------------------------------------------------------------

def resolve_m2o_values(rules: list[dict[str, Any]], fields: dict[str, Any], lookup: Any) -> dict[str, dict[int, str]]:
    """Turn many2one names the model wrote ("Won") into ids via ``lookup(relation, name)``,
    which returns [(id, name)] from Odoo. Names that don't resolve are left for the validator to refuse."""
    names: dict[str, dict[int, str]] = {}
    for r in rules:
        meta = fields.get(str(r.get("field") or "")) or {}
        if meta.get("type") != "many2one" or not meta.get("relation"):
            continue
        vals = r.get("value") if isinstance(r.get("value"), list) else [r.get("value")]
        out_vals: list[Any] = []
        for v in vals:
            if isinstance(v, int) and not isinstance(v, bool):
                hits = lookup(meta["relation"], None, [v])
            else:
                hits = lookup(meta["relation"], str(v or ""), None)
            exact = [h for h in hits if str(h[1]).strip().lower() == str(v).strip().lower()] or hits
            if len(exact) == 1:
                out_vals.append(int(exact[0][0]))
                names.setdefault(r["field"], {})[int(exact[0][0])] = str(exact[0][1])
            else:
                out_vals.append(v)
        r["value"] = out_vals if isinstance(r.get("value"), list) else out_vals[0]
    return names


def validate_condition_proposal(raw: Any, fields: dict[str, Any], lookup: Any) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(raw, dict):
        raise EngineError("The assistant's answer couldn't be read.")
    readings = raw.get("readings")
    unclear = raw.get("unclear") if isinstance(raw.get("unclear"), str) and raw.get("unclear").strip() else None
    if not isinstance(readings, list):
        raise EngineError("The assistant's answer couldn't be read.")
    out: list[dict[str, Any]] = []
    problems: list[str] = []
    for reading in readings[:2]:
        if not isinstance(reading, dict):
            continue
        rules = [dict(r) for r in reading.get("rules") or [] if isinstance(r, dict)]
        try:
            names = resolve_m2o_values(rules, fields, lookup)
            clean = vl.validate_condition({"match": reading.get("match"), "rules": rules}, fields, record_names=names)
        except EngineError as exc:
            problems.append(str(exc))
            continue
        sentence = vl.condition_sentence(clean, fields, names)
        out.append({
            "sense": "hide" if reading.get("sense") == "hide" else "show",
            "condition": clean,
            "sentence": sentence,
            "expression": vl.compile_condition(clean),
            "record_names": {k: {str(i): n for i, n in v.items()} for k, v in names.items()},
        })
    if not out and not unclear:
        unclear = problems[0] if problems else "The assistant couldn't turn that into a rule. Try the dropdowns."
    return out, unclear


def propose_condition(text: str, attr: str, fields: dict[str, Any], values: dict[str, list[dict[str, Any]]], lookup: Any) -> tuple[list[dict[str, Any]], str | None]:
    text = (text or "").strip()
    if not text or len(text) > 300:
        raise EngineError("Describe the rule in up to 300 characters.")
    usable = {k: v for k, v in fields.items() if (v.get("type") in vl.OPS_BY_TYPE)}
    payload = {
        "sentence": text,
        "applies_to": {"invisible": "when the field is shown or hidden", "required": "when it must be filled in",
                       "readonly": "when it is read-only", "column_invisible": "when the column is hidden"}.get(attr, attr),
        "fields": field_list(usable, values),
        "operators": vl.OP_WORDS,
    }
    raw = designer_json(CONDITION_SYSTEM_PROMPT, payload, CONDITION_SCHEMA, "view_designer_condition")
    return validate_condition_proposal(raw, usable, lookup)


# ----------------------------------------------------------------------------
# Tidy up (stage 2b): group the screen's fields by meaning. Proposal only;
# view_engine_library.validate_sections keeps fields that are on the screen
# and tidy_plan turns it into moves the compiler checks again.
# ----------------------------------------------------------------------------

TIDY_SYSTEM_PROMPT = (
    "You group the fields of one Odoo screen by what they mean to the person filling it in. "
    "You receive the fields with names, labels and types. Return only JSON matching the schema. "
    "Use only field names from the input and put each field in at most one group. "
    "Give each group a short plain title. Never invent fields or facts not in the input. "
    "If the fields have no clear groups, return an empty list."
)
TIDY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"sections": {"type": "array", "items": {"type": "object", "properties": {
        "title": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}},
        "required": ["title", "fields"]}}},
    "required": ["sections"],
}


def propose_sections(screen_fields: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {"fields": screen_fields[:120]}
    return designer_json(TIDY_SYSTEM_PROMPT, payload, TIDY_SCHEMA, "view_designer_tidy")
