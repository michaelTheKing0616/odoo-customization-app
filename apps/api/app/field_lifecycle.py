"""TRUST-4 — field lifecycle helpers (deprecate + pre-delete data export)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.settings import settings


class FieldLifecycleError(Exception):
    """User-facing field lifecycle failure."""


@dataclass(frozen=True)
class FieldColumnExport:
    csv_text: str
    row_count: int
    truncated: bool
    model: str
    field_name: str


def _deprecated_name(original: str) -> str:
    base = original.removeprefix("x_")
    return f"x_deprecated_{base}"


def export_field_column_csv(
    client: OdooClient,
    *,
    model: str,
    field_name: str,
) -> FieldColumnExport:
    """Export id → column value CSV for all rows (batched, capped)."""
    if not client.field_exists(model, field_name):
        raise FieldLifecycleError(f"Field {field_name!r} not found on model {model!r}")

    max_rows = max(1, settings.field_export_max_rows)
    batch_size = max(1, settings.field_export_batch_size)
    rows_out: list[dict[str, str]] = []
    offset = 0
    truncated = False

    while offset < max_rows:
        limit = min(batch_size, max_rows - offset)
        try:
            batch = client.execute_kw(
                model,
                "search_read",
                [[]],
                {
                    "fields": ["id", field_name],
                    "limit": limit,
                    "offset": offset,
                    "order": "id asc",
                },
            )
        except OdooClientError as exc:
            raise FieldLifecycleError(f"Column export failed: {exc}") from exc

        if not batch:
            break
        for row in batch:
            rid = row.get("id")
            val = row.get(field_name)
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                val = val[1]
            rows_out.append({"id": str(rid), "value": "" if val is None else str(val)})
        offset += len(batch)
        if len(batch) < limit:
            break
        if offset >= max_rows:
            truncated = True
            break

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id", "value"])
    writer.writeheader()
    writer.writerows(rows_out)
    return FieldColumnExport(
        csv_text=buf.getvalue(),
        row_count=len(rows_out),
        truncated=truncated,
        model=model,
        field_name=field_name,
    )


def deprecate_field(client: OdooClient, field_id: int) -> dict:
    """Rename to x_deprecated_* and mark readonly — keeps column/data."""
    try:
        updated = client.deprecate_field(field_id)
    except OdooClientError as exc:
        raise FieldLifecycleError(str(exc)) from exc
    return updated.model_dump()
