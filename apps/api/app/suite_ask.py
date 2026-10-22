"""Configuration Suite stage 2: Ask (Copilot) steps with code validation.

Order: money questions are routed by code to Odoo's own screens; a batch
request is turned into a plan (prompt 9.2 when an allowed AI is set up, else a
plain code reader), and the validator keeps only record types, fields, values
and buttons that exist in the input packet. Unknown names are dropped; if the
request needs a field that doesn't exist, there is no plan, only "unclear".
"""

from __future__ import annotations

import difflib
import json
import re
from typing import Any

from app.suite_change import BUTTONS, MONEY_ROUTE

PROMPT_92 = ("You turn one request into a plan to change many records in an Odoo database. You receive the request, the record types with their labels, "
             "their fields with labels, types and choice values, and the buttons each record type offers. Return only JSON matching the schema. Use only "
             "record types, fields, values and buttons from the input. Never invent anything not in the input. If the request is ambiguous or needs something "
             "not in the input, return no plan and explain in \"unclear\" in one plain sentence. Never plan changes to accounting fields.")
PROMPT_93 = ("You help a person choose between ways to set up Odoo. You receive the topic, facts from their database (each with an id) and documentation "
             "excerpts for their Odoo version. Ask the one question that most changes the outcome, with at most four options. For each option, say in plain "
             "words what changes and how hard it is to reverse, citing only the given fact ids. Never invent facts, numbers, scores or settings not in the input. "
             "If the database already decides the question, say so instead of asking.")
PROMPT_94 = ("You describe one scheduled job in an Odoo database in one plain sentence for a non-technical person. You receive its name, the record type label, "
             "how often it runs, and the label of the action it calls. Say what it does and how often, using only the input. Never guess effects that are not "
             "stated in the input. If the input is not enough, return \"Runs {how often} on {record type}.\" exactly.")

MONEY_TOPICS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(tax|taxes|vat|gst|withholding)\b", re.I), MONEY_ROUTE["account.tax"]),
    (re.compile(r"\b(chart of accounts?|account codes?|ledger accounts?)\b", re.I), MONEY_ROUTE["account.account"]),
    (re.compile(r"\b(journals?)\b", re.I), MONEY_ROUTE["account.journal"]),
    (re.compile(r"\bfiscal positions?\b", re.I), "Change fiscal positions in Odoo: Accounting > Configuration > Fiscal Positions."),
    (re.compile(r"\b(post|unpost|cancel|edit|change)\b.*\b(invoices?|bills?|entries)\b", re.I), MONEY_ROUTE["account.move"]),
    (re.compile(r"\block dates?\b", re.I), "Set lock dates in Odoo: Accounting > Accounting > Lock Dates."),
]
BATCH_MODELS = ["sale.order", "purchase.order", "crm.lead", "res.partner", "product.template", "project.task"]


def money_route_for(text: str) -> str | None:
    for pat, route in MONEY_TOPICS:
        if pat.search(text):
            return route
    return None


def packet(client: Any, models: list[str] | None = None) -> dict[str, Any]:
    """What the AI may use: record types, their fields (labels, types, choices) and buttons. Code reads it live."""
    want = models or BATCH_MODELS
    live = {r["model"]: r["name"] for r in client.execute_kw("ir.model", "search_read", [[("model", "in", want)]], {"fields": ["model", "name"]})}
    out = []
    for m in want:
        if m not in live:
            continue
        meta = client.execute_kw(m, "fields_get", [], {"attributes": ["string", "type", "selection", "readonly", "store", "relation"]})
        fields = [{"name": f, "label": v.get("string") or f, "type": v.get("type"), "choices": [k for k, _ in (v.get("selection") or [])],
                   "relation": v.get("relation")}
                  for f, v in meta.items() if v.get("store") and not v.get("readonly") and v.get("type") not in {"binary", "one2many", "many2many"}]
        out.append({"model": m, "label": live[m], "fields": fields, "buttons": [{"key": k, "label": b["label"]} for k, b in BUTTONS.get(m, {}).items()]})
    return {"record_types": out}


def validate_plan(raw: Any, pk: dict[str, Any]) -> dict[str, Any]:
    """Keep only what exists in the packet. Unknown filters are dropped; an unknown change means no plan."""
    if not isinstance(raw, dict):
        return {"plan": None, "unclear": "The request could not be read as a plan.", "dropped": []}
    if raw.get("unclear"):
        return {"plan": None, "unclear": str(raw["unclear"])[:300], "dropped": []}
    types = {t["model"]: t for t in pk["record_types"]}
    by_label = {t["label"].lower(): t for t in pk["record_types"]}
    rt = types.get(str(raw.get("record_type"))) or by_label.get(str(raw.get("record_type", "")).lower())
    dropped: list[str] = []
    if not rt:
        return {"plan": None, "unclear": "That record type isn't in this database.", "dropped": [str(raw.get("record_type"))]}
    if rt["model"].startswith("account."):
        return {"plan": None, "unclear": "The suite doesn't plan changes to accounting records.", "dropped": []}
    fields = {f["name"]: f for f in rt["fields"]}
    meta_ok = {"state", "date_order", "create_date", "write_date", "name", "id", "active"}
    filters = []
    for flt in raw.get("filters") or []:
        if isinstance(flt, list | tuple) and len(flt) == 3 and isinstance(flt[0], str):
            base = flt[0].split(".")[0]
            ok_op = flt[1] in {"=", "!=", ">", "<", ">=", "<=", "in", "not in", "ilike", "like"}
            if (base in fields or base in meta_ok) and ok_op:
                if base in fields and fields[base]["choices"] and flt[1] in {"=", "!="} and flt[2] not in fields[base]["choices"]:
                    dropped.append(f"{flt[0]}={flt[2]}")
                    continue
                filters.append([flt[0], flt[1], flt[2]])
                continue
        dropped.append(json.dumps(flt, default=str)[:80])
    ch = raw.get("change") or {}
    if not isinstance(ch, dict):
        return {"plan": None, "unclear": "The change could not be read.", "dropped": dropped}
    if ch.get("button"):
        keys = {b["key"] for b in rt["buttons"]}
        b = str(ch["button"])
        if b not in keys:
            lab = {x["label"].lower(): x["key"] for x in rt["buttons"]}
            b = lab.get(b.lower(), "")
        if not b:
            return {"plan": None, "unclear": f"{rt['label']} has no button called '{ch['button']}' here.", "dropped": dropped + [str(ch["button"])]}
        change = {"tool": "transitions", "button": b}
    elif ch.get("field"):
        f = str(ch["field"])
        if f not in fields:
            return {"plan": None, "unclear": f"There's no field called '{f}' on {rt['label']}.", "dropped": dropped + [f]}
        v = ch.get("value")
        if fields[f]["choices"] and v not in fields[f]["choices"]:
            return {"plan": None, "unclear": f"'{v}' is not a choice for {fields[f]['label']}.", "dropped": dropped}
        change = {"tool": "edit", "field": f, "value": v}
    else:
        return {"plan": None, "unclear": "Say what should change.", "dropped": dropped}
    return {"plan": {"record_type": rt["model"], "label": rt["label"], "filters": filters, "change": change}, "unclear": None, "dropped": dropped}


def _closest(word: str, options: dict[str, Any]) -> Any:
    hit = difflib.get_close_matches(word.lower(), list(options), n=1, cutoff=0.8)
    return options[hit[0]] if hit else None


def read_request(text: str, pk: dict[str, Any]) -> dict[str, Any]:
    """Plain code reader for when no allowed AI is set up. Same output shape as 9.2; the validator still runs."""
    t = text.strip().lower()
    labels = {}
    for rt in pk["record_types"]:
        labels[rt["label"].lower()] = rt
        labels[rt["label"].lower().rstrip("s")] = rt
    aliases = {"quotation": "sale.order", "quotations": "sale.order", "orders": "sale.order", "leads": "crm.lead", "opportunities": "crm.lead",
               "contacts": "res.partner", "customers": "res.partner", "products": "product.template", "purchases": "purchase.order", "tasks": "project.task"}
    rt = None
    for w, m in aliases.items():
        if re.search(rf"\b{w}\b", t):
            rt = next((x for x in pk["record_types"] if x["model"] == m), None)
            break
    if rt is None:
        for lab, x in labels.items():
            if lab and lab in t:
                rt = x
                break
    if rt is None:
        return {"record_type": None, "filters": [], "change": {}, "unclear": "Say which records: for example quotations, leads or contacts."}
    filters: list[Any] = []
    if rt["model"] == "sale.order" and re.search(r"\bsent\b", t):
        filters.append(["state", "=", "sent"])
    elif rt["model"] == "sale.order" and re.search(r"\bquotations?\b", t):
        filters.append(["state", "in", ["draft", "sent"]])
    m = re.search(r"\b(?:set|change)\s+(?:the\s+)?(.+?)\s+to\s+(.+?)(?:\s+on\b|\s+for\b|$)", text.strip(), re.I)
    if m:
        flabel, value = m.group(1).strip().lower(), m.group(2).strip().strip("'\"")
        fmap = {f["label"].lower(): f for f in rt["fields"]}
        f = fmap.get(flabel) or _closest(flabel, fmap)
        if not f:
            return {"record_type": rt["model"], "filters": filters, "change": {"field": flabel}, "unclear": None}
        v: Any = value
        if f["type"] == "many2one":
            v = {"ref": value}
        elif f["type"] == "boolean":
            v = value in {"yes", "true", "on"}
        elif f["choices"]:
            v = next((c for c in f["choices"] if c.lower() == value.lower()), value)
        return {"record_type": rt["model"], "filters": filters, "change": {"field": f["name"], "value": v}, "unclear": None}
    for b in rt["buttons"]:
        verb = b["label"].lower().split()[0]
        if re.search(rf"\b{re.escape(verb)}\b", t):
            return {"record_type": rt["model"], "filters": filters, "change": {"button": b["key"]}, "unclear": None}
    return {"record_type": rt["model"], "filters": filters, "change": {}, "unclear": "Say what should change: a button such as Confirm, or 'set {field} to {value}'."}


def ai_allowed(cloud_ai: bool) -> bool:
    from app.llm_provider import resolve_provider_mode

    mode = resolve_provider_mode()
    return mode != "off" and (mode == "ollama" or cloud_ai)


def ai_json(system: str, payload: dict[str, Any], *, cloud_ai: bool, step: str) -> Any:
    """One AI JSON step through the existing gateway, only when D6 allows it. None when not allowed or it fails."""
    if not ai_allowed(cloud_ai):
        return None
    try:
        from app.llm_provider import generate_json_with_timeout_retry, get_llm_provider

        prov = get_llm_provider()
        if prov is None:
            return None
        from app.ai_client.guards import fence_fields

        payload = fence_fields(payload, source="odoo_records")
        raw = generate_json_with_timeout_retry(prov, json.dumps(payload, default=str), system=system, timeout_s=60, log_step=f"suite_{step}")
        return json.loads(raw)
    except Exception:  # noqa: BLE001  any AI trouble falls back to code
        return None


# ---------------------------------------------------------------- decision guide (9.3 shape, code-grounded)
def guide(topic: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    f = {x["id"]: x for x in facts}
    if topic == "costing":
        decided = f.get("posted_entries", {}).get("value", 0) or f.get("done_moves", {}).get("value", 0)
        if decided:
            return {"question": None, "decided": "This database already has posted entries or stock moves, so the costing method stays as it is. "
                    "Changing it now is done product category by category in Odoo, with a valuation entry.", "options": [], "why_asking": None,
                    "facts": facts}
        return {"question": "How should product costs be worked out?", "why_asking": "It changes your margins and stock value and is hard to change after the first stock move.",
                "options": [
                    {"label": "Standard price", "what_changes": "Each product keeps a fixed cost you set.", "affects_fact_ids": ["categories"], "reversible": "easy"},
                    {"label": "Average cost", "what_changes": "Cost follows the average of what you paid.", "affects_fact_ids": ["categories", "stock_installed"], "reversible": "hard"},
                    {"label": "First in, first out", "what_changes": "Cost follows the oldest stock first.", "affects_fact_ids": ["categories", "stock_installed"], "reversible": "hard"}],
                "facts": facts, "decided": None}
    if topic == "delivery_steps":
        if not f.get("stock_installed", {}).get("value"):
            return {"question": None, "decided": "Inventory is not installed, so there are no delivery steps to choose.", "options": [], "why_asking": None, "facts": facts}
        return {"question": "How many steps should a delivery take?", "why_asking": "It decides the transfers your warehouse handles for every order.",
                "options": [
                    {"label": "Ship directly", "what_changes": "One transfer from stock to the customer.", "affects_fact_ids": ["warehouses", "delivery_steps"], "reversible": "easy"},
                    {"label": "Pick, then ship", "what_changes": "Two transfers: pick to an output area, then ship.", "affects_fact_ids": ["warehouses", "delivery_steps"], "reversible": "easy"},
                    {"label": "Pick, pack, then ship", "what_changes": "Three transfers with a packing step.", "affects_fact_ids": ["warehouses", "delivery_steps"], "reversible": "easy"}],
                "facts": facts, "decided": None}
    if topic == "multi_company":
        return {"question": "Do you need separate companies, or one company with branches?", "why_asking": "Companies keep separate books; branches share them.",
                "options": [
                    {"label": "Keep one company", "what_changes": "Nothing changes.", "affects_fact_ids": ["companies"], "reversible": "easy"},
                    {"label": "Add branches", "what_changes": "Branches share the parent's books and settings.", "affects_fact_ids": ["companies"], "reversible": "hard"},
                    {"label": "Add separate companies", "what_changes": "Each company gets its own books, taxes and users' access.", "affects_fact_ids": ["companies", "multi_company_on"], "reversible": "after_posting_no"}],
                "facts": facts, "decided": None}
    return {"question": None, "decided": None, "options": [], "why_asking": None, "facts": facts, "unknown_topic": True}


def validate_guide(raw: Any, fact_ids: set[str]) -> dict[str, Any] | None:
    """9.3 output check: at most 4 options, cited facts must exist, reversible from the allowed words."""
    if not isinstance(raw, dict):
        return None
    opts = []
    for o in (raw.get("options") or [])[:4]:
        if not isinstance(o, dict) or o.get("reversible") not in {"easy", "hard", "after_posting_no"}:
            continue
        ids = [i for i in o.get("affects_fact_ids") or [] if i in fact_ids]
        opts.append({"label": str(o.get("label") or "")[:80], "what_changes": str(o.get("what_changes") or "")[:240], "affects_fact_ids": ids, "reversible": o["reversible"]})
    if not opts and not raw.get("decided"):
        return None
    return {"question": raw.get("question"), "options": opts, "why_asking": raw.get("why_asking"), "decided": raw.get("decided")}
