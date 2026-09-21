"""Batch OS API — universal runner, Config Atlas, recipe execute."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.batch_os.atlas.loader import list_atlas, search_atlas
from app.batch_os.parse import parse_upload
from app.batch_os.persistence import public_job_dict
from app.batch_os.recipes.registry import list_recipes, require_recipe
from app.batch_os.runner import job_public, run_phase
from app.batch_os.types import (
    DOCUMENT_COLUMN_TARGETS,
    HONESTY_PREVIEW_NE_POSTED,
    JOURNAL_COLUMN_TARGETS,
    PAYMENT_COLUMN_TARGETS,
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
    prefix="/connections/{connection_id}/batch-os",
    tags=["batch-os"],
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


def _state_out(state) -> dict[str, Any]:
    return public_job_dict(state)


# ── Atlas ─────────────────────────────────────────────────────────────


@router.get("/atlas")
def atlas_list(
    connection_id: str,
    class_id: str | None = Query(None),
) -> dict[str, Any]:
    del connection_id
    return {
        "classes": list_atlas(class_id=class_id),
        "honesty": HONESTY_PREVIEW_NE_POSTED,
    }


@router.get("/atlas/search")
def atlas_search(
    connection_id: str,
    q: str = Query(""),
    class_id: str | None = Query(None),
    risk: str | None = Query(None),
) -> dict[str, Any]:
    del connection_id
    return {"hits": search_atlas(q, class_id=class_id, risk=risk)}


# ── Recipes ───────────────────────────────────────────────────────────


@router.get("/recipes")
def recipes_list(connection_id: str) -> list[dict[str, Any]]:
    del connection_id
    return [c.to_dict() for c in list_recipes()]


class MapBody(BaseModel):
    job_id: str
    column_map: dict[str, str] = Field(default_factory=dict)


class PhaseBody(BaseModel):
    job_id: str


class ApplyBody(ConfirmAdvancedBody):
    job_id: str
    post_after_create: bool = False


class LockDatesBody(ConfirmAdvancedBody):
    period_lock_date: str | None = None
    fiscalyear_lock_date: str | None = None
    tax_lock_date: str | None = None
    dry_run: bool = True


class RecipeExecuteBody(ConfirmAdvancedBody):
    """Generic recipe execute (lock dates / stubs / resume)."""

    dry_run: bool = True
    post_after_create: bool = False
    column_map: dict[str, str] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None
    rows: list[dict[str, str]] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    filename: str = ""


@router.get("/columns")
def journal_columns(connection_id: str) -> dict[str, Any]:
    del connection_id
    return {
        "targets": list(JOURNAL_COLUMN_TARGETS),
        "required": ["account", "debit", "credit"],
        "optional": ["journal", "date", "ref", "label", "partner", "analytic", "move_group"],
        "honesty": HONESTY_PREVIEW_NE_POSTED,
    }


@router.post("/journal/intake")
async def journal_intake(
    connection_id: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    recipe_id: str = Form("accounting.journal_batch"),
) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        headers, rows = parse_upload(raw, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        recipe = require_recipe(recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = run_phase(
        db,
        recipe,
        phase="intake",
        connection_id=connection_id,
        filename=file.filename or "upload.csv",
        headers=headers,
        rows=rows,
    )
    return _state_out(state)


@router.post("/journal/map")
def journal_map(
    connection_id: str,
    body: MapBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    recipe = require_recipe("accounting.journal_batch")
    try:
        state = run_phase(
            db,
            recipe,
            phase="map",
            connection_id=connection_id,
            job_id=body.job_id,
            column_map=body.column_map or None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/journal/validate")
def journal_validate(
    connection_id: str,
    body: PhaseBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client = _client(connection_id, db)
    recipe = require_recipe("accounting.journal_batch")
    try:
        state = run_phase(
            db,
            recipe,
            phase="validate",
            connection_id=connection_id,
            client=client,
            job_id=body.job_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/journal/dry-run")
def journal_dry_run(
    connection_id: str,
    body: PhaseBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client = _client(connection_id, db)
    recipe = require_recipe("accounting.journal_batch")
    try:
        state = run_phase(
            db,
            recipe,
            phase="dry_run",
            connection_id=connection_id,
            client=client,
            job_id=body.job_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/journal/apply")
def journal_apply(
    connection_id: str,
    body: ApplyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client = _client(connection_id, db)
    recipe = require_recipe("accounting.journal_batch")
    risks = [
        "Creates account.move drafts on the live database",
        HONESTY_PREVIEW_NE_POSTED,
    ]
    if body.post_after_create:
        risks.append("Will call action_post (L2) — posted entries are harder to reverse")
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Journal batch apply writes to live Odoo Accounting",
            risks=risks,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    try:
        state = run_phase(
            db,
            recipe,
            phase="apply",
            connection_id=connection_id,
            client=client,
            job_id=body.job_id,
            post_after_create=body.post_after_create,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)




@router.get("/document/columns")
def document_columns(connection_id: str) -> dict[str, Any]:
    del connection_id
    return {
        "targets": list(DOCUMENT_COLUMN_TARGETS),
        "required": ["partner", "qty", "price"],
        "optional": [
            "move_type",
            "date",
            "due",
            "product",
            "account",
            "label",
            "tax",
            "journal",
            "ref",
            "invoice_group",
        ],
        "honesty": HONESTY_PREVIEW_NE_POSTED,
    }


@router.get("/payment/columns")
def payment_columns(connection_id: str) -> dict[str, Any]:
    del connection_id
    return {
        "targets": list(PAYMENT_COLUMN_TARGETS),
        "required": ["amount"],
        "optional": ["move_ref", "partner", "date", "journal", "memo", "payment_type"],
        "honesty": HONESTY_PREVIEW_NE_POSTED,
        "risk": "L2",
    }


def _batch_flow(
    *,
    connection_id: str,
    db: Session,
    recipe_id: str,
    phase: str,
    job_id: str | None = None,
    column_map: dict[str, str] | None = None,
    post_after_create: bool = False,
):
    client = _client(connection_id, db) if phase in {"validate", "dry_run", "apply"} else None
    recipe = require_recipe(recipe_id)
    return run_phase(
        db,
        recipe,
        phase=phase,
        connection_id=connection_id,
        client=client,
        job_id=job_id,
        column_map=column_map,
        post_after_create=post_after_create,
    )


@router.post("/document/intake")
async def document_intake(
    connection_id: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    recipe_id: str = Form("document_batch.invoices"),
) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        headers, rows = parse_upload(raw, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        recipe = require_recipe(recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = run_phase(
        db,
        recipe,
        phase="intake",
        connection_id=connection_id,
        filename=file.filename or "upload.csv",
        headers=headers,
        rows=rows,
    )
    return _state_out(state)


@router.post("/document/map")
def document_map(
    connection_id: str,
    body: MapBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.invoices",
            phase="map",
            job_id=body.job_id,
            column_map=body.column_map or None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/document/validate")
def document_validate(
    connection_id: str,
    body: PhaseBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.invoices",
            phase="validate",
            job_id=body.job_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/document/dry-run")
def document_dry_run(
    connection_id: str,
    body: PhaseBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.invoices",
            phase="dry_run",
            job_id=body.job_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/document/apply")
def document_apply(
    connection_id: str,
    body: ApplyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    risks = [
        "Creates account.move invoice/bill drafts on the live database",
        HONESTY_PREVIEW_NE_POSTED,
    ]
    if body.post_after_create:
        risks.append("Will call action_post (L2) — posted invoices are harder to reverse")
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Invoice/bill batch apply writes to live Odoo Accounting",
            risks=risks,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.invoices",
            phase="apply",
            job_id=body.job_id,
            post_after_create=body.post_after_create,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/payment/intake")
async def payment_intake(
    connection_id: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    recipe_id: str = Form("document_batch.payments"),
) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        headers, rows = parse_upload(raw, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        recipe = require_recipe(recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = run_phase(
        db,
        recipe,
        phase="intake",
        connection_id=connection_id,
        filename=file.filename or "upload.csv",
        headers=headers,
        rows=rows,
    )
    return _state_out(state)


@router.post("/payment/map")
def payment_map(
    connection_id: str,
    body: MapBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.payments",
            phase="map",
            job_id=body.job_id,
            column_map=body.column_map or None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/payment/dry-run")
def payment_dry_run(
    connection_id: str,
    body: PhaseBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.payments",
            phase="dry_run",
            job_id=body.job_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)


@router.post("/payment/apply")
def payment_apply(
    connection_id: str,
    body: ApplyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    risks = [
        "Registers payments against open invoices/bills (L2)",
        "Preview ≠ posted — dry-run first",
        HONESTY_PREVIEW_NE_POSTED,
    ]
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Payment matching writes posted payments on live Odoo",
            risks=risks,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    try:
        state = _batch_flow(
            connection_id=connection_id,
            db=db,
            recipe_id="document_batch.payments",
            phase="apply",
            job_id=body.job_id,
            post_after_create=True,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_out(state)



@router.get("/jobs/{job_id}")
def get_job(connection_id: str, job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = job_public(db, job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if payload.get("connection_id") != connection_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@router.post("/recipes/{recipe_id}/execute")
def recipe_execute(
    connection_id: str,
    recipe_id: str,
    body: RecipeExecuteBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        recipe = require_recipe(recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    risk = getattr(recipe, "risk", "L1")
    if risk in {"L2", "L3"} and not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Recipe {recipe_id} is risk {risk}",
                risks=[
                    f"Risk tier {risk}",
                    getattr(recipe, "blurb", ""),
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    client = None
    if not body.dry_run or recipe_id.startswith("accounting."):
        # validate/dry_run/apply need client for accounting recipes
        try:
            client = _client(connection_id, db)
        except HTTPException:
            if not body.dry_run:
                raise
            client = None

    extras = dict(body.extras)
    if recipe_id == "accounting.lock_dates":
        for key in ("period_lock_date", "fiscalyear_lock_date", "tax_lock_date"):
            if key in extras or getattr(body, key, None):
                pass
        # allow top-level via extras only; LockDatesBody separate endpoint below

    if body.job_id:
        phase = "dry_run" if body.dry_run else "apply"
        if client is None:
            client = _client(connection_id, db)
        try:
            state = run_phase(
                db,
                recipe,
                phase=phase,
                connection_id=connection_id,
                client=client,
                job_id=body.job_id,
                post_after_create=body.post_after_create,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _state_out(state)

    # Fresh intake from inline rows or empty
    state = run_phase(
        db,
        recipe,
        phase="intake",
        connection_id=connection_id,
        filename=body.filename or recipe_id,
        headers=body.headers,
        rows=body.rows,
        extras=extras,
    )
    if body.column_map:
        state = run_phase(
            db,
            recipe,
            phase="map",
            connection_id=connection_id,
            job_id=state.job_id,
            column_map=body.column_map,
        )
    if client is None and recipe_id.startswith("accounting."):
        client = _client(connection_id, db)
    if client is not None:
        phase = "dry_run" if body.dry_run else "apply"
        state = run_phase(
            db,
            recipe,
            phase=phase,
            connection_id=connection_id,
            client=client,
            job_id=state.job_id,
            post_after_create=body.post_after_create and recipe_id in {"accounting.journal_batch", "document_batch.invoices"},
        )
    return _state_out(state)


@router.post("/recipes/accounting.lock_dates")
def lock_dates_execute(
    connection_id: str,
    body: LockDatesBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    recipe = require_recipe("accounting.lock_dates")
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning="Lock dates (L3) block posting in closed periods",
                risks=[
                    "Sets period_lock_date / fiscalyear_lock_date / tax_lock_date on res.company",
                    "Can block legitimate posting until dates are cleared",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    client = _client(connection_id, db)
    extras = {
        "period_lock_date": body.period_lock_date,
        "fiscalyear_lock_date": body.fiscalyear_lock_date,
        "tax_lock_date": body.tax_lock_date,
    }
    state = run_phase(
        db,
        recipe,
        phase="intake",
        connection_id=connection_id,
        filename="lock_dates",
        headers=[],
        rows=[],
        extras=extras,
    )
    phase = "dry_run" if body.dry_run else "apply"
    state = run_phase(
        db,
        recipe,
        phase=phase,
        connection_id=connection_id,
        client=client,
        job_id=state.job_id,
    )
    return _state_out(state)
