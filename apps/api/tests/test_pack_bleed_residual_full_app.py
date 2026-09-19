"""Pack bleed gates — residual full_app hints only; no Contacts invent; selection ≠ stats."""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.no_app_db

import copy

from app.ai_domain_pack_restaurant import restaurant_pack
from app.ai_domain_packs import merge_domain_pack
from app.ai_rules import apply_pattern_rules
from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons
from app.preview_views import _selection_chrome_labels, _smart_buttons_for_model


def test_rules_do_not_invent_contacts_for_restaurant_residual() -> None:
    draft = copy.deepcopy(restaurant_pack())
    draft["grain"] = "full_app"
    draft["_user_prompt"] = "Build Restaurant Management app with dining tables and reservations"
    apply_pattern_rules(draft)
    partners = [
        b
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict) and b.get("on_model") == "res.partner"
    ]
    assert partners == []


def test_merge_hints_only_skips_models_and_contacts() -> None:
    llm = {
        "display_name": "Dining Tables",
        "technical_name": "dining_tables",
        "grain": "full_app",
        "models": [
            {
                "model": "x_dining_table",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "smart_buttons": [],
    }
    pack = restaurant_pack()
    # Inject a Contacts host button into pack copy to prove gate.
    pack = copy.deepcopy(pack)
    pack.setdefault("smart_buttons", []).append(
        {
            "on_model": "res.partner",
            "label": "Restaurant Management",
            "related_model": "x_reservation",
            "relation_field": "x_partner_id",
        }
    )
    out, notes = merge_domain_pack(llm, pack, hints_only=True)
    assert out["display_name"] == "Dining Tables"
    assert len(out["models"]) == 1
    assert out["models"][0]["model"] == "x_dining_table"
    assert not any(
        isinstance(b, dict) and b.get("on_model") == "res.partner"
        for b in (out.get("smart_buttons") or [])
    )
    assert any("reuse_hints only" in n for n in notes)


def test_merge_full_skips_contacts_host_button() -> None:
    llm = {
        "display_name": "Dining Tables",
        "grain": "full_app",
        "models": [],
        "smart_buttons": [],
    }
    pack = copy.deepcopy(restaurant_pack())
    pack.setdefault("smart_buttons", []).append(
        {
            "on_model": "res.partner",
            "label": "Restaurant Management",
            "related_model": "x_reservation",
            "relation_field": "x_partner_id",
        }
    )
    out, notes = merge_domain_pack(llm, pack, hints_only=False)
    assert out["display_name"] == "Dining Tables"  # not overwritten
    assert not any(
        isinstance(b, dict) and b.get("on_model") == "res.partner"
        for b in (out.get("smart_buttons") or [])
    )


def test_selection_chrome_not_smart_buttons() -> None:
    draft = {
        "models": [
            {
                "model": "x_dining_table",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('free','Free'),('seated','Seated'),"
                            "('reserved','Reserved'),('dirty','Dirty'),"
                            "('blocked','Blocked')]"
                        ),
                    }
                ],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "x_dining_table",
                "label": "Reserved",
                "related_model": "x_reservation",
            },
            {
                "on_model": "x_dining_table",
                "label": "Tables",
                "related_model": "x_reservation",
            },
        ],
    }
    chrome = _selection_chrome_labels(draft, "x_dining_table")
    assert "reserved" in chrome and "seated" in chrome
    buttons = _smart_buttons_for_model(draft, "x_dining_table", arch_buttons=[])
    labels = {b["string"] for b in buttons}
    assert "Reserved" not in labels
    assert "Tables" in labels


def test_punch_card_partner_tie_still_gets_contacts() -> None:
    from tests.test_ai_stock_host_smart_buttons import LAGOS

    draft = {
        "display_name": "Punch Card",
        "grain": "full_app",
        "_user_prompt": LAGOS,
        "models": [
            {
                "model": "x_punch_card",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    }
                ],
            }
        ],
        "smart_buttons": [],
    }
    apply_stock_host_smart_buttons(draft, prompt=LAGOS)
    assert any(b.get("on_model") == "res.partner" for b in draft["smart_buttons"])
