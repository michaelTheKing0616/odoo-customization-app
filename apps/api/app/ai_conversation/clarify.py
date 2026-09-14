"""Clarification orchestrator — one question in flight, merge answers into prompt."""

from __future__ import annotations

import re
from typing import Any

from app.ai_conversation.intent_gate import IntentAssessment, merge_resolved_prompt

_TICKET_RE = re.compile(
    r"\b(tickets?|helpdesk|support\s+desk|it\s+support|internal\s+support)\b",
    re.I,
)


def _mentions_tickets(prompt: str) -> bool:
    return bool(_TICKET_RE.search(prompt or ""))


def _helpdesk_is_in_play(assessment: IntentAssessment) -> bool:
    blob = f"{assessment.competing_pack_id or ''} {' '.join(assessment.notes)}"
    return "helpdesk_tickets" in blob


def _pack_ambiguity_default(prompt: str) -> str:
    text = (prompt or "").lower()
    if re.search(r"\b(add|field|on\s+(invoices?|bills?|orders?|contacts?))\b", text):
        return "on_existing_form"
    return "transactional"


def build_clarification(assessment: IntentAssessment, prompt: str = "") -> dict[str, Any] | None:
    """Return a single clarifying question with quick-reply options."""
    trigger = assessment.primary_trigger()
    if trigger == "none" or assessment.clear:
        return None

    if trigger == "low_ir_confidence":
        return {
            "id": "ir_confidence",
            "merge_key": "ir_confidence",
            "question": "Should we build a new app, or only set up apps Odoo already includes?",
            "help": (
                "A new app gets its own records on the home screen. "
                "Standard apps means Sales, Invoicing, Inventory, and the rest — no new tile."
            ),
            "options": [
                {
                    "id": "residual_app",
                    "label": "Build a new app — people will open its records from the home screen",
                },
                {
                    "id": "stock_first",
                    "label": "Use Odoo’s standard apps only — Sales, Invoicing, Inventory…",
                },
            ],
            "default_id": "residual_app",
        }

    if trigger == "pack_conflict":
        return {
            "id": "pack_conflict",
            "merge_key": "pack_conflict",
            "question": "That doesn’t quite match a ready-made industry setup. How should we continue?",
            "help": "Pick the closest shape. You can still refine fields after the preview appears.",
            "options": [
                {
                    "id": "thin_ticket",
                    "label": "Staff support tickets — someone asks for help, someone closes it",
                },
                {
                    "id": "transactional",
                    "label": "One new kind of record — a request, log, or form people fill in",
                },
                {"id": "rephrase", "label": "I’ll describe it differently"},
            ],
            "default_id": "thin_ticket",
        }

    if trigger == "pack_ambiguity":
        options: list[dict[str, str]] = [
            {
                "id": "on_existing_form",
                "label": "Add it to a form you already use — bills, invoices, contacts…",
            },
        ]
        if _helpdesk_is_in_play(assessment) and _mentions_tickets(prompt):
            options.append(
                {
                    "id": "helpdesk_tickets",
                    "label": "Staff support tickets — someone asks for help, someone closes it",
                }
            )
        options.extend(
            [
                {
                    "id": "transactional",
                    "label": "Create a new kind of record on the home screen",
                },
                {"id": "rephrase", "label": "Neither — I’ll describe it differently"},
            ]
        )
        return {
            "id": "pack_choice",
            "merge_key": "pack_choice",
            "question": "Where should this live in Odoo?",
            "help": (
                "If you’re adding a field to vendor bills or invoices, pick the first option. "
                "If people need a brand-new record to fill in, pick the next."
            ),
            "options": options,
            "default_id": _pack_ambiguity_default(prompt),
        }

    if trigger == "rental_ambiguity":
        return {
            "id": "rental_domain",
            "merge_key": "rental_domain",
            "question": "What are you renting out?",
            "help": "This picks the right records — cars, equipment, or spaces.",
            "options": [
                {"id": "cars", "label": "Vehicles / car hire"},
                {"id": "equipment", "label": "Equipment"},
                {"id": "property", "label": "Property or event space"},
            ],
            "default_id": "cars",
        }

    if trigger == "material_ambiguity":
        return {
            "id": "residual",
            "merge_key": "residual",
            "question": "What should people create in Odoo?",
            "help": "This is the record they open, fill in, and follow through.",
            "options": [
                {
                    "id": "tickets",
                    "label": "Support tickets — someone asks for help, someone closes it",
                },
                {"id": "log", "label": "A simple list or register they update over time"},
                {"id": "other", "label": "Something else — I’ll type it below"},
            ],
            "default_id": "tickets",
        }

    return None


def _pack_choice_blob(answers: dict[str, str]) -> str:
    return " ".join(
        str(answers.get(key) or "") for key in ("pack_choice", "pack_conflict")
    ).lower()


def _chose_existing_form(answers: dict[str, str]) -> bool:
    blob = _pack_choice_blob(answers)
    return "on_existing_form" in blob or "form you already use" in blob


def _chose_simple_document(answers: dict[str, str]) -> bool:
    blob = _pack_choice_blob(answers)
    if _chose_existing_form(answers):
        return False
    return any(
        token in blob
        for token in (
            "transactional",
            "simple document",
            "new_document",
            "new kind of record",
        )
    )


def apply_clarification_answer(
    prompt: str,
    *,
    merge_key: str,
    answer_id: str,
    answer_text: str = "",
    resolved_answers: dict[str, str] | None = None,
    understanding: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str]]:
    """Merge chip or free-text answer into resolved answers and prompt."""
    answers = dict(resolved_answers or {})
    label = (answer_text or answer_id or "").strip()
    answers[merge_key] = label

    extra_lines: list[str] = []
    if merge_key == "ir_confidence":
        # "One simple document" already picked a custom x_* — do not wipe it
        # with the later stock-vs-custom chip (purchase-request empty canvas).
        if _chose_existing_form(answers):
            extra_lines.append("Inherit an existing Odoo form people already use.")
            extra_lines.append("Do not create a new home-screen app.")
        elif answer_id == "stock_first" and not _chose_simple_document(answers):
            extra_lines.append("Custom residual: None — stock Community apps only.")
            extra_lines.append("Capability path: stock_first")
        else:
            extra_lines.append("Custom residual: named in brief.")
            extra_lines.append("Capability path: residual_app")
            answers["ir_confidence"] = "residual_app"
    elif merge_key == "pack_conflict" and answer_id == "thin_ticket":
        extra_lines.append("Custom residual: tickets.")
        extra_lines.append("Out of scope: project, timesheet, ITSM.")
    elif merge_key == "pack_conflict" and answer_id in {"transactional", "new_document"}:
        extra_lines.append("Custom residual: named in brief.")
        extra_lines.append("Capability path: residual_app")
        answers["ir_confidence"] = "residual_app"
    elif merge_key == "rental_domain":
        domain_map = {
            "cars": "car rental",
            "equipment": "equipment rental",
            "property": "real estate rental",
        }
        extra_lines.append(f"Industry: {domain_map.get(answer_id, label)}")
    elif merge_key == "residual":
        if answer_id == "tickets":
            extra_lines.append("I want tickets with requester, status workflow, and time lines.")
        elif answer_id == "log":
            extra_lines.append("I want a simple log in Odoo.")
        elif label:
            extra_lines.append(f"Custom residual: {label}")
    elif merge_key == "pack_choice" and answer_id == "helpdesk_tickets":
        extra_lines.append("Helpdesk tickets — internal support, not project management.")
        answers["ir_confidence"] = "residual_app"
    elif merge_key == "pack_choice" and answer_id in {"transactional", "new_document"}:
        extra_lines.append("Custom residual: named in brief.")
        extra_lines.append("Capability path: residual_app")
        answers["ir_confidence"] = "residual_app"
    elif merge_key == "pack_choice" and answer_id == "on_existing_form":
        extra_lines.append("Inherit an existing Odoo form people already use.")
        extra_lines.append("Do not create a new home-screen app.")
        try:
            from app.ai_grain import preferred_inherit_host

            host = preferred_inherit_host(prompt)
            if host:
                extra_lines.append(f"Host: {host}")
        except Exception:  # noqa: BLE001
            pass
    elif merge_key == "diagnosis" and answer_id == "confirm":
        from app.ai_conversation.understand import (
            DIAGNOSIS_KEY,
            append_locked_diagnosis,
            apply_understanding_edits,
            dump_understanding,
            load_understanding,
        )

        answers[DIAGNOSIS_KEY] = "confirm"
        locked = load_understanding(answers)
        if locked:
            locked = apply_understanding_edits(locked, understanding)
            dump_understanding(answers, locked)
            extra_lines.append(append_locked_diagnosis("", locked).lstrip())
    elif merge_key == "diagnosis" and answer_id == "reject":
        from app.ai_conversation.understand import DIAGNOSIS_KEY

        answers[DIAGNOSIS_KEY] = "reject"

    merged = merge_resolved_prompt(prompt, answers)
    if extra_lines:
        merged = merged + "\n" + "\n".join(extra_lines)
    return merged, answers


def vague_refinement_needs_followup(instruction: str) -> dict[str, Any] | None:
    """Detect ambiguous refinement instructions like 'make it better'."""
    text = (instruction or "").strip().lower()
    if not text:
        return None
    vague = re.search(
        r"(?i)^(make it better|improve it|change the layout|fix it|clean it up)\.?$",
        text,
    )
    if not vague:
        return None
    return {
        "id": "refine_vague",
        "merge_key": "refine_vague",
        "question": "What should change on this form?",
        "help": "A specific change is faster than a general polish.",
        "options": [
            {"id": "more_fields", "label": "Show more fields on the form"},
            {"id": "simpler", "label": "Simpler form — hide optional fields"},
            {"id": "required", "label": "Make key fields required"},
        ],
        "default_id": "more_fields",
    }


__all__ = [
    "apply_clarification_answer",
    "build_clarification",
    "vague_refinement_needs_followup",
]
