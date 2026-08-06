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
    notify_mode: str | None = Field(
        None, description="batch_summary (default) or individual"
    )
    allow_coa_as_is: bool = False


class IngestCommitBody(ConfirmAdvancedBody):
    batch_size: int = Field(50, ge=1, le=500)
    notify_mode: str | None = Field(
        None, description="batch_summary (default) or individual chatter/mail"
    )
    allow_coa_as_is: bool = False


class IngestOverrideBody(BaseModel):
    """Override classification for files that need_user_confirm."""

    force_doc_types: dict[str, str] = Field(default_factory=dict)


class IngestPrefsOut(BaseModel):
    notify_mode: str = "batch_summary"
    allow_coa_as_is_default: bool = False
    coa_auto_remap_default: bool = False


class IngestPrefsBody(BaseModel):
    notify_mode: str | None = None
    allow_coa_as_is_default: bool | None = None
    coa_auto_remap_default: bool | None = None


class IngestCoaRemapBody(BaseModel):
    """legacy_code → target l10n/live code. Empty remap + auto=true applies suggestions."""

    remap: dict[str, str] = Field(default_factory=dict)
    auto: bool = False
    min_score: float = Field(0.45, ge=0.0, le=1.0)


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


@router.get("/prefs", response_model=IngestPrefsOut)
def get_prefs(connection_id: str, db: Session = Depends(get_db)) -> IngestPrefsOut:
    from app.ingest.prefs import get_ingest_prefs

    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IngestPrefsOut(**get_ingest_prefs(row))


@router.patch("/prefs", response_model=IngestPrefsOut)
def patch_prefs(
    connection_id: str,
    body: IngestPrefsBody,
    db: Session = Depends(get_db),
) -> IngestPrefsOut:
    from app.ingest.prefs import set_ingest_prefs

    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.notify_mode is not None and body.notify_mode not in {
        "batch_summary",
        "individual",
    }:
        raise HTTPException(status_code=400, detail="notify_mode must be batch_summary|individual")
    prefs = set_ingest_prefs(
        db,
        row,
        notify_mode=body.notify_mode,
        allow_coa_as_is_default=body.allow_coa_as_is_default,
        coa_auto_remap_default=body.coa_auto_remap_default,
    )
    return IngestPrefsOut(**prefs)


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
    from app.ingest.prefs import get_ingest_prefs

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    try:
        conn = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    prefs = get_ingest_prefs(conn)
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
    batch.notify_mode = prefs["notify_mode"]  # type: ignore[assignment]
    batch.allow_coa_as_is = bool(prefs.get("allow_coa_as_is_default"))
    if prefs.get("coa_auto_remap_default"):
        batch.meta["coa_auto_remap"] = True
        batch = stage_map(batch, client)
        batch = stage_plan(batch)
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


@router.post("/jobs/{job_id}/coa-remap", response_model=IngestJobOut)
def coa_remap_job(
    connection_id: str,
    job_id: str,
    body: IngestCoaRemapBody,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    from app.ingest.coa_align import (
        apply_coa_remap,
        load_instance_account_codes,
        suggest_coa_remaps,
    )

    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    batch, _ = load_payload(row)
    client = _client(connection_id, db)
    live = load_instance_account_codes(client)
    remap = dict(body.remap)
    if body.auto:
        for table in batch.tables:
            if table.doc_type != "coa":
                continue
            for sug in suggest_coa_remaps(client, table):
                if (
                    sug.get("suggested_code")
                    and (sug.get("score") or 0) >= body.min_score
                    and sug["legacy_code"] not in remap
                ):
                    remap[sug["legacy_code"]] = sug["suggested_code"]
    if not remap:
        raise HTTPException(
            status_code=400,
            detail="No remap pairs provided and auto found no high-confidence suggestions",
        )
    notes: list[str] = []
    for table in batch.tables:
        if table.doc_type == "coa":
            notes.extend(apply_coa_remap(table, remap, live=live))
    batch.warnings.extend(notes)
    batch.meta["coa_remap_applied"] = remap
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    save_batch(db, row, batch, status=IngestJobStatus.planned)
    row = load_job(db, job_id)
    return _job_out(row)


@router.post("/jobs/{job_id}/override", response_model=IngestJobOut)
def override_classification(
    connection_id: str,
    job_id: str,
    body: IngestOverrideBody,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    from app.ingest.pipeline import run_pipeline
    from app.ingest.schema import validate_doc_type

    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    forced = {}
    for fid, dtype in body.force_doc_types.items():
        try:
            forced[fid] = validate_doc_type(dtype)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = _client(connection_id, db)
    try:
        batch = run_pipeline(
            db, job_id, client=client, through="plan", force_doc_types=forced
        )
    except (OdooClientError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_batch(db, row, batch, status=IngestJobStatus.planned)
    row = load_job(db, job_id)
    return _job_out(row)


@router.post("/jobs/{job_id}/dry-run", response_model=IngestJobOut)
def dry_run_job(
    connection_id: str,
    job_id: str,
    body: IngestDryRunBody | None = None,
    db: Session = Depends(get_db),
) -> IngestJobOut:
    body = body or IngestDryRunBody()
    row = load_job(db, job_id)
    if row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    batch, _ = load_payload(row)
    if body.notify_mode in {"batch_summary", "individual"}:
        batch.notify_mode = body.notify_mode  # type: ignore[assignment]
    if body.allow_coa_as_is:
        batch.allow_coa_as_is = True
    client = _client(connection_id, db)
    if not batch.plan or body.allow_coa_as_is:
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
    if body.notify_mode in {"batch_summary", "individual"}:
        batch.notify_mode = body.notify_mode  # type: ignore[assignment]
    if body.allow_coa_as_is:
        batch.allow_coa_as_is = True
    financial = any(f.doc_type in FINANCIAL_DOC_TYPES for f in batch.files)
    if financial:
        try:
            require_advanced_confirmation(
                body,
                warning="Financial ingest (CoA / opening balances) can alter accounting data.",
                risks=[
                    "Incorrect accounts may break fiscal reports",
                    "Opening balances create a DRAFT journal entry — never auto-posted",
                    "Legacy CoA codes may diverge from l10n_* package",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    client = _client(connection_id, db)
    # Remap with allow_coa_as_is so legacy-code gaps clear when confirmed
    batch = stage_map(batch, client)
    batch = stage_plan(batch)
    all_gaps = list(batch.plan.gaps) if batch.plan else list(batch.gaps)
    blocking = [g for g in all_gaps if getattr(g, "severity", "block") == "block"]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Unresolved gaps block commit",
                "gaps": [g.model_dump() for g in blocking],
            },
        )
    needs_confirm = [f for f in batch.files if f.needs_user_confirm]
    if needs_confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Low-confidence classification needs override",
                "files": [
                    {"id": f.id, "filename": f.filename, "doc_type": f.doc_type}
                    for f in needs_confirm
                ],
            },
        )
    batch = stage_dry_run(batch, client)
    batch = stage_commit(batch, client)
    save_batch(db, row, batch, status=IngestJobStatus.committed)
    row = load_job(db, job_id)
    return _job_out(row)
