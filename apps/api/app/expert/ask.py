"""Odoo Expert ask pipeline — retrieval + grounding + ground-or-decline generation (EXP-3)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.expert.grounding import (
    GroundingBundle,
    assemble_context,
    looks_like_rpc_error,
    merge_question_with_pasted_error,
)
from app.expert.access_guidance import try_rule_based_access_guidance
from app.expert.answer_relevance import answer_matches_question, conversation_is_on_topic
from app.expert.error_diagnosis import try_rule_based_error_diagnosis
from app.expert.field_constraint_guidance import try_rule_based_required_field_guidance
from app.expert.instance_caveats import compose_dual_layer_answer
from app.expert.l10n_guidance import try_rule_based_l10n_guidance
from app.expert.knowledge_fallback import (
    try_rule_based_bulk_routing,
    try_rule_based_field_type_guidance,
    try_rule_based_protected_guidance,
)
from app.expert.model_lookup import try_rule_based_model_lookup
from app.expert.view_guidance import try_rule_based_view_guidance
from app.expert.view_mode_guidance import try_rule_based_view_mode_guidance
from app.expert.retrieval import RetrievedChunk, passes_generation_threshold, retrieve_expert_chunks
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
4. CITATION FORMAT (strict):
   - Use inline markers [1], [2], … matching SOURCE EXCERPT numbers exactly.
   - Every paragraph AND every list item MUST end with at least one [n] marker.
   - Place the marker at the end of the sentence or list item, before any trailing punctuation
     is fine: e.g. "Install Contacts for students [1]."
   - citation_ids in JSON must list every source number used in the answer.
5. For protected tier-1 areas (accounting_core, payroll, payments, subscriptions, etc.):
   explain WHY the constraint exists, point to the legitimate link-only or module path,
   and our in-app bulk tools when relevant — never give bypass instructions.
6. Never give definitive legal, tax, or compliance conclusions — say what Odoo supports
   and recommend a qualified advisor for jurisdiction-specific rules.
""".strip()

ERROR_DIAGNOSIS_RULES = """
ERROR DIAGNOSIS (when ERROR LOG, Fault, traceback, or validation error text is present):
1. Diagnose the specific error immediately — never ask the user to paste the error again.
2. Use INSTANCE GROUNDING error_diagnostics when present (model_missing, field_missing, suggestions).
3. For "Model not found" on x_* custom models during view save: the ir.model record must exist
   before the view validates — create it in Models & Fields or re-save from Designer (auto-create).
4. Give concrete remediation steps in numbered order with [n] citations from sources.
""".strip()

EXPERT_PERSONA = (
    "You are the Odoo Expert — a careful advisor for Odoo Community customization via "
    "public ORM/RPC only. Tone: plain, confident, honest (COPY_GUIDE). Cite sources. "
    "When vertical playbook excerpts match the question, prefer their stock-module lists "
    "and custom-model guidance over generic answers."
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
            "description": "Always return [] — the server adds caution flags; do not invent flags.",
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

# Vertical / module-stack questions — factual lists, not multi-step diagnostics.
_BULK_PLANNING_HINTS = (
    "what modules",
    "which modules",
    "what apps",
    "which apps",
    "modules would",
    "apps would",
    "modules do i need",
    "apps do i need",
    "build an odoo",
    "build a odoo",
    "recommended modules",
    "module stack",
    "apps to install",
    "modules to install",
    "for a school",
    "for school",
    "for a nonprofit",
    "for retail",
    "for manufacturing",
    "for logistics",
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

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")


@dataclass
class ExpertCitation:
    source: str
    version: str
    breadcrumb: str
    chunk_id: str
    source_index: int = 0

    def to_dict(self) -> dict[str, str | int]:
        return {
            "source": self.source,
            "version": self.version,
            "breadcrumb": self.breadcrumb,
            "chunk_id": self.chunk_id,
            "source_index": self.source_index,
        }


_INTERNAL_CAUTION_FLAGS = frozenset(
    {
        "citations_enforced",
        "reasoning_empty_retry_bulk",
        "answer_relevance_fallback",
        "below_retrieval_threshold",
        "answer_off_topic",
    }
)

_PUBLIC_CAUTION_FLAG_EXACT = frozenset(
    {
        "legal_tax_deflection",
        "low_retrieval",
        "instance_caveats",
        "pcm_consistent_refusal",
    }
)


def _sanitize_caution_flags(flags: list[str]) -> list[str]:
    """Drop internal telemetry and LLM guardrail spam; keep user-meaningful server flags."""
    out: list[str] = []
    for raw in flags:
        f = str(raw).strip()
        if not f or f in _INTERNAL_CAUTION_FLAGS:
            continue
        # LLMs sometimes echo prompt guardrails as caution_flags — reject that pattern.
        if f.startswith("no_"):
            continue
        if "reiterated" in f or "allowed_in_answers" in f or len(f) > 80:
            continue
        if (
            f.startswith("protected_")
            or f.startswith("rule_based_")
            or f in _PUBLIC_CAUTION_FLAG_EXACT
        ):
            if f not in out:
                out.append(f)
    return sorted(out)


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

    def __post_init__(self) -> None:
        self.caution_flags = _sanitize_caution_flags(self.caution_flags)

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
    del retrieval_chars  # kept for API stability; no longer used as a trigger
    q = (question or "").lower()
    if any(h in q for h in _BULK_PLANNING_HINTS):
        return False
    if any(h in q for h in _REASONING_HINTS):
        return True
    if looks_like_error_question(q):
        return True
    return False


def looks_like_error_question(text: str) -> bool:
    return looks_like_rpc_error(text)


def _expand_error_retrieval_query(question: str) -> str:
    """Bias retrieval toward remediation docs when the user pasted an RPC fault."""
    ql = question.lower()
    extra: list[str] = []
    if "model not found" in ql or "validating view" in ql:
        extra.extend(["ir.model", "custom model", "view validation", "designer"])
    if "accesserror" in ql or "access error" in ql:
        extra.extend(["access rights", "ir.model.access", "security"])
    if "fault" in ql or "traceback" in ql:
        extra.extend(["rpc error", "troubleshooting"])
    if not extra:
        return question
    return f"{question} {' '.join(extra)}"


def detect_legal_tax_question(question: str) -> bool:
    q = (question or "").lower()
    return any(h in q for h in _LEGAL_TAX_HINTS)


def detect_tier1_logic_request(
    question: str,
    manifest: dict[str, Any],
) -> tuple[str, str] | None:
    """Return (model, safe_alternative) when the question asks for tier-1 write logic."""
    from app.expert.grounding import _MODEL_RE, extract_model_field_refs

    qtext = question or ""
    if not _TIER1_LOGIC_VERBS.search(qtext):
        return None
    seen: set[str] = set()
    for model, _fld in extract_model_field_refs(qtext):
        if model in seen:
            continue
        seen.add(model)
        if protected_models_for(manifest, model) == "tier_1":
            return model, safe_alternative_for(model)
    for match in _MODEL_RE.finditer(qtext):
        model = match.group(1).lower()
        if model in seen:
            continue
        seen.add(model)
        if protected_models_for(manifest, model) == "tier_1":
            return model, safe_alternative_for(model)
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
        parts.extend(
            [
                "",
                "PRIOR TURNS (background only — may be unrelated; do NOT answer these unless the "
                "current QUESTION explicitly asks):",
                history,
            ]
        )
    if strict_citations:
        parts.extend(
            [
                "",
                "REMINDER — CITATION FORMAT:",
                "- Every paragraph AND every numbered/bulleted list item must end with [n].",
                '- Example: "Use xpath position=\\"after\\" on the anchor field [1]."',
                "- citation_ids must include every [n] used.",
                "Return JSON with answer_markdown and citation_ids (source numbers used).",
            ]
        )
    parts.extend(
        [
            "",
            "INSTRUCTION: Answer ONLY the QUESTION block above using SOURCE EXCERPTS and "
            "INSTANCE GROUNDING. Do not copy format examples or unrelated prior topics.",
            "",
            "Respond with JSON: "
            '{"answer_markdown":"...", "citation_ids":[1], "caution_flags":[]}',
            "caution_flags must always be an empty array — the server adds flags.",
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


def _split_citation_blocks(answer: str) -> list[str]:
    """Split answer into blocks that each require a [n] citation marker."""
    blocks: list[str] = []
    for para in re.split(r"\n\s*\n", answer.strip()):
        para = para.strip()
        if not para:
            continue
        lines = [ln for ln in para.split("\n") if ln.strip()]
        if lines and all(_LIST_ITEM_RE.match(ln) for ln in lines):
            blocks.extend(ln.strip() for ln in lines)
            continue
        if any(_LIST_ITEM_RE.match(ln) for ln in lines):
            buf: list[str] = []
            for ln in lines:
                if _LIST_ITEM_RE.match(ln):
                    if buf:
                        blocks.append(" ".join(buf).strip())
                        buf = []
                    blocks.append(ln.strip())
                else:
                    buf.append(ln.strip())
            if buf:
                blocks.append(" ".join(buf).strip())
        else:
            blocks.append(para)
    return blocks


def _blocks_have_citations(answer: str) -> bool:
    blocks = _split_citation_blocks(answer)
    if not blocks:
        return False
    return all(_CITATION_MARKER_RE.search(block) for block in blocks)


def _paragraphs_have_citations(answer: str) -> bool:
    """Back-compat alias — uses list-item-aware block splitting."""
    return _blocks_have_citations(answer)


def _extract_citation_ids_from_answer(answer: str, index_map: dict[int, RetrievedChunk]) -> list[int]:
    seen: list[int] = []
    for match in _CITATION_MARKER_RE.finditer(answer):
        idx = int(match.group(1))
        if idx in index_map and idx not in seen:
            seen.append(idx)
    return seen


def _primary_citation_id(
    answer: str,
    citation_ids: list[int],
    index_map: dict[int, RetrievedChunk],
) -> int:
    for match in _CITATION_MARKER_RE.finditer(answer):
        idx = int(match.group(1))
        if idx in index_map:
            return idx
    for raw_id in citation_ids:
        try:
            idx = int(raw_id)
        except (TypeError, ValueError):
            continue
        if idx in index_map:
            return idx
    return min(index_map.keys()) if index_map else 1


def _append_citation_marker(text: str, source_index: int) -> str:
    stripped = text.rstrip()
    if not stripped or _CITATION_MARKER_RE.search(stripped):
        return text
    return f"{stripped} [{source_index}]"


def _enforce_citation_markers(
    answer: str,
    *,
    index_map: dict[int, RetrievedChunk],
    citation_ids: list[int] | None = None,
) -> tuple[str, list[int]]:
    """Ensure every citation block ends with [n]; return normalized answer + ids."""
    primary = _primary_citation_id(answer, citation_ids or [], index_map)
    paragraphs = re.split(r"\n\s*\n", answer.strip())
    fixed_paras: list[str] = []

    for para in paragraphs:
        if not para.strip():
            continue
        lines = para.split("\n")
        content_lines = [ln for ln in lines if ln.strip()]
        if content_lines and all(_LIST_ITEM_RE.match(ln) for ln in content_lines):
            fixed_lines = [_append_citation_marker(ln, primary) for ln in lines]
            fixed_paras.append("\n".join(fixed_lines))
            continue
        if any(_LIST_ITEM_RE.match(ln) for ln in content_lines):
            fixed_lines: list[str] = []
            for ln in lines:
                if _LIST_ITEM_RE.match(ln):
                    fixed_lines.append(_append_citation_marker(ln, primary))
                else:
                    fixed_lines.append(ln)
            joined = "\n".join(fixed_lines)
            if not _blocks_have_citations(joined):
                fixed_paras.append(_append_citation_marker(joined, primary))
            else:
                fixed_paras.append(joined)
        elif not _CITATION_MARKER_RE.search(para):
            fixed_paras.append(_append_citation_marker(para, primary))
        else:
            fixed_paras.append(para)

    result = "\n\n".join(fixed_paras)
    ids = _extract_citation_ids_from_answer(result, index_map)
    if not ids and primary in index_map:
        ids = [primary]
    return result, ids


def _citations_from_response(
    data: dict[str, Any],
    index_map: dict[int, RetrievedChunk],
    *,
    answer: str | None = None,
) -> list[ExpertCitation]:
    cited: list[ExpertCitation] = []
    seen: set[str] = set()
    ids: list[int] = []
    if answer:
        ids.extend(_extract_citation_ids_from_answer(answer, index_map))
    raw_ids = data.get("citation_ids") or []
    if isinstance(raw_ids, list):
        for raw_id in raw_ids:
            try:
                idx = int(raw_id)
            except (TypeError, ValueError):
                continue
            if idx not in ids:
                ids.append(idx)
    for idx in ids:
        chunk = index_map.get(idx)
        if chunk and chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            cited.append(
                ExpertCitation(
                    source=chunk.source,
                    version=chunk.version,
                    breadcrumb=chunk.breadcrumb,
                    chunk_id=chunk.chunk_id,
                    source_index=idx,
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
    q = merge_question_with_pasted_error((question or "").strip(), ui_context)
    if not q:
        return ExpertAskResult(
            answer_markdown="Ask a specific question about Odoo or this connection.",
            declined=True,
        )

    effective_conversation = conversation
    if effective_conversation and not conversation_is_on_topic(q, effective_conversation):
        effective_conversation = []

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
        _expand_error_retrieval_query(q),
        version=version,
        top_k=_RETRIEVAL_TOP_K,
        min_score=min_score,
    )

    suggested = list(bundle.suggested_tools or [])

    def _rule_based_fallback() -> ExpertAskResult | None:
        for resolver in (
            try_rule_based_view_guidance,
            try_rule_based_view_mode_guidance,
            try_rule_based_l10n_guidance,
            try_rule_based_required_field_guidance,
            try_rule_based_error_diagnosis,
            try_rule_based_access_guidance,
            try_rule_based_model_lookup,
            try_rule_based_bulk_routing,
            try_rule_based_field_type_guidance,
            try_rule_based_protected_guidance,
        ):
            payload = resolver(q, bundle, connection_id=connection_id, client=client)
            if not payload:
                continue
            diag_flags = payload.get("caution_flags") or []
            if "rule_based_diagnosis" in diag_flags:
                answer = str(payload["answer_markdown"])
                caveat_flags: list[str] = []
            else:
                section = "Answer"
                answer, caveat_flags = compose_dual_layer_answer(
                    str(payload["answer_markdown"]),
                    bundle,
                    connection_id=connection_id,
                    section_title=section,
                )
            flags = list(diag_flags) + caveat_flags
            return ExpertAskResult(
                answer_markdown=answer,
                citations=[],
                grounded=bool(payload.get("grounded")),
                declined=False,
                suggested_tools=suggested,
                caution_flags=flags,
                retrieval_version=version,
            )
        return None

    if not chunks:
        ruled = _rule_based_fallback()
        if ruled:
            return ruled
        return ExpertAskResult(
            answer_markdown=DECLINE_LOW_CONFIDENCE,
            citations=[],
            grounded=False,
            declined=True,
            suggested_tools=suggested,
            caution_flags=["low_retrieval"],
            retrieval_version=version,
        )

    # High-confidence rule paths must win over weak/unreliable LLM output.
    _PRIORITY_RULE_FLAGS = frozenset(
        {
            "rule_based_view_guidance",
            "rule_based_view_mode_guidance",
            "rule_based_l10n_guidance",
            "rule_based_required_field_guidance",
            "rule_based_access_guidance",
            "rule_based_diagnosis",
        }
    )
    priority = _rule_based_fallback()
    if priority and any(
        flag in (priority.caution_flags or []) for flag in _PRIORITY_RULE_FLAGS
    ):
        return priority

    if not passes_generation_threshold(chunks, min_score=min_score):
        ruled = _rule_based_fallback()
        if ruled:
            return ruled
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
    if looks_like_error_question(q):
        system_parts.append(ERROR_DIAGNOSIS_RULES)
    if manifest:
        system_parts.append(guardrail_prompt(manifest))

    system_text = "\n\n".join(system_parts)

    def _generate(*, use_reasoning: bool, strict_citations: bool = False) -> dict[str, Any]:
        prompt = _build_user_prompt(
            question=q,
            chunks=chunks,
            bundle=bundle,
            conversation=effective_conversation,
            strict_citations=strict_citations,
        )
        raw = llm.generate_json(
            prompt,
            system=system_text,
            reasoning=use_reasoning,
            temperature=_EXPERT_TEMPERATURE,
            format_schema=EXPERT_RESPONSE_SCHEMA,
            timeout_s=settings.expert_llm_timeout_s,
        )
        return _parse_llm_response(raw)

    try:
        data = _generate(use_reasoning=reasoning)
    except (json.JSONDecodeError, ValueError, LLMError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMError(str(exc), status_code=502) from exc

    answer = str(data.get("answer_markdown") or "").strip()
    if not answer and reasoning:
        reasoning = False
        caution_flags.append("reasoning_empty_retry_bulk")
        try:
            data = _generate(use_reasoning=False)
            answer = str(data.get("answer_markdown") or "").strip()
        except (json.JSONDecodeError, ValueError, LLMError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc), status_code=502) from exc

    cited = _citations_from_response(data, index_map, answer=answer)
    # caution_flags come from server-side policy only — ignore LLM-provided flags.

    if answer and not _blocks_have_citations(answer):
        try:
            data2 = _generate(use_reasoning=reasoning, strict_citations=True)
            answer2 = str(data2.get("answer_markdown") or "").strip()
            if answer2 and _blocks_have_citations(answer2):
                answer = answer2
                data = data2
                cited = _citations_from_response(data2, index_map, answer=answer)
            else:
                answer, enforced_ids = _enforce_citation_markers(
                    answer2 or answer,
                    index_map=index_map,
                    citation_ids=data2.get("citation_ids") if answer2 else data.get("citation_ids"),
                )
                data = data2 if answer2 else data
                if enforced_ids:
                    data = {**data, "citation_ids": enforced_ids}
                cited = _citations_from_response(data, index_map, answer=answer)
                caution_flags.append("citations_enforced")
        except Exception:  # noqa: BLE001
            answer, enforced_ids = _enforce_citation_markers(
                answer,
                index_map=index_map,
                citation_ids=data.get("citation_ids"),
            )
            if enforced_ids:
                data = {**data, "citation_ids": enforced_ids}
            cited = _citations_from_response(data, index_map, answer=answer)
            caution_flags.append("citations_enforced")

    if answer and _blocks_have_citations(answer):
        merged_ids = _extract_citation_ids_from_answer(answer, index_map)
        if merged_ids:
            data = {**data, "citation_ids": merged_ids}
            cited = _citations_from_response(data, index_map, answer=answer)

    uncited_warning = bool(answer) and not _blocks_have_citations(answer)

    if answer and not answer_matches_question(q, answer):
        ruled = _rule_based_fallback()
        if ruled:
            flags = list(ruled.caution_flags or [])
            if "answer_relevance_fallback" not in flags:
                flags.append("answer_relevance_fallback")
            ruled.caution_flags = flags
            ruled.suggested_tools = suggested
            return ruled
        return ExpertAskResult(
            answer_markdown=DECLINE_LOW_CONFIDENCE,
            citations=[],
            grounded=False,
            declined=True,
            suggested_tools=suggested,
            caution_flags=["answer_off_topic"],
            retrieval_version=version,
        )

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
        uncited_warning=uncited_warning,
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
    "_blocks_have_citations",
    "_enforce_citation_markers",
    "_split_citation_blocks",
    "expert_assist_enabled",
]
