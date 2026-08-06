"""ING-9 — Expert interview → IngestBatch."""

from __future__ import annotations

from app.ingest.interview import InterviewAnswers, build_batch_from_interview


def test_interview_builds_partner_and_product_tables() -> None:
    batch = build_batch_from_interview(
        connection_id="conn-1",
        answers=InterviewAnswers(
            business_name="Acme Retail",
            product_type="mixed",
            product_lines=["Widget | W-01 | 19.99", "Support Hour | SVC-1 | 45 | service"],
            starter_contacts=["Jane Doe | jane@example.com | +1234"],
            expense_categories=["Rent", "Utilities"],
        ),
    )
    assert batch.source == "interview"
    models = {t.model for t in batch.tables}
    assert "res.partner" in models
    assert "product.template" in models
    assert any("expense categories" in w for w in batch.warnings)
