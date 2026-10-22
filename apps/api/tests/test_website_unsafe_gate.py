"""DOC-WEBSITE — unsafe gate on website page save (PDF-05 family)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.website_blocks import (  # noqa: E402
    WebsiteBlock,
    gate_website_save,
    refuse_unsafe_website_arch,
    refuse_unsafe_website_blocks,
)


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def connection_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="website-gate-test",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _website_client():
    fake = MagicMock()

    def execute_kw(model, method, args, kwargs=None):
        if model == "ir.module.module" and method == "search_read":
            return [{"name": "website"}]
        if model == "ir.ui.view" and method == "write":
            return True
        raise AssertionError(f"unexpected execute_kw {model}.{method}")

    fake.execute_kw = execute_kw
    return fake


def test_refuse_script_in_arch() -> None:
    with pytest.raises(ValueError, match="script"):
        refuse_unsafe_website_arch("<section><script>x</script></section>")


def test_refuse_javascript_href_in_blocks() -> None:
    with pytest.raises(ValueError, match="javascript"):
        refuse_unsafe_website_blocks(
            [WebsiteBlock(id="a-1", kind="link", text="x", href="javascript:alert(1)")]
        )


def test_allow_locked_foreach() -> None:
    blocks = [
        WebsiteBlock(
            id="locked-1",
            kind="locked",
            locked_xml='<t t-foreach="items" t-as="item"/>',
        )
    ]
    arch = "<section><p>Hi</p></section>"
    gate_website_save(blocks, arch)


def test_allow_plain_save(client: TestClient, connection_id: str) -> None:
    fake = _website_client()
    with patch("app.routers.website.client_from_connection", return_value=fake):
        with patch("app.routers.website.snapshot_view", return_value=MagicMock(id="snap")):
            res = client.put(
                f"/api/connections/{connection_id}/website/pages/1/blocks",
                json={
                    "page_id": 1,
                    "view_id": 10,
                    "blocks": [{"id": "p-1", "kind": "paragraph", "text": "Updated"}],
                },
            )
    assert res.status_code == 200


def test_refuse_script_on_save_api(client: TestClient, connection_id: str) -> None:
    fake = _website_client()
    with patch("app.routers.website.client_from_connection", return_value=fake):
        with patch("app.routers.website.snapshot_view", return_value=MagicMock(id="snap")):
            res = client.put(
                f"/api/connections/{connection_id}/website/pages/1/blocks",
                json={
                    "page_id": 1,
                    "view_id": 10,
                    "blocks": [
                        {
                            "id": "locked-1",
                            "kind": "locked",
                            "locked_xml": "<script>evil()</script>",
                        }
                    ],
                },
            )
    assert res.status_code == 400
    assert "script" in res.json()["detail"].lower()
