"""Unified file extract dispatcher — tabular, PDF text, PDF/image vision."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingest.extract_pdf import extract_pdf_file
from app.ingest.extract_tabular import extract_tabular_file
from app.ingest.extract_vision import (
    VisionNotReadyError,
    extract_image_with_vision,
    extract_pdf_with_vision,
    ingest_vision_enabled,
    is_image_bytes,
    pdf_needs_vision,
)
from app.ingest.schema import DocType, IngestRef, IngestTable


def _is_pdf(filename: str, raw: bytes) -> bool:
    name = filename.lower()
    if name.endswith(".pdf"):
        return True
    return raw[:4] == b"%PDF"


def _is_image(filename: str, raw: bytes) -> bool:
    name = filename.lower()
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff")):
        return True
    return is_image_bytes(raw)


def extract_upload_file(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db: Session | None = None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    warnings: list[str] = []
    if _is_image(filename, raw):
        if not ingest_vision_enabled():
            raise ValueError(
                "Image upload requires vision OCR — set INGEST_VISION=ollama "
                "and install qwen3-vl (see docs/research/ingest_vision_enable.md)"
            )
        try:
            tables, refs, vw = extract_image_with_vision(
                filename=filename, raw=raw, doc_type=doc_type, db=db
            )
            return tables, refs, warnings + vw
        except VisionNotReadyError as exc:
            raise ValueError(str(exc)) from exc

    if _is_pdf(filename, raw):
        if pdf_needs_vision(raw):
            if not ingest_vision_enabled():
                raise ValueError(
                    "Scanned PDF has no extractable text — enable vision "
                    "(INGEST_VISION=ollama + qwen3-vl) for OCR"
                )
            try:
                tables, refs, vw = extract_pdf_with_vision(
                    filename=filename, raw=raw, doc_type=doc_type, db=db
                )
                return tables, refs, warnings + vw
            except VisionNotReadyError as exc:
                raise ValueError(str(exc)) from exc
        if ingest_vision_enabled() and pdf_needs_vision(raw):
            # unreachable; kept for clarity
            pass
        tables, refs, pw = extract_pdf_file(
            filename=filename, raw=raw, doc_type=doc_type, db=db
        )
        return tables, refs, warnings + pw
    tables = extract_tabular_file(filename=filename, raw=raw, doc_type=doc_type)
    return tables, [], warnings
