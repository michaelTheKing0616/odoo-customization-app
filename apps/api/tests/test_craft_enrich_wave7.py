"""Wave 7 — enrich datetime + money craft gates."""

from __future__ import annotations

from app.ai_enrich import coerce_uncued_datetime_fields, coerce_uncued_money_fields


def test_enrich_coerces_uncued_datetime() -> None:
    draft = {
        "_user_prompt": "Visitor log with Visit date only",
        "models": [
            {
                "model": "x_visitor",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_visit", "ttype": "datetime", "string": "Visit date"},
                ],
            }
        ],
    }
    notes = coerce_uncued_datetime_fields(draft)
    assert notes
    assert draft["models"][0]["fields"][1]["ttype"] == "date"


def test_enrich_keeps_datetime_with_craft() -> None:
    draft = {
        "_user_prompt": "Sessions with start time",
        "_approved_craft": {"datetime_over_date": True},
        "models": [
            {
                "model": "x_session",
                "fields": [
                    {"name": "x_start", "ttype": "datetime", "string": "Start"},
                ],
            }
        ],
    }
    notes = coerce_uncued_datetime_fields(draft)
    assert notes == [] or draft["models"][0]["fields"][0]["ttype"] == "datetime"


def test_enrich_drops_uncued_currency() -> None:
    draft = {
        "_user_prompt": "thin tickets name and state only",
        "_ambition": "thin",
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                ],
            }
        ],
        "_generate_ir": {"admitted": [{"name": "x_name"}]},
    }
    notes = coerce_uncued_money_fields(draft)
    assert notes
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_currency_id" not in names


def test_enrich_keeps_money_with_craft() -> None:
    draft = {
        "_user_prompt": "thin tickets",
        "_approved_craft": {"money_slots": True},
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                ],
            }
        ],
    }
    notes = coerce_uncued_money_fields(draft)
    assert notes == []
    assert draft["models"][0]["fields"][0]["name"] == "x_currency_id"
