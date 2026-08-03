"""Workflow states + transitions — staged Step 4 and single-path derivation (AI-4)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
from app.ai_self_consistency import (
    WORKFLOW_VOTE_SAMPLES,
    merge_workflow_states,
    selection_literal_from_states,
    self_consistency_enabled,
)
from app.llm_provider import LLMError, LLMProvider

TEMP_WORKFLOW = STEP_TEMPERATURES["pipeline.relationships"]  # 0.15
TERMINAL_STATES = frozenset(
    {"done", "cancelled", "canceled", "closed", "lost", "retired", "archived", "paid"}
)


def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def parse_selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    return re.findall(r"\('([^']+)'\s*,", selection)


def derive_default_transitions(keys: list[str]) -> list[list[str]]:
    """Deterministic chain draft→…→terminal when LLM omitted transitions."""
    if len(keys) < 2:
        return []
    transitions: list[list[str]] = []
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a in TERMINAL_STATES:
            break
        transitions.append([a, b])
        if b in TERMINAL_STATES:
            break
    return transitions


def validate_workflow_definition(
    states: list[str],
    transitions: list[list[str]],
) -> list[str]:
    """Validate states exist and transitions reference real states."""
    notes: list[str] = []
    state_set = set(states)
    if not state_set:
        notes.append("workflow: no states defined")
        return notes

    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) < 2:
            notes.append(f"workflow: invalid transition {tr!r}")
            continue
        a, b = str(tr[0]), str(tr[1])
        if a not in state_set:
            notes.append(f"workflow: transition from unknown state {a!r}")
        if b not in state_set:
            notes.append(f"workflow: transition to unknown state {b!r}")

    outgoing: dict[str, list[str]] = {s: [] for s in states}
    for tr in transitions:
        if isinstance(tr, (list, tuple)) and len(tr) >= 2:
            a, b = str(tr[0]), str(tr[1])
            if a in outgoing:
                outgoing[a].append(b)

    for term in TERMINAL_STATES:
        if term in state_set and outgoing.get(term):
            notes.append(
                f"workflow: terminal state {term!r} has outgoing edges (non-mandatory ok)"
            )
    return notes


def active_states_from_transitions(
    states: list[str],
    transitions: list[list[str]],
) -> list[str]:
    """Non-terminal states that participate in at least one transition."""
    in_graph = set(states)
    for tr in transitions:
        if isinstance(tr, (list, tuple)) and len(tr) >= 2:
            in_graph.add(str(tr[0]))
            in_graph.add(str(tr[1]))
    return [s for s in states if s in in_graph and s not in TERMINAL_STATES]


def apply_state_field_to_model(
    model: dict[str, Any],
    *,
    states: list[dict[str, Any]] | list[str],
    transitions: list[list[str]],
) -> dict[str, Any]:
    """Write state_field + x_status selection on a model copy."""
    out = dict(model)
    state_dicts: list[dict[str, Any]] = []
    state_keys: list[str] = []
    for st in states:
        if isinstance(st, dict):
            val = str(st.get("value") or st.get("name") or "")
            label = str(st.get("label") or st.get("string") or val.replace("_", " ").title())
            if val:
                state_dicts.append({"value": val, "label": label})
                state_keys.append(val)
        elif isinstance(st, str) and st.strip():
            state_keys.append(st.strip())
            state_dicts.append(
                {"value": st.strip(), "label": st.strip().replace("_", " ").title()}
            )

    if state_dicts:
        sel = selection_literal_from_states(state_dicts)
    else:
        sel = ""

    fields = [dict(f) for f in (out.get("fields") or []) if isinstance(f, dict)]
    updated = False
    for f in fields:
        if f.get("name") == "x_status":
            if sel:
                f["ttype"] = "selection"
                f["selection"] = sel
            f.setdefault("string", "Status")
            updated = True
            break
    if not updated and sel:
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
    out["state_field"] = {
        "field": "x_status",
        "transitions": [list(tr) for tr in transitions],
    }
    if state_keys:
        out["state_field"]["states"] = state_keys
    out["is_workflow"] = True
    return out


def _llm_workflow_sample(
    provider: LLMProvider,
    *,
    model: dict[str, Any],
    user_prompt: str,
    guardrail: str,
) -> dict[str, Any] | None:
    mid = str(model.get("model") or "")
    system = append_prompt_blocks(
        "Define workflow status states and valid transitions for one Odoo custom model. "
        "Example output:\n"
        '{"states":[{"value":"draft","label":"Draft"},{"value":"open","label":"Open"},'
        '{"value":"done","label":"Done"}],'
        '"transitions":[["draft","open"],["open","done"]]}\n'
        "Terminal states (done/cancelled) should not require outgoing transitions.",
        guardrail=guardrail,
    )
    prompt = (
        f"User app request:\n{user_prompt}\n\n"
        f"Workflow model: {mid}\n"
        f"Purpose: {model.get('description') or mid}\n"
        f"Existing fields: {[f.get('name') for f in (model.get('fields') or []) if isinstance(f, dict)]}"
    )
    raw = provider.generate_json(
        prompt,
        system=system,
        reasoning=True,
        temperature=TEMP_WORKFLOW,
    )
    data = _extract_json(raw)
    return data if isinstance(data, dict) else None


def step4_workflow_entity(
    provider: LLMProvider,
    model: dict[str, Any],
    *,
    user_prompt: str,
    guardrail: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Step 4 — reasoning model defines states + transitions for one workflow entity."""
    warnings: list[str] = []
    if not (
        model.get("is_workflow")
        or any(
            isinstance(f, dict) and f.get("name") == "x_status"
            for f in (model.get("fields") or [])
        )
    ):
        return model, warnings

    samples: list[dict[str, Any]] = []
    n = WORKFLOW_VOTE_SAMPLES if self_consistency_enabled() else 1
    for i in range(n):
        try:
            data = _llm_workflow_sample(
                provider, model=model, user_prompt=user_prompt, guardrail=guardrail
            )
            if data:
                samples.append(data)
        except (LLMError, ValueError, json.JSONDecodeError, TypeError) as exc:
            warnings.append(f"step4: workflow sample {i + 1} failed ({exc})")

    if not samples:
        status = next(
            (f for f in (model.get("fields") or []) if isinstance(f, dict) and f.get("name") == "x_status"),
            None,
        )
        keys = parse_selection_keys((status or {}).get("selection"))
        transitions = derive_default_transitions(keys)
        if keys:
            states = [{"value": k, "label": k.replace("_", " ").title()} for k in keys]
            out = apply_state_field_to_model(model, states=states, transitions=transitions)
            warnings.append("step4: LLM failed — derived default transition chain")
            return out, warnings
        return model, warnings

    if len(samples) == 1:
        merged = samples[0]
        merge_w: list[str] = []
    else:
        merged, merge_w = merge_workflow_states(samples)
        warnings.extend(merge_w)

    state_keys = [
        str(s.get("value") or s.get("name") or s)
        if isinstance(s, dict)
        else str(s)
        for s in (merged.get("states") or [])
    ]
    transitions = [
        [str(tr[0]), str(tr[1])]
        for tr in (merged.get("transitions") or [])
        if isinstance(tr, (list, tuple)) and len(tr) >= 2
    ]
    if not transitions and state_keys:
        transitions = derive_default_transitions(state_keys)
        warnings.append("step4: derived default transitions from merged states")

    warnings.extend(validate_workflow_definition(state_keys, transitions))
    out = apply_state_field_to_model(
        model,
        states=merged.get("states") or state_keys,
        transitions=transitions,
    )
    return out, warnings


def step4_workflow_models(
    provider: LLMProvider,
    models: list[dict[str, Any]],
    *,
    user_prompt: str,
    guardrail: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        updated, w = step4_workflow_entity(
            provider, m, user_prompt=user_prompt, guardrail=guardrail
        )
        out.append(updated)
        warnings.extend(w)
    return out, warnings


def ensure_workflow_transitions_on_draft(draft: dict[str, Any]) -> list[str]:
    """Single pipeline: derive/validate transitions from x_status when state_field missing."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        sf = model.get("state_field")
        if isinstance(sf, dict) and sf.get("transitions"):
            continue
        status = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and f.get("name") == "x_status"
            ),
            None,
        )
        if not status:
            continue
        keys = parse_selection_keys(status.get("selection"))
        if len(keys) < 2:
            continue
        transitions = derive_default_transitions(keys)
        model["state_field"] = {
            "field": "x_status",
            "transitions": transitions,
            "states": keys,
        }
        model["is_workflow"] = True
        notes.append(
            f"quality: derived default transitions for {model.get('model')} ({len(transitions)} edges)"
        )
        notes.extend(validate_workflow_definition(keys, transitions))
    return notes


def transition_button_label(from_state: str, to_state: str) -> str:
    if to_state in {"cancelled", "canceled"}:
        return "Cancel"
    if to_state in {"done", "closed", "paid"}:
        return "Complete"
    if from_state == "draft" and to_state in {"open", "confirmed", "submitted"}:
        return "Confirm"
    return to_state.replace("_", " ").title()


def build_transition_header_buttons(
    transitions: list[list[str]],
) -> str:
    """Form header buttons derived from transition edges (draft metadata / enrich arch)."""
    if not transitions:
        return ""
    bits: list[str] = []
    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) < 2:
            continue
        a, b = str(tr[0]), str(tr[1])
        label = transition_button_label(a, b)
        bits.append(
            f'<button string="{label}" type="object" class="oe_highlight" '
            f'invisible="x_status != \'{a}\'" data-transition-to="{b}"/>'
        )
    return "".join(bits)
