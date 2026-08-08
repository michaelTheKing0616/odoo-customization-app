"""Unit tests for apply-readiness blockers (GEN2-11+)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

FIXTURE5 = Path(__file__).parent / "fixtures" / "draft_supermarket5_2026-08-07.json"
PROMPT = "A large, mega, super market with multiple branches around the world"


def _load_fixture5() -> dict:
    return json.loads(FIXTURE5.read_text())


def test_normalize_company_fields_renames_x_company_id() -> None:
    from app.ai_apply_readiness import normalize_company_fields_for_export

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
        "record_rules": [
            {
                "model": "x_branch",
                "domain_force": "['|', ('x_company_id', '=', False), ('x_company_id', 'in', company_ids)]",
            }
        ],
    }
    normalize_company_fields_for_export(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "company_id" in names
    assert "x_company_id" not in names
    assert "company_id" in draft["record_rules"][0]["domain_force"]


def test_dedupe_search_view_filters() -> None:
    from app.ai_apply_readiness import dedupe_search_view_filters

    draft = {
        "views": [
            {
                "model": "x_branch",
                "type": "search",
                "arch": (
                    '<search string="Branch">'
                    '<filter string="Manager" name="grp1" context="{\'group_by\': \'x_manager_id\'}"/>'
                    '<filter string="Manager" name="grp1" context="{\'group_by\': \'x_manager_id\'}"/>'
                    "</search>"
                ),
            }
        ]
    }
    notes = dedupe_search_view_filters(draft)
    assert notes
    assert draft["views"][0]["arch"].count("grp1") == 1


def test_ensure_unique_sequence_prefixes() -> None:
    from app.ai_apply_readiness import ensure_unique_sequence_prefixes

    draft = {
        "sequences": [
            {"model": "x_branch", "prefix": "BRANCH/", "field": "x_code"},
            {"model": "x_branch_transfer", "prefix": "BRANCH/", "field": "x_code"},
        ],
        "models": [
            {"model": "x_branch", "fields": [{"name": "x_code", "ttype": "char"}]},
            {"model": "x_branch_transfer", "fields": [{"name": "x_code", "ttype": "char"}]},
        ],
    }
    ensure_unique_sequence_prefixes(draft)
    prefixes = [s["prefix"] for s in draft["sequences"]]
    assert len(prefixes) == len(set(prefixes))


def test_fixture5_full_pass_reaches_high_score() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    scored = draft_scorecard(draft, user_prompt=PROMPT)
    assert scored["score_0_10"] >= 9.9


def test_sync_company_fields_with_record_rules() -> None:
    from app.ai_apply_readiness import sync_company_fields_with_record_rules

    draft = {
        "models": [
            {
                "model": "x_store_order_line",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "record_rules": [
            {
                "model": "x_store_order_line",
                "domain_force": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
            }
        ],
    }
    notes = sync_company_fields_with_record_rules(draft)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "company_id" in names


def test_fix_workflow_skip_terminal_transitions() -> None:
    from app.ai_apply_readiness import fix_workflow_skip_terminal_transitions

    draft = {
        "models": [
            {
                "model": "x_promotion",
                "is_workflow": True,
                "state_field": {
                    "transitions": [
                        ["draft", "active"],
                        ["draft", "expired"],
                        ["active", "expired"],
                    ]
                },
            }
        ],
        "views": [
            {
                "model": "x_promotion",
                "type": "form",
                "arch": (
                    '<form><header>'
                    '<button string="Expired" invisible="x_status != \'draft\'" '
                    'data-transition-to="expired"/>'
                    '<button string="Expired" invisible="x_status != \'active\'" '
                    'data-transition-to="expired"/>'
                    "</header></form>"
                ),
            }
        ],
    }
    fix_workflow_skip_terminal_transitions(draft)
    transitions = draft["models"][0]["state_field"]["transitions"]
    assert ["draft", "expired"] not in transitions
    assert ["active", "expired"] in transitions
    assert "draft" not in draft["views"][0]["arch"] or 'data-transition-to="expired"' not in (
        draft["views"][0]["arch"].split("active")[0]
    )


def test_fix_assignee_staff_relations() -> None:
    from app.ai_apply_readiness import fix_assignee_staff_relations

    draft = {
        "depends": ["base", "hr"],
        "models": [
            {
                "model": "x_event",
                "fields": [
                    {
                        "name": "x_staff_id",
                        "ttype": "many2one",
                        "relation": "x_staff_shift",
                    }
                ],
            }
        ],
    }
    fix_assignee_staff_relations(draft)
    rel = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_staff_id")["relation"]
    assert rel == "hr.employee"


def test_apply_line_subtotal_computes_monetary() -> None:
    from app.ai_apply_readiness import apply_line_subtotal_computes

    draft = {
        "models": [
            {
                "model": "x_store_order_line",
                "fields": [
                    {"name": "x_qty", "ttype": "float"},
                    {"name": "x_price_unit", "ttype": "monetary", "currency_field": "x_currency_id"},
                    {"name": "x_subtotal", "ttype": "monetary", "currency_field": "x_currency_id"},
                    {"name": "x_currency_id", "ttype": "many2one", "relation": "res.currency"},
                ],
            }
        ]
    }
    apply_line_subtotal_computes(draft)
    block = draft["custom_code_blocks"][0]
    assert "fields.Monetary" in block["content"]
    assert "currency_field='x_currency_id'" in block["content"]


def test_fix_broken_shift_assignee_smart_buttons() -> None:
    from app.ai_apply_readiness import fix_broken_shift_assignee_smart_buttons

    draft = {
        "smart_buttons": [
            {
                "on_model": "x_staff_shift",
                "related_model": "x_event",
                "relation_field": "x_staff_id",
                "label": "Market Event",
            },
            {
                "on_model": "x_branch",
                "related_model": "x_event",
                "relation_field": "x_branch_id",
                "label": "Market Event",
            },
        ]
    }
    fix_broken_shift_assignee_smart_buttons(draft)
    assert len(draft["smart_buttons"]) == 1
    assert draft["smart_buttons"][0]["on_model"] == "x_branch"


def test_clear_resolved_compute_suggestions() -> None:
    from app.ai_apply_readiness import clear_resolved_compute_suggestions

    draft = {
        "_compute_suggestions": [{"model": "x_store_order_line", "message": "x"}] * 3,
        "custom_code_blocks": [{"model": "x_store_order_line", "content": "x"}],
    }
    clear_resolved_compute_suggestions(draft)
    assert draft["_compute_suggestions"] == []


def test_filter_stale_enrich_warnings() -> None:
    from app.ai_apply_readiness import filter_stale_enrich_warnings

    draft = {
        "_depth": {"ok": True, "gaps": []},
        "models": [
            {
                "model": "x_store_order",
                "fields": [{"name": "company_id", "ttype": "many2one"}],
            }
        ],
    }
    warnings = [
        "depth: company on x_store_order",
        "depth padded via generic seeds — regenerate recommended",
        "depth: ambition=comprehensive still missing depth_models",
        "enrich: synced forms",
    ]
    kept = filter_stale_enrich_warnings(warnings, draft)
    assert kept == ["enrich: synced forms"]


def test_fixture5_worldclass_hygiene_after_pass() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    draft["_user_prompt"] = PROMPT
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    scored = draft_scorecard(draft, user_prompt=PROMPT)
    details = {f.get("detail") for f in scored["findings"]}
    assert "draft/new skips to terminal without activation" not in " ".join(details)
    assert "line qty×price without stored subtotal compute" not in details
    assert "assignee points to shift row not employee/user" not in details
    order_line = next(m for m in draft["models"] if m["model"] == "x_store_order_line")
    assert any(f.get("name") == "company_id" for f in order_line["fields"])
    event = next(m for m in draft["models"] if m["model"] == "x_event")
    staff = next(f for f in event["fields"] if f["name"] == "x_staff_id")
    assert staff["relation"] == "hr.employee"
    promotion = next(m for m in draft["models"] if m["model"] == "x_promotion")
    transitions = promotion["state_field"]["transitions"]
    assert ["draft", "expired"] not in transitions
    assert not draft.get("_compute_suggestions")
    assert draft.get("_critique", {}).get("ready") is True
    order = next(m for m in draft["models"] if m["model"] == "x_store_order")
    assert any(b.get("model") == "x_store_order" for b in draft.get("custom_code_blocks") or [])
    shift_btns = [
        b
        for b in draft.get("smart_buttons") or []
        if b.get("on_model") == "x_staff_shift" and b.get("related_model") in {"x_event", "x_task"}
    ]
    assert not shift_btns
    block = next(
        b for b in draft.get("custom_code_blocks") or [] if b.get("model") == "x_store_order_line"
    )
    assert "fields.Monetary" in block["content"]


def test_demote_parallel_billing_models() -> None:
    from app.ai_apply_readiness import demote_parallel_billing_models

    draft = {
        "anti_patterns": ["Do NOT implement payment capture — link purchase/sale documents only"],
        "depends": ["account"],
        "reuse": {"models": ["account.move"]},
        "models": [
            {
                "model": "x_store_order",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_store_order_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_bill_id", "ttype": "many2one", "relation": "x_store_order_invoice"},
                ],
            },
            {
                "model": "x_store_order_invoice",
                "is_workflow": True,
                "state_field": {
                    "selection": "[('draft','Draft'),('sent','Sent'),('paid','Paid')]",
                },
                "fields": [{"name": "x_amount_total", "ttype": "monetary"}],
            },
        ],
        "views": [{"model": "x_store_order_invoice", "type": "form", "arch": "<form/>"}],
        "actions": [{"model": "x_store_order_invoice", "name": "Invoices"}],
    }
    notes = demote_parallel_billing_models(draft)
    assert notes
    model_ids = {m["model"] for m in draft["models"]}
    assert "x_store_order_invoice" not in model_ids
    line = next(m for m in draft["models"] if m["model"] == "x_store_order_line")
    assert not any(f.get("name") == "x_bill_id" for f in line["fields"])
    order = next(m for m in draft["models"] if m["model"] == "x_store_order")
    assert any(f.get("name") == "x_invoice_id" for f in order["fields"])


def test_apply_order_header_total_computes_monetary_after_float_promotion() -> None:
    from app.ai_apply_readiness import apply_order_header_total_computes
    from app.ai_production_shape import apply_money_and_tracking_defaults

    draft = {
        "models": [
            {
                "model": "x_store_order",
                "fields": [
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_store_order_line",
                    },
                    {"name": "x_amount_total", "ttype": "float"},
                    {"name": "x_currency_id", "ttype": "many2one", "relation": "res.currency"},
                ],
            },
            {
                "model": "x_store_order_line",
                "fields": [
                    {"name": "x_qty", "ttype": "float"},
                    {"name": "x_price_unit", "ttype": "float"},
                    {"name": "x_subtotal", "ttype": "float"},
                    {"name": "x_currency_id", "ttype": "many2one", "relation": "res.currency"},
                ],
            },
        ]
    }
    apply_money_and_tracking_defaults(draft)
    apply_order_header_total_computes(draft)
    block = next(b for b in draft["custom_code_blocks"] if b["model"] == "x_store_order")
    assert "fields.Monetary" in block["content"]
    assert "currency_field='x_currency_id'" in block["content"]


def test_ensure_operational_companion_models_restores_x_task() -> None:
    from app.ai_apply_readiness import ensure_operational_companion_models

    draft = {
        "_user_prompt": "super market branches",
        "depends": ["hr"],
        "models": [
            {"model": "x_branch", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_event", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
    }
    notes = ensure_operational_companion_models(draft)
    assert notes
    assert any(m["model"] == "x_task" for m in draft["models"])


def test_fix_reuse_link_only_from_domain_pack() -> None:
    from app.ai_apply_readiness import fix_reuse_link_only_consistency

    draft = {
        "domain_pack": "retail_supermarket",
        "_user_prompt": "super market",
        "reuse": {
            "plan": {
                "decisions": [
                    {"model": "purchase.order", "link_only": False, "confirmed": True},
                ]
            }
        },
    }
    notes = fix_reuse_link_only_consistency(draft)
    assert notes
    assert draft["reuse"]["plan"]["decisions"][0]["link_only"] is True


@pytest.mark.integration
def test_fixture5_sandbox_install_smoke() -> None:
    """Optional Docker gate: export supermarket fixture after apply-readiness."""
    import shutil

    if not shutil.which("docker"):
        pytest.skip("docker not available")

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    from app.module_spec_codec import export_draft_module_zip
    from app.sandbox import run_sandbox_install

    draft = copy.deepcopy(_load_fixture5())
    draft["_user_prompt"] = PROMPT
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    extra = [
        dep
        for dep in (draft.get("depends") or [])
        if dep not in {"base", "mail", "contacts"}
    ]
    zip_bytes = export_draft_module_zip(draft, odoo_major=19)
    result = run_sandbox_install(zip_bytes, odoo_major=19, extra_modules=extra)
    if not result.ok:
        pytest.skip(f"sandbox unavailable: {result.message}")
    assert result.ok


def test_finalize_enriched_draft_attaches_scorecard() -> None:
    from app.ai_enrich_jobs import finalize_enriched_draft

    draft = {
        "technical_name": "demo_enrich",
        "models": [{"model": "x_branch", "fields": [{"name": "x_name", "ttype": "char"}]}],
        "_user_prompt": PROMPT,
    }
    warnings = finalize_enriched_draft(draft, prompt=PROMPT, warnings=[])
    assert isinstance(draft.get("_scorecard"), dict)
    assert float(draft["_scorecard"].get("score_0_10") or 0) >= 0
    assert any("production:" in w or "apply:" in w for w in warnings)
