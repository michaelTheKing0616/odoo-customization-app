"""ING-5 — map + xref with fake Odoo client."""

from __future__ import annotations

from typing import Any

from app.ingest.map import map_batch
from app.ingest.schema import IngestBatch, IngestRow, IngestTable


class FakeIngestClient:
    def __init__(self, models: set[str] | None = None) -> None:
        self._models = models or {"res.partner", "product.template", "uom.uom"}

    def model_exists(self, model: str) -> bool:
        return model in self._models

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        _ = kwargs
        if model == "ir.model.fields" and method == "search_read":
            domain = args[0] if args else []
            target = domain[0][2] if domain else "res.partner"
            if target == "res.partner":
                return [
                    {"name": "name", "ttype": "char", "required": True, "readonly": False},
                    {"name": "email", "ttype": "char", "required": False, "readonly": False},
                ]
            if target == "product.template":
                return [
                    {"name": "name", "ttype": "char", "required": True, "readonly": False},
                    {"name": "uom_id", "ttype": "many2one", "relation": "uom.uom", "required": False},
                ]
        if model == "uom.uom" and method == "search_read":
            return []
        return []


def test_required_field_missing_gap() -> None:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="t1",
                model="res.partner",
                doc_type="customer_list",
                mapping={"email": "email"},
                rows=[IngestRow(raw={"email": "a@b.com"}, values={"email": "a@b.com"})],
            )
        ]
    )
    out = map_batch(FakeIngestClient(), batch)
    assert any(g.field == "name" for g in out.gaps)


def test_uom_missing_soft_gap() -> None:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="t1",
                model="product.template",
                doc_type="product_catalog",
                mapping={"name": "name", "uom": "uom_id"},
                rows=[IngestRow(raw={"name": "Widget", "uom": "crates"}, values={})],
            )
        ]
    )
    out = map_batch(FakeIngestClient(), batch)
    assert any("UoM" in g.message for g in out.gaps)
