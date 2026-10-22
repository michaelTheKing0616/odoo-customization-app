"""Brief expansion: turn a short, vague request into a structured App Studio brief.

Non-technical users type things like "app to manage equipment rentals". The
pipeline's design step only runs for long or structured briefs, so a vague
request would otherwise get one thin record. This step asks the LLM to write
the structured brief a consultant would, in the shape the outline parser and
design step already understand (## sections, "Create a **X** model containing:"
lists, ### security groups).

Rules:
* Only vague, residual full_app briefs are expanded. Precise briefs, Prefer /
  inherit briefs, gold, custom code, refuse and stock-reuse briefs are untouched.
* The expansion must stay Live-Install safe (no Python / QWeb cues), still
  classify as residual full_app, and keep the person's own words.
* Never raises. Any failure returns None and the original brief is used.
* The person confirms through the existing Diagnosis step; the expansion and
  its assumptions are returned so the UI can show them.

Env:
* STUDIO_BRIEF_EXPAND=off disables the step (default on).
* STUDIO_BRIEF_EXPAND_TIER picks the provider tier (default "fast"). Point it
  at a stronger tier when you integrate a stronger model.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MIN_WORDS = 3
MIN_EXPANDED_CHARS = 400
MAX_EXPANDED_CHARS = 6000
MIN_WORD_OVERLAP = 0.6
EXPAND_TIMEOUT_S = 60.0
MAX_ATTEMPTS = 2

_PRECISE_RE = re.compile(
    r"(?i)\bmodel\s+with\b|\bwith\s+fields?\b|\bfields?\s*:|\bx_[a-z0-9_]+|"
    r"##\s*Diagnosis\s*\(locked\)|"
    r"\b(?:sale|account|res|hr|crm|stock|purchase|project|product|fleet|helpdesk|"
    r"calendar|mail)\.[a-z_]{3,}"
)
_INHERIT_RE = re.compile(
    r"(?i)\b(?:add|extend|inherit|prefer)\b[^.\n]{0,80}"
    r"\b(?:fields?|checkbox(?:es)?|buttons?|columns?|filters?)\b|"
    r"\bdo\s+not\s+(?:create|invent|build)\b"
)
_STOP = frozenset(
    {
        "that", "this", "with", "have", "from", "what", "want", "need", "would",
        "could", "like", "into", "some", "them", "they", "your", "about", "which",
        "their", "there", "will", "make", "build", "create", "app", "apps",
        "application", "manage", "track", "tool", "system", "please", "using",
    }
)


@dataclass
class BriefExpansion:
    original: str
    expanded: str
    assumptions: list[str] = field(default_factory=list)
    source: str = "llm"
    model: str | None = None
    latency_ms: int = 0
    attempts: int = 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        n = len(self.assumptions)
        tail = f" {n} assumption(s) to check." if n else ""
        return f"Your request was expanded into a structured brief.{tail}"


def _enabled() -> bool:
    return os.environ.get("STUDIO_BRIEF_EXPAND", "on").strip().lower() not in {
        "0", "off", "false", "no",
    }


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def _tokens(text: str) -> set[str]:
    return {
        t.rstrip("s")
        for t in re.findall(r"[a-z]{4,}", (text or "").lower())
        if t not in _STOP
    }


def not_vague_reason(prompt: str) -> str | None:
    """Why this brief should NOT be expanded, or None when it is vague enough."""
    from app.ai_conversation.grounding import brief_wants_llm

    text = (prompt or "").strip()
    if _words(text) < MIN_WORDS:
        return "too_short"
    if brief_wants_llm(text):
        return "already_structured"
    if _PRECISE_RE.search(text):
        return "precise_brief"
    if _INHERIT_RE.search(text):
        return "inherit_brief"
    return None


def _classify_ok(text: str) -> tuple[bool, str]:
    """True when the text is a residual full_app brief (never gold / custom code / refuse)."""
    try:
        from app.ai_generation_engine import classify_generation
        from app.ai_grain import classify_grain

        if classify_grain(text) != "full_app":
            return False, "grain_not_full_app"
        plan = classify_generation(text)
        if plan.capability != "residual_app" or plan.gold_artifact_id:
            return False, f"capability_{plan.capability}"
    except Exception:  # noqa: BLE001
        return False, "classify_failed"
    return True, ""


def _system_prompt() -> str:
    return (
        "You turn a short, vague request from a non-technical person into a complete, "
        "structured app brief for App Studio, which builds Odoo customizations. Reply with "
        'ONE JSON object only: {"brief": str, "assumptions": [str]}.\n\n'
        "Rules for the brief:\n"
        "- Keep everything the person said and never contradict it. Add only what a "
        "competent Odoo consultant would reasonably assume for that kind of business.\n"
        "- Write it as instructions, starting with: Build a <App Name> app. The goal of "
        "this app is to <purpose>.\n"
        "- Then one markdown section per record, each exactly in this form:\n"
        "## <Record Name>\n"
        "Create a **<Record Name>** model containing:\n"
        "- <Field> (<type or options in plain words>)\n"
        "  Use 3 to 8 records, never more than 10. Fewer rich records beat many hollow ones. "
        "Give each record 5 to 12 fields. Write selection options like "
        "Status (Draft, Confirmed, Done). Do not use the words view, security, access, "
        "dashboard, interface, workspace or section in a record name.\n"
        "- Link to existing Odoo records (Contact, User, Employee, Product, Sales Order) "
        "with a many2one field such as Customer (Contact). Never create a new record that "
        "duplicates contacts, invoices, quotations, leads or tickets.\n"
        "- Then these sections when they apply: ## Workflow (states and who moves them), "
        "## Views and menus (one top-level menu, sub-menus, list/form/kanban/calendar, "
        "useful filters), ## Connections (smart buttons on existing forms, status hints), "
        "## Security with a ### heading per group (for example Clerk and Manager) and one "
        "line on what each can do, ## Rules (non-goals such as no invoicing or accounting, "
        "and chatter on tracked records).\n"
        "- Everything must be deliverable with fields, views, menus, groups and simple "
        "automations. Never mention Python, code, QWeb, controllers, webhooks, APIs, cron "
        "scripts, computed-field code or PDF report templates.\n"
        "- Plain English. No technical x_ names. No JSON inside the brief.\n"
        "- Length 1500 to 4500 characters.\n\n"
        "assumptions: up to 6 short plain sentences naming choices the person did not "
        "state (for example: assumed daily rental rates; assumed a deposit per rental) so "
        "they can correct them."
    )


def _user_prompt(prompt: str, conn: Any, repair: list[str] | None) -> str:
    parts: list[str] = []
    try:
        from app.ai_conversation.grounding import (
            grounding_from_connection,
            grounding_prompt_block,
        )

        block = grounding_prompt_block(grounding_from_connection(conn, None))
        if block:
            parts.append(block)
    except Exception:  # noqa: BLE001
        pass
    if repair:
        parts.append(
            "Your previous brief was rejected: "
            + "; ".join(repair[:6])
            + ". Write a corrected brief that fixes this."
        )
    parts.append(f"The person's request:\n{prompt}")
    return "\n\n".join(parts)


def _parse(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw or None
    text = str(raw or "").strip()
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


def _validate(original: str, brief: str) -> list[str]:
    """Reasons the expanded brief is unusable (empty list = accepted)."""
    from app.ai_conversation.grounding import brief_wants_llm
    from app.ai_conversation.understand import brief_implies_option_a

    problems: list[str] = []
    if len(brief) < MIN_EXPANDED_CHARS:
        problems.append(f"too short ({len(brief)} chars; write at least {MIN_EXPANDED_CHARS})")
    if len(brief) > MAX_EXPANDED_CHARS:
        problems.append(f"too long ({len(brief)} chars; stay under {MAX_EXPANDED_CHARS})")
    if "## Diagnosis (locked)" in brief:
        problems.append("must not contain a Diagnosis block")
    if not brief_wants_llm(brief):
        problems.append("needs markdown ## sections")
    if brief_implies_option_a(brief):
        problems.append("mentions Python/QWeb/controller/webhook; use only fields, views, menus, groups")
    ok, why = _classify_ok(brief)
    if not ok:
        problems.append(f"does not read as one new app ({why})")
    want = _tokens(original)
    if want:
        overlap = len(want & _tokens(brief)) / len(want)
        if overlap < MIN_WORD_OVERLAP:
            problems.append("dropped words the person used")
    return problems


def _provider():
    from app.llm_provider import get_llm_provider_for_tier

    tier = os.environ.get("STUDIO_BRIEF_EXPAND_TIER", "fast").strip() or "fast"
    provider = None
    try:
        provider = get_llm_provider_for_tier(tier)
    except Exception:  # noqa: BLE001
        provider = None
    if provider is None and tier != "fast":
        try:
            provider = get_llm_provider_for_tier("fast")
        except Exception:  # noqa: BLE001
            provider = None
    return provider


def _model_name(provider: Any) -> str | None:
    for attr in ("model", "model_name", "name"):
        val = getattr(provider, attr, None)
        if isinstance(val, str) and val:
            return val
    return None


def _expand(prompt: str, conn: Any) -> BriefExpansion | None:
    from app.ai_conversation.intent_llm import intent_llm_enabled
    from app.llm_provider import LLMError

    if not _enabled():
        logger.info("Brief expansion skipped: disabled")
        return None
    text = (prompt or "").strip()
    reason = not_vague_reason(text)
    if reason:
        logger.info("Brief expansion skipped: %s", reason)
        return None
    if not intent_llm_enabled():
        logger.info("Brief expansion skipped: ai_step_off")
        return None
    ok, why = _classify_ok(text)
    if not ok:
        logger.info("Brief expansion skipped: %s", why)
        return None
    provider = _provider()
    if provider is None:
        logger.info("Brief expansion skipped: no_provider")
        return None

    started = time.monotonic()
    repair: list[str] | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = provider.generate_json(
                _user_prompt(text, conn, repair),
                system=_system_prompt(),
                timeout_s=EXPAND_TIMEOUT_S,
                temperature=0.3,
            )
        except (LLMError, TimeoutError) as exc:
            logger.warning("Brief expansion LLM call failed: %s", str(exc)[:200])
            return None
        parsed = _parse(raw)
        brief = str((parsed or {}).get("brief") or "").strip()
        if not brief:
            repair = ["the reply had no brief"]
            continue
        problems = _validate(text, brief)
        if not problems:
            assumptions = [
                str(a).strip()
                for a in ((parsed or {}).get("assumptions") or [])
                if isinstance(a, str) and a.strip()
            ][:6]
            latency = int((time.monotonic() - started) * 1000)
            logger.info(
                "Brief expansion accepted: %d -> %d chars, %d ms, attempt %d",
                len(text), len(brief), latency, attempt,
            )
            return BriefExpansion(
                original=text,
                expanded=brief,
                assumptions=assumptions,
                source="llm",
                model=_model_name(provider),
                latency_ms=latency,
                attempts=attempt,
            )
        logger.info("Brief expansion attempt %d rejected: %s", attempt, problems)
        repair = problems
    logger.info("Brief expansion gave up; using the original brief")
    return None


def maybe_expand_brief(prompt: str, *, conn: Any = None) -> BriefExpansion | None:
    """Expand a vague residual brief, or return None to keep the original. Never raises."""
    try:
        return _expand(prompt, conn)
    except Exception:  # noqa: BLE001
        logger.exception("Brief expansion failed; using the original brief")
        return None


__all__ = ["BriefExpansion", "maybe_expand_brief", "not_vague_reason"]