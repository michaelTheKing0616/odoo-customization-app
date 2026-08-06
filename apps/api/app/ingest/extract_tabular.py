"""Stage 2 — tabular extraction wired to data_import (ING-3)."""

from __future__ import annotations

import uuid

from app.data_import import parse_tabular, suggest_mapping
from app.ingest.constants import (
    DOC_TYPE_PRIMARY_MODEL,
    NATURAL_KEY_FIELDS,
    WAGE_LIKE_HEADERS,
)
from app.ingest.schema import DocType, IngestRow, IngestTable


def _header_set(headers: list[str]) -> set[str]:
    return {h.strip().lower().replace(" ", "_") for h in headers}


def _strip_wage_columns(
    headers: list[str],
    rows: list[dict[str, str]],
) -> tuple[list[str], list[dict[str, str]], list[str]]:
    low = _header_set(headers)
    drop = [h for h in headers if h.strip().lower().replace(" ", "_") in WAGE_LIKE_HEADERS]
    if not drop:
        return headers, rows, []
    keep = [h for h in headers if h not in drop]
    cleaned: list[dict[str, str]] = []
    for row in rows:
        cleaned.append({k: v for k, v in row.items() if k in keep})
    warnings = [f"stripped payroll/compensation columns: {', '.join(drop)}"]
    return keep, cleaned, warnings


def extract_tabular_bytes(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
) -> IngestTable:
    headers, rows = parse_tabular(raw, filename)
    warnings: list[str] = []
    if doc_type == "employee_roster":
        headers, rows, wage_warn = _strip_wage_columns(headers, rows)
        warnings.extend(wage_warn)

    model = DOC_TYPE_PRIMARY_MODEL.get(doc_type, "res.partner")
    if doc_type == "price_list":
        low_headers = _header_set(headers)
        if not (low_headers & {"min_quantity", "qty", "quantity", "tier_qty"}):
            model = "product.template"
    if doc_type == "vendor_list":
        for row in rows:
            if "is_company" not in row and "company_type" not in row:
                row.setdefault("is_company", "true")

    mapping = suggest_mapping(model, headers)
    natural = list(NATURAL_KEY_FIELDS.get(model, []))
    ingest_rows = [
        IngestRow(
            values=dict(row),
            raw=dict(row),
            confidence=1.0,
            source_ref=f"{filename}:{idx}",
        )
        for idx, row in enumerate(rows, start=1)
    ]
    return IngestTable(
        id=str(uuid.uuid4()),
        model=model,
        doc_type=doc_type,
        rows=ingest_rows,
        mapping=mapping,
        natural_key_fields=natural,
        mode="upsert",
        warnings=warnings,
    )


def _flat_bom_to_payload(rows: list[dict[str, str]]) -> dict:
    """Group flat product_code/component_code rows into nested BoM payload."""
    grouped: dict[str, dict] = {}
    for row in rows:
        parent = (
            row.get("product_code")
            or row.get("parent_product")
            or row.get("assembly")
            or row.get("finished_product")
            or ""
        ).strip()
        comp = (
            row.get("component_code")
            or row.get("component")
            or row.get("part")
            or row.get("material")
            or ""
        ).strip()
        if not parent or not comp:
            continue
        bucket = grouped.setdefault(
            parent,
            {
                "product_code": parent,
                "quantity": float(row.get("product_qty") or row.get("qty") or 1) or 1,
                "lines": [],
            },
        )
        bucket["lines"].append(
            {
                "component_code": comp,
                "quantity": float(row.get("quantity") or row.get("qty") or 1) or 1,
                "uom": row.get("uom") or row.get("product_uom") or "",
                "is_subassembly": str(row.get("is_subassembly") or "").lower()
                in {"1", "true", "yes"},
            }
        )
    return {"boms": list(grouped.values())}


def extract_tabular_file(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
) -> list[IngestTable]:
    if doc_type == "bom":
        headers, rows = parse_tabular(raw, filename)
        _ = headers
        from app.ingest.extract_pdf import _tables_from_bom_payload

        tables, _refs = _tables_from_bom_payload(
            _flat_bom_to_payload(rows), filename=filename
        )
        if tables:
            return tables
    return [extract_tabular_bytes(filename=filename, raw=raw, doc_type=doc_type)]
