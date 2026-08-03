"""Self-consistency (N-sample vote/merge) for high-stakes draft steps — AI-3."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
from app.llm_provider import LLMError, LLMProvider
from app.settings import settings

SCAFFOLD_VOTE_TEMP = 0.5
SCAFFOLD_VOTE_SAMPLES = 3
WORKFLOW_VOTE_SAMPLES = 3


def self_consistency_enabled() -> bool:
    return (settings.ai_self_consistency or "off").strip().lower() in {
        "on",
        "true",
        "1",
    }


def self_consistency_status() -> dict[str, Any]:
    enabled = self_consistency_enabled()
    return {
        "ai_self_consistency": settings.ai_self_consistency,
        "enabled": enabled,
        "note": "~2–3x LLM calls on scaffold + workflow steps when on",
        "scaffold_samples": SCAFFOLD_VOTE_SAMPLES,
        "workflow_samples": WORKFLOW_VOTE_SAMPLES,
    }


def vote_pack_id(
    votes: list[str],
    scores: dict[str, float],
) -> tuple[str | None, list[str]]:
    """Majority vote on pack id; tie-break by highest retrieval score."""
    warnings: list[str] = []
    cleaned = [v.strip() for v in votes if isinstance(v, str) and v.strip()]
    if not cleaned:
        return None, ["self_consistency: no pack votes — using baseline retrieval"]

    counts = Counter(cleaned)
    top_count = counts.most_common(1)[0][1]
    leaders = [pid for pid, n in counts.items() if n == top_count]
    unique_votes = set(cleaned)

    if len(leaders) == 1:
        winner = leaders[0]
        if len(unique_votes) > 1:
            warnings.append(
                f"self_consistency: pack vote split {dict(counts)} → {winner}"
            )
        return winner, warnings

    winner = max(leaders, key=lambda pid: scores.get(pid, 0.0))
    warnings.append(
        f"self_consistency: pack vote tie {leaders} → {winner} (retrieval score)"
    )
    return winner, warnings


def _normalize_state_entry(st: Any) -> tuple[str, str] | None:
    if isinstance(st, dict):
        key = str(st.get("value") or st.get("name") or st.get("id") or "").strip()
        if not key:
            return None
        label = str(st.get("label") or st.get("string") or key.replace("_", " ").title())
        return key, label
    if isinstance(st, (list, tuple)) and len(st) >= 2:
        return str(st[0]).strip(), str(st[1]).strip()
    if isinstance(st, str) and st.strip():
        key = st.strip()
        return key, key.replace("_", " ").title()
    return None


def merge_workflow_states(
    samples: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Merge N workflow-state samples: states appearing ≥2 times; transitions with surviving endpoints."""
    warnings: list[str] = []
    if not samples:
        return {"states": [], "transitions": []}, ["workflow merge: no samples"]

    state_counts: Counter[str] = Counter()
    state_positions: dict[str, list[int]] = {}
    state_labels: dict[str, str] = {}

    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for i, raw in enumerate(sample.get("states") or []):
            norm = _normalize_state_entry(raw)
            if norm is None:
                continue
            key, label = norm
            state_counts[key] += 1
            state_positions.setdefault(key, []).append(i)
            state_labels.setdefault(key, label)

    kept = [k for k, n in state_counts.items() if n >= 2]
    if not kept and samples:
        first = samples[0]
        for raw in (first.get("states") or []) if isinstance(first, dict) else []:
            norm = _normalize_state_entry(raw)
            if norm:
                kept.append(norm[0])
                state_labels.setdefault(norm[0], norm[1])
        warnings.append("workflow merge: no state ≥2 votes — using first sample states")

    kept.sort(
        key=lambda k: sum(state_positions.get(k, [0])) / max(len(state_positions.get(k, [1])), 1)
    )
    kept_set = set(kept)

    transitions: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    transition_counts: Counter[tuple[str, str]] = Counter()
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for tr in sample.get("transitions") or []:
            if not isinstance(tr, (list, tuple)) or len(tr) < 2:
                continue
            a, b = str(tr[0]).strip(), str(tr[1]).strip()
            if a in kept_set and b in kept_set:
                transition_counts[(a, b)] += 1

    for (a, b), n in transition_counts.items():
        if n >= 2 and (a, b) not in seen:
            transitions.append([a, b])
            seen.add((a, b))

    # Endpoints survive but pair only once — still keep (card: when endpoints survive)
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for tr in sample.get("transitions") or []:
            if not isinstance(tr, (list, tuple)) or len(tr) < 2:
                continue
            a, b = str(tr[0]).strip(), str(tr[1]).strip()
            if a in kept_set and b in kept_set and (a, b) not in seen:
                transitions.append([a, b])
                seen.add((a, b))

    if len(samples) > 1 and len({json.dumps(s, sort_keys=True) for s in samples}) > 1:
        warnings.append(
            f"workflow merge: merged {len(kept)} states, {len(transitions)} transitions "
            f"from {len(samples)} samples"
        )

    states_out = [{"value": k, "label": state_labels.get(k, k)} for k in kept]
    return {"states": states_out, "transitions": transitions}, warnings


def selection_literal_from_states(states: list[dict[str, Any]]) -> str:
    pairs = []
    for st in states:
        if isinstance(st, dict):
            val = st.get("value") or st.get("name")
            label = st.get("label") or st.get("string") or val
        else:
            norm = _normalize_state_entry(st)
            if norm is None:
                continue
            val, label = norm
        if val:
            pairs.append(f"('{val}','{label}')")
    return "[" + ",".join(pairs) + "]"


def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def llm_vote_domain_pack(
    prompt: str,
    provider: LLMProvider,
    *,
    pack_ids: list[str],
    pack_summaries: list[str],
    retrieval_scores: dict[str, float],
) -> tuple[str | None, list[str]]:
    """Run N LLM pack-classification samples at temp 0.5 and majority-vote."""
    warnings: list[str] = []
    if not pack_ids:
        return None, ["self_consistency: no packs to vote on"]

    allowed = ", ".join(pack_ids)
    system = append_prompt_blocks(
        "Classify which domain pack best matches the user request. "
        f"Allowed pack_id values: {allowed} or null when none fit.\n"
        'Example output: {"pack_id":"law_firm"}',
    )
    user = (
        f"User request:\n{prompt}\n\nPack summaries:\n"
        + "\n".join(pack_summaries[:20])
    )
    votes: list[str] = []
    for i in range(SCAFFOLD_VOTE_SAMPLES):
        try:
            raw = provider.generate_json(
                user,
                system=system,
                reasoning=True,
                temperature=SCAFFOLD_VOTE_TEMP,
            )
            data = _extract_json(raw)
            pid = data.get("pack_id") if isinstance(data, dict) else None
            if pid is None or pid == "null":
                votes.append("")
            elif str(pid) in pack_ids:
                votes.append(str(pid))
            else:
                warnings.append(f"self_consistency: sample {i + 1} invalid pack {pid!r}")
                votes.append("")
        except (LLMError, ValueError, json.JSONDecodeError, TypeError) as exc:
            warnings.append(f"self_consistency: scaffold sample {i + 1} failed ({exc})")
            votes.append("")

    winner, vote_w = vote_pack_id(votes, retrieval_scores)
    warnings.extend(vote_w)
    return winner, warnings


def llm_merge_workflow_states_for_model(
    provider: LLMProvider,
    *,
    model: dict[str, Any],
    user_prompt: str,
    guardrail: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Three-sample workflow state generation + merge; returns updated model copy."""
    warnings: list[str] = []
    mid = str(model.get("model") or "")
    system = append_prompt_blocks(
        "Define workflow status states and valid transitions for one Odoo custom model. "
        "Example output:\n"
        '{"states":[{"value":"draft","label":"Draft"},{"value":"open","label":"Open"},'
        '{"value":"done","label":"Done"}],'
        '"transitions":[["draft","open"],["open","done"]]}\n'
        "Terminal states (done/cancelled) should have no mandatory outgoing edges.",
        guardrail=guardrail,
    )
    prompt = (
        f"User app request:\n{user_prompt}\n\n"
        f"Workflow model: {mid}\n"
        f"Purpose: {model.get('description') or mid}\n"
        f"Existing fields: {[f.get('name') for f in (model.get('fields') or []) if isinstance(f, dict)]}"
    )
    samples: list[dict[str, Any]] = []
    for i in range(WORKFLOW_VOTE_SAMPLES):
        try:
            raw = provider.generate_json(
                prompt,
                system=system,
                reasoning=True,
                temperature=SCAFFOLD_VOTE_TEMP,
            )
            data = _extract_json(raw)
            if isinstance(data, dict):
                samples.append(data)
            else:
                warnings.append(f"self_consistency: workflow sample {i + 1} not an object")
        except (LLMError, ValueError, json.JSONDecodeError, TypeError) as exc:
            warnings.append(f"self_consistency: workflow sample {i + 1} failed ({exc})")

    if not samples:
        return model, warnings

    merged, merge_w = merge_workflow_states(samples)
    warnings.extend(merge_w)

    out = dict(model)
    fields = [dict(f) for f in (out.get("fields") or []) if isinstance(f, dict)]
    sel = selection_literal_from_states(merged.get("states") or [])
    if not sel or sel == "[]":
        return out, warnings

    updated = False
    for f in fields:
        if f.get("name") == "x_status":
            f["ttype"] = "selection"
            f["selection"] = sel
            f.setdefault("string", "Status")
            updated = True
            break
    if not updated:
        fields.append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": sel,
                "required": True,
            }
        )
    out["fields"] = fields
    out["state_transitions"] = merged.get("transitions") or []
    return out, warnings


def retrieve_scaffold_with_consistency(
    prompt: str,
    provider: LLMProvider | None,
    *,
    baseline: tuple[str, dict[str, Any], float] | None,
    pack_loader: Any,
) -> tuple[tuple[str, dict[str, Any], float] | None, list[str]]:
    """When self-consistency on + provider: vote on pack id; else return baseline unchanged."""
    warnings: list[str] = []
    if not self_consistency_enabled() or provider is None:
        return baseline, warnings

    packs = pack_loader()
    pack_ids = [pid for pid, _ in packs]
    summaries = [
        f"- {pid}: {str(p.get('display_name') or pid)} ({p.get('domain_pack') or pid})"
        for pid, p in packs
    ]
    scores: dict[str, float] = {}
    if baseline:
        scores[baseline[0]] = baseline[2]
    from app.ai_domain_packs import score_domain_pack

    for pid, pack in packs:
        scores.setdefault(pid, score_domain_pack(prompt, pack))

    winner, vote_w = llm_vote_domain_pack(
        prompt,
        provider,
        pack_ids=pack_ids,
        pack_summaries=summaries,
        retrieval_scores=scores,
    )
    warnings.extend(vote_w)

    if not winner:
        return baseline, warnings

    import copy

    pack = next((copy.deepcopy(p) for pid, p in packs if pid == winner), None)
    if pack is None:
        warnings.append(f"self_consistency: voted pack {winner} not found — baseline kept")
        return baseline, warnings

    score = scores.get(winner, baseline[2] if baseline else 0.0)
    if isinstance(pack, dict):
        pack["_retrieval"] = {"method": "self_consistency", "score": score}
    return (winner, pack, float(score)), warnings


def apply_workflow_consistency_to_models(
    provider: LLMProvider | None,
    models: list[dict[str, Any]],
    *,
    user_prompt: str,
    guardrail: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    if not self_consistency_enabled() or provider is None:
        return models, []

    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        if m.get("is_workflow") or any(
            isinstance(f, dict) and f.get("name") == "x_status"
            for f in (m.get("fields") or [])
        ):
            updated, w = llm_merge_workflow_states_for_model(
                provider,
                model=m,
                user_prompt=user_prompt,
                guardrail=guardrail,
            )
            out.append(updated)
            warnings.extend(w)
        else:
            out.append(m)
    return out, warnings
