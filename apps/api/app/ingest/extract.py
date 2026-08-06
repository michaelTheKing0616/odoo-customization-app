"""Unified file extract dispatcher — tabular, PDF text, PDF vision."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingest.extract_pdf import extract_pdf_file
from app.ingest.extract_tabular import extract_tabular_file
from app.ingest.extract_vision import (
    VisionNotReadyError,
    extract_pdf_with_vision,
    ingest_vision_enabled,
    pdf_needs_vision,
)
from app.ingest.schema import DocType, IngestRef, IngestTable


def _is_pdf(filename: str, raw: bytes) -> bool:
    name = filename.lower()
    if name.endswith(".pdf"):
        return True
    return raw[:4] == b"%PDF"


def extract_upload_file(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db: Session | None = None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    warnings: list[str] = []
    if _is_pdf(filename, raw):
        if pdf_needs_vision(raw) and ingest_vision_enabled():
            try:
                tables, refs, vw = extract_pdf_with_vision(
                    filename=filename, raw=raw, doc_type=doc_type, db=db
                )
                return tables, refs, warnings + vw
            except VisionNotReadyError as exc:
                raise ValueError(str(exc)) from exc
        tables, refs, pw = extract_pdf_file(
            filename=filename, raw=raw, doc_type=doc_type, db=db
        )
        return tables, refs, warnings + pw
    tables = extract_tabular_file(filename=filename, raw=raw, doc_type=doc_type)
    return tables, [], warnings
