"""Craft smart buttons — Diagnosis Nice-to-have chips → Generate gate."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db
os.environ["AI_INTENT_LLM"] = "off"

from app.ai_craft_smart_buttons import propose_craft_smart_buttons  # noqa: E402
from app.ai_conversation.understand import (  # noqa: E402
    append_locked_diagnosis,
    apply_understanding_edits,
    attach_understanding,
    build_understanding,
    diagnosis_clarification,
)
from app.ai_operator_surface import attach_operator_surface, build_operator_surface  # noqa: E402
from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons  # noqa: E402
from app.ai_grain import classify_grain  # noqa: E402
from app.ai_operator_brief import intent_corpus  # noqa: E402

VISITOR = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

PREFER = (
    "On Contacts (res.partner), add checkbox Preferred for delivery and "
    "Delivery notes text under Delivery group. Do not create a new app."
)

PUNCH = (
    "We already use Community POS. What we don’t have is a simple loyalty punch card: "
    "buy 9 coffees get the 10th free, tied to the customer (Contacts)."
)


def test_visitor_log_proposes_employee_visits_craft_chip() -> None:
    u = build_understanding(VISITOR)
    props = u.craft_proposals
    assert props, "expected craft proposals on Visitor Log"
    assert props[0]["on_model"] == "hr.employee"
    assert props[0]["label"] == "Visits"
    assert props[0]["default_on"] is True
    assert props[0]["related_model"] == "x_visitor_log"
    if len(props) > 1:
        assert props[1]["default_on"] is False
    card = diagnosis_clarification(u)
    assert "«Visits» on Employees" in (card.get("nice_to_have") or [])


def test_removed_craft_chip_not_in_generate_ir() -> None:
    u = build_understanding(VISITOR)
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": [],
        },
    )
    assert locked.craft_smart_buttons == []
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "hr.employee",
                "label": "Visits",
                "related_model": "x_visitor_log",
                "relation_field": "x_host_id",
            }
        ],
        "_understanding": locked.to_dict(),
    }
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    hosts = {
        str(b.get("on_model"))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    assert "hr.employee" not in hosts
    assert "res.partner" not in hosts


def test_confirmed_craft_chip_stamped_on_generate() -> None:
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": kept,
        },
    )
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [],
        "_understanding": locked.to_dict(),
    }
    notes = apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert any("craft_smart_btn" in n for n in notes)
    btns = [b for b in draft["smart_buttons"] if isinstance(b, dict)]
    assert len(btns) == 1
    assert btns[0]["on_model"] == "hr.employee"
    assert btns[0]["source"] == "craft_confirmed"
    surface = build_operator_surface(draft)
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    assert "hr.employee" in hosts


def test_silent_invent_still_blocked_without_craft() -> None:
    draft = {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                ],
            }
        ],
        "smart_buttons": [],
        "_understanding": {"grain": "full_app", "craft_smart_buttons": []},
    }
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert draft.get("smart_buttons") == []


def test_prefer_contacts_unchanged_no_craft() -> None:
    u = build_understanding(PREFER)
    assert u.inherit_existing is True
    assert u.host_model == "res.partner"
    assert propose_craft_smart_buttons(PREFER, u) == []
    assert u.craft_proposals == []


def test_punch_partner_tie_still_gets_contacts_without_craft() -> None:
    draft = {
        "display_name": "Punch Card",
        "grain": "full_app",
        "_user_prompt": PUNCH,
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [],
    }
    apply_stock_host_smart_buttons(draft, prompt=PUNCH)
    hosts = {b["on_model"] for b in draft["smart_buttons"]}
    assert "res.partner" in hosts


def _visitor_draft() -> dict:
    return {
        "display_name": "Visitor Log",
        "grain": "full_app",
        "_user_prompt": VISITOR,
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [
                    {"name": "x_host_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "smart_buttons": [],
        "menus": [{"name": "Visitor Log", "technical_name": "visitor_log_root"}],
    }


def test_locked_employees_craft_survives_attach_and_find_it() -> None:
    """Session craft must reach apply_stock + find-it (not zeroed by attach rebuild)."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    assert kept and kept[0]["on_model"] == "hr.employee"
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": kept,
        },
    )
    # Live-shaped prompt: may or may not include locked block; session IR is source of truth.
    prompt = append_locked_diagnosis(VISITOR, locked)
    draft = _visitor_draft()
    # Invent residual that must not appear on find-it.
    draft["smart_buttons"] = [
        {
            "on_model": "res.partner",
            "label": "Visitor Logs",
            "related_model": "x_visitor_log",
            "relation_field": "x_company_id",
            "source": "odoo_app_bar",
        }
    ]
    attach_understanding(draft, prompt, locked=locked.to_dict())
    assert draft["_understanding"]["craft_smart_buttons"]
    assert draft["_understanding"]["craft_smart_buttons"][0]["on_model"] == "hr.employee"
    apply_stock_host_smart_buttons(draft, prompt=prompt)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    assert hosts == {"hr.employee"}
    labels = {b.get("button_label") for b in surface["host_buttons"]}
    assert labels == {"Visits"}
    assert "Contacts" not in (surface.get("summary") or "")
    assert "Visitor Logs" not in (surface.get("summary") or "")
    assert "Visits" in (surface.get("summary") or "")


def test_attach_without_locked_block_preserves_session_craft() -> None:
    """Generate often re-attaches from prompt alone — session locked must still win."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": kept,
        },
    )
    draft = _visitor_draft()
    # Raw brief only — no ## Diagnosis (locked) block (the old zeroing path).
    attach_understanding(draft, VISITOR, locked=locked.to_dict())
    assert len(draft["_understanding"]["craft_smart_buttons"]) == 1
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    attach_operator_surface(draft)
    hosts = {b["host_model"] for b in draft["_operator_surface"]["host_buttons"]}
    assert hosts == {"hr.employee"}


def test_empty_craft_find_it_has_no_stock_host_line() -> None:
    locked = apply_understanding_edits(
        build_understanding(VISITOR),
        {
            "craft_smart_buttons": [],
            "inherit_existing": False,
            "needs_module": False,
        },
    )
    draft = _visitor_draft()
    draft["smart_buttons"] = [
        {
            "on_model": "res.partner",
            "label": "Visitor Logs",
            "related_model": "x_visitor_log",
            "relation_field": "x_company_id",
        },
        {
            "on_model": "hr.employee",
            "label": "Visits",
            "related_model": "x_visitor_log",
            "relation_field": "x_host_id",
        },
    ]
    attach_understanding(draft, VISITOR, locked=locked.to_dict())
    assert draft["_understanding"]["craft_smart_buttons"] == []
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    assert surface["host_buttons"] == []
    summary = surface.get("summary") or ""
    assert "Also on stock forms" not in summary
    assert "Contacts" not in summary or "form fields" in summary.lower()


def test_feature_slice_grain_flip_still_craft_gates_find_it() -> None:
    """Locked full_app + invent Contacts «Visitor Logs» + draft grain feature_slice.

    Live bug: Gemini/locked-chrome flipped grain → residual find-it gate skipped →
    banner «Also on stock forms: «Visitor Logs» on Contacts». Craft Employees only
    must win («Visits»), never invent Contacts / pluralized app name.
    """
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    assert kept and kept[0]["on_model"] == "hr.employee"
    locked = apply_understanding_edits(
        u,
        {
            "title": u.title,
            "constraints": u.constraints,
            "inherit_existing": False,
            "needs_module": False,
            "craft_smart_buttons": kept,
            "grain": "full_app",
        },
    )
    draft = _visitor_draft()
    draft["grain"] = "feature_slice"
    draft["_generation_engine"] = {"grain": "feature_slice", "capability": "residual_app"}
    draft["smart_buttons"] = [
        {
            "on_model": "res.partner",
            "label": "Visitor Logs",
            "related_model": "x_visitor_log",
            "relation_field": "x_company_id",
            "source": "odoo_app_bar",
        }
    ]
    # Stamp locked understanding without relying on attach flipping grain first —
    # surface must still craft-gate when understanding carries locked full_app.
    draft["_understanding"] = locked.to_dict()
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    summary = surface.get("summary") or ""
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    labels = {b.get("button_label") for b in surface.get("host_buttons") or []}
    assert hosts == {"hr.employee"}, hosts
    assert labels == {"Visits"}, labels
    assert "Visitor Logs" not in summary
    assert "on Contacts" not in summary
    assert "Visits" in summary and "Employees" in summary


def test_feature_slice_empty_craft_no_stock_host_line() -> None:
    """Empty craft_smart_buttons + feature_slice draft grain → no Also-on-stock-forms."""
    locked = apply_understanding_edits(
        build_understanding(VISITOR),
        {
            "craft_smart_buttons": [],
            "inherit_existing": False,
            "needs_module": False,
            "grain": "full_app",
        },
    )
    draft = _visitor_draft()
    draft["grain"] = "feature_slice"
    draft["_generation_engine"] = {"grain": "feature_slice"}
    draft["_understanding"] = locked.to_dict()
    draft["smart_buttons"] = [
        {
            "on_model": "res.partner",
            "label": "Visitor Logs",
            "related_model": "x_visitor_log",
            "relation_field": "x_company_id",
        },
        {
            "on_model": "hr.employee",
            "label": "Visits",
            "related_model": "x_visitor_log",
            "relation_field": "x_host_id",
        },
    ]
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    assert surface["host_buttons"] == []
    summary = surface.get("summary") or ""
    assert "Also on stock forms" not in summary
    assert "Visitor Logs" not in summary


def test_locked_diagnosis_chrome_does_not_flip_grain_via_intent_corpus() -> None:
    """## Diagnosis (locked) craft lines must not make classify_grain → feature_slice."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "craft_smart_buttons": kept,
            "inherit_existing": False,
            "needs_module": False,
            "grain": "full_app",
        },
    )
    prompt = append_locked_diagnosis(VISITOR, locked)
    # Raw classify may still see "Inherit"/"smart button" if corpus kept Diagnosis;
    # intent_corpus must drop Diagnosis so Generate grain stays full_app.
    corpus = intent_corpus(prompt)
    assert "Craft smart button" not in corpus
    assert classify_grain(corpus or prompt) == "full_app"
    # attach restores draft grain even if someone stamped feature_slice.
    draft = _visitor_draft()
    draft["grain"] = "feature_slice"
    draft["_generation_engine"] = {"grain": "feature_slice"}
    attach_understanding(draft, prompt, locked=locked.to_dict())
    assert draft["grain"] == "full_app"
    assert draft["_generation_engine"]["grain"] == "full_app"


def test_prefer_contacts_inherit_unchanged_with_feature_slice_path() -> None:
    """Prefer Contacts inherit is not residual craft-gated."""
    surface = build_operator_surface(
        {
            "display_name": "Contacts field",
            "technical_name": "contacts_field",
            "grain": "field_pack",
            "_generation_engine": {"grain": "field_pack", "host_model": "res.partner"},
            "models": [{"model": "res.partner", "mode": "inherit", "fields": []}],
            "menus": [],
            "smart_buttons": [
                {
                    "on_model": "res.partner",
                    "label": "Notes",
                    "related_model": "x_note",
                    "relation_field": "x_partner_id",
                }
            ],
            "_understanding": {
                "grain": "field_pack",
                "inherit_existing": True,
                "host_model": "res.partner",
            },
            "_user_prompt": PREFER,
        }
    )
    # Inherit Preferred Contacts still may list host buttons — not craft-scrubbed away.
    assert "residual app" not in (surface.get("summary") or "").lower() or "Contacts" in (
        surface.get("summary") or ""
    )
