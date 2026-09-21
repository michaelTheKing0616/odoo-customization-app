"""Per-connection App Studio preferences (Flash AST enrich toggle, etc.).

Stored inside OdooConnection.ingest_prefs_json under the ``studio`` key so we
do not need a schema migration. Env AI_INTENT_LLM remains the server
default/override when no explicit preference is stored.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import OdooConnection


def _parse(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get_studio_prefs(row: OdooConnection) -> dict[str, Any]:
    """Return studio prefs. ``flash_ast_enrich`` is bool | None (None = follow env)."""
    root = _parse(getattr(row, "ingest_prefs_json", None))
    studio = root.get("studio") if isinstance(root.get("studio"), dict) else {}
    enrich = studio.get("flash_ast_enrich", None)
    if enrich is not None:
        enrich = bool(enrich)
    return {
        "flash_ast_enrich": enrich,
        # Honest label for UI
        "flash_ast_enrich_label": "Enrich Must-do with Flash",
        "flash_ast_enrich_help": (
            "On: optional Flash AST fill (same path as AI_INTENT_LLM). "
            "Off: deterministic floor only. When unset, the server AI_INTENT_LLM "
            "default applies (auto unless the env sets on/off)."
        ),
    }


def set_studio_prefs(
    db: Session,
    row: OdooConnection,
    *,
    flash_ast_enrich: bool | None = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    root = _parse(getattr(row, "ingest_prefs_json", None))
    studio = dict(root.get("studio") or {}) if isinstance(root.get("studio"), dict) else {}
    if flash_ast_enrich is not ...:
        if flash_ast_enrich is None:
            studio.pop("flash_ast_enrich", None)
        else:
            studio["flash_ast_enrich"] = bool(flash_ast_enrich)
    root["studio"] = studio
    row.ingest_prefs_json = json.dumps(root)
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_studio_prefs(row)


def resolve_flash_ast_enrich(
    *,
    connection_pref: bool | None = None,
    request_override: bool | None = None,
) -> bool | None:
    """Return explicit True/False override for intent_llm_enabled, or None to follow env.

    Request body wins over stored connection preference.
    """
    if request_override is not None:
        return bool(request_override)
    if connection_pref is not None:
        return bool(connection_pref)
    return None


__all__ = [
    "get_studio_prefs",
    "resolve_flash_ast_enrich",
    "set_studio_prefs",
]
