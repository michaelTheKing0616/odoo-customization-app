"""BLK probe recording for Odoo 17/18 — cron trigger + report render."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.report_render import probe_report_render

from app.bulk_suite.cron_manager import probe_run_method

PROBE_DOC = Path(__file__).resolve().parents[3] / "docs" / "research" / "blk_probe_matrix_2026-08-03.json"


def _client_for_major(major: int) -> OdooClient:
    if major == 17:
        url = os.environ.get("ODOO17_URL", "http://127.0.0.1:8071")
        db = os.environ.get("ODOO17_DB", "odoo17_dev")
    elif major == 18:
        url = os.environ.get("ODOO18_URL", "http://127.0.0.1:8070")
        db = os.environ.get("ODOO18_DB", "odoo18_dev")
    else:
        url = os.environ.get("ODOO_URL", "http://127.0.0.1:8069")
        db = os.environ.get("ODOO_DB", "odoo_dev")
    config = ConnectionConfig(
        url=url,
        db=db,
        username=os.environ.get("ODOO_USER", "admin"),
        password=os.environ.get("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo {major} not reachable: {exc}")
    if c.capabilities.major != major:
        pytest.skip(f"Expected major {major}, got {c.capabilities.major}")
    return c


def _record_probe(major: int, cron_probe: dict, report_probe: dict) -> None:
    data: dict = {"date": "2026-08-03", "majors": {}}
    if PROBE_DOC.is_file():
        data = json.loads(PROBE_DOC.read_text())
    data.setdefault("majors", {})[str(major)] = {
        "cron_run_now": cron_probe,
        "report_render": {
            "primary_path": report_probe.get("primary_path"),
            "http_report_pdf": report_probe.get("http_report_pdf"),
            "major": report_probe.get("major"),
        },
    }
    PROBE_DOC.parent.mkdir(parents=True, exist_ok=True)
    PROBE_DOC.write_text(json.dumps(data, indent=2) + "\n")


@pytest.mark.integration
@pytest.mark.parametrize("major", [17, 18, 19])
def test_blk_probe_cron_and_report_recorded(major: int) -> None:
    client = _client_for_major(major)
    cron_probe = probe_run_method(client)
    assert cron_probe.get("primary") == "method_direct_trigger"

    company_ids = client.execute_kw("res.company", "search", [[]], {"limit": 1})
    if not company_ids:
        pytest.skip("No res.company on instance")
    report_rows = client.execute_kw(
        "ir.actions.report",
        "search_read",
        [[("report_name", "in", ["web.preview_internalreport"])]],
        {"fields": ["id"], "limit": 1},
    )
    if not report_rows:
        pytest.skip("web.preview_internalreport not on instance")
    report_probe = probe_report_render(
        client,
        sample_report_id=int(report_rows[0]["id"]),
        sample_res_id=int(company_ids[0]),
    )
    assert report_probe.primary_path != "none"
    _record_probe(major, cron_probe, report_probe.to_dict())
