"""Canonical operator brief — structure any prompt without inventing facts.

Draft Studio and Job Autopilot both attach this IR so a marketing dump, a
one-liner, or a formal brief become the same slot layout. Empty slots stay
unknowns. Downstream must not fill them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.text_negation import has_positive_match, has_positive_needle, span_is_negated

_HEADING_RE = re.compile(
    r"(?im)^(#{1,3}\s*)?(description|features|benefits|screenshots|"
    r"how to configure(?: the module)?|goal|scope|brief)\s*:?\s*$"
)
_LABEL_GOAL_RE = re.compile(
    r"(?im)^(?:goal|objective|description)\s*[:\-]\s*(.+)$"
)
_INDUSTRY_LABEL_RE = re.compile(
    r"(?i)\b(?:domain|industry|vertical)\s+is\s+([^.\n]{3,80})"
)
_WE_ARE_RE = re.compile(
    r"(?i)\bwe are (?:a|an)\s+([^.\n]{3,80})"
)
_ACTOR_RE = re.compile(
    r"(?i)\b(cashier|accountant|salesperson|sales team|warehouse staff|"
    r"technician|manager|receptionist|nurse|doctor|lawyer|attorney|"
    r"producer|engineer|hr|operator|attendant|waiter|clerk)\b"
)
_STOCK_NAMED: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bpoint(?:s)? of sale\b|\bpos\b"), "point_of_sale"),
    (re.compile(r"(?i)\bquotations?\b|\bsales orders?\b"), "sale"),
    (re.compile(r"(?i)\binvoices?\b|\binvoicing\b"), "account"),
    (re.compile(r"(?i)\bemployees?\b|\btimesheets?\b|\bhr\b"), "hr"),
    (re.compile(r"(?i)\bcalendar\b|\bmeetings?\b"), "calendar"),
    (re.compile(r"(?i)\bleads?\b|\bcrm\b"), "crm"),
    # Standalone project/tasks — not the ``task`` suffix of negated ``project.task``.
    (re.compile(r"(?i)\bprojects?\b|(?<!project\.)\btasks?\b"), "project"),
    (re.compile(r"(?i)\bpurchase orders?\b|\bprocurement\b"), "purchase"),
    (re.compile(r"(?i)\binventory\b|\bwarehouses?\b"), "stock"),
)
_CONSTRAINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bper pos\.config\b"),
    re.compile(r"(?i)\bper point of sale\b"),
    re.compile(r"(?i)\b58\s*mm\b"),
    re.compile(r"(?i)\b80\s*mm\b"),
    re.compile(r"(?i)\bmulti-company is not required\b"),
    re.compile(r"(?i)\btwo offices of one company\b"),
    re.compile(r"(?i)\bsingle company\b"),
    re.compile(r"(?i)\bone company\b"),
    re.compile(r"(?i)\bnot multi-company\b"),
    re.compile(r"(?i)\bgift\s*/\s*basic receipt\b"),
    re.compile(r"(?i)\bstandard (?:odoo )?receipt keeps working\b"),
    re.compile(r"(?i)\bstandard odoo receipt remains the fallback\b"),
    re.compile(r"(?i)\bcustom residual is the [^.\n]+"),
)
_LEGAL_ENTITY_SPLIT_RE = re.compile(
    r"\b(multi[\s-]?compan(?:y|ies)|separate\s+legal\s+entit|"
    r"multiple\s+compan(?:y|ies)|several\s+compan(?:y|ies)|"
    r"group\s+of\s+compan(?:y|ies))\b",
    re.I,
)
# Capability stock_first = named path / residual none — NOT "Receipts stay stock POS"
# (that phrase only defers receipt Option A; see _DEFER_POS_PRINT_RE).
_STOCK_FIRST_PATH_RE = re.compile(
    r"(?i)("
    r"capability\s+path\s*:?\s*stock_first|"
    r"stock_first\s*\(\s*\+\s*later\s+option\s+a"
    r")"
)
_RESIDUAL_NONE_RE = re.compile(
    r"(?i)("
    r"custom\s+residual\s*:?\s*none|"
    r"residual\s*:?\s*none|"
    r"custom residual is none"
    r")"
)
_SECTION_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_CHROME_LINE_RE = re.compile(
    r"(?im)^(#{1,3}\s*)?operator\s+brief\s*:?\s*$"
)
_DROP_DETECTION_SECTIONS = (
    "out of scope",
    "unknowns",
    "unknowns — do not assume",
    "notes",
    "done bar",
    "capability path",
    # Locked Contract IR — grain/host/craft already on understanding_json; chrome
    # like "Craft smart button" / "Inherit existing form" must not flip classify_grain.
    "diagnosis",
    # Clarifications dump (incl. understanding_json) must never seed field IR /
    # Other Info labels. Locked Contract stays on session understanding_json.
    "clarifications",
    "clarifications (resolved)",
)
_KNOWN_STOCK_APPS = frozenset(
    {
        "point_of_sale",
        "sale",
        "account",
        "contacts",
        "mail",
        "hr",
        "stock",
        "purchase",
        "crm",
        "project",
        "calendar",
        "mrp",
        "website",
        "website_sale",
        "pos_hr",
        "hr_attendance",
        "product",
        "inventory",
    }
)
_COUNTRY_RE = re.compile(
    r"(?i)\b(nigeria|united states|united kingdom|germany|france|"
    r"kenya|ghana|india|canada|australia|south africa)\b"
)
_CITY_COUNTRY: dict[str, str] = {
    "accra": "Ghana",
    "kumasi": "Ghana",
    "lagos": "Nigeria",
    "abuja": "Nigeria",
    "nairobi": "Kenya",
    "mombasa": "Kenya",
}
_CITY_RE = re.compile(
    r"(?i)\b(" + "|".join(re.escape(c) for c in _CITY_COUNTRY) + r")\b"
)
_CURRENCY_RE = re.compile(
    r"(?i)\b(naira|ngn|usd|gbp|eur|cad|inr|aud|zar|kes|ghs)\b"
)
_COMPANY_LABEL_RE = re.compile(
    r"(?i)(?:client|company|business)\s+name\s*:\s*(.+)"
)
_NEGATED_NOUN_RE = re.compile(
    r"(?i)\b(?:not|no|never|without)\s+(?:a\s+|an\s+|the\s+)?"
    r"(?!and\b|or\b|not\b)([a-z][a-z-]{2,}(?:\s+(?!and\b|or\b|not\b)[a-z][a-z-]{2,}){0,2})"
)
_DO_NOT_ACTION_RE = re.compile(
    r"(?i)\b(?:do\s+not|don['’]t)\s+(?:create|clone|invent|build|add)\s+"
    r"(?:a\s+|an\s+|the\s+)?(.+?)(?:\.|$)"
)
# "I want a simple visitor log in Odoo" — requires "in odoo" so POS receipt asks stay Option A.
_I_WANT_RESIDUAL_RE = re.compile(
    r"(?i)\b(?:i want|we (?:want|need))\s+(?:a|an|the)?\s*"
    r"(?:simple|minimal|basic)?\s+"
    r"([^.:\n]{3,60}?)\s+in odoo"
)
_WANT_TICKETS_RE = re.compile(r"(?i)\bi want tickets?\b")
# "What we don't have is a simple loyalty punch card: …"
_DONT_HAVE_RESIDUAL_RE = re.compile(
    r"(?i)\bwhat we (?:don'?t|do not) have is\s+(?:a|an|the)?\s*"
    r"(?:simple|minimal|basic|lightweight|thin)?\s*"
    r"([^.:\n]{3,60}?)(?=\s*[:.]|\s*$)"
)
_ADD_ON_HOST_RE = re.compile(
    r"(?i)\badd(?: an| a)?\s+(.+?)\s+on\s+"
    r"(?:the\s+)?(?:stock\s+)?(?:customer\s+)?"
    r"(invoices?|bills?|orders?|leads?|contacts?)\b"
)
_DO_NOT_USE_PYTHON_RE = re.compile(
    r"(?i)\b(?:do\s+not|don['’]t)\s+use\s+python\b"
)
_SCOPE_VERB_NOUNS = frozenset({"create", "clone", "invent", "build", "add"})
_POS_RECEIPT_RE = re.compile(
    r"(?i)\b("
    r"pos\s+receipt|point of sale receipt|receipt designer|"
    r"receipt configurator|receipt design(?:s)?|thermal receipt|"
    r"receipt preview|paper width"
    r")\b"
)
_DEFER_POS_PRINT_RE = re.compile(
    r"(?i)("
    r"receipts?\s+stay\s+stock|"
    r"until\s+(?:a\s+)?separate\s+option\s+a|"
    r"later\s+option\s+a\s+only\s+if|"
    r"standard\s+(?:odoo\s+)?receipt\s+remains|"
    r"stock\s+pos\s+until"
    r")"
)
_CBN_BANK_RE = re.compile(r"(?i)\b(cbn|central\s+bank\s+of\s+nigeria)\b")
_CBN_RATE_RE = re.compile(
    r"(?i)\b("
    r"exchange\s+rates?|currency\s+rates?|fx\s+rates?|live\s+rates?|"
    r"automatic\s+currency|currency\s+provider|rate\s+service|"
    r"naira\s+per|usd\s*/\s*ngn|pull\s+(?:the\s+)?(?:cbn\s+)?rates?|"
    r"service\s+(?:dropdown|field|provider)"
    r")\b"
)
_PROCESS_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bquote|quotation|sales order\b"), "quote → invoice"),
    (re.compile(r"(?i)\bprint(?:ing)? (?:the )?receipt\b"), "POS print"),
    (re.compile(r"(?i)\bbooking|session\b"), "booking → invoice"),
    (re.compile(r"(?i)\bpurchase|rfq\b"), "procure"),
    (re.compile(r"(?i)\bpayslip|payroll\b"), "payroll"),
    (re.compile(r"(?i)\bmatter file|conflict check\b"), "matter workflow"),
)
# "custom residual is a visitor log" / "Residual is the punch card, not a new POS".
_EXPLICIT_RESIDUAL_RE = re.compile(
    r"(?i)\b(?:custom\s+)?residual\s*(?:is|:)\s*"
    r"(?:a|an|the|just|simply|only)?\s*"
    r"([^.,;\n]+?)(?=\s*(?:,|\.|$|\n|\(|—|-|\bnot\b))"
)


@dataclass
class OperatorBrief:
    source_prompt: str
    goal: str = ""
    industry: str = ""
    actors: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    stock_reuse: list[str] = field(default_factory=list)
    custom_residual: str = ""
    constraints: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    forbidden_bridges: list[str] = field(default_factory=list)
    country: str = ""
    unknowns: list[str] = field(default_factory=list)
    capability_path: str = "stock_first"
    capability_notes: list[str] = field(default_factory=list)
    # Hop-boundary provenance — Flash must treat inferred IR as a hint.
    residual_kind: str = "unstated"  # named | none | unstated
    capability_source: str = "inferred"  # explicit | inferred
    ir_confidence: str = "medium"  # high | medium | low
    formatted: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "industry": self.industry,
            "actors": list(self.actors),
            "processes": list(self.processes),
            "documents": list(self.documents),
            "stock_reuse": list(self.stock_reuse),
            "custom_residual": self.custom_residual,
            "constraints": list(self.constraints),
            "out_of_scope": list(self.out_of_scope),
            "forbidden_bridges": list(self.forbidden_bridges),
            "country": self.country,
            "unknowns": list(self.unknowns),
            "capability_path": self.capability_path,
            "capability_notes": list(self.capability_notes),
            "residual_kind": self.residual_kind,
            "capability_source": self.capability_source,
            "ir_confidence": self.ir_confidence,
            "formatted": self.formatted,
        }


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split `#` / `##` brief slots. Unstructured prompts stay one untitled block."""
    lines = (text or "").splitlines()
    sections: list[tuple[str, str]] = []
    title = ""
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if title or body:
            sections.append((title, body))

    for ln in lines:
        match = _SECTION_HEADING_RE.match(ln.strip())
        if match:
            flush()
            title = match.group(2).strip()
            buf = []
            continue
        buf.append(ln)
    flush()
    return sections


def _section_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower().split("—")[0]).strip(" :")


def _section_body(text: str, titles: tuple[str, ...]) -> str:
    want = {t.lower() for t in titles}
    for title, body in split_markdown_sections(text):
        key = _section_key(title)
        if key in want or any(key.startswith(t) for t in want):
            return body
    return ""


def intent_corpus(prompt: str) -> str:
    """Stated asks only — drop Out of scope / Unknowns / deferred Option A slots.

    Out-of-scope 'receipt designer' and 'later Option A only if we ask for QWeb'
    must not become a POS/PDF capability hit.
    """
    text = (prompt or "").strip()
    if not text:
        return ""
    sections = split_markdown_sections(text)
    if len(sections) <= 1 and not (sections and sections[0][0]):
        return text
    kept: list[str] = []
    for title, body in sections:
        key = _section_key(title)
        if any(key == d or key.startswith(d) for d in _DROP_DETECTION_SECTIONS):
            continue
        if _CHROME_LINE_RE.match(title):
            continue
        if body:
            kept.append(body)
    return "\n".join(kept).strip() or text


def is_explicit_stock_first(prompt: str) -> bool:
    return bool(_STOCK_FIRST_PATH_RE.search(prompt or ""))


def is_residual_none(prompt: str) -> bool:
    return stated_residual_kind(prompt)[0] == "none"


def stated_residual_kind(prompt: str) -> tuple[str, str]:
    """Return ('none'|'named'|'unstated', text). 'Do not invent x_invoice' is not none."""
    text = prompt or ""
    section = _section_body(text, ("custom residual",))
    if section:
        first = section.strip().split("\n")[0].strip().lstrip("-* ").strip()
        if re.match(r"(?i)^none\b", first):
            return "none", first
        if re.match(r"(?i)^named\s+in\s+brief\b", first):
            # Clarification placeholder — residual exists, title comes from the original brief.
            return "named", ""
        if first:
            return "named", first
    none_m = _RESIDUAL_NONE_RE.search(text)
    if none_m and not span_is_negated(text, none_m.start()):
        return "none", "None"
    residual_m = _EXPLICIT_RESIDUAL_RE.search(text)
    if residual_m and not span_is_negated(text, residual_m.start()):
        value = residual_m.group(1).strip()
        if re.match(r"(?i)^none\b", value):
            return "none", value
        if re.match(r"(?i)^named\s+in\s+brief\b", value):
            return "named", ""
        return "named", value
    want = _I_WANT_RESIDUAL_RE.search(text)
    if want and not span_is_negated(text, want.start()):
        noun = re.sub(r"\s+", " ", want.group(1)).strip(" .")
        if noun and noun.lower() not in {"app", "module", "system"}:
            return "named", noun
    tickets = _WANT_TICKETS_RE.search(text)
    if tickets and not span_is_negated(text, tickets.start()):
        return "named", "tickets"
    dont_have = _DONT_HAVE_RESIDUAL_RE.search(text)
    if dont_have and not span_is_negated(text, dont_have.start()):
        noun = re.sub(r"\s+", " ", dont_have.group(1)).strip(" .")
        if noun and noun.lower() not in {"app", "module", "system"}:
            return "named", noun
    add_on = _ADD_ON_HOST_RE.search(text)
    if add_on and not span_is_negated(text, add_on.start()):
        noun = re.sub(r"\s+", " ", add_on.group(1)).strip(" .")
        if noun and noun.lower() not in {"field", "fields", "column"}:
            return "named", noun
    return "unstated", ""


def wants_extension_grain(prompt: str) -> bool:
    """Inherit-and-wire / feature slice — not an empty stock_reuse seed."""
    from app.ai_grain import classify_grain

    corpus = intent_corpus(prompt) or (prompt or "")
    return classify_grain(corpus) in {"field_pack", "feature_slice"}


def wants_stock_reuse(prompt: str) -> bool:
    """Empty spec: residual none + stock_first, and not an inherit or POS-print ask.

    Leftover PDF/QWeb tokens in deferred slots must not starve this path.
    Named residual and “Add X on invoices” stay residual_app / field_pack.
    """
    kind, _ = stated_residual_kind(prompt)
    if kind != "none":
        return False
    if not is_explicit_stock_first(prompt):
        return False
    if wants_extension_grain(prompt):
        return False
    if is_pos_receipt_prompt(prompt):
        return False
    if is_cbn_currency_rates_prompt(prompt):
        return False
    return True


def is_cbn_currency_rates_prompt(prompt: str) -> bool:
    """True when the operator wants CBN live rates — not a Nigeria Autopilot brief."""
    text = intent_corpus(prompt or "") or (prompt or "")
    return has_positive_match(_CBN_BANK_RE, text) and has_positive_match(_CBN_RATE_RE, text)


def is_pos_receipt_prompt(prompt: str) -> bool:
    """True when the operator is asking for POS print/layout — not deferring it."""
    text = prompt or ""
    if is_explicit_stock_first(text) and stated_residual_kind(text)[0] == "none":
        if _DEFER_POS_PRINT_RE.search(text):
            return False
    return has_positive_match(_POS_RECEIPT_RE, intent_corpus(text))


def gazetteer_place_tokens() -> set[str]:
    """City names and resolved countries — identity slots, not domain nouns."""
    tokens = set(_CITY_COUNTRY.keys())
    tokens.update(v.lower() for v in _CITY_COUNTRY.values())
    return tokens


def has_named_stock_section(prompt: str) -> bool:
    """True when the operator filled ## Stock reuse (named) — exclusive install list."""
    return bool(_section_body(prompt or "", ("stock reuse (named)", "stock reuse")))


def capability_path_is_explicit(prompt: str) -> bool:
    """True when the operator filled ## Capability path (not regex-inferred alone)."""
    return bool(_section_body(prompt or "", ("capability path",)))


def ir_confidence_for(
    *,
    residual_kind: str,
    capability_source: str,
    capability_path: str,
) -> str:
    """high = stated residual/capability; low = inferred empty residual (Lagos failure class)."""
    if residual_kind == "named" and capability_path == "residual_app":
        return "high"
    if residual_kind == "none" and capability_source == "explicit":
        return "high"
    if residual_kind == "unstated" and capability_source == "inferred":
        return "low"
    if residual_kind == "named":
        return "high"
    return "medium"


def prompt_for_generators(raw: str, draft: dict[str, Any] | None = None) -> str:
    """Labeled original + upstream IR. Generators must not invent past the original."""
    blob = draft.get("_operator_brief") if isinstance(draft, dict) else None
    formatted = ""
    if isinstance(blob, dict):
        formatted = str(blob.get("formatted") or "").strip()
    if not formatted:
        formatted = build_operator_brief(raw).formatted
    original = (raw or "").strip()
    if not formatted:
        return (
            "## Original operator message (verbatim — authoritative)\n"
            f"{original}"
        )
    if formatted in original or original in formatted:
        # Structured brief paste — still label so Flash knows the source of truth.
        return (
            "## Original operator message (verbatim — authoritative)\n"
            f"{original}\n\n"
            "## Upstream operator brief IR (may be wrong — verify against original)\n"
            f"{formatted}"
        )
    return (
        "## Original operator message (verbatim — authoritative)\n"
        f"{original}\n\n"
        "## Upstream operator brief IR (may be wrong — verify against original)\n"
        f"{formatted}"
    )


def brief_llm_contract(prompt: str, *, draft: dict[str, Any] | None = None) -> str:
    """Hard contract Flash must obey — domain-agnostic, derived from the operator brief."""
    from app.ai_document_shape import THIN_SHAPES, classify_document_shape

    blob = draft.get("_operator_brief") if isinstance(draft, dict) else None
    if isinstance(blob, dict) and blob.get("formatted"):
        brief = blob
    else:
        brief = build_operator_brief(prompt).to_dict()
    shape = classify_document_shape(prompt, draft if isinstance(draft, dict) else None)
    unknowns = [str(u) for u in (brief.get("unknowns") or []) if u]
    oos = [str(x) for x in (brief.get("out_of_scope") or []) if x]
    forbidden = [str(x) for x in (brief.get("forbidden_bridges") or []) if x]
    residual = str(brief.get("custom_residual") or "").strip()
    capability = str(brief.get("capability_path") or "").strip()
    residual_kind = str(brief.get("residual_kind") or "").strip() or "unstated"
    capability_source = str(brief.get("capability_source") or "").strip() or "inferred"
    confidence = str(brief.get("ir_confidence") or "").strip() or ir_confidence_for(
        residual_kind=residual_kind,
        capability_source=capability_source,
        capability_path=capability,
    )
    lines = [
        "OPERATOR BRIEF CONTRACT (overrides ambition floors and CE-19 defaults when they conflict):",
        "- Source of truth: the Original operator message (verbatim). "
        "Upstream IR and this contract are hints — if they contradict a named residual "
        "in the original (\"Residual is …\", \"what we don't have is a simple …\", "
        "\"I want a simple … in Odoo\"), trust the original and emit that residual only.",
        f"- Document shape: {shape}",
        f"- Capability path: {capability or '(unstated)'} "
        f"(source={capability_source}, ir_confidence={confidence})",
        f"- Residual kind: {residual_kind}",
    ]
    if confidence == "low":
        lines.append(
            "- IR confidence is low (inferred). Do not invent a full ERP or hotel/PMS "
            "workspace. Prefer one residual document linked to named stock hosts."
        )
    if residual:
        lines.append(f"- Custom residual (only this x_* document): {residual}")
    if oos:
        lines.append("- Out of scope — do not implement: " + ", ".join(oos))
    if forbidden:
        lines.append("- Forbidden stock bridges — do not inherit: " + ", ".join(forbidden))
    if unknowns:
        lines.append("- Unknowns — omit, do not invent: " + "; ".join(unknowns))
        unk = " ".join(unknowns).lower()
        if "multi-company" in unk:
            lines.append(
                "  → no x_company_id, no res.company field, no multi-company ir.rule"
            )
        if "currency" in unk:
            lines.append("  → no x_currency_id")
        if "industry" in unk:
            lines.append(
                "  → do not dress this as hotel/PMS/CRM/restaurant unless the residual is that"
            )
        if "company name" in unk:
            lines.append("  → do not invent a company/legal name")
    if shape in THIN_SHAPES and not _LEGAL_ENTITY_SPLIT_RE.search(prompt or ""):
        lines.append(
            "- Thin shape: no x_company_id / multi-company ir.rule "
            "(the brief did not name a legal-entity split)."
        )
    if shape == "register":
        lines.extend(
            [
                "- Register: one header x_*; list+form; no kanban/workflow/x_status/x_code "
                "unless the brief named them.",
                "- Field strings copy the brief's words. Do not upgrade time in/out to "
                "check-in/check-out unless the brief used check-in.",
                "- At most one duration on_time if asked; clock the header datetime, not create_date.",
            ]
        )
    elif shape == "field_pack":
        lines.append(
            "- Field pack: inherit the named stock model only; no new root menu or parallel x_*."
        )
    elif shape == "stock_reuse":
        lines.append("- Stock reuse: models: [] — do not invent x_*.")
    elif shape == "catalog":
        lines.append(
            "- Catalog: master data only; no transactional workflow unless the brief named one."
        )
    lines.append(
        "- Do not add notes/company/currency/status/sequence fields the brief did not name."
    )
    lines.append(
        "- A reuse plan lists stock hosts to *link when used*, not fields to invent."
    )
    return "\n".join(lines)


def attach_operator_brief(draft: dict[str, Any], *, user_prompt: str = "") -> OperatorBrief:
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    brief = build_operator_brief(prompt)
    draft["_operator_brief"] = brief.to_dict()
    if prompt and not draft.get("_user_prompt"):
        draft["_user_prompt"] = prompt
    return brief


def build_operator_brief(prompt: str) -> OperatorBrief:
    text = (prompt or "").strip()
    brief = OperatorBrief(source_prompt=text)
    if not text:
        brief.unknowns = ["goal", "country", "currency", "company"]
        brief.formatted = _format_brief(brief)
        return brief

    brief.goal = _extract_goal(text)
    brief.industry = _extract_industry(text)
    detect = intent_corpus(text)
    brief.actors = _unique(_ACTOR_RE.findall(detect))
    brief.processes = _extract_processes(detect)
    brief.stock_reuse = _extract_stock(text)
    brief.constraints = _extract_constraints(text)
    brief.out_of_scope = _extract_out_of_scope(text)
    brief.forbidden_bridges = _forbidden_bridges(text, brief.out_of_scope)
    brief.country = _extract_country(text)
    residual_kind, residual_text = stated_residual_kind(text)
    if residual_kind == "named":
        brief.custom_residual = residual_text
        brief.documents.append(residual_text)
    elif residual_kind == "none":
        brief.custom_residual = residual_text or "None"

    pos_receipt = is_pos_receipt_prompt(text)
    from app.ai_capability_gaps import assess_capability_gaps

    assessment = assess_capability_gaps(text)
    option_a_ids = [g.id for g in assessment.gaps]
    if residual_kind == "named":
        brief.capability_path = "residual_app"
        brief.capability_notes.append(
            "Named residual — custom x_* only for that document. "
            "Do not clone invoice/partner/employee. Completeness ≠ Cert. Promote stays human."
        )
        if is_explicit_stock_first(text):
            brief.capability_notes.append(
                "Stock Community apps first where named; residual stays residual_app."
            )
    elif wants_stock_reuse(text) or (
        residual_kind == "none"
        and not pos_receipt
        and not assessment.primary_option_a
        and not wants_extension_grain(text)
    ):
        brief.capability_path = "stock_first"
        if residual_kind == "none" and not brief.custom_residual:
            brief.custom_residual = (
                "None. Do not invent x_receipt, x_pos_config, x_client, or x_invoice."
            )
        brief.capability_notes.append(
            "Stock-first: named Community apps cover this brief. No print/layout "
            "module until the operator explicitly asks. Autopilot RPC smoke is the done-bar."
        )
    elif pos_receipt:
        brief.capability_path = "option_a"
        brief.capability_notes.append(
            "POS receipt layout is Community `point_of_sale` OWL/QWeb (Option A: "
            "module → sandbox prove → human Promote). It is not a live `x_*` residual "
            "and not a back-office form designer."
        )
        if "point_of_sale" not in brief.stock_reuse:
            brief.stock_reuse.insert(0, "point_of_sale")
        if not brief.custom_residual:
            brief.custom_residual = (
                "None — do not invent x_receipt / x_pos_config. Stock POS stays the host."
            )
        if "POS print" not in brief.processes:
            brief.processes.append("POS print")
    elif assessment.primary_option_a:
        brief.capability_path = "option_a"
        brief.capability_notes.extend(
            f"{g.label}: {g.option_a_path}" for g in assessment.gaps
        )
    elif option_a_ids:
        brief.capability_path = "mixed"
        brief.capability_notes.extend(
            f"{g.label}: {g.option_a_path}" for g in assessment.gaps
        )
    else:
        brief.capability_path = (
            "residual_app" if residual_kind == "named" else "stock_first"
        )
        if brief.custom_residual:
            brief.capability_notes.append(
                "Custom residual only for what stock Community apps do not cover."
            )

    brief.residual_kind = residual_kind
    brief.capability_source = (
        "explicit" if capability_path_is_explicit(text) else "inferred"
    )
    brief.ir_confidence = ir_confidence_for(
        residual_kind=brief.residual_kind,
        capability_source=brief.capability_source,
        capability_path=brief.capability_path,
    )
    if brief.ir_confidence == "low":
        brief.capability_notes.append(
            "IR confidence low — verify Custom residual / Capability path against "
            "the Original operator message before inventing models."
        )

    brief.unknowns = _unknowns(text, brief)
    brief.formatted = _format_brief(brief)
    return brief


def _extract_goal(text: str) -> str:
    labeled = _LABEL_GOAL_RE.search(text)
    if labeled:
        return _clip_sentence(labeled.group(1))
    goal_body = _section_body(text, ("goal", "objective"))
    if goal_body:
        return _clip_sentence(goal_body)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        body = " ".join(
            ln
            for ln in lines
            if not _HEADING_RE.match(ln) and not _CHROME_LINE_RE.match(ln)
        )
        if len(body) >= 24:
            return _clip_sentence(body)
    return _clip_sentence(text)


def _clip_sentence(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    cleaned = re.sub(r"(?i)^#+\s*operator\s+brief\s+", "", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 280:
        return cleaned
    cut = cleaned[:280]
    if ". " in cut:
        return cut.rsplit(". ", 1)[0] + "."
    return cut.rstrip(" ,;") + "…"


def _extract_industry(text: str) -> str:
    if is_pos_receipt_prompt(text):
        labeled = _INDUSTRY_LABEL_RE.search(text) or _WE_ARE_RE.search(text)
        if labeled and not span_is_negated(text, labeled.start()):
            return labeled.group(1).strip(" .")
        return ""
    labeled = _INDUSTRY_LABEL_RE.search(text)
    if labeled and not span_is_negated(text, labeled.start()):
        return labeled.group(1).strip(" .")
    we = _WE_ARE_RE.search(text)
    if we and not span_is_negated(text, we.start()):
        return we.group(1).strip(" .")
    return ""


_COUNTRY_TITLE = {
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "south africa": "South Africa",
}


def _extract_country(text: str) -> str:
    """Stated country, or gazetteer lookup from a named city. Never invent."""
    raw = text or ""
    hit = next(
        (m for m in _COUNTRY_RE.finditer(raw) if not span_is_negated(raw, m.start())),
        None,
    )
    if hit:
        token = hit.group(1).strip().lower()
        return _COUNTRY_TITLE.get(token, token.title())
    city = next(
        (m for m in _CITY_RE.finditer(raw) if not span_is_negated(raw, m.start())),
        None,
    )
    if city:
        return _CITY_COUNTRY[city.group(1).lower()]
    return ""


def _extract_processes(text: str) -> list[str]:
    out: list[str] = []
    for pat, name in _PROCESS_HINTS:
        if has_positive_match(pat, text) and name not in out:
            out.append(name)
    return out


def _extract_stock(text: str) -> list[str]:
    named = _section_body(text, ("stock reuse (named)", "stock reuse"))
    out: list[str] = []
    if named:
        for token in re.findall(r"[a-z][a-z0-9_]*", named.lower()):
            app = "stock" if token == "inventory" else token
            if app in _KNOWN_STOCK_APPS and app not in out:
                out.append(app)
        if out:
            return out
    forbidden = set(_forbidden_bridges(text, _extract_out_of_scope(text)))
    for pat, app in _STOCK_NAMED:
        if app in forbidden:
            continue
        if has_positive_match(pat, text) and app not in out:
            out.append(app)
    return out


def _extract_constraints(text: str) -> list[str]:
    out: list[str] = []
    for pat in _CONSTRAINT_PATTERNS:
        match = next(
            (m for m in pat.finditer(text) if not span_is_negated(text, m.start())),
            None,
        )
        if match:
            out.append(re.sub(r"\s+", " ", match.group(0)).strip())
    return out


def _extract_out_of_scope(text: str) -> list[str]:
    section = _section_body(text, ("out of scope", "out of scope (stated)"))
    if section:
        out: list[str] = []
        for ln in section.splitlines():
            item = re.sub(r"^[-*]\s+", "", ln.strip()).strip()
            if len(item) >= 3 and item not in out:
                out.append(item)
        return out[:12]
    out = []
    for match in _DO_NOT_ACTION_RE.finditer(text):
        item = _normalize_scope_item(re.sub(r"\s+", " ", match.group(1)).strip(" .,"))
        if len(item) >= 3 and item not in out:
            out.append(item)
    for match in _NEGATED_NOUN_RE.finditer(text):
        noun = re.sub(r"\s+", " ", match.group(1)).strip(" .,")
        if len(noun) < 3:
            continue
        if noun.lower().split()[0] in _SCOPE_VERB_NOUNS:
            continue
        if noun.lower().startswith(("required", "touching", "code")):
            continue
        noun = _normalize_scope_item(noun)
        if noun and noun not in out:
            out.append(noun)
    if _DO_NOT_USE_PYTHON_RE.search(text) and "python" not in {x.lower() for x in out}:
        out.append("python")
    return out[:8]


def _normalize_scope_item(noun: str) -> str:
    low = re.sub(r"\s+", " ", (noun or "").strip().lower())
    if not low:
        return ""
    if re.search(r"\bcrm\b", low) or low == "crm":
        return "crm"
    if re.search(r"project\.task|project\.project|\bfake\s+project\b", low) or low in {
        "project",
        "projects",
        "project task",
        "project tasks",
    }:
        return "project"
    if "contact" in low:
        return "contacts_app"
    if re.search(r"\baccount\.move\b", low):
        return "account.move"
    # Keep clone/app wording stated — collapsing to "invoicing" forbids stock inherit
    if re.search(r"invoic", low) and any(
        tok in low for tok in ("app", "clone", "parallel", "second")
    ):
        return noun.strip()
    if re.search(r"invoic", low):
        return "invoicing"
    if low in {"python", "py"}:
        return "python"
    return noun.strip()


def _forbidden_bridges(text: str, out_of_scope: list[str]) -> list[str]:
    """Do-not-invent invoicing forbids account.move bridges — not stock_reuse account.

    "Do not create a new Invoices app" / "Do not clone account.move" while inheriting
    the stock invoice is field_pack — that must not add ``account`` here.
    """
    out: list[str] = []
    blob = " ".join(out_of_scope).lower()
    if "crm" in blob or re.search(r"(?i)\bnot\s+(?:a\s+|an\s+|the\s+)?crm\b", text or ""):
        out.append("crm")
    invent_invoice = bool(
        re.search(
            r"(?i)(?:do\s+not|don['’]t)\s+invent\s+invoic(?:e|es|ing)?\b",
            text or "",
        )
    )
    bare_invoicing = any(
        re.fullmatch(r"invoic(?:e|es|ing)?", str(x).strip().lower()) for x in out_of_scope
    )
    if invent_invoice or bare_invoicing:
        out.append("account")
    if "contacts_app" in blob:
        out.append("contacts")
    clone_project = bool(
        re.search(
            r"(?i)(?:do\s+not|don['’]t)\s+clone\s+project(?:\.task|\.project)?\b",
            text or "",
        )
        or re.search(r"(?i)\bfake\s+project\b", text or "")
    )
    if (
        "project" in blob
        or "project.task" in blob
        or clone_project
    ):
        out.append("project")
    if re.search(r"(?i)\bpurchase(?:\s+order)?\b", blob):
        out.append("purchase")
    # Dedup preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _unknowns(text: str, brief: OperatorBrief) -> list[str]:
    slots: list[str] = []
    if not brief.country and not has_positive_match(_COUNTRY_RE, text) and not _CITY_RE.search(
        text or ""
    ):
        slots.append("country")
    if not has_positive_match(_CURRENCY_RE, text):
        slots.append("currency")
    if not _COMPANY_LABEL_RE.search(text):
        slots.append("company name")
    if not brief.industry:
        slots.append("industry / vertical (beyond what was named)")
    constraint_blob = " ".join(brief.constraints).lower()
    if (
        "multi-company" not in constraint_blob
        and "one company" not in constraint_blob
        and "single company" not in constraint_blob
        and not has_positive_needle(text, "multi-company")
    ):
        slots.append("multi-company vs one company")
    return slots


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _format_brief(brief: OperatorBrief) -> str:
    def bullets(title: str, rows: list[str], empty: str = "(none stated)") -> str:
        body = "\n".join(f"- {r}" for r in rows) if rows else f"- {empty}"
        return f"## {title}\n{body}"

    residual = brief.custom_residual or (
        "(none stated — stock Community apps only; do not invent parallel x_* documents)"
    )
    unknown = (
        "\n".join(f"- {u}" for u in brief.unknowns)
        if brief.unknowns
        else "- (all requested identity slots were stated)"
    )
    notes = (
        "\n".join(f"- {n}" for n in brief.capability_notes)
        if brief.capability_notes
        else "- Stock-first residual; Completeness ≠ Certification; Promote stays human."
    )
    return "\n".join(
        [
            "# Operator brief",
            "## Goal",
            brief.goal or "(not stated)",
            "## Industry",
            brief.industry or "(not stated — do not assume)",
            "## Country",
            brief.country or "(not stated — do not assume)",
            bullets("Actors", brief.actors),
            bullets("Processes", brief.processes),
            bullets("Stock reuse (named)", brief.stock_reuse),
            "## Custom residual",
            residual,
            bullets("Constraints (stated)", brief.constraints),
            bullets("Out of scope (stated)", brief.out_of_scope),
            bullets(
                "Forbidden stock bridges",
                brief.forbidden_bridges,
                empty="(none stated)",
            ),
            "## Unknowns — do not assume",
            unknown,
            f"## Capability path\n{brief.capability_path}",
            f"## IR provenance\nresidual_kind={brief.residual_kind}; "
            f"capability_source={brief.capability_source}; "
            f"ir_confidence={brief.ir_confidence}",
            "## Notes",
            notes,
        ]
    )


__all__ = [
    "OperatorBrief",
    "attach_operator_brief",
    "brief_llm_contract",
    "build_operator_brief",
    "capability_path_is_explicit",
    "gazetteer_place_tokens",
    "intent_corpus",
    "ir_confidence_for",
    "is_explicit_stock_first",
    "is_cbn_currency_rates_prompt",
    "is_pos_receipt_prompt",
    "is_residual_none",
    "prompt_for_generators",
    "split_markdown_sections",
    "stated_residual_kind",
    "wants_extension_grain",
    "wants_stock_reuse",
    "has_named_stock_section",
]
