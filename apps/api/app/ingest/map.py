"""Stage 3 — map rows to live schema + cross-reference (ING-5)."""

from __future__ import annotations

import re
from typing import Any

from odoo_client import OdooClient

from app.bulk_suite.dedupe import DedupeValidationError, scan_duplicates
from app.data_import import _field_meta
from app.ingest.constants import FINANCIAL_DOC_TYPES, NATURAL_KEY_FIELDS
from app.ingest.schema import IngestBatch, IngestGap, IngestRef, IngestTable
from app.invoicing_l10n import detect_l10n


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _batch_index(batch: IngestBatch) -> dict[str, dict[str, dict[str, Any]]]:
    """model -> normalized natural key -> row values dict."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for table in batch.tables:
        keys = table.natural_key_fields or NATURAL_KEY_FIELDS.get(table.model, [])
        if not keys:
            continue
        bucket = out.setdefault(table.model, {})
        for row in table.rows:
            parts: list[str] = []
            for k in keys:
                v = row.values.get(k) or row.raw.get(k, "")
                if v:
                    parts.append(f"{k}={_norm_key(str(v))}")
            if parts:
                bucket["|".join(parts)] = row.values
    return out


def _resolve_uom(client: OdooClient, name: str) -> int | None:
    if not name or not client.model_exists("uom.uom"):
        return None
    rows = client.execute_kw(
        "uom.uom",
        "search_read",
        [[("name", "ilike", name.strip())]],
        {"fields": ["id", "name"], "limit": 2},
    )
    if len(rows) == 1:
        return int(rows[0]["id"])
    return None


def map_table(
    client: OdooClient,
    table: IngestTable,
    *,
    batch_index: dict[str, dict[str, dict[str, Any]]],
    meta: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[IngestRef], list[IngestGap], list[str]]:
    refs: list[IngestRef] = []
    gaps: list[IngestGap] = []
    warnings: list[str] = []
    field_meta = meta or _field_meta(client, table.model)

    required = [n for n, info in field_meta.items() if info.get("required")]
    for row in table.rows:
        for req in required:
            mapped_headers = [h for h, f in table.mapping.items() if f == req]
            val = ""
            for h in mapped_headers:
                val = str(row.raw.get(h, "") or row.values.get(req, ""))
                if val:
                    break
            if not val and req not in row.values:
                gaps.append(
                    IngestGap(
                        model=table.model,
                        field=req,
                        value="",
                        message=f"Required field {req} missing on row {row.source_ref or '?'}",
                    )
                )
                row.flags.append(f"missing_required:{req}")

    for field_name, info in field_meta.items():
        if str(info.get("ttype")) != "many2one":
            continue
        relation = str(info.get("relation") or "")
        if not relation:
            continue
        headers = [h for h, f in table.mapping.items() if f == field_name]
        for row in table.rows:
            for h in headers:
                raw_val = str(row.raw.get(h, "") or "").strip()
                if not raw_val:
                    continue
                batch_hit = batch_index.get(relation, {})
                found_in_batch = any(
                    _norm_key(str(v.get("name", ""))) == _norm_key(raw_val)
                    for v in batch_hit.values()
                )
                ref = IngestRef(
                    from_table_id=table.id,
                    field=field_name,
                    to_model=relation,
                    to_value=raw_val,
                    resolved=found_in_batch,
                    note=None if found_in_batch else f"Awaiting {relation} match",
                )
                refs.append(ref)
                if not found_in_batch:
                    row.flags.append(f"unresolved_m2o:{field_name}")

    uom_headers = [h for h, f in table.mapping.items() if f in {"uom_id", "uom_po_id"}]
    for row in table.rows:
        for h in uom_headers:
            raw_uom = str(row.raw.get(h, "") or "").strip()
            if not raw_uom:
                continue
            if raw_uom.isdigit():
                continue
            uid = _resolve_uom(client, raw_uom)
            if uid is None:
                gaps.append(
                    IngestGap(
                        model=table.model,
                        field=table.mapping.get(h, h),
                        value=raw_uom,
                        message=f"UoM {raw_uom!r} not found on instance",
                    )
                )
                row.flags.append(f"uom_missing:{raw_uom}")
            else:
                target = table.mapping.get(h, h)
                row.values[target] = uid

    return refs, gaps, warnings


def _batch_duplicate_warnings(table: IngestTable) -> list[str]:
    if not table.natural_key_fields:
        return []
    seen: dict[str, int] = {}
    warnings: list[str] = []
    for row in table.rows:
        parts = []
        for k in table.natural_key_fields:
            v = row.raw.get(k) or row.values.get(k, "")
            if v:
                parts.append(f"{k}={_norm_key(str(v))}")
        if not parts:
            continue
        key = "|".join(parts)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            warnings.append(f"batch duplicate natural key in {table.model}: {key}")
            row.flags.append("batch_duplicate")
    return warnings


def _live_dedupe_warnings(client: OdooClient, table: IngestTable) -> list[str]:
    if not table.natural_key_fields or not client.model_exists(table.model):
        return []
    try:
        scan = scan_duplicates(
            client,
            model=table.model,
            match_fields=table.natural_key_fields,
            mode="exact",
            limit=500,
        )
    except DedupeValidationError:
        return []
    if not scan.groups:
        return []
    return [
        f"live duplicate group on {table.model} ({g.group_key}): {len(g.records)} records"
        for g in scan.groups[:5]
    ]


def map_batch(client: OdooClient, batch: IngestBatch) -> IngestBatch:
    """Enrich batch with refs/gaps using live field meta + batch-internal index."""
    index = _batch_index(batch)
    all_refs: list[IngestRef] = []
    all_gaps: list[IngestGap] = []
    meta_cache: dict[str, dict[str, dict[str, Any]]] = {}

    for table in batch.tables:
        if table.model not in meta_cache:
            if client.model_exists(table.model):
                meta_cache[table.model] = _field_meta(client, table.model)
            else:
                meta_cache[table.model] = {}
                batch.warnings.append(f"Model {table.model} not found on Odoo instance")
        refs, gaps, warns = map_table(
            client,
            table,
            batch_index=index,
            meta=meta_cache[table.model],
        )
        all_refs.extend(refs)
        all_gaps.extend(gaps)
        table.warnings.extend(warns)
        table.warnings.extend(_batch_duplicate_warnings(table))
        table.warnings.extend(_live_dedupe_warnings(client, table))

    financial = any(f.doc_type in FINANCIAL_DOC_TYPES for f in batch.files)
    if financial:
        l10n = detect_l10n(client)
        if not l10n.get("ok"):
            batch.warnings.append(str(l10n.get("message") or "Fiscal localization not detected"))

    batch.refs = all_refs
    batch.gaps = all_gaps
    return batch
