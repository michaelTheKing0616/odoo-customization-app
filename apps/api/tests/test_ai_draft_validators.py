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
