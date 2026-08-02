"""Rate limit middleware unit test."""

from __future__ import annotations

import asyncio
import os

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.main import app  # noqa: E402
from app.rate_limit import RateLimitMiddleware  # noqa: E402


def test_rate_limit_blocks_excess_posts() -> None:
    mw = RateLimitMiddleware(app, limit=3, window_s=60.0)

    class FakeRequest:
        method = "POST"
        url = type("U", (), {"path": "/api/connections"})()
        headers: dict[str, str] = {}
        client = type("C", (), {"host": "127.0.0.1"})()

    async def ok(_req):
        return type("R", (), {"status_code": 200})()

    async def run() -> None:
        req = FakeRequest()
        for _ in range(3):
            res = await mw.dispatch(req, ok)
            assert getattr(res, "status_code", 200) == 200
        blocked = await mw.dispatch(req, ok)
        assert blocked.status_code == 429

    asyncio.run(run())


def test_health_still_ok() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
