"""Stage 3 — map rows to live schema + cross-reference (ING-5)."""

from __future__ import annotations

import re
from typing import Any

from odoo_client import OdooClient

from app.bulk_suite.dedupe import DedupeValidationError, scan_duplicates
from app.data_import import _field_meta
from app.ingest.coa_align import align_coa_table
from app.ingest.constants import (
    EMPLOYEE_ORG_FIELDS,
    FINANCIAL_DOC_TYPES,
    NATURAL_KEY_FIELDS,
)
from app.ingest.inventory import validate_inventory_table
from app.ingest.opening_balance import validate_opening_tb_table
from app.ingest.schema import IngestBatch, IngestGap, IngestRef, IngestTable
from app.ingest.vat_check import validate_partner_vats


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
            name = row.values.get("name") or row.raw.get("name")
            if name:
                bucket.setdefault(f"name={_norm_key(str(name))}", row.values)
            code = row.values.get("default_code") or row.raw.get("default_code")
            if code:
                bucket.setdefault(f"default_code={_norm_key(str(code))}", row.values)
    return out


def _uom_field_names(client: OdooClient) -> set[str]:
    """Odoo ≤18 uses category_id; Odoo 19+ uses relative_uom_id family tree."""
    cache_attr = "_ingest_uom_field_names"
    cached = getattr(client, cache_attr, None)
    if isinstance(cached, set):
        return cached
    names: set[str] = set()
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", "uom.uom"), ("name", "in", ["category_id", "relative_uom_id"])]],
            {"fields": ["name"]},
        )
        names = {str(r["name"]) for r in rows or []}
    except Exception:
        names = set()
    setattr(client, cache_attr, names)
    return names


def _resolve_uom(
    client: OdooClient,
    name: str,
    *,
    category_id: int | None = None,
) -> int | None:
    """Resolve UoM by name; optionally prefer same category (≤18) or relative family (19+)."""
    if not name or not client.model_exists("uom.uom"):
        return None
    uom_fields = _uom_field_names(client)
    read_fields = ["id", "name"]
    if "category_id" in uom_fields:
        read_fields.append("category_id")
    if "relative_uom_id" in uom_fields:
        read_fields.append("relative_uom_id")

    domain: list[Any] = [("name", "ilike", name.strip())]
    if category_id is not None and "category_id" in uom_fields:
        domain = ["&", ("category_id", "=", category_id), ("name", "ilike", name.strip())]
    elif category_id is not None and "relative_uom_id" in uom_fields:
        # Family root id: match root itself or children pointing at it
        domain = [
            "&",
            "|",
            ("id", "=", category_id),
            ("relative_uom_id", "=", category_id),
            ("name", "ilike", name.strip()),
        ]

    rows = client.execute_kw(
        "uom.uom",
        "search_read",
        [domain],
        {"fields": read_fields, "limit": 8},
    )
    if not rows and category_id is not None:
        rows = client.execute_kw(
            "uom.uom",
            "search_read",
            [[("name", "ilike", name.strip())]],
            {"fields": read_fields, "limit": 8},
        )
    if not rows:
        return None
    exact = [r for r in rows if _norm_key(str(r.get("name") or "")) == _norm_key(name)]
    pool = exact or rows
    if category_id is not None and "category_id" in uom_fields:
        same = [
            r
            for r in pool
            if isinstance(r.get("category_id"), (list, tuple))
            and int(r["category_id"][0]) == category_id
        ]
        if same:
            pool = same
    elif category_id is not None and "relative_uom_id" in uom_fields:
        same = []
        for r in pool:
            rid = r.get("relative_uom_id")
            if int(r["id"]) == category_id:
                same.append(r)
            elif isinstance(rid, (list, tuple)) and rid and int(rid[0]) == category_id:
                same.append(r)
            elif rid in (False, None) and int(r["id"]) == category_id:
                same.append(r)
        if same:
            pool = same
    if len(pool) == 1:
        return int(pool[0]["id"])
    # Prefer exact name match among pool
    if len(exact) == 1:
        return int(exact[0]["id"])
    return None


def _uom_category_hint(
    client: OdooClient, table: IngestTable, row_values: dict[str, Any]
) -> int | None:
    """Infer UoM family from product uom — category_id (≤18) or relative root (19+)."""
    _ = table
    uom_fields = _uom_field_names(client)
    for key in ("product_id", "product_tmpl_id"):
        pid = row_values.get(key)
        if not isinstance(pid, int):
            continue
        model = "product.product" if key == "product_id" else "product.template"
        if not client.model_exists(model):
            continue
        rows = client.execute_kw(
            model,
            "read",
            [[pid]],
            {"fields": ["uom_id"]},
        )
        if not rows:
            continue
        uom = rows[0].get("uom_id")
        if not (isinstance(uom, (list, tuple)) and uom):
            continue
        uom_id = int(uom[0])
        want = [f for f in ("category_id", "relative_uom_id") if f in uom_fields]
        if not want:
            return None
        urows = client.execute_kw(
            "uom.uom",
            "read",
            [[uom_id]],
            {"fields": want},
        )
        if not urows:
            continue
        if "category_id" in uom_fields:
            cat = urows[0].get("category_id")
            if isinstance(cat, (list, tuple)) and cat:
                return int(cat[0])
        if "relative_uom_id" in uom_fields:
            rel = urows[0].get("relative_uom_id")
            if isinstance(rel, (list, tuple)) and rel:
                return int(rel[0])
            # Root UoM — use itself as family id
            return uom_id
    return None


def _live_resolve_m2o(
    client: OdooClient, relation: str, raw_val: str
) -> int | None:
    if not raw_val or not client.model_exists(relation):
        return None
    if raw_val.isdigit():
        return int(raw_val)
    domains: list[list[Any]] = []
    if relation in {"product.product", "product.template"}:
        domains = [
            [("default_code", "=", raw_val)],
            [("barcode", "=", raw_val)],
            [("name", "ilike", raw_val)],
        ]
    elif relation == "res.partner":
        domains = [
            [("email", "=ilike", raw_val)],
            [("vat", "=", raw_val)],
            [("name", "ilike", raw_val)],
        ]
    elif relation == "account.account":
        domains = [[("code", "=", raw_val)], [("code", "ilike", raw_val)]]
    elif relation in {"hr.department", "hr.job"}:
        domains = [[("name", "ilike", raw_val)]]
    elif relation == "hr.employee":
        domains = [
            [("work_email", "=ilike", raw_val)],
            [("name", "ilike", raw_val)],
        ]
    elif relation == "mrp.bom":
        # BoM has no name — resolve via finished product SKU/name → product_tmpl_id
        tmpl_id = _live_resolve_m2o(client, "product.template", raw_val)
        if tmpl_id is None:
            return None
        rows = client.execute_kw(
            "mrp.bom",
            "search_read",
            [[("product_tmpl_id", "=", tmpl_id)]],
            {"fields": ["id"], "limit": 2},
        )
        if len(rows) == 1:
            return int(rows[0]["id"])
        return None
    else:
        domains = [[("name", "ilike", raw_val)]]
    for domain in domains:
        try:
            rows = client.execute_kw(
                relation,
                "search_read",
                [domain],
                {"fields": ["id"], "limit": 2},
            )
        except Exception:
            continue
        if len(rows) == 1:
            return int(rows[0]["id"])
    return None


def _strip_employee_non_org(table: IngestTable) -> list[str]:
    if table.doc_type != "employee_roster" and table.model != "hr.employee":
        return []
    notes: list[str] = []
    drop_map = {
        h: f
        for h, f in table.mapping.items()
        if f not in EMPLOYEE_ORG_FIELDS and f not in {"name", "work_email"}
    }
    if drop_map:
        for h in drop_map:
            table.mapping.pop(h, None)
        notes.append(
            f"stripped non-org employee fields: {', '.join(sorted(drop_map.values()))}"
        )
    for row in table.rows:
        banned = [k for k in list(row.values) if k not in EMPLOYEE_ORG_FIELDS]
        for k in banned:
            row.values.pop(k, None)
            row.flags.append(f"stripped_payroll_field:{k}")
    return notes


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

    warnings.extend(_strip_employee_non_org(table))

    # Soft-check required fields — many Odoo required fields have server defaults
    # (uom_id, company_id). Hard-block only when no mapping AND no value AND char/text.
    mapped_fields = set(table.mapping.values())
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
                row.flags.append(f"missing_required:{req}")
                # Only hard-block when the operator mapped this field but left it empty.
                # Unmapped required fields rely on Odoo server defaults.
                severity = "block" if req in mapped_fields else "warn"
                gaps.append(
                    IngestGap(
                        model=table.model,
                        field=req,
                        value="",
                        message=f"Required field {req} missing on row {row.source_ref or '?'}",
                        severity=severity,  # type: ignore[arg-type]
                    )
                )

    for field_name, info in field_meta.items():
        if str(info.get("ttype")) != "many2one":
            continue
        relation = str(info.get("relation") or "")
        if not relation:
            continue
        headers = [h for h, f in table.mapping.items() if f == field_name]
        # Also accept already-mapped values keys
        for row in table.rows:
            raw_candidates: list[str] = []
            for h in headers:
                raw_candidates.append(str(row.raw.get(h, "") or "").strip())
            if field_name in row.values and not isinstance(row.values[field_name], int):
                raw_candidates.append(str(row.values[field_name]).strip())
            # BoM common aliases
            if field_name in {"product_tmpl_id", "product_id"} and not any(raw_candidates):
                for alias in ("product_code", "default_code", "sku", "product"):
                    if row.raw.get(alias):
                        raw_candidates.append(str(row.raw[alias]).strip())
                    if row.values.get(alias):
                        raw_candidates.append(str(row.values[alias]).strip())
            for raw_val in raw_candidates:
                if not raw_val:
                    continue
                batch_hit = batch_index.get(relation, {})
                found_in_batch = any(
                    _norm_key(str(v.get("name", ""))) == _norm_key(raw_val)
                    or _norm_key(str(v.get("default_code", ""))) == _norm_key(raw_val)
                    for v in batch_hit.values()
                )
                live_id = None if found_in_batch else _live_resolve_m2o(
                    client, relation, raw_val
                )
                resolved = found_in_batch or live_id is not None
                if live_id is not None:
                    row.values[field_name] = live_id
                ref = IngestRef(
                    from_table_id=table.id,
                    field=field_name,
                    to_model=relation,
                    to_value=raw_val,
                    resolved=resolved,
                    resolved_id=live_id,
                    note=None
                    if resolved
                    else f"Unresolved {relation} for {raw_val!r}",
                )
                refs.append(ref)
                if not resolved:
                    row.flags.append(f"unresolved_m2o:{field_name}")
                    gaps.append(
                        IngestGap(
                            model=table.model,
                            field=field_name,
                            value=raw_val,
                            message=f"No live/batch match for {relation}={raw_val!r}",
                        )
                    )
                break

    uom_headers = [
        h
        for h, f in table.mapping.items()
        if f in {"uom_id", "uom_po_id", "product_uom_id"}
    ]
    for row in table.rows:
        cat_hint = _uom_category_hint(client, table, row.values)
        for h in uom_headers:
            raw_uom = str(
                row.raw.get(h, "")
                or row.values.get(table.mapping.get(h, ""), "")
                or ""
            ).strip()
            if not raw_uom:
                continue
            if raw_uom.isdigit():
                row.values[table.mapping.get(h, h)] = int(raw_uom)
                continue
            uid = _resolve_uom(client, raw_uom, category_id=cat_hint)
            if uid is None:
                gaps.append(
                    IngestGap(
                        model=table.model,
                        field=table.mapping.get(h, h),
                        value=raw_uom,
                        message=(
                            f"UoM {raw_uom!r} not found on instance"
                            + (f" (category_id={cat_hint})" if cat_hint else "")
                        ),
                    )
                )
                row.flags.append(f"uom_missing:{raw_uom}")
            else:
                target = table.mapping.get(h, h)
                row.values[target] = uid

    warnings.extend(_apply_bom_defaults(client, table))

    # Write resolved IDs back onto mapped headers so data_import._row_to_vals
    # (which reads headers, not values) commits numeric m2o ids.
    for row in table.rows:
        for header, field_name in table.mapping.items():
            val = row.values.get(field_name)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                row.raw[header] = str(int(val) if float(val).is_integer() else val)
            elif isinstance(val, str) and val and header not in row.raw:
                row.raw[header] = val

    return refs, gaps, warnings


def _apply_bom_defaults(client: OdooClient, table: IngestTable) -> list[str]:
    """Fill Odoo 19 required mrp.bom selections + UoM when extract omitted them."""
    if table.model != "mrp.bom":
        return []
    notes: list[str] = []
    defaults = {
        "type": "normal",
        "consumption": "warning",
        "ready_to_produce": "all_available",
    }
    for key, val in defaults.items():
        if key not in table.mapping.values():
            table.mapping[key] = key
    if "product_uom_id" not in table.mapping.values():
        table.mapping["product_uom"] = "product_uom_id"

    for row in table.rows:
        if "product_qty" not in row.values:
            q = row.raw.get("quantity") or row.raw.get("product_qty") or "1"
            try:
                row.values["product_qty"] = float(str(q).replace(",", ""))
            except ValueError:
                row.values["product_qty"] = 1.0
            row.raw.setdefault("quantity", str(row.values["product_qty"]))
        for key, val in defaults.items():
            row.values.setdefault(key, val)
            row.raw.setdefault(key, val)
        if "product_uom_id" not in row.values:
            tmpl = row.values.get("product_tmpl_id")
            uom_id = None
            if isinstance(tmpl, int) and client.model_exists("product.template"):
                rows = client.execute_kw(
                    "product.template",
                    "read",
                    [[tmpl]],
                    {"fields": ["uom_id"]},
                )
                if rows and isinstance(rows[0].get("uom_id"), (list, tuple)):
                    uom_id = int(rows[0]["uom_id"][0])
            if uom_id is None:
                uom_id = _resolve_uom(client, "Units")
            if uom_id is not None:
                row.values["product_uom_id"] = uom_id
                row.raw["product_uom"] = str(uom_id)
    notes.append("applied mrp.bom defaults (type/consumption/ready_to_produce/uom)")
    return notes


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
    warnings: list[str] = []
    for mode in ("exact", "fuzzy"):
        try:
            scan = scan_duplicates(
                client,
                model=table.model,
                match_fields=table.natural_key_fields,
                mode=mode,  # type: ignore[arg-type]
                limit=500,
            )
        except (DedupeValidationError, TypeError, ValueError):
            continue
        if not scan.groups:
            continue
        warnings.extend(
            f"live duplicate group ({mode}) on {table.model} ({g.group_key}): "
            f"{len(g.records)} records"
            for g in scan.groups[:5]
        )
    return warnings


def map_batch(
    client: OdooClient,
    batch: IngestBatch,
    *,
    allow_coa_as_is: bool = False,
) -> IngestBatch:
    """Enrich batch with refs/gaps using live field meta + batch-internal index."""
    index = _batch_index(batch)
    all_refs: list[IngestRef] = []
    all_gaps: list[IngestGap] = []
    meta_cache: dict[str, dict[str, dict[str, Any]]] = {}
    batch.meta = dict(batch.meta or {})

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

        if table.doc_type == "coa" or table.model == "account.account":
            cgaps, cwarns, summary = align_coa_table(
                client,
                table,
                allow_as_is=allow_coa_as_is or batch.allow_coa_as_is,
                auto_remap=bool(batch.meta.get("coa_auto_remap")),
            )
            all_gaps.extend(cgaps)
            table.warnings.extend(cwarns)
            batch.meta["coa_alignment"] = summary

        if table.doc_type == "opening_trial_balance":
            tgaps, twarns = validate_opening_tb_table(client, table)
            all_gaps.extend(tgaps)
            table.warnings.extend(twarns)

        if table.doc_type == "inventory_count":
            igaps, iwarns = validate_inventory_table(client, table)
            all_gaps.extend(igaps)
            table.warnings.extend(iwarns)

        if table.model == "res.partner":
            vgaps, vwarns = validate_partner_vats(client, table)
            all_gaps.extend(vgaps)
            table.warnings.extend(vwarns)

    financial = any(f.doc_type in FINANCIAL_DOC_TYPES for f in batch.files)
    if financial and "coa_alignment" not in (batch.meta or {}):
        from app.invoicing_l10n import detect_l10n

        l10n = detect_l10n(client)
        if not l10n.get("ok"):
            batch.warnings.append(str(l10n.get("message") or "Fiscal localization not detected"))

    batch.refs = all_refs
    batch.gaps = all_gaps
    return batch
