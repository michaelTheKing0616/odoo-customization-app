"""Unit tests for bulk CSV import helpers."""

from __future__ import annotations

from app.data_import import (
    build_preview,
    parse_tabular,
    results_to_error_csv,
    suggest_mapping,
    template_csv,
)
from app.data_import import RowResult


def test_parse_csv_and_suggest_partner_mapping() -> None:
    raw = template_csv("res.partner").encode("utf-8")
    headers, rows = parse_tabular(raw, "partners.csv")
    assert "name" in headers
    assert len(rows) >= 1
    mapping = suggest_mapping("res.partner", headers)
    assert mapping["name"] == "name"
    assert mapping.get("email") == "email"
    preview = build_preview(headers=headers, rows=rows, model=None)
    assert preview.suggested_model == "res.partner"
    assert preview.row_count == len(rows)


def test_parse_product_template() -> None:
    raw = template_csv("product.template").encode()
    headers, rows = parse_tabular(raw, "products.csv")
    mapping = suggest_mapping("product.template", headers)
    assert mapping["list_price"] == "list_price"
    assert rows[0]["name"]


def test_error_csv() -> None:
    csv = results_to_error_csv(
        [
            RowResult(row_index=1, ok=True, action="create"),
            RowResult(row_index=2, ok=False, error="boom"),
        ]
    )
    assert "boom" in csv
    assert "2" in csv
