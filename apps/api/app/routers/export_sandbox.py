"""Phase 5 export + Phase 6 sandbox + promote endpoints."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import PromotedModule, SandboxValidation
from app.export_service import export_connection_module_zip
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.module_inspect import extract_model_names_from_zip
from app.promote import (
    consume_validation,
    get_valid_validation,
    promote_module_zip,
    record_sandbox_validation,
    sha256_bytes,
)
from app.sandbox import resolve_sandbox_major, run_sandbox_install
from app.zip_safety import validate_zip_bytes
from app.schemas import (
    DeploymentPanelOut,
    ExportModuleBody,
    ModuleExportOut,
    PromoteModuleBody,
    PromoteModuleOut,
    PromotedModuleOut,
    SandboxRunBody,
    SandboxRunOut,
    StoreReadinessItemOut,
    StoreReadinessReportOut,
    SuggestDependsOut,
    UninstallModuleBody,
    UninstallModuleOut,
)
from app.store_packaging import apply_store_packaging
from app.snapshots import ConfirmationRequired, require_advanced_confirmation
from app.capabilities import probe_web_base_url, sample_installed_modules
from app.deploy_odoo_sh import deploy_odoo_sh_markdown, inject_file_into_zip
from app.hosting import hosting_hint_from_url
from app.tier_gating import (
    deployment_panel,
    gating_context_for_connection,
    online_python_promote_gating,
    sandbox_approximation_label,
    sh_staging_suggestion,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections/{connection_id}", tags=["export-sandbox"])

PROMOTE_WARNING = (
    "Installing a module on this Odoo connection changes live metadata and may add "
    "models, fields, views, and access rules. Uninstall may not fully reverse data."
)
PROMOTE_RISKS = [
    "New models/fields persist until uninstall (data rows may remain)",
    "View overrides can affect existing users immediately",
    "Python modules require filesystem access (local Docker) or data-mode export",
    "Only promote zips that passed sandbox validation",
]

UNINSTALL_WARNING = (
    "Uninstalling a module removes its data files and may drop models/fields. "
    "Business records created while the module was installed can remain or become orphaned."
)
UNINSTALL_RISKS = [
    "Tables/columns may remain depending on Odoo uninstall behavior",
    "Related views, automations, and ACL from the module are removed",
    "This cannot always be fully rolled back without a DB backup",
]


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _sandbox_honesty(
    db: Session,
    *,
    connection_id: str,
    odoo_major: int | None,
) -> dict[str, Any]:
    from app.db_models import OdooConnection

    row = db.get(OdooConnection, connection_id)
    if row is None:
        return {
            "approximation": False,
            "approximation_label": None,
            "sh_staging_suggestion": None,
        }
    ctx = gating_context_for_connection(url=row.url, server_version=row.server_version)
    approximation = ctx.hosting == "online"
    approx_label = sandbox_approximation_label(odoo_major) if approximation else None
    sh_sibling = (
        db.query(OdooConnection)
        .filter(OdooConnection.id != connection_id)
        .all()
    )
    other_sh = next(
        (r for r in sh_sibling if hosting_hint_from_url(r.url) == "odoo_sh"),
        None,
    )
    staging_hint = None
    if approximation and other_sh is not None:
        staging_hint = sh_staging_suggestion(has_other_sh=True, other_sh_name=other_sh.name)
    return {
        "approximation": approximation,
        "approximation_label": approx_label,
        "sh_staging_suggestion": staging_hint,
    }


def _sandbox_honesty(
    db: Session,
    *,
    connection_id: str,
    odoo_major: int | None,
) -> dict[str, Any]:
    from app.db_models import OdooConnection

    row = db.get(OdooConnection, connection_id)
    if row is None:
        return {
            "approximation": False,
            "approximation_label": None,
            "sh_staging_suggestion": None,
        }
    ctx = gating_context_for_connection(url=row.url, server_version=row.server_version)
    approximation = ctx.hosting == "online"
    approx_label = sandbox_approximation_label(odoo_major) if approximation else None
    sh_sibling = (
        db.query(OdooConnection)
        .filter(OdooConnection.id != connection_id)
        .all()
    )
    other_sh = next(
        (r for r in sh_sibling if hosting_hint_from_url(r.url) == "odoo_sh"),
        None,
    )
    staging_hint = None
    if approximation and other_sh is not None:
        staging_hint = sh_staging_suggestion(has_other_sh=True, other_sh_name=other_sh.name)
    return {
        "approximation": approximation,
        "approximation_label": approx_label,
        "sh_staging_suggestion": staging_hint,
    }


def _connection_odoo_major(connection_id: str, db: Session) -> int:
    """Major for matching-major sandbox from stored server_version (default 19)."""
    from odoo_client.compat import UnsupportedOdooMajorError, parse_major

    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    sv = getattr(row, "server_version", None) or ""
    if not sv:
        return 19
    try:
        return resolve_sandbox_major(parse_major(str(sv)))
    except (UnsupportedOdooMajorError, ValueError, TypeError):
        return 19


@router.get("/suggest-depends", response_model=SuggestDependsOut)
def suggest_depends(connection_id: str, db: Session = Depends(get_db)) -> SuggestDependsOut:
    """Suggest module depends from live M2O/O2M/M2M relation targets."""
    from module_generator import MODEL_TO_MODULE

    client = _client(connection_id, db)
    suggested: list[str] = []
    from_relations: list[str] = []

    def _add(mod: str | None) -> None:
        if not mod or mod in suggested:
            return
        suggested.append(mod)

    _add("base")
    try:
        customs = client.list_models(custom_only=True, limit=200)
        for m in customs:
            for f in client.list_fields(m.model):
                if not f.relation:
                    continue
                from_relations.append(f"{m.model}.{f.name}->{f.relation}")
                mod = MODEL_TO_MODULE.get(f.relation)
                if mod:
                    _add(mod)
                elif f.relation.startswith("mail."):
                    _add("mail")
    except Exception as exc:  # noqa: BLE001
        return SuggestDependsOut(
            suggested=suggested,
            from_relations=from_relations,
            message=f"Partial suggest: {exc}",
        )
    return SuggestDependsOut(
        suggested=suggested,
        from_relations=from_relations[:50],
        message=f"{len(suggested)} module(s) suggested from relation targets",
    )


def _resolve_zip(
    connection_id: str,
    db: Session,
    *,
    zip_base64: str | None,
    technical_name: str | None,
    display_name: str | None,
    include_custom_models: bool,
    include_views: bool,
    model_filter: list[str] | None,
    install_mode: str = "python",
    include_extensions: bool = True,
    extend_models: list[str] | None = None,
    depends: list[str] | None = None,
) -> tuple[bytes, str]:
    if zip_base64:
        try:
            zip_bytes = base64.b64decode(zip_base64)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Invalid zip_base64: {exc}") from exc
        try:
            validate_zip_bytes(zip_bytes)
        except ValueError as exc:
            detail = str(exc)
            lower = detail.lower()
            if (
                "too large" in lower
                or "zip-bomb" in lower
                or "too many files" in lower
            ):
                raise HTTPException(status_code=413, detail=detail) from exc
            raise HTTPException(status_code=400, detail=detail) from exc
        from module_generator import zip_technical_name

        return zip_bytes, technical_name or zip_technical_name(zip_bytes)

    if not technical_name or not display_name:
        raise HTTPException(
            status_code=422,
            detail="Provide technical_name + display_name to export, or zip_base64",
        )
    client = _client(connection_id, db)
    try:
        zip_bytes, spec, _warnings = export_connection_module_zip(
            client,
            technical_name=technical_name,
            display_name=display_name,
            include_custom_models=include_custom_models,
            include_extensions=include_extensions,
            include_views=include_views,
            model_filter=model_filter,
            extend_models=extend_models,
            depends=depends,
            install_mode=install_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not spec.models and not spec.views and not spec.python_automations:
        raise HTTPException(status_code=400, detail="Nothing to package — no custom models/views")
    return zip_bytes, spec.technical_name


@router.post("/export-module", response_model=ModuleExportOut)
def export_module(
    connection_id: str,
    body: ExportModuleBody,
    store_ready: bool = Query(False, description="Apps Store packaging assist"),
    db: Session = Depends(get_db),
) -> ModuleExportOut:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    client = _client(connection_id, db)
    try:
        zip_bytes, spec, warnings = export_connection_module_zip(
            client,
            technical_name=body.technical_name,
            display_name=body.display_name,
            include_custom_models=body.include_custom_models,
            include_extensions=body.include_extensions,
            include_views=body.include_views,
            model_filter=body.model_filter,
            extend_models=body.extend_models,
            depends=body.depends,
            install_mode=body.install_mode,
            include_reports=body.include_reports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not spec.models and not spec.views and not spec.python_automations and not spec.reports:
        raise HTTPException(
            status_code=400,
            detail="Nothing to export — create custom x_* models first or pass zip_base64 to sandbox",
        )

    major = int(getattr(client.capabilities, "major", 19) or 19)
    ctx = gating_context_for_connection(url=row.url, server_version=row.server_version)
    panel_data = deployment_panel(ctx, technical_name=spec.technical_name)
    if ctx.hosting == "sh":
        doc = deploy_odoo_sh_markdown(
            technical_name=spec.technical_name,
            display_name=spec.display_name or spec.technical_name,
            odoo_major=major,
        )
        zip_bytes = inject_file_into_zip(
            zip_bytes,
            f"{spec.technical_name}/DEPLOY_ODOO_SH.md",
            doc,
        )
        warnings = list(warnings) + ["DEPLOY_ODOO_SH.md included in zip for Odoo.sh Git deploy."]
    panel = DeploymentPanelOut(**panel_data)
    store_report: StoreReadinessReportOut | None = None
    if store_ready or body.store_ready:
        zip_bytes, _, report_dict = apply_store_packaging(
            zip_bytes, spec, major=major
        )
        store_report = StoreReadinessReportOut(
            ok=bool(report_dict.get("ok")),
            items=[
                StoreReadinessItemOut(**item) for item in report_dict.get("items") or []
            ],
            fail_count=int(report_dict.get("fail_count") or 0),
            warn_count=int(report_dict.get("warn_count") or 0),
            disclaimer=str(report_dict.get("disclaimer") or ""),
            message=str(report_dict.get("message") or ""),
        )
        warnings = list(warnings) + [
            f"Store-ready packaging applied — {store_report.message} (see STORE_READINESS.json in zip)",
        ]
    return ModuleExportOut(
        technical_name=spec.technical_name,
        filename=f"{spec.technical_name}.zip",
        content_base64=base64.b64encode(zip_bytes).decode("ascii"),
        note=(
            f"Installable Odoo {major} addon zip (manifest {spec.version}, "
            f"mode={spec.install_mode}). One zip per connection major — "
            "validate via sandbox/run (matching-major ephemeral Docker on :18069) "
            "before promote."
        ),
        model_count=len(spec.models),
        view_count=len(spec.views),
        report_count=len(spec.reports),
        target_major=major,
        manifest_version=spec.version,
        warnings=warnings,
        deployment_panel=panel,
        store_readiness=store_report,
    )


@router.post("/sandbox/run", response_model=SandboxRunOut)
def sandbox_run(
    connection_id: str, body: SandboxRunBody, db: Session = Depends(get_db)
) -> SandboxRunOut:
    """Spin ephemeral matching-major Odoo, install module zip, tear down (unless keep_alive)."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    zip_bytes, module_name = _resolve_zip(
        connection_id,
        db,
        zip_base64=body.zip_base64,
        technical_name=body.technical_name,
        display_name=body.display_name,
        include_custom_models=body.include_custom_models,
        include_extensions=body.include_extensions,
        include_views=body.include_views,
        model_filter=body.model_filter,
        extend_models=body.extend_models,
        depends=body.depends,
        install_mode="python",  # sandbox always uses filesystem Python addons
    )

    # Explicit body.extra_modules wins; otherwise settings / SANDBOX_EXTRA_MODULES.
    sandbox_extras = body.extra_modules
    try:
        odoo_major = (
            resolve_sandbox_major(body.odoo_major)
            if body.odoo_major is not None
            else _connection_odoo_major(connection_id, db)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if body.async_job:
        from app.jobs import create_job, enqueue

        job = create_job(db, kind="sandbox", connection_id=connection_id)
        keep_alive = body.keep_alive
        conn_id = connection_id
        zip_copy = zip_bytes
        mod = module_name
        extras = sandbox_extras
        major = odoo_major

        def _work() -> dict:
            from app.db import SessionLocal
            from app.promote import record_sandbox_validation
            from app.sandbox import run_sandbox_install

            result = run_sandbox_install(
                zip_copy,
                module_name=mod,
                keep_alive=keep_alive,
                extra_modules=extras,
                odoo_major=major,
            )
            out: dict = {
                "ok": result.ok,
                "module": result.module,
                "message": result.message,
                "log_tail": result.log_tail,
                "sandbox_url": result.sandbox_url,
                "odoo_major": result.odoo_major,
                "validation_id": None,
                "zip_sha256": None,
                "zip_base64": None,
            }
            if result.ok:
                sdb = SessionLocal()
                try:
                    validation = record_sandbox_validation(
                        sdb,
                        connection_id=conn_id,
                        module_name=result.module,
                        zip_bytes=zip_copy,
                    )
                    out["validation_id"] = validation.id
                    out["zip_sha256"] = validation.zip_sha256
                    out["zip_base64"] = base64.b64encode(zip_copy).decode("ascii")
                finally:
                    sdb.close()
            return out

        enqueue(job.id, _work)
        honesty = _sandbox_honesty(db, connection_id=connection_id, odoo_major=odoo_major)
        return SandboxRunOut(
            ok=True,
            module=module_name,
            message=(
                f"Sandbox job queued (Odoo {odoo_major}) — poll GET /api/jobs/{{job_id}}"
            ),
            job_id=job.id,
            odoo_major=odoo_major,
            **honesty,
        )

    try:
        result = run_sandbox_install(
            zip_bytes,
            module_name=module_name,
            keep_alive=body.keep_alive,
            extra_modules=sandbox_extras,
            odoo_major=odoo_major,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("sandbox run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    validation_id = None
    digest = None
    echoed = None
    if result.ok:
        validation = record_sandbox_validation(
            db,
            connection_id=connection_id,
            module_name=result.module,
            zip_bytes=zip_bytes,
        )
        validation_id = validation.id
        digest = validation.zip_sha256
        echoed = base64.b64encode(zip_bytes).decode("ascii")

    honesty = _sandbox_honesty(db, connection_id=connection_id, odoo_major=result.odoo_major)
    return SandboxRunOut(
        ok=result.ok,
        module=result.module,
        message=result.message,
        log_tail=result.log_tail,
        sandbox_url=result.sandbox_url,
        odoo_major=result.odoo_major,
        validation_id=validation_id,
        zip_sha256=digest,
        zip_base64=echoed,
        **honesty,
    )


@router.post("/modules/promote", response_model=PromoteModuleOut)
def promote_module(
    connection_id: str, body: PromoteModuleBody, db: Session = Depends(get_db)
) -> PromoteModuleOut:
    """Install a sandbox-validated zip onto the connection (confirm required)."""
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=PROMOTE_WARNING,
            risks=PROMOTE_RISKS,
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "warning": exc.warning,
                "risks": exc.risks,
                "confirm_phrase": "I understand the risks",
            },
        ) from exc

    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ctx = gating_context_for_connection(url=row.url, server_version=row.server_version)
    if ctx.hosting == "online" and body.install_mode == "python":
        gating = online_python_promote_gating()
        raise HTTPException(status_code=403, detail={"gating": gating.to_dict()})

    zip_bytes, module_name = _resolve_zip(
        connection_id,
        db,
        zip_base64=body.zip_base64,
        technical_name=body.technical_name,
        display_name=body.display_name,
        include_custom_models=body.include_custom_models,
        include_views=body.include_views,
        model_filter=body.model_filter,
        install_mode=body.install_mode,
    )

    validation_id = body.validation_id
    if body.run_sandbox:
        major = _connection_odoo_major(connection_id, db)
        sandbox = run_sandbox_install(
            zip_bytes,
            module_name=module_name,
            keep_alive=False,
            odoo_major=major,
        )
        if not sandbox.ok:
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "message": sandbox.message, "log_tail": sandbox.log_tail},
            )
        validation = record_sandbox_validation(
            db,
            connection_id=connection_id,
            module_name=sandbox.module,
            zip_bytes=zip_bytes,
        )
        validation_id = validation.id
        module_name = sandbox.module
    else:
        if not validation_id:
            raise HTTPException(
                status_code=422,
                detail="Provide validation_id from sandbox/run, or set run_sandbox=true",
            )
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

    client = _client(connection_id, db)
    try:
        result = promote_module_zip(client, zip_bytes)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("promote failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if validation_id:
        row = db.get(SandboxValidation, validation_id)
        if row:
            consume_validation(db, row)

    model_names = extract_model_names_from_zip(zip_bytes)
    promotion = PromotedModule(
        connection_id=connection_id,
        module_name=result.module,
        method=result.method,
        zip_sha256=sha256_bytes(zip_bytes),
        models_json=json.dumps(model_names) if model_names else None,
        status="installed",
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)

    return PromoteModuleOut(
        ok=result.ok,
        module=result.module,
        method=result.method,
        message=result.message,
        module_state=result.module_state,
        validation_id=validation_id,
        promotion_id=promotion.id,
    )


@router.get("/modules/promoted", response_model=list[PromotedModuleOut])
def list_promoted(
    connection_id: str, db: Session = Depends(get_db)
) -> list[PromotedModuleOut]:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = (
        db.query(PromotedModule)
        .filter(PromotedModule.connection_id == connection_id)
        .order_by(PromotedModule.created_at.desc())
        .limit(100)
        .all()
    )
    out: list[PromotedModuleOut] = []
    for r in rows:
        models: list[str] = []
        if r.models_json:
            try:
                models = list(json.loads(r.models_json))
            except json.JSONDecodeError:
                models = []
        item = PromotedModuleOut.model_validate(r)
        item.models = models
        out.append(item)
    return out


@router.post("/modules/uninstall", response_model=UninstallModuleOut)
def uninstall_module(
    connection_id: str, body: UninstallModuleBody, db: Session = Depends(get_db)
) -> UninstallModuleOut:
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=UNINSTALL_WARNING,
            risks=UNINSTALL_RISKS,
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "warning": exc.warning,
                "risks": exc.risks,
                "confirm_phrase": "I understand the risks",
            },
        ) from exc

    client = _client(connection_id, db)

    promo = (
        db.query(PromotedModule)
        .filter(
            PromotedModule.connection_id == connection_id,
            PromotedModule.module_name == body.module_name,
            PromotedModule.status == "installed",
        )
        .order_by(PromotedModule.created_at.desc())
        .first()
    )
    tracked_models: list[str] = []
    if promo and promo.models_json:
        try:
            tracked_models = list(json.loads(promo.models_json))
        except json.JSONDecodeError:
            tracked_models = []

    try:
        state = client.uninstall_module(body.module_name)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("uninstall failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    from datetime import datetime, timezone

    if promo:
        promo.status = "uninstalled"
        promo.uninstalled_at = datetime.now(timezone.utc)
        db.add(promo)
        db.commit()

    residual_models: list[str] = []
    used_prefix_heuristic = False
    if tracked_models:
        residual_models = sorted(m for m in tracked_models if client.model_exists(m))
    else:
        # Fallback: module-name-related custom models only (legacy promotes without models_json)
        used_prefix_heuristic = True
        related_prefix = body.module_name.replace("-", "_")
        residual_models = sorted(
            m.model
            for m in client.list_models(custom_only=True, limit=500)
            if related_prefix in m.model
        )[:20]

    residual_note = None
    message = f"Uninstalled {body.module_name}"
    if residual_models:
        if used_prefix_heuristic:
            residual_note = (
                "legacy promote without zip model list — residuals are heuristic. "
                "Odoo may leave tables/metadata; a DB backup is the only full rollback."
            )
        else:
            residual_note = (
                "Tracked models from the promoted zip still exist after uninstall. "
                "Odoo may leave tables/metadata; a DB backup is the only full rollback."
            )
        message = f"Uninstalled {body.module_name} with residual models detected"

    return UninstallModuleOut(
        ok=True,
        module=body.module_name,
        module_state=(state or {}).get("state"),
        message=message,
        residual_models=residual_models,
        residual_note=residual_note,
    )
