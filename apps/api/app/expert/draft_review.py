"""Expert draft review — scorecard + cited review + deterministic fixes (EXP2-2)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from app.ai_critique import apply_critique_repairs, finalize_critique_block
from app.ai_draft_scorecard import attach_scorecard, draft_scorecard, scorecard_required_repairs
from app.ai_post_critique import run_post_critique_pipeline
from app.ai_production_shape import run_production_shape_pass


@dataclass
class DraftReviewFinding:
    priority: int
    element: str
    summary: str
    detail: str
    deterministic: bool
    repair_hint: str | None = None
    citation: str | None = None


@dataclass
class DraftReviewResult:
    score_before: float
    score_after: float | None
    findings: list[DraftReviewFinding] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    verdict: str = "needs_work"
    review_markdown: str = ""
    draft: dict[str, Any] | None = None


def _finding_from_scorecard_row(row: dict[str, Any], priority: int) -> DraftReviewFinding:
    dim = str(row.get("dimension") or "hygiene")
    el = str(row.get("element") or "?")
    detail = str(row.get("detail") or "")
    deterministic = dim in {"structure", "hygiene", "semantics", "ux"} and (
        "missing" in detail
        or "line model" in detail
        or "non-string" in detail
        or "workflow model missing" in detail
        or "duplicate smart button" in detail
        or "duplicate address" in detail
        or "record rule" in detail
        or "duplicate sequence" in detail
        or "duplicate search" in detail
        or "without hr in depends" in detail
        or "generic depth_seed" in detail
    )
    summary = f"{dim.replace('_', ' ').title()}: {el}"
    return DraftReviewFinding(
        priority=priority,
        element=el,
        summary=summary,
        detail=detail,
        deterministic=deterministic,
        repair_hint=scorecard_required_repairs({"findings": [row]})[0] if deterministic else None,
        citation="GEN2-12 scorecard rubric",
    )


def apply_deterministic_scorecard_fixes(draft: dict[str, Any], *, user_prompt: str = "") -> tuple[dict[str, Any], list[str]]:
    """Re-run post-critique + production passes (deterministic repairs)."""
    out = copy.deepcopy(draft)
    notes: list[str] = []
    notes.extend(run_post_critique_pipeline(out, user_prompt=user_prompt))
    notes.extend(run_production_shape_pass(out))
    notes.extend(finalize_critique_block(out))
    return out, notes


def review_draft(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    apply_fixes: bool = False,
    overlap_notes: list[str] | None = None,
) -> DraftReviewResult:
    """Run scorecard, build prioritized review, optionally apply deterministic fixes."""
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    before = draft_scorecard(draft, user_prompt=prompt)
    score_before = float(before.get("score_0_10") or 0.0)
    findings: list[DraftReviewFinding] = []
    for i, row in enumerate(before.get("findings") or []):
        if isinstance(row, dict):
            findings.append(_finding_from_scorecard_row(row, priority=i + 1))
    if overlap_notes:
        for i, note in enumerate(overlap_notes):
            findings.append(
                DraftReviewFinding(
                    priority=len(findings) + i + 1,
                    element="reuse_overlap",
                    summary="Reuse overlap",
                    detail=note,
                    deterministic=False,
                    citation="AI-9 overlap planner",
                )
            )
    repairs: list[str] = []
    suggestions: list[str] = []
    score_after: float | None = None
    working = copy.deepcopy(draft)
    if apply_fixes:
        working, fix_notes = apply_deterministic_scorecard_fixes(working, user_prompt=prompt)
        repairs = [n for n in fix_notes if not n.startswith("post_critique: near-dup")]
        suggestions = [n for n in fix_notes if n.startswith("post_critique: near-dup")]
        after = attach_scorecard(working, user_prompt=prompt)
        score_after = float(after.get("score_0_10") or score_before)
    else:
        working = None
        for f in findings:
            if f.deterministic and f.repair_hint:
                repairs.append(f.repair_hint)
            else:
                suggestions.append(f.detail)
    verdict = "ready" if score_before >= 9.0 else "needs_work"
    if score_after is not None and score_after >= 9.0:
        verdict = "ready"
    lines = [
        f"**Draft quality: {score_before:.1f}/10**",
        "",
        "Top findings:",
    ]
    for f in sorted(findings, key=lambda x: x.priority)[:8]:
        tag = "Fix available" if f.deterministic else "Suggestion"
        lines.append(f"- [{tag}] {f.summary}: {f.detail}")
    if score_after is not None:
        lines.append("")
        lines.append(f"After deterministic fixes: **{score_after:.1f}/10**")
    return DraftReviewResult(
        score_before=score_before,
        score_after=score_after,
        findings=findings,
        repairs=repairs,
        suggestions=suggestions,
        verdict=verdict,
        review_markdown="\n".join(lines),
        draft=working if apply_fixes else None,
    )


__all__ = [
    "DraftReviewResult",
    "apply_deterministic_scorecard_fixes",
    "review_draft",
]
