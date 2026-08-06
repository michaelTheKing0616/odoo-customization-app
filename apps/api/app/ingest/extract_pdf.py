"""PDF text extraction + LLM structured parse (ING-4). Vision deferred to extract_vision.py."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.ingest.constants import NATURAL_KEY_FIELDS, WAGE_LIKE_HEADERS
from app.ingest.extract_tabular import _strip_wage_columns
from app.ingest.layout_cache import get_cached_extraction, save_cached_extraction
from app.ingest.schema import DocType, IngestRef, IngestRow, IngestTable
from app.llm_provider import LLMError, get_llm_provider
from app.settings import settings

_PRICE_REQUIRED = frozenset({"min_quantity", "qty", "quantity", "tier_qty"})
_PRICE_FORBIDDEN_COLLAPSE_MSG = (
    "price_list rows must include qty-break column (min_quantity/qty); "
    "single collapsed price rows rejected"
)


def extract_text_from_pdf(raw: bytes) -> str:
    reader = PdfReader(BytesIO(raw))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("PDF contains no extractable text — enable vision (qwen3-vl) for scans")
    return text


def layout_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())[:4000]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _lines_to_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Best-effort parse of whitespace/comma separated PDF text blocks."""
    rows_raw: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 3:
            continue
        if "," in line:
            cells = [c.strip() for c in line.split(",")]
        else:
            cells = re.split(r"\s{2,}|\t", line)
            cells = [c.strip() for c in cells if c.strip()]
        if len(cells) >= 2:
            rows_raw.append(cells)
    if not rows_raw:
        return [], []
    width = max(len(r) for r in rows_raw)
    headers = [f"col_{i+1}" for i in range(width)]
    rows: list[dict[str, str]] = []
    for r in rows_raw:
        padded = r + [""] * (width - len(r))
        rows.append({headers[i]: padded[i] for i in range(width)})
    return headers, rows


def _schema_for_doc_type(doc_type: DocType) -> dict[str, Any]:
    if doc_type == "coa":
        return {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "name": {"type": "string"},
                            "account_type": {"type": "string"},
                        },
                        "required": ["code", "name"],
                    },
                }
            },
            "required": ["rows"],
        }
    if doc_type == "bom":
        return {
            "type": "object",
            "properties": {
                "boms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_code": {"type": "string"},
                            "quantity": {"type": "number"},
                            "lines": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "component_code": {"type": "string"},
                                        "quantity": {"type": "number"},
                                        "is_subassembly": {"type": "boolean"},
                                    },
                                    "required": ["component_code", "quantity"],
                                },
                            },
                        },
                        "required": ["product_code", "lines"],
                    },
                }
            },
            "required": ["boms"],
        }
    if doc_type == "price_list":
        return {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_code": {"type": "string"},
                            "min_quantity": {"type": "number"},
                            "price": {"type": "number"},
                            "date_start": {"type": "string"},
                            "date_end": {"type": "string"},
                        },
                        "required": ["product_code", "min_quantity", "price"],
                    },
                }
            },
            "required": ["rows"],
        }
    return {
        "type": "object",
        "properties": {
            "headers": {"type": "array", "items": {"type": "string"}},
            "rows": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": {"type": "string"}},
            },
        },
        "required": ["headers", "rows"],
    }


def _llm_extract(doc_type: DocType, text: str) -> dict[str, Any]:
    provider = get_llm_provider()
    if provider is None:
        raise LLMError("LLM provider unavailable for PDF structured extract")
    schema = _schema_for_doc_type(doc_type)
    prompt = (
        f"Extract structured rows from this {doc_type} document for Odoo import.\n"
        f"Document text (truncated):\n{text[:6000]}\n"
        "Return JSON matching the schema exactly. Do not invent account codes."
    )
    raw = provider.generate_json(
        prompt,
        system=(
            "You extract migration documents into strict JSON for Odoo import. "
            "For price lists always include min_quantity qty-break tiers. "
            "For BoMs preserve nested sub-assemblies via is_subassembly on lines."
        ),
        temperature=0.15,
        format_schema=schema,
    )
    return json.loads(raw) if isinstance(raw, str) else raw


def _validate_price_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        has_qty = any(row.get(k) not in (None, "", 0) for k in _PRICE_REQUIRED)
        if not has_qty:
            raise ValueError(_PRICE_FORBIDDEN_COLLAPSE_MSG)


def _tables_from_bom_payload(
    payload: dict[str, Any],
    *,
    filename: str,
) -> tuple[list[IngestTable], list[IngestRef]]:
    boms = payload.get("boms") or []
    parent_tables: list[IngestTable] = []
    line_tables: list[IngestTable] = []
    refs: list[IngestRef] = []
    for idx, bom in enumerate(boms, start=1):
        parent_id = str(uuid.uuid4())
        product_code = str(bom.get("product_code") or "")
        parent = IngestTable(
            id=parent_id,
            model="mrp.bom",
            doc_type="bom",
            mapping={"product_code": "product_tmpl_id", "quantity": "product_qty"},
            natural_key_fields=["product_tmpl_id"],
            rows=[
                IngestRow(
                    raw={"product_code": product_code, "quantity": str(bom.get("quantity") or 1)},
                    values={},
                    source_ref=f"{filename}:bom:{idx}",
                )
            ],
            warnings=[],
        )
        parent_tables.append(parent)
        line_rows: list[IngestRow] = []
        for lidx, line in enumerate(bom.get("lines") or [], start=1):
            comp = str(line.get("component_code") or "")
            if line.get("is_subassembly"):
                child_id = str(uuid.uuid4())
                child = IngestTable(
                    id=child_id,
                    model="mrp.bom",
                    doc_type="bom",
                    mapping={"product_code": "product_tmpl_id", "quantity": "product_qty"},
                    natural_key_fields=["product_tmpl_id"],
                    rows=[
                        IngestRow(
                            raw={"product_code": comp, "quantity": str(line.get("quantity") or 1)},
                            values={},
                            source_ref=f"{filename}:subbom:{idx}:{lidx}",
                        )
                    ],
                )
                parent_tables.append(child)
                refs.append(
                    IngestRef(
                        from_table_id=parent_id,
                        field="product_tmpl_id",
                        to_model="product.template",
                        to_value=comp,
                        resolved=False,
                        note="nested sub-assembly — child bom table emitted separately",
                    )
                )
            line_rows.append(
                IngestRow(
                    raw={
                        "parent_product": product_code,
                        "component_code": comp,
                        "quantity": str(line.get("quantity") or 1),
                    },
                    values={},
                    source_ref=f"{filename}:bomline:{idx}:{lidx}",
                )
            )
        if line_rows:
            line_tables.append(
                IngestTable(
                    id=str(uuid.uuid4()),
                    model="mrp.bom.line",
                    doc_type="bom",
                    mapping={
                        "parent_product": "bom_id",
                        "component_code": "product_id",
                        "quantity": "product_qty",
                    },
                    natural_key_fields=["bom_id", "product_id"],
                    rows=line_rows,
                    warnings=["two-pass BoM: lines reference parent by product_code"],
                )
            )
    return parent_tables + line_tables, refs


def _table_from_generic_payload(
    doc_type: DocType,
    payload: dict[str, Any],
    *,
    filename: str,
    model: str,
    mapping: dict[str, str],
) -> IngestTable:
    headers = [str(h) for h in payload.get("headers") or []]
    raw_rows = payload.get("rows") or []
    rows: list[IngestRow] = []
    for idx, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            continue
        cleaned = {str(k): str(v) for k, v in row.items()}
        if doc_type == "employee_roster":
            low_keys = {k.strip().lower().replace(" ", "_") for k in cleaned}
            if low_keys & WAGE_LIKE_HEADERS:
                cleaned = {k: v for k, v in cleaned.items() if k.strip().lower().replace(" ", "_") not in WAGE_LIKE_HEADERS}
        rows.append(IngestRow(raw=cleaned, values=dict(cleaned), source_ref=f"{filename}:{idx}"))
    if doc_type == "employee_roster" and rows:
        hdrs = headers or list(rows[0].raw.keys())
        dict_rows = [r.raw for r in rows]
        hdrs, dict_rows, wage_warn = _strip_wage_columns(hdrs, dict_rows)
        rows = [
            IngestRow(raw=dr, values=dict(dr), source_ref=r.source_ref)
            for dr, r in zip(dict_rows, rows, strict=False)
        ]
        warnings = wage_warn
    else:
        warnings = []
    return IngestTable(
        id=str(uuid.uuid4()),
        model=model,
        doc_type=doc_type,
        rows=rows,
        mapping=mapping or {h: h for h in headers},
        natural_key_fields=list(NATURAL_KEY_FIELDS.get(model, [])),
        warnings=warnings,
    )


def _deterministic_extract(doc_type: DocType, text: str, *, filename: str) -> list[IngestTable]:
    headers, rows = _lines_to_table(text)
    if doc_type == "coa" and rows:
        mapped: list[IngestRow] = []
        for idx, row in enumerate(rows, start=1):
            vals = list(row.values())
            mapped.append(
                IngestRow(
                    raw={"code": vals[0], "name": vals[1] if len(vals) > 1 else vals[0]},
                    values={},
                    source_ref=f"{filename}:{idx}",
                )
            )
        return [
            IngestTable(
                id=str(uuid.uuid4()),
                model="account.account",
                doc_type="coa",
                mapping={"code": "code", "name": "name"},
                natural_key_fields=["code"],
                rows=mapped,
            )
        ]
    if not rows:
        raise ValueError("Could not parse PDF text into rows")
    from app.data_import import suggest_mapping
    from app.ingest.constants import DOC_TYPE_PRIMARY_MODEL

    model = DOC_TYPE_PRIMARY_MODEL.get(doc_type, "res.partner")
    mapping = suggest_mapping(model, headers)
    return [
        _table_from_generic_payload(
            doc_type,
            {"headers": headers, "rows": rows},
            filename=filename,
            model=model,
            mapping=mapping,
        )
    ]


def extract_pdf_from_text(
    *,
    filename: str,
    text: str,
    doc_type: DocType,
    db=None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    """Parse already-OCR'd text through the same CoA/BoM/price_list paths."""
    warnings: list[str] = []
    fp = layout_fingerprint(text)
    cached = get_cached_extraction(db, fingerprint=fp, doc_type=doc_type) if db is not None else None
    if cached:
        warnings.append(f"layout cache hit:{fp[:8]}")
        payload = cached
    else:
        try:
            payload = _llm_extract(doc_type, text)
            if db is not None:
                save_cached_extraction(db, fingerprint=fp, doc_type=doc_type, payload=payload)
        except (LLMError, json.JSONDecodeError, ValueError, TypeError):
            warnings.append("LLM unavailable — deterministic PDF parser")
            return _deterministic_extract(doc_type, text, filename=filename), [], warnings

    refs: list[IngestRef] = []
    if doc_type == "bom":
        tables, refs = _tables_from_bom_payload(payload, filename=filename)
        return tables, refs, warnings
    if doc_type == "price_list":
        rows = payload.get("rows") or []
        _validate_price_rows(rows)
        table = _table_from_generic_payload(
            doc_type,
            {
                "headers": ["product_code", "min_quantity", "price", "date_start", "date_end"],
                "rows": [
                    {
                        "product_code": str(r.get("product_code") or ""),
                        "min_quantity": str(r.get("min_quantity") or ""),
                        "price": str(r.get("price") or ""),
                        "date_start": str(r.get("date_start") or ""),
                        "date_end": str(r.get("date_end") or ""),
                    }
                    for r in rows
                ],
            },
            filename=filename,
            model="product.pricelist.item",
            mapping={
                "product_code": "product_id",
                "min_quantity": "min_quantity",
                "price": "fixed_price",
                "date_start": "date_start",
                "date_end": "date_end",
            },
        )
        return [table], refs, warnings
    if doc_type == "coa":
        rows = payload.get("rows") or []
        table = _table_from_generic_payload(
            doc_type,
            {
                "headers": ["code", "name", "account_type"],
                "rows": [
                    {
                        "code": str(r.get("code") or ""),
                        "name": str(r.get("name") or ""),
                        "account_type": str(r.get("account_type") or ""),
                    }
                    for r in rows
                ],
            },
            filename=filename,
            model="account.account",
            mapping={"code": "code", "name": "name", "account_type": "account_type"},
        )
        return [table], refs, warnings

    from app.ingest.constants import DOC_TYPE_PRIMARY_MODEL
    from app.data_import import suggest_mapping

    model = DOC_TYPE_PRIMARY_MODEL.get(doc_type, "res.partner")
    headers = [str(h) for h in payload.get("headers") or []]
    mapping = suggest_mapping(model, headers) if headers else {}
    table = _table_from_generic_payload(
        doc_type, payload, filename=filename, model=model, mapping=mapping
    )
    return [table], refs, warnings


def extract_pdf_file(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db=None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    text = extract_text_from_pdf(raw)
    return extract_pdf_from_text(filename=filename, text=text, doc_type=doc_type, db=db)
