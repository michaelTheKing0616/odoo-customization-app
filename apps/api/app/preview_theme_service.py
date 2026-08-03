"""Store/fetch preview theme on connection verify."""

from __future__ import annotations

import json
from typing import Any

from app.db_models import OdooConnection
from app.palette_extract import extract_theme_from_opener, serialize_theme
from app.routers.preview_proxy import _opener_for_connection


def refresh_preview_theme(row: OdooConnection) -> dict[str, Any]:
    """Best-effort CSS brand extraction; persists JSON on row when successful."""
    try:
        opener, base = _opener_for_connection(row)
        payload = extract_theme_from_opener(opener, base)
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": str(exc), "theme": {}, "preview_vars": {}}
    row.preview_theme_json = serialize_theme(payload)
    return payload


def load_preview_theme(row: OdooConnection) -> dict[str, Any]:
    raw = row.preview_theme_json
    if not raw:
        return {"ok": False, "theme": {}, "preview_vars": {}}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"ok": False, "theme": {}, "preview_vars": {}}
