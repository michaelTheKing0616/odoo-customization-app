"""Unit tests for apply-readiness blockers (GEN2-11+)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

FIXTURE5 = Path(__file__).parent / "fixtures" / "draft_supermarket5_2026-08-07.json"
FIXTURE_SEMANTIC = (
    Path(__file__).parent / "fixtures" / "draft_supermarket_semantic_corrupted_2026-08-10.json"
)
PROMPT = "A large, mega, super market with multiple branches around the world"


def _load_fixture5() -> dict:
    return json.loads(FIXTURE5.read_text())


def test_normalize_company_fields_renames_company_id_to_live() -> None:
    from app.ai_apply_readiness import normalize_company_fields_for_live

    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                ],
            }
        ],
        "record_rules": [
            {
                "model": "x_branch",
                "domain_force": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
            }
        ],
    }
    normalize_company_fields_for_live(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_company_id" in names
    assert "company_id" not in names
    assert "x_company_id" in draft["record_rules"][0]["domain_force"]


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


def test_ensure_search_filter_names_adds_group_by_names() -> None:
    from app.ai_apply_readiness import ensure_search_filter_names

    draft = {
        "views": [
            {
                "model": "x_branch",
                "type": "search",
                "arch": (
                    '<search string="Branch">'
                    '<filter string="Manager" context="{\'group_by\': \'x_manager_id\'}"/>'
                    "</search>"
                ),
            }
        ]
    }
    notes = ensure_search_filter_names(draft)
    assert notes
    assert 'name="group_x_manager_id"' in draft["views"][0]["arch"]


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
    assert "x_company_id" in names


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
    assert any(f.get("name") == "x_company_id" for f in order_line["fields"])
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
    order_names = {f.get("name") for f in order["fields"]}
    assert "x_purchase_order_id" not in order_names
    assert "x_promotion_id" in order_names
    promotion = next(m for m in draft["models"] if m["model"] == "x_promotion")
    promo_names = {f.get("name") for f in promotion["fields"]}
    assert "x_store_order_ids" in promo_names
    assert scored["score_0_10"] >= 9.9


def test_demote_parallel_billing_models() -> None:
    from app.ai_apply_readiness import demote_parallel_billing_models, ensure_transaction_document_links

    draft = {
        "anti_patterns": ["Do NOT implement payment capture — link purchase/sale documents only"],
        "depends": ["account"],
        "reuse": {"models": ["account.move"]},
        "models": [
            {
                "model": "x_store_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_line_ids", "ttype": "one2many", "relation": "x_store_order_line"},
                ],
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
    notes.extend(ensure_transaction_document_links(draft))
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


def test_scrub_payment_capture_fields() -> None:
    from app.ai_apply_readiness import scrub_payment_capture_fields

    draft = {
        "anti_patterns": ["Do NOT implement payment capture — link purchase/sale only"],
        "models": [
            {
                "model": "x_store_order",
                "fields": [
                    {"name": "x_payment_status", "ttype": "selection", "selection": "[('paid','Paid')]"},
                    {"name": "x_name", "ttype": "char"},
                ],
            }
        ],
    }
    scrub_payment_capture_fields(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_payment_status" not in names


def test_consolidate_header_monetary_fields() -> None:
    from app.ai_apply_readiness import consolidate_header_monetary_fields

    draft = {
        "models": [
            {
                "model": "x_store_order",
                "fields": [
                    {"name": "x_line_ids", "ttype": "one2many", "relation": "x_store_order_line"},
                    {"name": "x_amount_total", "ttype": "monetary"},
                    {"name": "x_total_amount", "ttype": "monetary"},
                    {"name": "x_tax_amount", "ttype": "monetary"},
                ],
            },
            {"model": "x_store_order_line", "fields": [{"name": "x_subtotal", "ttype": "monetary"}]},
        ],
        "custom_code_blocks": [
            {"model": "x_store_order", "content": "def _compute_x_amount_total(self): pass"}
        ],
    }
    consolidate_header_monetary_fields(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_amount_total" in names
    assert "x_total_amount" not in names
    assert "x_tax_amount" not in names


def test_ensure_transaction_document_links_purchase() -> None:
    from app.ai_apply_readiness import ensure_transaction_document_links

    draft = {
        "depends": ["purchase"],
        "reuse": {"models": ["purchase.order"]},
        "models": [
            {
                "model": "x_supplier_purchase",
                "is_workflow": True,
                "fields": [
                    {"name": "x_supplier_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "x_line_ids", "ttype": "one2many", "relation": "x_supplier_purchase_line"},
                ],
            }
        ],
    }
    notes = ensure_transaction_document_links(draft)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_purchase_order_id" in names


def test_ensure_transaction_document_links_skips_purchase_on_sales_order() -> None:
    from app.ai_apply_readiness import (
        ensure_transaction_document_links,
        scrub_misapplied_stock_document_links,
    )

    draft = {
        "depends": ["purchase"],
        "reuse": {"models": ["purchase.order"]},
        "models": [
            {
                "model": "x_store_order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_line_ids", "ttype": "one2many", "relation": "x_store_order_line"},
                    {"name": "x_purchase_order_id", "ttype": "many2one", "relation": "purchase.order"},
                ],
            }
        ],
    }
    scrub_misapplied_stock_document_links(draft)
    ensure_transaction_document_links(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_purchase_order_id" not in names


def test_ensure_campaign_order_links() -> None:
    from app.ai_apply_readiness import ensure_campaign_order_links

    draft = {
        "models": [
            {
                "model": "x_store_order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_line_ids", "ttype": "one2many", "relation": "x_store_order_line"},
                ],
            },
            {
                "model": "x_promotion",
                "is_workflow": True,
                "fields": [{"name": "x_discount_pct", "ttype": "float"}],
            },
        ]
    }
    notes = ensure_campaign_order_links(draft)
    assert notes
    order = next(m for m in draft["models"] if m["model"] == "x_store_order")
    promotion = next(m for m in draft["models"] if m["model"] == "x_promotion")
    assert any(f["name"] == "x_promotion_id" for f in order["fields"])
    assert any(
        f["name"] == "x_store_order_ids"
        and f.get("relation_field") == "x_promotion_id"
        for f in promotion["fields"]
    )


def test_dedupe_enrich_warnings() -> None:
    from app.ai_apply_readiness import dedupe_enrich_warnings

    kept = dedupe_enrich_warnings(
        [
            "workflow: semantic transitions on x_task (4 edges, 3 statusbar)",
            "workflow: semantic transitions on x_task (4 edges, 3 statusbar)",
            "presentation: line-total compute suggestion on x_store_order_line",
        ]
    )
    assert len(kept) == 2


def test_filter_stale_orphan_quality_warnings() -> None:
    from app.ai_apply_readiness import filter_stale_enrich_warnings

    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [{"name": "x_country_id", "ttype": "many2one", "relation": "res.country"}],
            }
        ]
    }
    kept = filter_stale_enrich_warnings(
        ["quality: dropped orphan field x_branch.x_country_id → res.country"],
        draft,
    )
    assert kept == []


def test_sanitize_automation_state_references_overdue() -> None:
    from app.ai_apply_readiness import sanitize_automation_state_references

    draft = {
        "models": [
            {
                "model": "x_task",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    }
                ],
            }
        ],
        "automations": [
            {
                "name": "Flag overdue on x_task",
                "model": "x_task",
                "filter_domain": "[('x_status', 'in', ['draft', 'open'])]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Flag overdue on x_task"}
                ],
            }
        ],
    }
    sanitize_automation_state_references(draft)
    assert "deadline" in draft["automations"][0]["name"].lower()
    assert "overdue" not in draft["automations"][0]["name"].lower()
    assert "deadline" in draft["automations"][0]["safe_actions"][0]["summary"].lower()
    assert "overdue" not in draft["automations"][0]["safe_actions"][0]["summary"].lower()


def test_sanitize_automation_object_writes_drops_invalid_status() -> None:
    from app.ai_apply_readiness import sanitize_automation_object_writes

    draft = {
        "models": [
            {
                "model": "x_task",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    }
                ],
            }
        ],
        "automations": [
            {
                "name": "Flag deadline on x_task",
                "model": "x_task",
                "trigger": "on_time",
                "filter_domain": "[('x_date_deadline', '<', 'now'), ('x_status', 'in', ['draft', 'open'])]",
                "safe_actions": [
                    {"kind": "object_write", "field": "x_status", "value": "overdue"},
                    {"kind": "next_activity", "summary": "deadline follow-up"},
                ],
            }
        ],
    }
    sanitize_automation_object_writes(draft)
    kinds = [a.get("kind") for a in draft["automations"][0]["safe_actions"]]
    assert "object_write" not in kinds
    assert "next_activity" in kinds


def test_dedupe_automations_by_signature_keeps_activity_only() -> None:
    from app.ai_apply_readiness import dedupe_automations_by_signature

    dom = "[('x_date_deadline', '<', 'now'), ('x_status', 'in', ['draft', 'open'])]"
    draft = {
        "automations": [
            {
                "name": "Flag deadline on x_task",
                "model": "x_task",
                "trigger": "on_time",
                "filter_domain": dom,
                "source": "rules_engine",
                "safe_actions": [{"kind": "next_activity", "summary": "Flag deadline on x_task"}],
            },
            {
                "name": "Flag deadline on x_task",
                "model": "x_task",
                "trigger": "on_time",
                "filter_domain": dom,
                "source": "rules_engine",
                "safe_actions": [
                    {"kind": "object_write", "field": "x_status", "value": "overdue"},
                    {"kind": "next_activity", "summary": "deadline follow-up"},
                ],
            },
        ]
    }
    dedupe_automations_by_signature(draft)
    assert len(draft["automations"]) == 1
    assert draft["automations"][0]["safe_actions"] == [
        {"kind": "next_activity", "summary": "Flag deadline on x_task"}
    ]


def test_v6_automation_pass_on_task_deadline_duplicate() -> None:
    from app.ai_apply_readiness import (
        dedupe_automations_by_signature,
        sanitize_automation_object_writes,
        sanitize_automation_state_references,
    )

    dom = "[('x_date_deadline', '<', 'now'), ('x_status', 'in', ['draft', 'open'])]"
    draft = {
        "models": [
            {
                "model": "x_task",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done'),('cancelled','Cancelled')]",
                    }
                ],
            }
        ],
        "automations": [
            {
                "name": "Flag overdue on x_task",
                "model": "x_task",
                "trigger": "on_time",
                "description": "Safety-net: when x_date_deadline is past → overdue",
                "filter_domain": dom,
                "source": "rules_engine",
                "safe_actions": [{"kind": "next_activity", "summary": "Flag overdue on x_task"}],
            },
            {
                "name": "Flag overdue on x_task",
                "model": "x_task",
                "trigger": "on_time",
                "description": "Safety-net: when x_date_deadline is past → overdue",
                "filter_domain": dom,
                "source": "rules_engine",
                "safe_actions": [
                    {"kind": "object_write", "field": "x_status", "value": "overdue"},
                    {"kind": "next_activity", "summary": "deadline follow-up"},
                ],
            },
        ],
    }
    sanitize_automation_state_references(draft)
    sanitize_automation_object_writes(draft)
    dedupe_automations_by_signature(draft)
    assert len(draft["automations"]) == 1
    auto = draft["automations"][0]
    assert "deadline" in auto["name"].lower()
    assert all(a.get("kind") == "next_activity" for a in auto["safe_actions"])
    assert "overdue" not in str(auto["safe_actions"]).lower()


def _thin_supermarket_draft() -> dict:
    return {
        "technical_name": "super_market_branches",
        "display_name": "Super Market",
        "domain_pack": "retail_supermarket",
        "_user_prompt": PROMPT,
        "_ambition": "comprehensive",
        "depends": ["base", "contacts", "mail", "product", "purchase", "stock", "hr"],
        "groups": [
            {"id": "group_super_market_branches_user", "name": "Super Market User"},
            {"id": "group_super_market_branches_manager", "name": "Super Market Manager"},
        ],
        "models": [
            {
                "model": "x_branch",
                "description": "Branch / Store location",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_manager_id", "ttype": "many2one", "relation": "res.users"},
                    {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                ],
            },
            {
                "model": "x_store_order",
                "description": "Store sales order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_store_order_line",
                        "relation_field": "x_order_id",
                    },
                ],
            },
            {"model": "x_store_order_line", "fields": [{"name": "x_name", "ttype": "char"}]},
            {
                "model": "x_branch_transfer",
                "description": "Inter-branch stock transfer",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_branch_from_id", "ttype": "many2one", "relation": "x_branch"},
                    {"name": "x_branch_to_id", "ttype": "many2one", "relation": "x_branch"},
                    {"name": "x_product_id", "ttype": "many2one", "relation": "product.product"},
                    {"name": "x_qty", "ttype": "float"},
                    {"name": "x_country_id", "ttype": "many2one", "relation": "res.country"},
                ],
            },
            {
                "model": "x_inventory_count",
                "description": "Stock count session",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                    {"name": "x_product_id", "ttype": "many2one", "relation": "product.product"},
                    {"name": "x_qty_system", "ttype": "float"},
                    {"name": "x_qty_counted", "ttype": "float"},
                ],
            },
            {
                "model": "x_supplier_agreement",
                "description": "Supplier terms / rebate",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner", "string": "Supplier"},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                ],
            },
            {
                "model": "x_event",
                "description": "Market Event",
                "source": "depth_seed",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                    {"name": "x_date", "ttype": "date"},
                    {"name": "x_location", "ttype": "char"},
                    {"name": "x_staff_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                    {"name": "x_notes", "ttype": "text"},
                ],
            },
            {
                "model": "x_task",
                "description": "Market Task",
                "source": "depth_seed",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                    {"name": "x_date_deadline", "ttype": "date"},
                    {"name": "x_status", "ttype": "selection", "selection": "[('draft','Draft'),('open','Open')]"},
                    {"name": "x_staff_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                    {"name": "x_notes", "ttype": "text"},
                ],
            },
        ],
        "reuse": {"models": ["purchase.order"]},
        "record_rules": [],
        "views": [
            {
                "model": "x_branch_transfer",
                "type": "form",
                "arch": '<form><field name="x_country_id"/><field name="x_product_id"/></form>',
            }
        ],
    }


def test_promote_retail_depth_seeds_clears_depth_gap() -> None:
    from app.ai_apply_readiness import (
        ensure_header_line_models,
        promote_retail_depth_seeds,
        reconcile_depth_metadata,
    )
    from app.ai_depth import depth_gaps

    draft = _thin_supermarket_draft()
    assert "depth_models" in depth_gaps(draft, "comprehensive")
    promote_retail_depth_seeds(draft)
    ensure_header_line_models(draft)
    event = next(m for m in draft["models"] if m["model"] == "x_event")
    assert event["source"] == "retail_depth"
    assert "depth_seed" not in event["description"].lower()
    reconcile_depth_metadata(draft)
    assert "depth_models" not in (draft.get("_depth") or {}).get("gaps", [])


def test_ensure_header_line_models_scaffolds_transfer_and_count_lines() -> None:
    from app.ai_apply_readiness import ensure_header_line_models

    draft = _thin_supermarket_draft()
    notes = ensure_header_line_models(draft)
    mids = {m["model"] for m in draft["models"]}
    assert "x_branch_transfer_line" in mids
    assert "x_inventory_count_line" in mids
    assert any("scaffolded x_branch_transfer_line" in n for n in notes)
    transfer = next(m for m in draft["models"] if m["model"] == "x_branch_transfer")
    assert "x_product_id" not in {f["name"] for f in transfer["fields"]}
    line = next(m for m in draft["models"] if m["model"] == "x_branch_transfer_line")
    assert any(f.get("name") == "x_transfer_id" for f in line["fields"])


def test_prune_transfer_country_field() -> None:
    from app.ai_apply_readiness import prune_transfer_country_field

    draft = _thin_supermarket_draft()
    prune_transfer_country_field(draft)
    transfer = next(m for m in draft["models"] if m["model"] == "x_branch_transfer")
    assert "x_country_id" not in {f["name"] for f in transfer["fields"]}
    form = next(v for v in draft["views"] if v["model"] == "x_branch_transfer")
    assert "x_country_id" not in form["arch"]


def test_strip_branch_manager_scope_rules() -> None:
    from app.ai_apply_readiness import strip_branch_manager_scope_rules

    draft = _thin_supermarket_draft()
    draft["record_rules"] = [
        {
            "model": "x_store_order",
            "domain_force": (
                "['|', ('x_branch_id', '=', False), "
                "('x_branch_id.x_manager_id', '=', user.id)]"
            ),
            "group_xml_ids": ["group_super_market_branches_user"],
            "technical_name": "rule_x_store_order_branch_manager_scope",
            "name": "Branch manager scope (x_store_order)",
        }
    ]
    notes = strip_branch_manager_scope_rules(draft)
    assert any("removed branch-manager scope" in n for n in notes)
    assert not any(
        "x_branch_id.x_manager_id" in str(r.get("domain_force") or "")
        for r in draft.get("record_rules") or []
    )


def test_supplier_agreement_gets_purchase_order_link() -> None:
    from app.ai_apply_readiness import ensure_transaction_document_links

    draft = _thin_supermarket_draft()
    ensure_transaction_document_links(draft)
    agreement = next(m for m in draft["models"] if m["model"] == "x_supplier_agreement")
    assert any(f.get("name") == "x_purchase_order_id" for f in agreement["fields"])


def test_thin_supermarket_reaches_ten_after_production_shape() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    from app.ai_depth import depth_gaps

    draft = _thin_supermarket_draft()
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    assert "depth_models" not in depth_gaps(draft, "comprehensive")
    scored = draft_scorecard(draft, user_prompt=PROMPT)
    assert scored["score_0_10"] >= 9.8
    assert draft.get("_depth", {}).get("ok") is True


@pytest.mark.integration
def test_fixture5_export_access_groups_prefixed() -> None:
    import io
    import zipfile

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    from app.module_spec_codec import export_draft_module_zip

    draft = copy.deepcopy(_load_fixture5())
    draft["_user_prompt"] = PROMPT
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    zip_bytes = export_draft_module_zip(draft, odoo_major=19)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        manifest = z.read("retail_supermarket/__manifest__.py").decode()
        csv = z.read("retail_supermarket/security/ir.model.access.csv").decode()
    assert "security/groups.xml" in manifest
    assert manifest.index("security/groups.xml") < manifest.index("security/ir.model.access.csv")
    assert "retail_supermarket.group_retail_supermarket_user" in csv


def test_wire_reuse_stock_documents_confirms_sale_and_account() -> None:
    from app.ai_apply_readiness import wire_reuse_stock_documents

    draft = {
        "depends": ["base", "mail", "contacts"],
        "_pack_reuse_stock": [
            {
                "model": "sale.order",
                "modules": ["sale"],
                "reason": "Sales orders (link-only)",
                "link_only": True,
            },
            {
                "model": "account.move",
                "modules": ["account"],
                "reason": "Invoices (link-only)",
                "link_only": True,
            },
        ],
        "models": [
            {
                "model": "x_store_order",
                "is_workflow": True,
                "fields": [
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_store_order_line",
                    }
                ],
            },
            {"model": "x_store_order_line", "fields": []},
        ],
    }
    notes = wire_reuse_stock_documents(draft)
    assert "sale.order" in draft["reuse"]["models"]
    assert "account.move" in draft["reuse"]["models"]
    assert "sale" in draft["depends"]
    assert "account" in draft["depends"]
    decisions = {
        d["model"]: d for d in draft["reuse"]["plan"]["decisions"] if isinstance(d, dict)
    }
    assert decisions["sale.order"]["confirmed"] is True
    assert decisions["account.move"]["link_only"] is True
    assert any("reuse wired sale.order" in n for n in notes)


def test_apply_promotion_discount_line_computes() -> None:
    from app.ai_apply_readiness import apply_promotion_discount_line_computes
    from app.module_spec_codec import merge_custom_code_blocks

    draft = {
        "models": [
            {
                "model": "x_store_order",
                "is_workflow": True,
                "fields": [
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_store_order_line",
                    },
                    {
                        "name": "x_promotion_id",
                        "ttype": "many2one",
                        "relation": "x_promotion",
                    },
                ],
            },
            {
                "model": "x_store_order_line",
                "fields": [
                    {
                        "name": "x_order_id",
                        "ttype": "many2one",
                        "relation": "x_store_order",
                    },
                    {"name": "x_qty", "ttype": "float"},
                    {"name": "x_price_unit", "ttype": "monetary"},
                    {"name": "x_subtotal", "ttype": "monetary"},
                    {"name": "x_currency_id", "ttype": "many2one", "relation": "res.currency"},
                ],
            },
            {
                "model": "x_promotion",
                "is_workflow": True,
                "fields": [{"name": "x_discount_pct", "ttype": "float"}],
            },
        ]
    }
    notes = apply_promotion_discount_line_computes(draft)
    assert notes
    block = next(
        b
        for b in merge_custom_code_blocks(draft)
        if b.get("model") == "x_store_order_line"
    )
    content = str(block["content"])
    assert "x_promotion_id.x_discount_pct" in content
    assert "1.0 - (pct or 0.0) / 100.0" in content


def test_prepare_spec_for_live_apply_normalizes_record_rules() -> None:
    from app.ai_apply_readiness import prepare_spec_for_live_apply

    spec = {
        "models": [
            {
                "model": "x_branch",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                ],
            }
        ],
        "record_rules": [
            {
                "name": "Multi-company (x_branch)",
                "model": "x_branch",
                "domain_force": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
            }
        ],
    }
    prepared, notes = prepare_spec_for_live_apply(spec)
    names = {f["name"] for f in prepared["models"][0]["fields"]}
    assert "x_company_id" in names
    assert "company_id" not in names
    assert "x_company_id" in prepared["record_rules"][0]["domain_force"]
    assert any("x_company_id" in n for n in notes)


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


def test_vocab_scrub_no_supplier_stutter() -> None:
    from app.ai_vocab_scrub import scrub_text

    pack = {"deposit": "Supplier hold", "retainer": "Supplier hold"}
    out, changed = scrub_text("Customer deposit and holds", pack)
    assert changed
    assert "supplier supplier" not in out.lower()
    assert "hold" in out.lower()


def test_consolidate_inventory_drops_orphan_access_rules() -> None:
    from app.ai_apply_readiness import consolidate_redundant_inventory_models

    draft = {
        "depends": ["stock"],
        "models": [
            {"model": "x_inventory_count", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_inventory", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
        "access_rules": [
            {"id": "access_x_store_inventory_user", "model": "model_x_store_inventory"},
            {"id": "access_x_inventory_count_user", "model": "model_x_inventory_count"},
        ],
    }
    notes = consolidate_redundant_inventory_models(draft)
    models = {m["model"] for m in draft["models"]}
    access_models = {r["model"].replace("model_", "", 1) for r in draft["access_rules"]}
    assert "x_store_inventory" not in models
    assert "x_store_inventory" not in access_models
    assert "x_inventory_count" in access_models
    assert any("removed x_store_inventory" in n for n in notes)


def test_worldwide_noun_covered_by_branch_country() -> None:
    from app.ai_domain_nouns import domain_noun_coverage

    draft = {
        "_user_prompt": "A large mega super market with multiple branches worldwide",
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_country_id", "ttype": "many2one", "relation": "res.country"},
                ],
            }
        ],
    }
    _items, uncovered, _w = domain_noun_coverage(draft, draft["_user_prompt"])
    assert "worldwide" not in uncovered


def test_remove_line_model_root_menus_under_app_root() -> None:
    from app.ai_apply_readiness import remove_line_model_root_menus

    draft = {
        "models": [{"model": "x_branch_transfer_line", "fields": []}],
        "actions": [{"technical_name": "action_x_branch_transfer_line", "model": "x_branch_transfer_line"}],
        "menus": [
            {"name": "Transfer line", "action_xml_id": "action_x_branch_transfer_line", "parent_xml_id": "menu_root_super_market"},
            {"name": "Operations", "parent_xml_id": "menu_root_super_market"},
        ],
    }
    notes = remove_line_model_root_menus(draft)
    assert len(draft["menus"]) == 1
    assert draft["menus"][0]["name"] == "Operations"
    assert any("line model" in n for n in notes)


def test_prune_timezone_from_line_models() -> None:
    from app.ai_apply_readiness import prune_transfer_timezone_field

    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [{"name": "x_timezone", "ttype": "char"}, {"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_branch_transfer_line",
                "fields": [{"name": "x_timezone", "ttype": "char"}, {"name": "x_name", "ttype": "char"}],
            },
        ],
        "views": [
            {
                "model": "x_branch_transfer_line",
                "type": "form",
                "arch": '<form><field name="x_timezone"/><field name="x_name"/></form>',
            }
        ],
    }
    notes = prune_transfer_timezone_field(draft)
    line = next(m for m in draft["models"] if m["model"] == "x_branch_transfer_line")
    branch = next(m for m in draft["models"] if m["model"] == "x_branch")
    assert any(f["name"] == "x_timezone" for f in branch["fields"])
    assert not any(f["name"] == "x_timezone" for f in line["fields"])
    assert 'name="x_timezone"' not in draft["views"][0]["arch"]
    assert notes


def test_priority_hygiene_supermarket_corrupted_labels() -> None:
    """Regression: all four priority fixes on a corrupted supermarket-shaped draft."""
    from app.ai_draft_scorecard import attach_scorecard, draft_scorecard
    from app.ai_production_shape import run_production_shape_pass

    prompt = "A large, mega, super market with multiple branches worldwide"
    draft = {
        "_user_prompt": prompt,
        "domain_pack": "retail_supermarket",
        "depends": ["stock"],
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Branch"},
                    {"name": "x_country_id", "ttype": "many2one", "relation": "res.country"},
                ],
            },
            {
                "model": "x_store_order",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_store_deposit",
                "description": "Customer Supplier Supplier Supplier deposits and holds",
                "fields": [
                    {
                        "name": "x_name",
                        "ttype": "char",
                        "string": "Supplier Supplier deposit",
                    }
                ],
            },
            {
                "model": "x_store_expense",
                "description": "Store expenses and expenses",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_compliance_check",
                "description": "Food safety check and Supplier approval",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_inventory_count",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_store_inventory",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_branch_transfer_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_timezone", "ttype": "char", "string": "Timezone"},
                ],
            },
        ],
        "access_rules": [
            {"id": "access_x_store_inventory_user", "model": "model_x_store_inventory"},
        ],
        "actions": [
            {"technical_name": "action_x_store_deposit", "model": "x_store_deposit", "name": "Bad deposit"},
            {
                "technical_name": "action_x_branch_transfer_line",
                "model": "x_branch_transfer_line",
                "name": "Transfer line",
            },
        ],
        "menus": [
            {
                "name": "Bad deposit menu",
                "action_xml_id": "action_x_store_deposit",
                "parent_xml_id": "menu_sub_other",
            },
            {
                "name": "Transfer line",
                "action_xml_id": "action_x_branch_transfer_line",
                "parent_xml_id": "menu_root_super_market",
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_branch",
                "label": "Customer Supplier Supplier deposits and holds",
                "related_model": "x_store_deposit",
                "relation_field": "x_branch_id",
            }
        ],
        "views": [
            {
                "name": "x_branch.search",
                "model": "x_branch",
                "type": "search",
                "arch": '<search string="Branch"><field name="x_name"/></search>',
            },
            {
                "name": "x_store_deposit.form",
                "model": "x_store_deposit",
                "type": "form",
                "arch": '<form string="Bad deposit"><field name="x_name"/></form>',
            },
        ],
    }
    run_production_shape_pass(draft)
    by_id = {m["model"]: m for m in draft["models"]}
    assert "x_store_inventory" not in by_id
    access_models = {r["model"].replace("model_", "", 1) for r in draft["access_rules"]}
    assert "x_store_inventory" not in access_models
    assert "supplier supplier" not in by_id["x_store_deposit"]["description"].lower()
    assert by_id["x_store_deposit"]["description"] == "Customer deposits and holds"
    assert by_id["x_store_expense"]["description"] == "Store expense"
    assert by_id["x_compliance_check"]["description"] == "Food safety and supplier approval"
    branch_fields = {f["name"] for f in by_id["x_branch"]["fields"]}
    assert "x_region" in branch_fields
    line_fields = {f["name"] for f in by_id["x_branch_transfer_line"]["fields"]}
    assert "x_timezone" not in line_fields
    menu_action_models = []
    for menu in draft["menus"]:
        ref = menu.get("action_xml_id")
        for action in draft["actions"]:
            if action.get("technical_name") == ref:
                menu_action_models.append(action.get("model"))
    assert "x_branch_transfer_line" not in menu_action_models
    search_arch = next(v["arch"] for v in draft["views"] if v.get("name") == "x_branch.search")
    assert "group_x_country_id" in search_arch
    assert "group_x_region" in search_arch
    deposit_form = next(v["arch"] for v in draft["views"] if v.get("name") == "x_store_deposit.form")
    assert "Customer deposits and holds" in deposit_form
    attach_scorecard(draft, user_prompt=prompt)
    scored = draft_scorecard(draft, user_prompt=prompt)
    uncovered = [f["element"] for f in scored.get("findings", []) if "noun:" in str(f.get("element"))]
    assert "noun:worldwide" not in uncovered


def test_align_workflow_selection_domains_clears_conflicting_domain() -> None:
    from app.ai_apply_readiness import align_workflow_selection_domains

    draft = {
        "models": [
            {
                "model": "x_store_order",
                "is_workflow": True,
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('confirmed','Confirmed'),"
                            "('picking','Picking'),('delivered','Delivered'),"
                            "('cancelled','Cancelled')]"
                        ),
                        "domain": ["draft", "sent", "paid", "cancelled"],
                    }
                ],
                "state_field": {
                    "states": ["draft", "sent", "paid", "cancelled"],
                    "transitions": [["draft", "sent"]],
                },
            }
        ],
        "views": [
            {
                "model": "x_store_order",
                "type": "search",
                "arch": (
                    '<search string="Order">'
                    '<filter string="Sent" name="status_sent" '
                    'domain="[(\'x_status\',\'=\',\'sent\')]"/>'
                    "</search>"
                ),
            }
        ],
    }
    notes = align_workflow_selection_domains(draft)
    assert notes
    status = draft["models"][0]["fields"][0]
    assert "domain" not in status
    assert draft["models"][0]["state_field"]["states"][1] == "confirmed"
    assert "status_sent" not in draft["views"][0]["arch"]


def test_consolidate_branch_master_data_drops_duplicates() -> None:
    from app.ai_apply_readiness import consolidate_branch_master_data

    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_country", "ttype": "char", "string": "Country"},
                    {"name": "x_country_id", "ttype": "many2one", "relation": "res.country"},
                    {"name": "x_address_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "x_street", "ttype": "char"},
                    {"name": "x_logo", "ttype": "binary"},
                    {"name": "x_logo_id", "ttype": "many2many", "relation": "ir.attachment"},
                ],
            }
        ],
        "views": [
            {
                "model": "x_branch",
                "type": "form",
                "arch": (
                    '<form><field name="x_country"/>'
                    '<field name="x_street"/><field name="x_logo_id"/></form>'
                ),
            }
        ],
    }
    notes = consolidate_branch_master_data(draft)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_country" not in names
    assert "x_street" not in names
    assert "x_logo_id" not in names
    assert "x_country_id" in names
    assert "x_address_id" in names


def test_wire_inventory_adjustment_reason_and_search() -> None:
    from app.ai_apply_readiness import ensure_inventory_reason_search, wire_inventory_adjustment_reason

    draft = {
        "models": [
            {
                "model": "x_inventory_reason",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "selection": "[('adjustment','Adjustment'),('damage','Damage')]",
                    },
                ],
            },
            {
                "model": "x_inventory_adjustment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_reason", "ttype": "text", "string": "Reason"},
                ],
            },
        ],
        "views": [
            {
                "model": "x_inventory_reason",
                "type": "search",
                "arch": (
                    '<search string="Reason">'
                    '<filter string="Branch" name="group_x_branch_id" '
                    'context="{\'group_by\': \'x_branch_id\'}"/>'
                    "</search>"
                ),
            },
            {
                "model": "x_inventory_adjustment",
                "type": "form",
                "arch": '<form><field name="x_reason"/></form>',
            },
        ],
    }
    wire_inventory_adjustment_reason(draft)
    ensure_inventory_reason_search(draft)
    adj_names = {f["name"] for f in draft["models"][1]["fields"]}
    assert "x_reason_id" in adj_names
    assert "x_reason" not in adj_names
    assert 'name="x_reason_id"' in draft["views"][1]["arch"]
    search = draft["views"][0]["arch"]
    assert "filter_active" in search
    assert "status_adjustment" in search
    assert "group_x_type" in search


def test_remove_line_model_menus_drops_operations_submenu() -> None:
    from app.ai_apply_readiness import remove_line_model_root_menus

    draft = {
        "models": [{"model": "x_store_order_line", "fields": [{"name": "x_name", "ttype": "char"}]}],
        "actions": [
            {"technical_name": "action_x_store_order_line", "model": "x_store_order_line"},
        ],
        "menus": [
            {
                "name": "Order line",
                "action_xml_id": "action_x_store_order_line",
                "parent_xml_id": "menu_sub_operations",
            }
        ],
    }
    notes = remove_line_model_root_menus(draft)
    assert notes
    assert draft["menus"] == []


def test_fix_assignee_staff_relations_includes_schedule() -> None:
    from app.ai_apply_readiness import fix_assignee_staff_relations

    draft = {
        "depends": ["base", "hr"],
        "models": [
            {
                "model": "x_staff_schedule",
                "fields": [
                    {
                        "name": "x_staff_ids",
                        "ttype": "many2many",
                        "relation": "res.users",
                    }
                ],
            }
        ],
    }
    fix_assignee_staff_relations(draft)
    field = draft["models"][0]["fields"][0]
    assert field["relation"] == "hr.employee"
    assert field["ttype"] == "many2many"


def test_fixture_semantic_corrupted_passes_production_shape() -> None:
    """Regression fixture: Top-3 semantic bugs → clean after production-shape."""
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_production_shape import run_production_shape_pass

    draft = json.loads(FIXTURE_SEMANTIC.read_text())
    draft["_user_prompt"] = (
        "A large, mega, super market with multiple branches worldwide"
    )
    run_production_shape_pass(draft)
    by_id = {m["model"]: m for m in draft["models"]}
    branch_names = {f["name"] for f in by_id["x_branch"]["fields"]}
    assert "x_country" not in branch_names
    assert "x_street" not in branch_names
    assert "x_logo_id" not in branch_names
    order_status = next(f for f in by_id["x_store_order"]["fields"] if f["name"] == "x_status")
    assert "domain" not in order_status
    assert "confirmed" in order_status["selection"]
    assert "sent" not in order_status["selection"]
    adj_names = {f["name"] for f in by_id["x_inventory_adjustment"]["fields"]}
    assert "x_reason_id" in adj_names
    assert "x_reason" not in adj_names
    assert by_id["x_staff_schedule"]["fields"][0]["relation"] == "hr.employee"
    assert draft["menus"] == []
    search = next(v for v in draft["views"] if v.get("model") == "x_inventory_reason")
    assert "filter_active" in search["arch"]
    assert "status_adjustment" in search["arch"]
    scored = draft_scorecard(draft, user_prompt=draft["_user_prompt"])
    semantic_findings = [
        f for f in scored.get("findings", []) if f.get("dimension") == "semantics"
    ]
    assert not any("domain allowlist" in str(f.get("detail")) for f in semantic_findings)
    assert float(scored.get("dimensions", {}).get("semantics") or 0) >= 9.0
    assert str(draft.get("_completeness", [{}])[0].get("detail", "")).startswith(
        f"{len(draft['models'])} model"
    )


def test_ensure_statusbar_transition_paths_adds_approved_to_closed() -> None:
    from app.ai_apply_readiness import ensure_statusbar_transition_paths

    draft = {
        "models": [
            {
                "model": "x_inventory_adjustment",
                "is_workflow": True,
                "state_field": {
                    "states": ["draft", "on_hold", "approved", "closed"],
                    "statusbar_visible": ["draft", "on_hold", "approved", "closed"],
                    "transitions": [["draft", "on_hold"], ["on_hold", "approved"]],
                },
            }
        ],
        "views": [
            {
                "model": "x_inventory_adjustment",
                "type": "form",
                "arch": (
                    '<form><header><field name="x_status" widget="statusbar"/>'
                    "</header><sheet/></form>"
                ),
            }
        ],
    }
    notes = ensure_statusbar_transition_paths(draft)
    assert notes
    sf = draft["models"][0]["state_field"]
    assert ["approved", "closed"] in sf["transitions"]
    form = draft["views"][0]["arch"]
    assert 'data-transition-to="closed"' in form


def test_sync_sequence_field_help_and_reason_prefix() -> None:
    from app.ai_apply_readiness import ensure_unique_sequence_prefixes, sync_sequence_field_help

    draft = {
        "models": [
            {
                "model": "x_inventory_reason",
                "fields": [
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "help": "Auto-numbered via ir.sequence (INVENTOR/00001)",
                    }
                ],
            }
        ],
        "sequences": [
            {"model": "x_inventory_reason", "field": "x_code", "prefix": "INVENTORY/"}
        ],
    }
    ensure_unique_sequence_prefixes(draft)
    sync_sequence_field_help(draft)
    assert draft["sequences"][0]["prefix"] == "REASON/"
    code = draft["models"][0]["fields"][0]
    assert code["help"] == "Auto-numbered via ir.sequence (REASON/00001)"


def test_consolidate_adjustment_header_fields_drops_shadow_qty() -> None:
    from app.ai_apply_readiness import consolidate_adjustment_header_fields

    draft = {
        "models": [
            {
                "model": "x_inventory_adjustment",
                "fields": [
                    {"name": "x_qty_adjusted", "ttype": "float"},
                    {"name": "x_quantity", "ttype": "float"},
                    {"name": "x_product_id", "ttype": "many2one", "relation": "product.product"},
                    {"name": "x_inventory_line_ids", "ttype": "one2many", "relation": "x_inventory_line"},
                ],
            }
        ],
        "views": [
            {
                "model": "x_inventory_adjustment",
                "type": "form",
                "arch": '<form><field name="x_quantity"/><field name="x_product_id"/></form>',
            }
        ],
    }
    notes = consolidate_adjustment_header_fields(draft)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_quantity" not in names
    assert "x_product_id" not in names
    assert 'name="x_quantity"' not in draft["views"][0]["arch"]


def test_ensure_branch_manager_record_rules_manager_group_only() -> None:
    from app.ai_apply_readiness import ensure_branch_manager_record_rules

    draft = {
        "domain_pack": "retail_supermarket",
        "groups": [
            {"id": "group_super_market_user", "name": "User"},
            {"id": "group_super_market_manager", "name": "Manager"},
        ],
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_manager_id", "ttype": "many2one", "relation": "res.users"},
                ],
            },
            {
                "model": "x_store_order",
                "fields": [
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                ],
            },
        ],
        "record_rules": [],
    }
    notes = ensure_branch_manager_record_rules(draft)
    assert notes
    rules = draft["record_rules"]
    assert len(rules) == 2
    assert all("group_super_market_manager" in (r.get("group_xml_ids") or []) for r in rules)
    assert all("user.id" in str(r.get("domain_force") or "") for r in rules)
