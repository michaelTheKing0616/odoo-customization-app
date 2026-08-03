"""ID Generator routes — CSV + live modes (BLK-9)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.bulk_suite.domain_util import DomainParseError, parse_domain
from app.bulk_suite.transitions import BulkSuiteError, DEFAULT_RECORD_CAP, resolve_record_ids
from app.data_import import parse_tabular
from app.db import get_db
from app.id_generator import (
    IdGeneratorConfig,
    IdGeneratorError,
    apply_csv_assignments,
    create_reference_sequence,
    generate_codes,
    rows_from_csv_dicts,
    run_live_id_generator,
)
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/id-generator",
    tags=["id-generator"],
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


class IdGeneratorConfigIn(BaseModel):
    prefix: str = Field(..., min_length=1)
    separator: str = "-"
    padding: int = Field(4, ge=1, le=12)
    initials_length: int = Field(3, ge=1, le=8)
    skip_if_present: bool = True


class CodeAssignmentOut(BaseModel):
    row_id: str | int
    name: str
    existing_code: str | None
    new_code: str | None
    changed: bool
    initials: str | None = None


class IdGeneratorPreviewOut(BaseModel):
    total: int
    changed: int
    skipped: int
    assignments: list[CodeAssignmentOut]
    headers: list[str] | None = None
    message: str


class IdGeneratorRunOut(BaseModel):
    run_id: str
    operation: str
    model: str
    total: int
    succeeded: int
    failed: int
    changed: int
    skipped: int
    dry_run: bool
    message: str
    assignments: list[CodeAssignmentOut]


class CsvDownloadBody(BaseModel):
    headers: list[str]
    rows: list[dict[str, str]]
    assignments: list[CodeAssignmentOut]
    code_column: str
    changed_only: bool = False


class LiveIdGeneratorBody(ConfirmAdvancedBody):
    model: str
    name_field: str
    code_field: str
    config: IdGeneratorConfigIn
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)
    dry_run: bool = True


class CreateSequenceBridgeBody(BaseModel):
    model: str
    config: IdGeneratorConfigIn
    sequence_name: str | None = None


def _config(body: IdGeneratorConfigIn) -> IdGeneratorConfig:
    try:
        return IdGeneratorConfig(
            prefix=body.prefix,
            separator=body.separator,
            padding=body.padding,
            initials_length=body.initials_length,
            skip_if_present=body.skip_if_present,
        )
    except IdGeneratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _assignments_out(items: list) -> list[CodeAssignmentOut]:
    return [CodeAssignmentOut.model_validate(a.to_dict()) for a in items]


@router.post("/csv/preview", response_model=IdGeneratorPreviewOut)
async def csv_preview(
    connection_id: str,
    file: UploadFile = File(...),
    name_column: str = Form(...),
    code_column: str | None = Form(None),
    id_column: str | None = Form(None),
    prefix: str = Form(...),
    separator: str = Form("-"),
    padding: int = Form(4),
    initials_length: int = Form(3),
    skip_if_present: bool = Form(True),
    changed_only: bool = Form(False),
    db: Session = Depends(get_db),
) -> IdGeneratorPreviewOut:
    _client(connection_id, db)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty file")
    try:
        headers, rows = parse_tabular(raw, file.filename or "data.csv")
        cfg = _config(
            IdGeneratorConfigIn(
                prefix=prefix,
                separator=separator,
                padding=padding,
                initials_length=initials_length,
                skip_if_present=skip_if_present,
            )
        )
        input_rows = rows_from_csv_dicts(
            rows,
            name_column=name_column,
            code_column=code_column,
            id_column=id_column,
        )
        assignments = generate_codes(input_rows, cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IdGeneratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IdGeneratorPreviewOut(
        total=len(assignments),
        changed=sum(1 for a in assignments if a.changed),
        skipped=sum(1 for a in assignments if not a.changed),
        assignments=_assignments_out(assignments),
        headers=headers,
        message=f"Preview: {sum(1 for a in assignments if a.changed)} changed of {len(assignments)} row(s)",
    )


@router.post("/csv/download")
def csv_download(body: CsvDownloadBody) -> StreamingResponse:
    from app.id_generator import CodeAssignment

    assignments = [CodeAssignment(**a.model_dump()) for a in body.assignments]
    try:
        csv_text = apply_csv_assignments(
            body.headers,
            body.rows,
            assignments,
            code_column=body.code_column,
            changed_only=body.changed_only,
        )
    except IdGeneratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        iter([csv_text.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="id-generator-updated.csv"'},
    )


@router.post("/live", response_model=IdGeneratorRunOut)
def live_id_generator(
    connection_id: str,
    body: LiveIdGeneratorBody,
    db: Session = Depends(get_db),
) -> IdGeneratorRunOut:
    client = _client(connection_id, db)
    model = body.model.strip()
    try:
        record_ids = resolve_record_ids(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Write generated reference codes on {len(record_ids)} {model!r} record(s).",
                risks=[
                    "Only empty code fields are updated when skip-if-present is on",
                    "Codes are assigned sequentially per initials group",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    cfg = _config(body.config)
    try:
        result = run_live_id_generator(
            client,
            model=model,
            name_field=body.name_field.strip(),
            code_field=body.code_field.strip(),
            config=cfg,
            record_ids=record_ids,
            dry_run=body.dry_run,
        )
    except IdGeneratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return IdGeneratorRunOut(
        run_id=result.run_id,
        operation=result.operation,
        model=result.model,
        total=result.total,
        succeeded=result.succeeded,
        failed=result.failed,
        changed=result.changed,
        skipped=result.skipped,
        dry_run=result.dry_run,
        message=result.message,
        assignments=_assignments_out(result.assignments),
    )


@router.post("/sequence")
def create_sequence_bridge(
    connection_id: str,
    body: CreateSequenceBridgeBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client = _client(connection_id, db)
    cfg = _config(body.config)
    try:
        row = create_reference_sequence(
            client,
            model=body.model.strip(),
            config=cfg,
            sequence_name=body.sequence_name,
        )
    except IdGeneratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "sequence": row}
