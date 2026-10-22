"""Universal ingest orchestrator — stages 1–6 (ING-1)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Literal

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
from app.live_schema_context import SchemaPacket, bind_schema_rpc, studio_schema_packet

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


def _prompt_from_batch(batch: IngestBatch) -> str:
    names = [str(f.filename or "") for f in batch.files if f.filename]
    return " ".join(names).strip() or "ingest"


def _schema_packet_for_ingest(
    connection: Any | None,
    *,
    prompt: str,
    schema_packet: SchemaPacket | None = None,
    schema_client: Any | None = None,
    schema_graph: Any | None = None,
) -> SchemaPacket | None:
    if schema_packet is not None:
        return schema_packet
    if connection is None:
        return None
    return studio_schema_packet(
        connection,
        prompt=prompt,
        schema_client=schema_client,
        schema_graph=schema_graph,
    )


def _bind_ingest_connection(
    connection: Any | None,
    client: OdooClient | None,
    *,
    connection_id: str | None = None,
) -> Any | None:
    if connection is None and client is None:
        return None
    row = connection
    if row is None:
        row = SimpleNamespace(id=connection_id or "ingest", client=client)
    return bind_schema_rpc(row, client)


def stage_classify(
    batch: IngestBatch,
    blobs: dict[str, bytes],
    *,
    connection: Any | None = None,
    schema_packet: SchemaPacket | None = None,
    schema_client: Any | None = None,
    schema_graph: Any | None = None,
) -> IngestBatch:
    from app.ai_conversation.intent_llm import reset_schema_packet, set_schema_packet

    packet = _schema_packet_for_ingest(
        connection,
        prompt=_prompt_from_batch(batch),
        schema_packet=schema_packet,
        schema_client=schema_client,
        schema_graph=schema_graph,
    )
    token = set_schema_packet(packet)
    try:
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
            result = classify_upload(
                filename=f.filename,
                headers=headers,
                sample_rows=sample,
                schema_packet=packet,
            )
            f.doc_type = result.doc_type
            f.confidence = result.confidence
            f.needs_user_confirm = result.needs_user_confirm
            if result.signals:
                f.warnings.append(f"classify:{result.method}:{','.join(result.signals[:3])}")
        return batch
    finally:
        reset_schema_packet(token)


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
    return map_batch(
        client,
        batch,
        allow_coa_as_is=bool(batch.allow_coa_as_is),
    )


def stage_plan(batch: IngestBatch) -> IngestBatch:
    batch.plan = build_plan(batch)
    return batch


def stage_dry_run(batch: IngestBatch, client: OdooClient) -> IngestBatch:
    batch.commit_log = run_commit_plan(
        client, batch, dry_run=True, notify_mode=batch.notify_mode
    )
    return batch


def stage_commit(batch: IngestBatch, client: OdooClient) -> IngestBatch:
    batch.commit_log = run_commit_plan(
        client, batch, dry_run=False, notify_mode=batch.notify_mode
    )
    return batch


def run_pipeline(
    db: Session,
    job_id: str,
    *,
    client: OdooClient | None = None,
    through: StageName = "plan",
    force_doc_types: dict[str, DocType] | None = None,
    connection: Any | None = None,
    schema_packet: SchemaPacket | None = None,
    schema_client: Any | None = None,
    schema_graph: Any | None = None,
) -> IngestBatch:
    row = load_job(db, job_id)
    batch, blobs = load_payload(row)

    if force_doc_types:
        for f in batch.files:
            if f.id in force_doc_types:
                f.doc_type = force_doc_types[f.id]
                f.needs_user_confirm = False
                f.confidence = 1.0

    bound = connection
    if bound is None and getattr(row, "connection_id", None):
        try:
            from app.odoo_service import get_connection_or_404

            bound = get_connection_or_404(db, row.connection_id)
        except Exception:  # noqa: BLE001
            bound = None
    bound = _bind_ingest_connection(
        bound,
        client,
        connection_id=getattr(row, "connection_id", None),
    )
    batch = stage_classify(
        batch,
        blobs,
        connection=bound,
        schema_packet=schema_packet,
        schema_client=schema_client,
        schema_graph=schema_graph,
    )
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
