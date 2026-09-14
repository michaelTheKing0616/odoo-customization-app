"""ir.ui.menu visibility-group helpers (Odoo 17/18 groups_id vs 19 group_ids)."""

from __future__ import annotations

from typing import Any


def menu_group_m2m_field(client: Any) -> str | None:
    """Odoo 19 renamed ir.ui.menu.groups_id → group_ids (17/18 keep groups_id)."""
    try:
        if client.field_exists("ir.ui.menu", "group_ids"):
            return "group_ids"
        if client.field_exists("ir.ui.menu", "groups_id"):
            return "groups_id"
    except Exception:  # noqa: BLE001 — probe best-effort
        return None
    return None


def m2m_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            out.append(item)
            continue
        if isinstance(item, (list, tuple)) and item:
            try:
                out.append(int(item[0]))
            except (TypeError, ValueError):
                continue
    return out
