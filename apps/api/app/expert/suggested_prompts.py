"""Contextual suggested prompts for Expert panel and command palette."""

from __future__ import annotations

from typing import Any


def _route_key(route: str | None) -> str:
    r = (route or "").lower()
    if "/wizard" in r:
        return "wizard"
    if "/builder" in r:
        return "builder"
    if "/bulk" in r:
        return "bulk"
    if "/automations" in r or "/studio" in r:
        return "automations"
    if "/ingest" in r or "/import" in r:
        return "ingest"
    if "/deploy" in r:
        return "deploy"
    if "/validate" in r:
        return "validate"
    return "default"


def suggested_prompts_for_context(
    *,
    route: str | None = None,
    model: str | None = None,
    view_type: str | None = None,
    draft_summary: str | None = None,
) -> list[dict[str, str]]:
    """Return {id, label, question} prompts for the current screen."""
    key = _route_key(route)
    prompts: list[dict[str, str]] = []

    base: dict[str, list[tuple[str, str]]] = {
        "wizard": [
            ("draft-score", "Why is my draft score low?", "What are the top reasons my AI draft score might be below 9/10 and how do I fix them?"),
            ("workflow", "Workflow best practices", "How should I structure selection fields and statusbar workflows for a custom Odoo app?"),
            ("reuse", "When to reuse stock models", "When should I link to stock Odoo models instead of creating parallel custom models?"),
        ],
        "builder": [
            ("view-xpath", "View inheritance tips", "How do I safely inherit and extend Odoo form views with xpath for Community?"),
            ("field-types", "Pick the right field type", "How do I choose between char, selection, many2one, and one2many for this model?"),
            ("search-view", "Search view filters", "What makes a good search view and filter setup for a custom model?"),
        ],
        "bulk": [
            ("mass-edit", "Safe mass edit", "What fields are safe to mass-edit on custom models and what should I avoid?"),
            ("export", "Export limits", "How does Odoo Community handle bulk export and what RPC limits apply?"),
        ],
        "automations": [
            ("trigger", "Automation triggers", "When should I use on_create vs on_write vs on_change for base.automation?"),
            ("domain", "Automation domains", "How do I write safe domains for automations on custom x_ models?"),
        ],
        "ingest": [
            ("mapping", "CSV field mapping", "How should I map CSV columns to Odoo fields for initial data import?"),
        ],
        "deploy": [
            ("sandbox", "Sandbox before prod", "Why must I test generated modules in sandbox before installing on production?"),
        ],
        "validate": [
            ("readiness", "Go-live checklist", "What should I verify on a custom Odoo app before go-live?"),
        ],
        "default": [
            ("modules", "Module dependencies", "How do I choose depends[] for a custom Odoo module in Community?"),
            ("security", "Groups and rules", "How should record rules and groups be set up for a multi-branch custom app?"),
        ],
    }

    for pid, label, question in base.get(key, base["default"]):
        prompts.append({"id": pid, "label": label, "question": question})

    m = (model or "").strip()
    if m:
        if m.startswith("x_"):
            prompts.insert(
                0,
                {
                    "id": "explain-model",
                    "label": f"Explain {m}",
                    "question": f"Explain model `{m}` — fields, workflow, and how it fits this connection.",
                },
            )
        elif m in {"sale.order", "purchase.order", "stock.picking", "account.move"}:
            prompts.insert(
                0,
                {
                    "id": "protected",
                    "label": f"Customize near {m}",
                    "question": f"I need customization near `{m}`. What is the safe Community path without mutating tier-1 records?",
                },
            )
        else:
            prompts.insert(
                0,
                {
                    "id": "model-context",
                    "label": f"About {m}",
                    "question": f"What should I know about `{m}` when extending it in Odoo Community?",
                },
            )

    if draft_summary:
        prompts.insert(
            0,
            {
                "id": "draft-context",
                "label": "Review my draft",
                "question": f"Review this draft context: {draft_summary[:200]}. What gaps should I fix first?",
            },
        )

    vt = (view_type or "").lower()
    if vt == "form":
        prompts.append(
            {
                "id": "form-layout",
                "label": "Form layout tips",
                "question": "How should I organize notebook pages and smart buttons on a custom form view?",
            }
        )

    # Dedupe by id, cap at 8
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for p in prompts:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
        if len(out) >= 8:
            break
    return out


__all__ = ["suggested_prompts_for_context"]
