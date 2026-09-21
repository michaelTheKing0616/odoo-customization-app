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
from app.ai_odoo_app_bar import humanize_app_surface  # noqa: E402
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
    # Empty craft must scrub invent from IR — not only hide on find-it.
    assert not any(
        isinstance(b, dict) and str(b.get("on_model") or "") in {"res.partner", "hr.employee"}
        for b in (draft.get("smart_buttons") or [])
    )
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    assert surface["host_buttons"] == []
    summary = surface.get("summary") or ""
    assert "Also on stock forms" not in summary
    assert "Visitor Logs" not in summary
    assert "Customer, Last Transaction" not in summary


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


def test_humanize_does_not_pluralize_craft_visits_label() -> None:
    """humanize_app_surface must not rewrite «Visits» → «Visitor Logs»."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "title": "Visitor Log",
            "craft_smart_buttons": kept,
            "inherit_existing": False,
            "needs_module": False,
            "grain": "full_app",
        },
    )
    draft = _visitor_draft()
    draft["models"][0]["description"] = "Visitor Log"
    attach_understanding(draft, VISITOR, locked=locked.to_dict())
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert any(
        b.get("label") == "Visits" and b.get("on_model") == "hr.employee"
        for b in draft["smart_buttons"]
        if isinstance(b, dict)
    )
    humanize_app_surface(draft)
    labels = {
        (b.get("on_model"), b.get("label"))
        for b in draft["smart_buttons"]
        if isinstance(b, dict)
    }
    assert ("hr.employee", "Visits") in labels
    assert not any(lab == "Visitor Logs" for _, lab in labels)
    attach_operator_surface(draft)
    summary = draft["_operator_surface"].get("summary") or ""
    assert "Visits" in summary and "Employees" in summary
    assert "Visitor Logs" not in summary
    assert "on Contacts" not in summary
    assert "Customer, Last Transaction" not in summary


def test_illicit_craft_confirmed_contacts_dropped_when_craft_is_employees() -> None:
    """Source=craft_confirmed on Contacts must not bypass craft-only ⊆ Employees."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    assert kept and kept[0]["on_model"] == "hr.employee"
    locked = apply_understanding_edits(
        u,
        {
            "craft_smart_buttons": kept,
            "inherit_existing": False,
            "grain": "full_app",
        },
    )
    draft = _visitor_draft()
    draft["_understanding"] = locked.to_dict()
    draft["smart_buttons"] = [
        {
            "on_model": "res.partner",
            "label": "Visitor Logs",
            "related_model": "x_visitor_log",
            "relation_field": "x_company_id",
            "source": "craft_confirmed",
        }
    ]
    apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    hosts = {
        str(b.get("on_model"))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    assert "res.partner" not in hosts
    assert "hr.employee" in hosts
    attach_operator_surface(draft)
    summary = draft["_operator_surface"].get("summary") or ""
    assert "on Contacts" not in summary
    assert "Visitor Logs" not in summary
    assert "Visits" in summary


def test_no_craft_no_understanding_residual_does_not_invent_contacts_find_it() -> None:
    """Rule 2: residual x_new with no craft must not invent Contacts find-it."""
    prompt = "Equipment checkout register: Asset, Borrower, Due date."
    draft = {
        "display_name": "Equipment Checkout",
        "technical_name": "equipment_checkout",
        "grain": "feature_slice",
        "_generation_engine": {"grain": "feature_slice"},
        "_user_prompt": prompt,
        "models": [
            {
                "model": "x_equipment_checkout",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Borrower",
                    }
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Equipment Checkouts",
                "related_model": "x_equipment_checkout",
                "relation_field": "x_partner_id",
                "source": "odoo_app_bar",
            }
        ],
        "menus": [{"name": "Equipment Checkout", "technical_name": "eq_root"}],
    }
    apply_stock_host_smart_buttons(draft, prompt=prompt)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    assert surface.get("host_buttons") == []
    summary = surface.get("summary") or ""
    assert "Also on stock forms" not in summary
    assert "on Contacts" not in summary


def test_prefer_contacts_field_pack_still_allows_legitimate_contacts() -> None:
    """Prefer Contacts field_pack must still allow Contacts host find-it."""
    draft = {
        "display_name": "Preferred delivery",
        "grain": "field_pack",
        "_generation_engine": {"grain": "field_pack", "host_model": "res.partner"},
        "_user_prompt": PREFER,
        "_understanding": {
            "grain": "field_pack",
            "inherit_existing": True,
            "host_model": "res.partner",
        },
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [{"name": "x_preferred", "ttype": "boolean"}],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Notes",
                "related_model": "x_delivery_note",
                "relation_field": "x_partner_id",
            }
        ],
        "menus": [],
    }
    apply_stock_host_smart_buttons(draft, prompt=PREFER)
    attach_operator_surface(draft)
    surface = draft["_operator_surface"]
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    assert "res.partner" in hosts or "Contacts" in (surface.get("summary") or "")


def test_field_pack_grain_still_proposes_when_residual_host_arrows() -> None:
    """Grain gate removed: field_pack + Host→Employee still gets «Visits» chip."""
    u = build_understanding(VISITOR)
    # Force field_pack while keeping residual constraints / relations.
    u.grain = "field_pack"
    u.inherit_existing = False
    props = propose_craft_smart_buttons(VISITOR, u)
    assert props, "field_pack with Host→Employee must propose craft"
    assert props[0]["on_model"] == "hr.employee"
    assert props[0]["label"] == "Visits"
    assert props[0]["default_on"] is True
    assert len(props) <= 2


def test_feature_slice_grain_still_proposes_when_residual_host_arrows() -> None:
    """Grain gate removed: feature_slice + Host→Employee still gets «Visits» chip."""
    u = build_understanding(VISITOR)
    u.grain = "feature_slice"
    u.inherit_existing = False
    props = propose_craft_smart_buttons(VISITOR, u)
    assert props, "feature_slice with Host→Employee must propose craft"
    assert props[0]["on_model"] == "hr.employee"
    assert props[0]["label"] == "Visits"
    # build_understanding attach path must also fill craft_proposals for non-full_app
    u2 = build_understanding(VISITOR)
    u2.grain = "feature_slice"
    from app.ai_conversation.understand import _attach_craft_proposals

    _attach_craft_proposals(VISITOR, u2)
    assert u2.craft_proposals and u2.craft_proposals[0]["label"] == "Visits"


def test_kept_craft_emits_find_it_even_when_smart_buttons_unstamped() -> None:
    """Defence: confirmed craft always appears as «Visits» on Employees in find-it.

    Live bug: craft kept on Diagnosis but find-it only showed form-field links
    (Host→Employees; Company→Contacts) because smart_buttons missed the stamp
    and defence was gated on suppress_host_invent alone.
    """
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
            "grain": "full_app",
        },
    )
    draft = _visitor_draft()
    draft["grain"] = "feature_slice"  # flip that historically skipped defence
    draft["_generation_engine"] = {"grain": "feature_slice"}
    draft["smart_buttons"] = []  # stamp missing — defence must still emit
    draft["_understanding"] = locked.to_dict()
    surface = build_operator_surface(draft)
    hosts = {b.get("host_model") for b in surface.get("host_buttons") or []}
    labels = {b.get("button_label") for b in surface.get("host_buttons") or []}
    summary = surface.get("summary") or ""
    assert hosts == {"hr.employee"}, hosts
    assert labels == {"Visits"}, labels
    assert "Also on stock forms" in summary
    assert "«Visits» on Employees" in summary
    # Must not fall through to form-field-only copy as the sole stock signal.
    assert "Host → Employees" not in summary or "Visits" in summary


def test_field_pack_kept_craft_stamps_and_find_it() -> None:
    """apply_confirmed stamps craft for field_pack grain; find-it emits host line."""
    u = build_understanding(VISITOR)
    kept = [p for p in u.craft_proposals if p.get("default_on")]
    locked = apply_understanding_edits(
        u,
        {
            "craft_smart_buttons": kept,
            "inherit_existing": False,
            "needs_module": False,
            "grain": "field_pack",
        },
    )
    draft = _visitor_draft()
    draft["grain"] = "field_pack"
    draft["_generation_engine"] = {"grain": "field_pack"}
    draft["_understanding"] = locked.to_dict()
    draft["smart_buttons"] = []
    notes = apply_stock_host_smart_buttons(draft, prompt=VISITOR)
    assert any("craft_smart_btn" in n for n in notes), notes
    btns = [b for b in draft["smart_buttons"] if isinstance(b, dict)]
    assert any(b.get("on_model") == "hr.employee" and b.get("source") == "craft_confirmed" for b in btns)
    attach_operator_surface(draft)
    summary = draft["_operator_surface"].get("summary") or ""
    assert "«Visits» on Employees" in summary or (
        "Visits" in summary and "Employees" in summary
    )


def test_empty_craft_residual_invent_gate_all_grains() -> None:
    """Empty craft + residual ⇒ no Contacts/Employees invent (full_app + feature_slice)."""
    for grain in ("full_app", "feature_slice", "field_pack"):
        draft = _visitor_draft()
        draft["grain"] = grain
        draft["_generation_engine"] = {"grain": grain}
        draft["_understanding"] = {
            "grain": "full_app" if grain != "field_pack" else grain,
            "inherit_existing": False,
            "craft_smart_buttons": [],
        }
        draft["smart_buttons"] = []
        apply_stock_host_smart_buttons(draft, prompt=VISITOR)
        hosts = {
            str(b.get("on_model"))
            for b in (draft.get("smart_buttons") or [])
            if isinstance(b, dict)
        }
        # field_pack without Prefer inherit may still be residual-shaped (x_new);
        # invent must stay off when craft empty.
        assert "hr.employee" not in hosts, grain
        assert "res.partner" not in hosts, grain
