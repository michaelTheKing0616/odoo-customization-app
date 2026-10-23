"""MIG-01: data migration studio routes (contract only).

Each handler calls exactly one injected engine function. The default engines say
plainly that migrations are not available yet; engine cards replace them.
Nothing here calls Odoo. The import route is the one route that will write to
Odoo (odoo_mutation=True); a Live target needs confirm=true or it gets 409 CONFLICT.
Every error leaves as the B5 envelope (SCAN-01 route class).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.migration_studio.contract import (
    CreateFn,
    DryRunFn,
    DryRunResult,
    FilesFn,
    GetMappingFn,
    ImportFn,
    ImportRequest,
    ImportResult,
    ImportTarget,
    MappingSet,
    MigrationCreate,
    MigrationFile,
    MigrationJob,
    PutMappingFn,
    ReconcileFn,
    ReconcileReport,
    TargetResolver,
)
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanError, ScanErrorEnvelope, ScanScope
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ScanErrorEnvelope} for s in (403, 404, 422)
}
_IMPORT_ERRORS: dict[int | str, dict[str, Any]] = {409: {"model": ScanErrorEnvelope}}

router = APIRouter(
    prefix="/connections/{connection_id}/migrations",
    tags=["migrations"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)

# Fail-safe: a target is Live (needs confirm) unless its write mode is a known
# non-Live value. None, blank, odd casing and unknown modes all count as Live.
_NON_LIVE_WRITE_MODES = frozenset({"observer", "standard"})


def _is_live(write_mode: object) -> bool:
    return str(write_mode or "").strip().lower() not in _NON_LIVE_WRITE_MODES


def mig_scope(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ScanScope:
    """404 unless the connection belongs to the caller's workspace (or client grant)."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return ScanScope(workspace_id=getattr(row, "workspace_id", None), connection_id=row.id)


def import_target_resolver(
    request: Request,
    db: Session = Depends(get_db),
) -> TargetResolver:
    """Resolve the body's target_connection_id in the same workspace scope (foreign = 404)."""
    auth: WorkspaceAuth = get_workspace_auth(request)

    def resolve(target_connection_id: str) -> ImportTarget:
        row = get_scoped_connection_or_404(db, target_connection_id, auth)
        live = _is_live(getattr(row, "write_mode", None))
        return ImportTarget(connection_id=row.id, live=live)

    return resolve


def _not_ready(*_a: Any) -> Any:
    raise ScanError("NOT_FOUND", "Data migration isn't available on this server yet.")


def create_engine() -> CreateFn:
    return _not_ready


def files_engine() -> FilesFn:
    return _not_ready


def get_mapping_engine() -> GetMappingFn:
    return _not_ready


def put_mapping_engine() -> PutMappingFn:
    return _not_ready


def dry_run_engine() -> DryRunFn:
    return _not_ready


def import_engine() -> ImportFn:
    return _not_ready


def reconcile_engine() -> ReconcileFn:
    return _not_ready


@router.post("", response_model=MigrationJob)
def create_migration(
    body: MigrationCreate,
    scope: ScanScope = Depends(mig_scope),
    engine: CreateFn = Depends(create_engine),
) -> MigrationJob:
    return engine(scope, body)


@router.post("/{mid}/files", response_model=MigrationFile)
def upload_file(
    mid: str,
    file: UploadFile = File(...),
    scope: ScanScope = Depends(mig_scope),
    engine: FilesFn = Depends(files_engine),
) -> MigrationFile:
    return engine(scope, mid, file)


@router.get("/{mid}/mapping", response_model=MappingSet)
def get_mapping(
    mid: str,
    scope: ScanScope = Depends(mig_scope),
    engine: GetMappingFn = Depends(get_mapping_engine),
) -> MappingSet:
    return engine(scope, mid)


@router.put("/{mid}/mapping", response_model=MappingSet)
def put_mapping(
    mid: str,
    body: MappingSet,
    scope: ScanScope = Depends(mig_scope),
    engine: PutMappingFn = Depends(put_mapping_engine),
) -> MappingSet:
    return engine(scope, mid, body)


@router.post("/{mid}/dry-run", response_model=DryRunResult)
def dry_run(
    mid: str,
    scope: ScanScope = Depends(mig_scope),
    engine: DryRunFn = Depends(dry_run_engine),
) -> DryRunResult:
    return engine(scope, mid)


@router.post("/{mid}/import", response_model=ImportResult, responses=_IMPORT_ERRORS)
def import_migration(
    mid: str,
    body: ImportRequest,
    scope: ScanScope = Depends(mig_scope),
    resolve_target: TargetResolver = Depends(import_target_resolver),
    engine: ImportFn = Depends(import_engine),
) -> ImportResult:
    target = resolve_target(body.target_connection_id)
    if target.live and not body.confirm:
        raise ScanError(
            "CONFLICT",
            "The target holds live data. Send confirm: true to import into it.",
            detail={"field": "confirm", "target_live": True},
        )
    return engine(scope, mid, target, body)


@router.get("/{mid}/reconcile", response_model=ReconcileReport)
def reconcile(
    mid: str,
    scope: ScanScope = Depends(mig_scope),
    engine: ReconcileFn = Depends(reconcile_engine),
) -> ReconcileReport:
    return engine(scope, mid)
