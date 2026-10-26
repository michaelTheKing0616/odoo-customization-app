"""Pin BL-02..BL-06 (REG-NP-BL).

AC1 split: re-verify writes docs/plans/next-phase/03_BASELINE.md, which is
outside this allow-list. This file does not invent an AC1 pin and does not
freeze router, test-file, or alembic counts.

Captured 2026-10-22 from current behaviour. Older pins are unchanged.
"""

from __future__ import annotations

import inspect
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

from app.logging_config import JsonLogFormatter, SensitiveLogFilter, install_json_logging
from app.request_id import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    _resolve_request_id,
    request_id_var,
)

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


def _source_code(path: Path) -> str:
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


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


def test_ac2_request_id_bounds_and_bearer_case() -> None:
    """Captured 2026-10-22. Safe ids match the 1..128 charset. Bearer is case-sensitive."""
    assert _resolve_request_id("a") == "a"
    assert _resolve_request_id("z9_-") == "z9_-"
    exact = "b" * 128
    assert _resolve_request_id(exact) == exact
    assert _resolve_request_id("bearer_ok") == "bearer_ok"

    missing = _resolve_request_id(None)
    assert missing != ""
    assert _HEX32.fullmatch(missing)
    for bad in ("", "c" * 129, "ok.dot", "has space", "ok-Bearer-ok"):
        replaced = _resolve_request_id(bad)
        assert replaced != bad
        assert _HEX32.fullmatch(replaced)

    with _client() as client:
        kept = client.get("/ping", headers={"X-Request-Id": exact})
        assert kept.headers.get("X-Request-Id") == exact
        over = client.get("/ping", headers={"X-Request-Id": "c" * 129})
        over_id = over.headers.get("X-Request-Id")
        assert over_id is not None
        assert over_id != "c" * 129
        assert _HEX32.fullmatch(over_id)
        dotted = client.get("/ping", headers={"X-Request-Id": "ok.dot"})
        dotted_id = dotted.headers.get("X-Request-Id")
        assert dotted_id is not None
        assert dotted_id != "ok.dot"
        assert _HEX32.fullmatch(dotted_id)
        lower = client.get("/ping", headers={"X-Request-Id": "bearer_ok"})
        assert lower.headers.get("X-Request-Id") == "bearer_ok"


def test_ac2_handler_sees_request_id_context() -> None:
    """Captured 2026-10-22. The route observes the id the response header echoes."""
    seen: list[str | None] = []

    async def _echo_rid(_request: object) -> PlainTextResponse:
        seen.append(request_id_var.get())
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/ping", _echo_rid)],
        middleware=[Middleware(RequestIdMiddleware)],
    )
    safe = "trace_abc123-XYZ_99"
    with TestClient(app) as client:
        echoed = client.get("/ping", headers={"X-Request-Id": safe})
        assert echoed.headers.get("X-Request-Id") == safe
        generated = client.get("/ping")
        generated_id = generated.headers.get("X-Request-Id")
        assert generated_id is not None
        assert _HEX32.fullmatch(generated_id)
    assert seen == [safe, generated_id]
    assert "request_id_var.reset(token)" in inspect.getsource(RequestIdMiddleware.dispatch)


def test_ac2_main_registers_request_id_middleware() -> None:
    """Captured 2026-10-22. Does not import app.main."""
    code = _source_code(_REPO / "apps" / "api" / "app" / "main.py")
    assert "app.add_middleware(RequestIdMiddleware)" in code


def test_ac3_null_request_id_and_utc_timestamp() -> None:
    """Captured 2026-10-22."""
    token = request_id_var.set(None)
    try:
        data = json.loads(JsonLogFormatter().format(_record("ping", None)))
    finally:
        request_id_var.reset(token)
    assert set(data) == _JSON_KEYS
    assert data["msg"] == "ping"
    assert data["request_id"] is None
    assert data["ts"].endswith("+00:00")


def test_ac3_filter_case_args_and_unformattable() -> None:
    """Captured 2026-10-22."""
    filt = SensitiveLogFilter()
    assert filt.filter(_record("PASSWORD=x", None)) is False
    assert filt.filter(_record("see Api_Key", None)) is False
    assert filt.filter(_record("has secret inside", None)) is False
    assert filt.filter(_record("session token", None)) is False
    assert filt.filter(_record("authorization header", None)) is False
    assert filt.filter(_record("need=%s extra=%s", (1,))) is False
    keyed = logging.LogRecord(
        name="reg.np.bl",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user=%(user)s",
        args={"user": "ada", "api_key": "hidden"},
        exc_info=None,
    )
    assert keyed.getMessage() == "user=ada"
    assert filt.filter(keyed) is False


def test_ac3_install_json_logging_is_one_extra_handler() -> None:
    """Captured 2026-10-22. Does not replace handlers already on the root logger."""
    root = logging.getLogger()
    before = list(root.handlers)
    install_json_logging()
    install_json_logging()
    marked = [
        handler
        for handler in root.handlers
        if getattr(handler, "_odoo_custom_json_logging_handler", False)
    ]
    assert len(marked) == 1
    assert isinstance(marked[0].formatter, JsonLogFormatter)
    assert any(isinstance(item, SensitiveLogFilter) for item in marked[0].filters)
    for handler in before:
        assert handler in root.handlers


def test_ac3_main_calls_install_json_logging() -> None:
    """Captured 2026-10-22. Does not import app.main."""
    code = _source_code(_REPO / "apps" / "api" / "app" / "main.py")
    assert "install_json_logging()" in code


def test_ac4_lint_script_runs_ruff_and_mypy() -> None:
    """Captured 2026-10-22. Does not freeze the module list."""
    code = _source_code(_REPO / "apps" / "api" / "scripts" / "lint_new_modules.sh")
    assert "if [[ ${#FILES[@]} -eq 0 ]]; then" in code
    assert "exit 0" in code
    assert 'uv run --extra dev ruff check "${FILES[@]}"' in code
    assert 'uv run --extra dev mypy "${FILES[@]}"' in code


def test_ac6_every_fact_bullet_is_tagged() -> None:
    """Captured 2026-10-22. Each fact bullet carries [verified] or [unverified]."""
    for name in ("verified-facts.md", "recon.md"):
        lines = (_REPO / "docs" / name).read_text(encoding="utf-8").splitlines()
        bullets = [line for line in lines if line.startswith("- ")]
        assert bullets
        missing = [
            line
            for line in bullets
            if "[verified]" not in line and "[unverified]" not in line
        ]
        assert missing == []
