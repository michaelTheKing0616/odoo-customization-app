"""CRUD for saved Odoo connections (credentials encrypted at rest)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.account_service import AccountError
from app.capabilities import capabilities_from_version, probe_web_base_url, sample_installed_modules, tier_matrix_response
from app.crypto import encrypt_secret
from app.db import get_db
from app.db_models import OdooConnection
from app.entitlements import assert_connection_limit
from app.odoo_service import OdooClientError, client_from_connection, probe_credentials
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth, require_admin, require_builder, scoped_connection_query
from app.schemas import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionUpdate,
    MigrationAssistOut,
    PreviewThemeOut,
    ProbeResult,
    ProtectedModulesOut,
    TierMatrixOut,
    WriteModeUpdate,
    WritesPausedUpdate,
)
from app.beta_gating import can_unlock_production_write_mode
from app.migration_assist import migration_assist_for_connection
from app.production_readiness import evaluate_production_readiness
from app.write_mode_service import normalize_write_mode
from app.tier_matrix import invalidate_matrix_cache

router = APIRouter(prefix="/connections", tags=["connections"])


def _store_protected_manifest(row: OdooConnection, manifest: dict) -> None:
    from app.protected_modules import manifest_to_json

    row.protected_manifest_json = manifest_to_json(manifest)
    row.protected_manifest_version = str(manifest.get("version") or "")


def _refresh_protected_manifest_for_row(row: OdooConnection, client=None) -> dict:
    from app.protected_modules import refresh_connection_protected_manifest

    manifest = refresh_connection_protected_manifest(
        server_version=row.server_version,
        client=client,
    )
    _store_protected_manifest(row, manifest)
    return manifest


def _connection_out(row: OdooConnection) -> ConnectionOut:
    return ConnectionOut(
        id=row.id,
        name=row.name,
        url=row.url,
        db_name=row.db_name,
        username=row.username,
        server_version=row.server_version,
        last_seen_version=row.last_seen_version,
        upgrade_detected=bool(row.upgrade_detected),
        upgrade_detected_at=row.upgrade_detected_at,
        write_mode=row.write_mode or "standard",
        writes_paused=bool(row.writes_paused),
        created_at=row.created_at,
        updated_at=row.updated_at,
        capabilities=capabilities_from_version(row.server_version, url=row.url),
    )


@router.get("", response_model=list[ConnectionOut])
def list_connections(
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> list[ConnectionOut]:
    rows = scoped_connection_query(db, auth).order_by(OdooConnection.created_at.desc()).all()
    return [_connection_out(r) for r in rows]


@router.post("", response_model=ConnectionOut, status_code=201)
def create_connection(
    body: ConnectionCreate,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_builder),
) -> ConnectionOut:
    assert_connection_limit(db, auth.workspace_id if auth.workspace_scoped else None, auth)
    server_version: str | None = None
    if body.verify:
        try:
            _, server_version = probe_credentials(
                body.url, body.db_name, body.username, body.password
            )
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = OdooConnection(
        name=body.name,
        url=body.url.rstrip("/"),
        db_name=body.db_name,
        username=body.username,
        secret_encrypted=encrypt_secret(body.password),
        server_version=server_version,
        last_seen_version=server_version,
        write_mode=os.environ.get("TEST_DEFAULT_WRITE_MODE", "observer"),
        workspace_id=auth.workspace_id if auth.workspace_scoped else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if server_version:
        _refresh_protected_manifest_for_row(row)
        try:
            from app.preview_theme_service import refresh_preview_theme

            refresh_preview_theme(row)
        except Exception:  # noqa: BLE001 — best-effort theme extract
            pass
        db.commit()
        db.refresh(row)
    return _connection_out(row)


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> ConnectionOut:
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return _connection_out(row)


@router.get("/{connection_id}/preview-theme", response_model=PreviewThemeOut)
def get_preview_theme(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> PreviewThemeOut:
    row = get_scoped_connection_or_404(db, connection_id, auth)
    from app.preview_theme_service import load_preview_theme

    data = load_preview_theme(row)
    return PreviewThemeOut(
        ok=bool(data.get("ok")),
        theme=dict(data.get("theme") or {}),
        preview_vars=dict(data.get("preview_vars") or {}),
        error=data.get("error"),
    )


@router.patch("/{connection_id}", response_model=ConnectionOut)
def update_connection(
    connection_id: str,
    body: ConnectionUpdate,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_builder),
) -> ConnectionOut:
    row = get_scoped_connection_or_404(db, connection_id, auth)

    if body.name is not None:
        row.name = body.name
    if body.url is not None:
        row.url = body.url.rstrip("/")
    if body.db_name is not None:
        row.db_name = body.db_name
    if body.username is not None:
        row.username = body.username
    if body.password is not None:
        row.secret_encrypted = encrypt_secret(body.password)

    if body.verify:
        from app.crypto import decrypt_secret

        password = body.password if body.password is not None else decrypt_secret(row.secret_encrypted)
        try:
            _, version = probe_credentials(row.url, row.db_name, row.username, password)
            row.server_version = version
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif body.url is not None or body.db_name is not None or body.username is not None or body.password is not None:
        # Connection endpoint changed without verify — clear stale version so UI
        # cannot keep a wrong capability matrix until the next probe.
        row.server_version = None

    db.commit()
    db.refresh(row)
    return _connection_out(row)


def _account_error(exc: AccountError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"error": exc.code, "message": exc.message},
    )


@router.patch("/{connection_id}/write-mode", response_model=ConnectionOut)
def update_write_mode(
    connection_id: str,
    body: WriteModeUpdate,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> ConnectionOut:
    row = get_scoped_connection_or_404(db, connection_id, auth)
    try:
        mode = normalize_write_mode(body.write_mode)
    except AccountError as exc:
        raise _account_error(exc) from exc
    if mode == "production":
        ok, err_code = can_unlock_production_write_mode(db, row)
        if not ok:
            if err_code == "production_readiness_required":
                report = evaluate_production_readiness(db, row)
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": err_code,
                        "message": (
                            "Production write mode requires passing the production readiness "
                            "checklist on this connection."
                        ),
                        "checklist": [
                            {"key": i.key, "status": i.status, "detail": i.detail}
                            for i in report.items
                        ],
                    },
                )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": err_code or "beta_partner_required",
                    "message": (
                        "Production write mode is limited to design-partner workspaces until GA. "
                        "Use standard mode, or set PRODUCTION_WRITE_MODE_GA_UNLOCKED=1 at launch."
                    ),
                },
            )
    row.write_mode = mode
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_out(row)


@router.patch("/{connection_id}/writes-paused", response_model=ConnectionOut)
def update_writes_paused(
    connection_id: str,
    body: WritesPausedUpdate,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> ConnectionOut:
    row = get_scoped_connection_or_404(db, connection_id, auth)
    row.writes_paused = body.writes_paused
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_out(row)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> None:
    from app.db_models import MetadataSnapshot, PromotedModule, SandboxValidation

    row = get_scoped_connection_or_404(db, connection_id, auth)
    # Cascade app-DB metadata for this connection (Odoo-side customizations remain).
    db.query(MetadataSnapshot).filter(MetadataSnapshot.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(SandboxValidation).filter(SandboxValidation.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(PromotedModule).filter(PromotedModule.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()


@router.post("/{connection_id}/probe", response_model=ProbeResult)
def probe_connection(connection_id: str, db: Session = Depends(get_db)) -> ProbeResult:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    from app.crypto import decrypt_secret
    from app.odoo_service import client_from_connection

    prior_version = row.server_version
    try:
        uid, version = probe_credentials(
            row.url, row.db_name, row.username, decrypt_secret(row.secret_encrypted)
        )
        from app.version_watch import observe_server_version

        watch = observe_server_version(db, row, version, auto_health_check=True)
        if prior_version != version:
            invalidate_matrix_cache(connection_id)
        db.refresh(row)
        mods: list[str] = []
        web_base_url: str | None = None
        try:
            client = client_from_connection(row)
            mods = sample_installed_modules(client)
            web_base_url = probe_web_base_url(client)
        except OdooClientError:
            mods = []
            client = None
        else:
            _refresh_protected_manifest_for_row(row, client=client)
            try:
                from app.preview_theme_service import refresh_preview_theme

                refresh_preview_theme(row)
            except Exception:  # noqa: BLE001
                pass
            db.commit()
            db.refresh(row)
        invalidate_matrix_cache(connection_id)
        tier_matrix_response(
            connection_id=connection_id,
            url=row.url,
            server_version=row.server_version,
            installed_modules=mods,
            web_base_url=web_base_url,
            use_cache=True,
        )
        return ProbeResult(
            ok=True,
            uid=uid,
            server_version=row.server_version,
            capabilities=capabilities_from_version(
                row.server_version, url=row.url, installed_modules=mods
            ),
            upgrade_detected=watch.upgrade_detected,
            health_job_id=watch.health_job_id,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{connection_id}/protected-modules", response_model=ProtectedModulesOut)
def get_protected_modules(connection_id: str, db: Session = Depends(get_db)) -> ProtectedModulesOut:
    from app.crypto import decrypt_secret
    from app.odoo_service import client_from_connection
    from app.protected_modules import manifest_from_json, tier_summary

    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    manifest = manifest_from_json(row.protected_manifest_json)
    if manifest is None or not row.server_version:
        client = None
        try:
            client = client_from_connection(row)
        except OdooClientError:
            client = None
        manifest = _refresh_protected_manifest_for_row(row, client=client)
        db.commit()
        db.refresh(row)
    elif row.protected_manifest_version != manifest.get("version"):
        client = None
        try:
            client = client_from_connection(row)
        except OdooClientError:
            client = None
        manifest = _refresh_protected_manifest_for_row(row, client=client)
        db.commit()
        db.refresh(row)

    summary = manifest.get("tier_summary") or tier_summary(manifest)
    return ProtectedModulesOut(
        connection_id=row.id,
        server_version=row.server_version,
        manifest_version=str(manifest.get("version") or row.protected_manifest_version),
        manifest=manifest,
        tier_summary=summary,
    )


@router.get("/{connection_id}/model-tier")
def get_model_protection_tier(
    connection_id: str,
    model: str,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    from app.protected_modules import manifest_from_json, protected_models_for

    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    manifest = manifest_from_json(row.protected_manifest_json) or {}
    tier = protected_models_for(manifest, model.strip())
    return {"model": model.strip(), "tier": tier}


@router.get("/{connection_id}/capability-matrix", response_model=TierMatrixOut)
def get_capability_matrix(connection_id: str, db: Session = Depends(get_db)) -> TierMatrixOut:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if not row.server_version:
        raise HTTPException(
            status_code=409,
            detail="Connection has no probed server_version — run POST /probe first.",
        )
    from app.crypto import decrypt_secret
    from app.odoo_service import client_from_connection

    mods: list[str] = []
    web_base_url: str | None = None
    try:
        client = client_from_connection(row, db=db, watch_version=True)
        mods = sample_installed_modules(client)
        web_base_url = probe_web_base_url(client)
    except OdooClientError:
        pass
    matrix = tier_matrix_response(
        connection_id=connection_id,
        url=row.url,
        server_version=row.server_version,
        installed_modules=mods,
        web_base_url=web_base_url,
        use_cache=True,
    )
    if matrix is None:
        raise HTTPException(status_code=409, detail="Could not evaluate capability matrix.")
    return matrix


@router.get("/{connection_id}/migration-assist", response_model=MigrationAssistOut)
def get_migration_assist(connection_id: str, db: Session = Depends(get_db)) -> MigrationAssistOut:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    mods: list[str] = []
    try:
        client = client_from_connection(row, db=db, watch_version=True)
        mods = sample_installed_modules(client)
    except OdooClientError:
        pass
    panel = migration_assist_for_connection(
        url=row.url,
        server_version=row.server_version,
        installed_modules=mods,
    )
    data = panel.to_dict()
    return MigrationAssistOut(**data)


@router.get("/{connection_id}/protected-modules", response_model=ProtectedModulesOut)
def get_protected_modules(connection_id: str, db: Session = Depends(get_db)) -> ProtectedModulesOut:
    from app.crypto import decrypt_secret
    from app.odoo_service import client_from_connection
    from app.protected_modules import manifest_from_json, tier_summary

    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    manifest = manifest_from_json(row.protected_manifest_json)
    if manifest is None or not row.server_version:
        client = None
        try:
            client = client_from_connection(row)
        except OdooClientError:
            client = None
        manifest = _refresh_protected_manifest_for_row(row, client=client)
        db.commit()
        db.refresh(row)
    elif row.protected_manifest_version != manifest.get("version"):
        client = None
        try:
            client = client_from_connection(row)
        except OdooClientError:
            client = None
        manifest = _refresh_protected_manifest_for_row(row, client=client)
        db.commit()
        db.refresh(row)

    summary = manifest.get("tier_summary") or tier_summary(manifest)
    return ProtectedModulesOut(
        connection_id=row.id,
        server_version=row.server_version,
        manifest_version=str(manifest.get("version") or row.protected_manifest_version),
        manifest=manifest,
        tier_summary=summary,
    )
