"""Odoo Expert ask pipeline — retrieval + grounding + ground-or-decline generation (EXP-3)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.expert.grounding import GroundingBundle, assemble_context
from app.expert.retrieval import RetrievedChunk, retrieve_expert_chunks
from app.llm_provider import LLMError, LLMProvider, get_llm_provider
from app.protected_enforcement import manifest_for_connection
from app.protected_modules import guardrail_prompt, protected_models_for, safe_alternative_for
from app.settings import settings

# COPY_GUIDE Expert empty-state + honest decline tone
DECLINE_LOW_CONFIDENCE = (
    "I don't have enough grounded sources to answer that confidently. "
    "Try rephrasing, connect an Odoo instance so I can filter docs to your version, "
    "or check the official Odoo documentation for your edition."
)

# Doc 8 §6 ground-or-decline discipline (structural + prompt)
GROUND_OR_DECLINE_RULES = """
GROUND OR DECLINE (mandatory — no exceptions):
1. Answer ONLY from the numbered SOURCE excerpts and INSTANCE GROUNDING below.
2. Do NOT answer from general parametric knowledge when sources are missing or thin.
3. If sources cannot support a confident answer, set answer_markdown to a short honest
   decline (do not invent steps).
4. Every factual paragraph in answer_markdown MUST include at least one citation marker
   like [1] referencing a source number from the excerpts list.
5. For protected tier-1 areas (accounting_core, payroll, payments, subscriptions, etc.):
   explain WHY the constraint exists, point to the legitimate link-only or module path,
   and our in-app bulk tools when relevant — never give bypass instructions.
6. Never give definitive legal, tax, or compliance conclusions — say what Odoo supports
   and recommend a qualified advisor for jurisdiction-specific rules.
""".strip()

EXPERT_PERSONA = (
    "You are the Odoo Expert — a careful advisor for Odoo Community customization via "
    "public ORM/RPC only. Tone: plain, confident, honest (COPY_GUIDE). Cite sources."
)

EXPERT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_markdown": {"type": "string"},
        "citation_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Source numbers [n] cited in the answer",
        },
        "caution_flags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["answer_markdown", "citation_ids"],
}

_EXPERT_TEMPERATURE = 0.15
_MAX_CONVERSATION_TURNS = 6
_MAX_CONVERSATION_CHARS = 2400
_RETRIEVAL_TOP_K = 8

_REASONING_HINTS = (
    "how do i",
    "walk me through",
    "step by step",
    "diagnose",
    "troubleshoot",
    "why does",
    "debug",
    "multi-step",
    "walkthrough",
)

_LEGAL_TAX_HINTS = (
    "legal advice",
    "tax advice",
    "compliance conclusion",
    "gdpr compliant",
    "definitely legal",
    "must pay tax",
    "file taxes as",
)

_TIER1_LOGIC_VERBS = re.compile(
    r"(?i)\b(automat(e|ion)|server action|write|mutate|post|validate|compute|"
    r"related_write|update_field|create.*logic)\b"
)


@dataclass
class ExpertCitation:
    source: str
    version: str
    breadcrumb: str
    chunk_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "version": self.version,
            "breadcrumb": self.breadcrumb,
            "chunk_id": self.chunk_id,
        }


@dataclass
class ExpertAskResult:
    answer_markdown: str
    citations: list[ExpertCitation] = field(default_factory=list)
    grounded: bool = False
    declined: bool = False
    suggested_tools: list[dict[str, Any]] = field(default_factory=list)
    caution_flags: list[str] = field(default_factory=list)
    retrieval_version: str | None = None
    model_used: str | None = None
    reasoning: bool = False
    uncited_warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_markdown": self.answer_markdown,
            "citations": [c.to_dict() for c in self.citations],
            "grounded": self.grounded,
            "declined": self.declined,
            "suggested_tools": list(self.suggested_tools),
            "caution_flags": list(self.caution_flags),
            "retrieval_version": self.retrieval_version,
            "model_used": self.model_used,
            "reasoning": self.reasoning,
            "uncited_warning": self.uncited_warning,
        }


def expert_assist_enabled() -> bool:
    return get_llm_provider() is not None


def classify_expert_intent(question: str, *, retrieval_chars: int) -> bool:
    """True → reasoning model + thinking; False → bulk/fast factual path."""
    q = (question or "").lower()
    if any(h in q for h in _REASONING_HINTS):
        return True
    if looks_like_error_question(q):
        return True
    if retrieval_chars > 4500:
        return True
    return False


def looks_like_error_question(text: str) -> bool:
    from app.expert.grounding import looks_like_rpc_error

    return looks_like_rpc_error(text)


def detect_legal_tax_question(question: str) -> bool:
    q = (question or "").lower()
    return any(h in q for h in _LEGAL_TAX_HINTS)


def detect_tier1_logic_request(
    question: str,
    manifest: dict[str, Any],
) -> tuple[str, str] | None:
    """Return (model, safe_alternative) when the question asks for tier-1 write logic."""
    from app.expert.grounding import extract_model_field_refs

    if not _TIER1_LOGIC_VERBS.search(question or ""):
        return None
    for model, _fld in extract_model_field_refs(question):
        if protected_models_for(manifest, model) == "tier_1":
            return model, safe_alternative_for(model)
    q = (question or "").lower()
    for token in ("account.move", "account.payment", "hr.payslip", "payment.transaction"):
        if token in q and protected_models_for(manifest, token) == "tier_1":
            return token, safe_alternative_for(token)
    return None


def _cap_conversation(conversation: list[dict[str, str]] | None) -> str:
    if not conversation:
        return ""
    turns = conversation[-_MAX_CONVERSATION_TURNS:]
    lines: list[str] = []
    total = 0
    for turn in turns:
        role = str(turn.get("role") or "user").strip()
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        line = f"{role.upper()}: {content}"
        if total + len(line) > _MAX_CONVERSATION_CHARS:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def _format_sources(chunks: list[RetrievedChunk]) -> tuple[str, dict[int, RetrievedChunk]]:
    lines: list[str] = []
    index_map: dict[int, RetrievedChunk] = {}
    for i, chunk in enumerate(chunks, start=1):
        index_map[i] = chunk
        lines.append(
            f"[{i}] ({chunk.source} / {chunk.version}) {chunk.breadcrumb}\n{chunk.text.strip()}"
        )
    return "\n\n".join(lines), index_map


def _format_grounding(bundle: GroundingBundle) -> str:
    parts: list[str] = []
    for key, text in (bundle.sections or {}).items():
        if text.strip():
            parts.append(f"## {key}\n{text.strip()}")
    if bundle.no_connection_note:
        parts.append(f"## note\n{bundle.no_connection_note}")
    return "\n\n".join(parts)


def _build_user_prompt(
    *,
    question: str,
    chunks: list[RetrievedChunk],
    bundle: GroundingBundle,
    conversation: list[dict[str, str]] | None,
    strict_citations: bool = False,
) -> str:
    sources_text, _ = _format_sources(chunks)
    grounding_text = _format_grounding(bundle)
    history = _cap_conversation(conversation)
    parts = [
        "QUESTION:",
        question.strip(),
        "",
        "INSTANCE GROUNDING:",
        grounding_text or "(none)",
        "",
        "SOURCE EXCERPTS (cite as [n]):",
        sources_text or "(none — decline if you cannot answer)",
    ]
    if history:
        parts.extend(["", "PRIOR TURNS:", history])
    if strict_citations:
        parts.extend(
            [
                "",
                "REMINDER: Every paragraph MUST include [n] citation markers. "
                "Return JSON with answer_markdown and citation_ids (source numbers used).",
            ]
        )
    parts.extend(
        [
            "",
            "Respond with JSON: "
            '{"answer_markdown":"...", "citation_ids":[1], "caution_flags":[]}',
        ]
    )
    return "\n".join(parts)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def _paragraphs_have_citations(answer: str) -> bool:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", answer.strip()) if b.strip()]
    if not blocks:
        return False
    for block in blocks:
        if not re.search(r"\[\d+\]", block):
            return False
    return True


def _citations_from_response(
    data: dict[str, Any],
    index_map: dict[int, RetrievedChunk],
) -> list[ExpertCitation]:
    cited: list[ExpertCitation] = []
    seen: set[str] = set()
    ids = data.get("citation_ids") or []
    if isinstance(ids, list):
        for raw_id in ids:
            try:
                idx = int(raw_id)
            except (TypeError, ValueError):
                continue
            chunk = index_map.get(idx)
            if chunk and chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                cited.append(
                    ExpertCitation(
                        source=chunk.source,
                        version=chunk.version,
                        breadcrumb=chunk.breadcrumb,
                        chunk_id=chunk.chunk_id,
                    )
                )
    return cited


def ask_expert(
    db: Session,
    *,
    question: str,
    connection_id: str | None = None,
    ui_context: dict[str, Any] | None = None,
    conversation: list[dict[str, str]] | None = None,
    provider: LLMProvider | None = None,
    client: Any | None = None,
) -> ExpertAskResult:
    """Run retrieval + grounding + generation with structural ground-or-decline."""
    q = (question or "").strip()
    if not q:
        return ExpertAskResult(
            answer_markdown="Ask a specific question about Odoo or this connection.",
            declined=True,
        )

    manifest: dict[str, Any] = {}
    if connection_id:
        from app.odoo_service import get_connection_or_404

        try:
            row = get_connection_or_404(db, connection_id)
            manifest = manifest_for_connection(row)
        except LookupError:
            pass

    tier1 = detect_tier1_logic_request(q, manifest) if manifest else None
    if tier1:
        model, alt = tier1
        return ExpertAskResult(
            answer_markdown=(
                f"I can't help generate business logic that mutates tier-1 model `{model}`. "
                f"{alt}\n\n"
                f"Protected-module policy (same as the draft generator): link-only relations "
                f"from custom models and Odoo's own methods via approved tools are the safe path."
            ),
            citations=[],
            grounded=bool(manifest),
            declined=False,
            caution_flags=[f"protected_tier_1:{model}", "pcm_consistent_refusal"],
            retrieval_version=_normalize_version_from_manifest(manifest),
        )

    bundle = assemble_context(
        db,
        connection_id=connection_id,
        ui_context=ui_context,
        question=q,
        client=client,
    )
    version = bundle.retrieval_version
    min_score = float(settings.ai_rag_min_score or 0.35)
    chunks = retrieve_expert_chunks(
        db,
        q,
        version=version,
        top_k=_RETRIEVAL_TOP_K,
        min_score=min_score,
    )

    suggested = list(bundle.suggested_tools or [])

    if not chunks:
        return ExpertAskResult(
            answer_markdown=DECLINE_LOW_CONFIDENCE,
            citations=[],
            grounded=False,
            declined=True,
            suggested_tools=suggested,
            caution_flags=["low_retrieval"],
            retrieval_version=version,
        )

    top_score = max(c.score for c in chunks)
    threshold = min_score
    if top_score < threshold:
        return ExpertAskResult(
            answer_markdown=DECLINE_LOW_CONFIDENCE,
            citations=[],
            grounded=False,
            declined=True,
            suggested_tools=suggested,
            caution_flags=["below_retrieval_threshold"],
            retrieval_version=version,
        )

    llm = provider if provider is not None else get_llm_provider()
    if llm is None:
        raise LLMError("Expert generation requires AI_ASSIST enabled", status_code=503)

    sources_text, index_map = _format_sources(chunks)
    retrieval_chars = len(sources_text)
    reasoning = classify_expert_intent(q, retrieval_chars=retrieval_chars)

    caution_flags: list[str] = []
    for pf in bundle.protected_flags or []:
        flag = f"protected_{pf.get('tier')}:{pf.get('model')}"
        if flag not in caution_flags:
            caution_flags.append(flag)
    if detect_legal_tax_question(q):
        caution_flags.append("legal_tax_deflection")

    system_parts = [
        EXPERT_PERSONA,
        GROUND_OR_DECLINE_RULES,
    ]
    if manifest:
        system_parts.append(guardrail_prompt(manifest))

    user_prompt = _build_user_prompt(
        question=q,
        chunks=chunks,
        bundle=bundle,
        conversation=conversation,
    )

    try:
        raw = llm.generate_json(
            user_prompt,
            system="\n\n".join(system_parts),
            reasoning=reasoning,
            temperature=_EXPERT_TEMPERATURE,
            format_schema=EXPERT_RESPONSE_SCHEMA,
        )
        data = _parse_llm_response(raw)
    except (json.JSONDecodeError, ValueError, LLMError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMError(str(exc), status_code=502) from exc

    answer = str(data.get("answer_markdown") or "").strip()
    cited = _citations_from_response(data, index_map)
    llm_flags = data.get("caution_flags") or []
    if isinstance(llm_flags, list):
        caution_flags.extend(str(f) for f in llm_flags if f)

    uncited = False
    if answer and not _paragraphs_have_citations(answer):
        strict_prompt = _build_user_prompt(
            question=q,
            chunks=chunks,
            bundle=bundle,
            conversation=conversation,
            strict_citations=True,
        )
        try:
            raw2 = llm.generate_json(
                strict_prompt,
                system="\n\n".join(system_parts),
                reasoning=reasoning,
                temperature=_EXPERT_TEMPERATURE,
                format_schema=EXPERT_RESPONSE_SCHEMA,
            )
            data2 = _parse_llm_response(raw2)
            answer2 = str(data2.get("answer_markdown") or "").strip()
            if answer2 and _paragraphs_have_citations(answer2):
                answer = answer2
                cited = _citations_from_response(data2, index_map)
            else:
                uncited = True
                caution_flags.append("uncited_paragraphs")
        except Exception:  # noqa: BLE001
            uncited = True
            caution_flags.append("uncited_paragraphs")

    return ExpertAskResult(
        answer_markdown=answer or DECLINE_LOW_CONFIDENCE,
        citations=cited,
        grounded=True,
        declined=not answer,
        suggested_tools=suggested,
        caution_flags=sorted(set(caution_flags)),
        retrieval_version=version,
        model_used=llm.name,
        reasoning=reasoning,
        uncited_warning=uncited,
    )


def _normalize_version_from_manifest(manifest: dict[str, Any]) -> str | None:
    ver = manifest.get("version")
    return str(ver) if ver else None


__all__ = [
    "DECLINE_LOW_CONFIDENCE",
    "ExpertAskResult",
    "ExpertCitation",
    "ask_expert",
    "classify_expert_intent",
    "detect_legal_tax_question",
    "detect_tier1_logic_request",
    "expert_assist_enabled",
]
