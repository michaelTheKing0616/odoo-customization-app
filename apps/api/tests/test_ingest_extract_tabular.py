"""ING-3 — tabular extract via data_import."""

from __future__ import annotations

from app.industry_seeds import partner_seed, product_seed
from app.ingest.extract_tabular import extract_tabular_bytes, extract_tabular_file


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


def test_bom_csv_expands_to_parent_and_lines() -> None:
    raw = (
        "product_code,component_code,quantity,uom\n"
        "ASSY-1,PART-A,2,Units\n"
        "ASSY-1,PART-B,1,Units\n"
    ).encode()
    tables = extract_tabular_file(filename="bom.csv", raw=raw, doc_type="bom")
    models = [t.model for t in tables]
    assert "mrp.bom" in models
    assert "mrp.bom.line" in models
    lines = next(t for t in tables if t.model == "mrp.bom.line")
    assert len(lines.rows) == 2
