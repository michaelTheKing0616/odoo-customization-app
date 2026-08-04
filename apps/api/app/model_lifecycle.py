"""TRUST-4 — model delete pre-export (record JSON backup)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.settings import settings


class ModelLifecycleError(Exception):
    """User-facing model lifecycle failure."""


@dataclass(frozen=True)
class ModelRecordsExport:
    json_text: str
    record_count: int
    truncated: bool
    model: str
    overflow_warning: str | None = None


def export_model_records_json(
    client: OdooClient,
    *,
    model: str,
    max_records: int | None = None,
) -> ModelRecordsExport:
    """Export all scalar + m2m id fields for a model before destructive delete."""
    if not client.model_exists(model):
        raise ModelLifecycleError(f"Model {model!r} not found")

    cap = max_records or max(1, settings.field_export_max_rows)
    batch_size = max(1, settings.field_export_batch_size)

    try:
        field_rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", model), ("store", "=", True)]],
            {"fields": ["name", "ttype"], "limit": 500},
        )
    except OdooClientError as exc:
        raise ModelLifecycleError(f"Field introspection failed: {exc}") from exc

    field_names = ["id"]
    for row in field_rows:
        name = str(row.get("name") or "")
        ttype = str(row.get("ttype") or "")
        if name and name != "id" and ttype not in ("one2many", "html"):
            field_names.append(name)

    records: list[dict] = []
    offset = 0
    truncated = False
    while offset < cap:
        limit = min(batch_size, cap - offset)
        try:
            batch = client.execute_kw(
                model,
                "search_read",
                [[]],
                {"fields": field_names, "limit": limit, "offset": offset, "order": "id asc"},
            )
        except OdooClientError as exc:
            raise ModelLifecycleError(f"Record export failed: {exc}") from exc
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
        if len(batch) < limit:
            break
        if offset >= cap:
            truncated = True
            break

    overflow: str | None = None
    if truncated:
        overflow = f"Export capped at {cap} records — database may contain more rows."

    payload = {
        "format": "model_records_json",
        "model": model,
        "record_count": len(records),
        "truncated": truncated,
        "records": records,
    }
    return ModelRecordsExport(
        json_text=json.dumps(payload, indent=2, default=str),
        record_count=len(records),
        truncated=truncated,
        model=model,
        overflow_warning=overflow,
    )


def export_records_by_ids_json(
    client: OdooClient,
    *,
    model: str,
    record_ids: list[int],
    max_records: int | None = None,
) -> ModelRecordsExport:
    """Export specific records before destructive power-ops / targeted deletes."""
    if not record_ids:
        raise ModelLifecycleError("No record ids to export")
    if not client.model_exists(model):
        raise ModelLifecycleError(f"Model {model!r} not found")

    cap = max_records or max(1, settings.field_export_max_rows)
    ids = [int(i) for i in record_ids[:cap]]
    truncated = len(record_ids) > len(ids)

    try:
        field_rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", model), ("store", "=", True)]],
            {"fields": ["name", "ttype"], "limit": 500},
        )
    except OdooClientError as exc:
        raise ModelLifecycleError(f"Field introspection failed: {exc}") from exc

    field_names = ["id"]
    for row in field_rows:
        name = str(row.get("name") or "")
        ttype = str(row.get("ttype") or "")
        if name and name != "id" and ttype not in ("one2many", "html"):
            field_names.append(name)

    try:
        records = client.execute_kw(
            model,
            "read",
            [ids],
            {"fields": field_names},
        )
    except OdooClientError as exc:
        raise ModelLifecycleError(f"Record export failed: {exc}") from exc

    overflow: str | None = None
    if truncated:
        overflow = f"Export capped at {cap} of {len(record_ids)} targeted records."

    payload = {
        "format": "model_records_json",
        "model": model,
        "record_count": len(records),
        "truncated": truncated,
        "record_ids": ids,
        "records": records,
    }
    return ModelRecordsExport(
        json_text=json.dumps(payload, indent=2, default=str),
        record_count=len(records),
        truncated=truncated,
        model=model,
        overflow_warning=overflow,
    )
