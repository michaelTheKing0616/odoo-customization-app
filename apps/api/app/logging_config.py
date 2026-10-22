"""Structured JSON logging for the API (stdlib logging only)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from app.request_id import request_id_var

_SENSITIVE = re.compile(
    r"(password|api_key|secret|token|authorization)",
    re.IGNORECASE,
)

_JSON_HANDLER_MARKER = "_odoo_custom_json_logging_handler"


class SensitiveLogFilter(logging.Filter):
    """Drop log records whose message or args mention sensitive key names."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return False
        if _SENSITIVE.search(msg):
            return False
        args = record.args
        if args is None:
            return True
        try:
            if isinstance(args, dict):
                for key in args:
                    if _SENSITIVE.search(str(key)):
                        return False
            if _SENSITIVE.search(str(args)):
                return False
        except Exception:
            return False
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, msg, request_id."""

    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get()
        try:
            msg = record.getMessage()
        except Exception:
            msg = "[unformattable]"
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": msg,
            "request_id": rid if rid is not None else None,
        }
        return json.dumps(payload, ensure_ascii=False)


def install_json_logging() -> None:
    """Attach a single JSON stream handler on the root logger (idempotent)."""
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, _JSON_HANDLER_MARKER, False):
            return

    handler = logging.StreamHandler()
    setattr(handler, _JSON_HANDLER_MARKER, True)
    handler.addFilter(SensitiveLogFilter())
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    _install_file_handler(root)


_FILE_HANDLER_MARKER = "_ingenium_file_handler"


def _install_file_handler(root: logging.Logger) -> None:
    """Also write JSON logs to apps/api/logs/api.log (rotating, gitignored).

    Off under pytest or with INGENIUM_LOG_FILE=0. Path override: INGENIUM_LOG_FILE_PATH.
    """
    import os
    import sys
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    if "pytest" in sys.modules or os.environ.get("INGENIUM_LOG_FILE", "1").lower() in {"0", "off", "false"}:
        return
    if any(getattr(h, _FILE_HANDLER_MARKER, False) for h in root.handlers):
        return
    path = Path(
        os.environ.get("INGENIUM_LOG_FILE_PATH")
        or Path(__file__).resolve().parents[1] / "logs" / "api.log"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    except OSError:
        return
    setattr(fh, _FILE_HANDLER_MARKER, True)
    fh.setLevel(logging.INFO)
    fh.addFilter(SensitiveLogFilter())
    fh.setFormatter(JsonLogFormatter())
    root.addHandler(fh)
