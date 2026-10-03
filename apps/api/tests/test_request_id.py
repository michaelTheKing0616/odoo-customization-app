"""X-Request-Id middleware tests."""

from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_generates_request_id_when_header_missing(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    rid = res.headers.get("X-Request-Id")
    assert rid is not None
    assert _HEX32.fullmatch(rid)


def test_echoes_safe_incoming_request_id(client: TestClient) -> None:
    safe = "trace_abc123-XYZ_99"
    res = client.get("/health", headers={"X-Request-Id": safe})
    assert res.status_code == 200
    assert res.headers.get("X-Request-Id") == safe


@pytest.mark.parametrize(
    "bad",
    [
        "has space inside",
        "prefix-Bearer-suffix",
    ],
)
def test_rejects_unsafe_request_id(client: TestClient, bad: str) -> None:
    res = client.get("/health", headers={"X-Request-Id": bad})
    assert res.status_code == 200
    rid = res.headers.get("X-Request-Id")
    assert rid is not None
    assert rid != bad
    assert _HEX32.fullmatch(rid)
