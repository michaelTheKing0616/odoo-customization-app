"""ING-5 — dedupe scan integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from app.bulk_suite.dedupe import DedupeGroup, DedupeCandidateRecord, DedupeScanResult
from app.ingest.map import map_batch
from app.ingest.schema import IngestBatch, IngestRow, IngestTable


class FakeMapClient:
    def model_exists(self, model: str) -> bool:
        return model in {"res.partner", "product.template"}

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        if model == "ir.model.fields" and method == "search_read":
            return [
                {"name": "name", "ttype": "char", "required": True, "readonly": False},
                {"name": "email", "ttype": "char", "required": False, "readonly": False},
            ]
        return []


def test_live_dedupe_warning_surfaced() -> None:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="t1",
                model="res.partner",
                doc_type="customer_list",
                mapping={"name": "name", "email": "email"},
                natural_key_fields=["email"],
                rows=[IngestRow(raw={"name": "A", "email": "a@x.com"}, values={})],
            )
        ]
    )
    fake_scan = DedupeScanResult(
        model="res.partner",
        mode="exact",
        match_fields=["email"],
        groups=[
            DedupeGroup(
                group_key="email=a@x.com",
                match_fields=["email"],
                records=[
                    DedupeCandidateRecord(id=1, display_name="A1", preview={"email": "a@x.com"}),
                    DedupeCandidateRecord(id=2, display_name="A2", preview={"email": "a@x.com"}),
                ],
            )
        ],
    )
    with patch("app.ingest.map.scan_duplicates", return_value=fake_scan):
        out = map_batch(FakeMapClient(), batch)
    assert any("live duplicate group" in w for t in out.tables for w in t.warnings)


def test_batch_internal_duplicate_flagged() -> None:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="t1",
                model="product.template",
                doc_type="product_catalog",
                mapping={"default_code": "default_code", "name": "name"},
                natural_key_fields=["default_code"],
                rows=[
                    IngestRow(raw={"default_code": "SKU-1", "name": "One"}, values={}),
                    IngestRow(raw={"default_code": "SKU-1", "name": "One dup"}, values={}),
                ],
            )
        ]
    )
    with patch("app.ingest.map.scan_duplicates", return_value=DedupeScanResult(
        model="product.template", mode="exact", match_fields=["default_code"], groups=[]
    )):
        out = map_batch(FakeMapClient(), batch)
    assert any("batch duplicate" in w for t in out.tables for w in t.warnings)
