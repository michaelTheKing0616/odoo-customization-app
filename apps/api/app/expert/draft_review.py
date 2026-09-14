"""Expert draft review — scorecard + cited review + deterministic fixes (EXP2-2)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.ai_apply_readiness import filter_stale_enrich_warnings
from app.ai_critique import finalize_critique_block
from app.ai_draft_scorecard import attach_scorecard, draft_scorecard, scorecard_required_repairs
from app.ai_post_critique import run_post_critique_pipeline
from app.ai_production_shape import run_production_shape_pass


def _model_ids(draft: dict[str, Any]) -> set[str]:
    return {
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def closer_must_not_mutate(draft: dict[str, Any]) -> bool:
    """Empty stock-reuse / refuse-clone specs are already honest — do not invent x_*."""
    from app.ai_generation_engine import is_refuse_draft, is_stock_reuse_draft

    return is_stock_reuse_draft(draft) or is_refuse_draft(draft)


def _live_apply_gap_rows(draft: dict[str, Any]) -> list[dict[str, Any]]:
    from app.ai_live_apply_contract import live_apply_contract_findings

    rows = live_apply_contract_findings(draft)
    return [row for row in rows if isinstance(row, dict) and str(row.get("detail") or "").strip()]


def _has_repairable_gaps(draft: dict[str, Any], scorecard: dict[str, Any]) -> bool:
    """True only when the closer can improve JSON — not Cert, not Autopilot, not ready:false."""
    if closer_must_not_mutate(draft):
        return False
    from app.ai_document_shape import (
        additive_model_growth_blocked,
        draft_needs_hygiene_repair,
        forbidden_stock_hosts,
    )

    prompt = str(draft.get("_user_prompt") or "")
    if draft_needs_hygiene_repair(draft, prompt=prompt):
        return True
    if additive_model_growth_blocked(draft) and not scorecard.get("findings") and not _live_apply_gap_rows(draft):
        # Register/field_pack: only repair if forbidden hosts or clones exist
        if forbidden_stock_hosts(draft):
            models = draft.get("models") or []
            if any(
                isinstance(m, dict)
                and str(m.get("mode") or "") == "inherit"
                and str(m.get("model") or "") in forbidden_stock_hosts(draft)
                for m in models
            ):
                return True
        from app.ai_stock_first import list_stock_clone_models

        return bool(list_stock_clone_models(draft))
    if any(isinstance(f, dict) for f in (scorecard.get("findings") or [])):
        return True
    if _live_apply_gap_rows(draft):
        return True
    from app.ai_stock_first import list_stock_clone_models

    return bool(list_stock_clone_models(draft))


def _worse_after_closer(
    original: dict[str, Any],
    candidate: dict[str, Any],
    *,
    score_before: float,
    score_after: float,
) -> str | None:
    """Return a reason if the closer made the spec less honest or lower-scoring."""
    from app.ai_generation_engine import is_refuse_draft, is_stock_reuse_draft
    from app.ai_stock_first import list_stock_clone_models

    if score_after + 0.05 < score_before:
        return f"completeness dropped {score_before:.1f} → {score_after:.1f}"
    if is_stock_reuse_draft(original):
        extra = {m for m in _model_ids(candidate) if m.startswith("x_")}
        if extra:
            return f"stock_reuse invented {sorted(extra)[:6]}"
        if not is_stock_reuse_draft(candidate) and _model_ids(candidate):
            return "stock_reuse capability lost"
    if is_refuse_draft(original) and not is_refuse_draft(candidate):
        return "refuse_clone was overwritten"
    before_clones = set(list_stock_clone_models(original))
    after_clones = set(list_stock_clone_models(candidate))
    gained = after_clones - before_clones
    if gained:
        return f"new stock clones {sorted(gained)[:6]}"
    try:
        from app.ai_document_shape import forbidden_stock_hosts

        hosts = forbidden_stock_hosts(original) | forbidden_stock_hosts(candidate)
        def _hits(d: dict[str, Any]) -> set[str]:
            out: set[str] = set()
            for m in d.get("models") or []:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("model") or "")
                if str(m.get("mode") or "") == "inherit" and mid in hosts:
                    out.add(mid)
            return out

        leftover = _hits(candidate)
        if leftover:
            return f"forbidden CRM/invoice {sorted(leftover)[:6]}"
    except Exception:  # noqa: BLE001
        pass
    return None


def _findings_from_live(draft: dict[str, Any], *, start_priority: int) -> list[DraftReviewFinding]:
    out: list[DraftReviewFinding] = []
    for i, row in enumerate(_live_apply_gap_rows(draft)):
        detail = str(row.get("detail") or "")
        out.append(
            DraftReviewFinding(
                priority=start_priority + i,
                element=str(row.get("element") or "live_apply"),
                summary="Live apply gap",
                detail=detail,
                deterministic=True,
                repair_hint=detail,
                citation="live-apply contract",
            )
        )
    return out


def _append_overlap(
    findings: list[DraftReviewFinding], overlap_notes: list[str] | None
) -> None:
    if not overlap_notes:
        return
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


def _restore_activity_automations(
    original: dict[str, Any], candidate: dict[str, Any]
) -> list[str]:
    """Keep next_activity rows the pipeline dropped so mixin stamping still has a target."""
    from app.ai_live_apply_contract import _has_activity_action

    orig = [
        copy.deepcopy(auto)
        for auto in (original.get("automations") or [])
        if isinstance(auto, dict) and _has_activity_action(auto)
    ]
    if not orig:
        return []
    current = [a for a in (candidate.get("automations") or []) if isinstance(a, dict)]
    keys = {
        (str(a.get("model") or ""), str(a.get("name") or ""))
        for a in current
        if _has_activity_action(a)
    }
    model_ids = _model_ids(candidate)
    notes: list[str] = []
    for auto in orig:
        mid = str(auto.get("model") or "")
        name = str(auto.get("name") or "")
        if (mid, name) in keys:
            continue
        if mid not in model_ids:
            continue
        current.append(auto)
        keys.add((mid, name))
        notes.append(f"closer: restored live-apply activity automation {name!r} on {mid}")
    if notes:
        candidate["automations"] = current
    return notes


def apply_deterministic_scorecard_fixes(draft: dict[str, Any], *, user_prompt: str = "") -> tuple[dict[str, Any], list[str]]:
    """Re-run pack merge + stock-first clip, then post-critique + app-bar + production."""
    if closer_must_not_mutate(draft):
        return copy.deepcopy(draft), [
            "no_repair: stock-reuse / refuse-clone — do not invent x_*; Job Autopilot is the done-bar",
        ]

    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    from app.ai_generation_engine import classify_generation

    plan = classify_generation(prompt)
    custom_x = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    if plan.grain == "field_pack" and (draft.get("domain_pack") or custom_x):
        from app.ai_pipeline import seed_studio_draft

        rebuilt = seed_studio_draft(prompt)
        return rebuilt, [
            "closer: rebuilt field_pack inherit seed; dropped vertical pack / parallel x_*",
        ]

    from app.ai_domain_packs import load_domain_pack, match_domain_pack, merge_domain_pack

    matched = match_domain_pack(prompt)
    current_pack = str(draft.get("domain_pack") or "")
    matched_id = matched[0] if matched else ""
    if current_pack and matched_id != current_pack:
        from app.ai_pipeline import seed_studio_draft

        rebuilt = seed_studio_draft(prompt)
        return rebuilt, [
            "closer: rebuilt seed; dropped incoherent vertical pack "
            f"{current_pack!r} (prompt matches {matched_id or 'none'})",
        ]

    out = copy.deepcopy(draft)
    notes: list[str] = []
    prompt = user_prompt or str(out.get("_user_prompt") or "")
    from app.ai_stock_first import clip_to_stock_first_floor, restore_pack_identity
    notes.extend(restore_pack_identity(out, user_prompt=prompt))
    pack = load_domain_pack(str(out.get("domain_pack") or ""))
    from app.ai_document_shape import additive_model_growth_blocked, honor_operator_brief

    notes.extend(honor_operator_brief(out, user_prompt=prompt))
    if pack and not additive_model_growth_blocked(out, prompt=prompt):
        merged, merge_notes = merge_domain_pack(out, pack)
        notes.extend(merge_notes)
        out.clear()
        out.update(merged)
    notes.extend(clip_to_stock_first_floor(out, user_prompt=prompt))
    notes.extend(run_post_critique_pipeline(out, user_prompt=prompt))
    from app.ai_odoo_app_bar import apply_senior_sequence_prefixes
    from app.ai_odoo_app_bar import close_odoo_architecture, run_odoo_app_bar_pass

    notes.extend(run_odoo_app_bar_pass(out, user_prompt=prompt))
    notes.extend(run_production_shape_pass(out))
    notes.extend(apply_senior_sequence_prefixes(out))
    notes.extend(close_odoo_architecture(out, user_prompt=prompt))
    notes.extend(clip_to_stock_first_floor(out, user_prompt=prompt))
    notes.extend(honor_operator_brief(out, user_prompt=prompt))
    notes.extend(_restore_activity_automations(draft, out))
    from app.ai_live_apply_contract import stamp_live_apply_contract

    notes.extend(stamp_live_apply_contract(out))
    notes.extend(finalize_critique_block(out))
    notes = filter_stale_enrich_warnings(notes, out)
    return out, notes


@dataclass
class DraftReviewFinding:
    priority: int
    element: str
    summary: str
    detail: str
    deterministic: bool
    repair_hint: str | None = None
    citation: str | None = None
    narrative_paragraph: str | None = None
    narrative_citations: list[dict[str, Any]] = field(default_factory=list)


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
    architecture = (
        "FK should target" in detail
        or "generic ops-loop" in detail
        or "parallel stock clone" in detail
        or "stock clone on packed" in detail
        or "missing site FK" in detail
        or "duplicate parent m2o" in detail
        or "count drift" in detail
    )
    deterministic = architecture or (
        dim in {"structure", "hygiene", "semantics", "ux", "validators"}
        and (
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


def review_draft(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    apply_fixes: bool = False,
    overlap_notes: list[str] | None = None,
    db: Session | None = None,
    version: str | None = None,
    include_narratives: bool = True,
) -> DraftReviewResult:
    """Run scorecard, build prioritized review, optionally apply deterministic fixes."""
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    before = draft_scorecard(draft, user_prompt=prompt)
    score_before = float(before.get("score_0_10") or 0.0)
    findings: list[DraftReviewFinding] = []
    for i, row in enumerate(before.get("findings") or []):
        if isinstance(row, dict):
            findings.append(_finding_from_scorecard_row(row, priority=i + 1))
    findings.extend(_findings_from_live(draft, start_priority=len(findings) + 1))
    _append_overlap(findings, overlap_notes)

    repairs: list[str] = []
    suggestions: list[str] = []
    score_after: float | None = None
    skipped_mutate = False
    working = copy.deepcopy(draft)
    if apply_fixes:
        from app.ai_document_shape import draft_needs_hygiene_repair

        hygiene = draft_needs_hygiene_repair(draft, prompt=prompt)
        if closer_must_not_mutate(draft) or (
            not hygiene
            and not _has_repairable_gaps(draft, before)
            and score_before >= 9.0
        ):
            skipped_mutate = True
            score_after = score_before
            repairs = [
                "no_repair: stock-reuse / refuse-clone — do not invent x_*; Job Autopilot is the done-bar"
                if closer_must_not_mutate(draft)
                else "no_repair: no scorecard, live-apply, hygiene, or stock-clone gaps"
            ]
        else:
            snapshot = copy.deepcopy(draft)
            working, fix_notes = apply_deterministic_scorecard_fixes(
                working, user_prompt=prompt
            )
            repairs = [n for n in fix_notes if not n.startswith("post_critique: near-dup")]
            suggestions = [n for n in fix_notes if n.startswith("post_critique: near-dup")]
            after = attach_scorecard(working, user_prompt=prompt)
            from app.ai_live_apply_contract import attach_live_apply_contract

            attach_live_apply_contract(working)
            score_after = float(after.get("score_0_10") or score_before)
            worse = _worse_after_closer(
                snapshot,
                working,
                score_before=score_before,
                score_after=score_after,
            )
            if worse:
                working = snapshot
                score_after = score_before
                repairs = [f"reverted: closer would have made JSON worse ({worse})"] + repairs[
                    :8
                ]
                findings = [
                    _finding_from_scorecard_row(row, priority=i + 1)
                    for i, row in enumerate(before.get("findings") or [])
                    if isinstance(row, dict)
                ]
                findings.extend(_findings_from_live(draft, start_priority=len(findings) + 1))
                _append_overlap(findings, overlap_notes)
            else:
                findings = []
                for i, row in enumerate(after.get("findings") or []):
                    if isinstance(row, dict):
                        findings.append(_finding_from_scorecard_row(row, priority=i + 1))
                findings.extend(
                    _findings_from_live(working, start_priority=len(findings) + 1)
                )
                _append_overlap(findings, overlap_notes)
    else:
        working = None
        for f in findings:
            if f.deterministic and f.repair_hint:
                repairs.append(f.repair_hint)
            else:
                suggestions.append(f.detail)

    # Narratives wait on the LLM — skip them when applying closer repairs so
    # "review and fix" cannot time out and leave the wizard on a cached 7.0.
    if include_narratives and findings and not apply_fixes:
        from app.expert.narrative import generate_finding_narratives

        narratives_by_priority: dict[int, Any] = {}
        for narrative in generate_finding_narratives(
            db,
            findings,
            user_prompt=prompt,
            version=version,
            top_n=5,
        ):
            narratives_by_priority[narrative.priority] = narrative
        for finding in findings:
            narrative = narratives_by_priority.get(finding.priority)
            if not narrative:
                continue
            finding.narrative_paragraph = narrative.paragraph
            finding.narrative_citations = [
                {
                    "source": c.source,
                    "version": c.version,
                    "breadcrumb": c.breadcrumb,
                    "chunk_id": c.chunk_id,
                    "source_index": c.source_index,
                }
                for c in narrative.citations
            ]

    judged = working if apply_fixes and working is not None else draft
    from app.ai_certification import stamp_certification
    from app.ai_stock_first import list_stock_clone_models

    if not isinstance(judged.get("_certification"), dict):
        stamp_certification(judged)
    cert = judged.get("_certification") if isinstance(judged.get("_certification"), dict) else {}
    tier = str(cert.get("tier") or "")
    clones = list_stock_clone_models(judged)
    option_a_pending = bool(
        judged.get("_capability_primary_option_a") or judged.get("custom_code_blocks")
    )
    score_now = score_after if score_after is not None else score_before
    if closer_must_not_mutate(judged) or skipped_mutate:
        verdict = "no_repair_needed"
    elif clones:
        verdict = "needs_work"
    elif score_now >= 9.0:
        verdict = "ready"
    else:
        verdict = "needs_work"
    lines = [
        f"**Completeness: {score_before:.1f}/10**"
        + (f" · **Certification: {tier or 'n/a'}**" if cert else ""),
        "",
        "Top findings:" if score_after is None else "Remaining findings:",
    ]
    for f in sorted(findings, key=lambda x: x.priority)[:8]:
        tag = "Fix available" if f.deterministic else "Suggestion"
        lines.append(f"- [{tag}] {f.summary}: {f.detail}")
    if not findings:
        lines.append("- none")
    if verdict == "no_repair_needed":
        lines.append("")
        lines.append(
            "**Expert closer:** no JSON repair — do not invent x_*. "
            "Completeness ≠ Cert ≠ Autopilot. Job Autopilot is the done-bar for stock reuse."
        )
    elif option_a_pending and tier not in {"Production", "Gold"}:
        lines.append("")
        lines.append(
            f"**Ship bar:** Certification is `{tier or 'missing'}` — "
            "need Production/Gold (sandbox prove for Option A). Completeness 10.0 alone is not go-live. "
            "Expert closer does not raise Certification."
        )
    narrated = [f for f in sorted(findings, key=lambda x: x.priority) if f.narrative_paragraph][:5]
    if narrated:
        lines.append("")
        lines.append("**Expert review (cited):**")
        for f in narrated:
            lines.append("")
            lines.append(f"**{f.summary}**")
            lines.append(f.narrative_paragraph or "")
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
    "closer_must_not_mutate",
    "review_draft",
]
