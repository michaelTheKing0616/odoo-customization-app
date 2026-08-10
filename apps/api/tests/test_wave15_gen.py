"""Wave 15 GEN cards — deterministic generation fidelity fixes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.ai_critique import apply_critique_repairs
from app.ai_depth import (
    apply_deterministic_depth,
    classify_ambition,
    classify_ambition_with_notes,
    depth_gaps,
    seed_operational_loop_models,
)
from app.ai_domain_nouns import (
    domain_noun_coverage,
    expand_uncovered_noun_models,
    extract_prompt_nouns,
)
from app.ai_domain_packs import match_domain_pack
from app.ai_model_quality import (
    enforce_on_write_filter_domains,
    repair_draft_integrity,
    strip_internal_scaffold,
)
from app.ai_ollama import derive_draft_naming_from_prompt
from app.ai_reuse_planner import apply_reuse_plan, plan_reuse
from app.ai_selection import dedupe_selection_pairs, normalize_selection_field
from app.ai_stock_reuse import infer_stock_reuse
from app.ai_workflow import ensure_workflow_transitions_on_draft

FIXTURE = Path(__file__).parent / "fixtures" / "draft_supermarket_2026-08-05.json"
SUPERMARKET_PROMPT = "A large mega Super Market with multiple branches"
LAW_PROMPT = "Comprehensive law firm matter management with hearings and billing"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def test_selection_dedupe_duplicate_cancelled() -> None:
    field = {
        "ttype": "selection",
        "name": "x_status",
        "selection": (
            "[('draft','Draft'),('cancelled','Cancelled'),('cancelled','Dup')]"
        ),
    }
    notes = normalize_selection_field(field, context="x_order.x_status")
    assert notes
    assert field["selection"].count("'cancelled'") == 1


def test_selection_dedupe_mixed_syntax() -> None:
    pairs = [("draft", "Draft"), ("open", "Open"), ("draft", "Draft again")]
    deduped, changed = dedupe_selection_pairs(pairs)
    assert changed
    assert deduped == [("draft", "Draft"), ("open", "Open")]


def test_terminal_merge_preserves_flow_states() -> None:
    draft = _load_fixture()
    repair_draft_integrity(draft, ambition="standard")
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    sf = order["state_field"]
    states = sf.get("states") or []
    assert "draft" in states
    assert "confirmed" in states
    assert "delivered" in states
    assert sf.get("transitions")


def test_supermarket_fixture_roundtrip_integrity() -> None:
    draft = _load_fixture()
    notes = repair_draft_integrity(draft, ambition="standard")
    assert notes
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    status = next(f for f in order["fields"] if f["name"] == "x_status")
    assert status["selection"].count("'cancelled'") == 1
    assert order["state_field"]["transitions"]


def test_domain_noun_flags_branch_for_supermarket() -> None:
    draft = _load_fixture()
    items, uncovered, warnings = domain_noun_coverage(draft, SUPERMARKET_PROMPT)
    assert "branch" in uncovered
    assert any(i["id"] == "noun_uncovered:branch" and not i["ok"] for i in items)
    assert warnings


def test_domain_noun_no_false_positive_law_firm() -> None:
    draft = {
        "models": [
            {"model": "x_matter", "description": "Legal matter"},
            {"model": "x_hearing", "description": "Hearing"},
        ]
    }
    _items, uncovered, _w = domain_noun_coverage(draft, LAW_PROMPT)
    assert "branch" not in uncovered


def test_seed_labels_neutral_no_law_firm_lexicon() -> None:
    draft = {
        "models": [
            {
                "model": "x_sales_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "_user_prompt": SUPERMARKET_PROMPT,
    }
    notes = seed_operational_loop_models(draft, "comprehensive", user_prompt=SUPERMARKET_PROMPT)
    assert notes
    seeded = [m for m in draft["models"] if m.get("source") == "depth_seed"]
    assert seeded
    for m in seeded:
        desc = str(m.get("description") or "").lower()
        assert "retainer" not in desc
        assert "appointment" not in desc
        assert "disbursement" not in desc


def test_seeded_only_depth_sets_flag() -> None:
    draft = {
        "models": [
            {
                "model": "x_sales_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "_ambition": "comprehensive",
    }
    out, notes = apply_deterministic_depth(
        draft, "comprehensive", user_prompt=SUPERMARKET_PROMPT
    )
    depth = out.get("_depth") or {}
    assert depth.get("seeded") is True
    assert "depth_models" in (depth.get("gaps") or [])
    assert any("generic seeds" in n for n in notes)


def test_strip_internal_json_scaffold() -> None:
    draft = {"technical_name": "demo", "json": {"models": [{"model": "x_ex_job"}]}}
    notes = strip_internal_scaffold(draft)
    assert "json" not in draft
    assert notes


def test_derive_naming_from_supermarket_prompt() -> None:
    draft: dict[str, Any] = {"technical_name": "custom_app"}
    warnings = derive_draft_naming_from_prompt(draft, SUPERMARKET_PROMPT)
    assert draft["technical_name"] != "custom_app"
    assert "super" in draft["technical_name"] or "market" in draft["technical_name"]
    assert draft.get("display_name")
    assert warnings


def test_on_write_automation_requires_filter_domain() -> None:
    draft = _load_fixture()
    notes = enforce_on_write_filter_domains(draft)
    assert notes
    assert not any(a.get("name") == "Notify on order confirmation" for a in draft["automations"])


def test_critique_ready_consistency_when_empty() -> None:
    draft = {"models": [{"model": "x_thing", "fields": []}]}
    out, _notes = apply_critique_repairs(
        draft, {"ready": False, "checklist": [], "notes": []}
    )
    assert out["_critique"]["ready"] is True


def test_critique_not_ready_has_notes() -> None:
    draft = {"models": [{"model": "x_thing", "fields": []}]}
    out, _notes = apply_critique_repairs(
        draft,
        {"ready": False, "checklist": [{"id": "x", "ok": False}], "notes": []},
    )
    assert out["_critique"]["ready"] is False
    assert out["_critique"]["notes"]


def test_workflow_empty_transitions_gets_chain() -> None:
    draft = copy.deepcopy(_load_fixture())
    for m in draft["models"]:
        if m.get("model") == "x_sales_order":
            m["state_field"] = {"field": "x_status", "states": [], "transitions": []}
    ensure_workflow_transitions_on_draft(draft)
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    assert order["state_field"]["transitions"]


def test_ambition_scales_mega_supermarket_to_comprehensive() -> None:
    amb, notes = classify_ambition_with_notes(SUPERMARKET_PROMPT)
    assert amb == "comprehensive"
    assert notes
    assert classify_ambition(SUPERMARKET_PROMPT) == "comprehensive"


def test_retail_supermarket_pack_matches_prompt() -> None:
    matched = match_domain_pack(SUPERMARKET_PROMPT)
    assert matched is not None
    pack_id, pack = matched
    assert pack_id == "retail_supermarket"
    models = {m.get("model"): m for m in pack.get("models") or [] if isinstance(m, dict)}
    assert "x_branch" in models
    assert pack.get("reuse_stock")
    branch_names = {f.get("name") for f in models["x_branch"].get("fields") or []}
    assert "x_address_id" in branch_names
    assert "x_country_id" in branch_names
    assert "x_address" not in branch_names
    assert "x_inventory_reason" in models
    assert "x_inventory_adjustment" in models
    adj_names = {f.get("name") for f in models["x_inventory_adjustment"].get("fields") or []}
    assert "x_reason_id" in adj_names
    assert "x_reason" not in adj_names
    order = models["x_store_order"]
    assert isinstance(order.get("state_field"), dict)
    assert "confirmed" in (order.get("state_field") or {}).get("states", [])


def test_depth_model_floor_excludes_depth_seed_only() -> None:
    draft = {
        "models": [
            {
                "model": f"x_event_{i}",
                "source": "depth_seed",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_date", "ttype": "date"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "x_notes", "ttype": "text"},
                ],
            }
            for i in range(6)
        ],
        "_ambition": "standard",
    }
    assert "depth_models" in depth_gaps(draft, "standard")


def test_noun_expand_adds_branch_model() -> None:
    draft = _load_fixture()
    notes = expand_uncovered_noun_models(draft, SUPERMARKET_PROMPT)
    assert notes
    assert any(m.get("model") == "x_branch" for m in draft["models"])


def test_infer_product_reuse_when_installed() -> None:
    decisions, _notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
    )
    models = {d["model"] for d in decisions}
    assert "product.template" in models or "product.product" in models


def test_infer_product_absent_notes_custom() -> None:
    _decisions, notes, _cat = infer_stock_reuse(
        "Supermarket product catalog",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
    )
    assert any("product" in n.lower() for n in notes)


def test_infer_product_installable_not_installed_offers_install() -> None:
    decisions, notes, _cat = infer_stock_reuse(
        "Supermarket product catalog",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
    )
    installable = [d for d in decisions if d.get("source") == "installable"]
    assert installable
    assert any(d.get("model") in {"product.template", "product.product"} for d in installable)
    assert any("install and reuse" in n for n in notes)


def test_pack_product_template_wins_over_noun_inference() -> None:
    pack_stock = [
        {
            "model": "product.template",
            "modules": ["product"],
            "reason": "Product catalog (domain pack)",
            "forbid_parallel": ["x_product", "x_product_template"],
        }
    ]
    decisions, _notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        pack_reuse_stock=pack_stock,
    )
    pt = next((d for d in decisions if d.get("model") == "product.template"), None)
    assert pt is not None
    assert pt.get("source") == "pack_reuse_stock"
    assert pt.get("reason") == "Product catalog (domain pack)"


def test_rejected_models_skip_inference() -> None:
    decisions, notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        rejected_models=["product.template"],
    )
    assert not any(d.get("model") == "product.template" for d in decisions)
    assert any("skipped product.template" in n for n in notes)


def test_plan_reuse_installable_decision() -> None:
    plan = plan_reuse(
        "Track employee expenses and reimbursements",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=[],
    )
    installable = [d for d in plan.decisions if d.source == "installable"]
    assert installable
    expense = next(d for d in installable if d.model == "hr.expense")
    assert expense.required_module == "hr_expense"

def test_pack_reuse_stock_surfaces_in_plan() -> None:
    pack_stock = [
        {
            "model": "purchase.order",
            "modules": ["purchase"],
            "reason": "Supplier purchase orders (link-only)",
            "link_only": True,
        }
    ]
    plan = plan_reuse(
        SUPERMARKET_PROMPT,
        available_models=["purchase.order", "product.template", "res.partner"],
        installed_modules=["base", "product", "purchase", "contacts"],
        operator_reuse=[],
        pack_reuse_stock=pack_stock,
    )
    pack_rows = [d for d in plan.decisions if d.source == "pack_reuse_stock"]
    assert pack_rows
    assert any(d.model == "purchase.order" for d in pack_rows)
    assert not any(d.confirmed for d in pack_rows)

def test_confirmed_product_reuse_forbids_x_product() -> None:
    plan = plan_reuse(
        "Mega supermarket with product catalog and inventory",
        available_models=["product.product", "product.template", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        operator_reuse=["product.product"],
    )
    assert "x_product" in plan.forbid_new_models
    draft = {
        "models": [
            {"model": "x_product", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_order", "fields": [{"name": "x_name", "ttype": "char"}]},
        ]
    }
    notes = apply_reuse_plan(draft, plan)
    assert notes
    assert not any(m.get("model") == "x_product" for m in draft["models"])


def test_invoice_inference_link_only() -> None:
    decisions, _notes, _cat = infer_stock_reuse(
        "Track customer invoices and billing",
        available_models=["account.move", "res.partner"],
        installed_modules=["base", "account", "contacts"],
    )
    inv = next((d for d in decisions if d["model"] == "account.move"), None)
    assert inv is not None
    assert inv.get("link_only") is True


def test_unconfirmed_inferred_not_in_forbid_until_confirmed() -> None:
    plan = plan_reuse(
        "Mega grocery branches nationwide",
        available_models=["product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        operator_reuse=[],
    )
    inferred = [d for d in plan.decisions if d.source == "inferred"]
    assert inferred
    assert not any(d.confirmed for d in inferred)
    assert "x_product" not in plan.forbid_new_models


def test_reapply_reuse_endpoint_collapses_parallel_without_llm() -> None:
    import os

    from fastapi.testclient import TestClient

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
    )
    os.environ.setdefault("FERNET_KEY", "dev-only-test")
    os.environ.setdefault("AUTH_MODE", "off")

    from app.main import app

    draft = {
        "technical_name": "demo",
        "models": [
            {"model": "x_product", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_order", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
    }
    with TestClient(app) as client:
        res = client.post(
            "/api/ai/reapply-reuse",
            json={
                "prompt": "Mega supermarket with product catalog",
                "draft": draft,
                "reuse_models": ["product.product"],
                "rejected_reuse_models": [],
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    models = {m["model"] for m in body["draft"]["models"]}
    assert "x_product" not in models
    assert body["draft"]["reuse"]["plan"]["decisions"]
    assert isinstance(body["draft"].get("_scorecard"), dict)
    assert float(body["draft"]["_scorecard"].get("score_0_10") or 0) >= 0
    assert any(
        d.get("model") == "product.product" and d.get("confirmed")
        for d in body["draft"]["reuse"]["plan"]["decisions"]
    )
