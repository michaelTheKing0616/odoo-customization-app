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
        "cleared",
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
        "blocked",
    }
)
_INITIAL_STATES = frozenset({"draft", "new", "intake"})
_ALLOWED_INITIAL_TERMINALS = frozenset({"cancelled", "canceled", "rejected"})
# Odoo ``action_draft`` / Reset to Draft — terminal-negative → working copy.
_RESET_TO_DRAFT_DEST = frozenset({"draft", "new", "pending"})


def classify_state(key: str) -> str:
    k = key.lower().strip()
    if k in _TERMINAL_SUCCESS:
        return "terminal_success"
    if k in _TERMINAL_NEGATIVE:
        return "terminal_negative"
    return "active"


def is_reset_to_draft_edge(src: str, dest: str) -> bool:
    """True for Odoo-style Reset to Draft (blocked/cancelled → pending/draft/new)."""
    return (
        classify_state(str(src)) == "terminal_negative"
        and str(dest).lower().strip() in _RESET_TO_DRAFT_DEST
    )


_LIFECYCLE_RANK: dict[str, int] = {}
for _i, _k in enumerate(
    (
        "planned",
        "draft",
        "new",
        "intake",  # matter / case files — before open (Confirm)
        "pending",
        "submitted",
        "qualified",
        "engaged",
        "confirmed",
        "open",
        "active",
        "in_progress",
        "picking",
        "processing",
        "review",
        "approved",
        "billed",  # invoiced / fee collected — before closed
        "on_hold",
        "cleared",
        "blocked",
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


def _transitions_look_pack_intentional(
    keys: list[str],
    transitions: list[Any],
) -> bool:
    """True when pack/LLM already left a Confirm-shaped edge we must not scramble."""
    keyset = {str(k).lower() for k in keys}
    edges: list[tuple[str, str]] = []
    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) < 2:
            continue
        a, b = str(tr[0]).lower(), str(tr[1]).lower()
        if a not in keyset or b not in keyset:
            return False
        edges.append((a, b))
    if not edges:
        return False
    # Confirm: intake|draft|new → open|confirmed
    if any(
        a in {"intake", "draft", "new"} and b in {"open", "confirmed", "qualified"}
        for a, b in edges
    ):
        return True
    # Clearance / check workflows: pending → cleared|blocked (not a linear chain)
    if any(a == "pending" and b in {"cleared", "blocked", "approved", "rejected"} for a, b in edges):
        return True
    return False


def _force_confirm_shaped_chain(
    keys: list[str], transitions: list[list[str]]
) -> list[list[str]]:
    """Hard rule: when intake|draft|new and open|confirmed coexist, Confirm is that edge.

    Never leave open→intake or intake→billed as the primary advance.
    """
    keyset = {str(k).lower() for k in keys}
    initial = next((k for k in ("intake", "draft", "new") if k in keyset), None)
    opened = next((k for k in ("open", "confirmed") if k in keyset), None)
    if not initial or not opened:
        return _drop_outgoing_from_terminals(
            [
                [str(tr[0]), str(tr[1])]
                for tr in transitions
                if isinstance(tr, (list, tuple)) and len(tr) >= 2
            ]
        )
    initial_key = next(k for k in keys if str(k).lower() == initial)
    opened_key = next(k for k in keys if str(k).lower() == opened)
    cleaned: list[list[str]] = []
    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) < 2:
            continue
        a, b = str(tr[0]).lower(), str(tr[1]).lower()
        if a == opened and b == initial:
            continue
        if a == initial and b not in {opened, "cancelled", "canceled", "rejected"}:
            continue
        cleaned.append([str(tr[0]), str(tr[1])])
    if not any(
        str(tr[0]).lower() == initial and str(tr[1]).lower() == opened for tr in cleaned
    ):
        cleaned.insert(0, [initial_key, opened_key])
    return _drop_outgoing_from_terminals(cleaned)


_TERMINAL_STATES = frozenset(
    {
        "delivered",
        "cancelled",
        "canceled",
        "done",
        "closed",
        "expired",
        "rejected",
    }
)


def _drop_outgoing_from_terminals(transitions: list[list[str]]) -> list[list[str]]:
    """Terminals have no outgoing edges — even when a pack Confirm chain is kept."""
    out: list[list[str]] = []
    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) < 2:
            continue
        if str(tr[0]).lower() in _TERMINAL_STATES:
            continue
        out.append([str(tr[0]), str(tr[1])])
    return out


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
    existing = sf.get("transitions") if isinstance(sf.get("transitions"), list) else []
    if existing and _transitions_look_pack_intentional(keys, existing):
        # Keep pack Confirm chain; refresh statusbar + force Confirm edge
        _, visible = synthesize_semantic_transitions(keys)
        sf["states"] = order_states_by_lifecycle(keys)
        sf["statusbar_visible"] = visible
        sf["transitions"] = _force_confirm_shaped_chain(keys, list(existing))
        model["state_field"] = sf
        notes.append(
            f"workflow: preserved pack transitions on {model.get('model')} "
            f"({len(sf['transitions'])} edges)"
        )
        return notes
    transitions, visible = synthesize_semantic_transitions(keys)
    transitions = _force_confirm_shaped_chain(keys, transitions)
    sf["transitions"] = transitions
    sf["states"] = order_states_by_lifecycle(keys)
    sf["statusbar_visible"] = visible
    model["state_field"] = sf
    notes.append(
        f"workflow: semantic transitions on {model.get('model')} "
        f"({len(transitions)} edges, {len(visible)} statusbar)"
    )
    return notes


_LINE_BILLING_STATUS_KEYS = frozenset(
    {
        "submitted",
        "approved",
        "billed",
        "written_off",
        "invoiced",
        "to_invoice",
    }
)


def strip_non_workflow_state(model: dict[str, Any]) -> list[str]:
    """Remove state_field / leftover workflow status from non-workflow models.

    ``*_line`` billing flags (draft/submitted/billed) are scalar columns, not
    document workflows — keep the selection, never a Confirm/kanban header.
    """
    notes: list[str] = []
    if model.get("is_workflow"):
        return notes
    mid = str(model.get("model") or "")
    if model.pop("state_field", None):
        notes.append(f"workflow: stripped state_field from non-workflow {mid}")
    fields = model.get("fields")
    if not isinstance(fields, list):
        return notes
    keep_line_status = mid.endswith("_line") or mid.endswith("_time")
    kept: list[dict[str, Any]] = []
    for f in fields:
        if not isinstance(f, dict):
            kept.append(f)
            continue
        if f.get("ttype") == "selection" and str(f.get("name", "")).endswith("_status"):
            keys = set(re.findall(r"\(\s*'([^']+)'\s*,", str(f.get("selection") or "")))
            if keep_line_status or (keys & _LINE_BILLING_STATUS_KEYS):
                kept.append(f)
                continue
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
    from app.ai_model_quality import demote_spurious_link_workflows

    notes.extend(demote_spurious_link_workflows(draft))
    return notes


__all__ = [
    "_ALLOWED_INITIAL_TERMINALS",
    "_INITIAL_STATES",
    "apply_semantic_workflow_pass",
    "classify_state",
    "is_reset_to_draft_edge",
    "strip_non_workflow_state",
    "synthesize_semantic_transitions",
]
