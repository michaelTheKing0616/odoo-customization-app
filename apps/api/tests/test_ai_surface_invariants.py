"""Surface invariants are properties + mutants, not screenshot denylists.

This file must not mention yesterday's bug names. If a new operator failure
appears, add a *class* (invariant) and a mutant here — never
``if display_name == "…"``.
"""

from __future__ import annotations

from app.ai_document_compiler import compile_document_grammar, premium_surface_findings
from app.ai_live_apply_contract import live_apply_contract_findings
from app.ai_surface_invariants import (
    extract_brief_slots,
    is_ir_jargon_title,
    mutate_identity_spray,
    mutate_isomorphic_siblings,
    mutate_stale_preview_tabs,
    mutate_ungrounded_title,
    surface_invariant_findings,
    title_is_grounded,
)

# Deliberately not the purchase-request screenshot. Same *classes* of failure.
LEAVE = (
    "Leave requests with a start date. An approver must approve or refuse it. "
    "Notify the approver with a to-do."
)
EXPENSE = (
    "Expense claims with a fee and currency. The submitter files the claim; "
    "a reviewer must approve or refuse it. Notify the reviewer with a to-do."
)
VISITOR = "Visitor log with visitor name and company and time in."
PURCHASE = (
    "Purchase requests with an amount and currency. "
    "The requester files it; a manager must approve or refuse. "
    "When waiting, notify the manager with a to-do."
)

THIN_PROMPTS = (LEAVE, EXPENSE, VISITOR, PURCHASE)


def _seed(prompt: str) -> dict:
    return {
        "display_name": "Untitled",
        "technical_name": "untitled",
        "_user_prompt": prompt,
        "depends": ["base"],
        "models": [
            {
                "model": "x_header",
                "mode": "new",
                "description": "Header",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                ],
            }
        ],
        "menus": [
            {"name": "Untitled", "xml_id": "menu_root", "technical_name": "root"},
            {
                "name": "Items",
                "action_xml_id": "action_x_header",
                "parent_xml_id": "menu_root",
            },
        ],
    }


def _attack(prompt: str) -> dict:
    """Apply every failure class at once, with labels that are not prior bugs."""
    draft = _seed(prompt)
    draft = mutate_ungrounded_title(draft, "Capability Path")
    draft = mutate_identity_spray(draft)
    draft = mutate_isomorphic_siblings(draft, names=("Folio", "Docket"))
    draft = mutate_stale_preview_tabs(draft)
    return draft


def test_brief_slots_are_synonym_aware() -> None:
    leave = extract_brief_slots(LEAVE)
    assert leave.wants_approval
    assert leave.wants_todo
    assert any(p.lemma == "approver" and p.relation == "res.users" for p in leave.people)
    expense = extract_brief_slots(EXPENSE)
    assert expense.wants_money
    assert any(p.lemma == "submitter" for p in expense.people)
    assert any(p.lemma == "reviewer" and p.relation == "res.users" for p in expense.people)
    visitor = extract_brief_slots(VISITOR)
    assert not visitor.wants_money
    assert not visitor.wants_approval


def test_title_grounding_is_a_class_not_a_string() -> None:
    assert is_ir_jargon_title("Capability Path")
    assert is_ir_jargon_title("Custom residual")
    assert not title_is_grounded("Capability Path", LEAVE)
    assert title_is_grounded("Leave Requests", LEAVE)
    assert not title_is_grounded("Folio Ledger", LEAVE)


def test_gate_fails_before_compile_on_mutants() -> None:
    draft = _attack(LEAVE)
    findings = surface_invariant_findings(draft)
    assert findings, "gate must see ungrounded title / extra siblings / spray before compile"
    blob = " ".join(findings).lower()
    assert "grounded" in blob or "isomorphic" in blob or "thin" in blob


def test_mutants_compile_clean_across_unseen_prompts() -> None:
    for prompt in THIN_PROMPTS:
        draft = _attack(prompt)
        compile_document_grammar(draft, prompt=prompt)
        findings = premium_surface_findings(draft)
        assert not findings, (prompt, findings)
        live = live_apply_contract_findings(draft)
        assert not any(str(f.get("detail") or "").startswith("surface:") for f in live), (
            prompt,
            live,
        )
        extra = (draft.get("_document_grammar") or {}).get("extra_apps")
        assert extra == 0, (prompt, extra)
        models = [
            str(m.get("model"))
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
        ]
        assert "x_folio" not in models
        assert "x_docket" not in models
        header = next(
            m
            for m in draft["models"]
            if isinstance(m, dict) and not str(m.get("model")).endswith("_line")
        )
        names = {str(f.get("name")) for f in header.get("fields") or [] if isinstance(f, dict)}
        assert "x_contact_id" not in names
        preview_pages = 0
        ir = draft.get("_generation_engine") or {}
        for nb in (ir.get("form_preview") or {}).get("notebooks") or []:
            preview_pages += len((nb or {}).get("pages") or [])
        o2m = sum(
            1
            for f in header.get("fields") or []
            if isinstance(f, dict) and f.get("ttype") in {"one2many", "many2many"}
        )
        assert preview_pages <= o2m, (prompt, preview_pages, o2m)


def test_invariants_module_does_not_denylist_prior_screenshots() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("app/ai_surface_invariants.py").read_text(
        encoding="utf-8"
    )
    for banned in ("Agreements", "Expenses", "Named In Brief"):
        assert banned not in src
