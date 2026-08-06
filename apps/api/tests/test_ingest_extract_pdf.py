"""ING-4 — PDF text extract + BoM/CoA/price list schemas."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.ingest.extract_pdf import (
    _tables_from_bom_payload,
    _validate_price_rows,
    extract_pdf_from_text,
    layout_fingerprint,
)
from app.llm_provider import LLMError


def test_layout_fingerprint_stable() -> None:
    a = layout_fingerprint("Account  Code  Name\n1000 Cash")
    b = layout_fingerprint("account code name\n1000 cash")
    assert a == b


def test_price_list_rejects_collapsed_price() -> None:
    with pytest.raises(ValueError, match="qty-break"):
        _validate_price_rows([{"product_code": "SKU1", "price": 10}])


def test_bom_two_pass_nested_subassembly() -> None:
    payload = {
        "boms": [
            {
                "product_code": "ASSY-1",
                "quantity": 1,
                "lines": [
                    {"component_code": "PART-A", "quantity": 2, "is_subassembly": False},
                    {"component_code": "SUB-ASSY", "quantity": 1, "is_subassembly": True},
                ],
            }
        ]
    }
    tables, refs = _tables_from_bom_payload(payload, filename="bom.pdf")
    models = [t.model for t in tables]
    assert "mrp.bom" in models
    assert "mrp.bom.line" in models
    assert any(r.to_value == "SUB-ASSY" for r in refs)
    assert len([t for t in tables if t.model == "mrp.bom"]) >= 2


def test_coa_deterministic_extract() -> None:
    text = "code,name,type\n1000,Cash,asset\n2000,Payables,liability\n"
    with patch("app.ingest.extract_pdf._llm_extract", side_effect=LLMError("off")):
        tables, refs, warnings = extract_pdf_from_text(
            filename="coa.pdf", text=text, doc_type="coa", db=None
        )
    assert not refs
    assert warnings
    assert tables[0].model == "account.account"
    assert len(tables[0].rows) >= 2


def test_employee_wage_stripped_in_pdf_generic() -> None:
    text = "name,salary,department\nJane,50000,Finance\n"
    with patch("app.ingest.extract_pdf._llm_extract", side_effect=LLMError("off")):
        tables, _, _ = extract_pdf_from_text(
            filename="staff.pdf", text=text, doc_type="employee_roster", db=None
        )
    assert "salary" not in (tables[0].rows[0].raw if tables[0].rows else {})
