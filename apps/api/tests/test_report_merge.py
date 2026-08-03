"""Unit tests for merged PDF reports (BLK-8)."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter

from app.report_merge import merge_pdf_bytes, pdf_page_count


def _blank_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_merge_pdf_bytes_preserves_order_and_page_count() -> None:
    a = _blank_pdf(1)
    b = _blank_pdf(2)
    merged, total = merge_pdf_bytes([a, b])
    assert total == 3
    assert pdf_page_count(merged) == 3
    assert merged.startswith(b"%PDF")


def test_merge_pdf_bytes_empty_raises() -> None:
    try:
        merge_pdf_bytes([])
    except Exception as exc:
        assert "No PDF chunks" in str(exc)
    else:
        raise AssertionError("expected error")
