"""Universal multi-file ingest pipeline API (Wave 17)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingest.constants import FINANCIAL_DOC_TYPES
from app.ingest.extract_vision import check_vision_model, ingest_vision_enabled
from app.ingest.interview import (
    INTERVIEW_QUESTIONS,
    InterviewAnswers,
    InterviewQuestion,
    build_batch_from_interview,
)
from app.ingest.pipeline import run_pipeline, stage_commit, stage_dry_run, stage_map, stage_plan
from app.ingest.schema import IngestBatch, IngestJobStatus
from app.ingest.store import create_job, create_job_from_batch, load_job, load_payload, save_batch
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation

router = APIRouter(
    prefix="/connections/{connection_id}/ingest",
    tags=["ingest"],
)


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class IngestJobOut(BaseModel):
    id: str
    connection_id: str
    status: str
    batch: IngestBatch
    error: str | None = None


class IngestDryRunBody(BaseModel):
    batch_size: int = Field(50, ge=1, le=500)


class IngestCommitBody(ConfirmAdvancedBody):
    batch_size: int = Field(50, ge=1, le=500)


class VisionStatusOut(BaseModel):
    enabled: bool
    ready: bool
    message: str
    model: str


def _job_out(row) -> IngestJobOut:
    batch, _ = load_payload(row)
    return IngestJobOut(
        id=row.id,
        connection_id=row.connection_id,
        status=row.status,
        batch=batch,
        error=row.error,
    )


@router.get("/vision/status", response_model=VisionStatusOut)
def vision_status(connection_id: str) -> VisionStatusOut:
    _ = connection_id
    from app.settings import settings

    ready, msg = check_vision_model()
    return VisionStatusOut(
        enabled=ingest_vision_enabled(),
        ready=ready,
        message=msg,
        model=settings.ingest_vision_model,
    )


@router.get("/interview/questions", response_model=list[InterviewQuestion])
def interview_questions(connection_id: str) -> list[InterviewQuestion]:
    _ = connection_id
    return INTERVIEW_QUESTIONS


@router.post("/interview/jobs", response_model=IngestJobOut)
def create_interview_job(
    connection_id: str,
    body: InterviewAnswers,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    batch = build_batch_from_interview(connection_id=connection_id, answers=body)
    if len(batch.tables) < 2:
        raise HTTPException(
            status_code=400,
            detail="Interview must produce at least one partner table and one product table",
        )
    row = create_job_from_batch(db, connection_id=connection_id, batch=batch)
    client = _client(connection_id, db)
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    save_batch(db, row, batch, status=IngestJobStatus.planned)
    row = load_job(db, row.id)
    return _job_out(row)


@router.post("/jobs", response_model=IngestJobOut)
async def create_ingest_job(
    connection_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> IngestJobOut:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    uploads: list[tuple[str, bytes, str | None]] = []
    for uf in files:
        raw = await uf.read()
        uploads.append((uf.filename or "upload.csv", raw, uf.content_type))
    row, _ = create_job(db, connection_id=connection_id, files=uploads)
    client = _client(connection_id, db)
    try:
        batch = run_pipeline(db, row.id, client=client, through="plan")
    except (OdooClientError, ValueError) as exc:
        save_batch(db, row, load_payload(row)[0], status=IngestJobStatus.failed, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_batch(db, row, batch, status=IngestJobStatus.planned)
    row = load_job(db, row.id)
    return _job_out(row)


@router.get("/jobs/{job_id}", response_model=IngestJobOut)
def get_ingest_job(
    connection_id: str,
    job_id: str,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(row)


@router.post("/jobs/{job_id}/dry-run", response_model=IngestJobOut)
def dry_run_job(
    connection_id: str,
    job_id: str,
    body: IngestDryRunBody | None = None,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    _ = body
    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    batch, _ = load_payload(row)
    client = _client(connection_id, db)
    if not batch.plan:
        batch = stage_map(batch, client)
        batch = stage_plan(batch)
    batch = stage_dry_run(batch, client)
    save_batch(db, row, batch, status=IngestJobStatus.dry_run)
    row = load_job(db, job_id)
    return _job_out(row)


@router.post("/jobs/{job_id}/commit", response_model=IngestJobOut)
def commit_job(
    connection_id: str,
    job_id: str,
    body: IngestCommitBody,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    batch, _ = load_payload(row)
    financial = any(f.doc_type in FINANCIAL_DOC_TYPES for f in batch.files)
    if financial:
        try:
            require_advanced_confirmation(
                body,
                warning="Financial ingest (CoA / opening balances) can alter accounting data.",
                risks=[
                    "Incorrect accounts may break fiscal reports",
                    "Opening balances affect trial balance",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    if batch.plan and batch.plan.gaps:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Unresolved gaps block commit",
                "gaps": [g.model_dump() for g in batch.plan.gaps],
            },
        )
    client = _client(connection_id, db)
    if not batch.plan:
        batch = stage_map(batch, client)
        batch = stage_plan(batch)
    batch = stage_dry_run(batch, client)
    batch = stage_commit(batch, client)
    save_batch(db, row, batch, status=IngestJobStatus.committed)
    row = load_job(db, job_id)
    return _job_out(row)
