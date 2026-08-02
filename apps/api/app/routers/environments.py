"""Multi-env promote pipelines: ephemeral sandbox → staging → Online prod."""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from module_generator import zip_technical_name

from app.db import get_db
from app.db_models import EnvPipeline, PipelineHop, PromotedModule
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.promote import (
    get_valid_validation,
    promote_module_zip,
    record_sandbox_validation,
    sha256_bytes,
)
from app.sandbox import resolve_sandbox_major, run_sandbox_install
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from app.zip_safety import validate_zip_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


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


class PipelineOut(BaseModel):
    id: str
    name: str
    staging_connection_id: str
    prod_connection_id: str
    sandbox_connection_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CreatePipelineBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    staging_connection_id: str
    prod_connection_id: str
    sandbox_connection_id: str | None = None


class HopOut(BaseModel):
    id: str
    pipeline_id: str
    hop: str
    module_name: str
    zip_sha256: str
    connection_id: str | None
    validation_id: str | None
    status: str
    message: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PipelinePromoteBody(ConfirmAdvancedBody):
    hop: Literal["sandbox", "staging", "prod"]
    zip_base64: str
    # For staging/prod after ephemeral sandbox: pass validation_id from sandbox hop
    validation_id: str | None = None
    install_mode: str | None = None  # filesystem | data — promote decides by target


class PipelinePromoteOut(BaseModel):
    ok: bool
    hop: str
    module_name: str
    zip_sha256: str
    validation_id: str | None = None
    message: str
    hop_record_id: str | None = None
    promote_method: str | None = None


@router.get("", response_model=list[PipelineOut])
def list_pipelines(db: Session = Depends(get_db)) -> list[PipelineOut]:
    rows = db.query(EnvPipeline).order_by(EnvPipeline.created_at.desc()).all()
    return [PipelineOut.model_validate(r) for r in rows]


@router.post("", response_model=PipelineOut, status_code=201)
def create_pipeline(
    body: CreatePipelineBody, db: Session = Depends(get_db)
) -> PipelineOut:
    for cid in (
        body.staging_connection_id,
        body.prod_connection_id,
        body.sandbox_connection_id,
    ):
        if not cid:
            continue
        try:
            get_connection_or_404(db, cid)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.staging_connection_id == body.prod_connection_id:
        raise HTTPException(
            status_code=422, detail="staging and prod connections must differ"
        )
    row = EnvPipeline(
        name=body.name,
        staging_connection_id=body.staging_connection_id,
        prod_connection_id=body.prod_connection_id,
        sandbox_connection_id=body.sandbox_connection_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return PipelineOut.model_validate(row)


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: str, db: Session = Depends(get_db)) -> PipelineOut:
    row = db.get(EnvPipeline, pipeline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return PipelineOut.model_validate(row)


@router.get("/{pipeline_id}/hops", response_model=list[HopOut])
def list_hops(pipeline_id: str, db: Session = Depends(get_db)) -> list[HopOut]:
    if not db.get(EnvPipeline, pipeline_id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    rows = (
        db.query(PipelineHop)
        .filter(PipelineHop.pipeline_id == pipeline_id)
        .order_by(PipelineHop.created_at.desc())
        .limit(100)
        .all()
    )
    return [HopOut.model_validate(r) for r in rows]


@router.delete("/{pipeline_id}")
def delete_pipeline(pipeline_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(EnvPipeline, pipeline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": pipeline_id}


def _decode_zip(zip_b64: str) -> bytes:
    try:
        raw = base64.b64decode(zip_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid zip_base64: {exc}") from exc
    try:
        validate_zip_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return raw


@router.post("/{pipeline_id}/promote", response_model=PipelinePromoteOut)
def promote_hop(
    pipeline_id: str, body: PipelinePromoteBody, db: Session = Depends(get_db)
) -> PipelinePromoteOut:
    pipeline = db.get(EnvPipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Multi-env promote hop={body.hop!r} installs a module zip onto the "
                f"target Odoo for this pipeline."
            ),
            risks=[
                "Installs/upgrades code or data modules on the target database",
                "Prod hop requires a prior successful staging hop for the same zip sha256",
                "Sandbox hop uses ephemeral Docker (or sandbox connection) — not customer prod",
                "Failed mid-hop leaves partial state — check Odoo Apps / Change journal",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    zip_bytes = _decode_zip(body.zip_base64)
    digest = sha256_bytes(zip_bytes)
    try:
        module_name = zip_technical_name(zip_bytes)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Cannot read module name: {exc}") from exc

    if body.hop == "sandbox":
        return _hop_sandbox(db, pipeline, zip_bytes, digest, module_name)

    if body.hop == "staging":
        return _hop_target(
            db,
            pipeline,
            hop="staging",
            connection_id=pipeline.staging_connection_id,
            zip_bytes=zip_bytes,
            digest=digest,
            module_name=module_name,
            validation_id=body.validation_id,
            require_prior_hop=None,
        )

    if body.hop == "prod":
        prior = (
            db.query(PipelineHop)
            .filter(
                PipelineHop.pipeline_id == pipeline_id,
                PipelineHop.hop == "staging",
                PipelineHop.zip_sha256 == digest,
                PipelineHop.status == "succeeded",
            )
            .first()
        )
        if not prior:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Prod promote requires a successful staging hop for this exact zip "
                    f"(sha256={digest[:12]}…)"
                ),
            )
        return _hop_target(
            db,
            pipeline,
            hop="prod",
            connection_id=pipeline.prod_connection_id,
            zip_bytes=zip_bytes,
            digest=digest,
            module_name=module_name,
            validation_id=body.validation_id or prior.validation_id,
            require_prior_hop="staging",
        )

    raise HTTPException(status_code=422, detail=f"Unknown hop {body.hop}")


def _record_hop(
    db: Session,
    *,
    pipeline_id: str,
    hop: str,
    module_name: str,
    digest: str,
    connection_id: str | None,
    validation_id: str | None,
    status: str,
    message: str,
) -> PipelineHop:
    row = PipelineHop(
        pipeline_id=pipeline_id,
        hop=hop,
        module_name=module_name,
        zip_sha256=digest,
        connection_id=connection_id,
        validation_id=validation_id,
        status=status,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _pipeline_sandbox_major(db: Session, pipeline: EnvPipeline) -> int:
    """Resolve ephemeral sandbox image major from pipeline connections (matching-major).

    Prefer staging, then prod, then optional sandbox connection ``server_version``.
    Falls back to 19 when unknown.
    """
    from odoo_client.compat import UnsupportedOdooMajorError, parse_major

    for cid in (
        pipeline.staging_connection_id,
        pipeline.prod_connection_id,
        pipeline.sandbox_connection_id,
    ):
        if not cid:
            continue
        try:
            row = get_connection_or_404(db, cid)
        except LookupError:
            continue
        sv = getattr(row, "server_version", None) or ""
        if not sv:
            continue
        try:
            return resolve_sandbox_major(parse_major(str(sv)))
        except (UnsupportedOdooMajorError, ValueError, TypeError):
            continue
    return 19


def _hop_sandbox(
    db: Session,
    pipeline: EnvPipeline,
    zip_bytes: bytes,
    digest: str,
    module_name: str,
) -> PipelinePromoteOut:
    # Prefer ephemeral Docker sandbox for isolation; optional dedicated connection noted.
    major = _pipeline_sandbox_major(db, pipeline)
    result = run_sandbox_install(
        zip_bytes,
        module_name=module_name,
        keep_alive=False,
        odoo_major=major,
    )
    if not result.ok:
        hop = _record_hop(
            db,
            pipeline_id=pipeline.id,
            hop="sandbox",
            module_name=module_name,
            digest=digest,
            connection_id=pipeline.sandbox_connection_id,
            validation_id=None,
            status="failed",
            message=result.message,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "message": result.message,
                "log_tail": result.log_tail,
                "hop_record_id": hop.id,
            },
        )
    # Tie validation to staging connection so staging promote can consume it
    validation = record_sandbox_validation(
        db,
        connection_id=pipeline.staging_connection_id,
        module_name=result.module or module_name,
        zip_bytes=zip_bytes,
    )
    hop = _record_hop(
        db,
        pipeline_id=pipeline.id,
        hop="sandbox",
        module_name=result.module or module_name,
        digest=digest,
        connection_id=pipeline.sandbox_connection_id,
        validation_id=validation.id,
        status="succeeded",
        message=result.message,
    )
    return PipelinePromoteOut(
        ok=True,
        hop="sandbox",
        module_name=result.module or module_name,
        zip_sha256=digest,
        validation_id=validation.id,
        message=result.message,
        hop_record_id=hop.id,
    )


def _hop_target(
    db: Session,
    pipeline: EnvPipeline,
    *,
    hop: str,
    connection_id: str,
    zip_bytes: bytes,
    digest: str,
    module_name: str,
    validation_id: str | None,
    require_prior_hop: str | None,
) -> PipelinePromoteOut:
    _ = require_prior_hop
    from app.db_models import SandboxValidation
    from app.promote import consume_validation

    if hop == "staging":
        if validation_id:
            try:
                get_valid_validation(
                    db,
                    validation_id=validation_id,
                    connection_id=connection_id,
                    zip_bytes=zip_bytes,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            sandbox = run_sandbox_install(
                zip_bytes,
                module_name=module_name,
                keep_alive=False,
                odoo_major=_pipeline_sandbox_major(db, pipeline),
            )
            if not sandbox.ok:
                hop_row = _record_hop(
                    db,
                    pipeline_id=pipeline.id,
                    hop=hop,
                    module_name=module_name,
                    digest=digest,
                    connection_id=connection_id,
                    validation_id=None,
                    status="failed",
                    message=sandbox.message,
                )
                raise HTTPException(
                    status_code=400,
                    detail={
                        "ok": False,
                        "message": sandbox.message,
                        "hop_record_id": hop_row.id,
                    },
                )
            validation = record_sandbox_validation(
                db,
                connection_id=connection_id,
                module_name=sandbox.module or module_name,
                zip_bytes=zip_bytes,
            )
            validation_id = validation.id
            module_name = sandbox.module or module_name
    else:
        # prod: staging hop already verified by caller; mint prod-scoped validation
        validation = record_sandbox_validation(
            db,
            connection_id=connection_id,
            module_name=module_name,
            zip_bytes=zip_bytes,
        )
        validation_id = validation.id

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        result = promote_module_zip(client, zip_bytes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        hop_row = _record_hop(
            db,
            pipeline_id=pipeline.id,
            hop=hop,
            module_name=module_name,
            digest=digest,
            connection_id=connection_id,
            validation_id=validation_id,
            status="failed",
            message=str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "message": str(exc), "hop_record_id": hop_row.id},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("pipeline promote failed")
        hop_row = _record_hop(
            db,
            pipeline_id=pipeline.id,
            hop=hop,
            module_name=module_name,
            digest=digest,
            connection_id=connection_id,
            validation_id=validation_id,
            status="failed",
            message=str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "message": str(exc), "hop_record_id": hop_row.id},
        ) from exc

    if validation_id:
        row = db.get(SandboxValidation, validation_id)
        if row:
            consume_validation(db, row)

    if result.ok:
        db.add(
            PromotedModule(
                connection_id=connection_id,
                module_name=result.module,
                method=result.method,
                zip_sha256=digest,
                status="installed",
            )
        )
        db.commit()

    hop_row = _record_hop(
        db,
        pipeline_id=pipeline.id,
        hop=hop,
        module_name=result.module,
        digest=digest,
        connection_id=connection_id,
        validation_id=validation_id,
        status="succeeded" if result.ok else "failed",
        message=result.message,
    )
    if not result.ok:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "message": result.message,
                "hop_record_id": hop_row.id,
            },
        )
    return PipelinePromoteOut(
        ok=True,
        hop=hop,
        module_name=result.module,
        zip_sha256=digest,
        validation_id=validation_id,
        message=result.message,
        hop_record_id=hop_row.id,
        promote_method=result.method,
    )
