"""Deterministic draft quality scorecard (GEN2-12)."""

from __future__ import annotations

import re
from typing import Any

from app.ai_domain_nouns import domain_noun_coverage, extract_prompt_nouns
from app.ai_post_critique import verify_model_ui_completeness
from app.ai_workflow_semantic import classify_state, synthesize_semantic_transitions

_FOREIGN_LEXICON = frozenset(
    {
        "retainer",
        "trust account",
        "disbursement",
        "matter",
        "hearing",
        "conflict check",
        "multi-party",
    }
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _blob(draft: dict[str, Any]) -> str:
    import json

    return json.dumps(draft, default=str).lower()


def _score_domain_fit(draft: dict[str, Any], prompt: str) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    items, uncovered, _w = domain_noun_coverage(draft, prompt)
    if uncovered:
        score -= min(4.0, len(uncovered) * 1.5)
        for n in uncovered:
            findings.append(
                {"dimension": "domain_fit", "element": f"noun:{n}", "detail": "uncovered prompt noun"}
            )
    vocab = draft.get("vocab") if isinstance(draft.get("vocab"), dict) else {}
    vocab_keys = {str(k).lower() for k in vocab}
    anti = " ".join(str(x) for x in (draft.get("anti_patterns") or [])).lower()
    blob = _blob(draft)
    for term in _FOREIGN_LEXICON:
        if term in prompt.lower():
            continue
        if term in vocab_keys:
            continue
        if term in anti and ("not" in anti or "do not" in anti):
            continue
        if term in blob:
            score -= 1.0
            findings.append(
                {"dimension": "domain_fit", "element": term, "detail": "foreign-domain lexicon leak"}
            )
    return max(0.0, score), findings


def _score_structure(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    ui_items = verify_model_ui_completeness(draft)
    bad = [c for c in ui_items if not c.get("ok")]
    if bad:
        score -= min(5.0, len(bad) * 1.2)
        for c in bad:
            findings.append(
                {
                    "dimension": "structure",
                    "element": c["id"],
                    "detail": c.get("detail") or "incomplete UI scaffold",
                }
            )
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            parent_fk = any(
                isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") in by_id
                and not str(f.get("relation") or "").endswith("_line")
                for f in (model.get("fields") or [])
            )
            if not parent_fk:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "structure",
                        "element": mid,
                        "detail": "line model missing parent m2o",
                    }
                )
    return max(0.0, score), findings


def _selection_keys(selection: Any) -> list[str]:
    if isinstance(selection, list):
        return [str(x[0]) for x in selection if isinstance(x, (list, tuple)) and x]
    if isinstance(selection, str):
        return re.findall(r"\('([^']+)'\s*,", selection)
    return []


def _score_semantics(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        mid = str(model.get("model") or "")
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        keys = list(sf.get("states") or [])
        if not keys:
            for f in model.get("fields") or []:
                if isinstance(f, dict) and f.get("name") == "x_status":
                    keys = _selection_keys(f.get("selection"))
        transitions = sf.get("transitions") or []
        if keys and not transitions:
            transitions, _vis = synthesize_semantic_transitions(keys)
        terminal = {k for k in keys if classify_state(k) != "active"}
        for a, _b in transitions:
            if str(a) in terminal:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": f"{mid}.{a}",
                        "detail": "terminal state has outgoing edge",
                    }
                )
        if "x_status" in {str(f.get("name")) for f in (model.get("fields") or [])} and not sf:
            score -= 2.0
            findings.append(
                {
                    "dimension": "semantics",
                    "element": mid,
                    "detail": "workflow model missing state_field",
                }
            )
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        if str(auto.get("trigger")) == "on_write" and not str(auto.get("filter_domain") or "").strip():
            score -= 0.5
            findings.append(
                {
                    "dimension": "semantics",
                    "element": str(auto.get("name") or "automation"),
                    "detail": "on_write without filter_domain",
                }
            )
    return max(0.0, score), findings


def _score_ux(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    action_models = {
        str(a.get("model"))
        for a in (draft.get("actions") or [])
        if isinstance(a, dict) and a.get("model")
    }
    search_models = {
        str(v.get("model"))
        for v in (draft.get("views") or [])
        if isinstance(v, dict) and str(v.get("type") or "") == "search"
    }
    missing_search = action_models - search_models
    if missing_search:
        score -= min(3.0, len(missing_search) * 0.8)
        for m in sorted(missing_search):
            findings.append(
                {"dimension": "ux", "element": m, "detail": "missing search view"}
            )
    labels: dict[tuple[str, str], int] = {}
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        key = (str(btn.get("on_model")), str(btn.get("label") or ""))
        labels[key] = labels.get(key, 0) + 1
    for key, count in labels.items():
        if count > 1:
            score -= 0.8
            findings.append(
                {
                    "dimension": "ux",
                    "element": key[1],
                    "detail": f"duplicate smart button label on {key[0]}",
                }
            )
    return max(0.0, score), findings


def _score_hygiene(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    if draft.get("error"):
        score -= 5.0
        findings.append({"dimension": "hygiene", "element": "error", "detail": "top-level error key"})
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for f in model.get("fields") or []:
            if not isinstance(f, dict) or f.get("ttype") != "selection":
                continue
            sel = f.get("selection")
            if isinstance(sel, list):
                score -= 1.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{f.get('name')}",
                        "detail": "non-string selection",
                    }
                )
            elif isinstance(sel, str):
                keys = _selection_keys(sel)
                if any(re.match(r"^option_[a-z]$", k, re.I) for k in keys):
                    score -= 0.8
                    findings.append(
                        {
                            "dimension": "hygiene",
                            "element": f"{mid}.{f.get('name')}",
                            "detail": "placeholder selection keys",
                        }
                    )
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    if meta:
        actual = len(draft.get("smart_buttons") or [])
        if meta.get("smart_button_count") not in (None, actual):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": "_meta.smart_button_count",
                    "detail": "count drift",
                }
            )
    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    if status.get("step") == 0 and status.get("completed_steps"):
        score -= 0.5
        findings.append(
            {
                "dimension": "hygiene",
                "element": "_llm_status",
                "detail": "step not finalized after completion",
            }
        )
    return max(0.0, score), findings


def draft_scorecard(
    spec: dict[str, Any],
    *,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Score draft 0–10 across five weighted dimensions."""
    prompt = user_prompt or str(spec.get("_user_prompt") or "")
    weights = {
        "domain_fit": 0.25,
        "structure": 0.25,
        "semantics": 0.20,
        "ux": 0.15,
        "hygiene": 0.15,
    }
    dim_scores: dict[str, float] = {}
    findings: list[dict[str, Any]] = []
    for name, fn in (
        ("domain_fit", lambda: _score_domain_fit(spec, prompt)),
        ("structure", lambda: _score_structure(spec)),
        ("semantics", lambda: _score_semantics(spec)),
        ("ux", lambda: _score_ux(spec)),
        ("hygiene", lambda: _score_hygiene(spec)),
    ):
        s, f = fn()
        dim_scores[name] = round(s, 2)
        findings.extend(f)
    score_0_10 = round(
        sum(dim_scores[k] * weights[k] for k in weights),
        2,
    )
    return {
        "score_0_10": score_0_10,
        "dimensions": dim_scores,
        "findings": findings,
        "prompt_nouns": extract_prompt_nouns(prompt),
    }


def attach_scorecard(draft: dict[str, Any], *, user_prompt: str = "") -> dict[str, Any]:
    draft["_scorecard"] = draft_scorecard(draft, user_prompt=user_prompt)
    return draft["_scorecard"]


def scorecard_required_repairs(scorecard: dict[str, Any]) -> list[str]:
    """Map scorecard findings to critique-style repair hints."""
    out: list[str] = []
    for f in scorecard.get("findings") or []:
        if not isinstance(f, dict):
            continue
        dim = f.get("dimension")
        el = f.get("element")
        detail = f.get("detail")
        out.append(f"scorecard({dim}): {el} — {detail}")
    return out


__all__ = [
    "attach_scorecard",
    "draft_scorecard",
    "scorecard_required_repairs",
]
