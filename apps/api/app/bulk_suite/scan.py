"""CMP-9 scan-to-field helpers (find + write via mass-edit policy)."""

from __future__ import annotations

from typing import Any

from odoo_client.client import OdooClient


def find_records_by_field(
    client: OdooClient,
    *,
    model: str,
    field: str,
    value: str,
    limit: int = 20,
) -> dict[str, Any]:
    if not model.startswith("x_"):
        raise ValueError("Scan find requires custom x_* model")
    if not field.startswith("x_"):
        raise ValueError("Scan find requires custom x_* field")
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError("Scanned value is empty")

    rows = client.execute_kw(
        model,
        "search_read",
        [[(field, "=", cleaned)]],
        {"fields": ["id", field, "display_name"], "limit": limit},
    )
    return {
        "ok": True,
        "model": model,
        "field": field,
        "value": cleaned,
        "count": len(rows),
        "records": [
            {
                "id": int(r["id"]),
                "display_name": r.get("display_name"),
                field: r.get(field),
            }
            for r in rows
        ],
    }
