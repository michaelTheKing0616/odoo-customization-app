"""Live RPC smoke — BLK-8 merged PDF on Docker Odoo 19."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.report_render import probe_report_render, render_report_pdf

from app.report_merge import pdf_page_count, run_merge_print


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
        pytest.skip(f"Odoo 19 not reachable for BLK-8 smoke: {exc}")
    version = c.server_version()
    if not str(version.get("server_version", "")).startswith("19"):
        pytest.skip(f"Expected Odoo 19, got {version.get('server_version')}")
    return c


@pytest.fixture(scope="module")
def company_preview_reports(client: OdooClient) -> tuple[int, int, int]:
    rows = client.execute_kw(
        "ir.actions.report",
        "search_read",
        [[("report_name", "in", ["web.preview_internalreport", "web.preview_externalreport"])]],
        {"fields": ["id", "report_name"], "order": "id"},
    )
    if len(rows) < 2:
        pytest.skip("Need web preview internal + external reports on this database")
    company_id = int(client.execute_kw("res.company", "search", [[]], {"limit": 1})[0])
    internal = next(r for r in rows if r["report_name"] == "web.preview_internalreport")
    external = next(r for r in rows if r["report_name"] == "web.preview_externalreport")
    return int(internal["id"]), int(external["id"]), company_id


@pytest.mark.integration
def test_report_render_probe_live(client: OdooClient, company_preview_reports: tuple[int, int, int]) -> None:
    internal_id, _, company_id = company_preview_reports
    probe = probe_report_render(client, sample_report_id=internal_id, sample_res_id=company_id)
    assert probe.http_report_pdf or probe.primary_path.startswith("rpc:")
    assert probe.primary_path != "none"
    assert probe.major == 19


@pytest.mark.integration
def test_merge_print_two_preview_reports_live(
    client: OdooClient, company_preview_reports: tuple[int, int, int]
) -> None:
    internal_id, external_id, company_id = company_preview_reports
    internal_pdf = render_report_pdf(client, internal_id, [company_id])
    external_pdf = render_report_pdf(client, external_id, [company_id])
    expected_pages = pdf_page_count(internal_pdf) + pdf_page_count(external_pdf)

    merged_bytes, meta = run_merge_print(
        client,
        items=[
            {"report_id": internal_id, "record_ids": [company_id]},
            {"report_id": external_id, "record_ids": [company_id]},
        ],
    )
    assert meta.total_pages == expected_pages
    assert pdf_page_count(merged_bytes) == expected_pages
    assert merged_bytes.startswith(b"%PDF")
    assert meta.probe is not None
    assert meta.probe.primary_path != "none"
