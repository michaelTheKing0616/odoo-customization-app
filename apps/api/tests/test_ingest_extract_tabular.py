"""ING-3 — tabular extract via data_import."""

from __future__ import annotations

from app.industry_seeds import partner_seed, product_seed
from app.ingest.extract_tabular import extract_tabular_bytes


def _csv_from_seed(pack_fn, model: str) -> bytes:
    pack = pack_fn()
    entry = next(m for m in pack["models"] if m["model"] == model)
    return entry["csv"].encode("utf-8")


def test_extract_partner_seed_pack() -> None:
    raw = _csv_from_seed(partner_seed, "res.partner")
    table = extract_tabular_bytes(filename="partners.csv", raw=raw, doc_type="customer_list")
    assert table.model == "res.partner"
    assert table.doc_type == "customer_list"
    assert len(table.rows) >= 2
    assert "email" in table.natural_key_fields or "name" in table.natural_key_fields
    assert table.mapping.get("name") == "name"


def test_extract_product_seed_pack() -> None:
    raw = _csv_from_seed(product_seed, "product.template")
    table = extract_tabular_bytes(filename="products.csv", raw=raw, doc_type="product_catalog")
    assert table.model == "product.template"
    assert table.mapping.get("list_price") == "list_price"
    assert table.rows[0].raw.get("default_code")


def test_employee_roster_strips_wage_columns() -> None:
    raw = (
        "name,employee_id,salary,wage,department\n"
        "Jane Doe,E001,50000,48000,Finance\n"
    ).encode()
    table = extract_tabular_bytes(filename="staff.csv", raw=raw, doc_type="employee_roster")
    assert table.model == "hr.employee"
    assert any("stripped payroll" in w for w in table.warnings)
    assert "salary" not in table.rows[0].raw
