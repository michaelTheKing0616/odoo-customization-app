"""Slice C/D live smoke — BoM map/plan + employee org-only roster on Docker Odoo 19."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.ingest.extract import extract_upload_file
from app.ingest.pipeline import stage_dry_run, stage_map, stage_plan
from app.ingest.schema import IngestBatch, IngestFile, IngestRow, IngestTable


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


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
        pytest.skip(f"Odoo 19 not reachable for Slice C: {exc}")
    if not str(c.server_version().get("server_version", "")).startswith("19"):
        pytest.skip("Expected Odoo 19")
    return c


@pytest.mark.integration
def test_slice_c_bom_plan_dry_run(client: OdooClient) -> None:
    if not client.model_exists("mrp.bom"):
        pytest.skip("Manufacturing (mrp) not installed — install for Slice C")

    # Ensure finish + component products exist (idempotent by SKU)
    for sku, name in (("ING-ASSY-1", "Ingest Assy"), ("ING-PART-A", "Ingest Part A")):
        found = client.execute_kw(
            "product.product",
            "search_read",
            [[("default_code", "=", sku)]],
            {"fields": ["id"], "limit": 1},
        )
        if not found:
            client.execute_kw(
                "product.product",
                "create",
                [{"name": name, "default_code": sku, "type": "consu", "is_storable": True}],
            )

    csv = (
        "product_code,component_code,quantity,uom\n"
        "ING-ASSY-1,ING-PART-A,2,Units\n"
    ).encode()
    tables, _, _ = extract_upload_file(
        filename="bom.csv", raw=csv, doc_type="bom"
    )
    assert any(t.model == "mrp.bom" for t in tables) or any(
        t.doc_type == "bom" for t in tables
    )
    batch = IngestBatch(
        connection_id="live-c",
        notify_mode="batch_summary",
        files=[
            IngestFile(
                id="bom1",
                filename="bom.csv",
                doc_type="bom",
                confidence=1.0,
                table_ids=[t.id for t in tables],
            )
        ],
        tables=tables,
    )
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    assert batch.plan and batch.plan.steps
    flat = [m for step in batch.plan.steps for m in step.models]
    assert "mrp.bom" in flat
    assert "mrp.bom.line" in flat
    # Parent BoMs must dry-run clean. Lines resolve bom_id in a second pass
    # after the parent exists — unresolved bom_id on first dry-run is expected.
    parents = [t for t in batch.tables if t.model == "mrp.bom"]
    parent_batch = IngestBatch(
        connection_id="live-c-parent",
        notify_mode="batch_summary",
        files=batch.files,
        tables=parents,
    )
    parent_batch = stage_plan(parent_batch)
    parent_batch = stage_dry_run(parent_batch, client)
    assert parent_batch.commit_log is not None
    assert parent_batch.commit_log.failed == 0
    assert parent_batch.commit_log.created + parent_batch.commit_log.updated >= 1


@pytest.mark.integration
def test_slice_d_employee_org_only_map(client: OdooClient) -> None:
    if not client.model_exists("hr.employee"):
        pytest.skip("HR (hr) not installed — install for Slice D")

    table = IngestTable(
        id="e1",
        model="hr.employee",
        doc_type="employee_roster",
        rows=[
            IngestRow(
                raw={
                    "name": "Ingest Test Employee",
                    "work_email": "ingest.employee@example.com",
                    "salary": "99999",  # must not be writable via ingest
                    "department": "Operations",
                }
            )
        ],
    )
    batch = IngestBatch(
        connection_id="live-d",
        files=[
            IngestFile(
                id="hr1",
                filename="staff.csv",
                doc_type="employee_roster",
                confidence=1.0,
            )
        ],
        tables=[table],
    )
    batch = stage_map(batch, client)
    # Wage/payroll columns must not become commit values
    for row in batch.tables[0].rows:
        assert "salary" not in row.values
        assert "wage" not in row.values
    batch = stage_plan(batch)
    batch = stage_dry_run(batch, client)
    assert batch.commit_log is not None
    assert batch.commit_log.failed == 0
