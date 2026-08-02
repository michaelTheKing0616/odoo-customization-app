"""M1 capability matrix serialization (no live Odoo required for unit cases)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.capabilities import capabilities_from_version  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from odoo_client.compat import CapabilityId  # noqa: E402


def test_capabilities_from_version_19() -> None:
    matrix = capabilities_from_version("19.0")
    assert matrix is not None
    assert matrix.major == 19
    assert matrix.ga is True
    assert matrix.edition == "community"
    assert CapabilityId.RELATED_WRITE_DOTTED_PATH.value in matrix.supported
    assert matrix.unsupported == []


def test_capabilities_enterprise_hint() -> None:
    matrix = capabilities_from_version("19.0+e")
    assert matrix is not None
    assert matrix.edition == "enterprise"
    assert matrix.ga is True  # still major 19
    assert "Enterprise edition detected" in (matrix.message or "")
    assert "Studio" in (matrix.message or "")


def test_capabilities_from_version_18_ga() -> None:
    matrix = capabilities_from_version("18.0")
    assert matrix is not None
    assert matrix.major == 18
    assert matrix.ga is True
    assert CapabilityId.RELATED_WRITE_DOTTED_PATH.value in matrix.supported


def test_capabilities_from_version_17_ga_tree_primary() -> None:
    matrix = capabilities_from_version("17.0")
    assert matrix is not None
    assert matrix.major == 17
    assert matrix.ga is True
    assert CapabilityId.RELATED_WRITE_DOTTED_PATH.value in matrix.supported
    assert CapabilityId.OBJECT_WRITE_UPDATE_PATH.value in matrix.supported
    assert CapabilityId.LIST_AS_LIST_TYPE.value not in matrix.supported
    assert any(u.id == CapabilityId.LIST_AS_LIST_TYPE.value for u in matrix.unsupported)


def test_capabilities_unsupported_major() -> None:
    matrix = capabilities_from_version("15.0")
    assert matrix is not None
    assert matrix.ga is False
    assert matrix.supported == []
    assert len(matrix.unsupported) == len(CapabilityId)


def test_capabilities_none_when_unknown() -> None:
    assert capabilities_from_version(None) is None
    assert capabilities_from_version("") is None


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_list_connections_includes_capabilities(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="caps-m1",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}")
    assert res.status_code == 200
    body = res.json()
    assert body["capabilities"]["major"] == 19
    assert body["capabilities"]["ga"] is True
    assert "related_write_dotted_path" in body["capabilities"]["supported"]
