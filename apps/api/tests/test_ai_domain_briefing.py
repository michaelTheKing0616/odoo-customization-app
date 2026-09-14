"""Pack-free domain briefing — collocations, selection rewrite, catalog bans."""

from __future__ import annotations

from app.ai_domain_briefing import apply_briefing_to_draft, build_domain_briefing
from app.ai_draft_scorecard import draft_scorecard
from app.ai_selection import parse_selection_literal
from app.ai_stock_catalog import infer_catalog_reuse, score_model_for_prompt, stock_entry

MUSIC_PROMPT = "A music production company with multiple recording studios and artistes"
FILM_PROMPT = "A film production studio with camera, lighting, and sound stages"
FACTORY_PROMPT = "A factory manufacturing plant with BOM and work orders"


def test_music_briefing_bans_mrp_and_names_console_gear() -> None:
    brief = build_domain_briefing(MUSIC_PROMPT)
    assert brief.collocation_id == "music_recording"
    assert brief.bans_stock("mrp.production")
    assert brief.bans_stock("mrp.production.group")
    keys = {k for k, _ in brief.equipment_types}
    assert "console" in keys
    assert "microphone" in keys
    assert "camera" not in keys
    assert "camera" in brief.banned_selection_keys


def test_film_studio_keeps_camera_types() -> None:
    brief = build_domain_briefing(FILM_PROMPT)
    assert brief.collocation_id == "film_studio"
    keys = {k for k, _ in brief.equipment_types}
    assert "camera" in keys
    assert "lens" in keys
    assert "console" in brief.banned_selection_keys


def test_manufacturing_allows_mrp() -> None:
    brief = build_domain_briefing(FACTORY_PROMPT)
    assert brief.collocation_id == "manufacturing"
    assert not brief.bans_stock("mrp.production")
    assert not brief.bans_stock("mrp.bom")


def test_apply_briefing_rewrites_film_types_on_music_equipment() -> None:
    draft = {
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_equipment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "selection": (
                            "[('camera','Camera'),('lens','Lens'),"
                            "('rigging','Rigging'),('lighting','Lighting')]"
                        ),
                    },
                ],
            }
        ],
        "reuse": {
            "catalog_suggestions": [
                {"model": "mrp.production", "source": "catalog"},
                {"model": "res.partner", "source": "catalog"},
            ]
        },
    }
    notes = apply_briefing_to_draft(draft, user_prompt=MUSIC_PROMPT)
    assert any("equipment types" in n for n in notes)
    field = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_type")
    keys = {k for k, _ in (parse_selection_literal(field["selection"]) or [])}
    assert "console" in keys
    assert "microphone" in keys
    assert "camera" not in keys
    suggestions = [r["model"] for r in draft["reuse"]["catalog_suggestions"]]
    assert "mrp.production" not in suggestions
    assert "res.partner" in suggestions


def test_apply_briefing_keeps_film_camera_types() -> None:
    draft = {
        "models": [
            {
                "model": "x_equipment",
                "fields": [
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "selection": (
                            "[('camera','Camera'),('lens','Lens'),"
                            "('lighting','Lighting')]"
                        ),
                    }
                ],
            }
        ]
    }
    apply_briefing_to_draft(draft, user_prompt=FILM_PROMPT)
    field = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_type")
    keys = {k for k, _ in (parse_selection_literal(field["selection"]) or [])}
    assert "camera" in keys
    assert "console" not in keys


def test_apply_briefing_rewrites_placeholder_types_on_maintenance() -> None:
    draft = {
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_maintenance",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_equipment_type",
                        "ttype": "selection",
                        "selection": "[('a','Option A'),('b','Option B'),('other','Other')]",
                    },
                ],
            }
        ],
    }
    notes = apply_briefing_to_draft(draft, user_prompt=MUSIC_PROMPT)
    assert any("placeholder types" in n for n in notes)
    field = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_equipment_type")
    keys = {k for k, _ in (parse_selection_literal(field["selection"]) or [])}
    assert "console" in keys
    assert "a" not in keys


def test_music_prompt_does_not_score_mrp_production() -> None:
    tokens = {
        "music",
        "production",
        "company",
        "multiple",
        "recording",
        "studios",
        "artistes",
    }
    score = score_model_for_prompt(
        "mrp.production", "Production Order", "mrp", tokens
    )
    assert score < 3


def test_music_prompt_does_not_infer_mrp_production() -> None:
    rows = [
        stock_entry("mrp.production", "Production Order"),
        stock_entry("mrp.production.group", "Production Group"),
        stock_entry("res.partner", "Contact"),
        stock_entry("hr.employee", "Employee"),
    ]
    hits = infer_catalog_reuse(
        MUSIC_PROMPT,
        rows,
        available_models={r["model"] for r in rows},
    )
    models = [h["model"] for h in hits]
    assert "mrp.production" not in models
    assert "mrp.production.group" not in models


def test_factory_prompt_still_infers_mrp() -> None:
    rows = [
        stock_entry("mrp.production", "Manufacturing Order"),
        stock_entry("res.partner", "Contact"),
    ]
    hits = infer_catalog_reuse(
        FACTORY_PROMPT,
        rows,
        available_models={r["model"] for r in rows},
    )
    models = [h["model"] for h in hits]
    assert "mrp.production" in models


def test_scorecard_flags_foreign_equipment_and_mrp_catalog() -> None:
    draft = {
        "technical_name": "music_app",
        "display_name": "Music",
        "models": [
            {
                "model": "x_equipment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "selection": "[('camera','Camera'),('lens','Lens')]",
                    },
                ],
            }
        ],
        "reuse": {
            "catalog_suggestions": [{"model": "mrp.production", "source": "catalog"}]
        },
        "views": [],
        "menus": [],
        "actions": [],
        "smart_buttons": [],
        "automations": [],
    }
    card = draft_scorecard(draft, user_prompt=MUSIC_PROMPT)
    details = " ".join(str(f.get("detail") or "") for f in card.get("findings") or [])
    assert "foreign-industry selection" in details
    assert "banned catalog reuse" in details


def test_apply_briefing_expands_truncated_rate_uoms() -> None:
    draft = {
        "_user_prompt": MUSIC_PROMPT,
        "models": [
            {
                "model": "x_rate_card",
                "fields": [
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "selection": "[('hour','session')]",
                    },
                    {
                        "name": "x_rate_type",
                        "ttype": "selection",
                        "selection": "[('hourly','session')]",
                    },
                ],
            }
        ],
    }
    notes = apply_briefing_to_draft(draft, user_prompt=MUSIC_PROMPT)
    assert any("rate UOMs" in n for n in notes)
    by_name = {f["name"]: f for f in draft["models"][0]["fields"]}
    for fname in ("x_rate_unit", "x_rate_type"):
        keys = {k for k, _ in (parse_selection_literal(by_name[fname]["selection"]) or [])}
        assert "hour" in keys
        assert "session" in keys
        assert len(keys) >= 3


AOP_LEGAL_BRIEF = (
    "Adeyemi, Okonkwo & Partners law firm. Domain is Law Firm / Legal Practice, "
    "not restaurant or hotel. No third-party food marketplace. "
    "No shop-floor or kitchen hardware. Multi-company is not required; "
    "Lagos and Abuja are two offices of one company. Paystack retainers. "
    "WhatsApp intake. PAYE, PENCOM, NHF."
)


def test_adeyemi_brief_is_not_restaurant_collocation() -> None:
    brief = build_domain_briefing(AOP_LEGAL_BRIEF)
    assert brief.collocation_id != "restaurant"
    assert brief.collocation_id != "hotel"
    keys = {k for k, _ in brief.equipment_types}
    assert "fryer" not in keys
    assert "oven" not in keys


def test_adeyemi_brief_with_harvest_client_is_not_farm() -> None:
    prompt = (
        AOP_LEGAL_BRIEF
        + " Sample clients: Northern Harvest Ltd; Rivers Marine Services; Adaeze Nwosu."
    )
    brief = build_domain_briefing(prompt)
    assert brief.collocation_id != "farm"
    assert "tractor" not in {k for k, _ in brief.equipment_types}
    from app.ai_domain_briefing import attach_domain_briefing

    draft = {"domain_pack": "law_firm", "_user_prompt": prompt, "_domain_briefing": brief.to_dict()}
    attached = attach_domain_briefing(draft, user_prompt=prompt)
    assert attached.collocation_id is None
    assert attached.industry == "legal practice"
    assert attached.source == "pack"


def test_positive_restaurant_brief_still_collocates() -> None:
    brief = build_domain_briefing(
        "Neighborhood restaurant with kitchen display, chef station, and dining room."
    )
    assert brief.collocation_id == "restaurant"
    keys = {k for k, _ in brief.equipment_types}
    assert "fryer" in keys
