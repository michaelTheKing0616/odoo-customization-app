"""Workspace session auth dependencies and role enforcement (MON-1)."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.types import Message, Receive, Scope, Send

from app.account_service import (
    can_admin,
    can_develop,
    can_mutate,
    can_read,
    resolve_session,
    SESSION_COOKIE,
)
from app.client_access import RouteGroup, client_request_decision, role_allows_route_group
from app.auth import extract_raw_key, key_matches_env, verify_api_key
from app.db import SessionLocal, get_db
from app.db_models import OdooConnection
from app.settings import settings
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Set per-request by require_app_auth; read by get_connection_or_404 (TRUST-7 IDOR choke).
_current_workspace_auth: ContextVar["WorkspaceAuth | None"] = ContextVar(
    "current_workspace_auth",
    default=None,
)
# True only while WorkspaceTenancyMiddleware is inside a request. A leftover
# bind_workspace_auth() from a test must not filter later sessions.
_workspace_scope_active: ContextVar[bool] = ContextVar(
    "workspace_scope_active",
    default=False,
)
# True after this request's ids were rewritten to a missing connection id.
# Account routes must not revoke the caller for a cross-tenant probe.
_cross_tenant_masked: ContextVar[bool] = ContextVar(
    "cross_tenant_masked",
    default=False,
)


def bind_workspace_auth(auth: WorkspaceAuth) -> None:
    _current_workspace_auth.set(auth)


def current_workspace_auth() -> WorkspaceAuth | None:
    return _current_workspace_auth.get()


def cross_tenant_request_masked() -> bool:
    """True when this request named another workspace's connection.

    Inputs: none. Output: whether the tenancy middleware rewrote that id to a
    missing one. Side effects: none.
    """
    return _cross_tenant_masked.get()


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
    # None means every connection in the workspace. A set means only those.
    connection_scope: frozenset[str] | None = None

    @property
    def workspace_scoped(self) -> bool:
        return self.mode == "accounts" and self.workspace_id is not None and not self.api_key_authenticated

    @property
    def client_limited(self) -> bool:
        return self.connection_scope is not None and not self.is_superadmin and not self.api_key_authenticated

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
        auth = WorkspaceAuth(mode="off")
        request.state.auth = auth
        bind_workspace_auth(auth)
        return auth

    path = request.url.path
    if path in _public_account_paths():
        auth = WorkspaceAuth(mode=mode)
        request.state.auth = auth
        bind_workspace_auth(auth)
        return auth

    if mode == "api_key":
        await _require_api_key(request, credentials, x_api_key, db)
        auth = WorkspaceAuth(mode="api_key", api_key_authenticated=True)
        request.state.auth = auth
        bind_workspace_auth(auth)
        return auth

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
                connection_scope=ctx.connection_scope,
            )
            if auth.client_limited and auth.connection_scope is not None:
                decision = client_request_decision(
                    request.method,
                    request.url.path,
                    auth.role or "",
                    auth.connection_scope,
                )
                if decision == "hide":
                    raise HTTPException(status_code=404, detail="Connection not found")
                if decision == "deny":
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "forbidden",
                            "message": "This account can only open approvals for its granted client.",
                            "role": auth.role,
                        },
                    )
            request.state.auth = auth
            bind_workspace_auth(auth)
            return auth

        raw_key = extract_raw_key(credentials, x_api_key)
        if raw_key and (key_matches_env(raw_key) or verify_api_key(db, raw_key)):
            auth = WorkspaceAuth(mode="accounts", api_key_authenticated=True)
            request.state.auth = auth
            bind_workspace_auth(auth)
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
        auth = WorkspaceAuth(mode="api_key", api_key_authenticated=True)
        request.state.auth = auth
        bind_workspace_auth(auth)
        return auth

    auth = WorkspaceAuth(mode="off")
    request.state.auth = auth
    bind_workspace_auth(auth)
    return auth


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


def require_developer(auth: WorkspaceAuth = Depends(require_app_auth)) -> WorkspaceAuth:
    if auth.mode != "accounts" or auth.api_key_authenticated or auth.is_superadmin:
        return auth
    role = auth.role or ""
    if not can_develop(role):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Requires developer role or higher.",
                "role": role,
            },
        )
    return auth


def scoped_connection_query(db: Session, auth: WorkspaceAuth):
    q = db.query(OdooConnection)
    if auth.client_limited and auth.connection_scope is not None:
        return q.filter(OdooConnection.id.in_(auth.connection_scope))
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


def require_route_group(auth: WorkspaceAuth, group: RouteGroup) -> None:
    """Enforce ROLE_CAPABILITIES for account sessions (workspace and client grants)."""
    if auth.mode != "accounts" or auth.api_key_authenticated or auth.is_superadmin:
        return
    if not role_allows_route_group(auth.role, group):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": f"This account is not allowed to use the {group} routes.",
                "role": auth.role,
            },
        )


_UUID_IN_TEXT = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_JSON_BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_WORKSPACE_QUERY_SCOPE_INSTALLED = False


def apply_workspace_query_scope(statement, workspace_id: str):
    """Limit an ORM select to one workspace.

    Inputs: a SQLAlchemy statement and a workspace id. Output: the same
    statement when it has no mapped ``workspace_id`` column, otherwise a copy
    with that predicate on each such entity. Side effects: none.
    """
    if not isinstance(workspace_id, str) or not workspace_id:
        return statement
    if not hasattr(statement, "where") or not hasattr(statement, "column_descriptions"):
        return statement
    scoped = statement
    seen: set[int] = set()
    for desc in statement.column_descriptions:
        if not isinstance(desc, dict):
            continue
        entity = desc.get("entity")
        if entity is None or id(entity) in seen:
            continue
        seen.add(id(entity))
        table = getattr(entity, "__table__", None)
        if table is None or "workspace_id" not in table.c:
            continue
        scoped = scoped.where(entity.workspace_id == workspace_id)
    return scoped


def stamp_workspace_id(row: object, workspace_id: str) -> None:
    """Stamp an empty row with ``workspace_id``.

    Inputs: a row object and a workspace id. Output: none. Side effect: sets
    ``workspace_id`` when it is missing or already the same value. A row
    already stamped for another workspace raises HTTP 404 and keeps that id.
    """
    current = getattr(row, "workspace_id", None)
    if current is None:
        row.workspace_id = workspace_id
        return
    if current == workspace_id:
        return
    raise HTTPException(status_code=404, detail="Not found")


def install_workspace_query_scope() -> None:
    """Register the shared select filter once.

    Inputs: none. Output: none. Side effect: one ``Session`` ``do_orm_execute``
    listener. A later call does not add a second listener. The listener calls
    ``apply_workspace_query_scope`` only when a workspace is bound, so an
    unbound query is left unchanged.
    """
    global _WORKSPACE_QUERY_SCOPE_INSTALLED
    if _WORKSPACE_QUERY_SCOPE_INSTALLED:
        return
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    @event.listens_for(Session, "do_orm_execute")
    def _scope_bound_workspace(execute_state):
        if not _workspace_scope_active.get():
            return
        if execute_state.execution_options.get("skip_workspace_scope"):
            return
        if not execute_state.is_select or execute_state.is_from_statement:
            return
        auth = current_workspace_auth()
        workspace_id = None if auth is None else auth.workspace_id
        if not workspace_id:
            return
        execute_state.statement = apply_workspace_query_scope(
            execute_state.statement, workspace_id
        )

    _WORKSPACE_QUERY_SCOPE_INSTALLED = True


def _uuids(text: str) -> set[str]:
    found: set[str] = set()
    for match in _UUID_IN_TEXT.findall(text):
        found.add(match)
        if match.lower() != match:
            found.add(match.lower())
    return found


def _ids_on_request(scope: Scope) -> set[str]:
    request = Request(scope)
    found = _uuids(request.url.path)
    for _key, value in request.query_params.multi_items():
        found |= _uuids(value)
    return found


def _content_type_is_json(scope: Scope) -> bool:
    method = str(scope.get("method") or "").upper()
    if method not in _JSON_BODY_METHODS:
        return False
    for name, value in scope.get("headers") or []:
        if name.lower() == b"content-type" and b"json" in value.lower():
            return True
    return False


async def _buffer_json_body(
    receive: Receive,
) -> tuple[set[str], Receive, list[Message]]:
    """Read a JSON body once and hand the same bytes to the next app."""
    body = b""
    messages: list[Message] = []
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    found = _uuids(body.decode("utf-8", errors="ignore")) if body else set()
    index = 0

    async def replay() -> Message:
        nonlocal index
        if index < len(messages):
            message = messages[index]
            index += 1
            return message
        return {"type": "http.disconnect"}

    return found, replay, messages


# A foreign connection id is swapped for this id before the handler runs.
# The handler then builds the same not-found body it builds for a missing id.
_NIL_CONNECTION_ID = "00000000-0000-0000-0000-000000000000"


def _foreign_connection_ids(
    db: Session, workspace_id: str, candidates: set[str]
) -> set[str]:
    """Return the candidate ids that belong to a different workspace.

    Inputs: a session, the caller's workspace id, and ids taken from the
    request. Output: those candidates, plus the stored id spelling. An empty
    set means none of the candidates are another workspace's connection.
    Side effects: one select that skips the workspace query filter.
    """
    if not candidates:
        return set()
    rows = db.execute(
        select(OdooConnection.id, OdooConnection.workspace_id)
        .where(OdooConnection.id.in_(candidates))
        .execution_options(skip_workspace_scope=True)
    ).all()
    stored_by_lower: dict[str, str] = {}
    for connection_id, owner in rows:
        if connection_id and owner and owner != workspace_id:
            stored_by_lower[str(connection_id).lower()] = str(connection_id)
    if not stored_by_lower:
        return set()
    matched: set[str] = set()
    for candidate in candidates:
        stored = stored_by_lower.get(candidate.lower())
        if stored is None:
            continue
        matched.add(candidate)
        matched.add(stored)
    return matched


def _mask_text(value: str, foreign_ids: set[str]) -> str:
    for item in foreign_ids:
        if item and item != _NIL_CONNECTION_ID:
            value = value.replace(item, _NIL_CONNECTION_ID)
    return value


def _mask_scope(scope: Scope, foreign_ids: set[str]) -> None:
    path = scope.get("path")
    if isinstance(path, str):
        scope["path"] = _mask_text(path, foreign_ids)
    raw_path = scope.get("raw_path")
    if isinstance(raw_path, (bytes, bytearray)):
        scope["raw_path"] = _mask_text(raw_path.decode("latin1"), foreign_ids).encode("latin1")
    query = scope.get("query_string")
    if isinstance(query, (bytes, bytearray)):
        scope["query_string"] = _mask_text(query.decode("latin1"), foreign_ids).encode("latin1")


def _body_is_dry_run_preview(messages: list[Message] | None) -> bool:
    """True when the JSON body is a dry-run preview the client must receive as 200."""
    if not messages:
        return False
    raw = b""
    for message in messages:
        chunk = message.get("body")
        if isinstance(chunk, (bytes, bytearray)):
            raw += bytes(chunk)
    if not raw:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("dry_run") is True


def _mask_messages(messages: list[Message], foreign_ids: set[str]) -> None:
    for message in messages:
        body = message.get("body")
        if isinstance(body, (bytes, bytearray)) and body:
            message["body"] = _mask_text(
                body.decode("utf-8", errors="ignore"), foreign_ids
            ).encode()


def _auth_from_session(ctx) -> WorkspaceAuth:
    return WorkspaceAuth(
        mode="accounts",
        user_id=ctx.user_id,
        email=ctx.email,
        workspace_id=ctx.workspace_id,
        role=ctx.role,
        is_superadmin=ctx.is_superadmin,
        connection_scope=ctx.connection_scope,
    )


class WorkspaceTenancyMiddleware:
    """Hide another workspace's connection id before the handler runs.

    A matching id is replaced with one that does not exist. The handler then
    returns the same not-found body it returns for a missing id. With no
    accounts session, the request is unchanged.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        token = _current_workspace_auth.set(None)
        try:
            receive, denied, coerce, keep_preview = await self._screen(scope, receive, send)
            if denied:
                return
            active = _workspace_scope_active.set(True)
            masked = _cross_tenant_masked.set(coerce)
            try:
                if not coerce:
                    await self.app(scope, receive, send)
                    return
                await self._call_and_hide_foreign(scope, receive, send, keep_preview)
            finally:
                _cross_tenant_masked.reset(masked)
                _workspace_scope_active.reset(active)
        finally:
            _current_workspace_auth.reset(token)

    async def _call_and_hide_foreign(
        self, scope: Scope, receive: Receive, send: Send, keep_preview: bool
    ) -> None:
        """Run the handler. Keep a 403 or 404. Any other result becomes 404.

        The kept 403 or 404 is the handler's own body, so it matches the body
        for a missing id. A 200 or a validation error would show that the id
        was recognised, so those become a not-found response. A dry-run
        preview is the 200 the client must see before it sends the real call,
        so that 200 is kept. An exception before a response is not-found.
        """
        kept = {403, 404}
        if keep_preview:
            kept.add(200)
        forwarded = False
        replaced = False
        body = b'{"detail":"Not found"}'

        async def _not_found() -> None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body, "more_body": False})

        async def wrapped(message: Message) -> None:
            nonlocal forwarded, replaced
            if message["type"] == "http.response.start":
                if message.get("status") in kept:
                    forwarded = True
                    await send(message)
                    return
                if not replaced:
                    replaced = True
                    await _not_found()
                return
            if message["type"] == "http.response.body":
                if forwarded:
                    await send(message)
                return
            await send(message)

        try:
            await self.app(scope, receive, wrapped)
        except Exception:
            if forwarded:
                raise
            if not replaced:
                await _not_found()

    async def _screen(
        self, scope: Scope, receive: Receive, _send: Send
    ) -> tuple[Receive, bool, bool, bool]:
        if settings.auth_mode.strip().lower() != "accounts":
            return receive, False, False, False
        raw = Request(scope).cookies.get(SESSION_COOKIE)
        if not raw:
            return receive, False, False, False
        candidates = _ids_on_request(scope)
        messages: list[Message] | None = None
        if _content_type_is_json(scope):
            body_ids, receive, messages = await _buffer_json_body(receive)
            candidates |= body_ids
        db = SessionLocal()
        try:
            ctx = resolve_session(db, raw)
            if ctx is None or not ctx.workspace_id:
                return receive, False, False, False
            foreign_ids = _foreign_connection_ids(db, ctx.workspace_id, candidates)
            _current_workspace_auth.set(_auth_from_session(ctx))
            if not foreign_ids:
                return receive, False, False, False
            # Swap the foreign id for a missing id in the path, query, and body.
            # The handler then returns the same not-found body it returns for a
            # random id. A result other than 403 or 404 is coerced to 404, except
            # a dry-run preview, which the client has to see as 200.
            _mask_scope(scope, foreign_ids)
            if messages is not None:
                _mask_messages(messages, foreign_ids)
            return receive, False, True, _body_is_dry_run_preview(messages)
        finally:
            db.close()

