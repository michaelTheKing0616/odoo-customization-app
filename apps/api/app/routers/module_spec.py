"""Apply ModuleSpec JSON + Code→ModuleSpec import."""

from __future__ import annotations

import copy
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.module_import import import_module_archive
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    ModuleSpecApplyBody,
    ModuleSpecApplyOut,
    ModuleSpecImportJsonBody,
    ModuleSpecImportOut,
    ModuleSpecValidateLiveBody,
    ValidateLiveItemOut,
    ValidateLiveOut,
)
from app.spec_validate_live import validate_module_spec_live
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from app.protected_enforcement import manifest_for_connection, scrub_spec_for_protected_apply
from app.ai_apply_readiness import prepare_spec_for_live_apply
from app.spec_apply_ui import apply_module_spec_ui
from app.mutation_lock_dep import require_connection_mutation_lock
from app.custom_code_authoring import lint_custom_code_blocks, model_class_skeleton
from app.module_spec_codec import export_draft_module_zip
from app.workspace_auth import WorkspaceAuth, require_app_auth
from app.code_studio_gating import assert_code_studio_entitlement, assert_developer_role
from app.mutation_lock_dep import require_connection_mutation_lock

router = APIRouter(
    prefix="/connections/{connection_id}/module-spec",
    tags=["module-spec"],
)

# Parse-only import (no live Odoo writes)
import_router = APIRouter(prefix="/module-spec", tags=["module-spec"])


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


@import_router.post("/import", response_model=ModuleSpecImportOut)
async def import_module_spec_file(
    file: UploadFile = File(..., description="Odoo module zip, .meta.json, .py, or .xml"),
) -> ModuleSpecImportOut:
    """Parse third-party / own module code into ModuleSpec (no Odoo writes)."""
    if not file.filename:
        raise HTTPException(status_code=422, detail="filename required")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty file")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 25MB)")
    try:
        result = import_module_archive(raw, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc

    payload = result.as_dict()
    return ModuleSpecImportOut(
        ok=True,
        spec=payload,
        warnings=result.warnings,
        unmapped=result.unmapped,
        custom_code_blocks=list(payload.get("custom_code_blocks") or []),
        source=result.source,
    )


@import_router.post("/import-json", response_model=ModuleSpecImportOut)
def import_module_spec_json(body: ModuleSpecImportJsonBody) -> ModuleSpecImportOut:
    """Accept pasted ModuleSpec JSON — optional apply-readiness prep, no Odoo writes."""
    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(
            status_code=422,
            detail="spec.models must be a non-empty list",
        )
    spec = copy.deepcopy(body.spec)
    warnings: list[str] = []
    if body.prepare:
        spec, prep_notes = prepare_spec_for_live_apply(spec)
        warnings.extend(prep_notes)
    blocks = list(spec.get("custom_code_blocks") or [])
    return ModuleSpecImportOut(
        ok=True,
        spec=spec,
        warnings=warnings,
        unmapped=[],
        custom_code_blocks=blocks,
        source="json_paste",
        note=(
            "JSON loaded into ModuleSpec — click Apply to Odoo on a connection "
            "or open the visual editor."
        ),
    )


@router.post("/validate-live", response_model=ValidateLiveOut)
def validate_live_module_spec(
    connection_id: str,
    body: ModuleSpecValidateLiveBody,
    db: Session = Depends(get_db),
) -> ValidateLiveOut:
    """Read-only pre-apply checks against the live Odoo instance."""
    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(status_code=422, detail="spec.models must be a non-empty list")
    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        result = validate_module_spec_live(client, body.spec)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ValidateLiveOut(
        ok=result.ok,
        items=[
            ValidateLiveItemOut(
                item_id=i.item_id,
                category=i.category,
                status=i.status,
                message=i.message,
            )
            for i in result.items
        ],
        fail_count=result.fail_count,
        warn_count=result.warn_count,
        message=result.message,
    )


class LintBlocksBody(BaseModel):
    spec: dict


class ExportSandboxBody(BaseModel):
    spec: dict
    async_job: bool = True
    odoo_major: int | None = None


class SkeletonBody(BaseModel):
    spec: dict
    model: str


@router.post("/lint-blocks")
def lint_blocks_route(
    connection_id: str,
    body: LintBlocksBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    get_connection_or_404(db, connection_id)
    return lint_custom_code_blocks(body.spec)


@router.post("/skeleton")
def model_skeleton_route(
    connection_id: str,
    body: SkeletonBody,
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    assert_developer_role(auth)
    return {"model": body.model, "code": model_class_skeleton(body.spec, body.model)}


@router.post("/export-sandbox")
def export_sandbox_from_draft(
    connection_id: str,
    body: ExportSandboxBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """DEV-2 — export draft ModuleSpec zip and run sandbox gate."""
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    lint = lint_custom_code_blocks(body.spec)
    if not lint.get("ok"):
        raise HTTPException(status_code=422, detail={"lint_failed": True, **lint})
    import base64

    from app.jobs import create_job, enqueue
    from app.sandbox import resolve_sandbox_major, run_sandbox_install
    from app.promote import record_sandbox_validation, sha256_bytes

    major = body.odoo_major or resolve_sandbox_major(conn.server_version)
    zip_bytes = export_draft_module_zip(body.spec, odoo_major=major)
    zip_b64 = base64.b64encode(zip_bytes).decode("ascii")
    tech = str(body.spec.get("technical_name") or "custom_module")

    if not body.async_job:
        result = run_sandbox_install(
            zip_bytes=zip_bytes,
            technical_name=tech,
            odoo_major=major,
            extra_modules=list(body.spec.get("depends") or []),
        )
        if not result.get("ok"):
            return {"ok": False, "lint": lint, "sandbox": result}
        validation_id = record_sandbox_validation(
            db,
            connection_id=connection_id,
            zip_sha256=sha256_bytes(zip_bytes),
            message=result.get("message", "ok"),
        )
        return {
            "ok": True,
            "lint": lint,
            "validation_id": validation_id,
            "zip_base64": zip_b64,
            "sandbox": result,
        }

    job = create_job(db, kind="sandbox", connection_id=connection_id)

    def _work() -> dict:
        result = run_sandbox_install(
            zip_bytes=zip_bytes,
            technical_name=tech,
            odoo_major=major,
            job_id=job.id,
            extra_modules=list(body.spec.get("depends") or []),
        )
        from app.db import SessionLocal

        wdb = SessionLocal()
        try:
            validation_id = None
            if result.get("ok"):
                validation_id = record_sandbox_validation(
                    wdb,
                    connection_id=connection_id,
                    zip_sha256=sha256_bytes(zip_bytes),
                    message=result.get("message", "ok"),
                )
        finally:
            wdb.close()
        return {
            "ok": bool(result.get("ok")),
            "validation_id": validation_id,
            "zip_base64": zip_b64,
            "sandbox": result,
            "lint": lint,
        }

    enqueue(job.id, _work)
    return {"ok": True, "job_id": job.id, "lint": lint, "message": "Sandbox job queued"}


@router.post("/apply", response_model=ModuleSpecApplyOut)
def apply_module_spec(
    connection_id: str,
    body: ModuleSpecApplyBody,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(require_connection_mutation_lock)] = None,
) -> ModuleSpecApplyOut:
    """Generate UI from ModuleSpec JSON (models, fields, views, menus, smart buttons)."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Generate UI from JSON creates models, fields, views, menus, and "
                "safe automations on the live Odoo database. Prefer a sandbox connection first."
            ),
            risks=[
                "Creates ir.model / ir.model.fields / ir.ui.view / ir.ui.menu",
                "May rewrite primary form arches for custom x_* models (statusbars)",
                "Smart buttons use inherit views (stock forms like Contacts stay intact)",
                "Safe automations (update_field / related_write / activity) are created live",
                "Does not fully roll back if a later step fails",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(
            status_code=422, detail="spec.models must be a non-empty list"
        )

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        validation = validate_module_spec_live(client, body.spec)
        if not validation.ok and not body.skip_validate_live:
            raise HTTPException(
                status_code=422,
                detail={
                    "validate_live_failed": True,
                    "fail_count": validation.fail_count,
                    "warn_count": validation.warn_count,
                    "message": validation.message,
                    "items": [
                        {
                            "item_id": i.item_id,
                            "category": i.category,
                            "status": i.status,
                            "message": i.message,
                        }
                        for i in validation.items
                        if i.status == "fail"
                    ],
                },
            )
        if not validation.ok and body.skip_validate_live:
            try:
                require_advanced_confirmation(
                    confirm_advanced=body.confirm_advanced,
                    confirm_phrase=body.confirm_phrase,
                    warning=(
                        "Apply despite validate-live failures — live Odoo may reject writes "
                        "or produce broken views."
                    ),
                    risks=[
                        f"{validation.fail_count} validate-live check(s) failed",
                        "Partial apply may leave inconsistent metadata",
                        "Prefer fixing the draft or re-running validate-live",
                    ],
                )
            except ConfirmationRequired as exc:
                raise _confirm_http(exc) from exc
        manifest = manifest_for_connection(conn)
        spec_prepared, prep_notes = prepare_spec_for_live_apply(body.spec)
        spec_clean, pcm_skips = scrub_spec_for_protected_apply(spec_prepared, manifest)
        result = apply_module_spec_ui(
            client,
            spec_clean,
            apply_views=body.apply_views,
            apply_menus=body.apply_menus,
            apply_smart_buttons=body.apply_smart_buttons,
            apply_automations=body.apply_automations,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skipped = list(result.skipped) + pcm_skips
    warnings = list(result.warnings)
    if prep_notes:
        warnings.append(f"Live prep: {len(prep_notes)} readiness adjustment(s)")
    if pcm_skips:
        warnings.append(f"PCM: skipped {len(pcm_skips)} protected item(s)")

    return ModuleSpecApplyOut(
        ok=True,
        models_created=result.models_created,
        fields_created=result.fields_created,
        views_created=result.views_created,
        views_updated=result.views_updated,
        menus_created=result.menus_created,
        smart_buttons=result.smart_buttons,
        automations_created=result.automations_created,
        skipped=skipped,
        warnings=warnings,
        message=result.message,
    )
