"""ING-2 — document classifier."""

from __future__ import annotations

from app.ingest.classify import classify_structured, classify_upload


def test_classify_customer_headers() -> None:
    result = classify_structured(
        filename="customers.csv",
        headers=["name", "email", "phone", "customer_id"],
    )
    assert result.doc_type == "customer_list"
    assert result.confidence >= 0.55
    assert result.needs_user_confirm is False


def test_classify_product_headers() -> None:
    result = classify_structured(
        filename="catalog.xlsx",
        headers=["name", "default_code", "list_price", "barcode"],
    )
    assert result.doc_type == "product_catalog"
    assert result.confidence >= 0.55


def test_classify_coa_like_headers() -> None:
    result = classify_structured(
        filename="gl.csv",
        headers=["account", "code", "debit", "credit", "asset"],
    )
    assert result.doc_type == "coa"


def test_classify_garbage_needs_confirm() -> None:
    result = classify_structured(filename="notes.txt", headers=["foo", "bar"])
    assert result.doc_type == "other"
    assert result.needs_user_confirm is True


def test_forced_doc_type() -> None:
    result = classify_upload(
        filename="x.csv",
        headers=[],
        force_doc_type="vendor_list",
    )
    assert result.doc_type == "vendor_list"
    assert result.confidence == 1.0
    assert result.needs_user_confirm is False
