"""Stock model catalog — ranking, filtering, and catalog inference."""

from __future__ import annotations

from app.ai_stock_catalog import (
    filter_catalog,
    filter_stock_entries,
    format_stock_models_for_llm,
    infer_catalog_reuse,
    is_custom_model,
    is_stock_model,
    rank_stock_models_for_prompt,
    stock_entry,
)


def test_is_stock_model_excludes_custom() -> None:
    assert is_stock_model("sale.order")
    assert not is_stock_model("x_matter")
    assert is_custom_model("x_matter")


def test_filter_stock_entries() -> None:
    rows = [
        stock_entry("sale.order", "Sales Order"),
        stock_entry("x_case", "Case"),
    ]
    stock = filter_stock_entries(rows)
    assert len(stock) == 1
    assert stock[0]["model"] == "sale.order"


def test_filter_catalog_search() -> None:
    rows = [
        stock_entry("crm.lead", "Lead"),
        stock_entry("sale.order", "Sales Order"),
    ]
    hits = filter_catalog(rows, q="lead")
    assert len(hits) == 1
    assert hits[0]["model"] == "crm.lead"


def test_rank_prompt_prefers_relevant_apps() -> None:
    rows = [
        stock_entry("sale.order", "Sales Order"),
        stock_entry("crm.lead", "Lead"),
        stock_entry("res.partner", "Contact"),
    ]
    ranked = rank_stock_models_for_prompt(
        rows, "CRM pipeline with leads and opportunities"
    )
    assert "crm.lead" in ranked[:2]


def test_format_llm_block_includes_apps() -> None:
    rows = [
        stock_entry("sale.order", "Sales Order"),
        stock_entry("product.product", "Product Variant"),
    ]
    block = format_stock_models_for_llm(rows, "retail checkout")
    assert "[sale]" in block
    assert "sale.order" in block


def test_infer_catalog_reuse_fleet() -> None:
    rows = [
        stock_entry("fleet.vehicle", "Vehicle"),
        stock_entry("res.partner", "Contact"),
    ]
    available = {"fleet.vehicle", "res.partner"}
    hits = infer_catalog_reuse(
        "Manage company fleet vehicles and maintenance",
        rows,
        available_models=available,
    )
    models = [h["model"] for h in hits]
    assert "fleet.vehicle" in models
    assert hits[0]["source"] == "catalog"


def test_infer_catalog_respects_rejected() -> None:
    rows = [stock_entry("crm.lead", "Lead")]
    hits = infer_catalog_reuse(
        "CRM leads pipeline",
        rows,
        available_models={"crm.lead"},
        rejected={"crm.lead"},
    )
    assert hits == []
