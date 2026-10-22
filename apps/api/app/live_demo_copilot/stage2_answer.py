"""Stage 2 — one model verdict, then a version/edition check. No second rewrite."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.llm_provider import LLMError, LLMProvider, get_llm_provider
from odoo_client.compat.version_table import DIFFERENCES

LIVE_UNCERTAIN_BANNER = (
    "Not fully certain — worth confirming before stating this to the client."
)

DEMO_MAJORS = frozenset({17, 18, 19, 20})
DEFAULT_DEMO_MAJOR = 20
DEFAULT_DEMO_EDITION = "community"

STOCK_COMMUNITY = "stock_community"
STOCK_ENTERPRISE_ONLY = "stock_enterprise_only"
STOCK_ONCE_INSTALLED = "stock_once_installed"
CUSTOMIZATION = "customization"
NOT_SURE = "not_sure"

VerdictKind = Literal[
    "stock_community",
    "stock_enterprise_only",
    "stock_once_installed",
    "customization",
    "not_sure",
]
EditionChoice = Literal["community", "enterprise", "both"]

_STOCK_VERDICTS = frozenset(
    {STOCK_COMMUNITY, STOCK_ENTERPRISE_ONLY, STOCK_ONCE_INSTALLED}
)
_CONNECT_ASK_RE = re.compile(
    r"connect (a |an |your |the )?(database|db|odoo instance|instance)",
    re.I,
)
_HOSTING_RE = re.compile(
    r"\b(odoo\.sh|odoo online|on-prem(?:ise)?s?|online hosting)\b",
    re.I,
)
_EDITION_ALIASES = {
    "community": "community",
    "ce": "community",
    "enterprise": "enterprise",
    "ee": "enterprise",
    "both": "both",
}
_VERDICT_ALIASES = {
    "stock_community": STOCK_COMMUNITY,
    "stock community": STOCK_COMMUNITY,
    "community stock": STOCK_COMMUNITY,
    "stock_enterprise_only": STOCK_ENTERPRISE_ONLY,
    "stock enterprise only": STOCK_ENTERPRISE_ONLY,
    "enterprise only": STOCK_ENTERPRISE_ONLY,
    "stock_once_installed": STOCK_ONCE_INSTALLED,
    "stock once that app is installed": STOCK_ONCE_INSTALLED,
    "stock once installed": STOCK_ONCE_INSTALLED,
    "customization": CUSTOMIZATION,
    "not_sure": NOT_SURE,
    "not sure": NOT_SURE,
}
# Edition table — apps, not a question catalog. The model still has to pick a verdict.
COMMUNITY_STOCK_APPS = {
    "sales": "Sales",
    "sale": "Sales",
    "settings": "Settings",
    "invoicing": "Invoicing",
    "accounting": "Invoicing",
    "crm": "CRM",
    "inventory": "Inventory",
    "purchase": "Purchase",
    "project": "Project",
    "pointofsale": "Point of Sale",
    "pos": "Point of Sale",
    "website": "Website",
    "manufacturing": "Manufacturing",
    "employees": "Employees",
    "contacts": "Contacts",
}
ENTERPRISE_ONLY_APPS = {
    "helpdesk": "Helpdesk",
    "sign": "Sign",
    "documents": "Documents",
    "approvals": "Approvals",
    "knowledge": "Knowledge",
    "studio": "Studio",
}
_PARTNER_API_RE = re.compile(
    r"bank'?s?\s+api|"
    r"post(?:ing)?\s+to\s+(?:our\s+|their\s+|a\s+)?bank|"
    r"external\s+(?:rest\s+)?api|"
    r"partner\s+api",
    re.I,
)
_CLAIM_STOP = frozenset(
    {
        "same",
        "verify",
        "present",
        "removed",
        "absent",
        "from",
        "base",
        "added",
        "preferred",
        "online",
        "only",
        "default",
        "legacy",
        "and",
        "the",
        "on",
        "in",
        "or",
        "to",
        "plus",
        "gone",
        "model",
        "override",
        "document",
        "level",
        "switch",
        "separate",
        "as",
        "of",
        "for",
    }
)

_PROPOSE_SYSTEM = (
    "You answer one consultant question: Can Odoo do this? "
    "There is no client database. Do not ask anyone to connect a database. "
    "Use the edition and version tables as facts, then pick a verdict. "
    "The tables are not a canned Q&A list. Return JSON only."
)


@dataclass(frozen=True)
class DemoProposal:
    verdict: VerdictKind
    app: str | None
    text: str
    claimed_names: tuple[str, ...]
    hosting_depends: bool


@dataclass
class LiveAnswer:
    question: str
    bullets: list[str]
    confidence: str  # high | low
    confidence_flag: str | None
    grounded: bool
    declined: bool
    citations: list[dict[str, Any]] = field(default_factory=list)
    answer_markdown: str = ""
    model_used: str | None = None
    latency_note: str = "demo_model_checked"
    verdict: str = NOT_SURE
    app_name: str | None = None
    demo_major: int = DEFAULT_DEMO_MAJOR
    demo_edition: str = DEFAULT_DEMO_EDITION
    check_passed: bool = True
    demo_label: str | None = None  # set by code from real Odoo lookups (db_grounding)


def parse_demo_major(major: int | str | None) -> int | None:
    """Return a demo major, or None when 16 and below (or unknown) are requested."""
    if major is None or major == "":
        return DEFAULT_DEMO_MAJOR
    try:
        value = int(str(major).strip().split(".", 1)[0])
    except (TypeError, ValueError):
        return None
    if value in DEMO_MAJORS:
        return value
    return None


def parse_demo_edition(edition: str | None) -> EditionChoice | None:
    if edition is None or str(edition).strip() == "":
        return DEFAULT_DEMO_EDITION
    key = str(edition).strip().casefold().replace("-", "_").replace(" ", "")
    if key in {"communityandenterprise", "enterpriseandcommunity"}:
        return "both"
    mapped = _EDITION_ALIASES.get(key)
    if mapped in {"community", "enterprise", "both"}:
        return mapped
    return None


def edition_label(edition: EditionChoice) -> str:
    if edition == "enterprise":
        return "Enterprise"
    if edition == "both":
        return "Community and Enterprise"
    return "Community"


def _tokenize_fact(fact: str) -> set[str]:
    tokens = {m.group(0) for m in re.finditer(r"[a-z][a-z0-9_.]*", (fact or "").lower())}
    return {tok for tok in tokens if tok not in _CLAIM_STOP}


def _is_claim_token(tok: str) -> bool:
    return "." in tok or tok.endswith("_id")


def present_version_claim_tokens(major: int) -> set[str]:
    """Field/menu tokens the version table lists as present for this major."""
    out: set[str] = set()
    for row in DIFFERENCES.values():
        if major not in row:
            continue
        fact = row[major]
        lowered = fact.strip().lower()
        if lowered == "removed" or lowered.startswith("absent"):
            continue
        out.update(tok for tok in _tokenize_fact(fact) if _is_claim_token(tok))
    return out


def all_version_claim_tokens() -> set[str]:
    out: set[str] = set()
    for row in DIFFERENCES.values():
        for fact in row.values():
            out.update(tok for tok in _tokenize_fact(fact) if _is_claim_token(tok))
    return out


def claimed_technical_names(text: str) -> set[str]:
    return {tok for tok in _tokenize_fact(text) if _is_claim_token(tok)}


def parse_verdict_kind(raw: object) -> VerdictKind | None:
    key = str(raw or "").strip().casefold().replace("-", " ")
    key = re.sub(r"\s+", " ", key)
    return _VERDICT_ALIASES.get(key) or _VERDICT_ALIASES.get(key.replace(" ", "_"))


def _app_key(app: str | None) -> str:
    return re.sub(r"[^a-z]+", "", (app or "").lower())


def _enterprise_only_hit(question: str, proposal: DemoProposal) -> str | None:
    app_key = _app_key(proposal.app)
    if app_key in ENTERPRISE_ONLY_APPS:
        return ENTERPRISE_ONLY_APPS[app_key]
    folded = f"{question} {proposal.text}".lower()
    for key, label in ENTERPRISE_ONLY_APPS.items():
        if re.search(rf"\b{re.escape(key)}\b", folded):
            return label
    return None


def _is_partner_api_claim(question: str, proposal: DemoProposal) -> bool:
    blob = f"{question} {proposal.text}"
    return bool(_PARTNER_API_RE.search(blob))


def _tables_prompt(major: int, edition: EditionChoice) -> str:
    ce = ", ".join(sorted(set(COMMUNITY_STOCK_APPS.values())))
    ee = ", ".join(sorted(set(ENTERPRISE_ONLY_APPS.values())))
    present = present_version_claim_tokens(major)
    absent = all_version_claim_tokens() - present
    present_s = ", ".join(sorted(present)) or "(none)"
    absent_s = ", ".join(sorted(absent)) or "(none)"
    return (
        f"EDITION TABLE ({edition_label(edition)} {major}):\n"
        f"- Community stock apps: {ce}.\n"
        f"- Enterprise-only apps: {ee}. Not Community stock. Not customization.\n"
        f"VERSION TABLE tokens present: {present_s}.\n"
        f"VERSION TABLE tokens absent on this major: {absent_s}.\n"
        "A partner bank or external API integration is never stock.\n"
    )


def _not_sure_text(edition: EditionChoice, major: int) -> str:
    ed = edition_label(edition)
    return (
        f"Not sure. "
        f"The version table does not list this as stock on Odoo {ed} {major}."
    )


def bullets_from_verdict(verdict_text: str, *, max_bullets: int = 3) -> list[str]:
    """Cut overlay bullets from the verdict. No second rewrite."""
    parts = re.split(r"(?<=[.!?])\s+", (verdict_text or "").strip())
    out = [p.strip() for p in parts if p.strip()]
    return out[:max_bullets]


def _scrub_connect_ask(text: str) -> str:
    if not text or not _CONNECT_ASK_RE.search(text):
        return text
    return _CONNECT_ASK_RE.sub("confirm against the version table", text)


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            loaded = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}


def parse_demo_proposal(raw: str) -> DemoProposal | None:
    data = _extract_json_object(raw)
    kind = parse_verdict_kind(data.get("verdict"))
    if kind is None:
        return None
    app = str(data.get("app") or data.get("app_name") or "").strip() or None
    text = str(data.get("text") or data.get("verdict_text") or "").strip()
    claimed_raw = data.get("claimed_names") or []
    claimed: list[str] = []
    if isinstance(claimed_raw, list):
        claimed = [str(n).strip() for n in claimed_raw if str(n).strip()]
    hosting = data.get("hosting_depends")
    return DemoProposal(
        verdict=kind,
        app=app,
        text=text,
        claimed_names=tuple(claimed),
        hosting_depends=bool(hosting),
    )


def check_demo_proposal(
    proposal: DemoProposal,
    *,
    major: int,
    edition: EditionChoice,
    question: str = "",
) -> str | None:
    """Return a fail reason, or None when the proposal may be shown.

    The tables do not invent a verdict. They refuse illegal claims.
    """
    kind = proposal.verdict
    app_key = _app_key(proposal.app)
    ee_hit = _enterprise_only_hit(question, proposal)
    community_target = edition in {"community", "both"}
    if ee_hit:
        if kind == STOCK_COMMUNITY:
            return "enterprise_app_as_community_stock"
        if kind == CUSTOMIZATION:
            return "enterprise_app_as_customization"
        if kind == STOCK_ONCE_INSTALLED and community_target:
            return "enterprise_app_as_community_stock"
    if kind in _STOCK_VERDICTS and _is_partner_api_claim(question, proposal):
        return "partner_api_not_stock"
    if kind == STOCK_COMMUNITY:
        if app_key in ENTERPRISE_ONLY_APPS:
            return "enterprise_app_as_community_stock"
        if not app_key:
            return "stock_requires_named_app"
    if kind == STOCK_ONCE_INSTALLED:
        if app_key in ENTERPRISE_ONLY_APPS and community_target:
            return "enterprise_app_as_community_stock"
        if not app_key:
            return "stock_requires_named_app"
    if kind == STOCK_ENTERPRISE_ONLY:
        if not app_key:
            return "stock_requires_named_app"
        if app_key in COMMUNITY_STOCK_APPS and app_key not in ENTERPRISE_ONLY_APPS:
            return "community_app_as_enterprise_only"
        if app_key not in ENTERPRISE_ONLY_APPS:
            return "unknown_enterprise_only_app"
    names = {n.lower() for n in proposal.claimed_names}
    names.update(claimed_technical_names(proposal.text))
    names.update(claimed_technical_names(proposal.app or ""))
    allowed = present_version_claim_tokens(major)
    known = all_version_claim_tokens()
    illegal = sorted(name for name in names if name in known and name not in allowed)
    if illegal:
        return "version_table_missing:" + ",".join(illegal)
    return None


def _ensure_edition_named(text: str, edition: EditionChoice, major: int) -> str:
    ed = edition_label(edition)
    if ed in text and str(major) in text:
        return text
    suffix = f" on Odoo {ed} {major}."
    body = text.rstrip()
    if not body.endswith("."):
        body += "."
    if ed in body:
        return body
    return body[: -1] + suffix


def _ensure_enterprise_not_in_community(text: str, kind: VerdictKind, app: str | None) -> str:
    if kind != STOCK_ENTERPRISE_ONLY:
        return text
    if re.search(r"not in Community", text, re.I):
        return text
    label = app or "This app"
    extra = f" {label} is not in Community."
    body = text.rstrip()
    if not body.endswith("."):
        body += "."
    return body + extra


def _finalize_checked_text(
    proposal: DemoProposal,
    *,
    major: int,
    edition: EditionChoice,
) -> str:
    text = proposal.text.strip()
    if not text:
        app = proposal.app or "the named app"
        if proposal.verdict == STOCK_COMMUNITY:
            text = f"Stock Community — {app}."
        elif proposal.verdict == STOCK_ENTERPRISE_ONLY:
            text = f"Stock Enterprise only — {app}."
        elif proposal.verdict == STOCK_ONCE_INSTALLED:
            text = f"Stock once {app} is installed."
        elif proposal.verdict == CUSTOMIZATION:
            text = "Customization."
        else:
            return _not_sure_text(edition, major)
    if not proposal.hosting_depends:
        text = _HOSTING_RE.sub("", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
    text = _ensure_enterprise_not_in_community(text, proposal.verdict, proposal.app)
    text = _ensure_edition_named(text, edition, major)
    return _scrub_connect_ask(text)


def _propose_system_and_prompt(
    question: str,
    *,
    major: int,
    edition: EditionChoice,
) -> tuple[str, str]:
    ed = edition_label(edition)
    prompt = (
        f"DEMO TARGET: Odoo {ed} {major}.\n"
        f"{_tables_prompt(major, edition)}"
        "Allowed verdicts: stock_community (name the app), "
        "stock_enterprise_only (name the app; it is not in Community), "
        "stock_once_installed, customization, not_sure.\n"
        "Name the edition in the text. Do not ask to connect a database. "
        "Name hosting only if the capability depends on it.\n"
        "JSON keys: verdict, app, text (two or three sentences), "
        "claimed_names (field or menu tokens), hosting_depends.\n\n"
        f"QUESTION: {question}\n"
    )
    return _PROPOSE_SYSTEM, prompt


def propose_demo_verdict(
    question: str,
    *,
    major: int,
    edition: EditionChoice,
    provider: LLMProvider,
) -> DemoProposal | None:
    """One model call. The caller must not call the model again to rewrite bullets."""
    from app.ai_client.guards import fence_untrusted

    # The client's words are data: fenced so the guards classify them and never follow them.
    system, prompt = _propose_system_and_prompt(fence_untrusted(question, "client_chat"), major=major, edition=edition)
    raw = provider.generate_json(prompt, system=system, temperature=0.1)
    return parse_demo_proposal(str(raw))


def _live_answer(
    *,
    question: str,
    kind: VerdictKind,
    text: str,
    app: str | None,
    major: int,
    edition: EditionChoice,
    model_used: str | None,
    check_passed: bool,
) -> LiveAnswer:
    text = _scrub_connect_ask(text)
    bullets = [_scrub_connect_ask(b) for b in bullets_from_verdict(text)]
    if not bullets:
        bullets = [text]
    unsure = kind == NOT_SURE
    return LiveAnswer(
        question=question,
        bullets=bullets[:3],
        confidence="low" if unsure else "high",
        confidence_flag=LIVE_UNCERTAIN_BANNER if unsure else None,
        grounded=not unsure,
        declined=unsure,
        answer_markdown=text,
        model_used=model_used,
        latency_note="demo_model_checked",
        verdict=kind,
        app_name=app if kind in _STOCK_VERDICTS else None,
        demo_major=major,
        demo_edition=edition,
        check_passed=check_passed,
    )


def generate_live_answer(
    db: Session | None = None,
    *,
    question: str,
    connection_id: str | None = None,
    major: int | str | None = DEFAULT_DEMO_MAJOR,
    edition: str | None = DEFAULT_DEMO_EDITION,
    hosting: str | None = None,
    provider: LLMProvider | None = None,
) -> LiveAnswer:
    """One model proposal, then the version/edition check. No client database."""
    _ = hosting
    parsed_major = parse_demo_major(major)
    parsed_edition = parse_demo_edition(edition)
    used_major = DEFAULT_DEMO_MAJOR if parsed_major is None else parsed_major
    used_edition: EditionChoice = (
        DEFAULT_DEMO_EDITION if parsed_edition is None else parsed_edition
    )
    if parsed_major is None or parsed_edition is None:
        return _live_answer(
            question=question,
            kind=NOT_SURE,
            text=_not_sure_text(used_edition, used_major),
            app=None,
            major=used_major,
            edition=used_edition,
            model_used=None,
            check_passed=False,
        )

    llm = provider if provider is not None else get_llm_provider()
    if llm is None:
        return _live_answer(
            question=question,
            kind=NOT_SURE,
            text=_not_sure_text(used_edition, used_major),
            app=None,
            major=used_major,
            edition=used_edition,
            model_used=None,
            check_passed=False,
        )

    try:
        proposal = propose_demo_verdict(
            question, major=used_major, edition=used_edition, provider=llm
        )
    except LLMError:
        proposal = None

    if proposal is None:
        return _live_answer(
            question=question,
            kind=NOT_SURE,
            text=_not_sure_text(used_edition, used_major),
            app=None,
            major=used_major,
            edition=used_edition,
            model_used=getattr(llm, "name", None),
            check_passed=False,
        )

    fail = check_demo_proposal(
        proposal,
        major=used_major,
        edition=used_edition,
        question=question,
    )
    if fail:
        return _live_answer(
            question=question,
            kind=NOT_SURE,
            text=_not_sure_text(used_edition, used_major),
            app=None,
            major=used_major,
            edition=used_edition,
            model_used=getattr(llm, "name", None),
            check_passed=False,
        )

    text = _finalize_checked_text(proposal, major=used_major, edition=used_edition)
    from app.live_demo_copilot.db_grounding import demo_label, installed_modules

    label = demo_label(proposal.verdict, proposal.app, installed_modules(db, connection_id))
    if label and not text.lower().startswith(label.lower()):
        text = f"{label}: {text}"
    out = _live_answer(
        question=question,
        kind=proposal.verdict,
        text=text,
        app=proposal.app,
        major=used_major,
        edition=used_edition,
        model_used=getattr(llm, "name", None),
        check_passed=True,
    )
    out.demo_label = label
    return out
