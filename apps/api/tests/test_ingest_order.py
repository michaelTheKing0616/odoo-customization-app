"""ING-6 — dependency ordering."""

from __future__ import annotations

from app.ingest.order import build_plan
from app.ingest.schema import IngestBatch, IngestTable


def _table(model: str, tid: str) -> IngestTable:
    return IngestTable(id=tid, model=model, doc_type="other")


def test_three_file_slice_a_order() -> None:
    batch = IngestBatch(
        tables=[
            _table("product.template", "t-prod"),
            _table("res.partner", "t-partner"),
            _table("product.template", "t-price"),
        ]
    )
    plan = build_plan(batch)
    assert plan.steps
    flat = [m for step in plan.steps for m in step.models]
    assert "res.partner" in flat
    assert "product.template" in flat


def test_parallel_ok_unrelated_models() -> None:
    batch = IngestBatch(
        tables=[
            _table("res.partner", "t1"),
            _table("product.template", "t2"),
        ]
    )
    plan = build_plan(batch)
    assert len(plan.steps) >= 1
    if len(plan.steps) == 1 and len(plan.steps[0].models) == 2:
        assert plan.steps[0].parallel_ok is True


def test_bom_dependency_order() -> None:
    batch = IngestBatch(
        tables=[
            _table("mrp.bom.line", "line"),
            _table("mrp.bom", "bom"),
        ]
    )
    plan = build_plan(batch)
    flat = [m for step in plan.steps for m in step.models]
    assert flat.index("mrp.bom") < flat.index("mrp.bom.line")
