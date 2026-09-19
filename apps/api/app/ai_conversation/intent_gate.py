"""Intent resolution gate — compose existing brief/pack signals before generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TriggerKind = Literal[
    "none",
    "low_ir_confidence",
    "pack_ambiguity",
    "pack_conflict",
    "material_ambiguity",
    "rental_ambiguity",
]


@dataclass
class IntentAssessment:
    clear: bool
    triggers: list[TriggerKind] = field(default_factory=list)
    ir_confidence: str = "medium"
    capability_path: str = ""
    residual_kind: str = "unstated"
    residual_text: str = ""
    blocked_pack_id: str | None = None
    competing_pack_id: str | None = None
    pending: list[TriggerKind] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    llm_resolved: dict[str, Any] | None = None

    def primary_trigger(self) -> TriggerKind:
        return self.triggers[0] if self.triggers else "none"


def thin_document_brief(prompt: str) -> bool:
    """Purchase-request class: one named document with money/roles/approval.

    These are not stock-vs-custom or pack-choice questions. IR may still be
    'unstated' because the operator did not write ``Custom residual:``.
    """
    text = (prompt or "").strip()
    if not text:
        return False
    try:
        from app.ai_operator_brief import is_cbn_currency_rates_prompt, is_pos_receipt_prompt

        if is_cbn_currency_rates_prompt(text) or is_pos_receipt_prompt(text):
            return False
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_document_shape import classify_document_shape
        from app.ai_surface_invariants import extract_brief_slots

        shape = classify_document_shape(text)
        if shape not in {"transactional_header", "register"}:
            return False
        slots = extract_brief_slots(text)
        return bool(slots.people or slots.wants_money or slots.wants_approval)
    except Exception:  # noqa: BLE001
        return False


def _sort_triggers(triggers: list[TriggerKind]) -> list[TriggerKind]:
    order = [
        "pack_conflict",
        "rental_ambiguity",
        "pack_ambiguity",
        "material_ambiguity",
        "low_ir_confidence",
    ]
    return sorted(triggers, key=lambda t: order.index(t) if t in order else 99)


def assess_intent(prompt: str, *, resolved_answers: dict[str, str] | None = None) -> IntentAssessment:
    """Deterministic intent gate — no LLM call."""
    from app.ai_domain_coherence import PACK_AMBIGUOUS_TOP_SCORE, PACK_MERGE_MIN_MARGIN, rank_domain_packs
    from app.ai_domain_packs import load_domain_pack, retrieve_domain_pack_lexical, score_domain_pack
    from app.ai_generation_engine import _BARE_RENTAL_RE
    from app.ai_operator_brief import build_operator_brief, stated_residual_kind

    text = (prompt or "").strip()
    answers = dict(resolved_answers or {})
    brief = build_operator_brief(text)
    residual_kind, residual_text = stated_residual_kind(text)
    triggers: list[TriggerKind] = []
    notes: list[str] = []

    ranked = rank_domain_packs(text)
    lexical = retrieve_domain_pack_lexical(text)
    pack_clear = False
    if lexical:
        pack_id, pack, score = lexical
        from app.ai_domain_coherence import pack_conflicts_with_brief

        conflicts, conflict_notes = pack_conflicts_with_brief(text, pack_id, pack)
        if conflicts and f"pack_conflict:{pack_id}" not in answers:
            triggers.append("pack_conflict")
            notes.extend(conflict_notes)
            assessment = IntentAssessment(
                clear=False,
                triggers=_sort_triggers(triggers),
                ir_confidence=brief.ir_confidence,
                capability_path=brief.capability_path,
                residual_kind=residual_kind,
                residual_text=residual_text or brief.custom_residual,
                blocked_pack_id=pack_id,
                pending=triggers[1:],
                notes=notes,
            )
            return assessment
        if not conflicts and score >= 0.5:
            pack_clear = True

    if thin_document_brief(text):
        pack_clear = True
        notes.append("thin document brief — skip pack/stock clarification")

    try:
        from app.ai_generation_engine import classify_generation

        gen = classify_generation(text)
        if gen.gold_artifact_id or gen.capability in {
            "option_a_authored",
            "option_a_standalone",
        }:
            pack_clear = True
            notes.append("generation engine Option A — skip pack/stock clarification")
    except Exception:  # noqa: BLE001
        pass

    try:
        from app.ai_grain import classify_grain

        grain = classify_grain(text)
        # Inherit packs and clear residual apps both skip pack/stock chips.
        # Otherwise tiny pack noise (restaurant@0.04) asks "Where should this live?"
        # for briefs that already classify as full_app (Visitor Log, Asset Checkout).
        if grain in {"field_pack", "feature_slice", "full_app"}:
            pack_clear = True
            notes.append(
                f"{grain} — skip pack/stock clarification"
                if grain == "full_app"
                else f"{grain} inherit-on-stock — skip pack/stock clarification"
            )
    except Exception:  # noqa: BLE001
        pass

    if _BARE_RENTAL_RE.match(text) and "rental_domain" not in answers:
        triggers.append("rental_ambiguity")

    if len(ranked) >= 2:
        best_id, best_score = ranked[0]
        second_score = ranked[1][1]
        if (
            best_score < PACK_AMBIGUOUS_TOP_SCORE
            and best_score - second_score < PACK_MERGE_MIN_MARGIN
            and second_score > 0.0
            and "pack_choice" not in answers
            and not pack_clear
        ):
            triggers.append("pack_ambiguity")
            notes.append(
                f"Ambiguous pack fit: {best_id}@{best_score:.2f} vs {ranked[1][0]}@{second_score:.2f}"
            )

    if not triggers and residual_kind == "unstated" and brief.ir_confidence != "high":
        if any(tok in text.lower() for tok in ("ticket", "helpdesk", "support")) and "residual" not in answers:
            triggers.append("material_ambiguity")
            notes.append("Ticket/helpdesk intent — confirm custom residual document")

    if (
        brief.ir_confidence == "low"
        and "ir_confidence" not in answers
        and "pack_choice" not in answers
        and "pack_conflict" not in answers
        and not pack_clear
        and not triggers
    ):
        triggers.append("low_ir_confidence")
        notes.append("IR confidence low — confirm custom residual vs stock-first")

    triggers = _sort_triggers(triggers)

    clear = len(triggers) == 0
    primary = triggers[0] if triggers else None
    competing = None
    if primary == "pack_ambiguity" and len(ranked) >= 2:
        competing = ranked[1][0]

    blocked = None
    if primary == "pack_conflict" and lexical:
        blocked = lexical[0]

    result = IntentAssessment(
        clear=clear,
        triggers=triggers,
        ir_confidence=brief.ir_confidence,
        capability_path=brief.capability_path,
        residual_kind=residual_kind,
        residual_text=residual_text or brief.custom_residual,
        blocked_pack_id=blocked,
        competing_pack_id=competing,
        pending=triggers[1:],
        notes=notes,
    )
    from app.ai_conversation.intent_llm import maybe_llm_refine_assessment

    return maybe_llm_refine_assessment(text, result, ranked=ranked)


def should_block_generation(assessment: IntentAssessment) -> bool:
    """True when generation must not start until clarification is resolved."""
    return not assessment.clear


def session_already_admitted(status: str) -> bool:
    """Create/clarify already passed the gate — generate must not 409 again."""
    return str(status or "") in {"ready", "generating", "review", "delivered"}


def merge_resolved_prompt(prompt: str, answers: dict[str, str]) -> str:
    """Append structured clarification answers so downstream brief/pack sees them."""
    if not answers:
        return prompt
    lines = [prompt.rstrip(), "", "## Clarifications (resolved)"]
    for key, value in answers.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip()


__all__ = [
    "IntentAssessment",
    "assess_intent",
    "merge_resolved_prompt",
    "session_already_admitted",
    "should_block_generation",
    "thin_document_brief",
]
