"""Deterministic draft quality scorecard (GEN2-12)."""

from __future__ import annotations

import re
from typing import Any

from app.ai_domain_nouns import domain_noun_coverage, extract_prompt_nouns
from app.ai_post_critique import verify_model_ui_completeness
from app.ai_workflow_semantic import (
    _ALLOWED_INITIAL_TERMINALS,
    _INITIAL_STATES,
    classify_state,
    synthesize_semantic_transitions,
)
from app.module_spec_codec import merge_custom_code_blocks

_GLOBAL_PROMPT_RE = re.compile(
    r"\b("
    r"around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
    r"across\s+countries|multiple\s+countries|multiple\s+branches"
    r")\b",
    re.I,
)
_LINE_QTY_NAMES = ("x_qty", "x_quantity", "quantity", "x_hours", "x_units")
_LINE_PRICE_NAMES = ("x_price", "x_unit_price", "x_price_unit", "x_rate", "price_unit")
_LINE_TOTAL_NAMES = ("x_subtotal", "x_total", "x_amount")

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
        for a, b in transitions:
            if (
                str(a).lower() in _INITIAL_STATES
                and classify_state(str(b)) == "terminal_negative"
                and str(b).lower() not in _ALLOWED_INITIAL_TERMINALS
            ):
                score -= 1.5
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": f"{mid}.{a}→{b}",
                        "detail": "draft/new skips to terminal without activation",
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


def _score_hygiene(draft: dict[str, Any], *, user_prompt: str = "") -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    if draft.get("error"):
        score -= 5.0
        findings.append({"dimension": "hygiene", "element": "error", "detail": "top-level error key"})
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
        if "x_address" in names and "x_address_id" in names:
            score -= 1.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "duplicate address char + address_id",
                }
            )
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("relation") or "")
            if rel == "hr.employee" and "hr" not in set(draft.get("depends") or []):
                score -= 1.5
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "hr.employee relation without hr in depends",
                    }
                )
            if f.get("ttype") != "selection":
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
    prefixes: dict[str, str] = {}
    for seq in draft.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        prefix = str(seq.get("prefix") or "")
        model = str(seq.get("model") or "")
        if prefix and model:
            if prefix in prefixes and prefixes[prefix] != model:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": prefix,
                        "detail": "duplicate sequence prefix",
                    }
                )
            prefixes[prefix] = model
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        model = str(rule.get("model") or "")
        mdef = by_id.get(model) or {}
        mnames = {str(f.get("name")) for f in (mdef.get("fields") or []) if isinstance(f, dict)}
        if "company_id" in dom and "company_id" not in mnames and "x_company_id" in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule uses company_id but model has x_company_id",
                }
            )
        if "x_company_id" in dom and "company_id" in mnames and "x_company_id" not in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule uses x_company_id but model has company_id",
                }
            )
        if "company_id" in dom and "company_id" not in mnames and "x_company_id" not in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule references company_id but model lacks field",
                }
            )
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    if _GLOBAL_PROMPT_RE.search(prompt):
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            desc = str(model.get("description") or "").lower()
            if mid != "x_branch" and "branch" not in mid and "branch" not in desc:
                continue
            names = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
            if "x_country_id" not in names:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "global prompt but branch model missing x_country_id",
                    }
                )
    compute_models = {
        str(b.get("model"))
        for b in merge_custom_code_blocks(draft)
        if isinstance(b, dict) and b.get("model")
    }
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        if (
            str(btn.get("on_model") or "") == "x_staff_shift"
            and str(btn.get("related_model") or "") in {"x_event", "x_task"}
            and str(btn.get("relation_field") or "") == "x_staff_id"
        ):
            score -= 1.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(btn.get("label") or "smart_button"),
                    "detail": "shift smart button uses x_staff_id after assignee→employee fix",
                }
            )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        fields = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
        qty = any(n in fields for n in _LINE_QTY_NAMES)
        price = any(n in fields for n in _LINE_PRICE_NAMES)
        total = any(n in fields for n in _LINE_TOTAL_NAMES)
        if qty and price and total and mid not in compute_models:
            score -= 1.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "line qty×price without stored subtotal compute",
                }
            )
        for f in model.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") != "x_staff_id":
                continue
            rel = str(f.get("relation") or "")
            if rel == "x_staff_shift" and mid in {"x_event", "x_task"}:
                score -= 1.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.x_staff_id",
                        "detail": "assignee points to shift row not employee/user",
                    }
                )
    header_models = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and any(
            isinstance(f, dict) and str(f.get("name")) in {"x_amount_total", "x_total", "x_amount"}
            for f in (m.get("fields") or [])
        )
        and any(
            isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and "line" in str(f.get("relation") or "").lower()
            for f in (m.get("fields") or [])
        )
    }
    for mid in header_models:
        if mid not in compute_models:
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "order header total not computed from line subtotals",
                }
            )
    anti = list(draft.get("anti_patterns") or [])
    forbid_capture = any(
        re.search(r"payment capture|recurring billing engines|folio settlement", str(p), re.I)
        for p in anti
    )
    if forbid_capture:
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            if not mid.startswith("x_") or "invoice" not in mid.lower():
                continue
            if model.get("is_workflow"):
                score -= 2.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "parallel billing workflow violates pack anti-pattern (link account.move only)",
                    }
                )
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        names = re.findall(r'name="([^"]+)"', arch)
        if len(names) != len(set(names)):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(v.get("model") or "search"),
                    "detail": "duplicate search filter names",
                }
            )
    for model in draft.get("models") or []:
        if isinstance(model, dict) and str(model.get("description") or "").startswith("Super "):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(model.get("model") or ""),
                    "detail": "generic depth_seed label (Super *)",
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
        ("hygiene", lambda: _score_hygiene(spec, user_prompt=prompt)),
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
