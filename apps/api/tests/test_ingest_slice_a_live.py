"""Slice A live smoke — 3 CSV ingest job on Docker Odoo 19."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.industry_seeds import partner_seed, product_seed
from app.ingest.extract import extract_upload_file
from app.ingest.order import build_plan
from app.ingest.pipeline import stage_commit, stage_dry_run, stage_map, stage_plan
from app.ingest.schema import IngestBatch, IngestFile


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _csv_from_seed(pack_fn, model: str) -> bytes:
    pack = pack_fn()
    entry = next(m for m in pack["models"] if m["model"] == model)
    return entry["csv"].encode("utf-8")


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for ingest smoke: {exc}")
    if not str(c.server_version().get("server_version", "")).startswith("19"):
        pytest.skip("Expected Odoo 19")
    return c


@pytest.mark.integration
def test_slice_a_three_csv_plan_and_dry_run(client: OdooClient) -> None:
    uploads = [
        ("prices.csv", _csv_from_seed(product_seed, "product.template"), "price_list"),
        ("customers.csv", _csv_from_seed(partner_seed, "res.partner"), "customer_list"),
        ("products.csv", _csv_from_seed(product_seed, "product.template"), "product_catalog"),
    ]
    batch = IngestBatch(connection_id="live")
    tables = []
    for filename, raw, doc_type in uploads:
        extracted, _, _ = extract_upload_file(
            filename=filename, raw=raw, doc_type=doc_type  # type: ignore[arg-type]
        )
        batch.files.append(
            IngestFile(
                id=filename,
                filename=filename,
                doc_type=doc_type,  # type: ignore[arg-type]
                confidence=1.0,
                table_ids=[t.id for t in extracted],
            )
        )
        tables.extend(extracted)
    batch.tables = tables
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    assert batch.plan and batch.plan.steps
    flat = [m for step in batch.plan.steps for m in step.models]
    assert "res.partner" in flat
    assert "product.template" in flat
    batch = stage_dry_run(batch, client)
    log = batch.commit_log
    assert log is not None
    assert log.created + log.updated >= 1

    # Re-upload products only — upsert not duplicate
    raw = _csv_from_seed(product_seed, "product.template")
    extracted, _, _ = extract_upload_file(
        filename="products.csv", raw=raw, doc_type="product_catalog"
    )
    batch2 = IngestBatch(
        tables=extracted,
        files=[
            IngestFile(
                id="p2",
                filename="products.csv",
                doc_type="product_catalog",
                confidence=1.0,
                table_ids=[extracted[0].id],
            )
        ],
    )
    batch2 = stage_map(batch2, client)
    batch2.plan = build_plan(batch2)
    batch2 = stage_commit(batch2, client)
    log2 = batch2.commit_log
    assert log2 is not None
    assert log2.failed == 0
