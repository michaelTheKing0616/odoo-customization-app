"""Layout template cache — repeat supplier fingerprint → mapping (ING-4)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import IngestLayoutCacheRow
from app.ingest.schema import DocType


def get_cached_extraction(
    db: Session,
    *,
    fingerprint: str,
    doc_type: DocType,
) -> dict[str, Any] | None:
    row = (
        db.query(IngestLayoutCacheRow)
        .filter(
            IngestLayoutCacheRow.source_fingerprint == fingerprint,
            IngestLayoutCacheRow.doc_type == doc_type,
        )
        .order_by(IngestLayoutCacheRow.updated_at.desc())
        .first()
    )
    if row is None:
        return None
    try:
        return json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return None


def save_cached_extraction(
    db: Session,
    *,
    fingerprint: str,
    doc_type: DocType,
    payload: dict[str, Any],
    headers: list[str] | None = None,
    mapping: dict[str, str] | None = None,
) -> IngestLayoutCacheRow:
    row = (
        db.query(IngestLayoutCacheRow)
        .filter(
            IngestLayoutCacheRow.source_fingerprint == fingerprint,
            IngestLayoutCacheRow.doc_type == doc_type,
        )
        .first()
    )
    if row is None:
        row = IngestLayoutCacheRow(
            id=str(uuid.uuid4()),
            source_fingerprint=fingerprint,
            doc_type=doc_type,
        )
    row.payload_json = json.dumps(payload)
    if headers is not None:
        row.headers_json = json.dumps(headers)
    if mapping is not None:
        row.mapping_json = json.dumps(mapping)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
