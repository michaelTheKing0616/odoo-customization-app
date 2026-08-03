"""Apply ModuleSpec JSON + Code→ModuleSpec import."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.module_import import import_module_archive
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    ModuleSpecApplyBody,
    ModuleSpecApplyOut,
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
from app.spec_apply_ui import apply_module_spec_ui

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


@router.post("/apply", response_model=ModuleSpecApplyOut)
def apply_module_spec(
    connection_id: str,
    body: ModuleSpecApplyBody,
    db: Session = Depends(get_db),
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
        spec_clean, pcm_skips = scrub_spec_for_protected_apply(body.spec, manifest)
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
