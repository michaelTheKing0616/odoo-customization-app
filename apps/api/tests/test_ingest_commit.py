"""ING-8 — commit order + upsert via fake client."""

from __future__ import annotations

from typing import Any

from app.ingest.commit import run_commit_plan
from app.ingest.order import build_plan
from app.ingest.schema import IngestBatch, IngestRow, IngestTable


class FakeCommitClient:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, int]] = {
            "res.partner": {},
            "product.template": {},
        }

    def model_exists(self, model: str) -> bool:
        return model in self._store

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        _ = kwargs
        if model == "ir.model.fields" and method == "search_read":
            domain = args[0] if args else []
            target = domain[0][2] if domain else model
            if target == "res.partner":
                return [
                    {"name": "name", "ttype": "char", "required": True, "readonly": False},
                    {"name": "email", "ttype": "char", "required": False, "readonly": False},
                ]
            return [
                {"name": "name", "ttype": "char", "required": True, "readonly": False},
                {"name": "default_code", "ttype": "char", "required": False, "readonly": False},
                {"name": "list_price", "ttype": "float", "required": False, "readonly": False},
            ]
        if method == "search":
            domain = args[0] if args else []
            key = domain[0][2] if domain else None
            bucket = self._store.get(model, {})
            rid = bucket.get(str(key))
            return [rid] if rid else []
        if method == "create":
            vals_list = args[0] if args else []
            ids = []
            for vals in vals_list:
                rid = len(self._store[model]) + 1
                match_key = vals.get("email") or vals.get("default_code") or vals.get("name")
                self._store[model][str(match_key)] = rid
                ids.append(rid)
            return ids
        if method == "write":
            return True
        return []


def _slice_a_batch() -> IngestBatch:
    batch = IngestBatch(
        tables=[
            IngestTable(
                id="p1",
                model="res.partner",
                doc_type="customer_list",
                mapping={"name": "name", "email": "email"},
                natural_key_fields=["email"],
                mode="upsert",
                rows=[
                    IngestRow(raw={"name": "Acme", "email": "ops@acme.example"}, values={}),
                ],
            ),
            IngestTable(
                id="t1",
                model="product.template",
                doc_type="product_catalog",
                mapping={"name": "name", "default_code": "default_code", "list_price": "list_price"},
                natural_key_fields=["default_code"],
                mode="upsert",
                rows=[
                    IngestRow(raw={"name": "GPS", "default_code": "GPS-KIT", "list_price": "89"}, values={}),
                ],
            ),
        ]
    )
    batch.plan = build_plan(batch)
    return batch


def test_dry_run_follows_plan_order() -> None:
    client = FakeCommitClient()
    batch = _slice_a_batch()
    log = run_commit_plan(client, batch, dry_run=True)
    assert log.created >= 2
    assert len(log.step_results) == 2


def test_second_upload_updates_not_duplicates() -> None:
    client = FakeCommitClient()
    batch = _slice_a_batch()
    run_commit_plan(client, batch, dry_run=False)
    log2 = run_commit_plan(client, batch, dry_run=False)
    assert log2.updated >= 1 or log2.skipped >= 1
