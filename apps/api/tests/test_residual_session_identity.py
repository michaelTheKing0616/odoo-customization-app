"""Residual full_app session/IR identity — Contract wins; pack bleed purged."""

from __future__ import annotations

import copy
import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.understand import (  # noqa: E402
    Understanding,
    attach_understanding,
    reconcile_contract_with_draft,
)
from app.ai_document_compiler import build_grammar_card  # noqa: E402
from app.ai_domain_pack_restaurant import restaurant_pack  # noqa: E402
from app.ai_odoo_app_bar import close_odoo_architecture  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.ai_residual_identity import (  # noqa: E402
    enforce_residual_draft_identity,
    is_field_type_display_name,
    locked_contract_should_win,
)
from app.ai_stock_first import restore_pack_identity  # noqa: E402


VISITOR = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

RESTAURANT = (
    "Dining Tables for our restaurant. Name, Capacity, Status "
    "(selection: Free / Seated / Reserved / Dirty / Blocked). Simple list + form."
)

PREFER = (
    "On Contacts (res.partner), add Preferred for delivery boolean and "
    "Delivery notes. Do not create a new app."
)


def _restaurant_under_visitor() -> dict:
    pack = copy.deepcopy(restaurant_pack())
    draft = {
        key: copy.deepcopy(pack[key])
        for key in (
            "models",
            "views",
            "menus",
            "actions",
            "depends",
            "automations",
            "smart_buttons",
            "technical_name",
            "display_name",
        )
        if key in pack
    }
    draft["domain_pack"] = "restaurant"
    draft["grain"] = "full_app"
    draft["_user_prompt"] = VISITOR
    draft["_pack_model_ids"] = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    return draft


def test_field_type_display_name_detected() -> None:
    assert is_field_type_display_name("char Field For 'name'")
    assert is_field_type_display_name("`char` Field For 'name'")
    assert is_field_type_display_name("Char Field For Names")
    assert not is_field_type_display_name("Visitor Log")
    assert not is_field_type_display_name("Restaurant Management")


def test_enforce_purges_restaurant_pack_under_visitor_locked() -> None:
    draft = _restaurant_under_visitor()
    locked = {
        "title": "Visitor Log",
        "grain": "full_app",
        "inherit_existing": False,
        "needs_module": False,
        "capability": "residual_app",
        "source": "locked",
    }
    notes = enforce_residual_draft_identity(draft, prompt=VISITOR, locked=locked)
    assert any("identity:" in n for n in notes)
    assert draft.get("domain_pack") in (None, "")
    models = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    assert models == ["x_visitor_log"]
    assert draft.get("display_name") == "Visitor Log"
    assert not is_field_type_display_name(str(draft.get("display_name")))
    names = {
        str(f.get("name"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
    }
    assert {"x_name", "x_company_id", "x_visit_date", "x_purpose", "x_host_id"} <= names


def test_locked_contract_wins_over_restaurant_draft_title() -> None:
    draft = {
        "display_name": "Restaurant Management",
        "grain": "full_app",
        "models": [{"model": "x_reservation", "mode": "new", "fields": []}],
        "domain_pack": "restaurant",
        "_user_prompt": VISITOR,
    }
    locked = Understanding(
        capability="residual_app",
        grain="full_app",
        host_model=None,
        inherit_existing=False,
        title="Visitor Log",
        summary="Diagnosis confirmed",
        source="locked",
    )
    assert locked_contract_should_win(locked.to_dict())
    kept = reconcile_contract_with_draft(
        draft, locked, prompt=VISITOR, prefer_locked=True
    )
    assert kept.title == "Visitor Log"
    assert kept.source == "locked"


def test_attach_session_locked_rebuilds_draft_not_contract() -> None:
    draft = _restaurant_under_visitor()
    locked = {
        "title": "Visitor Log",
        "grain": "full_app",
        "inherit_existing": False,
        "needs_module": False,
        "capability": "residual_app",
        "source": "mixed",
        "constraints": ["New model x_visitor_log (Visitor Log)", "Name"],
        "craft_smart_buttons": [],
    }
    attach_understanding(draft, VISITOR, locked=locked)
    u = draft["_understanding"]
    assert u["title"] == "Visitor Log"
    assert u.get("source") != "reconciled_draft"
    models = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    assert "x_visitor_log" in models
    assert "x_reservation" not in models
    assert draft.get("display_name") == "Visitor Log"


def test_close_after_enforce_grammar_no_eight_extra_apps() -> None:
    draft = _restaurant_under_visitor()
    locked = {
        "title": "Visitor Log",
        "grain": "full_app",
        "inherit_existing": False,
        "needs_module": False,
        "source": "locked",
    }
    enforce_residual_draft_identity(draft, prompt=VISITOR, locked=locked)
    close_odoo_architecture(draft, user_prompt=VISITOR)
    grammar = build_grammar_card(draft, prompt=VISITOR)
    assert grammar["display_name"] == "Visitor Log"
    assert grammar["extra_apps"] == 0
    assert "Reservations" not in str(draft.get("menus") or [])


def test_restore_pack_identity_clears_divergent_pack() -> None:
    draft = _restaurant_under_visitor()
    draft["display_name"] = "Visitor Log"
    notes = restore_pack_identity(draft, user_prompt=VISITOR)
    assert draft.get("domain_pack") in (None, "")
    assert any("cleared divergent pack" in n for n in notes)


def test_clean_visitor_seed_unchanged() -> None:
    draft = seed_studio_draft(VISITOR)
    before = [m.get("model") for m in (draft.get("models") or [])]
    notes = enforce_residual_draft_identity(
        draft,
        prompt=VISITOR,
        locked={"title": "Visitor Log", "grain": "full_app", "source": "locked"},
    )
    after = [m.get("model") for m in (draft.get("models") or [])]
    assert before == after
    assert draft.get("display_name") == "Visitor Log"
    assert not any("rebuilding register" in n for n in notes)


def test_restaurant_residual_dining_tables_ok() -> None:
    draft = seed_studio_draft(RESTAURANT)
    assert "dining" in str(draft.get("display_name") or "").lower() or draft.get(
        "display_name"
    ) == "Dining Tables"
    notes = enforce_residual_draft_identity(
        draft,
        prompt=RESTAURANT,
        locked={
            "title": draft.get("display_name") or "Dining Tables",
            "grain": "full_app",
            "source": "locked",
        },
    )
    assert not any("rebuilding register" in n for n in notes)


def test_prefer_contacts_not_touched_by_residual_gate() -> None:
    draft = seed_studio_draft(PREFER)
    locked = {
        "title": "Contacts field",
        "grain": "field_pack",
        "inherit_existing": True,
        "host_model": "res.partner",
        "source": "locked",
    }
    notes = enforce_residual_draft_identity(draft, prompt=PREFER, locked=locked)
    assert notes == []
    assert any(
        isinstance(m, dict) and m.get("model") == "res.partner"
        for m in (draft.get("models") or [])
    )


def test_mangled_char_field_title_replaced() -> None:
    draft = {
        "display_name": "`char` Field For 'name'",
        "technical_name": "char_field_for_name",
        "grain": "full_app",
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ],
        "_user_prompt": VISITOR,
    }
    enforce_residual_draft_identity(
        draft,
        prompt=VISITOR,
        locked={"title": "Visitor Log", "grain": "full_app", "source": "locked"},
    )
    assert draft["display_name"] == "Visitor Log"
    assert not is_field_type_display_name(draft["display_name"])
