"""Workspace session auth dependencies and role enforcement (MON-1)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.account_service import (
    SessionContext,
    can_admin,
    can_mutate,
    can_read,
    resolve_session,
    SESSION_COOKIE,
)
from app.auth import extract_raw_key, key_matches_env, verify_api_key
from app.db import get_db
from app.db_models import OdooConnection
from app.settings import settings
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class WorkspaceAuth:
    """Resolved auth context for a request."""

    mode: str  # off | api_key | accounts
    user_id: str | None = None
    email: str | None = None
    workspace_id: str | None = None
    role: str | None = None
    is_superadmin: bool = False
    api_key_authenticated: bool = False

    @property
    def workspace_scoped(self) -> bool:
        return self.mode == "accounts" and self.workspace_id is not None and not self.api_key_authenticated

    def require_role(self, minimum: str) -> None:
        if self.mode != "accounts" or self.api_key_authenticated or self.is_superadmin:
            return
        role = self.role or ""
        checks = {
            "viewer": can_read,
            "builder": can_mutate,
            "admin": can_admin,
        }
        fn = checks.get(minimum)
        if fn is None or not fn(role):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": f"Requires {minimum} role or higher.",
                    "role": role,
                },
            )


def _session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _public_account_paths() -> set[str]:
    return {
        "/health",
        "/api/auth/status",
        "/api/auth/bootstrap",
        "/api/accounts/signup",
        "/api/accounts/login",
        "/api/accounts/verify-email",
        "/api/accounts/request-password-reset",
        "/api/accounts/reset-password",
        "/api/accounts/accept-invite",
    }


async def require_app_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Depends(_api_key_header),
    db: Session = Depends(get_db),
) -> WorkspaceAuth:
    mode = settings.auth_mode.strip().lower()
    if mode in {"off", ""}:
        request.state.auth = WorkspaceAuth(mode="off")
        return request.state.auth

    path = request.url.path
    if path in _public_account_paths():
        request.state.auth = WorkspaceAuth(mode=mode)
        return request.state.auth

    if mode == "api_key":
        await _require_api_key(request, credentials, x_api_key, db)
        request.state.auth = WorkspaceAuth(mode="api_key", api_key_authenticated=True)
        return request.state.auth

    if mode == "accounts":
        raw_session = _session_token(request)
        ctx = resolve_session(db, raw_session)
        if ctx:
            auth = WorkspaceAuth(
                mode="accounts",
                user_id=ctx.user_id,
                email=ctx.email,
                workspace_id=ctx.workspace_id,
                role=ctx.role,
                is_superadmin=ctx.is_superadmin,
            )
            request.state.auth = auth
            return auth

        raw_key = extract_raw_key(credentials, x_api_key)
        if raw_key and (key_matches_env(raw_key) or verify_api_key(db, raw_key)):
            auth = WorkspaceAuth(mode="accounts", api_key_authenticated=True)
            request.state.auth = auth
            return auth

        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Login required. Use session cookie or API key.",
            },
        )

    # Legacy aliases
    if settings.auth_enabled:
        await _require_api_key(request, credentials, x_api_key, db)
        request.state.auth = WorkspaceAuth(mode="api_key", api_key_authenticated=True)
        return request.state.auth

    request.state.auth = WorkspaceAuth(mode="off")
    return request.state.auth


async def _require_api_key(request, credentials, x_api_key, db) -> None:
    from app.auth import require_api_auth

    await require_api_auth(request, credentials, x_api_key, db)


def get_workspace_auth(request: Request) -> WorkspaceAuth:
    auth = getattr(request.state, "auth", None)
    if auth is None:
        return WorkspaceAuth(mode=settings.auth_mode.strip().lower() or "off")
    return auth


def require_builder(auth: WorkspaceAuth = Depends(require_app_auth)) -> WorkspaceAuth:
    auth.require_role("builder")
    return auth


def require_admin(auth: WorkspaceAuth = Depends(require_app_auth)) -> WorkspaceAuth:
    auth.require_role("admin")
    return auth


def scoped_connection_query(db: Session, auth: WorkspaceAuth):
    q = db.query(OdooConnection)
    if auth.workspace_scoped and auth.workspace_id:
        q = q.filter(OdooConnection.workspace_id == auth.workspace_id)
    return q


def get_scoped_connection_or_404(
    db: Session,
    connection_id: str,
    auth: WorkspaceAuth,
) -> OdooConnection:
    row = scoped_connection_query(db, auth).filter(OdooConnection.id == connection_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return row
