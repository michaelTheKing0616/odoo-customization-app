"""FastAPI dependency enforcing TRUST-2 SafetyGate preflight."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db import get_db
from app.db_models import OdooConnection
from app.safety_gate import SafetyGate, SafetyGateError
from app.safety_registry import (
    MUTATING_METHODS,
    build_route_registry,
    connection_id_from_path,
    is_exempt,
    lookup_route_spec,
    route_key,
)
from app.workspace_auth import WorkspaceAuth, get_workspace_auth

_REGISTRY = None


def get_route_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        from app.main import app

        _REGISTRY = build_route_registry(app.openapi()["paths"])
    return _REGISTRY


def normalize_api_path(path: str) -> str:
    if path.startswith("/api/") or path == "/api":
        return path
    return f"/api{path}" if path.startswith("/") else f"/api/{path}"


def enforce_safety_gate(
    request: Request,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> None:
    route = request.scope.get("route")
    if route is None:
        return
    path = normalize_api_path(getattr(route, "path", request.url.path))
    method = request.method.upper()
    if method not in MUTATING_METHODS:
        return
    key = route_key(method, path)
    registry = get_route_registry()
    spec = lookup_route_spec(method, path, registry)
    if spec is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "safety_gate_unregistered",
                "message": f"No SafetySpec for {key}. Register in safety_registry.py.",
            },
        )
    if is_exempt(key):
        return

    connection: OdooConnection | None = None
    workspace: Workspace | None = None
    path_params = request.path_params
    conn_id = connection_id_from_path(path, dict(path_params))
    if conn_id:
        connection = db.get(OdooConnection, conn_id)
    if auth.workspace_id:
        workspace = db.get(Workspace, auth.workspace_id)
    elif auth.mode == "off":
        workspace = db.query(Workspace).order_by(Workspace.created_at).first()

    gate = SafetyGate(db, connection=connection, workspace=workspace)
    try:
        gate.preflight(spec)
    except SafetyGateError as exc:
        raise HTTPException(status_code=403, detail=exc.refusal.http_detail()) from exc
