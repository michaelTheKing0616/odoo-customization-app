"""Website editor live smoke (docker Odoo 19 + website module, optional)."""

from __future__ import annotations

import io
import os
import uuid

import pytest

pytestmark = pytest.mark.integration


def _connection_row():
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection

    init_db()
    db = SessionLocal()
    try:
        cid = os.environ.get("ODOO_E2E_CONNECTION_ID")
        if cid:
            row = db.get(OdooConnection, cid)
        else:
            row = db.query(OdooConnection).order_by(OdooConnection.created_at.desc()).first()
        return row
    finally:
        db.close()


@pytest.mark.skipif(os.environ.get("ODOO_E2E") != "1", reason="Set ODOO_E2E=1 for live website smoke")
def test_website_blocks_edit_publish_live() -> None:
    """Live: paragraph edit + image replace + publish toggle with RPC read-back."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.odoo_service import client_from_connection

    row = _connection_row()
    if row is None:
        pytest.skip("No connection in app DB")

    client = client_from_connection(row)
    mods = client.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", "website"), ("state", "=", "installed")]],
        {"fields": ["name"], "limit": 1},
    )
    if not mods:
        pytest.skip("website module not installed on target Odoo")

    pages = client.execute_kw(
        "website.page",
        "search_read",
        [[]],
        {"fields": ["name"], "limit": 1},
    )
    if not pages:
        pytest.skip("no website.page rows on target Odoo")

    page_id = pages[0]["id"]
    marker = f"REM14-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as http:
        res = http.get(f"/api/connections/{row.id}/website/pages/{page_id}/blocks")
        assert res.status_code == 200
        body = res.json()
        assert body["page_id"] == page_id
        view_id = body["view_id"]
        blocks = body["blocks"]
        assert blocks

        edited = False
        for block in blocks:
            if block.get("kind") == "paragraph" and not edited:
                block["text"] = marker
                edited = True
            if block.get("kind") == "image":
                png = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                    b"\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                up = http.post(
                    f"/api/connections/{row.id}/website/upload-image",
                    files={"file": ("rem14.png", io.BytesIO(png), "image/png")},
                )
                assert up.status_code == 200
                block["src"] = up.json()["src"]
                break

        assert edited, "no paragraph block to edit"
        save = http.put(
            f"/api/connections/{row.id}/website/pages/{page_id}/blocks",
            json={"page_id": page_id, "view_id": view_id, "blocks": blocks},
        )
        assert save.status_code == 200

        pub = http.post(
            f"/api/connections/{row.id}/website/pages/{page_id}/publish",
            json={"page_id": page_id, "publish": not body["is_published"]},
        )
        assert pub.status_code == 200
        assert pub.json()["is_published"] is (not body["is_published"])

    views = client.execute_kw(
        "ir.ui.view",
        "read",
        [[view_id]],
        {"fields": ["arch_db"]},
    )
    arch = views[0].get("arch_db") or ""
    assert marker in arch

    page_row = client.execute_kw(
        "website.page",
        "read",
        [[page_id]],
        {"fields": ["is_published"]},
    )
    assert bool(page_row[0]["is_published"]) is (not body["is_published"])
