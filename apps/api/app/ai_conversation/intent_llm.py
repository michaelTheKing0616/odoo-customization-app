"""Optional LLM tie-break for intent routing — only when deterministic gate is ambiguous.

Hard blocks (pack_conflict, rental_ambiguity) are never overridden.
LLM may auto-clear pack_ambiguity or material_ambiguity when confidence is high.
"""

from __future__ import annotations

import contextvars

import json
import logging
import re
from typing import Any

from app.ai_conversation.intent_gate import IntentAssessment
from app.settings import settings

logger = logging.getLogger(__name__)

_INTENT_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "clear": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "low"]},
        "pack_id": {"type": "string"},
        "residual": {"type": "string"},
        "host_model": {"type": "string"},
        "inherit_existing": {"type": "boolean"},
        "needs_module": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": ["clear", "confidence", "rationale"],
}


def _coerce_host_model(raw: str) -> str | None:
    from app.ai_grain import HOST_ALIASES, HOST_LABELS

    text = (raw or "").strip()
    if not text:
        return None
    allowed = set(HOST_ALIASES.values())
    if text in allowed:
        return text
    low = text.lower().replace("_", " ").replace(".", " ").strip()
    if text.lower() in allowed:
        return text.lower()
    if low in HOST_ALIASES:
        return HOST_ALIASES[low]
    dotted = text.lower().strip()
    if dotted in allowed:
        return dotted
    for model, label in HOST_LABELS.items():
        if low == label.lower() or dotted == model:
            return model
    compact = re.sub(r"\s+", ".", low)
    if compact in allowed:
        return compact
    return None



# Session / connection override for Studio "Enrich Must-do with Flash" toggle.
# None = follow env (AI_INTENT_LLM). True/False = force on/off for this request.
_intent_llm_override: contextvars.ContextVar[bool | None] = contextvars.ContextVar(
    "intent_llm_override", default=None
)


def set_intent_llm_override(value: bool | None) -> contextvars.Token[bool | None]:
    """Force Flash AST enrich on/off for the current request; None clears to env."""
    return _intent_llm_override.set(value)


def reset_intent_llm_override(token: contextvars.Token[bool | None]) -> None:
    _intent_llm_override.reset(token)


def intent_llm_override() -> bool | None:
    return _intent_llm_override.get()


def intent_llm_enabled() -> bool:
    """Whether Flash/LLM may enrich Must-do AST.

    Precedence:
    1. Request/session override from Studio toggle (set_intent_llm_override)
    2. AI_INTENT_LLM env — off = always floor; on = always allow; auto = provider
    Product default when env unset: auto (same as settings default).
    """
    override = _intent_llm_override.get()
    if override is not None:
        return bool(override)
    mode = (settings.ai_intent_llm or "auto").strip().lower()
    if mode == "off":
        return False
    if mode == "on":
        return True
    from app.llm_provider import get_llm_provider_for_tier

    return get_llm_provider_for_tier("fast") is not None


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


def maybe_llm_refine_assessment(
    prompt: str,
    assessment: IntentAssessment,
    *,
    ranked: list[tuple[str, float]] | None = None,
) -> IntentAssessment:
    """Return assessment unchanged, or LLM-cleared when tie-break is high confidence."""
    if assessment.clear or not intent_llm_enabled():
        return assessment

    trigger = assessment.primary_trigger()
    if trigger in {"pack_conflict", "rental_ambiguity", "none"}:
        return assessment

    ranked = ranked or []
    pack_options = [pid for pid, _ in ranked[:4]]

    from app.llm_provider import LLMError, get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        return assessment

    system = (
        "You resolve Odoo app-builder intent ambiguity. "
        "Reply with JSON only. Never pick a vertical pack that contradicts explicit "
        "ticket/helpdesk/no-project language. Prefer thin transactional doc when brief is vague. "
        "If the operator is extending a stock document (Sales, invoices, delivery slip), "
        "set inherit_existing=true and host_model to an Odoo model like sale.order. "
        "Set needs_module=true when Python, QWeb, HTTP, OWL, markup lines, or withholding tax "
        "cannot be live metadata. Do not invent a new home-screen app for those."
    )
    user = (
        f"Operator prompt:\n{prompt}\n\n"
        f"Trigger: {trigger}\n"
        f"IR confidence: {assessment.ir_confidence}\n"
        f"Capability path: {assessment.capability_path}\n"
        f"Ranked packs: {pack_options}\n\n"
        "If intent is clear, set clear=true, confidence=high. "
        "Prefer host_model + inherit_existing over pack_id when this extends Sales/Invoices/"
        "Delivery. Set needs_module when Python/QWeb is required. "
        "If still ambiguous, set clear=false, confidence=low."
    )

    try:
        raw = provider.generate_json(
            user,
            system=system,
            timeout_s=45.0,
            temperature=0.0,
            format_schema=_INTENT_LLM_SCHEMA,
        )
    except LLMError as exc:
        logger.info("Intent LLM tie-break skipped: %s", exc)
        return assessment

    parsed = _parse_llm_json(raw)
    if not parsed or parsed.get("confidence") != "high" or not parsed.get("clear"):
        assessment.notes.append(
            f"LLM intent tie-break inconclusive: {parsed.get('rationale') if parsed else 'parse failed'}"
        )
        return assessment

    rationale = str(parsed.get("rationale") or "").strip()
    pack_id = str(parsed.get("pack_id") or "").strip()
    residual = str(parsed.get("residual") or "").strip()
    host_model = _coerce_host_model(str(parsed.get("host_model") or ""))
    inherit_existing = bool(parsed.get("inherit_existing"))
    needs_module = bool(parsed.get("needs_module"))

    if host_model and (inherit_existing or needs_module):
        assessment.clear = True
        assessment.triggers = []
        assessment.notes.append(
            f"LLM intent parse: host={host_model} inherit={inherit_existing} "
            f"module={needs_module} — {rationale}"
        )
        assessment.llm_resolved = {
            "host_model": host_model,
            "inherit_existing": inherit_existing,
            "needs_module": needs_module,
            "rationale": rationale,
        }
        return assessment

    if trigger == "pack_ambiguity" and pack_id and pack_id in pack_options:
        assessment.clear = True
        assessment.triggers = []
        assessment.notes.append(f"LLM intent tie-break: pack={pack_id} — {rationale}")
        assessment.llm_resolved = {"pack_id": pack_id, "rationale": rationale}
        return assessment

    if trigger == "material_ambiguity" and residual:
        assessment.clear = True
        assessment.triggers = []
        assessment.residual_text = residual
        assessment.notes.append(f"LLM intent tie-break: residual={residual} — {rationale}")
        assessment.llm_resolved = {"residual": residual, "rationale": rationale}
        return assessment

    if trigger == "low_ir_confidence" and pack_id == "transactional":
        assessment.clear = True
        assessment.triggers = []
        assessment.capability_path = "stock_first"
        assessment.notes.append(f"LLM intent tie-break: stock-first — {rationale}")
        assessment.llm_resolved = {"capability_path": "stock_first", "rationale": rationale}
        return assessment

    if trigger == "low_ir_confidence" and residual:
        assessment.clear = True
        assessment.triggers = []
        assessment.capability_path = "residual_app"
        assessment.residual_text = residual
        assessment.notes.append(f"LLM intent tie-break: residual={residual} — {rationale}")
        assessment.llm_resolved = {"residual": residual, "rationale": rationale}
        return assessment

    assessment.notes.append(f"LLM intent tie-break rejected: {rationale}")
    return assessment


__all__ = ["intent_llm_enabled", "maybe_llm_refine_assessment"]
