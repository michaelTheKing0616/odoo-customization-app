"""Website editor API tests (REM-7)."""

from __future__ import annotations

import os
from io import BytesIO
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
            name="website-test",
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


def _website_client(*, arch: str = "<section><p>Hi</p></section>", published: bool = True):
    fake = MagicMock()

    def execute_kw(model, method, args, kwargs=None):
        kwargs = kwargs or {}
        if model == "ir.module.module" and method == "search_read":
            return [{"name": "website"}]
        if model == "website.page" and method == "read":
            return [
                {
                    "name": "Home",
                    "url": "/",
                    "view_id": [10, "Home"],
                    "is_published": published,
                }
            ]
        if model == "website.page" and method == "write":
            return True
        if model == "ir.ui.view" and method == "read":
            return [{"arch_db": arch}]
        if model == "ir.ui.view" and method == "write":
            return True
        if model == "ir.attachment" and method == "create":
            return 99
        raise AssertionError(f"unexpected execute_kw {model}.{method}")

    fake.execute_kw = execute_kw
    return fake


def _kinds(blocks: list[dict]) -> list[str]:
    out: list[str] = []
    for b in blocks:
        out.append(str(b.get("kind")))
        out.extend(_kinds(b.get("children") or []))
    return out


def test_get_page_blocks(client: TestClient, connection_id: str) -> None:
    fake = _website_client()
    with patch("app.routers.website.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{connection_id}/website/pages/1/blocks")
    assert res.status_code == 200
    body = res.json()
    assert body["page_id"] == 1
    assert body["view_id"] == 10
    assert body["is_published"] is True
    assert "paragraph" in _kinds(body["blocks"])


def test_save_page_blocks(client: TestClient, connection_id: str) -> None:
    fake = _website_client()
    with patch("app.routers.website.client_from_connection", return_value=fake):
        with patch("app.routers.website.snapshot_view", return_value=MagicMock(id="snap-w")):
            res = client.put(
                f"/api/connections/{connection_id}/website/pages/1/blocks",
                json={
                    "page_id": 1,
                    "view_id": 10,
                    "blocks": [{"id": "p-1", "kind": "paragraph", "text": "Updated"}],
                },
            )
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_publish_toggle(client: TestClient, connection_id: str) -> None:
    fake = _website_client(published=False)
    with patch("app.routers.website.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{connection_id}/website/pages/1/publish",
            json={"page_id": 1, "publish": False},
        )
    assert res.status_code == 200
    assert res.json()["is_published"] is False


def test_upload_image(client: TestClient, connection_id: str) -> None:
    fake = _website_client()
    png = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    with patch("app.routers.website.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{connection_id}/website/upload-image",
            files={"file": ("hero.png", png, "image/png")},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["attachment_id"] == 99
    assert body["src"] == "/web/image/99"
    assert body["name"] == "hero.png"
