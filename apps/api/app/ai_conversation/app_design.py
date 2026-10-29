"""App Studio full-app design: the LLM designs, guardrails validate and repair.

Full_app / long briefs only (short single-purpose briefs never reach here):

1. ``design_with_llm`` sends the FULL brief plus the grounding packet (edition,
   hosting, installed / missing apps, Online limits, live schema slice for
   implied stock models) and asks for one structured AppDesign JSON.
2. ``validate_and_repair`` normalizes names, checks relation targets, folds
   parallel copies of stock models into stock extensions, defers integrations
   for missing apps, fills empty selections, fixes one2many inverses, labels
   Python pieces with the custom-code path, applies the model budget and dedupes.
   Structural errors allow one LLM repair round; deterministic repair always runs.
3. ``outline_from_brief`` is the deterministic fallback: a multi-model outline
   from markdown sections. A big brief never collapses to one stub model.

Side effects: one or two LLM calls through the existing provider layer
(process-cached), logging. No Odoo writes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_NEW_MODELS = 12


def _in_scope(fn: Any) -> Any:
    """Run fn in a worker thread with the caller's AI scope (db, consent, surface, cache deps).
    Threads do not inherit contextvars, so without this the cloud-consent guard and per-DB
    cache keys would be lost on the parallel calls."""
    import contextvars

    ctx = contextvars.copy_context()
    return lambda *a, **kw: ctx.run(fn, *a, **kw)
MIN_DESIGN_MODELS = 2

FIELD_TYPES = frozenset(
    {
        "char",
        "text",
        "html",
        "integer",
        "float",
        "monetary",
        "boolean",
        "date",
        "datetime",
        "selection",
        "many2one",
        "one2many",
        "many2many",
        "binary",
    }
)
RELATIONAL = frozenset({"many2one", "one2many", "many2many"})
VIEW_TYPES = ("list", "form", "kanban", "graph", "pivot", "calendar", "search")
_TYPE_ALIASES = {
    "string": "char",
    "str": "char",
    "varchar": "char",
    "int": "integer",
    "number": "float",
    "decimal": "float",
    "double": "float",
    "money": "monetary",
    "currency": "monetary",
    "bool": "boolean",
    "m2o": "many2one",
    "o2m": "one2many",
    "m2m": "many2many",
    "timestamp": "datetime",
    "longtext": "text",
    "textarea": "text",
    "enum": "selection",
    "file": "binary",
    "image": "binary",
    "tree": "list",
}

# Stock model -> (module, app label). Base models are always present.
STOCK_APP_OF: dict[str, tuple[str, str]] = {
    "crm.lead": ("crm", "CRM"),
    "sale.order": ("sale", "Sales"),
    "sale.order.line": ("sale", "Sales"),
    "account.move": ("account", "Invoicing"),
    "account.payment": ("account", "Invoicing"),
    "helpdesk.ticket": ("helpdesk", "Helpdesk"),
    "helpdesk.team": ("helpdesk", "Helpdesk"),
    "project.project": ("project", "Project"),
    "project.task": ("project", "Project"),
    "calendar.event": ("calendar", "Calendar"),
    "hr.employee": ("hr", "Employees"),
}
BASE_MODELS = frozenset(
    {
        "res.partner",
        "res.users",
        "res.company",
        "res.currency",
        "res.country",
        "product.product",
        "product.template",
        "mail.activity",
        "crm.team",
        "uom.uom",
        "ir.attachment",
        "res.groups",
    }
)
_APP_ALIASES = {
    "account": {"account", "invoicing", "accounting"},
    "sale": {"sale", "sales", "sale_management"},
    "crm": {"crm"},
    "helpdesk": {"helpdesk"},
    "project": {"project"},
    "calendar": {"calendar"},
    "hr": {"hr", "employees"},
}
# Parallel copies of stock data (stem after x_) -> stock model to extend instead.
_DUPLICATE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"^(customer|client|contact|partner|company|account)s?(_(profile|record|master|info|details|data))?$"
        ),
        "res.partner",
    ),
    (re.compile(r"^(invoice|bill)s?$"), "account.move"),
    (re.compile(r"^(support_)?tickets?$"), "helpdesk.ticket"),
    (re.compile(r"^(lead|opportunit(y|ies)|crm_opportunity)s?$"), "crm.lead"),
    (re.compile(r"^(sale|sales|sale_order|sales_order|quotation)s?$"), "sale.order"),
    (re.compile(r"^projects?$"), "project.project"),
)
_IMPLIED_STOCK = (
    "res.partner",
    "crm.lead",
    "sale.order",
    "account.move",
    "helpdesk.ticket",
    "project.project",
)
_INTEGRATION_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("crm.lead", re.compile(r"(?i)\bcrm\b|\bopportunit")),
    ("sale.order", re.compile(r"(?i)\bsales?\s+orders?\b|\bquotations?\b|\bsales\b")),
    ("account.move", re.compile(r"(?i)\binvoic\w*|\bpayments?\b")),
    ("helpdesk.ticket", re.compile(r"(?i)\bhelpdesk\b|\btickets?\b")),
    ("project.project", re.compile(r"(?i)\bprojects?\b")),
    ("calendar.event", re.compile(r"(?i)\bcalendar\b")),
)


# ---------------------------------------------------------------- schema


@dataclass
class DesignField:
    name: str = ""
    ttype: str = "char"
    string: str = ""
    required: bool = False
    selection: list[list[str]] = field(default_factory=list)
    relation: str | None = None
    inverse_name: str | None = None
    help: str = ""
    requirement_id: str = ""
    requirement_ids: list[str] = field(default_factory=list)


@dataclass
class DesignModel:
    name: str = ""
    label: str = ""
    description: str = ""
    why: str = ""
    fields: list[DesignField] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    is_config: bool = False
    suggested: bool = False  # AI-proposed supporting model (not named in the brief)
    requirement_id: str = ""
    requirement_ids: list[str] = field(default_factory=list)
    # Fix plan (a): {"quote", "owner_fields", "role"} the designer copies from the owner's words.
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class StockExtension:
    model: str = ""
    fields: list[DesignField] = field(default_factory=list)
    reason: str = ""


@dataclass
class Integration:
    app: str = ""
    module: str = ""
    models: list[str] = field(default_factory=list)
    required: bool = False
    installed: bool | None = None
    status: str = "unchecked"  # available | deferred | unchecked
    note: str = ""


@dataclass
class SecurityGroup:
    name: str = ""
    implied: list[str] = field(default_factory=list)
    access: dict[str, str] = field(default_factory=dict)  # model -> subset of "rwcd"


@dataclass
class AppDesign:
    app_name: str = ""
    purpose: str = ""
    new_models: list[DesignModel] = field(default_factory=list)
    stock_extensions: list[StockExtension] = field(default_factory=list)
    integrations: list[Integration] = field(default_factory=list)
    security_groups: list[SecurityGroup] = field(default_factory=list)
    menus: list[str] = field(default_factory=list)
    python_needed: list[dict[str, Any]] = field(default_factory=list)
    # Material interpretations with source spans in the operator brief.
    intent_contract: list[dict[str, Any]] = field(default_factory=list)
    # An independent review can flag, but never silently mutate, this design.
    critic_findings: list[dict[str, Any]] = field(default_factory=list)
    # Standard automations / scheduled actions created as data, not Python.
    automations: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, str]] = field(default_factory=list)
    # Visibility rules: {"model", "group", "scope": own|all|cancel, "field", "label"}.
    record_rules: list[dict[str, Any]] = field(default_factory=list)
    model_budget: int = MAX_NEW_MODELS
    source: str = "llm"  # llm | llm_repaired | outline
    notes: list[str] = field(default_factory=list)
    repair_issues: list[str] = field(default_factory=list)
    llm_outcome: dict[str, Any] | None = None
    # Plain reason shown when the AI design did not come through.
    fallback_reason: str = ""
    # Built-in apps the brief points to, each with an Install link on the summary.
    stock_suggestions: list[dict[str, Any]] = field(default_factory=list)
    # Choices App Studio made for you: {"text", "requirement_id", "alternatives"}; editable on the summary.
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    # Things the brief asks for that this app leaves out, in plain words.
    out_of_scope: list[str] = field(default_factory=list)
    # Brief checklist: parts left out because the brief said so ({"id","item","quote","message",
    # "put_back"}) and ticked choices the operator can untick ({"id","item","quote","why","ticked"}).
    left_out: list[dict[str, Any]] = field(default_factory=list)
    # Fix plan (a): nouns the designer chose NOT to make models [{concept, quote, as, on}].
    folded: list[dict[str, Any]] = field(default_factory=list)
    checklist_choices: list[dict[str, Any]] = field(default_factory=list)
    # Stock-first result per build item ({"item","choice","label","install",...}) and outside-service routes.
    stock_checks: list[dict[str, Any]] = field(default_factory=list)
    integration_routes: list[dict[str, Any]] = field(default_factory=list)
    # Agent mode: plain-language playback {wants, reuses, new, assumptions, left_out, questions}.
    playback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def model_names(self) -> list[str]:
        return [m.name for m in self.new_models]

    @classmethod
    def from_dict(cls, raw: Any) -> AppDesign:
        raw = raw if isinstance(raw, dict) else {}
        if isinstance(raw.get("design"), dict):
            raw = raw["design"]
        out = cls(
            app_name=_s(raw.get("app_name") or raw.get("name"))[:80],
            purpose=_s(raw.get("purpose"))[:400],
            new_models=[_coerce_model(m) for m in _lst(raw.get("new_models") or raw.get("models"))],
            stock_extensions=[_coerce_ext(e) for e in _lst(raw.get("stock_extensions"))],
            integrations=[_coerce_integration(i) for i in _lst(raw.get("integrations"))],
            security_groups=[_coerce_group(g) for g in _lst(raw.get("security_groups"))],
            menus=[_s(m) for m in _lst(raw.get("menus")) if _s(m)],
            python_needed=[
                p for p in (_coerce_python(p) for p in _lst(raw.get("python_needed"))) if p
            ],
            intent_contract=_lst(raw.get("intent_contract") or raw.get("requirements")),
            automations=[a for a in (_coerce_automation(x) for x in _lst(raw.get("automations"))) if a],
            record_rules=[r for r in _lst(raw.get("record_rules")) if isinstance(r, dict) and r.get("model")],
            source=_s(raw.get("source")) or "llm",
            notes=[_s(n) for n in _lst(raw.get("notes")) if _s(n)],
            stock_suggestions=[a for a in _lst(raw.get("stock_suggestions")) if isinstance(a, dict) and a.get("module")],
            assumptions=[a for a in _lst(raw.get("assumptions")) if isinstance(a, dict) and a.get("text")],
            out_of_scope=[_s(x) for x in _lst(raw.get("out_of_scope")) if _s(x)],
            left_out=[x for x in _lst(raw.get("left_out")) if isinstance(x, dict) and x.get("item")],
            folded=[x for x in _lst(raw.get("folded")) if isinstance(x, dict) and x.get("concept")],
            checklist_choices=[x for x in _lst(raw.get("checklist_choices")) if isinstance(x, dict) and x.get("item")],
            stock_checks=[x for x in _lst(raw.get("stock_checks")) if isinstance(x, dict) and x.get("label")],
            integration_routes=[x for x in _lst(raw.get("integration_routes")) if isinstance(x, dict) and x.get("route")],
            playback=raw.get("playback") if isinstance(raw.get("playback"), dict) else {},
        )
        try:
            out.model_budget = int(raw.get("model_budget") or MAX_NEW_MODELS)
        except (TypeError, ValueError):
            out.model_budget = MAX_NEW_MODELS
        return out


def _s(v: Any) -> str:
    if isinstance(v, (dict, list)):
        return ""
    return str(v or "").strip()


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _snake(value: Any) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", _s(value))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return re.sub(r"_+", "_", s)


def _title(name: str) -> str:
    stem = re.sub(r"^x_", "", name or "").replace(".", "_")
    return " ".join(w.capitalize() for w in stem.split("_") if w)


def _plural(label: str) -> str:
    if re.search(r"(?i)[^aeiou]y$", label):
        return label[:-1] + "ies"
    return label if label.lower().endswith("s") else label + "s"


_SYMBOL_KEYS = {">": "gt", "<": "lt", "=": "eq", ">=": "gte", "<=": "lte", "!=": "ne"}


def _coerce_selection(raw: Any) -> list[list[str]]:
    out: list[list[str]] = []
    for opt in _lst(raw):
        if isinstance(opt, dict):
            label = _s(opt.get("label") or opt.get("name") or opt.get("value"))
            key = _snake(opt.get("value") or label)
        elif isinstance(opt, (list, tuple)) and opt:
            key, label = _snake(opt[0]), _s(opt[-1])
        else:
            label = _s(opt)
            key = _snake(label)
        key = key or _SYMBOL_KEYS.get(label) or (f"option_{len(out) + 1}" if label else "")
        if key and label and key not in {k for k, _ in out}:
            out.append([key, label])
    return out


def _coerce_field(raw: Any) -> DesignField:
    if isinstance(raw, str):
        raw = {"string": raw}
    raw = raw if isinstance(raw, dict) else {}
    ttype = _snake(raw.get("ttype") or raw.get("type") or "char")
    return DesignField(
        name=_s(raw.get("name") or raw.get("technical_name")),
        ttype=_TYPE_ALIASES.get(ttype, ttype),
        string=_s(raw.get("string") or raw.get("label"))[:60],
        required=bool(raw.get("required")),
        selection=_coerce_selection(raw.get("selection") or raw.get("options")),
        relation=_s(raw.get("relation") or raw.get("comodel") or raw.get("target")) or None,
        inverse_name=_s(raw.get("inverse_name") or raw.get("inverse")) or None,
        help=_s(raw.get("help"))[:200],
        requirement_id=_s(raw.get("requirement_id"))[:48],
        requirement_ids=[_s(x)[:48] for x in _lst(raw.get("requirement_ids")) if _s(x)],
    )


def _coerce_model(raw: Any) -> DesignModel:
    raw = raw if isinstance(raw, dict) else {}
    return DesignModel(
        name=_s(raw.get("name") or raw.get("technical_name") or raw.get("model")),
        label=_s(raw.get("label") or raw.get("string"))[:60],
        description=_s(raw.get("description"))[:300],
        why=_s(raw.get("why") or raw.get("explanation") or raw.get("reason"))[:300],
        fields=[_coerce_field(f) for f in _lst(raw.get("fields"))],
        views=[_TYPE_ALIASES.get(_snake(v), _snake(v)) for v in _lst(raw.get("views"))],
        is_config=bool(raw.get("is_config")),
        suggested=raw.get("suggested") is True or str(raw.get("suggested")).lower() == "true",
        requirement_id=_s(raw.get("requirement_id"))[:48],
        requirement_ids=[_s(x)[:48] for x in _lst(raw.get("requirement_ids")) if _s(x)],
        evidence=_coerce_evidence(raw.get("evidence")),
    )


def _coerce_evidence(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not (_s(raw.get("quote")) or _lst(raw.get("owner_fields"))):
        return {}  # empty evidence = none (old designs round-trip as {})
    return {"quote": _s(raw.get("quote"))[:300],
            "owner_fields": [_s(x)[:160] for x in _lst(raw.get("owner_fields")) if _s(x)][:20],
            "role": _s(raw.get("role"))[:60]}


def _coerce_ext(raw: Any) -> StockExtension:
    raw = raw if isinstance(raw, dict) else {}
    return StockExtension(
        model=_s(raw.get("model")).lower(),
        fields=[_coerce_field(f) for f in _lst(raw.get("fields"))],
        reason=_s(raw.get("reason"))[:300],
    )


def _coerce_integration(raw: Any) -> Integration:
    raw = raw if isinstance(raw, dict) else {}
    req = raw.get("required")
    return Integration(
        app=_s(raw.get("app") or raw.get("app_label") or raw.get("module")),
        module=_snake(raw.get("module") or raw.get("app")),
        models=[_s(m).lower() for m in _lst(raw.get("models")) if _s(m)]
        or ([_s(raw.get("model")).lower()] if _s(raw.get("model")) else []),
        required=req is True or _s(req).lower() == "required",
        note=_s(raw.get("note") or raw.get("reason"))[:300],
    )


def _coerce_automation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "requirement_id": _s(raw.get("requirement_id"))[:48],
        "label": _s(raw.get("label"))[:100],
        "trigger": _s(raw.get("trigger"))[:16],
        "target_model": _s(raw.get("target_model"))[:60],
        "mechanism": _s(raw.get("mechanism"))[:120],
        "automation": raw.get("automation") if isinstance(raw.get("automation"), dict) else {},
        "evidence": raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {},
    }


def _coerce_group(raw: Any) -> SecurityGroup:
    if isinstance(raw, str):
        raw = {"name": raw}
    raw = raw if isinstance(raw, dict) else {}
    access: dict[str, str] = {}
    acc = raw.get("access") or raw.get("model_access")
    if isinstance(acc, dict):
        access = {_s(k): _perm(v) for k, v in acc.items() if _s(k)}
    elif isinstance(acc, list):
        for row in acc:
            if isinstance(row, dict) and _s(row.get("model")):
                access[_s(row.get("model"))] = _perm(
                    row.get("perms") or row.get("permissions") or row
                )
    return SecurityGroup(
        name=_s(raw.get("name"))[:60],
        implied=[_s(x) for x in _lst(raw.get("implied") or raw.get("implied_groups")) if _s(x)],
        access=access,
    )


def _perm(v: Any) -> str:
    if isinstance(v, dict):
        keys = {"read": "r", "write": "w", "create": "c", "unlink": "d", "delete": "d"}
        return "".join(dict.fromkeys(c for k, c in keys.items() if v.get(k) or v.get(f"perm_{k}")))
    text = _s(v).lower()
    if text in {"full", "all", "crud"}:
        return "rwcd"
    if text in {"read", "readonly", "read_only"}:
        return "r"
    return (
        "".join(c for c in "rwcd" if c in text.replace("unlink", "d").replace("delete", "d")) or "r"
    )


def _coerce_python(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        raw = {"label": raw}
    if not isinstance(raw, dict):
        return None
    label = _s(raw.get("label") or raw.get("name") or raw.get("piece"))
    if not label:
        return None
    return {
        "key": _snake(raw.get("key") or label)[:40],
        "label": label[:80],
        "kind": _s(raw.get("kind"))[:40],
        "models": [_s(m) for m in _lst(raw.get("models")) if _s(m)],
        "reason": _s(raw.get("reason"))[:200],
        "requirement_id": _s(raw.get("requirement_id") or raw.get("contract_id"))[:48],
        "evidence": _s(raw.get("evidence") or raw.get("quote"))[:300],
    }


# ---------------------------------------------------------------- budget / grounding


_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+\S")


def model_budget_for(prompt: str) -> int:
    """New-model cap scales with the brief: 4 for a paragraph, up to 12."""
    words = len(re.findall(r"\w+", prompt or ""))
    heads = len(_HEADING_RE.findall(prompt or ""))
    return max(3, min(MAX_NEW_MODELS, max(4, heads, words // 150)))


def _app_status(model: str, grounding: Any, packet: Any) -> str:
    """installed | missing | unknown for the stock app behind ``model``."""
    if model in BASE_MODELS:
        return "installed"
    module, label = STOCK_APP_OF.get(model, ("", ""))
    names = set(_APP_ALIASES.get(module, {module})) | {label.lower()}
    names.discard("")
    if grounding is not None:
        if names & {x.lower() for x in getattr(grounding, "apps_missing", ())}:
            return "missing"
        if names & {x.lower() for x in getattr(grounding, "apps_installed", ())}:
            return "installed"
    models = getattr(packet, "models", None) or {}
    if model in models:
        return "installed"
    return "unknown"


def stock_schema_slice(
    packet: Any, models: tuple[str, ...] = _IMPLIED_STOCK, cap: int = 40
) -> dict[str, list[str]]:
    rows = getattr(packet, "models", None) or {}
    out: dict[str, list[str]] = {}
    for name in models:
        row = rows.get(name)
        if row is not None:
            out[name] = sorted(getattr(row, "fields", {}) or {})[:cap]
    return out


# ---------------------------------------------------------------- LLM design


def intent_contract_system_prompt() -> str:
    return (
        "You turn an App Studio brief into a structured requirement contract before any app "
        "design. Reply with one JSON object only. The brief may be informal or incomplete: "
        "capture what it states AND fill obvious gaps a non-technical operator would expect. "
        "Set origin 'stated' with evidence copied exactly from the brief, or origin 'inferred' "
        "for a gap you are filling (evidence is the nearest related phrase, or empty). Inferred "
        "requirements are suggestions: keep them metadata, or use decision clarify with a "
        "friendly question when something beyond metadata seems needed. Never decide that for "
        "the operator. For each requirement work up a ladder and stop at the lowest rung that "
        "works: (1) metadata: fields, views, menus, filters, reports, standard activities; "
        "(2) stock_automation: an Odoo automated action configured as data with no custom "
        "module; (3) option_a: custom Python, only when rungs 1 and 2 cannot deliver it. Set "
        "trigger: user_entry or none when people enter or read the value (a field NAMED "
        "'scheduled date', 'due date', 'score' or 'history' is user_entry); event, time, "
        "computation or external only when the brief says Odoo itself must act or derive "
        "something. For stock_automation or option_a, fill rungs with one row per lower rung "
        "(mechanism considered, sufficient=false, why it falls short) and set target_model. "
        "For stock_automation also fill automation: when (on_create, on_write, or on_time "
        "with a date_field and offset_days, negative = before the date) and action (activity: "
        "schedule a to-do for the record's responsible person, with a short summary). If the "
        "behavior cannot be expressed that way, leave automation empty. If either reading is "
        "plausible, use decision clarify with a question. Questions are for a non-technical "
        "business owner: one short plain sentence about their business (who, when, what "
        "happens), never about fields, models, automations or code, and never about hosting, "
        "installed apps, modules, permissions to cancel/see, or multi-company (the app decides "
        "those). With every clarify question give 2-4 short options that each answer it "
        "(e.g. 'Who approves?' -> 'Any manager', 'The person's own manager', 'A specific "
        "person'), each with the delivery decision it implies. Mark exactly one option "
        "\"recommended\": true: the answer the brief's own words point to, else the safest "
        "common default. App Studio uses it as an editable assumption instead of asking. "
        "Every kind=model row MUST carry a role: record = a thing with its own list of entries "
        "people create and look up; attribute = a single value stored on another record; "
        "dimension = a fixed choice/category used to group or filter; context = background, "
        "not built; future = wanted later, not now; rule = a behaviour; access = who may see or "
        "do what. A thing the owner refers to as distinct, reused instances across many logged "
        "rows (each delivery's van, each attendance's student) is a record, not an attribute or "
        "dimension; prefer an installed stock host for it (e.g. fleet.vehicle, hr.employee, "
        "res.partner) via grounding when it fits. Evidence is copied only from the owner's "
        "brief, never from helper notes."
    )


_CONTRACT_SHAPE = (
    '{"requirements": [{"kind": "app_name|host|integration|model|field|python|automation|other", '
    '"subject": str, "origin": "stated|inferred", "decision": '
    '"metadata|stock_automation|option_a|clarify", "evidence": "exact quote or empty", '
    '"trigger": "none|user_entry|event|time|computation|external", '
    '"target_model": "model the automation acts on", "mechanism": str, '
    '"automation": {"when": "on_create|on_write|on_time|untouched", "date_field": str, '
    '"values": {field: plain value} (set_fields only), "condition": [[field, op, value]], '
    '"group": str (notify a role), '
    '"offset_days": int, "action": "activity|set_fields|notify", "summary": str}, '
    '"rungs": [{"rung": "metadata|stock_automation", "mechanism": str, '
    '"sufficient": bool, "why": str}], "question": str, "options": [{"label": str, "decision": "metadata|stock_automation|option_a", "recommended": bool}], '
    '"confidence": "low|medium|high", '
    '"role": "record|attribute|dimension|context|future|rule|access"}]}'
)


def intent_contract_user_prompt(
    prompt: str, grounding: Any = None, packet: Any = None, snapshot: Any = None
) -> str:
    from app.ai_conversation.grounding import grounding_prompt_block

    context = grounding_prompt_block(grounding)
    if snapshot is not None and getattr(snapshot, "ok", False):
        schema_text = (
            "Live database snapshot. A requirement may already be met by something here: "
            "check it before proposing anything new.\n" + snapshot.digest(6000)
        )
    else:
        schema = stock_schema_slice(packet)
        schema_text = (
            "Live stock fields in this database (a requirement may already be met by one of "
            "these; check before proposing anything new):\n"
            + "\n".join(f"- {m}: {', '.join(f)}" for m, f in schema.items())
            if schema
            else ""
        )
    return "\n\n".join(
        part
        for part in (
            context,
            schema_text,
            f"JSON shape: {_CONTRACT_SHAPE}\n\nOperator brief (full):\n{prompt}",
        )
        if part
    )


def _call_verifier(
    provider: Any, prompt: str, requirements: list[dict[str, Any]],
    entail: list[dict[str, Any]] | None = None, entail_out: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Downgrade-only entailment check for code-lane rows. Returns id -> verdict.

    The verifier sees only the cited text, never the proposer's reasoning, so it
    cannot be anchored by it. No verdict means the row degrades to a question.
    """
    from app.llm_provider import LLMError

    rows = [
        r
        for r in requirements
        if r["decision"] in {"stock_automation", "option_a"}
        and not r.get("operator_confirmed")
        and r.get("evidence", {}).get("quote")
    ]
    if not rows and not entail:
        if entail_out is not None:
            entail_out["_status"] = "skipped"
        return {}
    items = []
    for r in rows:
        ev = r["evidence"]
        context = prompt[max(0, ev["start"] - 200) : ev["end"] + 200]
        items.append(
            {"id": r["id"], "quote": ev["quote"], "context": context, "subject": r["subject"]}
        )
    system = (
        "You verify one narrow claim per item. Decide whether the quote and context EXPLICITLY "
        "require Odoo to act or derive something by itself (on a schedule, on an event, by "
        "calculation, or toward an external system), as opposed to describing a value people "
        "enter or view. Reply JSON only: "
        '{"verdicts":[{"id":str,"verdict":"supports|not_supported|unclear"}]}. '
        "Use unclear when either reading is plausible. A field merely NAMED like an action "
        "(for example 'scheduled date') is not_supported."
    )
    payload: Any = items
    if entail:
        # Batched independent entailment check (clause mode): same round trip, separate list,
        # sees only snippet + item description, randomized order.
        from app.ai_conversation.clause_grounding import ENTAIL_INSTRUCTION

        system = system + " " + ENTAIL_INSTRUCTION
        payload = {"items": items, "entail": entail}
    try:
        raw = provider.generate_json(
            json.dumps(payload, ensure_ascii=False),
            system=system,
            timeout_s=design_timeout_for(prompt),
            temperature=0.0,
        )
    except (LLMError, TimeoutError):
        if entail_out is not None:
            entail_out["_status"] = "failed"
        return {}
    parsed = _parse_json(raw) or {}
    if entail_out is not None:
        got = {
            _s(v.get("id")): _s(v.get("verdict")).lower()
            for v in _lst(parsed.get("entailment"))
            if isinstance(v, dict)
        }
        entail_out["_status"] = "called" if (got or not entail) and parsed else "failed"
        entail_out["verdicts"] = got
    return {
        _s(v.get("id")): _s(v.get("verdict")).lower()
        for v in _lst(parsed.get("verdicts"))
        if isinstance(v, dict)
    }


def _call_conflict_look(provider: Any, prompt: str, contract: list[dict[str, Any]]) -> Any:
    """Independent AI read of quoted rows for contradictions. Code authorizes the result."""
    from app.ai_conversation import conflict_look as cl

    rows = cl.rows_for_look(contract, prompt)
    if len(rows) < 2:
        return {"conflicts": []}
    budget_s = min(60.0, design_timeout_for(prompt))
    for _attempt in (1, 2):  # one retry: a lost call must not lose the owner's contradiction
        try:  # tighter first attempt: total stays near one budget
            raw = provider.generate_json(
                "Owner's brief (data):\n" + prompt + "\n\nQuoted rows (data):\n" + json.dumps(rows, ensure_ascii=False),
                system=cl.SYSTEM, timeout_s=budget_s * (0.6 if _attempt == 1 else 0.5), temperature=0.0)
        except Exception:  # noqa: BLE001
            continue
        parsed = _parse_json(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("conflicts"), list):
            return parsed
    return None


def _call_second_look(provider: Any, prompt: str, items: list[dict[str, Any]]) -> dict[str, str] | None:
    """Small independent read of the 'no / later' quotes only. None on failure (=> choices)."""
    from app.ai_conversation import brief_checklist as bc

    rows = bc.second_look_items(items, seed=len(prompt))
    if not rows:
        return {}
    try:
        raw = provider.generate_json(json.dumps(rows, ensure_ascii=False), system=bc.SECOND_LOOK_SYSTEM,
                                     timeout_s=min(60.0, design_timeout_for(prompt)), temperature=0.0)
    except Exception:  # noqa: BLE001 - a failed second look leaves everything as a ticked choice
        return None
    return bc.parse_second_look(_parse_json(raw))


def _deterministic_ok(design: Any, snap: Any) -> bool:
    """True when admission passes after deterministic repair: an LLM repair round adds nothing."""
    if snap is None or not getattr(snap, "ok", False):
        return False
    try:
        from app.design_admission import SnapshotSchemaClient, validate_design
        res = validate_design(design.to_dict(), SnapshotSchemaClient(snap), major=snap.major,
                              edition=getattr(snap, "edition", "unknown"), installed=set(snap.modules))
        return bool(res.ok)
    except Exception:  # noqa: BLE001
        return False


def _bc_flag() -> bool:
    from app.ai_conversation import brief_checklist as bc

    return bc.enabled()


def checklist_only(prompt: str, answers: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Routes that diagnose without an app design still get the brief checklist (flagged).
    One checklist call + the second look. Returns the same shape as meta["checklist"]."""
    from app.ai_conversation import brief_checklist as bc
    from app.llm_provider import get_llm_provider_for_tier

    if not bc.enabled() or not prompt.strip():
        return None
    prompt = bc.source_brief(prompt)  # owner's words are the evidence authority
    provider = get_llm_provider_for_tier("contract") or get_llm_provider_for_tier("fast")
    if provider is None:
        return None
    raw = None
    budget_s = min(90.0, design_timeout_for(prompt))
    for attempt in (1, 2):  # one retry: a lost checklist call must not erase routes/declines
        try:  # first attempt is tighter so a retry does not double the wait
            raw = provider.generate_json(
                "Operator brief (data):\n" + prompt + _stock_catalog_now(), system=bc.CHECKLIST_ONLY_SYSTEM + bc.CONTRACT_ADDENDUM,
                timeout_s=budget_s * (0.6 if attempt == 1 else 0.5), temperature=0.0)
            break
        except Exception:  # noqa: BLE001 - retried once; then no checklist
            continue
    if raw is None:
        return None
    items = bc.parse_checklist(_parse_json(raw), prompt)
    second = _call_second_look(get_llm_provider_for_tier("refine") or provider, prompt, items)
    put_back = {k.split(":", 1)[1] for k, v in (answers or {}).items()
                if k.startswith("checklist_put_back:") and str(v).lower() in {"1", "true", "yes"}}
    decided = bc.decide(items, second, put_back)
    from app.ai_conversation import stock_routing as sr
    snap = _current_snapshot()
    build = [i for i in decided if i.get("final") in {"build", "choice", "unclear"} or i["status"] in {"build", "unclear"}]
    stock_checks = [dict(sr.stock_check(i, snap), id=i["id"]) for i in build if i.get("stock_options") or i.get("plan")]
    routes = _routes_for(decided, snap)
    reg = sr.register([i for i in decided if i.get("final") in {"build", "choice"}],
                      lambda q: bool(q) and bc.locate(prompt, q) is not None)
    from app.ai_conversation import capability as cap
    capability = cap.authorize([i for i in decided if i.get("final") in {"build", "choice", "declined"} or i["status"] == "cannot"], snap)
    # capability declines become left_out rows when code refuses analysis/prediction
    for c in capability:
        if c.get("decision") == "decline":
            decided = [dict(i, final="declined", reason=c.get("reason", "")) if i["id"] == c.get("id") else i for i in decided]
        elif c.get("decision") == "ask":
            decided = [dict(i, final="choice", cap_ask=True, reason=c.get("reason", ""), cap_options=c.get("options") or [])
                       if i["id"] == c.get("id") else i for i in decided]
    return {"items": len(decided), "second_look": "failed" if second is None else "called",
            "left_out": bc.left_out_rows(decided), "choices": bc.choice_rows(decided),
            "routes": routes, "stock_checks": stock_checks, "register": reg,
            "statuses": {s_: sum(1 for i in decided if i.get("status") == s_) for s_ in bc.STATUSES},
            "capability": capability}


def _stock_catalog_now() -> str:
    from app.ai_conversation.stock_routing import stock_catalog

    try:
        return stock_catalog(_current_snapshot())
    except Exception:  # noqa: BLE001
        return ""


def _current_snapshot() -> Any:
    from app.odoo_snapshot import current_snapshot

    return current_snapshot()


def _routes_for(items: list[dict[str, Any]], snap: Any = None) -> list[dict[str, Any]]:
    from app.ai_conversation import stock_routing as sr
    from app.ai_conversation.grounding import current_grounding

    out = []
    for i in items:
        if i.get("status") in {"build", "unclear"}:
            try:
                r = sr.route_service(i, snap, current_grounding())
            except Exception:  # noqa: BLE001 - a routing slip never blocks the diagnosis
                r = None
            if r:
                out.append(r)
    return out


def _call_intent_contract(
    provider: Any,
    prompt: str,
    grounding: Any,
    *,
    answers: dict[str, str] | None = None,
    verifier: Any = None,
    schema_packet: Any = None,
    snapshot: Any = None,
    parallel: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract a frozen, verified contract before a design model sees the brief.

    ``parallel(contract)`` (the design call) runs at the same time as the verifier, on the
    pre-verification contract: the verifier can only downgrade, and validate_and_repair rebuilds
    automations from the final contract, so nothing it removes survives."""
    from app.ai_conversation.intent_contract import (
        settle_open_questions,
        apply_capability_policy,
        detect_contract_conflicts,
        apply_verifier_verdicts,
        normalize_intent_contract,
        resolve_contract_answers,
    )
    from app.llm_provider import LLMError

    from app.ai_conversation.brief_checklist import source_brief as _src0

    stored = _stored_intent_contract(answers, _src0(prompt))
    if stored is not None:
        meta_cached: dict[str, Any] = {
            "status": "cached",
            "reason": "frozen_session_contract",
            "requirement_count": len(stored),
        }
        chk_stored = stored_checklist(answers)
        if chk_stored:
            # Same authorization graph on every rebuild (e.g. after an app install):
            # code re-applies the stored stock plan, declines and scope; nothing new is asked.
            meta_cached["checklist"] = chk_stored
        return resolve_contract_answers(stored, answers), meta_cached
    from app.ai_conversation import brief_checklist as _bc0

    expanded = prompt
    # Evidence authority: the owner's original words, always. The expansion is context only
    # and never quotable (quotes from it never resolve in the owner's text and were false folds).
    prompt = _bc0.source_brief(prompt)
    user_text = intent_contract_user_prompt(prompt, grounding, schema_packet, snapshot)
    user_text += _bc0.expansion_context(expanded)
    if _bc0.enabled():
        from app.ai_conversation.stock_routing import stock_catalog as _sc

        user_text += _sc(snapshot)
    # S8: the expansion never reaches the contract/checklist call (quotes must be the owner's);
    # it only enriches the design call.
    meta: dict[str, Any] = {
        "model": next(
            (
                getattr(provider, attr)
                for attr in ("model", "model_name", "name")
                if isinstance(getattr(provider, attr, None), str)
            ),
            None,
        ),
        "prompt_chars": len(user_text),
        "timeout_s": design_timeout_for(prompt),
    }
    from app.ai_conversation import brief_checklist as bc
    from app.ai_conversation import clause_grounding as cg

    checklist_on = bc.enabled()
    if checklist_on:
        user_text = user_text + "\n\n" + bc.CONTRACT_ADDENDUM
    clause_on = cg.enabled() and not checklist_on
    clauses = cg.segment_brief(prompt) if clause_on else []
    failed: list[str] = []
    labels_parsed: Any = None
    entail_out: dict[str, Any] = {}
    if clause_on:
        if cg.check_tiling(prompt, clauses):
            failed.append("tiling")
        user_text = user_text + "\n\n" + cg.clauses_prompt_block(clauses) + "\n\n" + cg.CONTRACT_SHAPE_ADDENDUM
        meta["llm_calls"] = 3  # contract || classify, then verifier(+entailment) || design

    def _classify() -> Any:
        try:
            return _parse_json(provider.generate_json(
                cg.clauses_prompt_block(clauses), system=cg.classify_system_prompt(),
                timeout_s=meta["timeout_s"], temperature=0.0, format_schema=cg.CLASSIFY_SCHEMA))
        except Exception:  # noqa: BLE001 - classifier failure is handled by the failure policy
            return None

    started = time.monotonic()
    from concurrent.futures import ThreadPoolExecutor

    cpool = ThreadPoolExecutor(max_workers=1) if clause_on else None
    f_labels = cpool.submit(_in_scope(_classify)) if cpool is not None else None  # parallel with the contract call
    try:
        raw = provider.generate_json(
            user_text,
            system=intent_contract_system_prompt(),
            timeout_s=meta["timeout_s"],
            temperature=0.0,
        )
    except (LLMError, TimeoutError) as exc:
        if cpool is not None:
            cpool.shutdown(wait=False)
        message = str(exc)
        meta.update(
            status=(
                "timed_out"
                if isinstance(exc, TimeoutError)
                or re.search(r"(?i)time[sd]?\s*out|timeout|deadline", message)
                else "failed"
            ),
            error=message[:200],
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return [], meta
    if f_labels is not None:
        labels_parsed = f_labels.result()
        cpool.shutdown(wait=False)
    parsed = _parse_json(raw)
    known = (
        set(getattr(snapshot, "index", None) or ()) | set(getattr(snapshot, "caps", None) or ())
        if snapshot is not None and getattr(snapshot, "ok", False)
        else set(getattr(schema_packet, "models", None) or {})
    )
    labels = None
    rejected: list[dict[str, Any]] = []
    if clause_on and parsed:
        labels = cg.parse_labels(labels_parsed, clauses)
        if labels is None:
            failed.append("classifier")
        entries = parsed.get("requirements") if isinstance(parsed, dict) else parsed
        kept, rejected = cg.ground_items(entries if isinstance(entries, list) else [], clauses, prompt, labels)
        for k in kept:
            k["stock_check"] = cg.stock_check(k, known or None)
        contract = normalize_intent_contract({"requirements": kept}, prompt, clause_mode=True)
    else:
        contract = normalize_intent_contract(parsed, prompt) if parsed else []
    contract, meta["role_repair"] = _repair_model_roles(provider, prompt, contract, meta["timeout_s"])
    entail = cg.entailment_items(contract, seed=len(prompt)) if clause_on else None
    checklist: list[dict[str, Any]] = []
    f_second = None
    f_conflict = None
    if checklist_on and parsed:
        checklist = bc.parse_checklist(parsed, prompt)
        from concurrent.futures import ThreadPoolExecutor as _TPE

        _spool = _TPE(max_workers=2)
        f_second = _spool.submit(_in_scope(_call_second_look), verifier or provider, prompt, checklist)
        # Independent conflict look over the quoted rows (parallel with the second look).
        f_conflict = _spool.submit(_in_scope(_call_conflict_look), verifier or provider, prompt, contract)
        _spool.shutdown(wait=False)
        from app.ai_conversation import stock_routing as sr
        from app.ai_conversation.grounding import current_grounding

        for i in checklist:  # requirement ids end to end: checklist item -> contract rows citing its quote
            i["requirement_ids"] = [str(r.get("id")) for r in contract if r.get("id") and i.get("located")
                                    and (r.get("evidence") or {}).get("end", -1) > i["start"]
                                    and i["end"] > (r.get("evidence") or {}).get("start", -1)]
        build = [i for i in checklist if i["status"] in {"build", "unclear"}]
        stock_checks = [dict(sr.stock_check(i, snapshot), id=i["id"], requirement_ids=i["requirement_ids"])
                        for i in build if i.get("stock_options") or i.get("plan")]
        routes = _routes_for(build, snapshot)
        by_id = {c["id"]: c for c in stock_checks}
        for r in contract:  # the designer sees the stock decision for the part of the brief each row cites
            ev = r.get("evidence") or {}
            for i in build:
                c = by_id.get(i["id"])
                if c and c["choice"] == "stock" and i["located"] and ev.get("end", -1) > i["start"] and i["end"] > ev.get("start", -1):
                    r["stock_plan"] = {"use": c["use"].get("model") or c["use"].get("module"),
                                       "note": "AUTHORITATIVE: extend this stock model (stock_extensions). Do not invent a custom model for it. Put requirement_id on every model/field/automation you create for this row."}
    verified_rows = 0
    if contract:
        # Independent verifier when a separate tier exists; otherwise the same
        # provider, still downgrade-only and still blind to the proposer's reasoning.
        if parallel is not None:
            from concurrent.futures import ThreadPoolExecutor

            preview = resolve_contract_answers(
                detect_contract_conflicts(apply_capability_policy(contract, known or None), prompt), answers)
            with ThreadPoolExecutor(max_workers=2) as pool:
                f_verify = pool.submit(_in_scope(_call_verifier), verifier or provider, prompt, contract,
                                       entail, entail_out if clause_on else None)
                f_design = pool.submit(_in_scope(parallel), preview)
                verdicts = f_verify.result()
                try:
                    meta["_parallel"] = f_design.result()
                except Exception as exc:  # noqa: BLE001
                    meta["parallel_error"] = str(exc)[:200]
        else:
            verdicts = _call_verifier(verifier or provider, prompt, contract,
                                      entail, entail_out if clause_on else None)
        contract = apply_verifier_verdicts(contract, verdicts)
        contract = apply_capability_policy(contract, known or None)
        contract = settle_open_questions(detect_contract_conflicts(contract, prompt), prompt)
        if checklist_on and f_conflict is not None:
            from app.ai_conversation import conflict_look as _cl

            try:
                raw_conf = f_conflict.result()
            except Exception:  # noqa: BLE001
                raw_conf = None
            contract, accepted = _cl.apply(contract, raw_conf, prompt)
            meta["conflict_look"] = {"status": "called" if raw_conf is not None else "failed",
                                     "accepted": accepted}
        verified_rows = sum(1 for r in contract if r.get("verified"))
    if checklist_on and parsed is not None:
        answers_second = f_second.result() if f_second is not None else None
        put_back = {k.split(":", 1)[1] for k, v in (answers or {}).items()
                    if k.startswith("checklist_put_back:") and str(v).lower() in {"1", "true", "yes"}}
        decided = bc.decide(checklist, answers_second, put_back)
        from app.ai_conversation import capability as cap
        from app.ai_conversation.grounding import current_grounding as _cg
        capability = cap.authorize(decided, snapshot, online=bool(getattr(_cg(), "online", False) if _cg() else False))
        for cauth in capability:
            for i in decided:
                if i["id"] != cauth.get("id"):
                    continue
                if cauth.get("decision") == "decline":
                    i["final"] = "declined"; i["reason"] = cauth.get("reason") or i.get("reason") or ""
                    i["status"] = "cannot"
                elif cauth.get("decision") == "ask" and not (answers or {}).get(f"checklist_put_back:{i['id']}"):
                    i["final"] = "choice"; i["cap_ask"] = True; i["reason"] = cauth.get("reason") or ""
                    i["cap_options"] = cauth.get("options") or []
        contract, dropped = bc.filter_contract(contract, decided)
        reg = sr.register([i for i in decided if i.get("final") in {"build", "choice"}],
                          lambda q: bool(q) and bc.locate(prompt, q) is not None)
        for q in reg["questions"]:
            if (answers or {}).get(f"intent_contract:{q['id']}"):
                continue
            template = normalize_intent_contract(
                {"requirements": [{"kind": "other", "subject": f"{q['item']}: {q['type'].replace('_', ' ')}", "decision": "metadata",
                  "origin": "stated"}]}, prompt, clause_mode=True)
            if template:
                contract.append(dict(template[0], id=q["id"], decision="clarify", question=q["question"] + (f' We suggest: {q["recommended"]}.' if q.get("recommended") else ""),
                                     recommended=q.get("recommended", ""), blocking_reason="risk",
                                     options=[{"label": o, "decision": "metadata"} for o in q["options"]],
                                     downgrade_reason=""))
        meta["checklist"] = {
            "items": len(decided), "second_look": "failed" if answers_second is None else "called",
            "left_out": bc.left_out_rows(decided), "choices": bc.choice_rows(decided),
            "dropped_requirements": [r.get("subject") for r in dropped],
            "statuses": {s_: sum(1 for i in decided if i["status"] == s_) for s_ in bc.STATUSES},
            "stock_checks": stock_checks, "routes": routes, "register": reg, "capability": capability,
            "conflicts": list((meta.get("conflict_look") or {}).get("accepted") or []),
        }
    if clause_on and parsed is not None:
        if entail_out.get("_status") == "failed":
            failed.append("verifier")
        contract = cg.apply_entailment(
            contract, entail_out.get("verdicts") if entail_out.get("_status") == "called" else None)
        contract = cg.apply_provenance_gate(cg.failure_policy(contract, failed))
        excluded = cg.exclusions(labels, clauses)
        meta["grounding"] = {
            "clauses": len(clauses), "failed": failed, "coverage": cg.coverage(contract, clauses, labels, failed),
            "fanout": cg.fanout(contract), "exclusions": excluded, "rejected": rejected,
            "must_not": cg.must_not_violations([r.get("subject") or "" for r in contract], excluded),
            "provenance": {p: sum(1 for r in contract if r.get("provenance") == p) for p in cg.PROVENANCE},
        }
        if answers is not None:
            answers["_justification_json"] = json.dumps(
                [cg.justification(r) for r in contract] + [dict(x, provenance="rejected") for x in rejected],
                ensure_ascii=False)
    # Persist the pre-answer form, not a model-generated id. An operator answer is
    # applied to this same reviewed contract; a retried extractor never gets to
    # silently change the question.
    if answers is not None and parsed is not None:
        answers["_intent_contract_json"] = json.dumps(contract, ensure_ascii=False)
        answers["_intent_contract_seal"] = _contract_seal(answers["_intent_contract_json"])
    contract = resolve_contract_answers(contract, answers)
    meta.update(
        status="called" if parsed is not None else "failed",
        requirement_count=len(contract),
        verified_rows=verified_rows,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    if parsed is None:
        meta["error"] = "unparseable JSON"
    return contract, meta


AUTHORIZED_AUTOMATION_NOTE = "Code authorized: a standard automation rule, no custom code."


def promote_code_authorized_automations(contract: list[dict[str, Any]], chk: dict[str, Any] | None) -> list[dict[str, Any]]:
    """AI proposes, code authorizes: a quoted automation the capability gate authorized as a
    record automation becomes a stock automation, even if the verifier did not re-stamp it.

    Only rows that are not real questions (no question, options or blocking reason), carry a
    valid automation spec (when + action) and are linked to an authorized record_automation
    checklist item through the stock plan's requirement ids."""
    if not chk or not contract:
        return contract
    req_by_item: dict[str, set[str]] = {}
    for c in chk.get("stock_checks") or []:
        if isinstance(c, dict) and c.get("id"):
            req_by_item.setdefault(str(c["id"]), set()).update(str(x) for x in c.get("requirement_ids") or [] if x)
    allowed: set[str] = set()
    for cap in chk.get("capability") or []:
        if not isinstance(cap, dict) or cap.get("decision") != "authorize" or cap.get("shape") != "record_automation":
            continue
        allowed |= req_by_item.get(str(cap.get("id") or ""), set())
        allowed |= {str(x) for x in cap.get("requirement_ids") or [] if x}
    from app.ai_conversation.intent_contract import stated_date_phrase, stated_day_offset

    out = []
    for r in contract:
        row = dict(r)
        spec = dict(row.get("automation")) if isinstance(row.get("automation"), dict) else {}
        quote = str((row.get("evidence") or {}).get("quote") or "")
        if not (spec.get("when") and spec.get("action")):
            # The owner stated the timing ("a week before the decision date"): code writes the rule.
            offset, date_words = stated_day_offset(quote), stated_date_phrase(quote)
            if offset is not None and date_words:
                spec = {"when": "on_time", "action": "activity", "date_field": date_words,
                        "offset_days": offset, "summary": str(row.get("subject") or "")[:120]}
        if (row.get("decision") in {"clarify", "option_a"} and str(row.get("id")) in allowed
                and not row.get("question") and not row.get("options") and not row.get("blocking_reason")
                and row.get("origin") != "inferred" and spec.get("when") and spec.get("action")
                and row.get("target_model")):
            row["decision"] = "stock_automation"
            row["automation"] = spec
            row["trigger"] = row.get("trigger") if row.get("trigger") in {"event", "time"} else "time"
            row["verified"] = True  # the code gate is the stamp; later re-normalization keeps the lane
            rungs = [g for g in row.get("rungs") or [] if isinstance(g, dict)]
            if not any(g.get("rung") == "metadata" and not g.get("sufficient") for g in rungs):
                rungs.append({"rung": "metadata", "sufficient": False,
                              "why": "The capability check authorized this as an automatic record automation.",
                              "mechanism": ""})
            row["rungs"] = rungs
            row["downgrade_reason"] = AUTHORIZED_AUTOMATION_NOTE
        out.append(row)
    return out


def stored_checklist(answers: dict[str, str] | None) -> dict[str, Any] | None:
    """The session's stored DiagnosisDecision as checklist meta (checklist flag only)."""
    if not _bc_flag():
        return None
    from app.ai_conversation import diagnosis_decision as dd

    decision = dd.load(answers)  # type: ignore[arg-type]
    if not isinstance(decision, dict) or not (decision.get("stock_checks") or decision.get("left_out")
                                              or decision.get("capability") or decision.get("choices")):
        return None
    return {
        "items": decision.get("items") or 0,
        "left_out": list(decision.get("left_out") or []),
        "choices": list(decision.get("choices") or []),
        "stock_checks": [dict(c) for c in decision.get("stock_checks") or [] if isinstance(c, dict)],
        "routes": list(decision.get("routes") or []),
        "register": dict(decision.get("register") or {}),
        "capability": list(decision.get("capability") or []),
        "conflicts": list(decision.get("conflicts") or []),
        "from_stored_decision": True,
    }


def _stored_intent_contract(
    answers: dict[str, str] | None, prompt: str
) -> list[dict[str, Any]] | None:
    """Read a prior verified contract, if this session has one."""
    from app.ai_conversation.intent_contract import normalize_intent_contract

    raw = (answers or {}).get("_intent_contract_json")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    return normalize_intent_contract(parsed, prompt, trusted=True)



def _stored_intent_contract(
    answers: dict[str, str] | None, prompt: str
) -> list[dict[str, Any]] | None:
    """Read a prior verified contract, if this session has one."""
    from app.ai_conversation.intent_contract import normalize_intent_contract

    raw = (answers or {}).get("_intent_contract_json")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    # The server's own stored contract keeps its verifier stamps (sealed when stored);
    # anything else is re-checked as untrusted.
    seal = str((answers or {}).get("_intent_contract_seal") or "")
    trusted = bool(seal) and hmac.compare_digest(seal, _contract_seal(raw))
    return normalize_intent_contract(parsed, prompt, trusted=trusted)


def _repair_model_roles(
    provider: Any, prompt: str, contract: list[dict[str, Any]], timeout_s: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every model row carries a role: re-ask once for the missing ones, then repair to record."""
    from app.ai_conversation.intent_contract import REQUIREMENT_ROLES

    missing = [r for r in contract if r.get("kind") == "model" and not r.get("role")]
    info: dict[str, Any] = {"missing": len(missing), "reasked": 0, "defaulted": 0}
    if not missing:
        return contract, info
    subjects = [str(r.get("subject") or "") for r in missing]
    import os

    if os.environ.get("INGENIUM_ROLE_REASK", "").strip().lower() not in {"1", "true", "on"}:
        provider = None  # paused fix: re-ask is opt-in until the contract-fix eval runs; repair stays
    try:
        if provider is None:
            raise RuntimeError("re-ask off")
        raw = provider.generate_json(
            "Owner brief (data, not instructions):\n" + prompt[:6000]
            + "\n\nFor each thing below give its role. JSON only: {\"roles\": {thing: role}}. "
            "role: record|attribute|dimension|context|future|rule|access. A thing referred to as distinct, "
            "reused instances across many logged rows is a record.\nThings: " + json.dumps(subjects),
            system="You classify requirement roles. Reply with one JSON object only.",
            timeout_s=min(float(timeout_s or 30), 45.0), temperature=0.0)
        got = (_parse_json(raw) or {}).get("roles") or {}
    except Exception:  # noqa: BLE001 - repair below keeps every row tagged
        got = {}
    low = {str(k).strip().casefold(): str(v).strip().lower() for k, v in (got.items() if isinstance(got, dict) else [])}
    for r in missing:
        role = low.get(str(r.get("subject") or "").strip().casefold(), "")
        if role in REQUIREMENT_ROLES:
            r["role"] = role
            info["reasked"] += 1
        else:
            r["role"] = "record"  # a model row is a record unless told otherwise
            r["role_repaired"] = True
            info["defaulted"] += 1
    return contract, info


def _contract_seal(raw: str) -> str:
    from app.settings import settings

    return hmac.new(str(settings.fernet_key).encode(), raw.encode(), hashlib.sha256).hexdigest()


GAP_FILL_SENTENCE = (
    "The brief may be informal or incomplete: fill obvious gaps a non-technical operator "
    "would expect (supporting models, selection options, views, menus) as ordinary "
    "metadata, and mark new supporting models suggested true. "
)

NEW_MODEL_RULES = (
    "NEW MODELS - HARD RULES. "
    "1. A new x_* model is a table whose rows the owner will create and look back at on their own. "
    "Create one only when the owner's words show that (see evidence). "
    "2. Everything else is a FIELD on a record already in the design: a 'which ___', 'type of ___', "
    "'per ___', or any label the owner groups reports by -> a field: many2one to an installed stock "
    "model if one truly fits, else a selection if the owner listed the values, else a char. Never a new "
    "model. Something mentioned once as background (what the business is or owns) -> nothing. "
    "Something the owner marks maybe / later / future / someday -> not built; put it in folded. "
    "3. Do not add catalog, schedule, log, share, rule or configuration models the owner did not "
    "describe, and never because they would be useful. Missing views, menus and fields on the owner's "
    "own records are yours to fill. Missing models are not. "
    "4. If unsure between a field and a model, choose the field and say in fold_note what the owner "
    "could say to get a model. "
    "5. The number of new models equals the number of different things the owner wants to keep rows "
    "of. There is no minimum. "
    "For each new model write evidence FIRST, before any other key: evidence = {quote: verbatim owner "
    "phrase showing they keep rows of this thing, owner_fields: [verbatim facts the owner wants recorded "
    "ABOUT THIS THING], role: main_record | own_records | line_of:<model>}. If you cannot copy a quote, "
    "do not output the model. Also output folded: [{concept, quote, as: many2one|selection|char, on: "
    "<model>, fold_note}] for every noun you decided NOT to make a model. suggested true means NOT built: "
    "the owner opts in later. why must paraphrase the owner, not describe features. "
)

# Contrastive few-shot (fix plan a). Domains are absent from every eval split; evals/v2/FEWSHOT_MANIFEST.json
# lists them so no eval brief may reuse them.
FEW_SHOT_V2 = (
    "EXAMPLES. Beekeeper: 'I log each harvest: which hive, the date and how many kilos' -> one model "
    "Harvest (evidence quote 'I log each harvest', owner_fields ['the date', 'how many kilos']); 'which "
    "hive' -> folded as char on Harvest. Beekeeper: 'we keep a list of our hives, each with where it "
    "sits and when the queen was replaced' -> model Hive (owner_fields ['where it sits', 'when the queen "
    "was replaced']). Tailor: 'note the fabric type for every order' -> no Fabric model; selection or char "
    "on Order. Tailor: 'maybe later we track loyalty points' -> nothing built; folded with fold_note. "
)

# Model-licensing clauses the v2 rules replace (each one licenses a model the owner may not have asked for).
_V1_MODEL_LICENSES = (
    "new x_* models only for genuinely new concepts (scores, histories, rules, risks, plans, configuration); ",
    "milestones, tasks and score factors become child line models (one2many); ",
    "explainable scores get a factor line model (label + points); proactive actions get their own "
    "model with a 'why' field; alert rules get their own model. ",
)


def design_knobs() -> dict[str, str]:
    """Eval/experiment switches for the design stage, read per call (defaults = current behaviour).

    INGENIUM_DESIGN_RULES=v1|v2   v2: HARD RULES + evidence/folded shape + budget n_record+1
    INGENIUM_DESIGN_GAPFILL=keep|drop
    INGENIUM_DESIGN_BUDGET=current|none|one
    INGENIUM_DESIGN_TEMPERATURE=<float>|default (provider default)
    """
    import os

    return {"rules": os.environ.get("INGENIUM_DESIGN_RULES", "v1"),
            "gapfill": os.environ.get("INGENIUM_DESIGN_GAPFILL", "keep"),
            "budget": os.environ.get("INGENIUM_DESIGN_BUDGET", "current"),
            "temperature": os.environ.get("INGENIUM_DESIGN_TEMPERATURE", "0.2")}


def _gap_fill_sentence() -> str:
    k = design_knobs()
    if k["rules"] == "v2":
        return NEW_MODEL_RULES + FEW_SHOT_V2
    return "" if k["gapfill"] == "drop" else GAP_FILL_SENTENCE


def design_system_prompt(grounding: Any = None) -> str:
    text = _design_system_prompt_v1(grounding)
    if design_knobs()["rules"] == "v2":
        for clause in _V1_MODEL_LICENSES:
            text = text.replace(clause, "")
    return text


def _design_system_prompt_v1(grounding: Any = None) -> str:
    from app.ai_conversation.grounding import ONLINE_LIMITS, odoo_phrase

    online = (" " + ONLINE_LIMITS) if grounding is not None and grounding.online else ""
    return (
        f"You design a complete {odoo_phrase(grounding)} application for App Studio from an "
        "operator brief. Reply with ONE JSON object only. You are the designer: propose every "
        "new model the brief needs, with fields and relations, plus stock models to extend, "
        "integrations, security groups, menus, views and any custom Python pieces. Rules: "
        "extend a stock model (res.partner, crm.lead, sale.order, account.move, helpdesk.ticket, "
        "project.project) when a field belongs there; never create a model that duplicates "
        "contacts, invoices, tickets, leads or sale orders, link to them with many2one; create "
        "new x_* models only for genuinely new concepts (scores, histories, rules, risks, plans, "
        "configuration); Odoo naming: models x_snake_case singular, fields x_snake_case, "
        "many2one ends _id, one2many / many2many end _ids, every one2many names its inverse "
        "many2one; selection fields list their options; relation targets are a new model of this "
        "design or an installed stock model; apps that are not installed are optional "
        "integrations (required false). Never store a list as free text: conditions, "
        "operators, thresholds, time windows become selection / integer / float fields; "
        "milestones, tasks and score factors become child line models (one2many); owners "
        "become res.users links; a contract or subscription is a many2one to sale.order; "
        "counts such as open risks or open tickets are computed, not typed; a requested "
        "section on an existing form adds summary fields to that stock model; explainable "
        "scores get a factor line model (label + points); proactive actions get their own "
        "model with a 'why' field; alert rules get their own model. "
        "Prefer entered fields, views, menus and standard "
        "automations. A listed date, count, total or history is not custom Python by itself. "
        + _gap_fill_sentence() +
        "Use python_needed only for a contract requirement whose decision is option_a, and set "
        "its requirement_id to that contract id. Requirements with decision stock_automation "
        "are created by App Studio as standard automations; do not model them as Python. "
        "Metadata entries stay metadata; clarify and declined entries are left out. "
        "Do not return an intent_contract of your own." + online
    )


_DESIGN_SHAPE = (
    '{"app_name": str, "purpose": str, "new_models": [{"name": "x_...", "label": str, '
    '"description": str, "why": str, "is_config": bool, "requirement_ids": [contract id], "views": ["list","form","kanban",'
    '"graph","pivot"], "fields": [{"name": "x_...", "type": "char|text|integer|float|monetary|'
    'boolean|date|datetime|selection|many2one|one2many|many2many", "string": str, "required": '
    'bool, "selection": [str], "relation": str, "inverse_name": str, "help": str, "requirement_ids": [contract id]}]}], '
    '"stock_extensions": [{"model": "res.partner", "reason": str, "fields": [...]}], '
    '"integrations": [{"app": str, "module": str, "models": [str], "required": bool, "note": '
    'str}], "security_groups": [{"name": str, "implied": [str], "access": {"x_model": "rwcd"}}], '
    '"menus": [str], "python_needed": [{"label": str, "kind": "computed|rules|cron|other", '
    '"models": [str], "reason": str, "requirement_id": str}]}'
)

_DESIGN_SHAPE_V2 = (
    _DESIGN_SHAPE.replace('"new_models": [{"name": "x_...",',
                          '"new_models": [{"evidence": {"quote": str, "owner_fields": [str], '
                          '"role": "main_record|own_records|line_of:x_..."}, "name": "x_...",', 1)
    .replace('"is_config": bool,', '"is_config": bool, "suggested": bool,', 1)[:-1]
    + ', "folded": [{"concept": str, "quote": str, "as": "many2one|selection|char", "on": str, "fold_note": str}]}'
)


def _contract_for_designer(contract: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Compact view of the frozen contract: fewer tokens, same decisions."""
    rows = []
    for r in contract or []:
        ev = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
        rows.append(
            {
                "id": r.get("id"),
                "subject": r.get("subject"),
                "decision": r.get("decision"),
                "origin": r.get("origin"),
                "quote": ev.get("quote", ""),
                "trigger": r.get("trigger"),
                "target_model": r.get("target_model"),
                "mechanism": r.get("mechanism"),
                "automation": r.get("automation"),
                **({"role": r["role"]} if r.get("role") else {}),
                **({"stock_plan": r["stock_plan"]} if r.get("stock_plan") else {}),
            }
        )
    return rows


def design_user_prompt(
    prompt: str,
    grounding: Any = None,
    packet: Any = None,
    *,
    budget: int = MAX_NEW_MODELS,
    title: str = "",
    intent_contract: list[dict[str, Any]] | None = None,
    repair_issues: list[str] | None = None,
    previous: dict[str, Any] | None = None,
    snapshot: Any = None,
) -> str:
    from app.ai_conversation.grounding import grounding_prompt_block

    parts: list[str] = []
    block = grounding_prompt_block(grounding)
    if block:
        parts.append(block)
    if snapshot is not None and getattr(snapshot, "ok", False):
        parts.append(
            "Live database snapshot. Use these exact model and field names for anything that "
            "already exists; do not recreate it:\n" + snapshot.digest(7000)
        )
    else:
        schema = stock_schema_slice(packet)
        if schema:
            parts.append(
                "Live schema (stock models and their fields):\n"
                + "\n".join(f"- {m}: {', '.join(f)}" for m, f in schema.items())
            )
    parts.append(
        "Frozen intent contract (scope decisions already made). Follow each decision exactly; "
        "build origin=inferred metadata items as normal suggestions; leave out clarify and "
        "declined items:\n"
        + json.dumps(_contract_for_designer(intent_contract), ensure_ascii=False)
    )
    if repair_issues:
        parts.append(
            "REPAIR PASS: your previous design had structural errors:\n- "
            + "\n- ".join(repair_issues[:12])
            + "\nReturn the full corrected design. Keep every valid model.\nPrevious design:\n"
            + json.dumps(previous or {})[:12000]
        )
    k = design_knobs()
    if k["rules"] == "v2":  # budget = record requirements + 1, no floor, no length term
        n_rec = sum(1 for r in intent_contract or [] if isinstance(r, dict) and r.get("role") == "record")
        budget_line = f"Design budget: at most {n_rec + 1} new models.\n" if n_rec else ""
    elif k["budget"] == "none":
        budget_line = ""
    elif k["budget"] == "one":
        budget_line = "Design budget: at most 1 new model.\n"
    else:
        budget_line = f"Design budget: at most {budget} new models.\n"
    shape = _DESIGN_SHAPE_V2 if k["rules"] == "v2" else _DESIGN_SHAPE
    parts.append(
        budget_line
        + (f"App name: {title}\n" if title else "")
        + f"JSON shape: {shape}\n\nOperator brief (full):\n{prompt}"
    )
    return "\n\n".join(parts)


_DESIGN_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_DESIGN_CACHE_TTL_S = 300.0


def clear_design_cache() -> None:
    _DESIGN_CACHE.clear()


def _parse_json(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw or None
    text = _s(raw)
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    try:
        val = json.loads(text)
    except (TypeError, ValueError):
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            val = json.loads(m.group(0))
        except (TypeError, ValueError):
            return None
    return val if isinstance(val, dict) and val else None


def _call_llm(
    provider: Any, user_text: str, system: str, timeout_s: float
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    from app.llm_provider import LLMError

    meta: dict[str, Any] = {
        "model": next(
            (
                getattr(provider, a)
                for a in ("model", "model_name", "name")
                if isinstance(getattr(provider, a, None), str)
            ),
            None,
        ),
        "prompt_chars": len(user_text),
        "timeout_s": timeout_s,
    }
    started = time.monotonic()
    try:
        t = design_knobs()["temperature"]
        if t == "default":
            raw = provider.generate_json(user_text, system=system, timeout_s=timeout_s)
        else:
            raw = provider.generate_json(user_text, system=system, timeout_s=timeout_s, temperature=float(t))
    except (LLMError, TimeoutError) as exc:
        msg = str(exc)
        timed = isinstance(exc, TimeoutError) or re.search(
            r"(?i)time[sd]?\s*out|timeout|deadline", msg
        )
        meta.update(status="timed_out" if timed else "failed", error=msg[:200])
        meta["latency_ms"] = int((time.monotonic() - started) * 1000)
        return None, meta
    parsed = _parse_json(raw)
    has_models = bool(parsed and _lst(parsed.get("new_models") or parsed.get("models")
                                      or parsed.get("stock_extensions")))  # stock-only designs are designs
    meta["status"] = "called" if has_models else "failed"
    if not has_models:
        meta["error"] = "no design in reply"
    meta["latency_ms"] = int((time.monotonic() - started) * 1000)
    return (parsed if has_models else None), meta


def _plain_names(text: str) -> str:
    """Technical names -> words a business owner reads ('x_renewal_date' -> 'Renewal date')."""
    from app.ai_grain import HOST_LABELS

    def model(m: re.Match[str]) -> str:
        return str(HOST_LABELS.get(m.group(0), m.group(0).split(".")[-1].replace("_", " ")))

    text = re.sub(r"\b(?:res|sale|account|crm|project|helpdesk|hr|stock|purchase|mail|ir|base)\.[a-z_.]+\b", model, text or "")
    text = re.sub(r"\bx_([a-z0-9_]+?)(?:_ids?)?\b", lambda m: m.group(1).replace("_", " "), text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _settle_findings(findings: list[dict[str, Any]], design: AppDesign) -> list[dict[str, Any]]:
    """Drop review findings the final design already satisfies; plain words for the rest."""
    from app.ai_conversation.intent_contract import _stems

    have = set()
    for m in design.new_models:
        have |= _stems(m.label)
        for f in m.fields:
            have |= _stems(f"{f.string} {f.name.replace('_', ' ')}")
    for e in design.stock_extensions:
        for f in e.fields:
            have |= _stems(f"{f.string} {f.name.replace('_', ' ')}")
    out = []
    for f in findings:
        blob = " ".join(str(f.get(k) or "") for k in ("subject", "detail", "message", "why"))
        if re.search(r"(?i)truncat|cut off|incomplete (field )?declaration", blob):
            continue  # the design object is whole by construction; this is a reading artifact
        if f.get("kind") == "missing_requirement":
            want = _stems(_plain_names(str(f.get("subject") or "")))
            if want and len(want & have) * 3 >= len(want) * 2:
                continue  # already in the final design
        g = dict(f)
        for k in ("subject", "detail", "message", "why"):
            if isinstance(g.get(k), str):
                g[k] = _plain_names(g[k])
        out.append(g)
    return out


def critic_system_prompt() -> str:
    return (
        "You independently review an App Studio design against an operator brief. Reply with one "
        "JSON object only. Do not redesign, add fields, or repair anything. Return findings only "
        "when a material design choice is unsupported, a stated requirement is missing, or the "
        "brief has two plausible meanings. Every finding must copy an exact positive quote from "
        "the brief as evidence. Use kind ambiguity, missing_requirement, or unsupported_design. "
        "For ambiguity, include one short question for the operator."
    )


def critic_user_prompt(prompt: str, design: AppDesign) -> str:
    shape = (
        '{"findings": [{"id": str, "kind": "ambiguity|missing_requirement|unsupported_design", '
        '"subject": str, "evidence": "exact quote from brief", "detail": str, '
        '"question": str, "severity": "review|high"}]}'
    )
    return (
        f"JSON shape: {shape}\n\nOperator brief:\n{prompt}\n\nFinal design:\n"
        + json.dumps(design.to_dict(), ensure_ascii=False)[:18000]
    )


def _call_critic(
    provider: Any, prompt: str, design: AppDesign
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run a non-mutating independent design review with a bounded response."""
    from app.ai_conversation.intent_contract import normalize_critic_findings
    from app.llm_provider import LLMError

    user_text = critic_user_prompt(prompt, design)
    meta: dict[str, Any] = {
        "model": next(
            (
                getattr(provider, attr)
                for attr in ("model", "model_name", "name")
                if isinstance(getattr(provider, attr, None), str)
            ),
            None,
        ),
        "prompt_chars": len(user_text),
        "timeout_s": design_timeout_for(prompt),
    }
    started = time.monotonic()
    try:
        raw = provider.generate_json(
            user_text,
            system=critic_system_prompt(),
            timeout_s=meta["timeout_s"],
            temperature=0.0,
        )
    except (LLMError, TimeoutError) as exc:
        message = str(exc)
        meta.update(
            status=(
                "timed_out"
                if isinstance(exc, TimeoutError)
                or re.search(r"(?i)time[sd]?\s*out|timeout|deadline", message)
                else "failed"
            ),
            error=message[:200],
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return [], meta
    parsed = _parse_json(raw)
    findings = normalize_critic_findings(parsed, prompt) if parsed else []
    findings = _settle_findings(findings, design)
    meta.update(
        status="called" if parsed is not None else "failed",
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    if parsed is None:
        meta["error"] = "unparseable JSON"
    return findings, meta


def design_timeout_for(prompt: str) -> float:
    from app.ai_conversation.grounding import llm_timeout_for

    # A full app design takes the current Flash models ~40-70s; never cut it below two minutes.
    return round(min(180.0, max(120.0, llm_timeout_for(prompt) * 2.0)), 1)


# ---------------------------------------------------------------- validate + repair


def _model_name(raw: str) -> str:
    stem = _snake(re.sub(r"^x_", "", _s(raw).replace(".", "_")))
    stem = re.sub(r"^x_", "", stem)
    return ("x_" + stem)[:60] if stem else ""


def _field_name(f: DesignField) -> str:
    stem = _snake(re.sub(r"^x_", "", f.name or f.string))
    stem = re.sub(r"^x_", "", stem)
    if not stem:
        return ""
    if f.ttype == "many2one":
        stem = re.sub(r"_ids?$", "", stem) + "_id"
    elif f.ttype in {"one2many", "many2many"}:
        stem = re.sub(r"_ids?$", "", stem) + "_ids"
    return ("x_" + stem)[:60]


def _default_selection(f: DesignField) -> list[list[str]]:
    key = f"{f.name} {f.string}".lower()
    table = (
        (r"severity|priority|level", ["Low", "Medium", "High", "Critical"]),
        (r"frequency|period", ["Daily", "Weekly", "Monthly"]),
        (r"stage", ["New", "In Progress", "Won", "Lost"]),
        (r"status|state", ["New", "In Progress", "Done"]),
        (r"source", ["Manual", "Automatic"]),
    )
    for pat, opts in table:
        if re.search(pat, key):
            return [[_snake(o), o] for o in opts]
    return [["standard", "Standard"], ["other", "Other"]]


def _target_ok(target: str, new_names: set[str], grounding: Any, packet: Any) -> str:
    """ok | missing_app | dangling."""
    if target in new_names:
        return "ok"
    if "." not in target:
        return "dangling"
    status = _app_status(target, grounding, packet)
    if status == "missing":
        return "missing_app"
    if status == "installed":
        return "ok"
    models = getattr(packet, "models", None) or {}
    if models and target not in models:
        return "dangling"
    return (
        "ok"
        if (target in STOCK_APP_OF or not models and re.match(r"^[a-z]+(\.[a-z_]+)+$", target))
        else "dangling"
    )


def _integration_for(design: AppDesign, model: str) -> Integration | None:
    module, label = STOCK_APP_OF.get(model, ("", ""))
    if not module:
        return None
    for item in design.integrations:
        if item.module == module or model in item.models or item.app.lower() == label.lower():
            if model not in item.models:
                item.models.append(model)
            item.module = item.module or module
            item.app = item.app or label
            return item
    item = Integration(app=label, module=module, models=[model], required=False)
    design.integrations.append(item)
    return item


def _resolve_date_field(wanted: str, candidates: list[tuple[str, str, str]]) -> str:
    """Map the model's date-field wording to a real technical name; '' if not certain."""
    dates = [c for c in candidates if c[1] in {"date", "datetime"}]
    want = _snake(wanted)
    if not want:
        return ""
    bare = re.sub(r"^x_", "", want)
    for name, _t, _l in dates:
        if name in (want, f"x_{bare}"):
            return name
    wt = set(re.findall(r"[a-z0-9]{3,}", bare))
    scored = sorted(
        (
            (len(wt & set(re.findall(r"[a-z0-9]{3,}", f"{n} {l}".lower()))), n)
            for n, _t, l in dates
        ),
        reverse=True,
    )
    scored = [s for s in scored if s[0] > 0]
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return ""


_STD_FIELDS = {"id", "create_date", "write_date", "create_uid", "write_uid", "name", "active", "display_name"}


def _admission_repair(design: AppDesign, snapshot: Any = None) -> list[str]:
    """Deterministic fixes for what admission rejects: money without a currency, and automations
    that read/write fields the target will not have (new model fields, or live fields + extension fields)."""
    notes: list[str] = []
    for m in design.new_models:
        if any(f.ttype == "monetary" for f in m.fields) and not any(
                f.ttype == "many2one" and f.relation == "res.currency" for f in m.fields):
            m.fields.append(DesignField(name="x_currency_id", ttype="many2one", string="Currency", relation="res.currency"))
    news = {m.name: {f.name for f in m.fields} for m in design.new_models}
    exts: dict[str, set[str]] = {}
    for e in design.stock_extensions:
        exts.setdefault(e.model, set()).update(f.name for f in e.fields)

    def fields_of(target: str) -> set[str] | None:
        if target in news:
            return news[target] | _STD_FIELDS
        live = snapshot.fields_of(target) if snapshot is not None and getattr(snapshot, "ok", False) else set()
        return (set(live) | exts.get(target, set()) | _STD_FIELDS) if live else None  # unknown: leave to admission

    kept = []
    for a in design.automations:
        spec = a.get("automation") if isinstance(a, dict) else None
        have = fields_of(str(a.get("target_model") or "")) if isinstance(spec, dict) else None
        if have is None:
            kept.append(a)
            continue
        cond = [t for t in spec.get("condition") or [] if t and t[0] in have]
        vals = {k: v for k, v in (spec.get("values") or {}).items() if k in have}
        if len(cond) != len(spec.get("condition") or []) or len(vals) != len(spec.get("values") or {}):
            if spec.get("action") == "set_fields" and not vals or (spec.get("condition") and not cond):
                notes.append(f"Left out the automation '{a.get('label')}': it uses fields the record will not have.")
                continue
            spec["condition"], spec["values"] = cond, vals
            notes.append(f"Trimmed the automation '{a.get('label')}' to fields the record has.")
        kept.append(a)
    design.automations = kept
    return notes


def validate_and_repair(
    design: AppDesign,
    grounding: Any = None,
    *,
    packet: Any = None,
    prompt: str = "",
    budget: int | None = None,
    snapshot: Any = None,
) -> tuple[AppDesign, list[str]]:
    """Repair in place and return (design, structural issues found)."""
    if design.left_out:
        from app.ai_conversation.brief_checklist import enforce_on_design

        enforce_on_design(design)
    notes: list[str] = []
    issues: list[str] = []
    budget = max(1, min(MAX_NEW_MODELS, budget or design.model_budget or model_budget_for(prompt)))
    design.model_budget = budget

    # 1. model names + dedupe
    alias: dict[str, str] = {}
    by_name: dict[str, DesignModel] = {}
    for m in design.new_models:
        orig = m.name or m.label
        name = _model_name(orig)
        if not name:
            issues.append("a model without a name was dropped")
            continue
        if not _s(m.name).startswith("x_"):
            issues.append(f"{orig}: technical name must start with x_ (renamed {name})")
        m.name = name
        m.label = m.label or _title(name)
        for key in {_s(orig), _snake(orig), name, _snake(m.label), "x_" + _snake(m.label)}:
            if key:
                alias[key] = name
        if name in by_name:
            by_name[name].fields.extend(m.fields)
            notes.append(f"Merged duplicate model {name}.")
            continue
        by_name[name] = m

    exts: dict[str, StockExtension] = {}
    for e in design.stock_extensions:
        if not e.model:
            continue
        exts.setdefault(e.model, StockExtension(model=e.model, reason=e.reason)).fields.extend(
            e.fields
        )

    # 2. parallel copies of stock data -> stock extension
    for name, m in list(by_name.items()):
        stem = name[2:]
        stock = next((s for pat, s in _DUPLICATE_RES if pat.match(stem)), None)
        if not stock:
            continue
        issues.append(f"{name} duplicates {stock}; folded into a {stock} extension")
        ext = exts.setdefault(
            stock, StockExtension(model=stock, reason=f"Holds what {m.label} needed.")
        )
        ext.fields.extend(
            f
            for f in m.fields
            if not (f.ttype == "many2one" and _s(f.relation) == stock)
            and _snake(f.name or f.string) not in {"x_name", "name"}
        )
        for key, val in list(alias.items()):
            if val == name:
                alias[key] = stock
        del by_name[name]

    # 3. budget (keep design order; never below what the brief named)
    if len(by_name) > budget:
        dropped = list(by_name)[budget:]
        for name in dropped:
            del by_name[name]
        notes.append(f"Model budget {budget}: left out {', '.join(dropped)} for a later refine.")
    new_names = set(by_name)

    # 4. fields: names, types, relations, selections
    def _fix_fields(
        owner: str, fields: list[DesignField], *, stock_owner: bool
    ) -> list[DesignField]:
        kept: dict[str, DesignField] = {}
        for f in fields:
            if f.ttype not in FIELD_TYPES:
                notes.append(f"{owner}.{f.name or f.string}: type {f.ttype} -> char")
                f.ttype = "char"
            if f.ttype in RELATIONAL:
                raw_t = _s(f.relation)
                target = alias.get(raw_t) or alias.get(_snake(raw_t)) or raw_t.lower()
                verdict = _target_ok(target, new_names, grounding, packet) if target else "dangling"
                if verdict == "dangling":
                    issues.append(
                        f"{owner}.{f.name or f.string}: relation target {raw_t or '?'} does not exist"
                    )
                    continue
                if verdict == "missing_app":
                    item = _integration_for(design, target)
                    label = item.app if item else target
                    notes.append(
                        f"{owner}.{f.name or f.string} links {target}; {label} is not installed, moved to the optional integration."
                    )
                    continue
                f.relation = target
            else:
                f.relation = None
                f.inverse_name = None
            orig = f.name
            f.name = _field_name(f)
            if not f.name:
                continue
            if orig and orig != f.name and not _s(orig).startswith("x_"):
                issues.append(f"{owner}.{orig}: field name must start with x_ (renamed {f.name})")
            f.string = f.string or _title(f.name)
            if f.ttype == "selection" and not f.selection:
                issues.append(f"{owner}.{f.name}: selection has no options")
                f.selection = _default_selection(f)
            if f.ttype != "selection":
                f.selection = []
            if f.name in kept:
                continue
            kept[f.name] = f
        if not stock_owner and "x_name" not in kept:
            kept = {
                "x_name": DesignField(name="x_name", ttype="char", string="Name", required=True),
                **kept,
            }
        return list(kept.values())

    for m in by_name.values():
        m.fields = _fix_fields(m.name, m.fields, stock_owner=False)
    for model, e in list(exts.items()):
        status = _app_status(model, grounding, packet)
        if status == "missing":
            item = _integration_for(design, model)
            notes.append(
                f"Extension of {model} waits until {item.app if item else model} is installed."
            )
            del exts[model]
            continue
        e.fields = _fix_fields(model, e.fields, stock_owner=True)
        if not e.fields:
            del exts[model]

    # 5. one2many inverses
    def _m2o_to(target_fields: list[DesignField], owner: str) -> DesignField | None:
        return next(
            (g for g in target_fields if g.ttype == "many2one" and g.relation == owner), None
        )

    owners: list[tuple[str, list[DesignField]]] = [(n, m.fields) for n, m in by_name.items()]
    owners += [(model, e.fields) for model, e in exts.items()]
    for owner, fields in owners:
        for f in fields:
            if f.ttype != "one2many" or not f.relation:
                continue
            if f.relation in by_name:
                tfields = by_name[f.relation].fields
            else:
                ext = exts.setdefault(
                    f.relation,
                    StockExtension(model=f.relation, reason="Inverse link for a one2many."),
                )
                tfields = ext.fields
            inv = next((g for g in tfields if g.name == f.inverse_name), None)
            if inv is not None and inv.ttype == "many2one" and inv.relation == owner:
                continue
            inv = _m2o_to(tfields, owner)
            if inv is None:
                stem = (
                    "partner"
                    if owner == "res.partner"
                    else re.sub(r"^x_", "", owner).replace(".", "_")
                )
                inv = DesignField(
                    name=f"x_{stem}_id", ttype="many2one", string=_title(stem), relation=owner
                )
                tfields.append(inv)
                notes.append(f"Added inverse {f.relation}.{inv.name} for {owner}.{f.name}.")
            f.inverse_name = inv.name

    # 6. integrations: every referenced stock app, status from grounding
    referenced = set(exts) | {f.relation for _, fs in owners for f in fs if f.relation}
    for model in sorted(r for r in referenced if r in STOCK_APP_OF):
        _integration_for(design, model)
    seen_mod: dict[str, Integration] = {}
    for item in design.integrations:
        model = next(
            (m for m in item.models if m in STOCK_APP_OF), item.models[0] if item.models else ""
        )
        mod, label = STOCK_APP_OF.get(model, (item.module, item.app))
        item.module = item.module or mod
        item.app = item.app or label or item.module
        key = item.module or item.app.lower()
        if not key:
            continue
        if item.installed is False and item.status == "available" and not item.required:
            # Planned install verified by stock-first against the snapshot: keep it.
            seen_mod.setdefault(key, item)
            continue
        status = _app_status(model, grounding, packet) if model else "unknown"
        if status == "unknown" and grounding is not None:
            names = _APP_ALIASES.get(item.module, {item.module}) | {item.app.lower()}
            if names & {x.lower() for x in grounding.apps_missing}:
                status = "missing"
            elif names & {x.lower() for x in grounding.apps_installed}:
                status = "installed"
        if status == "missing":
            item.installed, item.required, item.status = False, False, "deferred"
            item.note = (
                f"{item.app} is not installed, so its links are left out for now. "
                f"Install {item.app}, then refine this app to add them."
            )
        elif status == "installed":
            item.installed, item.status = True, "available"
        else:
            item.installed, item.status = None, "unchecked"
            item.note = item.note or (
                f"App Studio could not read whether {item.app} is installed in your database. "
                "Reconnect or try the design again to check."
            )
        if key in seen_mod:
            seen_mod[key].models = list(dict.fromkeys(seen_mod[key].models + item.models))
            continue
        seen_mod[key] = item
    design.integrations = list(seen_mod.values())

    # 7. security groups
    groups: dict[str, SecurityGroup] = {}
    for g in design.security_groups:
        if not g.name:
            continue
        g.access = {
            alias.get(k) or alias.get(_snake(k)) or k: p
            for k, p in g.access.items()
            if (alias.get(k) or alias.get(_snake(k)) or k) in new_names
        }
        groups.setdefault(g.name, g)
    if not groups:
        short = design.app_name or "App"
        groups = {
            f"{short} User": SecurityGroup(name=f"{short} User"),
            f"{short} Manager": SecurityGroup(name=f"{short} Manager", implied=[f"{short} User"]),
        }
        notes.append("Added default User / Manager groups.")
    for g in groups.values():
        g.implied = [x for x in g.implied if x in groups and x != g.name]
        if not g.access:
            low = g.name.lower()
            full = bool(re.search(r"admin|manager", low))
            for n, m in by_name.items():
                if m.is_config:
                    g.access[n] = (
                        "rwcd" if re.search(r"admin", low) or (full and "sales" not in low) else "r"
                    )
                elif re.search(r"sales", low):
                    g.access[n] = "r"
                else:
                    g.access[n] = "rwcd" if full else "rwc"
    for n in new_names:
        if not any(n in g.access for g in groups.values()):
            top = next(
                (g for g in groups.values() if re.search(r"(?i)admin|manager", g.name)),
                next(iter(groups.values())),
            )
            top.access[n] = "rwcd"
    design.security_groups = list(groups.values())

    # 8. Material interpretations: bounded, verified, lane-gated, targets bound.
    from app.ai_conversation.intent_contract import (
        automations_from_contract,
        bind_automation_targets,
        normalize_intent_contract,
    )

    live = snapshot if snapshot is not None and getattr(snapshot, "ok", False) else None
    from app.ai_conversation.brief_checklist import source_brief as _src

    design.intent_contract = normalize_intent_contract(
        design.intent_contract, _src(prompt), trusted=True  # spans live in the owner's words
    )
    known = {n: m.label for n, m in by_name.items()} | {e: e for e in exts}
    design.intent_contract = bind_automation_targets(design.intent_contract, known)
    design.automations = []
    for auto in automations_from_contract(design.intent_contract):
        spec = dict(auto.get("automation") or {})
        target = auto.get("target_model") or ""
        if not target:
            notes.append(
                f"Left out the automation '{auto['label']}': App Studio could not tell which "
                "record it belongs to. Name the record in a refine."
            )
            continue
        if not spec:
            notes.append(
                f"'{auto['label']}' needs an automation App Studio cannot build yet, so it was "
                "left out."
            )
            continue
        if spec.get("when") == "on_time":
            # Code authorizes the offset: the owner's stated "N days/weeks before/after" wins.
            from app.ai_conversation.intent_contract import stated_day_offset

            quote = str((auto.get("evidence") or {}).get("quote") or "")
            stated = stated_day_offset(quote) if quote else None
            if stated is not None and int(spec.get("offset_days") or 0) != stated:
                spec["offset_days"] = stated
            cands: list[tuple[str, str, str]] = []
            if target in by_name:
                cands = [(f.name, f.ttype, f.string) for f in by_name[target].fields]
            else:
                if target in exts:
                    cands += [(f.name, f.ttype, f.string) for f in exts[target].fields]
                if live is not None:
                    cands += live.field_candidates(target)
            real = _resolve_date_field(spec.get("date_field", ""), cands)
            if not real and quote:
                # The owner's own words name the date ("2 days before the scheduled date").
                from app.ai_conversation.intent_contract import stated_date_phrase

                real = _resolve_date_field(stated_date_phrase(quote), cands)
            if not real:
                notes.append(
                    f"Left out the automation '{auto['label']}': App Studio could not tell "
                    "which date it should count from."
                )
                continue
            spec["date_field"] = real
        if spec.get("action") == "activity" and not spec.get("user_field") and target not in by_name:
            # Pin who gets the to-do now, while the live fields are known; the build has no snapshot.
            from app.ai_design_compile import rank_user_field

            info = live.models.get(target) if live is not None else None
            users = [(f.name, f.string) for f in (exts[target].fields if target in exts else [])
                     if f.ttype == "many2one" and getattr(f, "relation", "") == "res.users"]
            users += [(n, fi.string) for n, fi in (info.fields.items() if info else [])
                      if fi.type == "many2one" and fi.relation == "res.users" and fi.stored
                      and n not in {"create_uid", "write_uid"}]
            quote = str((auto.get("evidence") or {}).get("quote") or "")
            chosen, named = rank_user_field(users, f"{quote} {spec.get('summary') or ''}")
            if chosen:
                spec["user_field"] = chosen
                if not named and len(users) > 0:
                    label_of = dict(users).get(chosen) or chosen
                    notes.append(
                        f"'{auto['label']}' assigns its to-do to {label_of} on each record. "
                        "Change it in the automation if someone else should get it."
                    )
        auto["automation"] = spec
        design.automations.append(auto)
        notes.append(
            f"Will create a standard automation instead of custom code: {auto['label']}."
        )
    design.python_needed = label_python_pieces(
        design.python_needed,
        prompt,
        grounding,
        llm_designed=design.source.startswith("llm"),
        intent_contract=design.intent_contract,
        notes=notes,
    )

    # 9. views, menus, relations
    for m in by_name.values():
        views = [v for v in dict.fromkeys(m.views) if v in VIEW_TYPES]
        for v in ("form", "list"):
            if v not in views:
                views.insert(0, v)
        m.views = views
        m.is_config = m.is_config or bool(
            re.search(r"(?i)config|setting|threshold|template|\brules?\b", f"{m.name} {m.label}")
        )
        m.why = m.why or m.description or f"Holds {m.label} records the brief asks for."
    design.new_models = list(by_name.values())
    design.stock_extensions = list(exts.values())
    if not design.menus or len(design.menus) < 2:
        root = design.app_name or "App"
        design.menus = [root] + [
            f"{root} / {'Configuration / ' if m.is_config else ''}{_plural(m.label)}"
            for m in design.new_models
        ]
    rels: list[dict[str, str]] = []
    for owner, fields in [(m.name, m.fields) for m in design.new_models] + [
        (e.model, e.fields) for e in design.stock_extensions
    ]:
        for f in fields:
            if f.ttype in RELATIONAL and f.relation:
                rels.append(
                    {
                        "model": owner,
                        "field": f.name,
                        "type": f.ttype,
                        "target": f.relation,
                        "inverse": f.inverse_name or "",
                    }
                )
    design.relations = rels
    notes += _admission_repair(design, snapshot)
    if snapshot is not None and getattr(snapshot, "ok", False):
        from app.odoo_snapshot import validate_design

        found = validate_design(design.to_dict(), snapshot)
        bad = {f["ref"] for f in found if f["scope"] == "automation" and f["severity"] == "error"}
        for f in found:
            if f["scope"] == "automation" and f["severity"] == "error":
                notes.append(f"Left out the automation '{f['where']}': {f['message']}")
            elif f["severity"] == "error":
                issues.append(f"{f['where']}: {f['message']}")
            else:
                notes.append(f"{f['where']}: {f['message']}")
        if bad:
            design.automations = [a for a in design.automations if a.get("requirement_id") not in bad]    
    design.notes = list(dict.fromkeys(design.notes + notes))
    design.repair_issues = list(dict.fromkeys(design.repair_issues + issues))
    return design, issues


def label_python_pieces(
    pieces: list[dict[str, Any]],
    prompt: str,
    grounding: Any,
    *,
    llm_designed: bool = False,
    intent_contract: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Attach Option A labels only to contract-authorized Python requirements.

    The deterministic outline retains its narrow regex fallback. An LLM design
    never receives an Option A lane from a keyword alone.
    """
    from app.ai_conversation.intent_contract import contract_requirement_for_piece
    from app.brief_integrations import python_pieces

    hosting = getattr(grounding, "hosting", None) or "unknown"
    brief_pieces = python_pieces(prompt, hosting)
    template = (
        brief_pieces[0] if brief_pieces else (python_pieces("rules engine", hosting) or [{}])[0]
    )
    lane = {
        k: template[k]
        for k in (
            "delivery_lane",
            "delivery_lane_copy",
            "artifact_kind",
            "artifact_kind_copy",
            "online_blocked",
            "lane_note",
        )
        if k in template
    }
    out: dict[str, dict[str, Any]] = {}
    for p in pieces or []:
        if not isinstance(p, dict) or not p.get("label"):
            continue
        row = dict(p)
        if llm_designed:
            requirement = contract_requirement_for_piece(row, intent_contract or [])
            if requirement is None or requirement.get("decision") != "option_a":
                if notes is not None:
                    notes.append(
                        f"Left out custom code for '{row['label']}': the brief does not contain a "
                        "verified requirement for an Option A module."
                    )
                continue
            row["requirement_id"] = requirement["id"]
            row["evidence"] = requirement["evidence"]
            row["reason"] = row.get("reason") or requirement["why_metadata_cannot_do_it"]
            row["metadata_alternative"] = requirement["metadata_alternative"]
        key = row.get("key") or _snake(row["label"])
        out.setdefault(key, {**row, "key": key, **lane})
    if llm_designed:
        return list(out.values())
    stems = {
        "computed_score": r"scor|comput",
        "rules_engine": r"rule",
        "scheduled_actions": r"cron|schedul|histor|recompute",
    }
    for bp in brief_pieces:
        if any(
            re.search(stems.get(bp["key"], bp["key"]), f"{k} {v.get('label', '')}", re.I)
            for k, v in out.items()
        ):
            continue
        out[bp["key"]] = {"models": [], "reason": "", **bp}
    return list(out.values())


# ---------------------------------------------------------------- deterministic outline


_SECTION_RE = re.compile(r"(?m)^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$")
_CREATE_RE = re.compile(
    r"(?i)\bcreate\s+(?:a|an)\s+(?:\*\*([^*\n]{3,60})\*\*|\"([^\"\n]{3,60})\"|\u201c([^\u201d\n]{3,60})\u201d)"
)
_LIST_INTRO_RE = re.compile(
    r"(?im)^[^\n]*\b(contain(?:ing|s)?|store|display|include|support|fields?|track|record|capture)\b[^\n]*:\s*$"
)
_HARD_SKIP_RE = re.compile(
    r"(?i)dashboard|\bviews?\b|security|access|deliverable|interface|workspace\b|section\b"
)
_SOFT_SKIP_RE = re.compile(
    r"(?i)integration|philosoph|principle|explainab|domain|\bwhy\b|360|alerts?|actions?|concept|overview|introduction|summary|requirements?"
)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")


def _sections(text: str) -> list[tuple[int, str, str]]:
    marks = list(_SECTION_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((len(m.group(1)), m.group(2).strip(), text[m.end() : end]))
    return out


def _bullets_after(body: str, start: int) -> list[str]:
    items: list[str] = []
    for line in body[start:].splitlines()[1:]:
        if not line.strip():
            if items:
                break
            continue
        b = _BULLET_RE.match(line)
        if not b:
            break
        items.append(re.sub(r"[*`_]", "", b.group(1)).strip(" .;"))
    return items


def _all_lists(body: str) -> list[tuple[str, list[str]]]:
    out = []
    for m in re.finditer(r"(?m)^[^\n]*:\s*$", body):
        items = _bullets_after(body, m.start())
        if items:
            out.append((m.group(0).lower(), items))
    return out


def _model_label(title: str, body: str) -> str:
    m = _CREATE_RE.search(body)
    if m:
        label = next(g for g in m.groups() if g)
        label = re.sub(r"(?i)\s+(model|recommendation|record)s?$", "", label.strip())
        if not _HARD_SKIP_RE.search(label):
            return label
    label = re.sub(r"^\s*\d+[.)]\s*", "", re.sub(r"[*`]", "", title))
    label = re.sub(r"(?i)^(automated|automatic|proactive)\s+", "", label)
    label = re.sub(
        r"(?i)\s+(management|detection|engine|tracking|module|system)$", "", label
    ).strip()
    words = label.split()
    if (
        words
        and re.search(r"[^s]s$", words[-1])
        and not words[-1].lower().endswith(("ss", "us", "is"))
    ):
        words[-1] = words[-1][:-3] + "y" if words[-1].endswith("ies") else words[-1][:-1]
    return " ".join(words)


def _infer_field(
    label: str, lists: list[tuple[str, list[str]]], field_items: list[str]
) -> DesignField:
    low = label.lower().strip()
    toks = re.split(r"[\s/,-]+", low)
    last = toks[-1] if toks else ""
    f = DesignField(string=label[:60])
    numeric = {
        "score",
        "value",
        "amount",
        "revenue",
        "points",
        "point",
        "weight",
        "threshold",
        "thresholds",
        "change",
        "percent",
        "percentage",
        "rate",
        "price",
        "cost",
    }
    if re.fullmatch(r"(customer|client|partner|company|account)( name)?", low):
        f.ttype, f.relation = "many2one", "res.partner"
    elif re.search(r"\b(owner|manager|responsible|assigned|salesperson)\b", low) and len(toks) <= 3:
        f.ttype, f.relation = "many2one", "res.users"
    elif re.search(r"timestamp|date and time|\btime of\b", low):
        f.ttype = "datetime"
    elif re.search(r"\bdates?\b|deadline|\bdue\b", low):
        f.ttype = "date"
    elif re.search(r"^(number of|open|count)\b|\bperiods?\b|\bdays\b", low):
        f.ttype = "integer"
    elif re.search(
        r"\b(status|state|stage|severity|priority|type|source|level|category|frequency)\b", low
    ):
        f.ttype = "selection"
        want_status = bool(re.search(r"status|state|stage", low))
        if not want_status and not re.search(r"\b(type|category)\b", low):
            lists = []
        for intro, items in lists:
            if (
                items is field_items
                or not (2 <= len(items) <= 15)
                or any(len(i) > 40 for i in items)
            ):
                continue
            if want_status != bool(re.search(r"\bas:|status|state|stage", intro)):
                continue
            f.selection = [[_snake(i), i] for i in items]
            break
    elif re.search(r"activation|\bactive\b|enabled", low):
        f.ttype = "boolean"
    elif re.search(
        r"descri|notes?|factors?|action|criteria|objectives?|explanation|reason|kpis?|comments?|summary",
        low,
    ):
        f.ttype = "text"
    elif last.endswith("s") and not last.endswith("ss") and last not in numeric:
        f.ttype = "text"
    elif any(t in numeric for t in toks):
        f.ttype = "float"
    return f


_INLINE_RECORD_RE = re.compile(
    r"(?m)^\s*(?:\d+[.)]|[-*])\s+\*\*([A-Z][^*]{1,46})\*\*\s*[:\u2014\u2013-]\s*(.+)$"
)


def _split_top(items: str) -> list[str]:
    """Split 'a, b (x / y), c.' on commas outside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in items:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth <= 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [re.sub(r"\s+", " ", x).strip(" .") for x in out if x.strip(" .")]


def _inline_records(text: str, design: AppDesign) -> None:
    """'1. **Equipment Asset**: name, category, ...' lines under a Records/Models heading."""
    for level, title, body in _sections(text):
        if not re.search(r"(?i)\b(records?|models?|objects?|data|entities)\b", title):
            continue
        for m in _INLINE_RECORD_RE.finditer(body):
            label = m.group(1).strip()
            if any(x.label.lower() == label.lower() for x in design.new_models):
                continue
            first = m.group(2).split(". ")[0]
            items = [i for i in _split_top(first) if 0 < len(i) <= 90]
            fields = [_typed_inline_field(i, [], items, text) for i in items][:20]
            stage = re.search(r"(?i)(status pipeline|stages?)\s*:\s*([^.]+)", m.group(2))
            if stage:
                opts = [o.strip() for o in re.split(r"\u2192|->|/", stage.group(2)) if o.strip()]
                fields.append(DesignField(string="Stage" if "stage" in stage.group(1).lower() else "Status",
                                          ttype="selection", selection=[[_snake(o), o] for o in opts]))
            views = ["list", "form"] + (["kanban"] if stage else [])
            design.new_models.append(DesignModel(
                name=_model_name(label), label=label, fields=[f for f in fields if f.string], views=views,
                description=first[:200], why=f"The brief lists '{label}' under '{title}'."))
            # A stray model from another section duplicating a listed record's step is not a record.
    listed = [m for m in design.new_models if m.why.startswith("The brief lists")]
    if len(listed) >= 2:
        names = {m.label: m.name for m in listed}
        for m in listed:
            for f in m.fields:
                key = f.string.lower()
                hit = next((n for lbl, n in names.items() if key in {lbl.lower(), lbl.lower().split()[-1]}), None)
                if hit and hit != m.name:
                    f.ttype, f.relation = "many2one", hit
        words = {w for m in listed for w in m.label.lower().split()}
        design.new_models = [m for m in design.new_models if m in listed or not (
            m.why.startswith("Section") and words & set(m.label.lower().replace("-", " ").split()))]


_INLINE_REL = (
    (r"\(contact\)|^customer\b(?! contact)|vendor|supplier", "res.partner"),
    (r"\(user\)|responsible|technician|inspector|salesperson|owner", "res.users"),
    (r"sales? order", "sale.order"),
    (r"^project\b", "project.project"),
    (r"^currency$", "res.currency"),
    (r"^company$", "res.company"),
)


def _typed_inline_field(item: str, lists: list, items: list[str], text: str) -> DesignField:
    f = _infer_field(item, lists, items)
    raw = item.strip()
    paren = re.search(r"\(([^)]*)\)", raw)
    label = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    low = raw.lower()
    for pat, rel in _INLINE_REL:
        if re.search(pat, low):
            return DesignField(string=label[:1].upper() + label[1:], ttype="many2one", relation=rel)
    if paren and re.fullmatch(r"(?i)\s*yes\s*/\s*no\s*", paren.group(1)):
        return DesignField(string=label[:1].upper() + label[1:], ttype="boolean")
    if paren and "/" in paren.group(1):
        opts = [o.strip() for o in paren.group(1).split("/") if o.strip()]
        return DesignField(string=label[:1].upper() + label[1:], ttype="selection",
                           selection=[[_snake(o), o] for o in opts])
    if re.search(r"photos?|image|picture", low):
        return DesignField(string=label[:1].upper() + label[1:], ttype="binary")
    if "%" in raw:
        return DesignField(string=label.replace("%", "(%)").strip()[:1].upper() + label.replace("%", "(%)").strip()[1:], ttype="float")
    if paren:  # "(days)", "(optional, for site jobs)": keep the type, drop the note from the label
        f.string = label[:1].upper() + label[1:]
    elif f.string:
        f.string = f.string[:1].upper() + f.string[1:]
    return f


def outline_from_brief(prompt: str, *, app_name: str = "", purpose: str = "") -> AppDesign:
    """Deterministic multi-model outline from markdown sections / numbered headings."""
    text = prompt or ""
    design = AppDesign(
        app_name=app_name, purpose=purpose, source="outline", model_budget=model_budget_for(text)
    )
    customer_brief = bool(re.search(r"(?i)\bcustomers?\b|\bclients?\b|\baccounts?\b", text))
    in_security = False
    for level, title, body in _sections(text):
        if level <= 2:
            in_security = bool(re.search(r"(?i)security|access|roles?|permissions?", title))
        elif in_security and level >= 3:
            design.security_groups.append(
                SecurityGroup(name=re.sub(r"[*`]", "", title).strip()[:60])
            )
            continue
        if level > 2 and not _CREATE_RE.search(body):
            continue
        created = bool(_CREATE_RE.search(body))
        intro = _LIST_INTRO_RE.search(body)
        if _HARD_SKIP_RE.search(title) or not (
            created or (intro and not _SOFT_SKIP_RE.search(title))
        ):
            continue
        label = _model_label(title, body)
        if not label or len(label) > 48:
            continue
        if re.fullmatch(r"(?i)configuration|settings?", label) and app_name:
            label = " ".join(app_name.split()[:2]) + " Configuration"
        lists = _all_lists(body)
        field_items = _bullets_after(body, intro.start()) if intro else []
        fields = [_infer_field(i, lists, field_items) for i in field_items if 0 < len(i) <= 48][:16]
        names = {_snake(f.string) for f in fields}
        if not field_items:
            if customer_brief and re.search(
                r"(?i)customer|client|account", f"{label} {body[:400]}"
            ):
                fields.append(
                    DesignField(string="Customer", ttype="many2one", relation="res.partner")
                )
            if re.search(r"(?i)score", label):
                fields.append(DesignField(string="Score", ttype="float"))
            bands = re.findall(
                r"(?m)^\s*[-*]\s*\d+\s*[\u2013-]\s*\d+\s*:\s*([A-Za-z][\w ]{1,20})\s*$", body
            )
            fields.append(
                DesignField(
                    string="Status",
                    ttype="selection",
                    selection=[[_snake(b), b.strip()] for b in bands],
                )
            )
            fields.append(DesignField(string="Notes", ttype="text"))
        elif (
            "customer" not in names
            and customer_brief
            and re.search(r"(?i)customer|renewal|plan|risk|history", label)
            and not re.search(r"(?i)config|setting", label)
        ):
            fields.insert(
                0, DesignField(string="Customer", ttype="many2one", relation="res.partner")
            )
        views = ["list", "form"]
        if any(f.ttype == "selection" and re.search(r"(?i)status|stage", f.string) for f in fields):
            views.append("kanban")
        if re.search(r"(?i)score$|history", label):
            views += ["graph", "pivot"]
        first = re.sub(r"\s+", " ", re.sub(r"[*`#]", "", body)).strip()
        design.new_models.append(
            DesignModel(
                name=_model_name(label),
                label=label,
                fields=fields,
                views=views,
                description=first[:200],
                why=f"Section '{re.sub(r'[*`]', '', title)}' of the brief describes it.",
            )
        )
    _inline_records(text, design)
    # Customer back-links on Contacts for the main customer-scoped models.
    linked = [m for m in design.new_models if any(f.relation == "res.partner" for f in m.fields)][
        :3
    ]
    if linked:
        design.stock_extensions.append(
            StockExtension(
                model="res.partner",
                reason="Customer-level links so the contact form shows its records.",
                fields=[
                    DesignField(
                        string=_plural(m.label),
                        ttype="one2many",
                        relation=m.name,
                        name=f"x_{m.name[2:]}_ids",
                    )
                    for m in linked
                ],
            )
        )
    for model, pat in _INTEGRATION_CUES:
        if pat.search(text):
            module, label = STOCK_APP_OF[model]
            design.integrations.append(
                Integration(app=label, module=module, models=[model], required=False)
            )
    if design.security_groups:
        names = [g.name for g in design.security_groups]
        for g in design.security_groups:
            low = g.name.lower()
            if "manager" in low:
                prefix = low.replace("manager", "").strip()
                g.implied = [
                    n
                    for n in names
                    if "user" in n.lower() and n.lower().replace("user", "").strip() == prefix
                ]
            elif "admin" in low:
                g.implied = [n for n in names if "manager" in n.lower()]
    return design


# ---------------------------------------------------------------- entry point


def build_app_design(
    prompt: str,
    *,
    grounding: Any = None,
    schema_packet: Any = None,
    use_llm: bool = True,
    title: str = "",
    purpose: str = "",
    resolved_answers: dict[str, str] | None = None,
    snapshot: Any = None,
) -> AppDesign | None:
    """LLM design + guardrails; outline fallback. None when the brief is one model."""
    budget = model_budget_for(prompt)
    outline = outline_from_brief(prompt, app_name=title, purpose=purpose)
    outcome: dict[str, Any] = {"status": "skipped", "reason": "ai_step_off"}
    contract: list[dict[str, Any]] = []
    contract_meta: dict[str, Any] = {"status": "skipped", "reason": "ai_step_off"}
    design: AppDesign | None = None
    live = snapshot if snapshot is not None and getattr(snapshot, "ok", False) else None
    from app.ai_conversation import studio_agent as _agent

    if use_llm and _agent.mode() == "agent":
        # AGENT MODE: one reasoning call + read-only Odoo tools on the owner's own words.
        # Its design then runs through the same code gates below (AI proposes, code authorizes).
        from app.ai_conversation.brief_checklist import source_brief as _src_a

        design, outcome = _agent.design_with_agent(
            _src_a(prompt), snapshot=live, grounding=grounding, schema_packet=schema_packet)
        contract = list(design.intent_contract) if design is not None else []
        contract_meta = {"status": "agent", "requirement_count": len(contract)}
        if design is not None:
            design.model_budget = budget
    elif use_llm:
        from app.llm_provider import get_llm_provider_for_tier

        provider = get_llm_provider_for_tier("fast")
        if provider is None:
            outcome = {"status": "skipped", "reason": "no_provider"}
            contract_meta = {"status": "skipped", "reason": "no_provider"}
        else:
            # The contract model is independently configurable. It can be the
            # fast provider when no contract-specific model is configured.
            contract_provider = get_llm_provider_for_tier("contract") or provider
            def _design_call(c: list[dict[str, Any]]) -> Any:
                return _call_llm(
                    provider,
                    design_user_prompt(prompt, grounding, schema_packet, budget=budget, title=title,
                                       intent_contract=c, snapshot=live),
                    design_system_prompt(grounding),
                    design_timeout_for(prompt),
                )

            contract, contract_meta = _call_intent_contract(
                contract_provider,
                prompt,
                grounding,
                # Frozen graph: under the checklist flag the design waits for authorization
                # (verifier + second look + capability + stock plan), never a preview contract.
                parallel=None if _bc_flag() else _design_call,
                answers=resolved_answers,
                verifier=get_llm_provider_for_tier("refine"),
                schema_packet=schema_packet,
                snapshot=live,
            )
            contract = promote_code_authorized_automations(contract, (contract_meta or {}).get("checklist"))
            g_key = json.dumps(grounding.as_dict() if grounding is not None else {}, sort_keys=True)
            contract_key = json.dumps(contract, ensure_ascii=False, sort_keys=True)
            snap_key = live.fingerprint() if live is not None else ""
            key = hashlib.sha256(
                f"{prompt}\n{g_key}\n{contract_key}\n{snap_key}\n{budget}\n{title}".encode()
            ).hexdigest()
            hit = _DESIGN_CACHE.get(key)
            system = design_system_prompt(grounding)
            early = contract_meta.pop("_parallel", None)
            if hit and time.monotonic() - hit[0] < _DESIGN_CACHE_TTL_S:
                parsed, outcome = hit[1], {"status": "called", "cached": True}
            elif early is not None and early[0]:
                # Batched with the verifier (one round trip instead of two in a row).
                parsed, outcome = early
                outcome = {**outcome, "batched_with_verifier": True}
                _DESIGN_CACHE[key] = (time.monotonic(), parsed)
            else:
                parsed, outcome = _call_llm(
                    provider,
                    design_user_prompt(
                        prompt,
                        grounding,
                        schema_packet,
                        budget=budget,
                        title=title,
                        intent_contract=contract,
                        snapshot=live,
                    ),
                    system,
                    design_timeout_for(prompt),
                )
                if parsed:
                    _DESIGN_CACHE[key] = (time.monotonic(), parsed)
            if parsed:
                design = AppDesign.from_dict(parsed)
                design.source = "llm"
                design.intent_contract = contract
                design, issues = validate_and_repair(
                    design, grounding, packet=schema_packet, prompt=prompt, budget=budget, snapshot=live
                )
                if issues and not outcome.get("cached") and not (_bc_flag() and _deterministic_ok(design, live)):
                    fixed, rmeta = _call_llm(
                        provider,
                        design_user_prompt(
                            prompt,
                            grounding,
                            schema_packet,
                            budget=budget,
                            title=title,
                            intent_contract=contract,
                            repair_issues=issues,
                            previous=parsed,
                            snapshot=live,
                        ),
                        system,
                        design_timeout_for(prompt),
                    )
                    outcome["repair_status"] = rmeta.get("status")
                    if fixed:
                        second = AppDesign.from_dict(fixed)
                        second.source = "llm_repaired"
                        second.intent_contract = contract
                        second, _ = validate_and_repair(
                            second,
                            grounding,
                            packet=schema_packet,
                            prompt=prompt,
                            budget=budget,
                            snapshot=live,
                        )
                        if len(second.new_models) >= len(design.new_models):
                            second.repair_issues = list(
                                dict.fromkeys(issues + second.repair_issues)
                            )
                            second.notes = list(dict.fromkeys(design.notes + second.notes))
                            design = second
                            design.source = "llm_repaired"
                            _DESIGN_CACHE[key] = (time.monotonic(), fixed)
    chk = (contract_meta.get("checklist") or {}) if isinstance(contract_meta, dict) else {}
    if design is not None and chk:
        from app.ai_conversation.brief_checklist import enforce_on_design

        design.left_out = list(chk.get("left_out") or [])
        design.checklist_choices = list(chk.get("choices") or [])
        design.integration_routes = list(chk.get("routes") or [])
        from app.ai_conversation.stock_routing import enforce_stock_first

        checks = [dict(c) for c in chk.get("stock_checks") or []]
        from app.ai_conversation import stock_routing as _sr

        _sr.align_checks_by_id(design, checks, snapshot)
        converted = enforce_stock_first(design, checks, snapshot)
        for c in checks:  # stock fits, a custom copy remains, and code found no verified reason
            if c["choice"] == "stock" and c.get("custom_kept") and not c.get("verified_reason"):
                c["custom_without_reason"] = True
        if converted:
            design.notes = list(dict.fromkeys(design.notes + converted))
            design, _ = validate_and_repair(design, grounding, packet=schema_packet, prompt=prompt,
                                            budget=budget, snapshot=snapshot)
        design.stock_checks = checks

        removed = enforce_on_design(design)
        if removed:
            chk["enforced_removals"] = removed
        from app.ai_conversation import design_scope as _ds

        auth_ids = {str(c.get("id")) for c in design.intent_contract if isinstance(c, dict) and c.get("id")}
        declined_any = any(r.get("status") == "cannot" for r in design.left_out) or any(
            c.get("decision") == "decline" for c in chk.get("capability") or [])
        declined_ids = {str(x) for r in design.left_out if r.get("status") == "cannot" for x in r.get("requirement_ids") or []}
        chk["scope"] = _ds.authorize(design, auth_ids, declined_any, declined_ids)
        design._auth = (auth_ids, declined_any, declined_ids)
        design._scoped = True  # code-authorized scope: no outline top-up may re-add models
    excluded = ((contract_meta.get("grounding") or {}).get("exclusions") or []) if isinstance(contract_meta, dict) else []
    if design is not None and excluded:
        # Must-not-appear: what the brief excludes (or defers) is not built, even if the design proposes it.
        from app.ai_conversation.clause_grounding import must_not_violations

        def _names(m: Any) -> str:
            return f"{getattr(m, 'label', '') or ''} {getattr(m, 'name', '') or ''}"

        hits = must_not_violations([_names(m) for m in design.new_models], excluded)
        drop = {h["name"] for h in hits}
        if drop:
            design.new_models = [m for m in design.new_models if _names(m) not in drop]
            design.notes = list(dict.fromkeys(design.notes + [
                f"Not part of this app: {h['excluded']} (your brief leaves it out)." for h in hits]))
            contract_meta["grounding"]["must_not_enforced"] = sorted(drop)
    level = logging.INFO if outcome.get("status") in {"called", "skipped"} else logging.WARNING
    outcome["intent_contract"] = contract_meta
    if live is not None:
        outcome["snapshot"] = {
            "major": live.major,
            "support": live.support,
            "models": len(live.models),
            "problems": live.problems[:5],
        }
    logger.log(level, "App design LLM outcome: %s", outcome)
    if design is not None and not getattr(design, "_scoped", False) and len(design.new_models) < max(
        MIN_DESIGN_MODELS, len(outline.new_models) // 2
    ):
        # Never shrink a big brief below its own sections: add what the design missed.
        design = _merge_outline(
            design, outline, grounding, packet=schema_packet, prompt=prompt, budget=budget, snapshot=live
        )
    if design is not None and design.source.startswith("llm") and not getattr(design, "_scoped", False):
        design = _cover_sections(
            design, outline, grounding, packet=schema_packet, prompt=prompt, snapshot=live
        )
    if design is None:
        design, _ = validate_and_repair(
            outline, grounding, packet=schema_packet, prompt=prompt, budget=budget, snapshot=live
        )
        design.fallback_reason = _fallback_reason(outcome)
        if use_llm and len(_HEADING_RE.findall(prompt or "")) >= 4:
            logger.error(
                "App design fell back to the outline for a %d-section brief: %s (%s)",
                len(_HEADING_RE.findall(prompt or "")),
                design.fallback_reason,
                outcome.get("error") or outcome.get("reason") or outcome.get("status"),
            )
    # Repair, never replace: fix list-as-text, add factor/action/alert records,
    # real links and form summary fields, then re-check with the guardrails.
    from app.ai_conversation.design_quality import strengthen_design

    sales_ok = not any(
        i.module == "sale" and i.status == "deferred" for i in design.integrations
    )
    keep_source, keep_reason = design.source, design.fallback_reason
    if strengthen_design(design, prompt, sales_ok=sales_ok):
        design, _ = validate_and_repair(
            design, grounding, packet=schema_packet, prompt=prompt, budget=design.model_budget, snapshot=live
        )
        design.source, design.fallback_reason = keep_source, keep_reason
    from app.ai_conversation.design_quality import complete_from_brief, dedupe_fields, ensure_jobs, scope_and_limits

    # Final pass after re-validation: no same-meaning duplicates, named jobs, roles, rules,
    # company scoping, asked-for views and alerts present.
    design.notes = list(dict.fromkeys(
        design.notes + dedupe_fields(design) + ensure_jobs(design, prompt) + complete_from_brief(design, prompt)
        + scope_and_limits(design, prompt)))
    from app.ai_conversation import orphan_repair as _orph

    if use_llm and _orph.mode() != "off":
        from app.llm_provider import get_llm_provider_for_tier as _tier

        outcome["orphan_repair"] = _orph.repair_step(design, prompt, grounding=grounding, schema_packet=schema_packet,
                                                     snapshot=live, provider=_tier("fast"))
    agent_assumptions = list(design.assumptions) if design.playback else []
    design.assumptions = agent_assumptions + [
        {"text": r["assumption"], "requirement_id": r.get("id", ""), "alternatives": r.get("alternatives") or []}
        for r in design.intent_contract if isinstance(r, dict) and r.get("assumption")]
    reg = ((contract_meta.get("checklist") or {}).get("register") or {}) if isinstance(contract_meta, dict) else {}
    design.assumptions += [  # decision register: shown, editable defaults ("choices we made")
        {"text": f"{d['item']}: {d['value']}", "requirement_id": d.get("id", ""), "alternatives": d.get("options") or []}
        for d in reg.get("defaults") or []]
    from app.ai_stock_catalog import suggest_stock_apps

    design.stock_suggestions = suggest_stock_apps(
        prompt, set(getattr(live, "modules", {}) or {}), str(getattr(live, "edition", "unknown") or "unknown"))
    if design.source.startswith("llm"):
        from app.llm_provider import get_llm_provider_for_tier

        # A separate configurable tier keeps review independent from the
        # extractor/designer call, while still allowing a lightweight provider.
        critic = get_llm_provider_for_tier("refine")
        if critic is None:
            critic_meta: dict[str, Any] = {"status": "skipped", "reason": "no_provider"}
        elif _bc_flag():
            # Off the blocking path: authorization already happened deterministically.
            critic_meta = {"status": "deferred", "reason": "off_blocking_path"}
        else:
            design.critic_findings, critic_meta = _call_critic(critic, prompt, design)
        outcome["critic"] = critic_meta
    if title and not design.app_name:
        design.app_name = title
    elif title and design.source == "outline":
        design.app_name = title
    design.purpose = design.purpose or purpose
    if getattr(design, "_auth", None) is not None:
        # Final gate: steps after scoping (support models, repairs) cannot add unapproved models.
        from app.ai_conversation import design_scope as _ds2

        outcome["scope_final"] = _ds2.authorize(design, *design._auth)
        # Real models and fields only: no copies of stock fields, automations on records
        # that exist, extension fields traced to approved requirements, short names.
        from app.ai_conversation.design_refresh import refresh_pass

        outcome["refresh_pass"] = refresh_pass(design, live)
        outcome["install_suggested"] = _ds2.ensure_install_suggestions(design, live, getattr(live, "major", None))
    design.llm_outcome = outcome
    if len(design.new_models) < MIN_DESIGN_MODELS:
        from app.ai_conversation import brief_checklist as bc

        if not bc.enabled() and not design.playback:  # agent mode: stock-only is a valid design
            return None
        # stock-only (extensions) and decline-only (everything declined/left out) are valid diagnoses
        if not (design.stock_extensions or design.left_out or design.integration_routes or design.integrations):
            return None
    return design


def _fallback_reason(outcome: dict[str, Any]) -> str:
    """Plain words for why the AI design did not come through."""
    st = str(outcome.get("status") or "")
    err = str(outcome.get("error") or outcome.get("reason") or "").lower()
    if outcome.get("reason") == "no_provider":
        return "No AI service is set up for App Studio."
    if outcome.get("reason") == "ai_step_off":
        return "The AI design step is turned off."
    if "vertex ai isn't switched on" in err:
        return "Vertex AI isn't switched on for this Google Cloud project."
    if "billing isn't turned on" in err or "requires billing" in err:
        return "Billing isn't turned on for this Google Cloud project."
    if "no longer offered" in err or "no longer available" in err:
        return "The AI model in settings is no longer offered by Google."
    if "429" in err or "quota" in err or "resource_exhausted" in err:
        return "The AI service is over its usage limit right now."
    if "503" in err or "high demand" in err or "unavailable" in err:
        return "The AI service is busy right now."
    if st == "timed_out":
        return "The AI design took too long."
    if "no design in reply" in err:
        return "The AI reply could not be read as an app design."
    return "The AI design call failed." if st == "failed" else ""


_GENERIC = {"customer", "health", "score", "management", "record", "config", "configuration", "line", "lines"}


def _core(m: DesignModel) -> set[str]:
    words = set(re.split(r"[^a-z0-9]+", f"{m.name[2:]} {m.label}".lower().replace("_", " ")))
    return {w.rstrip("s") for w in words if w and w not in _GENERIC}


def _cover_sections(
    design: AppDesign, outline: AppDesign, grounding: Any, *, packet: Any, prompt: str, snapshot: Any = None
) -> AppDesign:
    """A record the brief names by section but the AI did not design: add it, or say so."""
    have = [_core(m) for m in design.new_models]
    fields_blob = " ".join(f"{f.name} {f.string}" for m in design.new_models for f in m.fields).lower()
    added: list[str] = []
    for m in outline.new_models:
        core = _core(m)
        if not core or m.is_config or any(core & h for h in have):
            continue
        if len(design.new_models) >= max(design.model_budget, MAX_NEW_MODELS):
            design.notes.append(f"Not covered yet: '{m.label}' from the brief (model limit reached).")
            continue
        design.new_models.append(m)
        have.append(core)
        added.append(m.label)
    if not added:
        return design
    _ = fields_blob
    design.notes.append(
        "Added from the brief's sections the AI design missed (by checks): " + ", ".join(added) + "."
    )
    design.repair_issues.append("section_records_added: " + ", ".join(added))
    design, _ = validate_and_repair(
        design, grounding, packet=packet, prompt=prompt, budget=max(design.model_budget, len(design.new_models)),
        snapshot=snapshot,
    )
    return design


def _merge_outline(
    design: AppDesign,
    outline: AppDesign,
    grounding: Any,
    *,
    packet: Any,
    prompt: str,
    budget: int,
    snapshot: Any = None,
) -> AppDesign:
    stems = [m.name[2:] for m in design.new_models]
    added = []
    for m in outline.new_models:
        stem = m.name[2:]
        if any(stem == s or s in stem or stem in s for s in stems):
            continue
        design.new_models.append(m)
        stems.append(stem)
        added.append(m.label)
    if not added:
        return design
    for e in outline.stock_extensions:
        design.stock_extensions.append(e)
    design.notes.append(
        f"Added {len(added)} models from the brief's sections the design missed: {', '.join(added)}."
    )
    design, _ = validate_and_repair(
        design, grounding, packet=packet, prompt=prompt, budget=budget, snapshot=snapshot
    )
    return design


def design_must_do(design: AppDesign) -> list[str]:
    """Must-do rows in plain words: each new record with key fields, each extended app, roles, links."""
    from app.ai_grain import HOST_LABELS

    rows: list[str] = []
    for m in design.new_models:
        if m.suggested:
            continue  # suggestions are extras, never brief-named Must-do
        keys = [f.string for f in m.fields if f.name != "x_name" and f.string][:6]
        rows.append(f"New record: {m.label}" + (f" ({', '.join(keys)})" if keys else ""))
    for e in design.stock_extensions:
        label = HOST_LABELS.get(e.model, "")
        label = (label.title() if label.islower() else label) if label else "an existing app"
        names = [f.string for f in e.fields[:6] if f.string]
        if names:
            rows.append(f"Add to {label}: {', '.join(names)}")
    if design.security_groups:
        rows.append("Roles: " + ", ".join(g.name for g in design.security_groups))
    used = [i.app for i in design.integrations if i.status != "deferred"]
    later = [i.app for i in design.integrations if i.status == "deferred"]
    if used or later:
        rows.append(
            "Works with: "
            + (", ".join(used) if used else "no other apps")
            + (f"; {', '.join(later)} once installed" if later else "")
        )
    return rows


def design_technical_names(design: dict[str, Any] | None) -> set[str]:
    """Model and field names the design itself creates (live-schema filter allowlist)."""
    names: set[str] = set()
    if not isinstance(design, dict):
        return names
    for m in design.get("new_models") or []:
        names.add(str(m.get("name") or ""))
        names.update(str(f.get("name") or "") for f in m.get("fields") or [])
    for e in design.get("stock_extensions") or []:
        names.update(str(f.get("name") or "") for f in e.get("fields") or [])
    names.discard("")
    return names


__all__ = [
    "AppDesign",
    "DesignField",
    "DesignModel",
    "Integration",
    "SecurityGroup",
    "StockExtension",
    "build_app_design",
    "clear_design_cache",
    "design_must_do",
    "design_technical_names",
    "model_budget_for",
    "outline_from_brief",
    "validate_and_repair",
]


# ---------------------------------------------------------------- operator edits

_LANE_KEYS = (
    "delivery_lane",
    "delivery_lane_copy",
    "artifact_kind",
    "artifact_kind_copy",
    "online_blocked",
    "lane_note",
)


def apply_design_edits(
    base: dict[str, Any] | None, edited: Any, grounding: Any = None
) -> dict[str, Any] | None:
    """Accept an app_design edited on the diagnosis screen and re-run validate_and_repair.

    Operators may rename labels, remove models/fields and turn integrations off; they
    cannot grow the design past its budget. Without live grounding the integration
    status and Python lane labels from the confirmed design are kept (never upgraded).
    The intent contract always comes from the stored design, never from the client.
    """
    if not isinstance(edited, dict):
        return base
    design = AppDesign.from_dict(edited)
    if not design.new_models:
        return base
    prior = AppDesign.from_dict(base) if isinstance(base, dict) else None
    design.intent_contract = prior.intent_contract if prior else []
    design.source = (prior.source if prior else design.source) or "llm"
    design.llm_outcome = prior.llm_outcome if prior else design.llm_outcome
    budget = max(len(design.new_models), prior.model_budget if prior else 0) or MAX_NEW_MODELS
    off = [str(x) for x in _lst(edited.get("integrations_off")) if x]
    autos_off = {str(x) for x in _lst(edited.get("automations_off")) if x}
    if autos_off:
        # Operator removal is a deterministic decision on the stored contract, so the
        # automation is not rebuilt by validate_and_repair on this or any later save.
        removed = []
        for row in design.intent_contract:
            if isinstance(row, dict) and row.get("id") in autos_off:
                if row.get("decision") != "declined":
                    removed.append(str(row.get("subject") or row["id"]))
                row["decision"], row["operator_confirmed"] = "declined", True
        if removed:
            design.notes.append(f"Automation removed on the diagnosis screen: {', '.join(removed)}.")
    design.notes += apply_assumption_choices(design, edited.get("assumptions"))
    keep_int = {i.module or i.app: i for i in design.integrations}
    keep_py = {
        p.get("key") or _snake(p.get("label", "")): p
        for p in design.python_needed
        if isinstance(p, dict)
    }
    design, _issues = validate_and_repair(design, grounding, budget=min(budget, MAX_NEW_MODELS))
    if grounding is None:
        for item in design.integrations:
            old = keep_int.get(item.module or item.app)
            if old is not None and item.status == "unchecked":
                item.status, item.installed, item.note, item.required = (
                    old.status,
                    old.installed,
                    old.note,
                    old.required,
                )
        for p in design.python_needed:
            old = keep_py.get(p.get("key"))
            if old:
                p.update({k: old[k] for k in _LANE_KEYS if k in old})
    if off:
        design.integrations = [
            i for i in design.integrations if (i.module not in off and i.app not in off)
        ]
        design.notes.append(f"Turned off on the diagnosis screen: {', '.join(off)}.")
    design.notes.append("Edited on the diagnosis screen.")
    design.notes = list(dict.fromkeys(design.notes))
    return design.to_dict()


_LEAVE_OUT = re.compile(r"(?i)^(no\b|none|skip|leave (it )?out|don'?t|not needed|remove)")


def apply_assumption_choices(design: AppDesign, edited: Any) -> list[str]:
    """A choice changed under 'Choices we made for you' becomes a deterministic, operator-confirmed
    decision on the stored contract, so validate_and_repair rebuilds the design from it."""
    from app.ai_conversation.intent_contract import _AUTO_OPT, _MANUAL_OPT

    notes: list[str] = []
    by_id = {r.get("id"): r for r in design.intent_contract if isinstance(r, dict)}
    for a in _lst(edited):
        if not isinstance(a, dict):
            continue
        chosen = _s(a.get("chosen"))[:160]
        row = by_id.get(_s(a.get("requirement_id")))
        if not chosen or row is None:
            continue
        if _LEAVE_OUT.search(chosen):
            decision = "declined"
        elif _AUTO_OPT.search(chosen) and not _MANUAL_OPT.search(chosen) and row.get("automation") and row.get("target_model"):
            decision = "stock_automation"
        elif _MANUAL_OPT.search(chosen) and not _AUTO_OPT.search(chosen):
            decision = "metadata"
        else:
            decision = row.get("decision") or "metadata"  # a detail (who, which role): kept, and noted
        row.update(decision=decision, operator_confirmed=True, verified=decision != "clarify",
                   assumption=f"You chose: {chosen}", operator_choice=chosen)
        notes.append(f"Your choice for '{row.get('subject')}': {chosen}.")
    design.assumptions = [
        {"text": r["assumption"], "requirement_id": r.get("id", ""), "alternatives": r.get("alternatives") or [],
         **({"chosen": r["operator_choice"]} if r.get("operator_choice") else {})}
        for r in design.intent_contract if isinstance(r, dict) and r.get("assumption")]
    return notes


# ---------------------------------------------------------------- suggested supporting models

SUGGEST_SYSTEM = (
    "You suggest supporting models for ONE named Odoo record. Return JSON "
    '{"models": [{"kind": "lines|parties|documents", "label": str, "why": str, '
    '"fields": [{"name": str, "type": str, "string": str, "relation": str}]}]}. '
    "At most 3. Only what the main record obviously needs (one2many lines, parties, "
    "documents). Never copy stock apps (contacts, invoices, quotations, employees). "
    'Return {"models": []} when nothing is clearly needed.'
)
MAX_SUGGESTED = 3
_SUGGEST_KINDS = ("lines", "parties", "documents")
_IMPLIES = {
    "lines": re.compile(
        r"(?i)\b(?:lines?|line\s+items?|items|instal(?:l)?ments?|schedules?|coverages?|"
        r"entries|do\s+not\s+collapse|don'?t\s+collapse|one[\s-]+row)\b"
    ),
    "parties": re.compile(
        r"(?i)\b(?:parties|participants?|insured|beneficiar(?:y|ies)|members?|stakeholders?|"
        r"co-?owners?|signator(?:y|ies)|roles?)\b"
    ),
    "documents": re.compile(r"(?i)\b(?:documents?|attachments?|certificates?|scans?|evidence)\b"),
}


def _support_model(
    kind: str,
    main: DesignModel,
    *,
    label: str = "",
    why: str = "",
    fields: list[DesignField] | None = None,
) -> DesignModel:
    stem = main.name[2:] if main.name.startswith("x_") else main.name
    suffix = {"lines": "line", "parties": "party", "documents": "document"}[kind]
    base = main.label or _title(main.name)
    link = DesignField(
        name=f"x_{stem}_id", ttype="many2one", string=base, relation=main.name, required=True
    )
    default_fields = {
        "lines": [
            DesignField(name="x_name", ttype="char", string="Description", required=True),
            DesignField(name="x_sequence", ttype="integer", string="Sequence"),
            DesignField(name="x_amount", ttype="float", string="Amount"),
        ],
        "parties": [
            DesignField(
                name="x_partner_id",
                ttype="many2one",
                string="Contact",
                relation="res.partner",
                required=True,
            ),
            DesignField(
                name="x_role",
                ttype="selection",
                string="Role",
                selection=[["primary", "Primary"], ["other", "Other"]],
            ),
        ],
        "documents": [
            DesignField(name="x_name", ttype="char", string="Document", required=True),
            DesignField(name="x_attachment", ttype="binary", string="File"),
            DesignField(name="x_date", ttype="date", string="Date"),
        ],
    }[kind]
    rows = [
        f
        for f in (fields or default_fields)
        if not (f.ttype == "many2one" and _s(f.relation) == main.name)
    ]
    plural = {"lines": "Lines", "parties": "Parties", "documents": "Documents"}[kind]
    return DesignModel(
        name=f"x_{stem}_{suffix}"[:60],
        label=(label or f"{base} {suffix.title()}")[:60],
        why=(why or f"Suggested: {base} usually needs {plural.lower()}; remove it if you don't.")[
            :300
        ],
        fields=[link, *rows],
        views=["list", "form"],
        suggested=True,
    )


def deterministic_support(prompt: str, main: DesignModel) -> list[DesignModel]:
    """LLM-off fallback: only the supporting models the brief clearly implies."""
    main_words = set(re.findall(r"[a-z]+", (main.label or main.name).lower()))
    out: list[DesignModel] = []
    for kind in _SUGGEST_KINDS:
        hits = [m.group(0).lower() for m in _IMPLIES[kind].finditer(prompt or "")]
        if any(h not in main_words for h in hits):
            out.append(_support_model(kind, main))
    return out[:MAX_SUGGESTED]


def _llm_support(prompt: str, main: DesignModel) -> list[DesignModel] | None:
    from app.llm_provider import get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        return None
    user = (
        f"Brief:\n{(prompt or '')[:2000]}\n\nMain record: {main.label} ({main.name}). "
        f"Fields: {', '.join(f.string or f.name for f in main.fields)[:400]}"
    )
    data, _meta = _call_llm(provider, user, SUGGEST_SYSTEM, min(20.0, design_timeout_for(prompt)))
    if not isinstance(data, dict):
        return None
    out: list[DesignModel] = []
    for raw in _lst(data.get("models"))[:MAX_SUGGESTED]:
        if not isinstance(raw, dict):
            continue
        kind = _s(raw.get("kind")).lower()
        kind = next((k for k in _SUGGEST_KINDS if kind.startswith(k[:4])), "")
        if not kind or any(
            m.name.endswith({"lines": "_line", "parties": "_party", "documents": "_document"}[kind])
            for m in out
        ):
            continue
        # Ungrounded call: keep only scalar fields, so a suggestion can never point
        # at a stock model or field that the live database does not have.
        fields = [
            f
            for f in (_coerce_field(f) for f in _lst(raw.get("fields")))
            if f is not None and f.ttype not in {"many2one", "one2many", "many2many"}
        ]
        out.append(
            _support_model(
                kind,
                main,
                label=_s(raw.get("label")),
                why=_s(raw.get("why")),
                fields=fields or None,
            )
        )
    return out


def propose_supporting_models(
    prompt: str, main: DesignModel, *, use_llm: bool
) -> tuple[list[DesignModel], str]:
    """Up to 3 suggested supporting models for one named record: (models, source)."""
    if use_llm:
        try:
            got = _llm_support(prompt, main)
        except Exception:  # noqa: BLE001 — suggestions are optional
            got = None
        if got is not None:
            return got, "llm"
    return deterministic_support(prompt, main), "outline"


def named_residual_design(
    prompt: str, *, title: str = "", grounding: Any = None, use_llm: bool = False
) -> AppDesign | None:
    """Named main record + AI-suggested supporting models (each flagged ``suggested``)."""
    from app.ai_document_shape import naming_from_residual
    from app.ai_field_ir import fields_from_residual_brief

    display, slug = naming_from_residual(prompt)
    if not slug:
        return None
    name = slug if slug.startswith("x_") else f"x_{slug}"
    fields = [DesignField(name="x_name", ttype="char", string="Name", required=True)]
    try:
        for row in fields_from_residual_brief(prompt) or []:
            if isinstance(row, dict) and row.get("name") and row.get("name") != "x_name":
                fields.append(_coerce_field(row))
    except Exception:  # noqa: BLE001
        pass
    main = DesignModel(
        name=name,
        label=display or _title(name),
        fields=fields,
        why="The record your brief names.",
        views=["list", "form"],
    )
    support, source = propose_supporting_models(prompt, main, use_llm=use_llm)
    if not support:
        return None
    for sm in support:
        link = next(f for f in sm.fields if f.ttype == "many2one" and f.relation == main.name)
        plural = sm.name.rsplit("_", 1)[-1]
        main.fields.append(
            DesignField(
                name=f"x_{plural}_ids",
                ttype="one2many",
                string=_plural(sm.label),
                relation=sm.name,
                inverse_name=link.name,
            )
        )
    design = AppDesign(
        app_name=title or main.label,
        purpose="",
        new_models=[main, *support],
        source=source,
        notes=[f"{len(support)} supporting models suggested; remove any you don't need."],
    )
    design, _issues = validate_and_repair(design, grounding, prompt="", budget=1 + MAX_SUGGESTED)
    return design if len(design.new_models) >= 2 else None


def suggested_model_names(design: dict[str, Any] | None) -> set[str]:
    """Technical names of AI-suggested (not brief-named) models in a design dict."""
    if not isinstance(design, dict):
        return set()
    return {
        str(m.get("name"))
        for m in _lst(design.get("new_models"))
        if isinstance(m, dict) and m.get("suggested")
    }
