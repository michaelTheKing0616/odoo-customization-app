"""FastAPI application — Odoo customization API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.audit import AuditLogMiddleware
from app.auth import ensure_env_bootstrap_key
from app.db import SessionLocal, init_db
from app.rate_limit import RateLimitMiddleware
from app.entitlements import require_feature
from app.workspace_auth import require_app_auth
from app.routers import (
    access,
    accounts,
    actions,
    admin,
    ai,
    apps,
    audit,
    auth,
    automations,
    billing,
    builder,
    bulk_suite,
    config_ops,
    connections,
    data_import,
    domain_playbooks,
    ee_playbooks,
    studio_feature_recipes,
    environments,
    expert,
    export_sandbox,
    ee_drivers,
    approvals,
    health_check,
    introspection,
    jobs,
    menus_builder,
    module_spec,
    power_ops,
    preview_proxy,
    projects,
    reminders,
    reports,
    id_generator,
    snapshots,
    views,
    website,
)
from app.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    from app.jobs import mark_interrupted_jobs_on_boot

    db = SessionLocal()
    try:
        n = mark_interrupted_jobs_on_boot(db)
        if n:
            logger.info("Marked %s background job(s) as interrupted on boot", n)
        if settings.auth_enabled and settings.app_api_key:
            ensure_env_bootstrap_key(db)
        if settings.accounts_auth_enabled:
            from app.account_service import ensure_default_workspace_for_legacy_rows

            ensure_default_workspace_for_legacy_rows(db)
        from app.entitlements import seed_plan_features

        seed_plan_features(db)
        from app.admin_bootstrap import bootstrap_superadmin_from_env

        bootstrap_superadmin_from_env(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Odoo Customization API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLogMiddleware)

# All /api/* routers (except auth status/bootstrap which skip inside the dependency)
_protected = [Depends(require_app_auth)]

app.include_router(auth.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(admin.router, prefix="/api", dependencies=[Depends(require_app_auth)])
app.include_router(audit.router, prefix="/api", dependencies=_protected)
app.include_router(jobs.router, prefix="/api", dependencies=_protected)
app.include_router(connections.router, prefix="/api", dependencies=_protected)
app.include_router(health_check.router, prefix="/api", dependencies=_protected + [Depends(require_feature("health_check"))])
app.include_router(ee_drivers.router, prefix="/api", dependencies=_protected)
app.include_router(approvals.router, prefix="/api", dependencies=_protected + [Depends(require_feature("approvals"))])
app.include_router(apps.router, prefix="/api", dependencies=_protected)
app.include_router(ai.router, prefix="/api", dependencies=_protected + [Depends(require_feature("ai_draft"))])
app.include_router(expert.router, prefix="/api", dependencies=_protected + [Depends(require_feature("expert"))])
app.include_router(module_spec.router, prefix="/api", dependencies=_protected)
app.include_router(module_spec.import_router, prefix="/api", dependencies=_protected + [Depends(require_feature("import"))])
app.include_router(introspection.router, prefix="/api", dependencies=_protected)
app.include_router(builder.router, prefix="/api", dependencies=_protected)
app.include_router(projects.router, prefix="/api", dependencies=_protected)
app.include_router(reminders.router, prefix="/api", dependencies=_protected)
app.include_router(views.router, prefix="/api", dependencies=_protected + [Depends(require_feature("designer"))])
app.include_router(actions.router, prefix="/api", dependencies=_protected)
app.include_router(preview_proxy.router, prefix="/api", dependencies=_protected + [Depends(require_feature("designer"))])
app.include_router(automations.router, prefix="/api", dependencies=_protected + [Depends(require_feature("automations"))])
app.include_router(access.router, prefix="/api", dependencies=_protected)
app.include_router(snapshots.router, prefix="/api", dependencies=_protected)
app.include_router(export_sandbox.router, prefix="/api", dependencies=_protected + [Depends(require_feature("module_export"))])
app.include_router(data_import.router, prefix="/api", dependencies=_protected + [Depends(require_feature("import"))])
app.include_router(power_ops.router, prefix="/api", dependencies=_protected + [Depends(require_feature("power_ops"))])
app.include_router(bulk_suite.router, prefix="/api", dependencies=_protected + [Depends(require_feature("bulk_suite"))])
app.include_router(ee_playbooks.router, prefix="/api", dependencies=_protected)
app.include_router(domain_playbooks.router, prefix="/api", dependencies=_protected)
app.include_router(studio_feature_recipes.router, prefix="/api", dependencies=_protected)
app.include_router(config_ops.router, prefix="/api", dependencies=_protected)
app.include_router(menus_builder.router, prefix="/api", dependencies=_protected)
app.include_router(reports.router, prefix="/api", dependencies=_protected + [Depends(require_feature("reports_designer"))])
app.include_router(id_generator.router, prefix="/api", dependencies=_protected + [Depends(require_feature("id_generator"))])
app.include_router(environments.router, prefix="/api", dependencies=_protected + [Depends(require_feature("pipelines"))])
app.include_router(website.router, prefix="/api", dependencies=_protected)


@app.get("/health")
def health() -> dict[str, str | bool]:
    db_ok = False
    try:
        from sqlalchemy import text

        from app.db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    status = "ok" if db_ok else "degraded"
    from odoo_client.compat import ga_majors, supported_majors

    out: dict[str, str | bool] = {
        "status": status,
        "odoo_target_version": "19",
        "odoo_supported_majors": ",".join(
            str(m) for m in sorted(supported_majors(), reverse=True)
        ),
        "odoo_ga_majors": ",".join(str(m) for m in sorted(ga_majors(), reverse=True)),
        "auth_enabled": settings.auth_enabled or settings.accounts_auth_enabled,
        "auth_mode": settings.auth_mode,
        "database_ok": db_ok,
        "sandbox_docker_enabled": settings.sandbox_docker_enabled,
    }
    if settings.warn_auth_off and not settings.auth_enabled:
        out["auth_warning"] = (
            "AUTH_MODE is off — enable AUTH_MODE=api_key before any shared/deployed use"
        )
    if settings.ai_assist.strip().lower() == "ollama":
        from app.ai_ollama import ollama_reachable

        out["ai_assist"] = "ollama"
        out["ollama_model"] = settings.ollama_model
        ok, detail = ollama_reachable()
        out["ollama_reachable"] = ok
        out["ollama_detail"] = detail
    return out
