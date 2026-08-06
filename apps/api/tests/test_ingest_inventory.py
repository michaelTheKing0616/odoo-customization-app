"""Inventory count dedicated commit path."""

from __future__ import annotations

from typing import Any

from app.ingest.inventory import commit_inventory_count, validate_inventory_table
from app.ingest.schema import IngestRow, IngestTable


class FakeStockClient:
    def __init__(self) -> None:
        self.products = {"SKU-1": 10}
        self.locations = [{"id": 5, "complete_name": "WH/Stock", "usage": "internal"}]
        self.quants: dict[tuple[int, int], dict[str, Any]] = {}
        self.applied: list[int] = []

    def model_exists(self, model: str) -> bool:
        return model in {"stock.quant", "stock.location", "product.product"}

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        kwargs = kwargs or {}
        if model == "product.product" and method == "search_read":
            domain = args[0]
            code = domain[0][2]
            pid = self.products.get(str(code))
            return [{"id": pid}] if pid else []
        if model == "stock.location" and method == "search_read":
            return list(self.locations)
        if model == "stock.quant" and method == "search_read":
            domain = args[0]
            pid = domain[0][2]
            lid = domain[1][2]
            q = self.quants.get((pid, lid))
            return [q] if q else []
        if model == "stock.quant" and method == "create":
            vals = args[0]
            qid = len(self.quants) + 1
            self.quants[(vals["product_id"], vals["location_id"])] = {
                "id": qid,
                **vals,
            }
            return qid
        if model == "stock.quant" and method == "write":
            qid = args[0][0]
            vals = args[1]
            for k, q in self.quants.items():
                if q["id"] == qid:
                    q.update(vals)
            return True
        if model == "stock.quant" and method == "action_apply_inventory":
            self.applied.extend(args[0])
            return True
        return []


def test_inventory_validate_and_commit() -> None:
    client = FakeStockClient()
    table = IngestTable(
        id="i1",
        model="stock.quant",
        doc_type="inventory_count",
        rows=[IngestRow(raw={"product": "SKU-1", "quantity": "12", "location": "WH/Stock"})],
    )
    gaps, warns = validate_inventory_table(client, table)
    assert not gaps
    assert any("inventory_quantity" in w for w in warns)
    res = commit_inventory_count(client, table, dry_run=False)
    assert res["ok"] is True
    assert res["created"] == 1
    assert client.applied
