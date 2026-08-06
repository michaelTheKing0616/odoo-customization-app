"""Per-connection ingest preferences (notify mode, CoA defaults)."""

from __future__ import annotations

import json
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db_models import OdooConnection
from app.ingest.constants import DEFAULT_NOTIFY_MODE

NotifyMode = Literal["batch_summary", "individual"]


def _parse(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get_ingest_prefs(row: OdooConnection) -> dict[str, Any]:
    prefs = _parse(getattr(row, "ingest_prefs_json", None))
    mode = prefs.get("notify_mode") or DEFAULT_NOTIFY_MODE
    if mode not in {"batch_summary", "individual"}:
        mode = DEFAULT_NOTIFY_MODE
    return {
        "notify_mode": mode,
        "allow_coa_as_is_default": bool(prefs.get("allow_coa_as_is_default")),
        "coa_auto_remap_default": bool(prefs.get("coa_auto_remap_default")),
    }


def set_ingest_prefs(
    db: Session,
    row: OdooConnection,
    *,
    notify_mode: str | None = None,
    allow_coa_as_is_default: bool | None = None,
    coa_auto_remap_default: bool | None = None,
) -> dict[str, Any]:
    prefs = _parse(getattr(row, "ingest_prefs_json", None))
    if notify_mode in {"batch_summary", "individual"}:
        prefs["notify_mode"] = notify_mode
    if allow_coa_as_is_default is not None:
        prefs["allow_coa_as_is_default"] = bool(allow_coa_as_is_default)
    if coa_auto_remap_default is not None:
        prefs["coa_auto_remap_default"] = bool(coa_auto_remap_default)
    row.ingest_prefs_json = json.dumps(prefs)
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_ingest_prefs(row)


__all__ = ["get_ingest_prefs", "set_ingest_prefs"]
