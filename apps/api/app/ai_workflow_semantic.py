"""Semantic workflow transition synthesis (GEN2-3)."""

from __future__ import annotations

import re
from typing import Any

_TERMINAL_SUCCESS = frozenset(
    {
        "done",
        "closed",
        "complete",
        "completed",
        "delivered",
        "received",
        "paid",
        "passed",
        "approved",
        "posted",
        "confirmed_done",
    }
)
_TERMINAL_NEGATIVE = frozenset(
    {
        "cancelled",
        "canceled",
        "void",
        "voided",
        "failed",
        "expired",
        "rejected",
        "refused",
    }
)
_INITIAL_STATES = frozenset({"draft", "new"})
_ALLOWED_INITIAL_TERMINALS = frozenset({"cancelled", "canceled", "rejected"})


def classify_state(key: str) -> str:
    k = key.lower().strip()
    if k in _TERMINAL_SUCCESS:
        return "terminal_success"
    if k in _TERMINAL_NEGATIVE:
        return "terminal_negative"
    return "active"


_LIFECYCLE_RANK: dict[str, int] = {}
for _i, _k in enumerate(
    (
        "planned",
        "draft",
        "new",
        "submitted",
        "confirmed",
        "open",
        "active",
        "in_progress",
        "picking",
        "processing",
        "review",
        "approved",
        "done",
        "closed",
        "delivered",
        "received",
        "paid",
        "passed",
        "posted",
        "cancelled",
        "canceled",
        "void",
        "failed",
        "expired",
        "rejected",
    )
):
    _LIFECYCLE_RANK.setdefault(_k, _i)


def order_states_by_lifecycle(keys: list[str]) -> list[str]:
    """Order selection keys by lifecycle lexicon instead of LLM listing order."""

    def rank(k: str) -> tuple[int, int]:
        kl = k.lower().strip()
        return (_LIFECYCLE_RANK.get(kl, 50), keys.index(k))

    return sorted(keys, key=rank)


def synthesize_semantic_transitions(keys: list[str]) -> tuple[list[list[str]], list[str]]:
    """Active chain + branch to terminals; terminals have no outgoing edges."""
    if not keys:
        return [], []
    keys = order_states_by_lifecycle(keys)
    active: list[str] = []
    terminal_success: list[str] = []
    terminal_negative: list[str] = []
    for k in keys:
        kind = classify_state(k)
        if kind == "terminal_success":
            terminal_success.append(k)
        elif kind == "terminal_negative":
            terminal_negative.append(k)
        else:
            active.append(k)

    transitions: list[list[str]] = []
    for i in range(len(active) - 1):
        transitions.append([active[i], active[i + 1]])
    for a in active:
        for neg in terminal_negative:
            if (
                a.lower() in _INITIAL_STATES
                and neg.lower() not in _ALLOWED_INITIAL_TERMINALS
            ):
                continue
            transitions.append([a, neg])
    if active and terminal_success:
        transitions.append([active[-1], terminal_success[0]])

    statusbar_visible = active + terminal_success
    return transitions, statusbar_visible


def apply_semantic_transitions_to_model(model: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not model.get("is_workflow"):
        return notes
    sf = model.get("state_field")
    if not isinstance(sf, dict):
        return notes
    from app.ai_workflow import parse_selection_keys

    field_name = str(sf.get("field") or "x_status")
    keys = list(sf.get("states") or [])
    if not keys:
        for f in model.get("fields") or []:
            if isinstance(f, dict) and f.get("name") == field_name:
                keys = parse_selection_keys(f.get("selection"))
                break
    if not keys:
        return notes
    transitions, visible = synthesize_semantic_transitions(keys)
    sf["transitions"] = transitions
    sf["states"] = keys
    sf["statusbar_visible"] = visible
    model["state_field"] = sf
    notes.append(
        f"workflow: semantic transitions on {model.get('model')} "
        f"({len(transitions)} edges, {len(visible)} statusbar)"
    )
    return notes


def strip_non_workflow_state(model: dict[str, Any]) -> list[str]:
    """Remove state_field / status selection from non-workflow models."""
    notes: list[str] = []
    if model.get("is_workflow"):
        return notes
    mid = str(model.get("model") or "")
    if model.pop("state_field", None):
        notes.append(f"workflow: stripped state_field from non-workflow {mid}")
    fields = model.get("fields")
    if not isinstance(fields, list):
        return notes
    kept: list[dict[str, Any]] = []
    for f in fields:
        if not isinstance(f, dict):
            kept.append(f)
            continue
        if f.get("ttype") == "selection" and str(f.get("name", "")).endswith("_status"):
            notes.append(f"workflow: stripped status selection on non-workflow {mid}")
            continue
        kept.append(f)
    model["fields"] = kept
    return notes


def apply_semantic_workflow_pass(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        notes.extend(strip_non_workflow_state(model))
        if model.get("is_workflow"):
            notes.extend(apply_semantic_transitions_to_model(model))
    return notes


__all__ = [
    "_ALLOWED_INITIAL_TERMINALS",
    "_INITIAL_STATES",
    "apply_semantic_workflow_pass",
    "classify_state",
    "strip_non_workflow_state",
    "synthesize_semantic_transitions",
]
