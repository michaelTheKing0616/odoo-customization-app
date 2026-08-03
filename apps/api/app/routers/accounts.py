"""User accounts — signup, login, sessions, invitations, 2FA (MON-1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.account_models import TotpRecoveryCode, User, Workspace, WorkspaceMembership
from app.account_service import (
    AccountError,
    SESSION_COOKIE,
    accept_invitation,
    authenticate_user,
    create_invitation,
    create_session,
    generate_token,
    hash_token,
    request_password_reset,
    reset_password,
    revoke_session,
    signup_user,
    verify_email,
)
from app.db import get_db
from app.settings import settings
from app.workspace_auth import WorkspaceAuth, get_workspace_auth, require_admin, require_app_auth

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


@router.post("/login", response_model=SessionOut)
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    if settings.auth_mode.strip().lower() != "accounts":
        raise HTTPException(status_code=400, detail="Login only available when AUTH_MODE=accounts")
    try:
        user = authenticate_user(db, email=body.email, password=body.password)
    except AccountError as exc:
        raise _account_error(exc) from exc

    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail={"error": "email_unverified", "message": "Verify your email before logging in."},
        )

    _verify_totp_or_recovery(db, user, body)

    membership = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.user_id == user.id)
        .order_by(WorkspaceMembership.created_at.asc())
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=400, detail="No workspace membership")

    _, raw = create_session(
        db,
        user=user,
        workspace_id=membership.workspace_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, raw)
    return _session_out(db, user, membership.workspace_id, membership.role)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        revoke_session(db, raw)
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


@router.post("/totp/enroll", response_model=TotpEnrollOut)
def totp_enroll(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> TotpEnrollOut:
    if not auth.user_id:
        raise HTTPException(status_code=401, detail="Session required")
    user = db.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_enabled = False
    db.add(user)
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Odoo Custom")
    return TotpEnrollOut(secret=secret, provisioning_uri=uri)


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
