"""JSON logging formatter and sensitive-field filter tests."""

from __future__ import annotations

import io
import json
import logging

from app.logging_config import (
    JsonLogFormatter,
    SensitiveLogFilter,
    install_json_logging,
)
from app.request_id import request_id_var


def _isolated_logger(name: str, stream: io.StringIO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(SensitiveLogFilter())
    logger.addHandler(handler)
    return logger


def test_json_line_includes_request_id_from_contextvar() -> None:
    stream = io.StringIO()
    logger = _isolated_logger("test.logging_config.request_id", stream)
    token = request_id_var.set("trace-xyz-99")
    try:
        logger.info("hello")
    finally:
        request_id_var.reset(token)

    data = json.loads(stream.getvalue().strip())
    assert set(data) == {"ts", "level", "logger", "msg", "request_id"}
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logging_config.request_id"
    assert data["msg"] == "hello"
    assert data["request_id"] == "trace-xyz-99"


def test_request_id_null_when_unset() -> None:
    stream = io.StringIO()
    logger = _isolated_logger("test.logging_config.no_rid", stream)
    logger.info("ping")
    data = json.loads(stream.getvalue().strip())
    assert data["request_id"] is None


def test_broken_format_string_does_not_raise() -> None:
    stream = io.StringIO()
    logger = _isolated_logger("test.logging_config.broken_format", stream)
    logger.info("id=%s %s", 1)
    out = stream.getvalue().strip()
    assert out == ""

    record = logging.LogRecord(
        name="test.broken",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="need=%s extra=%s",
        args=(1,),
        exc_info=None,
    )
    assert SensitiveLogFilter().filter(record) is False
    data = json.loads(JsonLogFormatter().format(record))
    assert data["msg"] == "[unformattable]"
    assert "args" not in data


def test_sensitive_password_message_not_in_output() -> None:
    stream = io.StringIO()
    logger = _isolated_logger("test.logging_config.sensitive", stream)
    logger.info("password=hunter2")
    out = stream.getvalue()
    assert "hunter2" not in out
    assert out.strip() == ""


def test_install_json_logging_is_idempotent() -> None:
    install_json_logging()
    root = logging.getLogger()
    marker = "_odoo_custom_json_logging_handler"
    before = sum(1 for h in root.handlers if getattr(h, marker, False))
    install_json_logging()
    after = sum(1 for h in root.handlers if getattr(h, marker, False))
    assert before == after
    assert before >= 1
