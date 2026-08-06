"""Ingest job persistence (ING-1)."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db_models import IngestJobRow
from app.ingest.schema import IngestBatch, IngestFile, IngestJobStatus


class IngestJobStoreError(LookupError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _batch_to_dict(batch: IngestBatch) -> dict:
    return batch.model_dump(mode="json")


def _batch_from_dict(data: dict) -> IngestBatch:
    return IngestBatch.model_validate(data)


def create_job(
    db: Session,
    *,
    connection_id: str,
    files: list[tuple[str, bytes, str | None]],
) -> tuple[IngestJobRow, dict[str, bytes]]:
    job_id = str(uuid.uuid4())
    ingest_files: list[IngestFile] = []
    blobs: dict[str, bytes] = {}
    for filename, raw, mime in files:
        fid = str(uuid.uuid4())
        ingest_files.append(
            IngestFile(
                id=fid,
                filename=filename,
                mime=mime,
            )
        )
        blobs[fid] = raw

    batch = IngestBatch(connection_id=connection_id, files=ingest_files)
    payload = {
        "batch": _batch_to_dict(batch),
        "file_blobs_b64": {k: base64.b64encode(v).decode("ascii") for k, v in blobs.items()},
    }
    row = IngestJobRow(
        id=job_id,
        connection_id=connection_id,
        status=IngestJobStatus.pending.value,
        payload_json=json.dumps(payload),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, blobs


def load_job(db: Session, job_id: str) -> IngestJobRow:
    row = db.get(IngestJobRow, job_id)
    if row is None:
        raise IngestJobStoreError(f"Ingest job {job_id} not found")
    return row


def load_payload(row: IngestJobRow) -> tuple[IngestBatch, dict[str, bytes]]:
    data = json.loads(row.payload_json or "{}")
    batch = _batch_from_dict(data.get("batch") or {})
    blobs: dict[str, bytes] = {}
    for fid, b64 in (data.get("file_blobs_b64") or {}).items():
        blobs[fid] = base64.b64decode(b64.encode("ascii"))
    return batch, blobs


def save_batch(
    db: Session,
    row: IngestJobRow,
    batch: IngestBatch,
    *,
    status: IngestJobStatus | None = None,
    file_blobs: dict[str, bytes] | None = None,
    error: str | None = None,
) -> IngestJobRow:
    data = json.loads(row.payload_json or "{}")
    data["batch"] = _batch_to_dict(batch)
    if file_blobs is not None:
        data["file_blobs_b64"] = {
            k: base64.b64encode(v).decode("ascii") for k, v in file_blobs.items()
        }
    row.payload_json = json.dumps(data)
    row.updated_at = _utcnow()
    if status is not None:
        row.status = status.value
    if error is not None:
        row.error = error
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_job_from_batch(
    db: Session,
    *,
    connection_id: str,
    batch: IngestBatch,
) -> IngestJobRow:
    job_id = str(uuid.uuid4())
    payload = {"batch": _batch_to_dict(batch), "file_blobs_b64": {}}
    row = IngestJobRow(
        id=job_id,
        connection_id=connection_id,
        status=IngestJobStatus.pending.value,
        payload_json=json.dumps(payload),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_job_from_batch(
    db: Session,
    *,
    connection_id: str,
    batch: IngestBatch,
) -> IngestJobRow:
    job_id = str(uuid.uuid4())
    payload = {"batch": _batch_to_dict(batch), "file_blobs_b64": {}}
    row = IngestJobRow(
        id=job_id,
        connection_id=connection_id,
        status=IngestJobStatus.pending.value,
        payload_json=json.dumps(payload),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
