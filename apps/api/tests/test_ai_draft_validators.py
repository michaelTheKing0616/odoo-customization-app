"""GEN2-13 draft validator tests."""

from __future__ import annotations

from app.ai_draft_validators import run_draft_validators, validate_view_archs


def test_validate_view_archs_flags_empty_field_tags() -> None:
    draft = {
        "models": [{"model": "x_store_order_line", "fields": [{"name": "x_name", "ttype": "char"}]}],
        "views": [
            {
                "model": "x_store_order_line",
                "type": "list",
                "arch": '<list><field name="x_name"/><field /></list>',
            }
        ],
    }
    findings = validate_view_archs(draft)
    assert any("empty field tag" in f.get("detail", "") for f in findings)


def test_run_draft_validators_green_on_minimal_valid_draft() -> None:
    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_company_id", "ttype": "many2one", "relation": "res.company"},
                ],
            }
        ],
        "views": [
            {
                "model": "x_branch",
                "type": "form",
                "arch": '<form><field name="x_name"/></form>',
            }
        ],
        "_depth": {
            "metrics": {"model_count": 1},
            "metrics_without_seeds": {"model_count": 1},
        },
    }
    out = run_draft_validators(draft)
    assert out["all_green"] is True


def test_validate_consistency_allows_catalog_and_booking_on_usage_line() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "models": [
            {"model": "x_equipment", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_booking", "fields": [{"name": "x_name", "ttype": "char"}]},
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
        ]
    }
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert not any("duplicate parent" in d for d in details)


def test_validate_consistency_flags_two_unrelated_line_parents() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "models": [
            {"model": "x_rate", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_booking", "fields": [{"name": "x_name", "ttype": "char"}]},
            {
                "model": "x_rate_line",
                "fields": [
                    {"name": "x_rate_id", "ttype": "many2one", "relation": "x_rate"},
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "relation": "x_booking",
                    },
                ],
            },
        ]
    }
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert any("duplicate parent" in d for d in details)


def test_validate_consistency_flags_usage_line_with_third_parent() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "models": [
            {"model": "x_equipment", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_booking", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_rate_card", "fields": [{"name": "x_name", "ttype": "char"}]},
            {
                "model": "x_equipment_line",
                "fields": [
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
        ]
    }
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert any("duplicate parent" in d for d in details)


def test_validate_consistency_allows_stock_fk_beside_custom_line_parent() -> None:
    from app.ai_draft_validators import validate_consistency

    draft = {
        "models": [
            {"model": "x_matter", "fields": [{"name": "x_name", "ttype": "char"}]},
            {
                "model": "hr.employee",
                "mode": "inherit",
                "fields": [{"name": "x_bar_number", "ttype": "char"}],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                    },
                ],
            },
        ]
    }
    details = [str(f.get("detail") or "") for f in validate_consistency(draft)]
    assert not any("duplicate parent" in d for d in details)
