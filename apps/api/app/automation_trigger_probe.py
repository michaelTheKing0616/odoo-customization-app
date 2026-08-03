"""Probe automation trigger availability per Odoo major (CMP-3 §7)."""

from __future__ import annotations

from typing import Any

from odoo_client.client import OdooClient
from odoo_client.compat import parse_major

# Conservative fallback when live probe unavailable (experimental 16 noted in ERRORS).
TRIGGER_PROBE_FALLBACK: dict[int, dict[str, bool]] = {
    16: {"on_webhook": False, "on_change": False},
    17: {"on_webhook": True, "on_change": False},
    18: {"on_webhook": True, "on_change": True},
    19: {"on_webhook": True, "on_change": True},
}


def _selection_values(fields_get: dict[str, Any], field: str) -> set[str]:
    meta = fields_get.get(field) or {}
    sel = meta.get("selection")
    if not sel:
        return set()
    out: set[str] = set()
    for item in sel:
        if isinstance(item, (list, tuple)) and item:
            out.add(str(item[0]))
    return out


def probe_automation_triggers(client: OdooClient) -> dict[str, Any]:
    """Return supported triggers + probe metadata for this connection."""
    major = int(getattr(client.capabilities, "major", 19) or 19)
    source = "fallback"
    triggers: set[str] = set()
    has_on_change_fields = False

    try:
        if client.model_exists("base.automation"):
            fg = client.execute_kw(
                "base.automation",
                "fields_get",
                [],
                {"attributes": ["selection", "type"]},
            )
            triggers = _selection_values(fg, "trigger")
            has_on_change_fields = "on_change_field_ids" in fg
            source = "live"
    except Exception:  # noqa: BLE001 — fall back to matrix
        pass

    if not triggers:
        fb = TRIGGER_PROBE_FALLBACK.get(major, TRIGGER_PROBE_FALLBACK[19])
        triggers = {t for t, ok in (
            ("on_webhook", fb["on_webhook"]),
            ("on_change", fb["on_change"]),
        ) if ok}
        # Include safe triggers always offered in UI
        triggers.update(
            {
                "on_create",
                "on_write",
                "on_create_or_write",
                "on_unlink",
                "on_archive",
                "on_unarchive",
                "on_time",
                "on_time_created",
                "on_time_updated",
                "on_message_received",
                "on_message_sent",
            }
        )
        if fb["on_webhook"]:
            triggers.add("on_webhook")
        if fb["on_change"]:
            triggers.add("on_change")

    row = {
        "major": major,
        "source": source,
        "on_webhook": "on_webhook" in triggers,
        "on_change": "on_change" in triggers,
        "on_change_field_ids": has_on_change_fields,
        "trigger_count": len(triggers),
    }
    return {
        "major": major,
        "source": source,
        "supported_triggers": sorted(triggers),
        "probe_table": [row],
    }


def probe_table_for_major(major: int) -> list[dict[str, Any]]:
    """Fixture probe rows for tests without live Odoo."""
    fb = TRIGGER_PROBE_FALLBACK.get(major, TRIGGER_PROBE_FALLBACK[19])
    return [
        {
            "major": major,
            "source": "fixture",
            "on_webhook": fb["on_webhook"],
            "on_change": fb["on_change"],
            "on_change_field_ids": fb["on_change"],
        }
    ]
