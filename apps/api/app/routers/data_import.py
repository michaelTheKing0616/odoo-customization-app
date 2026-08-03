"""Bulk CSV/XLSX data import into live Odoo models."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.data_import import (
    build_preview,
    dry_run_or_commit,
    parse_tabular,
    results_to_error_csv,
    suggest_mapping,
    template_csv,
)
from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/data-import",
    tags=["data-import"],
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


class DataImportPreviewOut(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, str]]
    row_count: int
    suggested_model: str | None = None
    field_hints: list[dict[str, Any]] = Field(default_factory=list)
    suggested_mapping: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DataImportCommitBody(ConfirmAdvancedBody):
    model: str
    mapping: dict[str, str]
    mode: Literal["create", "upsert"] = "create"
    match_fields: list[str] = Field(default_factory=list)
    dry_run: bool = True
    batch_size: int = Field(50, ge=1, le=500)
    # Rows sent from client after preview (avoids re-upload). Cap size in handler.
    rows: list[dict[str, str]]


class RowResultOut(BaseModel):
    row_index: int
    ok: bool
    record_id: int | None = None
    action: str | None = None
    error: str | None = None


class DataImportCommitOut(BaseModel):
    ok: bool
    dry_run: bool
    created: int
    updated: int
    failed: int
    skipped: int
    message: str
    results: list[RowResultOut]
    error_csv: str | None = None


class TemplateOut(BaseModel):
    model: str
    filename: str
    csv: str


@router.get("/template", response_model=TemplateOut)
def get_template(connection_id: str, model: str = "res.partner") -> TemplateOut:
    _ = connection_id
    safe = model.strip() or "res.partner"
    return TemplateOut(
        model=safe,
        filename=f"{safe.replace('.', '_')}_import_template.csv",
        csv=template_csv(safe),
    )


class SeedPackSummary(BaseModel):
    id: str
    name: str
    description: str
    models: list[str]


class SeedPackModelOut(BaseModel):
    model: str
    filename: str
    csv: str


class SeedPackDetail(BaseModel):
    id: str
    name: str
    description: str
    models: list[SeedPackModelOut]


@router.get("/seed-packs", response_model=list[SeedPackSummary])
def list_import_seed_packs(connection_id: str) -> list[SeedPackSummary]:
    _ = connection_id
    from app.industry_seeds import list_seed_packs

    return [SeedPackSummary.model_validate(p) for p in list_seed_packs()]


@router.get("/seed-packs/{pack_id}", response_model=SeedPackDetail)
def get_import_seed_pack(connection_id: str, pack_id: str) -> SeedPackDetail:
    _ = connection_id
    from app.industry_seeds import get_seed_pack

    pack = get_seed_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Unknown seed pack {pack_id}")
    return SeedPackDetail(
        id=pack["id"],
        name=pack["name"],
        description=pack["description"],
        models=[SeedPackModelOut.model_validate(m) for m in pack["models"]],
    )


@router.post("/preview", response_model=DataImportPreviewOut)
async def preview_import(
    connection_id: str,
    file: UploadFile = File(...),
    model: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DataImportPreviewOut:
    _client(connection_id, db)  # validate connection
    if not file.filename:
        raise HTTPException(status_code=422, detail="filename required")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty file")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 15MB)")
    try:
        headers, rows = parse_tabular(raw, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    preview = build_preview(headers=headers, rows=rows, model=model)
    mapping = (
        suggest_mapping(preview.suggested_model, headers)
        if preview.suggested_model
        else suggest_mapping(model or "res.partner", headers)
    )
    return DataImportPreviewOut(
        headers=preview.headers,
        sample_rows=preview.sample_rows,
        row_count=preview.row_count,
        suggested_model=preview.suggested_model,
        field_hints=preview.field_hints,
        suggested_mapping=mapping,
        warnings=preview.warnings,
    )


@router.post("/parse-rows", response_model=DataImportPreviewOut)
async def parse_rows_for_commit(
    connection_id: str,
    file: UploadFile = File(...),
    model: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DataImportPreviewOut:
    """Parse file and return all rows embedded in sample_rows (for commit without re-map loss).

    For large files prefer client-side CSV parse; this endpoint caps at 5000 rows.
    """
    _ = _client(connection_id, db)
    raw = await file.read()
    try:
        headers, rows = parse_tabular(raw, file.filename or "data.csv")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(rows) > 5000:
        raise HTTPException(status_code=413, detail="max 5000 rows per import")
    preview = build_preview(headers=headers, rows=rows, model=model)
    mapping = suggest_mapping(preview.suggested_model or model or "res.partner", headers)
    return DataImportPreviewOut(
        headers=headers,
        sample_rows=rows,  # full set for commit helper UIs
        row_count=len(rows),
        suggested_model=preview.suggested_model,
        field_hints=preview.field_hints,
        suggested_mapping=mapping,
        warnings=preview.warnings
        + (["Showing all rows in sample_rows for commit"] if rows else []),
    )


@router.post("/commit", response_model=DataImportCommitOut)
def commit_import(
    connection_id: str,
    body: DataImportCommitBody,
    db: Session = Depends(get_db),
) -> DataImportCommitOut:
    if not body.rows:
        raise HTTPException(status_code=422, detail="rows required")
    if len(body.rows) > 5000:
        raise HTTPException(status_code=413, detail="max 5000 rows")
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Bulk {body.mode} on {body.model} will write "
                    f"{len(body.rows)} row(s) to the live Odoo database."
                ),
                risks=[
                    "Creates or updates business records (contacts, products, custom models)",
                    "Many2one resolution mistakes can link wrong related records",
                    "Does not automatically roll back successful rows if later rows fail",
                    "Prefer dry-run first; use a sandbox connection when unsure",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = dry_run_or_commit(
            client,
            model=body.model,
            rows=body.rows,
            mapping=body.mapping,
            mode=body.mode,
            match_fields=body.match_fields,
            dry_run=body.dry_run,
            batch_size=body.batch_size,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    err_csv = results_to_error_csv(result.results) if result.failed else None
    return DataImportCommitOut(
        ok=result.ok,
        dry_run=body.dry_run,
        created=result.created,
        updated=result.updated,
        failed=result.failed,
        skipped=result.skipped,
        message=result.message,
        results=[
            RowResultOut(
                row_index=r.row_index,
                ok=r.ok,
                record_id=r.record_id,
                action=r.action,
                error=r.error,
            )
            for r in result.results
        ],
        error_csv=err_csv,
    )


class ImageImportPreviewOut(BaseModel):
    row_count: int
    sample_rows: list[dict[str, str]]
    image_field: str
    match_field: str
    match_mode: str
    warnings: list[str] = Field(default_factory=list)


class ImageImportCommitBody(ConfirmAdvancedBody):
    model: str
    manifest_rows: list[dict[str, str]]
    image_field: str
    match_field: str = "x_name"
    dry_run: bool = True


class ImageImportRowOut(BaseModel):
    row_index: int
    match_value: str
    filename: str
    ok: bool
    record_id: int | None = None
    action: str | None = None
    error: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0


class ImageImportCommitOut(BaseModel):
    ok: bool
    dry_run: bool
    updated: int
    failed: int
    skipped: int
    message: str
    results: list[ImageImportRowOut]


@router.post("/images/preview", response_model=ImageImportPreviewOut)
async def preview_image_import(
    connection_id: str,
    manifest: UploadFile = File(..., description="CSV manifest: match,name + filename"),
    images_zip: UploadFile = File(..., description="ZIP of image files"),
    db: Session = Depends(get_db),
) -> ImageImportPreviewOut:
    _client(connection_id, db)
    if not manifest.filename or not images_zip.filename:
        raise HTTPException(status_code=422, detail="manifest CSV and images ZIP required")
    manifest_raw = await manifest.read()
    zip_raw = await images_zip.read()
    if len(zip_raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="ZIP too large (max 50MB)")
    try:
        from app.image_import import build_image_import_preview, parse_image_upload

        rows, image_field, match_field, match_mode, zip_images = parse_image_upload(
            manifest_raw, zip_raw
        )
        preview = build_image_import_preview(
            manifest_rows=rows,
            image_field=image_field,
            match_field=match_field,
            match_mode=match_mode,
            zip_names=set(zip_images.keys()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImageImportPreviewOut(
        row_count=preview.row_count,
        sample_rows=preview.sample_rows,
        image_field=preview.image_field,
        match_field=preview.match_field,
        match_mode=preview.match_mode,
        warnings=preview.warnings,
    )


@router.post("/images/commit", response_model=ImageImportCommitOut)
async def commit_image_import(
    connection_id: str,
    manifest: UploadFile = File(...),
    images_zip: UploadFile = File(...),
    model: str = Form(...),
    match_field: str = Form("x_name"),
    image_field: str = Form(""),
    dry_run: bool = Form(True),
    confirm_advanced: bool = Form(False),
    confirm_phrase: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ImageImportCommitOut:
    if not dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=confirm_advanced,
                confirm_phrase=confirm_phrase,
                warning=f"Bulk image import will write images to {model} on live Odoo.",
                risks=[
                    "Overwrites existing binary/image field data on matched records",
                    "Wrong match column can attach images to incorrect records",
                    "Large images are downscaled but still consume DB space",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    manifest_raw = await manifest.read()
    zip_raw = await images_zip.read()
    try:
        from app.image_import import parse_image_upload, run_image_import

        rows, default_field, _, _, zip_images = parse_image_upload(manifest_raw, zip_raw)
        target_field = (image_field or default_field).strip() or default_field
        client = _client(connection_id, db)
        result = run_image_import(
            client,
            model=model.strip(),
            manifest_rows=rows,
            zip_images=zip_images,
            image_field=target_field,
            match_field=match_field.strip() or "x_name",
            dry_run=dry_run,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ImageImportCommitOut(
        ok=result.ok,
        dry_run=dry_run,
        updated=result.updated,
        failed=result.failed,
        skipped=result.skipped,
        message=result.message,
        results=[
            ImageImportRowOut(
                row_index=r.row_index,
                match_value=r.match_value,
                filename=r.filename,
                ok=r.ok,
                record_id=r.record_id,
                action=r.action,
                error=r.error,
                bytes_in=r.bytes_in,
                bytes_out=r.bytes_out,
            )
            for r in result.results
        ],
    )


class ImageImportPreviewOut(BaseModel):
    row_count: int
    sample_rows: list[dict[str, str]]
    image_field: str
    match_field: str
    match_mode: str
    warnings: list[str] = Field(default_factory=list)


class ImageImportCommitBody(ConfirmAdvancedBody):
    model: str
    manifest_rows: list[dict[str, str]]
    image_field: str
    match_field: str = "x_name"
    dry_run: bool = True


class ImageImportRowOut(BaseModel):
    row_index: int
    match_value: str
    filename: str
    ok: bool
    record_id: int | None = None
    action: str | None = None
    error: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0


class ImageImportCommitOut(BaseModel):
    ok: bool
    dry_run: bool
    updated: int
    failed: int
    skipped: int
    message: str
    results: list[ImageImportRowOut]


@router.post("/images/preview", response_model=ImageImportPreviewOut)
async def preview_image_import(
    connection_id: str,
    manifest: UploadFile = File(..., description="CSV manifest: match,name + filename"),
    images_zip: UploadFile = File(..., description="ZIP of image files"),
    db: Session = Depends(get_db),
) -> ImageImportPreviewOut:
    _client(connection_id, db)
    if not manifest.filename or not images_zip.filename:
        raise HTTPException(status_code=422, detail="manifest CSV and images ZIP required")
    manifest_raw = await manifest.read()
    zip_raw = await images_zip.read()
    if len(zip_raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="ZIP too large (max 50MB)")
    try:
        from app.image_import import build_image_import_preview, parse_image_upload

        rows, image_field, match_field, match_mode, zip_images = parse_image_upload(
            manifest_raw, zip_raw
        )
        preview = build_image_import_preview(
            manifest_rows=rows,
            image_field=image_field,
            match_field=match_field,
            match_mode=match_mode,
            zip_names=set(zip_images.keys()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImageImportPreviewOut(
        row_count=preview.row_count,
        sample_rows=preview.sample_rows,
        image_field=preview.image_field,
        match_field=preview.match_field,
        match_mode=preview.match_mode,
        warnings=preview.warnings,
    )


@router.post("/images/commit", response_model=ImageImportCommitOut)
async def commit_image_import(
    connection_id: str,
    manifest: UploadFile = File(...),
    images_zip: UploadFile = File(...),
    model: str = Form(...),
    match_field: str = Form("x_name"),
    image_field: str = Form(""),
    dry_run: bool = Form(True),
    confirm_advanced: bool = Form(False),
    confirm_phrase: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ImageImportCommitOut:
    if not dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=confirm_advanced,
                confirm_phrase=confirm_phrase,
                warning=f"Bulk image import will write images to {model} on live Odoo.",
                risks=[
                    "Overwrites existing binary/image field data on matched records",
                    "Wrong match column can attach images to incorrect records",
                    "Large images are downscaled but still consume DB space",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    manifest_raw = await manifest.read()
    zip_raw = await images_zip.read()
    try:
        from app.image_import import parse_image_upload, run_image_import

        rows, default_field, _, _, zip_images = parse_image_upload(manifest_raw, zip_raw)
        target_field = (image_field or default_field).strip() or default_field
        client = _client(connection_id, db)
        result = run_image_import(
            client,
            model=model.strip(),
            manifest_rows=rows,
            zip_images=zip_images,
            image_field=target_field,
            match_field=match_field.strip() or "x_name",
            dry_run=dry_run,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ImageImportCommitOut(
        ok=result.ok,
        dry_run=dry_run,
        updated=result.updated,
        failed=result.failed,
        skipped=result.skipped,
        message=result.message,
        results=[
            ImageImportRowOut(
                row_index=r.row_index,
                match_value=r.match_value,
                filename=r.filename,
                ok=r.ok,
                record_id=r.record_id,
                action=r.action,
                error=r.error,
                bytes_in=r.bytes_in,
                bytes_out=r.bytes_out,
            )
            for r in result.results
        ],
    )
