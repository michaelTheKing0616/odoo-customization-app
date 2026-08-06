"""Universal ingest orchestrator — stages 1–6 (ING-1)."""

from __future__ import annotations

from typing import Literal

from odoo_client import OdooClient
from sqlalchemy.orm import Session

from app.data_import import parse_tabular
from app.ingest.classify import classify_upload
from app.ingest.commit import run_commit_plan
from app.ingest.extract import extract_upload_file
from app.ingest.extract_pdf import extract_text_from_pdf
from app.ingest.map import map_batch
from app.ingest.order import build_plan
from app.ingest.schema import DocType, IngestBatch, IngestJobStatus, IngestRef
from app.ingest.store import load_job, load_payload, save_batch

StageName = Literal[
    "classify",
    "extract",
    "map",
    "plan",
    "dry_run",
    "commit",
]


def _is_pdf(filename: str, raw: bytes) -> bool:
    return filename.lower().endswith(".pdf") or raw[:4] == b"%PDF"


def stage_classify(batch: IngestBatch, blobs: dict[str, bytes]) -> IngestBatch:
    for f in batch.files:
        raw = blobs.get(f.id, b"")
        headers: list[str] = []
        sample: list[dict[str, str]] = []
        if raw:
            try:
                if _is_pdf(f.filename, raw):
                    text = extract_text_from_pdf(raw)
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    headers = lines[0].split() if lines else []
                    sample = [
                        dict(zip(headers, ln.split(), strict=False))
                        for ln in lines[1:4]
                        if ln.split()
                    ]
                else:
                    headers, rows = parse_tabular(raw, f.filename)
                    sample = rows[:3]
            except ValueError:
                headers = []
        result = classify_upload(filename=f.filename, headers=headers, sample_rows=sample)
        f.doc_type = result.doc_type
        f.confidence = result.confidence
        f.needs_user_confirm = result.needs_user_confirm
        if result.signals:
            f.warnings.append(f"classify:{result.method}:{','.join(result.signals[:3])}")
    return batch


def stage_extract(
    batch: IngestBatch,
    blobs: dict[str, bytes],
    *,
    db: Session | None = None,
    client: OdooClient | None = None,
) -> IngestBatch:
    tables = []
    extra_refs: list[IngestRef] = []
    for f in batch.files:
        raw = blobs.get(f.id, b"")
        if not raw:
            f.warnings.append("empty file")
            continue
        extracted, refs, warns = extract_upload_file(
            filename=f.filename,
            raw=raw,
            doc_type=f.doc_type,
            db=db,
        )
        f.warnings.extend(warns)
        f.table_ids = [t.id for t in extracted]
        tables.extend(extracted)
        extra_refs.extend(refs)
    batch.tables = tables
    batch.refs.extend(extra_refs)
    if client is not None:
        from app.ingest.map_columns import enhance_mapping_with_llm

        for table in batch.tables:
            headers = list(table.mapping.keys()) or list(
                table.rows[0].raw.keys() if table.rows else []
            )
            rows = [r.raw for r in table.rows]
            mapping, mw = enhance_mapping_with_llm(
                client,
                model=table.model,
                headers=headers,
                rows=rows,
                mapping=table.mapping,
            )
            table.mapping = mapping
            table.warnings.extend(mw)
    return batch


def stage_map(batch: IngestBatch, client: OdooClient) -> IngestBatch:
    return map_batch(client, batch)


def stage_plan(batch: IngestBatch) -> IngestBatch:
    batch.plan = build_plan(batch)
    return batch


def stage_dry_run(batch: IngestBatch, client: OdooClient) -> IngestBatch:
    batch.commit_log = run_commit_plan(client, batch, dry_run=True)
    return batch


def stage_commit(batch: IngestBatch, client: OdooClient) -> IngestBatch:
    batch.commit_log = run_commit_plan(client, batch, dry_run=False)
    return batch


def run_pipeline(
    db: Session,
    job_id: str,
    *,
    client: OdooClient | None = None,
    through: StageName = "plan",
    force_doc_types: dict[str, DocType] | None = None,
) -> IngestBatch:
    row = load_job(db, job_id)
    batch, blobs = load_payload(row)

    if force_doc_types:
        for f in batch.files:
            if f.id in force_doc_types:
                f.doc_type = force_doc_types[f.id]
                f.needs_user_confirm = False
                f.confidence = 1.0

    batch = stage_classify(batch, blobs)
    save_batch(db, row, batch, status=IngestJobStatus.classified)

    batch = stage_extract(batch, blobs, db=db, client=client)
    save_batch(db, row, batch, status=IngestJobStatus.extracted, file_blobs={})

    if through in {"map", "plan", "dry_run", "commit"}:
        if client is None:
            raise ValueError("Odoo client required for map/plan/dry_run/commit stages")
        batch = stage_map(batch, client)
        save_batch(db, row, batch, status=IngestJobStatus.mapped)

    if through in {"plan", "dry_run", "commit"}:
        batch = stage_plan(batch)
        save_batch(db, row, batch, status=IngestJobStatus.planned)

    if through == "dry_run":
        if client is None:
            raise ValueError("Odoo client required for dry_run")
        batch = stage_dry_run(batch, client)
        save_batch(db, row, batch, status=IngestJobStatus.dry_run)

    if through == "commit":
        if client is None:
            raise ValueError("Odoo client required for commit")
        batch = stage_dry_run(batch, client)
        batch = stage_commit(batch, client)
        save_batch(db, row, batch, status=IngestJobStatus.committed)

    return batch
