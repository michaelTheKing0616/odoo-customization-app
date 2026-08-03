"""Export/import translations for ModuleSpec artifact lists (CMP-11)."""

from __future__ import annotations

import csv
import io
from typing import Any

from odoo_client.client import OdooClient, OdooClientError


def export_spec_translations_csv(
    client: OdooClient,
    *,
    spec: dict[str, Any],
    lang: str = "fr_FR",
) -> str:
    """CSV for all fields on models declared in a ModuleSpec-like draft."""
    models = [
        str(m["model"])
        for m in (spec.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "model", "name", "lang", "source", "value"])
    for model in models:
        if not client.model_exists(model):
            continue
        try:
            fields = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model)]],
                {
                    "fields": ["name", "field_description", "ttype"],
                    "limit": 2000,
                    "order": "name",
                    "context": {"lang": lang},
                },
            )
            for f in fields:
                w.writerow(
                    [
                        "field",
                        model,
                        f.get("name") or "",
                        lang,
                        f.get("ttype") or "",
                        f.get("field_description") or "",
                    ]
                )
        except OdooClientError:
            continue
    return buf.getvalue()


def import_spec_translations_csv(
    client: OdooClient,
    *,
    rows: list[list[str]],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Import field label rows (same shape as config_ops /translations)."""
    updated = 0
    skipped = 0
    preview: list[dict[str, str]] = []
    for row in rows[1:] if rows else []:
        if len(row) < 6 or row[0] != "field":
            skipped += 1
            continue
        _typ, model, fname, lang, _src, value = row[:6]
        if not model or not fname or not lang:
            skipped += 1
            continue
        preview.append({"model": model, "name": fname, "lang": lang, "value": value})
        if dry_run:
            continue
        try:
            ids = client.execute_kw(
                "ir.model.fields",
                "search",
                [[("model", "=", model), ("name", "=", fname)]],
                {"limit": 1},
            )
            if not ids:
                skipped += 1
                continue
            client.execute_kw(
                "ir.model.fields",
                "write",
                [ids, {"field_description": value}],
                {"context": {"lang": lang}},
            )
            updated += 1
        except OdooClientError:
            skipped += 1
    return {
        "ok": True,
        "dry_run": dry_run,
        "updated": updated,
        "skipped": skipped,
        "preview": preview[:20],
    }
