"""FastAPI dependency enforcing TRUST-2 SafetyGate preflight."""

from __future__ import annotations

import re

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
from app.workspace_auth import WorkspaceAuth, get_workspace_auth, scoped_connection_query

_REGISTRY = None


def get_route_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        from app.main import app

        _REGISTRY = build_route_registry(app.openapi()["paths"])
    return _REGISTRY


_PATH_CONVERTER = re.compile(r"\{([^{}:]+):[^{}]+\}")


def normalize_api_path(path: str) -> str:
    if path.startswith("/api/") or path == "/api":
        normalized = path
    else:
        normalized = f"/api{path}" if path.startswith("/") else f"/api/{path}"
    # OpenAPI keys omit Starlette converters (`{path:path}`), so the registry lookup must too.
    return _PATH_CONVERTER.sub(r"{\1}", normalized)


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
        connection = (
            scoped_connection_query(db, auth).filter(OdooConnection.id == conn_id).first()
        )
        if connection is None:
            raise HTTPException(status_code=404, detail="Connection not found")
    if auth.workspace_id:
        workspace = db.get(Workspace, auth.workspace_id)
    elif auth.mode == "off":
        workspace = db.query(Workspace).order_by(Workspace.created_at).first()

    gate = SafetyGate(db, connection=connection, workspace=workspace)
    try:
        gate.preflight(spec, snapshot_id=request.headers.get("x-snapshot-id"))
    except SafetyGateError as exc:
        raise HTTPException(status_code=403, detail=exc.refusal.http_detail()) from exc
