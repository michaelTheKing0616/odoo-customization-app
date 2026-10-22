"""Model authorizer (APP_STUDIO_FIX_PLAN (b)): AI proposes models, code authorizes them.

Pure: no I/O, no LLM. Idempotent, independent of model order, never adds a model, biased to fold.
No English cue lists: lexical judgements come from the LLM (contract roles, model evidence) and code
only verifies them (verbatim spans in the owner's own brief, structure of the design).

Verified data shapes (2026-10-19):
- contract rows (design.intent_contract): {id, kind, subject, decision, origin, evidence:{quote,start,end}, role?}
  `role` is new (record|attribute|dimension|context|future|rule|access); absent on old recordings.
- DesignModel.requirement_ids, DesignModel.evidence? {quote, owner_fields[], role} (new; absent on old recordings).
- design.left_out rows {id, item, quote, ...}: things the owner said wait/maybe/not.
Fallback when a model has no evidence (old recordings): a label token found verbatim in the owner's brief
anchors it, with the sentence around it as the quote; own attributes come from the brief's clauses.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

RELATIONAL = {"many2one", "one2many", "many2many"}
KEEP, KEEP_LINE, FOLD, DROP, SUGGEST = "keep", "keep_line", "fold", "drop", "suggest"


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").casefold()
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in t if not unicodedata.combining(c))))


def stems(text: str) -> set[str]:
    """Language-agnostic 5-char prefixes of tokens of 3+ letters (no stop list)."""
    # A final "s" is dropped on longer tokens so a plural and its singular share a prefix (items/item).
    return {(w[:-1] if len(w) > 4 and w.endswith("s") else w)[:5] for w in norm(text).split() if len(w) >= 3 and not w.isdigit()}


def verbatim(quote: str, brief_n: str) -> bool:
    q = norm(quote)
    return bool(q) and q in brief_n


def clauses(brief: str) -> list[str]:
    """Owner phrases: split on punctuation only (works for any language / code-switching)."""
    return [c.strip() for c in re.split(r"[,;:.!?()\n\-–—/]+", brief or "") if len(norm(c)) >= 3]


def _sentences(brief: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n]+", brief or "") if s.strip()]


@dataclass
class Call:
    model: str
    label: str
    verdict: str
    rule: str
    reason: str
    fold: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthResult:
    calls: list[Call]

    @property
    def touched(self) -> bool:
        return any(c.verdict not in {KEEP, KEEP_LINE} for c in self.calls)

    def to_list(self) -> list[dict[str, Any]]:
        return [c.__dict__ for c in self.calls]


def _own_fields(m: Any) -> list[Any]:
    """The model's own facts: not links, not its name/label field."""
    lab = stems(m.label or m.name.removeprefix("x_").replace("_", " "))
    out = []
    for f in m.fields:
        if f.ttype in RELATIONAL or f.name in {"x_name", "name"}:
            continue
        fs = stems(f.string or f.name)
        if fs and fs <= lab | {"name", "title"}:
            continue
        out.append(f)
    return out


def _gather(m: Any, brief: str, brief_n: str, contract: dict[str, dict[str, Any]], left_quotes: list[str]) -> dict[str, Any]:
    ev = getattr(m, "evidence", None) or {}
    if not (ev.get("quote") or ev.get("owner_fields")):
        ev = {}
    label_st = stems(m.label or m.name.removeprefix("x_").replace("_", " "))
    reqs = [contract[r] for r in (m.requirement_ids or ([m.requirement_id] if getattr(m, "requirement_id", "") else [])) if r in contract]
    quote = str(ev.get("quote") or "")
    bound = verbatim(quote, brief_n) and bool(label_st & stems(quote))
    implicit = ""
    if not ev:  # old recording: anchor on a label token in the owner's words
        for s in _sentences(brief):
            if label_st & stems(s):
                implicit = s
                break
    spans = [str((r.get("evidence") or {}).get("quote") or "") for r in reqs]
    spans = [s for s in spans if verbatim(s, brief_n) and label_st & stems(s)]
    owner_phrases = [q for q in (ev.get("owner_fields") or []) if verbatim(str(q), brief_n)] if ev else clauses(brief)
    return {"ev": ev, "anchored": bound or bool(spans) or bool(implicit), "quote": quote if bound else (spans[0] if spans else implicit),
            "roles": {str(r.get("role") or "") for r in reqs} - {""}, "spans": spans, "phrases": owner_phrases,
            "llm_role": str(ev.get("role") or ""), "own": set(), "label_st": label_st,
            "future": any(s and (norm(s) in norm(lq) or norm(lq) in norm(s)) for s in spans + ([implicit] if implicit else []) for lq in left_quotes if lq)}


def _credit_each_owner_phrase_once(info: dict[str, dict[str, Any]], design: Any) -> None:
    """Each owner word counts for exactly one record (its best-matching field), across new models and stock
    extensions, so one phrase can't be laundered into several models. Words that name a proposed model are
    record names, not facts, and are never credited. Result: info[m]["own"] = the model's fields backed by owner words."""
    targets: list[tuple[str, Any]] = [(m.name, f) for m in design.new_models for f in _own_fields(m)]
    targets += [(f"stock:{e.model}", f) for e in getattr(design, "stock_extensions", []) or [] for f in e.fields if f.ttype not in RELATIONAL]
    label_words = set().union(*[stems(m.label or m.name.removeprefix("x_").replace("_", " ")) for m in design.new_models]) if design.new_models else set()
    owner_words = set().union(*[stems(p) for i in info.values() for p in i["phrases"]]) if info else set()
    for w in sorted(owner_words - label_words):
        best, best_score, best_field = None, 0.0, None
        for name, f in sorted(targets, key=lambda t: (t[0], t[1].name)):
            fs = stems(f.string or f.name)
            if w in fs and 1 / len(fs) > best_score:
                best, best_score, best_field = name, 1 / len(fs), f.name
        if best in info and w in set().union(*[stems(p) for p in info[best]["phrases"]]):
            info[best]["own"].add(best_field)


def _referrers(design: Any, name: str) -> list[tuple[Any, Any]]:
    out = []
    for m in design.new_models:
        for f in m.fields:
            if f.relation == name and m.name != name:
                out.append((m, f))
    for e in getattr(design, "stock_extensions", []) or []:
        for f in e.fields:
            if f.relation == name:
                out.append((e, f))
    return out


def _decide(m: Any, i: dict[str, Any], design: Any, brief_n: str, force_keep: frozenset[str]) -> Call:
    lab = m.label or m.name
    if m.name in force_keep:
        return Call(m.name, lab, KEEP, "0", "The owner added this list.")
    if i["future"]:
        return Call(m.name, lab, SUGGEST, "1", "The owner said this can wait.")
    if not i["anchored"]:
        return Call(m.name, lab, DROP, "2", "Nothing in the owner's words points to this list.")
    own = len(i["own"])
    if "record" in i["roles"] and (i["llm_role"] == "main_record" or own >= 1 or (not i["ev"] and i["spans"])):
        # No designer evidence (v1 prompt): a contract "record" row whose quote is verbatim and names the model.
        return Call(m.name, lab, KEEP, "3", "The owner keeps rows of this.")
    if own >= 2 and not (i["roles"] & {"attribute", "dimension"}):
        return Call(m.name, lab, KEEP, "4", "The owner lists several facts about it.")
    names = {x.name for x in design.new_models}
    parents = {f.relation for f in m.fields if f.ttype == "many2one" and f.relation in names - {m.name}}
    inverse = any(f.ttype == "one2many" and f.relation == m.name for x in design.new_models for f in x.fields)
    refs = _referrers(design, m.name)
    if not i["ev"] and own >= 1 and refs and not (i["roles"] & {"attribute", "dimension"}):
        # Old recordings: a record other records point at and that carries its own owner fact (rule 4, one fact).
        return Call(m.name, lab, KEEP, "4b", "Other records pick from it and the owner gives it its own fact.")
    # Old recordings carry no LLM role: a record that links to one other proposed record and holds an owner fact
    # is treated as that record's lines/transactions (the line_of claim, verified structurally).
    line_claim = i["llm_role"].startswith("line_of:") or (not i["ev"] and (inverse or bool(parents)))
    if line_claim and (len(parents) == 1 or (not i["ev"] and parents)) and own >= 1 and not (i["roles"] & {"attribute", "dimension"}):
        return Call(m.name, lab, KEEP_LINE, "5", "Lines of another record.")
    refs = _referrers(design, m.name)
    if not refs:
        return Call(m.name, lab, DROP, "6", "Nothing in the app uses this list.")
    sel = [f for f in m.fields if f.ttype == "selection" and f.selection]
    values = [v for v in (sel[0].selection if sel else []) if verbatim(str(v[1] if isinstance(v, (list, tuple)) else v), brief_n)]
    as_ = "selection" if len(values) >= 2 else "char"
    host = sorted({getattr(h, "name", "") or getattr(h, "model", "") for h, _ in refs})
    return Call(m.name, lab, FOLD, "7", "The owner names it as a detail of another record.",
                {"as": as_, "on": host, "values": values if as_ == "selection" else []})


def authorize_models(design: Any, *, brief: str, force_keep: frozenset[str] = frozenset(),
                     suggested_not_built: bool = False) -> AuthResult:
    brief_n = norm(brief)
    contract = {str(r.get("id")): r for r in getattr(design, "intent_contract", []) or [] if isinstance(r, dict) and r.get("id")}
    left_quotes = [str(x.get("quote") or x.get("item") or "") for x in getattr(design, "left_out", []) or [] if isinstance(x, dict)]
    contract_future = [str((r.get("evidence") or {}).get("quote") or "") for r in contract.values() if r.get("role") == "future"]
    info = {m.name: _gather(m, brief, brief_n, contract, left_quotes + contract_future) for m in design.new_models}
    _credit_each_owner_phrase_once(info, design)
    calls = []
    for m in sorted(design.new_models, key=lambda m: m.name):
        c = _decide(m, info[m.name], design, brief_n, force_keep)
        if suggested_not_built and getattr(m, "suggested", False) and c.verdict in {KEEP, KEEP_LINE} and m.name not in force_keep:
            # Flipped semantics (fix plan a): suggested = NOT built, the owner opts in.
            c = Call(m.name, c.label, SUGGEST, "s", "Suggested, not built: add it if you want it.")
        calls.append(c)
    return AuthResult(_keep_lines(calls, design, info, contract, brief_n, force_keep))


def _keep_lines(calls: list[Call], design: Any, info: dict[str, dict[str, Any]], contract: dict[str, dict[str, Any]],
                brief_n: str, force_keep: frozenset[str]) -> list[Call]:
    """Rule 5b (structural, one pass over first-pass verdicts, so order-independent): a model is kept as the
    lines of a kept parent when it has a many2one to that parent, the parent has the one2many back, and the
    owner gives the line at least one fact (an owner word credited to one of its fields, or a linked contract
    row whose quote is verbatim in the brief, e.g. a quantity or price per item). Never adds a model."""
    verdict = {c.model: c.verdict for c in calls}
    by_name = {m.name: m for m in design.new_models}
    out = []
    for c in calls:
        m = by_name[c.model]
        if c.verdict in {KEEP, KEEP_LINE, SUGGEST} or c.model in force_keep:
            out.append(c)
            continue
        parents = {f.relation for f in m.fields if f.ttype == "many2one" and verdict.get(f.relation) in {KEEP, KEEP_LINE}}
        backed = {p for p in parents if any(f.ttype == "one2many" and f.relation == m.name for f in by_name[p].fields)}
        reqs = [contract[r] for r in (m.requirement_ids or ([m.requirement_id] if m.requirement_id else [])) if r in contract]
        quoted = any(verbatim(str((r.get("evidence") or {}).get("quote") or ""), brief_n) for r in reqs)
        if backed and (info[m.name]["own"] or quoted) and not (info[m.name]["roles"] & {"future"}):
            out.append(Call(m.name, c.label, KEEP_LINE, "5b", f"Lines of {by_name[sorted(backed)[0]].label or sorted(backed)[0]}."))
        else:
            out.append(c)
    return out


def apply_calls(design: Any, result: AuthResult) -> list[str]:
    """Rewrite the design for fold/drop/suggest verdicts; returns owner-facing notes. Never adds a model."""
    from app.ai_conversation.app_design import DesignField

    gone = {c.model: c for c in result.calls if c.verdict in {FOLD, DROP, SUGGEST}}
    if not gone:
        return []
    by_name = {m.name: m for m in design.new_models}
    notes: list[str] = []
    for owner in list(design.new_models) + list(getattr(design, "stock_extensions", []) or []):
        kept_fields = []
        for f in owner.fields:
            c = gone.get(f.relation or "")
            if not c:
                kept_fields.append(f)
                continue
            if f.ttype == "many2one" and c.verdict == FOLD:
                vals = c.fold.get("values") or []
                kept_fields.append(DesignField(name=f.name[:-3] if f.name.endswith("_id") else f.name, string=f.string,
                                               ttype="selection" if vals else "char", required=f.required,
                                               selection=[[re.sub(r"\W+", "_", norm(str(v[1] if isinstance(v, (list, tuple)) else v)))[:30],
                                                           str(v[1] if isinstance(v, (list, tuple)) else v)] for v in vals],
                                               help=f.help, requirement_id=f.requirement_id, requirement_ids=list(f.requirement_ids)))
            # o2m/m2m to a folded/dropped model and m2o to a dropped one are removed
        owner.fields = kept_fields
    design.new_models = [m for m in design.new_models if m.name not in gone]
    names = set(gone)
    design.menus = [x for x in design.menus if not any(norm(by_name[n].label) == norm(str(x)) for n in names if by_name[n].label)]
    design.record_rules = [r for r in design.record_rules if r.get("model") not in names]
    design.automations = [a for a in design.automations if a.get("target_model") not in names]
    for g in design.security_groups:
        g.access = {k: v for k, v in g.access.items() if k not in names}
    for p in design.python_needed:
        p["models"] = [x for x in p.get("models") or [] if x not in names]
    design.relations = [r for r in design.relations if r.get("model") not in names and r.get("target") not in names]
    folded = getattr(design, "folded", None)
    for c in sorted(gone.values(), key=lambda c: c.model):
        m = by_name[c.model]
        if c.verdict == FOLD:
            notes.append(f"I kept **{c.label}** as a simple choice on {', '.join(h.replace('x_', '').replace('_', ' ') for h in c.fold['on'])} "
                         f"instead of a separate list. Want to manage {c.label} as its own list? Add it.")
        elif c.verdict == SUGGEST:
            notes.append(f"You said {c.label} can wait. I haven't built it.")
        if isinstance(folded, list) and c.verdict in {FOLD, SUGGEST}:
            folded.append({"concept": c.label, "as": c.fold.get("as", ""), "on": c.fold.get("on", []), "verdict": c.verdict,
                           "rule": c.rule, "proposal": _model_dict(m)})
    design.model_budget = max(1, len(design.new_models))
    return notes


def _model_dict(m: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(m)


def dangling_refs(design: Any) -> list[str]:
    names = {m.name for m in design.new_models}
    out = []
    for m in design.new_models:
        for f in m.fields:
            if f.relation and f.relation.startswith("x_") and f.relation not in names:
                out.append(f"{m.name}.{f.name}->{f.relation}")
    return out


# ------------------------------------------------------------------ step 4: python gate + orphan audit

SCHEDULED_KINDS = frozenset({"scheduled_action", "cron"})


def authorize_python(design: Any) -> list[dict[str, Any]]:
    """Precision audit for custom code: a python_needed item stays only when it is a scheduled action or a
    linked contract requirement decided option_a. Everything else is realized without code (pivot/graph
    measure, list sum, group-by, related field) and returned as a left_out entry. Pure; never adds."""
    contract = {str(r.get("id")): r for r in getattr(design, "intent_contract", []) or [] if isinstance(r, dict)}
    out = []
    for p in getattr(design, "python_needed", []) or []:
        req = contract.get(str(p.get("requirement_id") or ""))
        if str(p.get("kind") or "").lower() in SCHEDULED_KINDS or (req and req.get("decision") == "option_a"):
            continue
        out.append({"id": f"python:{p.get('key') or p.get('label')}", "item": p.get("label") or "",
                    "quote": "", "status": "declined", "put_back": "python",
                    "message": f"I didn't write custom code for \"{p.get('label')}\". You didn't ask for it, so "
                               "it is shown with standard Odoo views (totals, counts, group-by) instead."})
    return out


def apply_python_gate(design: Any, declined: list[dict[str, Any]]) -> None:
    gone = {d["id"].removeprefix("python:") for d in declined}
    design.python_needed = [p for p in design.python_needed if (p.get("key") or p.get("label")) not in gone]
    design.left_out.extend(declined)


_REALIZABLE = frozenset({"metadata", "stock_automation", "option_a"})


def orphan_requirements(design: Any) -> list[dict[str, Any]]:
    """Recall audit: in-scope contract requirements no design element cites (by requirement_id(s))."""
    cited: set[str] = set()

    def add(obj: Any) -> None:
        get = obj.get if isinstance(obj, dict) else (lambda k, d=None: getattr(obj, k, d))
        if get("requirement_id"):
            cited.add(str(get("requirement_id")))
        cited.update(str(x) for x in get("requirement_ids") or [])

    for m in design.new_models:
        add(m)
        for f in m.fields:
            add(f)
    for e in getattr(design, "stock_extensions", []) or []:
        for f in e.fields:
            add(f)
    for x in list(getattr(design, "automations", []) or []) + list(getattr(design, "python_needed", []) or []):
        add(x)
    return [r for r in getattr(design, "intent_contract", []) or []
            if isinstance(r, dict) and r.get("decision") in _REALIZABLE and str(r.get("id")) not in cited
            and r.get("kind") not in {"app_name", "host", "integration"}]
