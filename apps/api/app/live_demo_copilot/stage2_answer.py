"""Stage 2 — Expert RAG adapted for live presenter brevity + confidence flags."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.expert.ask import ExpertAskResult, ask_expert, expert_assist_enabled
from app.llm_provider import LLMError, get_llm_provider


LIVE_UNCERTAIN_BANNER = (
    "Not fully certain — worth confirming before stating this to the client."
)


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
    latency_note: str = "expert_rag_live"


def _bulletize_markdown(md: str, *, max_bullets: int = 3) -> list[str]:
    lines: list[str] = []
    for raw in (md or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"^[-*•]\s+", "", s)
        s = re.sub(r"^\d+[.)]\s+", "", s)
        s = re.sub(r"^#+\s+", "", s)
        if len(s) < 8:
            continue
        s = re.sub(r"\s*\[\d+\]\s*", " ", s).strip()
        if s:
            lines.append(s)
    if lines:
        return lines[:max_bullets]
    parts = re.split(r"(?<=[.!?])\s+", (md or "").strip())
    out = [p.strip() for p in parts if len(p.strip()) >= 12]
    return out[:max_bullets]


def _compress_with_llm(question: str, answer_markdown: str) -> list[str] | None:
    provider = get_llm_provider()
    if provider is None:
        return None
    prompt = (
        "Compress the following Odoo Expert answer into exactly 2 or 3 ultra-short "
        "bullet points a presenter can read in under three seconds while still talking. "
        "No preamble or headings. Each bullet one line, max ~18 words.\n\n"
        f"QUESTION:\n{question}\n\nANSWER:\n{answer_markdown}\n"
    )
    try:
        text = provider.generate_text(prompt)
        return _bulletize_markdown(str(text), max_bullets=3) or None
    except Exception:  # noqa: BLE001
        return None


def live_confidence(result: ExpertAskResult) -> tuple[str, str | None]:
    """Adapt Document 8 ground-or-decline for live: surface low-confidence instead of silence."""
    if result.declined or not result.grounded or result.uncited_warning:
        return "low", LIVE_UNCERTAIN_BANNER
    if result.caution_flags:
        return "low", LIVE_UNCERTAIN_BANNER
    return "high", None


def generate_live_answer(
    db: Session,
    *,
    question: str,
    connection_id: str | None,
) -> LiveAnswer:
    if not expert_assist_enabled():
        return LiveAnswer(
            question=question,
            bullets=[
                "Expert AI is offline (enable AI_ASSIST).",
                "Note the question and follow up after the meeting.",
            ],
            confidence="low",
            confidence_flag=LIVE_UNCERTAIN_BANNER,
            grounded=False,
            declined=True,
            answer_markdown="",
        )

    try:
        result = ask_expert(db, question=question, connection_id=connection_id, conversation=[])
    except LLMError as exc:
        return LiveAnswer(
            question=question,
            bullets=[
                f"Could not generate a live answer ({exc}).",
                "Park the question for follow-up.",
            ],
            confidence="low",
            confidence_flag=LIVE_UNCERTAIN_BANNER,
            grounded=False,
            declined=True,
            answer_markdown="",
        )

    conf, flag = live_confidence(result)
    bullets = _compress_with_llm(question, result.answer_markdown) or _bulletize_markdown(
        result.answer_markdown
    )
    if not bullets:
        if result.declined:
            bullets = [
                "No solid grounded answer yet.",
                "Say you'll confirm and follow up.",
            ]
            conf, flag = "low", LIVE_UNCERTAIN_BANNER
        else:
            bullets = [result.answer_markdown.strip()[:160]]

    citations = []
    for c in result.citations[:5]:
        citations.append(
            {
                "source": c.source,
                "version": c.version,
                "breadcrumb": c.breadcrumb,
                "source_index": c.source_index,
            }
        )

    return LiveAnswer(
        question=question,
        bullets=bullets[:3],
        confidence=conf,
        confidence_flag=flag,
        grounded=result.grounded,
        declined=result.declined,
        citations=citations,
        answer_markdown=result.answer_markdown,
        model_used=result.model_used,
    )
