"""Architecture close pass — named FKs, stock clones, registers, Expert fixer."""

from __future__ import annotations

from app.ai_draft_scorecard import draft_scorecard
from app.ai_odoo_app_bar import (
    close_odoo_architecture,
    looks_like_register,
    run_odoo_app_bar_pass,
    senior_sequence_prefix,
)
from app.ai_presentation import _menu_category
from app.ai_rules import apply_pattern_rules
from app.expert.draft_review import review_draft

MUSIC_PROMPT = "A music production company with multiple recording studios and artistes"


def _status_field(*keys: str) -> dict:
    inner = ",".join(f"('{k}','{k.title()}')" for k in keys)
    return {
        "name": "x_status",
        "ttype": "selection",
        "selection": f"[{inner}]",
        "tracking": True,
    }


def _broken_music_draft() -> dict:
    return {
        "technical_name": "music_production_recording_studios",
        "display_name": "Music Production Recording Studios",
        "_user_prompt": MUSIC_PROMPT,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts", "hr", "account", "sale"],
        "reuse": {
            "models": [
                "res.partner",
                "res.users",
                "res.company",
                "res.currency",
                "hr.employee",
                "account.move",
            ]
        },
        "models": [
            {
                "model": "x_studio",
                "description": "Studio",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("draft", "open", "active", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_artist",
                "description": "Artist",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_artist_id",
                        "ttype": "many2one",
                        "relation": "x_artist",
                    },
                    _status_field("draft", "open", "done"),
                ],
            },
            {
                "model": "x_booking_line",
                "description": "Booking Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_equipment",
                "description": "Equipment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("available", "in_use", "maintenance"),
                    {
                        "name": "x_recording_session_ids",
                        "ttype": "one2many",
                        "relation": "x_recording_session",
                        "relation_field": "x_studio_id",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_recording_session",
                "description": "Recording Session",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_artist_id",
                        "ttype": "many2one",
                        "relation": "x_artist",
                    },
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                        "string": "Studio",
                    },
                ],
            },
            {
                "model": "x_engagement",
                "description": "Engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_artist_id",
                        "ttype": "many2one",
                        "relation": "x_artist",
                    },
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                    },
                    _status_field("draft", "in_progress", "done"),
                ],
            },
            {
                "model": "x_currency",
                "description": "Currency",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_code", "ttype": "char"},
                ],
            },
            {
                "model": "x_payment",
                "description": "Payment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_amount",
                        "ttype": "monetary",
                        "currency_field": "x_currency_id",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                    _status_field("draft", "open", "done"),
                ],
            },
            {
                "model": "x_crew",
                "description": "Crew",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_crew_id",
                        "ttype": "many2one",
                        "relation": "x_crew",
                    },
                    _status_field("draft", "open", "done"),
                ],
            },
            {
                "model": "x_line_item",
                "description": "Line Item",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_quantity", "ttype": "float"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "related_model": "x_engagement",
                "relation_field": "x_artist_id",
                "label": "Engagements",
            },
            {
                "on_model": "res.partner",
                "related_model": "x_artist",
                "relation_field": "x_partner_id",
                "label": "Artists",
            },
        ],
        "sequences": [
            {
                "model": "x_engagement",
                "field": "x_code",
                "prefix": "ENGAGEMENT/",
                "padding": 5,
            }
        ],
        "actions": [
            {"name": "Studios", "model": "x_studio", "technical_name": "action_x_studio"},
            {"name": "Bookings", "model": "x_booking", "technical_name": "action_x_booking"},
            {
                "name": "Engagements",
                "model": "x_engagement",
                "technical_name": "action_x_engagement",
            },
            {
                "name": "Sessions",
                "model": "x_recording_session",
                "technical_name": "action_x_recording_session",
            },
        ],
        "menus": [
            {
                "name": "Music",
                "technical_name": "menu_root",
                "xml_id": "menu_root",
                "sequence": 10,
            },
            {
                "name": "Engagements",
                "action_xml_id": "action_x_engagement",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_engagement",
            },
            {
                "name": "Bookings",
                "action_xml_id": "action_x_booking",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_booking",
            },
            {
                "name": "Studios",
                "action_xml_id": "action_x_studio",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_studio",
            },
            {
                "name": "Sessions",
                "action_xml_id": "action_x_recording_session",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_recording_session",
            },
        ],
    }


def _by_id(draft: dict) -> dict:
    return {m["model"]: m for m in draft["models"]}


def test_looks_like_register_covers_studio_crew_rate_card() -> None:
    assert looks_like_register("x_studio")
    assert looks_like_register("x_artist")
    assert looks_like_register("x_equipment")
    assert looks_like_register("x_crew")
    assert looks_like_register("x_rate_card")
    assert looks_like_register("x_rate")
    assert looks_like_register("x_rate_unit")
    assert looks_like_register("x_unavailability")
    assert looks_like_register("x_party_role")
    assert looks_like_register("x_site_specialty")
    assert not looks_like_register("x_booking")
    assert not looks_like_register("x_recording_session")
    assert not looks_like_register("x_og_work_order")


def test_apply_pattern_rules_does_not_promote_registers() -> None:
    draft = {
        "models": [
            {
                "model": "x_studio",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("active", "inactive"),
                ],
            },
            {
                "model": "x_booking",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "open", "done"),
                ],
            },
        ]
    }
    apply_pattern_rules(draft)
    by = _by_id(draft)
    assert by["x_studio"].get("is_workflow") is not True
    assert by["x_booking"].get("is_workflow") is True


def test_close_repairs_music_session_fk_and_stock_clones() -> None:
    draft = _broken_music_draft()
    notes = close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    assert notes
    by = _by_id(draft)
    assert "x_currency" not in by
    assert "x_payment" not in by
    assert "x_crew" not in by
    assert "x_line_item" not in by
    session = by["x_recording_session"]
    studio_fk = next(f for f in session["fields"] if f["name"] == "x_studio_id")
    assert studio_fk["relation"] == "x_studio"
    booking = by["x_booking"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_studio"
        for f in booking["fields"]
    )
    assert by["x_studio"].get("is_workflow") is not True
    assert by["x_artist"].get("is_workflow") is not True
    assert by["x_equipment"].get("is_workflow") is not True
    equipment = by["x_equipment"]
    eq_type = next((f for f in equipment["fields"] if f.get("name") == "x_type"), None)
    assert eq_type is not None
    assert "console" in str(eq_type.get("selection") or "")
    assert "camera" not in str(eq_type.get("selection") or "")
    assert not any(
        f.get("ttype") == "one2many" and f.get("relation") == "x_recording_session"
        for f in equipment["fields"]
    )
    studio = by["x_studio"]
    assert any(
        f.get("ttype") == "one2many" and f.get("relation") == "x_recording_session"
        for f in studio["fields"]
    )
    partner_btns = [
        b
        for b in (draft.get("smart_buttons") or [])
        if b.get("on_model") == "res.partner"
    ]
    assert all(b.get("relation_field") != "x_artist_id" or b.get("related_model") != "x_engagement" for b in partner_btns)


def test_app_bar_pass_repairs_the_same_music_graph() -> None:
    draft = _broken_music_draft()
    run_odoo_app_bar_pass(draft, user_prompt=MUSIC_PROMPT)
    by = _by_id(draft)
    session = by["x_recording_session"]
    studio_fk = next(f for f in session["fields"] if f["name"] == "x_studio_id")
    assert studio_fk["relation"] == "x_studio"
    assert "x_currency" not in by
    assert by["x_studio"].get("is_workflow") is not True


def test_expert_fix_repairs_music_architecture() -> None:
    draft = _broken_music_draft()
    before = review_draft(
        draft, user_prompt=MUSIC_PROMPT, apply_fixes=False, include_narratives=False
    )
    fk = next(
        (f for f in before.findings if "FK should target" in f.detail),
        None,
    )
    assert fk is not None
    assert fk.deterministic is True
    after = review_draft(
        draft, user_prompt=MUSIC_PROMPT, apply_fixes=True, include_narratives=False
    )
    assert after.draft is not None
    by = _by_id(after.draft)
    studio_fk = next(
        f for f in by["x_recording_session"]["fields"] if f["name"] == "x_studio_id"
    )
    assert studio_fk["relation"] == "x_studio"
    assert "x_currency" not in by
    assert "x_payment" not in by
    assert after.score_after is not None
    assert after.score_after >= before.score_before


def test_sequence_prefix_engagement_is_not_truncated() -> None:
    draft = {
        "models": [
            {
                "model": "x_engagement",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "sequences": [
            {"model": "x_engagement", "prefix": "ENGAGEMENT/", "padding": 5}
        ],
        "actions": [{"model": "x_engagement", "technical_name": "a"}],
        "views": [],
        "menus": [],
    }
    sc = draft_scorecard(draft, user_prompt=MUSIC_PROMPT)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert not any("ENGAGEMENT/" in d for d in details)
    draft["sequences"][0]["prefix"] = "ENGA/"
    sc_bad = draft_scorecard(draft, user_prompt=MUSIC_PROMPT)
    details_bad = [str(f.get("detail") or "") for f in sc_bad.get("findings") or []]
    assert any("ENGA/" in d and "truncated" in d for d in details_bad)


def test_engagement_and_agreement_menus_are_operations() -> None:
    assert _menu_category("Engagements", "x_engagement") == "Operations"
    assert _menu_category("Agreements", "x_agreement") == "Operations"


def test_pack_draft_keeps_curated_payment_model() -> None:
    draft = {
        "domain_pack": "hospital",
        "depends": ["account"],
        "reuse": {"models": ["account.move"]},
        "models": [
            {
                "model": "x_payment",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_appointment",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
    }
    close_odoo_architecture(draft, user_prompt="hospital clinic appointments")
    ids = {m["model"] for m in draft["models"]}
    assert "x_payment" in ids


def test_senior_sequence_prefix_uses_whole_word() -> None:
    assert senior_sequence_prefix("x_engagement") == "ENGAGEMENT/"
    assert senior_sequence_prefix("x_booking") == "BOOKING/"
    assert senior_sequence_prefix("x_rate_card") == "RC/"


def test_close_renames_generic_site_party_and_repairs_structure() -> None:
    """Live music draft defects: x_site/x_party, missing ACL, orphan lines, ghost menus."""
    draft = {
        "technical_name": "music_production_recording_studios",
        "display_name": "Music Production Recording Studios",
        "_user_prompt": MUSIC_PROMPT,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts", "hr", "account"],
        "models": [
            {
                "model": "x_site",
                "description": "Site",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_location_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_party",
                "description": "Party",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_contact_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('confirmed','Confirmed'),('done','Done')]",
                    },
                    {
                        "name": "x_site_id",
                        "ttype": "many2one",
                        "relation": "x_site",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_rate_card",
                "description": "Rate Card",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_rate_line",
                "description": "Rate Line",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_service_line",
                "description": "Service Line",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('done','Done')]",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_maintenance",
                "description": "Maintenance",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    },
                ],
            },
            {
                "model": "x_booking_line",
                "description": "Booking Line",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                        "required": True,
                    },
                ],
            },
        ],
        "actions": [
            {"name": "Sites", "model": "x_site", "technical_name": "action_x_site"},
            {"name": "Bookings", "model": "x_booking", "technical_name": "action_x_booking"},
            {
                "name": "Deposits",
                "model": "x_deposit",
                "technical_name": "action_x_deposit",
            },
        ],
        "menus": [
            {
                "name": "Music",
                "technical_name": "menu_root",
                "xml_id": "menu_root",
                "sequence": 10,
            },
            {
                "name": "Sites",
                "action_xml_id": "action_x_site",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_site",
            },
            {
                "name": "Deposit",
                "action_xml_id": "action_x_deposit",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_deposit",
            },
            {
                "name": "Booking Lines",
                "action_xml_id": "action_x_booking_line",
                "parent_xml_id": "menu_root",
                "technical_name": "menu_x_booking_line",
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_party",
                "label": "Agreements",
                "related_model": "x_agreement",
                "relation_field": "x_party_a_id",
            },
            {
                "on_model": "x_party",
                "label": "Agreements",
                "related_model": "x_agreement",
                "relation_field": "x_party_b_id",
            },
        ],
        "sequences": [{"model": "x_booking", "field": "x_code", "prefix": "BOOK/"}],
        "access_rules": [],
        "groups": [],
        "review_notes": [
            "rules: added x_code reference on workflow model x_site",
            "density: party from prompt x_party",
        ],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    by = _by_id(draft)
    assert "x_site" not in by
    assert "x_party" not in by
    assert "x_studio" in by
    assert "x_artist" in by
    notes = draft.get("review_notes") or []
    assert any("x_studio" in str(n) for n in notes)
    assert not any("x_site" in str(n) and "in favor of" not in str(n) for n in notes)
    assert any("x_artist" in str(n) for n in notes)
    assert not any(str(n).endswith("x_party") for n in notes)
    booking = by["x_booking"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_studio"
        for f in booking["fields"]
    )
    rate_line = by["x_rate_line"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_rate_card"
        for f in rate_line["fields"]
    )
    assert by["x_service_line"].get("is_workflow") is not True
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_booking"
        for f in by["x_service_line"]["fields"]
    )
    assert isinstance(by["x_maintenance"].get("state_field"), dict)
    access_models = {
        str(r.get("model") or "").replace("model_", "", 1)
        for r in (draft.get("access_rules") or [])
        if isinstance(r, dict)
    }
    assert "x_booking_line" in access_models
    assert "x_maintenance" in access_models
    action_xml = {
        str(a.get("technical_name") or ""): str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    menu_actions = {
        str(m.get("action_xml_id") or "")
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    }
    assert "action_x_deposit" not in menu_actions
    for xml in menu_actions:
        mid = action_xml.get(xml, "")
        assert not mid.endswith("_line"), mid
    prefixes = {str(s.get("prefix")) for s in (draft.get("sequences") or []) if isinstance(s, dict)}
    assert "BOOKING/" in prefixes
    sc = draft_scorecard(draft, user_prompt=MUSIC_PROMPT)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert not any("missing access" in d for d in details)
    assert not any("line model missing parent m2o" in d for d in details)
    assert not any("workflow model missing state_field" in d for d in details)
    assert not any("looks truncated" in d for d in details)


def test_generic_loop_leaf_matches_staffing() -> None:
    from app.ai_odoo_app_bar import _generic_loop_leaf

    assert _generic_loop_leaf("x_staffing") in {"staff", "staffing"}
    assert _generic_loop_leaf("x_staff") == "staff"


def test_close_repairs_music_lexicon_typed_fks_staffing_and_totals() -> None:
    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts", "hr", "account"],
        "reuse": {"models": ["res.partner", "hr.employee", "res.company", "res.currency"]},
        "models": [
            {
                "model": "x_studio",
                "description": "Studio",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Site Name", "required": True},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.company"},
                ],
            },
            {
                "model": "x_equipment",
                "description": "Equipment",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "selection": "[('console','Console'),('microphone','Microphone')]",
                    },
                    {
                        "name": "x_engagement_ids",
                        "ttype": "one2many",
                        "relation": "x_engagement",
                        "relation_field": "x_console_id",
                    },
                ],
            },
            {
                "model": "x_engagement",
                "description": "Engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_console_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                        "string": "Console",
                    },
                    {
                        "name": "x_microphone_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                        "string": "Microphone",
                    },
                    {
                        "name": "x_deliverable_ids",
                        "ttype": "one2many",
                        "relation": "x_deliverable",
                        "relation_field": "x_matter_id",
                    },
                    _status_field("draft", "open", "done"),
                ],
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                        "string": "Site",
                    },
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_booking_id",
                    },
                    _status_field("draft", "confirmed", "done"),
                ],
            },
            {
                "model": "x_deliverable",
                "description": "Deliverable",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Engagement",
                        "relation": "x_engagement",
                    },
                ],
            },
            {
                "model": "x_staffing",
                "description": "Crew And Staff Assignments",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True, "selection": "[]"},
                    {
                        "name": "x_person_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_job_cost",
                "description": "Cost",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_total_cost",
                        "ttype": "monetary",
                        "currency_field": "x_currency_id",
                    },
                    {
                        "name": "x_amount",
                        "ttype": "monetary",
                        "currency_field": "x_currency_id",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_job_cost_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_cost_line",
                        "relation_field": "x_job_cost_id",
                    },
                ],
            },
            {
                "model": "x_job_cost_line",
                "description": "Cost Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_job_cost_id",
                        "ttype": "many2one",
                        "relation": "x_job_cost",
                        "required": True,
                    },
                    {"name": "x_qty", "ttype": "float", "default": 1},
                ],
            },
            {
                "model": "x_equipment_line",
                "description": "Equipment Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                ],
            },
            {
                "model": "x_revision",
                "description": "Revision",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_description", "ttype": "text"},
                ],
            },
            {
                "model": "x_recording_session",
                "description": "Recording Session",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_sale_order_id",
                        "ttype": "many2one",
                        "relation": "sale.order",
                        "string": "Sales order",
                    },
                    _status_field("draft", "open", "done"),
                ],
            },
        ],
        "actions": [
            {"name": "Engagements", "model": "x_engagement", "technical_name": "action_x_engagement"},
            {"name": "Bookings", "model": "x_booking", "technical_name": "action_x_booking"},
            {"name": "Staffings", "model": "x_staffing", "technical_name": "action_x_staffing"},
        ],
        "menus": [
            {
                "name": "Staffings",
                "action_xml_id": "action_x_staffing",
                "technical_name": "menu_x_staffing",
            }
        ],
        "views": [
            {
                "name": "x_equipment.kanban",
                "model": "x_equipment",
                "type": "kanban",
                "arch": (
                    '<kanban default_group_by="x_status" class="o_kanban_small_column">'
                    '<templates><t t-name="card"><field name="x_name"/></t></templates></kanban>'
                ),
            }
        ],
        "smart_buttons": [
            {
                "on_model": "x_equipment",
                "related_model": "x_engagement",
                "relation_field": "x_console_id",
                "label": "Engagements",
            },
            {
                "on_model": "x_booking",
                "related_model": "x_equipment_line",
                "relation_field": "x_equipment_id",
                "label": "Equipment Lines",
            },
        ],
        "access_rules": [],
        "groups": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    by = _by_id(draft)
    assert "x_staffing" not in by
    deliverable = by["x_deliverable"]
    names = {f["name"] for f in deliverable["fields"]}
    assert "x_matter_id" not in names
    assert "x_engagement_id" in names
    engagement = by["x_engagement"]
    eq_fks = [
        f
        for f in engagement["fields"]
        if f.get("ttype") == "many2one" and f.get("relation") == "x_equipment"
    ]
    assert len(eq_fks) <= 1
    assert not any(f.get("name") in {"x_console_id", "x_microphone_id"} for f in engagement["fields"])
    line = by["x_equipment_line"]
    assert any(
        f.get("name") == "x_booking_id" and f.get("relation") == "x_booking"
        for f in line["fields"]
    )
    kanban = next(v for v in draft["views"] if v.get("type") == "kanban" and v.get("model") == "x_equipment")
    assert 'default_group_by="x_status"' not in str(kanban.get("arch") or "")
    cost_line = by["x_job_cost_line"]
    cost_names = {f["name"] for f in cost_line["fields"]}
    assert "x_rate" in cost_names or "x_price" in cost_names
    assert "x_subtotal" in cost_names or "x_amount" in cost_names
    compute_models = {
        str(b.get("model"))
        for b in (draft.get("custom_code_blocks") or [])
        if isinstance(b, dict) and b.get("model")
    }
    assert "x_job_cost" in compute_models
    blob = str(draft).lower()
    assert "x_matter_id" not in blob
    sc = draft_scorecard(draft, user_prompt=MUSIC_PROMPT)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert not any("foreign-domain lexicon leak" in d for d in details)
    assert not any("order header total not computed" in d for d in details)
    booking = by["x_booking"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_engagement"
        for f in booking["fields"]
    )
    revision = by["x_revision"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_deliverable"
        for f in revision["fields"]
    )
    session = by["x_recording_session"]
    sale_fk = next(f for f in session["fields"] if f.get("name") == "x_sale_order_id")
    assert sale_fk["relation"] == "sale.order"
    assert "link-only" in str(sale_fk.get("help") or "").lower()
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_engagement"
        for f in session["fields"]
    )
    assert not any("booking/session missing FK" in d for d in details)
    assert not any("revision missing FK" in d for d in details)
    assert not any("must be link-only" in d for d in details)


def _job_draft(
    *,
    prompt: str,
    domain_pack: str | None = None,
    extra_models: list[dict] | None = None,
) -> dict:
    draft: dict = {
        "technical_name": "ops_app",
        "display_name": "Ops",
        "_user_prompt": prompt,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts"],
        "models": [
            {
                "model": "x_engagement",
                "description": "Engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_project",
                "description": "Project",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_appointment",
                "description": "Appointment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_engagement_id",
                        "ttype": "many2one",
                        "relation": "x_engagement",
                    },
                    _status_field("draft", "confirmed", "done"),
                ],
            },
            {
                "model": "x_deliverable",
                "description": "Deliverable",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_project_id",
                        "ttype": "many2one",
                        "relation": "x_project",
                    },
                ],
            },
        ],
        "actions": [],
        "menus": [],
        "views": [],
        "automations": [],
    }
    if domain_pack:
        draft["domain_pack"] = domain_pack
    if extra_models:
        draft["models"].extend(extra_models)
    return draft


def test_close_collapses_parallel_job_headers_clinic() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _job_draft(prompt=prompt)
    sc = draft_scorecard(draft, user_prompt=prompt)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert any("parallel job headers" in d for d in details)

    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    headers = ids & {"x_engagement", "x_project"}
    assert len(headers) == 1
    keep = next(iter(headers))
    deliverable = next(m for m in draft["models"] if m["model"] == "x_deliverable")
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == keep
        for f in deliverable["fields"]
    )
    appointment = next(m for m in draft["models"] if m["model"] == "x_appointment")
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == keep
        for f in appointment["fields"]
    )
    sc2 = draft_scorecard(draft, user_prompt=prompt)
    details2 = [str(f.get("detail") or "") for f in sc2.get("findings") or []]
    assert not any("parallel job headers" in d for d in details2)


def test_close_keeps_both_job_headers_when_prompt_names_them() -> None:
    prompt = "Track client engagements and internal projects"
    draft = _job_draft(prompt=prompt)
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_engagement" in ids
    assert "x_project" in ids


def test_close_project_prompt_keeps_project() -> None:
    prompt = "Construction project tracker for site jobs"
    draft = _job_draft(prompt=prompt)
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_project" in ids
    assert "x_engagement" not in ids


def test_close_law_prompt_keeps_matter() -> None:
    prompt = "A law firm with attorneys"
    draft = _job_draft(
        prompt=prompt,
        extra_models=[
            {
                "model": "x_matter",
                "description": "Matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            }
        ],
    )
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_matter" in ids
    assert "x_engagement" not in ids
    assert "x_project" not in ids


def test_close_skips_job_header_collapse_for_domain_pack() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _job_draft(prompt=prompt, domain_pack="clinic")
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_engagement" in ids
    assert "x_project" in ids


def test_close_canonicalizes_selections_and_drops_fake_automations() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _job_draft(prompt=prompt)
    draft["models"].append(
        {
            "model": "x_agreement",
            "description": "Agreement",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "selection": "[('Draft','Draft'),('draft','Draft'),('open','Open'),('done','Done')]",
                    "default": "Draft",
                    "tracking": True,
                },
                {
                    "name": "x_rate_unit",
                    "ttype": "selection",
                    "selection": "[('Hour','Hour'),('Day','Day')]",
                },
            ],
            "state_field": {
                "field": "x_status",
                "transitions": [["Draft", "draft"], ["draft", "open"]],
                "states": ["Draft", "draft", "open", "done"],
            },
        }
    )
    draft["models"].append(
        {
            "model": "x_unavailability",
            "description": "Unavailability",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "selection": "[('active','inactive'),('draft','Draft')]",
                    "default": "active",
                    "tracking": True,
                },
            ],
            "state_field": {"field": "x_status"},
        }
    )
    draft["models"].append(
        {
            "model": "x_job_cost",
            "description": "Cost",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {
                    "name": "x_party_id",
                    "ttype": "many2one",
                    "relation": "x_engagement",
                    "string": "Party",
                },
            ],
        }
    )
    draft["automations"] = [
        {
            "name": "Notify Confirmation",
            "model": "x_appointment",
            "trigger": "on_write",
            "filter_domain": "['x_name', '!=', '']",
            "safe_actions": [
                {
                    "kind": "mail_post",
                    "field": "x_confirmation_email",
                    "value": "send_confirmation_email(x_partner_id)",
                }
            ],
        },
        {
            "name": "Update Rate",
            "model": "x_appointment",
            "trigger": "on_write",
            "filter_domain": "[('x_name', '!=', False)]",
            "safe_actions": [
                {
                    "kind": "object_write",
                    "field": "x_rate",
                    "value": "calculate_rate(x_start, x_end)",
                }
            ],
        },
        {
            "name": "Follow up deadline Appointment",
            "model": "x_appointment",
            "trigger": "on_time",
            "filter_domain": "[('x_name', '!=', False)]",
            "safe_actions": [{"kind": "next_activity", "summary": "deadline appointment"}],
        },
    ]
    sc = draft_scorecard(draft, user_prompt=prompt)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert any("workflow flag without status" in d for d in details)
    assert any("non-metadata action" in d or "invalid domain" in d for d in details)

    close_odoo_architecture(draft, user_prompt=prompt)
    by = {m["model"]: m for m in draft["models"]}
    agreement = by["x_agreement"]
    status = next(f for f in agreement["fields"] if f["name"] == "x_status")
    assert "('Draft'" not in str(status.get("selection"))
    assert "('draft'" in str(status.get("selection"))
    assert status.get("default") == "draft"
    rate = next(f for f in agreement["fields"] if f["name"] == "x_rate_unit")
    assert "('hour','Hour')" in str(rate.get("selection")).replace(" ", "")
    unavail = by["x_unavailability"]
    assert unavail.get("is_workflow") is False
    cost = by["x_job_cost"]
    assert cost.get("is_workflow") is False
    party = next(f for f in cost["fields"] if f.get("ttype") == "many2one")
    assert party["name"].endswith("_id")
    assert party["name"] != "x_party_id" or party["relation"] == "x_party"
    autos = [a.get("name") for a in draft.get("automations") or []]
    assert "Notify Confirmation" not in autos
    assert "Update Rate" not in autos
    assert any("deadline" in str(n).lower() for n in autos)
    sc2 = draft_scorecard(draft, user_prompt=prompt)
    details2 = [str(f.get("detail") or "") for f in sc2.get("findings") or []]
    assert not any("workflow flag without status" in d for d in details2)
    assert not any("non-metadata action" in d for d in details2)


def _m2o(name: str, relation: str, string: str = "") -> dict:
    field = {"name": name, "ttype": "many2one", "relation": relation}
    if string:
        field["string"] = string
    return field


def _clinic_architecture_gaps_draft() -> dict:
    prompt = "A neighborhood clinic with walk-in appointments"
    return {
        "technical_name": "clinic_ops",
        "display_name": "Clinic Ops",
        "_user_prompt": prompt,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts"],
        "models": [
            {
                "model": "x_clinic",
                "description": "Clinic",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_patient",
                "description": "Patient",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_last_interaction_date", "ttype": "date"},
                    {"name": "x_rate", "ttype": "float", "string": "Rate"},
                    {"name": "x_rate_unit", "ttype": "char"},
                ],
            },
            {
                "model": "x_engagement",
                "description": "Engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_company_id", "res.company", "Clinic"),
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_appointment",
                "description": "Appointment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_engagement_id", "x_engagement"),
                    _m2o("x_purchase_order_id", "purchase.order", "Purchase order"),
                    _status_field("draft", "confirmed", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_deliverable",
                "description": "Deliverable",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_patient_id", "x_patient"),
                    _m2o("x_clinic_id", "x_clinic"),
                ],
            },
            {
                "model": "x_job_cost_expense",
                "description": "Job Cost",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_clinic_id", "x_clinic"),
                ],
            },
            {
                "model": "x_rate_card",
                "description": "Rate Card",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_rate_line",
                "description": "Rate Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_rate_card_id", "x_rate_card"),
                    _m2o("x_product_id", "product.product", "Product"),
                    {"name": "x_qty", "ttype": "float", "default": 1.0},
                ],
            },
            {
                "model": "x_rate_card_line",
                "description": "Rate Card Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_rate_card_id", "x_rate_card"),
                    {"name": "x_qty", "ttype": "float", "default": 1.0},
                ],
            },
            {
                "model": "x_agreement",
                "description": "Agreement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_patient_id", "x_patient", "Party A"),
                    _m2o("x_patient_b_id", "x_patient", "Party B"),
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('active','Active'),('done','Done')]",
                        "default": "active",
                        "tracking": True,
                    },
                ],
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "active", "done"],
                    "statusbar_visible": ["draft", "active", "done"],
                },
            },
            {
                "model": "x_equipment",
                "description": "Equipment",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_equipment_line",
                "description": "Equipment Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_equipment_id", "x_equipment"),
                ],
            },
        ],
        "actions": [],
        "menus": [],
        "views": [],
        "automations": [],
    }


def test_close_attaches_job_children_and_collapses_duplicate_lines() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _clinic_architecture_gaps_draft()
    sc = draft_scorecard(draft, user_prompt=prompt)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert any("missing job-header FK" in d for d in details)
    assert any("duplicate line models" in d for d in details)
    assert any("without depends product" in d for d in details)

    close_odoo_architecture(draft, user_prompt=prompt)
    by = _by_id(draft)
    assert "x_rate_line" not in by or "x_rate_card_line" not in by
    line_ids = [m for m in by if m.endswith("_line") and "rate" in m]
    assert len(line_ids) == 1
    keeper = line_ids[0]
    assert any(
        f.get("relation") == "product.product" for f in by[keeper]["fields"]
    )

    deliverable = by["x_deliverable"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_engagement"
        for f in deliverable["fields"]
    )
    cost = by["x_job_cost_expense"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_engagement"
        for f in cost["fields"]
    )

    agreement = by["x_agreement"]
    party_m2os = [
        f
        for f in agreement["fields"]
        if f.get("ttype") == "many2one" and f.get("relation") == "x_patient"
    ]
    assert len(party_m2os) == 1
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "res.partner"
        for f in agreement["fields"]
    )
    status = next(f for f in agreement["fields"] if f["name"] == "x_status")
    assert status.get("default") == "draft"

    company = next(f for f in by["x_engagement"]["fields"] if f["name"] == "x_company_id")
    assert company.get("string") == "Company"

    eq_line = by["x_equipment_line"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_appointment"
        for f in eq_line["fields"]
    )
    appt = by["x_appointment"]
    assert not any(
        f.get("relation") == "purchase.order" for f in appt["fields"] if isinstance(f, dict)
    )
    assert "product" in (draft.get("depends") or [])

    patient = by["x_patient"]
    names = {f.get("name") for f in patient["fields"]}
    assert "x_last_interaction_date" not in names
    assert "x_rate" not in names

    sc2 = draft_scorecard(draft, user_prompt=prompt)
    details2 = [str(f.get("detail") or "") for f in sc2.get("findings") or []]
    assert not any("missing job-header FK" in d for d in details2)
    assert not any("duplicate line models" in d for d in details2)
    assert not any("without depends product" in d for d in details2)


def test_close_skips_line_collapse_and_agreement_rewrite_for_domain_pack() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _clinic_architecture_gaps_draft()
    draft["domain_pack"] = "clinic"
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_rate_line" in ids
    assert "x_rate_card_line" in ids
    agreement = next(m for m in draft["models"] if m["model"] == "x_agreement")
    party_m2os = [
        f
        for f in agreement["fields"]
        if f.get("ttype") == "many2one" and f.get("relation") == "x_patient"
    ]
    assert len(party_m2os) == 2


def _clinic_remaining_gaps_draft() -> dict:
    prompt = "A neighborhood clinic with walk-in appointments"
    return {
        "technical_name": "clinic_ops",
        "display_name": "Clinic Ops",
        "_user_prompt": prompt,
        "_ambition": "comprehensive",
        "depends": ["base", "mail", "contacts", "hr"],
        "models": [
            {
                "model": "x_clinic",
                "description": "Clinic",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_engagement",
                "description": "Engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_clinic_id", "x_clinic", "Recording Site"),
                    _m2o("x_attorney_id", "res.users", "Attorney"),
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('completed','Completed'),"
                            "('done','Done')]"
                        ),
                        "default": "draft",
                        "tracking": True,
                    },
                ],
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "completed", "done"],
                    "statusbar_visible": ["draft", "completed", "done"],
                    "transitions": [["draft", "completed"], ["draft", "done"]],
                },
            },
            {
                "model": "x_appointment",
                "description": "Appointment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_engagement_id", "x_engagement"),
                    _status_field("draft", "confirmed", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_job_cost_expense",
                "description": "Expense",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_engagement_id", "x_engagement"),
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_cost_expense_line",
                        "relation_field": "x_job_cost_expense_id",
                        "string": "Lines",
                    },
                ],
            },
            {
                "model": "x_job_cost_expense_line",
                "description": "Expense Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_job_cost_expense_id", "x_job_cost_expense"),
                    {"name": "x_qty", "ttype": "float", "default": 1.0},
                    {"name": "x_price", "ttype": "float"},
                ],
            },
            {
                "model": "x_job_cost",
                "description": "Job Cost",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_clinic_id", "x_clinic"),
                    _m2o("x_engagement_id", "x_engagement"),
                    _m2o("x_appointment_id", "x_appointment"),
                ],
            },
            {
                "model": "x_rate_card",
                "description": "Rate Card",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_rate_line_ids",
                        "ttype": "one2many",
                        "relation": "x_rate_line",
                        "relation_field": "x_rate_card_id",
                        "string": "X Rate Line",
                    },
                ],
            },
            {
                "model": "x_rate_line",
                "description": "X Rate Line",
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_rate_card_id", "x_rate_card"),
                    {
                        "name": "x_duration_hours",
                        "ttype": "float",
                        "string": "Duration (Hours)},{",
                    },
                ],
            },
            {
                "model": "x_equipment",
                "description": "Equipment",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_unavailability",
                "description": "Unavailability",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_staff_id", "res.users", "Staff"),
                ],
            },
        ],
        "actions": [
            {
                "name": "Rate Lines",
                "model": "x_rate_line",
                "view_mode": "list,kanban,form",
                "technical_name": "action_x_rate_line",
            }
        ],
        "menus": [],
        "views": [
            {
                "name": "x_rate_line.kanban",
                "model": "x_rate_line",
                "type": "kanban",
                "arch": '<kanban><templates><t t-name="card"><field name="x_name"/></t></templates></kanban>',
            }
        ],
        "sequences": [{"model": "x_rate_line", "prefix": "RL/"}],
        "automations": [
            {
                "name": "Mark done follow-up",
                "model": "x_engagement",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'completed')]",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_status",
                        "value": "done",
                    }
                ],
            }
        ],
    }


def test_close_repairs_foreign_role_hollow_cost_and_terminals() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _clinic_remaining_gaps_draft()
    sc = draft_scorecard(draft, user_prompt=prompt)
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert any("foreign-domain lexicon leak" in d for d in details)
    assert any("hollow duplicate cost header" in d for d in details)
    assert any("duplicate terminals completed and done" in d for d in details)
    assert any("corrupt field string" in d for d in details)
    assert any("equipment catalog missing usage line" in d for d in details)

    close_odoo_architecture(draft, user_prompt=prompt)
    by = _by_id(draft)
    engagement = by["x_engagement"]
    names = {f.get("name") for f in engagement["fields"]}
    assert "x_attorney_id" not in names
    site = next(f for f in engagement["fields"] if f.get("name") == "x_clinic_id")
    assert site.get("string") == "Clinic"
    status = next(f for f in engagement["fields"] if f["name"] == "x_status")
    sel = str(status.get("selection") or "")
    assert "completed" not in sel
    assert "('done'" in sel.replace(" ", "")
    autos = draft.get("automations") or []
    assert autos
    assert "completed" not in str(autos[0].get("filter_domain") or "")
    assert "done" in str(autos[0].get("filter_domain") or "")

    ids = set(by)
    assert "x_job_cost" not in ids
    assert "x_job_cost_expense" in ids
    assert "x_job_cost_expense_line" in ids

    duration = next(
        f for f in by["x_rate_line"]["fields"] if f["name"] == "x_duration_hours"
    )
    assert duration.get("string") == "Duration (Hours)"
    assert "mail.thread" not in (by["x_rate_line"].get("mixins") or [])
    o2m = next(
        f for f in by["x_rate_card"]["fields"] if f.get("ttype") == "one2many"
    )
    assert o2m.get("string") == "Lines"
    assert not any(
        str(v.get("model") or "") == "x_rate_line" and v.get("type") == "kanban"
        for v in (draft.get("views") or [])
        if isinstance(v, dict)
    )
    assert not any(
        isinstance(s, dict) and s.get("model") == "x_rate_line"
        for s in (draft.get("sequences") or [])
    )

    assert "x_equipment_line" in ids
    eq_line = by["x_equipment_line"]
    assert any(
        f.get("ttype") == "many2one" and f.get("relation") == "x_appointment"
        for f in eq_line["fields"]
    )

    staff = next(
        f for f in by["x_unavailability"]["fields"] if f.get("name") == "x_staff_id"
    )
    assert staff.get("relation") == "hr.employee"

    sc2 = draft_scorecard(draft, user_prompt=prompt)
    details2 = [str(f.get("detail") or "") for f in sc2.get("findings") or []]
    assert not any("foreign-domain lexicon leak" in d for d in details2)
    assert not any("hollow duplicate cost header" in d for d in details2)
    assert not any("duplicate terminals completed and done" in d for d in details2)
    assert not any("corrupt field string" in d for d in details2)
    assert not any("equipment catalog missing usage line" in d for d in details2)


def test_close_keeps_attorney_on_law_prompt() -> None:
    prompt = "A law firm with attorneys"
    draft = {
        "technical_name": "law_ops",
        "display_name": "Law Ops",
        "_user_prompt": prompt,
        "depends": ["base", "mail"],
        "models": [
            {
                "model": "x_matter",
                "description": "Matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_attorney_id", "res.users", "Attorney"),
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            }
        ],
        "actions": [],
        "menus": [],
        "views": [],
    }
    close_odoo_architecture(draft, user_prompt=prompt)
    matter = next(m for m in draft["models"] if m["model"] == "x_matter")
    fee = next(
        f
        for f in matter["fields"]
        if f.get("name") in {"x_attorney_id", "x_employee_id"}
        or f.get("relation") == "hr.employee"
    )
    assert fee.get("relation") == "hr.employee"


def test_close_keeps_two_lined_cost_documents() -> None:
    prompt = "Construction project tracker for site jobs"
    draft = {
        "technical_name": "construction_ops",
        "display_name": "Construction Ops",
        "_user_prompt": prompt,
        "depends": ["base", "mail"],
        "models": [
            {
                "model": "x_project",
                "description": "Project",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _status_field("draft", "open", "done"),
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_job_cost",
                "description": "Job Cost",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_project_id", "x_project"),
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_cost_line",
                        "relation_field": "x_job_cost_id",
                        "string": "Lines",
                    },
                ],
            },
            {
                "model": "x_job_cost_line",
                "description": "Job Cost Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_job_cost_id", "x_job_cost"),
                    {"name": "x_qty", "ttype": "float", "default": 1.0},
                ],
            },
            {
                "model": "x_expense",
                "description": "Expense",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_project_id", "x_project"),
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_expense_line",
                        "relation_field": "x_expense_id",
                        "string": "Lines",
                    },
                ],
            },
            {
                "model": "x_expense_line",
                "description": "Expense Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    _m2o("x_expense_id", "x_expense"),
                    {"name": "x_qty", "ttype": "float", "default": 1.0},
                ],
            },
        ],
        "actions": [],
        "menus": [],
        "views": [],
    }
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_job_cost" in ids
    assert "x_expense" in ids
    assert "x_job_cost_line" in ids
    assert "x_expense_line" in ids


def test_close_skips_hollow_cost_collapse_for_domain_pack() -> None:
    prompt = "A neighborhood clinic with walk-in appointments"
    draft = _clinic_remaining_gaps_draft()
    draft["domain_pack"] = "clinic"
    close_odoo_architecture(draft, user_prompt=prompt)
    ids = {m["model"] for m in draft["models"]}
    assert "x_job_cost" in ids
    assert "x_job_cost_expense" in ids


def test_close_drops_stock_o2m_specialty_satellite_and_hollow_autos() -> None:
    prompt = MUSIC_PROMPT
    draft = {
        "technical_name": "music_ops",
        "display_name": "Music",
        "_user_prompt": prompt,
        "depends": ["base", "mail", "hr"],
        "reuse": {"models": ["hr.employee", "res.currency"]},
        "models": [
            {
                "model": "x_studio",
                "description": "Studio",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_specialty",
                        "ttype": "selection",
                        "selection": "[('tracking','Tracking'),('mix','Mix')]",
                    },
                ],
            },
            {
                "model": "x_site_specialty",
                "description": "Site Specialty",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_crew",
                "description": "Crew",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_rate_unit",
                "description": "Rate Unit",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate",
                        "ttype": "monetary",
                        "currency_field": "x_currency_id",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_crew_ids",
                        "ttype": "one2many",
                        "relation": "x_crew",
                        "relation_field": "x_rate_unit_id",
                        "string": "Crew",
                    },
                ],
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "done"),
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_booking_line",
                        "relation_field": "x_booking_id",
                        "string": "Lines",
                    },
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_booking_id",
                        "string": "Lines",
                    },
                ],
            },
            {
                "model": "x_booking_line",
                "description": "Booking Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                ],
            },
            {
                "model": "x_equipment",
                "description": "Equipment",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_equipment_line",
                "description": "Equipment Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                ],
            },
        ],
        "automations": [
            {
                "name": "Auto-Assign Studio to Booking",
                "model": "x_booking",
                "trigger": "on_create",
                "filter_domain": "[]",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_studio_id",
                        "value": "x_studio_id",
                    }
                ],
            },
            {
                "name": "Notify Completion",
                "model": "x_booking",
                "trigger": "on_write",
                "filter_domain": "[('x_status','in',['completed','done'])]",
                "safe_actions": [
                    {
                        "kind": "mail_post",
                        "value": "Done % (x_id, x_name)",
                    }
                ],
            },
        ],
        "actions": [],
        "menus": [],
        "views": [],
    }
    close_odoo_architecture(draft, user_prompt=prompt)
    by = _by_id(draft)
    assert "x_crew" not in by
    assert "x_site_specialty" not in by
    rate = by["x_rate_unit"]
    assert not any(
        f.get("ttype") == "one2many" and str(f.get("relation") or "") == "hr.employee"
        for f in rate["fields"]
    )
    assert "x_crew_ids" not in {str(f.get("name")) for f in rate["fields"]}
    fnames = [str(f.get("name")) for f in rate["fields"]]
    assert fnames.index("x_currency_id") < fnames.index("x_rate")
    booking = by["x_booking"]
    eq_o2m = next(
        f for f in booking["fields"] if f.get("name") == "x_equipment_line_ids"
    )
    assert str(eq_o2m.get("string") or "").strip().lower() not in {"lines", "line"}
    auto_names = [str(a.get("name") or "") for a in (draft.get("automations") or [])]
    assert not any("Auto-Assign" in n for n in auto_names)
    assert not any("Notify Completion" in n for n in auto_names)


def test_close_trims_usage_line_rate_card_parent_and_search_group_by() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "_meta": {"smart_button_count": 30},
        "models": [
            {
                "model": "x_equipment",
                "description": "Equipment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_equipment_id",
                    },
                ],
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "open", "done"),
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_booking_id",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_rate_card",
                "description": "Rate Card",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_rate_card_id",
                        "source": "post_critique_line",
                    },
                ],
            },
            {
                "model": "x_rate_unit",
                "description": "Rate Unit",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "open", "active", "done"),
                    {
                        "name": "x_rate_unit_id",
                        "ttype": "many2one",
                        "relation": "x_rate_unit",
                    },
                    {
                        "name": "x_rate_unit_ids",
                        "ttype": "one2many",
                        "relation": "x_rate_unit",
                        "relation_field": "x_rate_unit_id",
                    },
                    {
                        "name": "x_crew_line_ids",
                        "ttype": "one2many",
                        "relation": "x_crew_line",
                        "relation_field": "x_rate_unit_id",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_equipment_line",
                "description": "Equipment Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                    {
                        "name": "x_rate_card_id",
                        "ttype": "many2one",
                        "relation": "x_rate_card",
                    },
                    {
                        "name": "x_site_specialty",
                        "ttype": "selection",
                        "selection": "[('recording','Recording')]",
                    },
                    {
                        "name": "x_specialty",
                        "ttype": "selection",
                        "selection": "[('recording','Recording')]",
                    },
                ],
            },
            {
                "model": "x_crew_line",
                "description": "Crew Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_unit_id",
                        "ttype": "many2one",
                        "relation": "x_rate_unit",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                        "related": "x_rate_unit_id.x_currency_id",
                    },
                ],
            },
            {
                "model": "x_booking_line",
                "description": "Booking Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_equipment",
                "related_model": "x_equipment_line",
                "relation_field": "x_equipment_id",
                "label": "Lines",
            },
            {
                "on_model": "x_rate_unit",
                "related_model": "x_rate_unit",
                "relation_field": "x_rate_unit_id",
                "label": "Rate Units",
            },
        ],
        "automations": [
            {
                "name": "Notify Booking Confirmation",
                "model": "x_booking",
                "trigger": "on_write",
                "filter_domain": "[]",
                "safe_actions": [{"kind": "mail_post", "body": "<p>ok</p>"}],
            },
            {
                "name": "Calculate Engagement Total Amount",
                "model": "x_booking",
                "trigger": "on_write",
                "filter_domain": "['x_rate_unit in ('hour','day')']",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_name",
                        "value": (
                            "x_rate * x_duration if x_rate_unit == 'hour' "
                            "else x_rate * x_duration / 8"
                        ),
                    }
                ],
            },
        ],
        "views": [
            {
                "name": "x_booking_line.search",
                "model": "x_booking_line",
                "type": "search",
                "arch": (
                    '<search string="Booking Lines">'
                    "<filter string=\"My records\" name=\"my_x_user_id\" "
                    "domain=\"[('x_user_id','=', uid)]\"/>"
                    "<filter string=\"Booking\" name=\"group_x_equipment_id\" "
                    "context=\"{'group_by': 'x_equipment_id'}\"/>"
                    "</search>"
                ),
            }
        ],
        "actions": [],
        "menus": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    by = _by_id(draft)
    line = by["x_equipment_line"]
    rels = {
        str(f.get("relation"))
        for f in line["fields"]
        if f.get("ttype") == "many2one" and str(f.get("relation") or "").startswith("x_")
    }
    assert "x_equipment" in rels
    assert "x_booking" in rels
    assert "x_rate_card" not in rels
    rate_card = by["x_rate_card"]
    assert not any(
        f.get("ttype") == "one2many" and f.get("relation") == "x_equipment_line"
        for f in rate_card["fields"]
    )
    if "x_rate_unit" in by:
        assert by["x_rate_unit"].get("is_workflow") is not True
        ru_names = {str(f.get("name")) for f in by["x_rate_unit"]["fields"]}
        assert "x_rate_unit_id" not in ru_names
        assert "x_rate_unit_ids" not in ru_names
    crew = by["x_crew_line"]
    crew_rels = {
        str(f.get("relation"))
        for f in crew["fields"]
        if f.get("ttype") == "many2one" and str(f.get("relation") or "").startswith("x_")
    }
    assert "x_rate_unit" not in crew_rels
    assert "x_booking" in crew_rels
    search = next(v for v in draft["views"] if v.get("model") == "x_booking_line")
    search_arch = str(search.get("arch") or "")
    assert "x_equipment_id" not in search_arch
    assert "group_x_equipment_id" not in search_arch
    assert "x_user_id" in search_arch
    auto_names = [str(a.get("name") or "") for a in (draft.get("automations") or [])]
    assert not any("Notify Booking" in n for n in auto_names)
    assert not any("Calculate Engagement" in n for n in auto_names)
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert not any("duplicate parent" in d for d in details)
    meta = draft.get("_meta") or {}
    assert meta.get("smart_button_count") == len(draft.get("smart_buttons") or [])


def test_expert_fix_drops_usage_line_rate_card_parent() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "_meta": {"smart_button_count": 3},
        "models": [
            {
                "model": "x_equipment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_equipment_id",
                    },
                ],
            },
            {
                "model": "x_booking",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "open", "done"),
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_booking_id",
                    },
                ],
                "state_field": {"field": "x_status"},
            },
            {
                "model": "x_rate_card",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_line_ids",
                        "ttype": "one2many",
                        "relation": "x_equipment_line",
                        "relation_field": "x_rate_card_id",
                        "source": "post_critique_line",
                    },
                ],
            },
            {
                "model": "x_equipment_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                    {
                        "name": "x_rate_card_id",
                        "ttype": "many2one",
                        "relation": "x_rate_card",
                    },
                ],
            },
        ],
        "smart_buttons": [],
        "views": [],
        "actions": [],
        "menus": [],
    }
    before = review_draft(
        draft, user_prompt=MUSIC_PROMPT, apply_fixes=False, include_narratives=False
    )
    parent_finding = next(
        (f for f in before.findings if "duplicate parent" in f.detail), None
    )
    assert parent_finding is not None
    assert parent_finding.deterministic is True
    after = review_draft(
        draft, user_prompt=MUSIC_PROMPT, apply_fixes=True, include_narratives=False
    )
    assert after.draft is not None
    line = next(m for m in after.draft["models"] if m.get("model") == "x_equipment_line")
    rels = {
        str(f.get("relation"))
        for f in (line.get("fields") or [])
        if isinstance(f, dict) and f.get("ttype") == "many2one"
    }
    assert "x_rate_card" not in rels
    assert "x_equipment" in rels
    assert "x_booking" in rels
    assert not any("duplicate parent" in f.detail for f in after.findings)
    assert not any("duplicate parent" in d for d in [
        str(f.get("detail") or "") for f in validate_consistency(after.draft)
    ])
    assert after.score_after is not None
    assert after.score_after >= before.score_before
    assert "After deterministic fixes" in after.review_markdown


def test_close_collapses_duplicate_same_parent_m2o() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "_user_prompt": "A supermarket with branches",
        "models": [
            {
                "model": "x_inventory_count",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_inventory_count_line_ids",
                        "ttype": "one2many",
                        "relation": "x_inventory_count_line",
                        "relation_field": "x_count_id",
                    },
                ],
            },
            {
                "model": "x_inventory_count_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_inventory_count_id",
                        "ttype": "many2one",
                        "relation": "x_inventory_count",
                    },
                    {
                        "name": "x_count_id",
                        "ttype": "many2one",
                        "relation": "x_inventory_count",
                    },
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt="A supermarket with branches")
    line = next(m for m in draft["models"] if m["model"] == "x_inventory_count_line")
    parent_m2os = [
        str(f.get("name"))
        for f in line["fields"]
        if f.get("ttype") == "many2one"
        and f.get("relation") == "x_inventory_count"
    ]
    assert parent_m2os == ["x_inventory_count_id"]
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert not any("duplicate parent" in d for d in details)


def test_close_drops_demoted_register_search_status_and_restores_company_group_by() -> None:
    from app.ai_live_apply_contract import live_apply_contract_findings

    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_unit",
                "description": "Rate Unit",
                "is_workflow": False,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                    },
                ],
            },
            {
                "model": "x_booking_line",
                "description": "Booking Line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                ],
            },
            {
                "model": "x_studio",
                "description": "Studio",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_booking",
                "description": "Booking",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
        "record_rules": [
            {
                "name": "Multi-company (x_booking_line)",
                "model": "x_booking_line",
                "domain_force": (
                    "['|', ('x_company_id', '=', False), "
                    "('x_company_id', 'in', company_ids)]"
                ),
                "technical_name": "rule_x_crew_line_multi_company",
            },
            {
                "name": "Multi-company (x_booking_line)",
                "model": "x_booking_line",
                "domain_force": (
                    "['|', ('x_company_id', '=', False), "
                    "('x_company_id', 'in', company_ids)]"
                ),
                "technical_name": "rule_x_booking_line_multi_company",
            },
        ],
        "views": [
            {
                "name": "x_rate_unit.search",
                "model": "x_rate_unit",
                "type": "search",
                "arch": (
                    '<search string="Rate Units">'
                    '<filter string="Active" name="status_active" '
                    "domain=\"[('x_status','=','active')]\"/>"
                    '<filter string="Studio" name="group_x_studio_id" '
                    "context=\"{'group_by': 'x_studio_id'}\"/>"
                    "</search>"
                ),
            },
            {
                "name": "x_booking_line.search",
                "model": "x_booking_line",
                "type": "search",
                "arch": (
                    '<search string="Booking Lines">'
                    '<filter string="Company" name="group_x_company_id" '
                    "context=\"{'group_by': 'x_booking_id'}\"/>"
                    "</search>"
                ),
            },
        ],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    ru_search = next(v for v in draft["views"] if v.get("model") == "x_rate_unit")
    ru_arch = str(ru_search.get("arch") or "")
    assert "x_status" not in ru_arch
    assert "x_studio_id" in ru_arch
    line = next(m for m in draft["models"] if m["model"] == "x_booking_line")
    assert any(f.get("name") == "x_company_id" for f in line["fields"])
    line_search = next(v for v in draft["views"] if v.get("model") == "x_booking_line")
    line_arch = str(line_search.get("arch") or "")
    assert "group_by': 'x_company_id'" in line_arch
    assert "group_by': 'x_booking_id'" not in line_arch
    rules = [
        r
        for r in (draft.get("record_rules") or [])
        if r.get("model") == "x_booking_line"
    ]
    assert len(rules) == 1
    details = [str(f.get("detail") or "") for f in live_apply_contract_findings(draft)]
    assert not any("search filter names missing" in d for d in details)


def test_close_collapses_asset_usage_into_line() -> None:
    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_equipment",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_booking",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_equipment_usage",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                    {"name": "x_hours_used", "ttype": "float", "required": True},
                    {"name": "x_usage_date", "ttype": "date", "required": True},
                ],
            },
            {
                "model": "x_equipment_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_id",
                        "ttype": "many2one",
                        "relation": "x_equipment",
                    },
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
        "record_rules": [
            {
                "model": "x_equipment_usage",
                "technical_name": "rule_x_equipment_usage_multi_company",
                "domain_force": "[('x_company_id','in',company_ids)]",
            },
            {
                "model": "x_equipment_usage_line",
                "technical_name": "rule_x_equipment_usage_line_multi_company",
            },
        ],
    }
    notes = close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    ids = {m["model"] for m in draft["models"]}
    assert "x_equipment_usage" not in ids
    assert "x_equipment_line" in ids
    line = next(m for m in draft["models"] if m["model"] == "x_equipment_line")
    names = {f.get("name") for f in line["fields"]}
    assert "x_hours_used" in names
    by_name = {f["name"]: f for f in line["fields"]}
    assert not by_name["x_hours_used"].get("required")
    assert not by_name["x_usage_date"].get("required")
    assert any("collapsed parallel asset usage" in n for n in notes)
    names_by_rule = {
        str(r.get("technical_name")): str(r.get("model"))
        for r in (draft.get("record_rules") or [])
    }
    assert "rule_x_equipment_line_multi_company" in names_by_rule
    assert names_by_rule["rule_x_equipment_line_multi_company"] == "x_equipment_line"
    assert "rule_x_equipment_usage_multi_company" not in names_by_rule
    assert "rule_x_equipment_usage_line_multi_company" in names_by_rule


def test_close_rewrites_collapsed_rate_selection() -> None:
    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_card",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_type",
                        "ttype": "selection",
                        "selection": "[('hourly','session')]",
                    },
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "selection": "[('hour','session')]",
                    },
                ],
            }
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    card = next(m for m in draft["models"] if m["model"] == "x_rate_card")
    by_name = {f["name"]: f for f in card["fields"]}
    from app.ai_selection import parse_selection_literal

    assert "x_rate_type" not in by_name
    unit_keys = {k for k, _ in (parse_selection_literal(by_name["x_rate_unit"]["selection"]) or [])}
    assert "hour" in unit_keys
    assert "session" in unit_keys
    assert len(unit_keys) >= 3


def test_close_drops_parent_m2o_when_o2m_exists() -> None:
    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_artist",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_party_role_id",
                        "ttype": "many2one",
                        "relation": "x_party_role",
                    },
                    {
                        "name": "x_party_role_ids",
                        "ttype": "one2many",
                        "relation": "x_party_role",
                        "relation_field": "x_artist_id",
                    },
                ],
            },
            {
                "model": "x_party_role",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_artist_id",
                        "ttype": "many2one",
                        "relation": "x_artist",
                    },
                    {
                        "name": "x_artist_ids",
                        "ttype": "one2many",
                        "relation": "x_artist",
                        "relation_field": "x_party_role_id",
                    },
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    artist = next(m for m in draft["models"] if m["model"] == "x_artist")
    role = next(m for m in draft["models"] if m["model"] == "x_party_role")
    artist_names = {f.get("name") for f in artist["fields"]}
    role_names = {f.get("name") for f in role["fields"]}
    assert "x_party_role_id" not in artist_names
    assert "x_party_role_ids" in artist_names
    assert "x_artist_id" in role_names
    assert "x_artist_ids" not in role_names


def test_close_folds_uom_register_into_rate_card() -> None:
    draft = {
        "technical_name": "music_production_recording_studios",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_card",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "selection": "[('hour','Hour'),('session','Session'),('day','Day')]",
                    },
                ],
            },
            {
                "model": "x_rate_unit",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    notes = close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    ids = {m["model"] for m in draft["models"]}
    assert "x_rate_unit" not in ids
    assert "x_rate_card" in ids
    assert any("collapsed redundant UOM register" in n for n in notes)


def test_close_keeps_unit_register_when_no_rate_card() -> None:
    draft = {
        "technical_name": "music_ops",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_unit",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    ids = {m["model"] for m in draft["models"]}
    assert "x_rate_unit" in ids


def test_close_strips_last_interaction_from_party() -> None:
    draft = {
        "technical_name": "music_ops",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_artist",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_last_interaction", "ttype": "datetime"},
                ],
            }
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    artist = next(m for m in draft["models"] if m["model"] == "x_artist")
    names = {f.get("name") for f in artist["fields"]}
    assert "x_last_interaction" not in names


def test_close_drops_terminal_status_todo_keeps_on_time() -> None:
    draft = {
        "technical_name": "music_ops",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_engagement",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    _status_field("draft", "done"),
                    {"name": "x_deadline", "ttype": "date"},
                ],
                "mixins": ["mail.thread", "mail.activity.mixin"],
            }
        ],
        "automations": [
            {
                "name": "Mark Engagement as Completed",
                "model": "x_engagement",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'done')]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "To Do", "note": "Completed"}
                ],
            },
            {
                "name": "Follow up deadline Engagement",
                "model": "x_engagement",
                "trigger": "on_time",
                "trg_date_field_name": "x_deadline",
                "filter_domain": "[('x_deadline', '!=', False)]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Follow up", "note": "Due"}
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    names = [str(a.get("name") or "") for a in (draft.get("automations") or [])]
    assert not any("Mark Engagement as Completed" in n for n in names)
    assert any("Follow up deadline" in n for n in names)


def test_close_keeps_two_lined_rate_documents() -> None:
    """Do not fold a unit register that has its own line child (lined price lists)."""
    draft = {
        "technical_name": "music_ops",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_card",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "selection": "[('hour','Hour'),('session','Session')]",
                    },
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_rate_card_line",
                        "relation_field": "x_rate_card_id",
                    },
                ],
            },
            {
                "model": "x_rate_card_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_card_id",
                        "ttype": "many2one",
                        "relation": "x_rate_card",
                    },
                ],
            },
            {
                "model": "x_rate_unit",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_rate_unit_line",
                        "relation_field": "x_rate_unit_id",
                    },
                ],
            },
            {
                "model": "x_rate_unit_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_unit_id",
                        "ttype": "many2one",
                        "relation": "x_rate_unit",
                    },
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    ids = {m["model"] for m in draft["models"]}
    assert "x_rate_card" in ids
    assert "x_rate_unit" in ids
    assert "x_rate_card_line" in ids
    assert "x_rate_unit_line" in ids


def test_rewrite_model_ident_xml_prefixed_rule() -> None:
    from app.ai_odoo_app_bar import _rewrite_model_ident

    assert (
        _rewrite_model_ident(
            "rule_x_equipment_usage_multi_company",
            "x_equipment_usage",
            "x_equipment_line",
        )
        == "rule_x_equipment_line_multi_company"
    )
    assert (
        _rewrite_model_ident(
            "rule_x_equipment_usage_line_multi_company",
            "x_equipment_usage",
            "x_equipment_line",
        )
        == "rule_x_equipment_usage_line_multi_company"
    )
    assert (
        _rewrite_model_ident("x_equipment_usage_id", "x_equipment_usage", "x_equipment_line")
        == "x_equipment_line_id"
    )


def test_close_drops_required_rate_on_lined_cost_header() -> None:
    draft = {
        "technical_name": "music_ops",
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_job_cost",
                "description": "Job Cost",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_rate", "ttype": "float", "required": True},
                    {"name": "x_amount", "ttype": "float"},
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_cost_line",
                        "relation_field": "x_job_cost_id",
                    },
                ],
            },
            {
                "model": "x_job_cost_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_job_cost_id",
                        "ttype": "many2one",
                        "relation": "x_job_cost",
                    },
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
        ],
        "views": [],
        "actions": [],
        "menus": [],
        "smart_buttons": [],
    }
    close_odoo_architecture(draft, user_prompt=MUSIC_PROMPT)
    header = next(m for m in draft["models"] if m["model"] == "x_job_cost")
    by_name = {f["name"]: f for f in header["fields"]}
    assert by_name["x_name"].get("required") is True
    assert not by_name["x_rate"].get("required")

