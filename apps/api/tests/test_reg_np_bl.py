"""Pin BL-02..BL-06 (REG-NP-BL).

AC1 is held: re-verify writes docs/plans/next-phase/03_BASELINE.md, which is
outside this allow-list. This file does not freeze router, test-file, or
alembic counts.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.logging_config import JsonLogFormatter, SensitiveLogFilter
from app.request_id import REQUEST_ID_HEADER, RequestIdMiddleware, request_id_var

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_JSON_KEYS = {"ts", "level", "logger", "msg", "request_id"}


async def _ping(_request: object) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _client() -> TestClient:
    app = Starlette(
        routes=[Route("/ping", _ping)],
        middleware=[Middleware(RequestIdMiddleware)],
    )
    return TestClient(app)


def _record(msg: str, args: tuple[object, ...] | None) -> logging.LogRecord:
    return logging.LogRecord(
        name="reg.np.bl",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_ac2_request_id_middleware() -> None:
    assert REQUEST_ID_HEADER == "X-Request-Id"
    with _client() as client:
        missing = client.get("/ping")
        assert missing.status_code == 200
        generated = missing.headers.get("X-Request-Id")
        assert generated is not None
        assert _HEX32.fullmatch(generated)

        safe = "trace_abc123-XYZ_99"
        echoed = client.get("/ping", headers={"X-Request-Id": safe})
        assert echoed.status_code == 200
        assert echoed.headers.get("X-Request-Id") == safe

        for bad in ("has space inside", "prefix-Bearer-suffix"):
            rejected = client.get("/ping", headers={"X-Request-Id": bad})
            assert rejected.status_code == 200
            rid = rejected.headers.get("X-Request-Id")
            assert rid is not None
            assert rid != bad
            assert _HEX32.fullmatch(rid)


def test_ac3_json_log_formatter() -> None:
    token = request_id_var.set("trace_abc123-XYZ_99")
    try:
        data = json.loads(JsonLogFormatter().format(_record("hello", None)))
    finally:
        request_id_var.reset(token)
    assert set(data) == _JSON_KEYS
    assert data["level"] == "INFO"
    assert data["logger"] == "reg.np.bl"
    assert data["msg"] == "hello"
    assert data["request_id"] == "trace_abc123-XYZ_99"
    assert isinstance(data["ts"], str) and data["ts"]

    broken = json.loads(JsonLogFormatter().format(_record("need=%s extra=%s", (1,))))
    assert set(broken) == _JSON_KEYS
    assert broken["msg"] == "[unformattable]"


def test_ac3_sensitive_log_filter() -> None:
    filt = SensitiveLogFilter()
    assert filt.filter(_record("see password field", None)) is False
    assert filt.filter(_record("missing api_key", None)) is False
    assert filt.filter(_record("invoice posted", None)) is True


def test_ac4_lint_and_type_slots() -> None:
    script = (_REPO / "apps/api/scripts/lint_new_modules.sh").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in script.splitlines() if line.strip() and not line.strip().startswith("#")
    )
    assert "app/request_id.py" in code
    assert "app/logging_config.py" in code
    package = json.loads((_REPO / "apps/web/package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["typecheck"] == "tsc --noEmit"


def test_ac5_adr_folder() -> None:
    adr = _REPO / "docs" / "adr"
    missing = [
        f"ADR-{index:02d}.md"
        for index in range(1, 15)
        if not (adr / f"ADR-{index:02d}.md").is_file()
    ]
    assert missing == []


def test_ac6_verified_facts_and_recon() -> None:
    assert (_REPO / "docs" / "recon.md").is_file()
    facts = (_REPO / "docs" / "verified-facts.md").read_text(encoding="utf-8").splitlines()
    middleware = [line for line in facts if "RequestIdMiddleware" in line]
    assert middleware
    assert all("[verified]" in line for line in middleware)
    production = [line for line in facts if "rewriting headers" in line]
    assert len(production) == 1
    assert "[unverified]" in production[0]
    assert "[verified]" not in production[0]
