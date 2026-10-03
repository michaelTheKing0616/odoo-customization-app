"""AI_IR_TRACE — dump draft IR after each Generate pass (handoff §4 step 1).

Enable with ``AI_IR_TRACE=1`` (or settings.ai_ir_trace). Writes under
``.cache/ai_ir_trace/`` so order-of-operations for depth / app_bar / scrub /
surface can be confirmed before redesign.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "ai_ir_trace"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def ir_trace_enabled() -> bool:
    env = (os.environ.get("AI_IR_TRACE") or "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    if env in {"0", "false", "no", "off"}:
        return False
    try:
        from app.settings import settings

        return bool(getattr(settings, "ai_ir_trace", False))
    except Exception:  # noqa: BLE001
        return False


def _field_snapshot(model: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in model.get("fields") or []:
        if not isinstance(f, dict):
            continue
        out.append(
            {
                "name": f.get("name"),
                "ttype": f.get("ttype"),
                "relation": f.get("relation"),
                "string": f.get("string"),
                "source": f.get("source"),
            }
        )
    return out


def draft_ir_snapshot(draft: dict[str, Any]) -> dict[str, Any]:
    """Compact IR view for tracing — models/fields/menus/depends only."""
    models = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        models.append(
            {
                "model": m.get("model"),
                "description": m.get("description"),
                "mode": m.get("mode"),
                "source": m.get("source"),
                "is_workflow": m.get("is_workflow"),
                "fields": _field_snapshot(m),
            }
        )
    menus = []
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        menus.append(
            {
                "name": menu.get("name"),
                "technical_name": menu.get("technical_name"),
                "parent": menu.get("parent") or menu.get("parent_menu"),
            }
        )
    return {
        "technical_name": draft.get("technical_name"),
        "display_name": draft.get("display_name"),
        "grain": draft.get("grain"),
        "depends": list(draft.get("depends") or []),
        "models": models,
        "menus": menus,
        "smart_button_count": len(draft.get("smart_buttons") or []),
        "user_prompt": str(draft.get("_user_prompt") or "")[:240],
    }


def trace_ir(
    draft: dict[str, Any],
    *,
    stage: str,
    notes: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Persist a stage dump when enabled. Always logs a one-line summary."""
    snap = draft_ir_snapshot(draft)
    model_ids = [str(m.get("model") or "") for m in snap["models"]]
    field_names: list[str] = []
    for m in snap["models"]:
        for f in m.get("fields") or []:
            n = str(f.get("name") or "")
            if n:
                field_names.append(f"{m.get('model')}.{n}")
    logger.info(
        "ai_ir_trace stage=%s models=%s fields=%s menus=%s",
        stage,
        len(model_ids),
        len(field_names),
        len(snap["menus"]),
    )
    if not ir_trace_enabled():
        return None
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _SLUG_RE.sub("_", (stage or "stage").lower()).strip("_")[:48] or "stage"
    stamp = time.strftime("%Y%m%dT%H%M%S")
    path = _CACHE_DIR / f"{stamp}_{slug}.json"
    payload = {
        "stage": stage,
        "stamp": stamp,
        "notes": list(notes or [])[:80],
        "model_ids": model_ids,
        "field_names": field_names[:200],
        "ir": snap,
        "extra": extra or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("ai_ir_trace_saved path=%s", path)
    return str(path)


__all__ = [
    "draft_ir_snapshot",
    "ir_trace_enabled",
    "trace_ir",
]
