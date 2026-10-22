"""User accounts — signup, login, sessions, invitations, 2FA (MON-1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.account_models import ConnectionAccessGrant, TotpRecoveryCode, User, Workspace, WorkspaceMembership
from app.db_models import OdooConnection
from app.account_service import (
    AccountError,
    SESSION_COOKIE,
    accept_invitation,
    authenticate_user,
    change_membership_role,
    create_invitation,
    create_session,
    disable_totp,
    enroll_totp,
    grant_connection_access,
    login_workspace,
    generate_token,
    hash_token,
    normalize_email,
    request_password_reset,
    reset_password,
    resolve_session,
    revoke_connection_access,
    revoke_session,
    signup_user,
    verify_email,
)
from app.auth_audit import record_auth_event
from app.db import get_db
from app.settings import settings
from app.workspace_auth import WorkspaceAuth, get_workspace_auth, require_admin, require_app_auth
from app.oauth_service import (
    complete_oauth_totp,
    create_oauth_start,
    enabled_oauth_providers,
    exchange_oauth_code,
    list_oauth_identities,
    resolve_oauth_login,
    unlink_oauth_identity,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])

COOKIE_MAX_AGE = 14 * 24 * 3600


class SignupBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=10, max_length=200)
    workspace_name: str | None = Field(None, max_length=200)


class LoginBody(BaseModel):
    email: str
    password: str
    totp_code: str | None = None
    recovery_code: str | None = None


class TokenBody(BaseModel):
    token: str


class ResetPasswordBody(BaseModel):
    token: str
    password: str = Field(..., min_length=10, max_length=200)


class AcceptInviteBody(BaseModel):
    token: str
    password: str | None = Field(None, min_length=10, max_length=200)


class InviteBody(BaseModel):
    email: str
    role: str = "builder"


class ConnectionGrantBody(BaseModel):
    connection_id: str
    email: str
    role: str = "client_approver"


class ConnectionGrantOut(BaseModel):
    id: str
    connection_id: str
    user_id: str
    email: str
    role: str
    created_at: datetime | None = None


class MembershipRoleBody(BaseModel):
    role: str


class UserOut(BaseModel):
    id: str
    email: str
    email_verified: bool
    totp_enabled: bool
    is_superadmin: bool


class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    role: str


class SessionOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class TotpEnrollOut(BaseModel):
    secret: str
    provisioning_uri: str


class TotpVerifyBody(BaseModel):
    code: str


def _set_session_cookie(response: Response, raw_token: str) -> None:
    secure = settings.session_cookie_secure
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def _account_error(exc: AccountError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"error": exc.code, "message": exc.message},
    )


def _session_out(db: Session, user: User, workspace_id: str, role: str) -> SessionOut:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=500, detail="Workspace missing")
    return SessionOut(
        user=UserOut(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified,
            totp_enabled=user.totp_enabled,
            is_superadmin=user.is_superadmin,
        ),
        workspace=WorkspaceOut(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            plan=ws.plan,
            role=role,
        ),
    )


def _verify_totp_or_recovery(db: Session, user: User, body: LoginBody) -> None:
    if not user.totp_enabled:
        return
    if body.recovery_code:
        digest = hash_token(body.recovery_code.strip())
        row = (
            db.query(TotpRecoveryCode)
            .filter(
                TotpRecoveryCode.user_id == user.id,
                TotpRecoveryCode.code_hash == digest,
                TotpRecoveryCode.used_at.is_(None),
            )
            .first()
        )
        if row is None:
            raise HTTPException(status_code=401, detail={"error": "invalid_2fa", "message": "Invalid recovery code"})
        row.used_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
        return
    if not body.totp_code or not user.totp_secret:
        raise HTTPException(
            status_code=401,
            detail={"error": "totp_required", "message": "Two-factor code required."},
        )
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.totp_code.strip(), valid_window=1):
        raise HTTPException(status_code=401, detail={"error": "invalid_2fa", "message": "Invalid 2FA code"})


@router.post("/signup", status_code=201)
def signup(body: SignupBody, db: Session = Depends(get_db)) -> dict[str, str]:
    if settings.auth_mode.strip().lower() != "accounts":
        raise HTTPException(status_code=400, detail="Signup only available when AUTH_MODE=accounts")
    try:
        user, workspace, _token = signup_user(
            db,
            email=body.email,
            password=body.password,
            workspace_name=body.workspace_name,
        )
    except AccountError as exc:
        raise _account_error(exc) from exc
    return {
        "message": "Account created — check your email to verify.",
        "user_id": user.id,
        "workspace_id": workspace.id,
    }


@router.post("/verify-email")
def verify_email_route(body: TokenBody, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        verify_email(db, body.token)
    except AccountError as exc:
        raise _account_error(exc) from exc
    return {"message": "Email verified — you can log in."}


def _login_audit(
    db: Session,
    *,
    actor: str,
    target_user: str | None,
    provider: str,
    result: str,
) -> None:
    record_auth_event(
        db,
        kind="login",
        actor=actor,
        target_user=target_user,
        provider=provider,
        result=result,
    )


def _login_actor_for_email(db: Session, email: str) -> tuple[str, str | None]:
    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if user is None:
        return "anonymous", None
    return user.id, user.id


@router.post("/login", response_model=SessionOut)
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    if settings.auth_mode.strip().lower() != "accounts":
        _login_audit(db, actor="anonymous", target_user=None, provider="password", result="failure")
        raise HTTPException(status_code=400, detail="Login only available when AUTH_MODE=accounts")
    try:
        user = authenticate_user(db, email=body.email, password=body.password)
    except AccountError as exc:
        actor, target = _login_actor_for_email(db, body.email)
        _login_audit(db, actor=actor, target_user=target, provider="password", result="failure")
        raise _account_error(exc) from exc

    if not user.email_verified:
        _login_audit(db, actor=user.id, target_user=user.id, provider="password", result="failure")
        raise HTTPException(
            status_code=403,
            detail={"error": "email_unverified", "message": "Verify your email before logging in."},
        )

    try:
        _verify_totp_or_recovery(db, user, body)
    except HTTPException:
        _login_audit(db, actor=user.id, target_user=user.id, provider="password", result="failure")
        raise

    try:
        workspace_id, role = login_workspace(db, user)
    except AccountError as exc:
        _login_audit(db, actor=user.id, target_user=user.id, provider="password", result="failure")
        raise _account_error(exc) from exc

    _, raw = create_session(
        db,
        user=user,
        workspace_id=workspace_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _login_audit(db, actor=user.id, target_user=user.id, provider="password", result="success")
    _set_session_cookie(response, raw)
    return _session_out(db, user, workspace_id, role)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        record_auth_event(
            db,
            kind="logout",
            actor="anonymous",
            target_user=None,
            provider=None,
            result="failure",
        )
        _clear_session_cookie(response)
        return
    ctx = resolve_session(db, raw)
    if ctx is None:
        record_auth_event(
            db,
            kind="logout",
            actor="anonymous",
            target_user=None,
            provider=None,
            result="failure",
        )
        _clear_session_cookie(response)
        return
    revoke_session(db, raw)
    record_auth_event(
        db,
        kind="logout",
        actor=ctx.user_id,
        target_user=ctx.user_id,
        provider=None,
        result="success",
    )
    _clear_session_cookie(response)


@router.get("/me", response_model=SessionOut)
def me(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> SessionOut:
    if auth.mode != "accounts" or not auth.user_id or auth.api_key_authenticated:
        raise HTTPException(status_code=401, detail="Session required")
    user = db.get(User, auth.user_id)
    if user is None or not auth.workspace_id:
        raise HTTPException(status_code=401, detail="Session invalid")
    return _session_out(db, user, auth.workspace_id, auth.role or "viewer")


@router.post("/request-password-reset", status_code=204)
def password_reset_request(body: dict[str, str], db: Session = Depends(get_db)) -> None:
    email = body.get("email", "")
    request_password_reset(db, email)


@router.post("/reset-password")
def password_reset(body: ResetPasswordBody, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        reset_password(db, body.token, body.password)
    except AccountError as exc:
        raise _account_error(exc) from exc
    return {"message": "Password updated — log in with your new password."}


@router.post("/accept-invite", response_model=SessionOut)
def accept_invite_route(
    body: AcceptInviteBody,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    try:
        user, workspace = accept_invitation(db, raw_token=body.token, password=body.password)
    except AccountError as exc:
        raise _account_error(exc) from exc
    membership = (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id == workspace.id,
        )
        .first()
    )
    role = membership.role if membership else "viewer"
    _, raw = create_session(db, user=user, workspace_id=workspace.id)
    _set_session_cookie(response, raw)
    return _session_out(db, user, workspace.id, role)


@router.post("/invitations", status_code=201)
def invite_member(
    body: InviteBody,
    auth: WorkspaceAuth = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not auth.user_id or not auth.workspace_id:
        raise HTTPException(status_code=401, detail="Session required")
    create_invitation(
        db,
        workspace_id=auth.workspace_id,
        email=body.email,
        role=body.role,
        invited_by_user_id=auth.user_id,
    )
    return {"message": "Invitation sent."}


@router.get("/connection-grants", response_model=list[ConnectionGrantOut])
def list_connection_grants(
    connection_id: str,
    auth: WorkspaceAuth = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ConnectionGrantOut]:
    if not auth.user_id or not auth.workspace_id or auth.client_limited:
        raise HTTPException(status_code=403, detail="Workspace admin required")
    connection = db.get(OdooConnection, connection_id)
    if connection is None or connection.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=404, detail="Connection not found")
    rows = (
        db.query(ConnectionAccessGrant, User.email)
        .join(User, User.id == ConnectionAccessGrant.user_id)
        .filter(
            ConnectionAccessGrant.connection_id == connection_id,
            ConnectionAccessGrant.workspace_id == auth.workspace_id,
        )
        .order_by(ConnectionAccessGrant.created_at.asc())
        .all()
    )
    return [
        ConnectionGrantOut(
            id=grant.id,
            connection_id=grant.connection_id,
            user_id=grant.user_id,
            email=email,
            role=grant.role,
            created_at=grant.created_at,
        )
        for grant, email in rows
    ]


@router.post("/connection-grants", status_code=201)
def create_connection_grant(
    body: ConnectionGrantBody,
    auth: WorkspaceAuth = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Grant a client approver or viewer access to one connection. Not a workspace role."""
    if not auth.user_id or not auth.workspace_id or auth.client_limited:
        record_auth_event(
            db,
            kind="grant",
            actor=auth.user_id or "anonymous",
            target_user=None,
            provider=None,
            result="failure",
            extra={"action": "create"},
        )
        raise HTTPException(status_code=403, detail="Workspace admin required")
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        record_auth_event(
            db,
            kind="grant",
            actor=auth.user_id,
            target_user=None,
            provider=None,
            result="failure",
            extra={"action": "create"},
        )
        raise HTTPException(
            status_code=404,
            detail="No account for that email yet. They need an Ingenium login before they can approve.",
        )
    connection = db.get(OdooConnection, body.connection_id)
    if connection is None or connection.workspace_id != auth.workspace_id:
        record_auth_event(
            db,
            kind="grant",
            actor=auth.user_id,
            target_user=user.id,
            provider=None,
            result="failure",
            extra={"action": "create", "connection_id": body.connection_id},
        )
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        grant = grant_connection_access(
            db,
            workspace_id=auth.workspace_id,
            connection_id=connection.id,
            user_id=user.id,
            role=body.role,
            actor_user_id=auth.user_id,
        )
    except AccountError as exc:
        raise _account_error(exc) from exc
    return {"id": grant.id, "role": grant.role, "connection_id": grant.connection_id}


@router.delete("/connection-grants/{grant_id}", status_code=204)
def delete_connection_grant(
    grant_id: str,
    auth: WorkspaceAuth = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    if not auth.user_id or not auth.workspace_id or auth.client_limited:
        record_auth_event(
            db,
            kind="revoke",
            actor=auth.user_id or "anonymous",
            target_user=None,
            provider=None,
            result="failure",
            extra={"action": "revoke", "grant_id": grant_id},
        )
        raise HTTPException(status_code=403, detail="Workspace admin required")
    try:
        revoke_connection_access(
            db,
            workspace_id=auth.workspace_id,
            grant_id=grant_id,
            actor_user_id=auth.user_id,
        )
    except AccountError as exc:
        raise _account_error(exc) from exc


@router.patch("/memberships/{user_id}")
def patch_membership_role(
    user_id: str,
    body: MembershipRoleBody,
    auth: WorkspaceAuth = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not auth.user_id or not auth.workspace_id or auth.client_limited:
        record_auth_event(
            db,
            kind="grant",
            actor=auth.user_id or "anonymous",
            target_user=user_id,
            provider=None,
            result="failure",
            extra={"action": "role_change", "role": body.role},
        )
        raise HTTPException(status_code=403, detail="Workspace admin required")
    try:
        membership = change_membership_role(
            db,
            workspace_id=auth.workspace_id,
            target_user_id=user_id,
            role=body.role,
            actor_user_id=auth.user_id,
        )
    except AccountError as exc:
        raise _account_error(exc) from exc
    return {"user_id": membership.user_id, "role": membership.role}


@router.post("/totp/enroll", response_model=TotpEnrollOut)
def totp_enroll(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> TotpEnrollOut:
    if not auth.user_id:
        try:
            enroll_totp(db, None, actor_user_id="anonymous")
        except AccountError as exc:
            raise _account_error(exc) from exc
    user = db.get(User, auth.user_id)
    try:
        secret, uri = enroll_totp(db, user, actor_user_id=auth.user_id)
    except AccountError as exc:
        raise _account_error(exc) from exc
    return TotpEnrollOut(secret=secret, provisioning_uri=uri)


@router.post("/totp/disable", status_code=204)
def totp_disable(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> None:
    if not auth.user_id:
        try:
            disable_totp(db, None, actor_user_id="anonymous")
        except AccountError as exc:
            raise _account_error(exc) from exc
    user = db.get(User, auth.user_id)
    try:
        disable_totp(db, user, actor_user_id=auth.user_id)
    except AccountError as exc:
        raise _account_error(exc) from exc


@router.post("/totp/verify")
def totp_verify(
    body: TotpVerifyBody,
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> dict[str, list[str]]:
    if not auth.user_id:
        raise HTTPException(status_code=401, detail="Session required")
    user = db.get(User, auth.user_id)
    if user is None or not user.totp_secret:
        raise HTTPException(status_code=400, detail="Enroll TOTP first")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    user.totp_enabled = True
    db.query(TotpRecoveryCode).filter(TotpRecoveryCode.user_id == user.id).delete()
    codes: list[str] = []
    for _ in range(8):
        raw = generate_token()[:10]
        codes.append(raw)
        db.add(TotpRecoveryCode(user_id=user.id, code_hash=hash_token(raw)))
    db.add(user)
    db.commit()
    return {"recovery_codes": codes}


class OAuthProvidersOut(BaseModel):
    providers: list[str]


class OAuthIdentityOut(BaseModel):
    provider: str
    email: str | None
    created_at: datetime


class OAuthComplete2FABody(BaseModel):
    token: str
    totp_code: str


@router.get("/oauth/providers", response_model=OAuthProvidersOut)
def oauth_providers() -> OAuthProvidersOut:
    return OAuthProvidersOut(providers=enabled_oauth_providers())


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, db: Session = Depends(get_db)) -> RedirectResponse:
    if settings.auth_mode.strip().lower() != "accounts":
        raise HTTPException(status_code=404, detail="OAuth not available")
    try:
        url, _state = create_oauth_start(db, provider=provider)
    except AccountError as exc:
        raise _account_error(exc) from exc
    return RedirectResponse(url=url, status_code=302)


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    if settings.auth_mode.strip().lower() != "accounts":
        raise HTTPException(status_code=404, detail="OAuth not available")
    if not code or not state:
        _login_audit(db, actor="anonymous", target_user=None, provider=provider, result="failure")
        raise HTTPException(status_code=400, detail="Missing OAuth callback parameters")
    try:
        profile = exchange_oauth_code(db, provider=provider, code=code, raw_state=state)
    except AccountError as exc:
        _login_audit(db, actor="anonymous", target_user=None, provider=provider, result="failure")
        return RedirectResponse(
            url=f"{settings.app_public_url.rstrip('/')}/login?oauth_error={exc.code}",
            status_code=302,
        )
    try:
        result = resolve_oauth_login(db, profile)
    except AccountError as exc:
        redirect = RedirectResponse(
            url=f"{settings.app_public_url.rstrip('/')}/login?oauth_error={exc.code}",
            status_code=302,
        )
        return redirect

    if result.totp_pending_token:
        return RedirectResponse(
            url=(
                f"{settings.app_public_url.rstrip('/')}/login"
                f"?oauth_totp=1&token={result.totp_pending_token}"
            ),
            status_code=302,
        )

    try:
        workspace_id, _role = login_workspace(db, result.user)
    except AccountError as exc:
        _login_audit(
            db,
            actor=result.user.id,
            target_user=result.user.id,
            provider=provider,
            result="failure",
        )
        raise _account_error(exc) from exc

    _, raw = create_session(
        db,
        user=result.user,
        workspace_id=workspace_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _login_audit(
        db,
        actor=result.user.id,
        target_user=result.user.id,
        provider=provider,
        result="success",
    )
    redirect = RedirectResponse(
        url=f"{settings.app_public_url.rstrip('/')}/connect",
        status_code=302,
    )
    _set_session_cookie(redirect, raw)
    return redirect


@router.post("/oauth/complete-2fa", response_model=SessionOut)
def oauth_complete_2fa(
    body: OAuthComplete2FABody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    if settings.auth_mode.strip().lower() != "accounts":
        raise HTTPException(status_code=400, detail="OAuth not available")
    try:
        user = complete_oauth_totp(db, raw_token=body.token, totp_code=body.totp_code)
    except AccountError as exc:
        raise _account_error(exc) from exc
    try:
        workspace_id, role = login_workspace(db, user)
    except AccountError as exc:
        _login_audit(db, actor=user.id, target_user=user.id, provider="oauth", result="failure")
        raise _account_error(exc) from exc

    _, raw = create_session(
        db,
        user=user,
        workspace_id=workspace_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _login_audit(db, actor=user.id, target_user=user.id, provider="oauth", result="success")
    _set_session_cookie(response, raw)
    return _session_out(db, user, workspace_id, role)


@router.get("/oauth/identities", response_model=list[OAuthIdentityOut])
def oauth_identities(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> list[OAuthIdentityOut]:
    if auth.mode != "accounts" or not auth.user_id or auth.api_key_authenticated:
        raise HTTPException(status_code=401, detail="Session required")
    rows = list_oauth_identities(db, auth.user_id)
    return [
        OAuthIdentityOut(provider=row.provider, email=row.email, created_at=row.created_at)
        for row in rows
    ]


@router.delete("/oauth/{provider}", status_code=204)
def oauth_unlink(
    provider: str,
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> None:
    if auth.mode != "accounts" or not auth.user_id or auth.api_key_authenticated:
        raise HTTPException(status_code=401, detail="Session required")
    user = db.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        unlink_oauth_identity(db, user=user, provider=provider)
    except AccountError as exc:
        raise _account_error(exc) from exc



class DisplayNameIn(BaseModel):
    display_name: str | None = Field(None, max_length=60)


def clean_display_name(v: str | None) -> str | None:
    v = " ".join((v or "").split())
    return v or None


@router.get("/whoami")
def whoami(auth: WorkspaceAuth = Depends(get_workspace_auth), db: Session = Depends(get_db)) -> dict:
    """Read-only: who is using the app, for greetings. The saved display name only; never guessed."""
    user = db.get(User, auth.user_id) if getattr(auth, "user_id", None) else None
    return {"signed_in": user is not None, "display_name": getattr(user, "display_name", None) if user else None, "mode": getattr(auth, "mode", None)}


@router.patch("/me/display-name")
def set_display_name(body: DisplayNameIn, auth: WorkspaceAuth = Depends(require_app_auth), db: Session = Depends(get_db)) -> dict:
    """Settings: 'What should we call you?'. Empty clears it."""
    user = db.get(User, auth.user_id) if getattr(auth, "user_id", None) else None
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to save a name")
    user.display_name = clean_display_name(body.display_name)
    db.add(user)
    db.commit()
    return {"display_name": user.display_name}
