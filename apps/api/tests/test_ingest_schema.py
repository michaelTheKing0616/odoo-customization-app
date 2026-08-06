"""ING-1 — ingest schema round-trip and allowlist."""

from __future__ import annotations

import json

import pytest

from app.ingest.schema import (
    DOC_TYPE_ALLOWLIST,
    IngestBatch,
    IngestFile,
    IngestTable,
    validate_doc_type,
)


def test_batch_round_trip_json() -> None:
    batch = IngestBatch(
        connection_id="conn-1",
        files=[IngestFile(id="f1", filename="partners.csv", doc_type="customer_list", confidence=0.9)],
        tables=[
            IngestTable(
                id="t1",
                model="res.partner",
                doc_type="customer_list",
                natural_key_fields=["email"],
            )
        ],
    )
    raw = batch.model_dump(mode="json")
    restored = IngestBatch.model_validate(raw)
    assert restored.connection_id == "conn-1"
    assert restored.files[0].doc_type == "customer_list"
    assert json.dumps(raw)


def test_unknown_doc_type_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown doc_type"):
        validate_doc_type("invoice_pdf")
    assert "customer_list" in DOC_TYPE_ALLOWLIST
