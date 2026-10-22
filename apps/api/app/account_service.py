"""Account, workspace, session, and role helpers (MON-1)."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.account_models import (
    ConnectionAccessGrant,
    EmailVerification,
    PasswordReset,
    TotpRecoveryCode,
    User,
    UserSession,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from app.auth_audit import record_auth_event
from app.email_receipt import receipt_html
from app.email_transport import send_email
from app.password_breach import COMMON_PASSWORDS
from app.settings import settings

_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

ROLE_ORDER = {"viewer": 0, "builder": 1, "developer": 2, "admin": 3, "owner": 4}
VALID_ROLES = frozenset(ROLE_ORDER)
CLIENT_GRANT_ROLES = frozenset({"client_approver", "client_viewer"})

SESSION_COOKIE = "oc_session"
SESSION_DAYS = 14
VERIFY_HOURS = 48
RESET_HOURS = 2
INVITE_DAYS = 7
LOCKOUT_AFTER = 5
LOCKOUT_MINUTES = 15

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_password_policy(password: str) -> None:
    if len(password) < 10:
        raise AccountError("weak_password", "Password must be at least 10 characters.")
    if password.lower() in COMMON_PASSWORDS:
        raise AccountError("breached_password", "Password is too common — choose a stronger one.")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> None:
    if not EMAIL_RE.match(email):
        raise AccountError("invalid_email", "Invalid email address.")


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_ORDER.get(role, -1) >= ROLE_ORDER.get(minimum, 99)


def can_read(role: str) -> bool:
    return role in VALID_ROLES


def can_mutate(role: str) -> bool:
    return role_at_least(role, "builder")


def can_admin(role: str) -> bool:
    return role_at_least(role, "admin")


def can_develop(role: str) -> bool:
    """DEV-1 — Code Studio and module code authoring."""
    return role in {"developer", "admin", "owner"}


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return base[:60]


@dataclass
class SessionContext:
    user_id: str
    email: str
    workspace_id: str
    role: str
    is_superadmin: bool
    session_id: str
    # None = every connection in the workspace. A set = only those connections.
    connection_scope: frozenset[str] | None = None


def _unique_slug(db: Session, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    n = 1
    while db.query(Workspace).filter(Workspace.slug == candidate).first():
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


def signup_user(
    db: Session,
    *,
    email: str,
    password: str,
    workspace_name: str | None = None,
) -> tuple[User, Workspace, str]:
    """Create user + personal workspace; return verification token."""
    email = normalize_email(email)
    validate_email(email)
    validate_password_policy(password)

    if db.query(User).filter(User.email == email).first():
        raise AccountError("email_taken", "An account with this email already exists.", 409)

    user = User(
        email=email,
        password_hash=hash_password(password),
        email_verified=False,
    )
    db.add(user)
    db.flush()

    ws_name = (workspace_name or f"{email.split('@')[0]}'s workspace").strip()[:200]
    workspace = Workspace(name=ws_name, slug=_unique_slug(db, ws_name))
    db.add(workspace)
    db.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)

    raw_token = generate_token()
    verification = EmailVerification(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=_now() + timedelta(hours=VERIFY_HOURS),
    )
    db.add(verification)
    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    verify_url = f"{settings.app_public_url.rstrip('/')}/verify?token={raw_token}"
    send_email(
        to=email,
        subject="Verify your Ingenium account",
        body=f"Click to verify your email (expires in {VERIFY_HOURS}h):\n\n{verify_url}\n",
        html=receipt_html(title="Verify your email", lead=f"Confirm this is your address. The link works for {VERIFY_HOURS} hours.", button_label="Verify email", button_url=verify_url, footnote="If you didn't sign up, ignore this email."),
    )
    return user, workspace, raw_token


def verify_email(db: Session, raw_token: str) -> User:
    digest = hash_token(raw_token)
    row = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.token_hash == digest,
            EmailVerification.used_at.is_(None),
        )
        .first()
    )
    if row is None or row.expires_at < _now():
        raise AccountError("invalid_token", "Verification link is invalid or expired.", 400)
    user = db.get(User, row.user_id)
    if user is None:
        raise AccountError("invalid_token", "Verification link is invalid.", 400)
    row.used_at = _now()
    user.email_verified = True
    db.add(row)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    dummy_hash = user.password_hash if user else hash_password("dummy-timing-safe")
    ok = verify_password(dummy_hash, password)
    if user is None or not ok:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= LOCKOUT_AFTER:
                user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
            db.add(user)
            db.commit()
        raise AccountError("invalid_credentials", "Invalid email or password.", 401)

    if user.locked_until and user.locked_until > _now():
        raise AccountError("account_locked", "Account temporarily locked — try again later.", 429)

    user.failed_login_count = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def grants_for_user(db: Session, user_id: str, workspace_id: str | None = None) -> list[ConnectionAccessGrant]:
    query = db.query(ConnectionAccessGrant).filter(ConnectionAccessGrant.user_id == user_id)
    if workspace_id is not None:
        query = query.filter(ConnectionAccessGrant.workspace_id == workspace_id)
    return query.order_by(ConnectionAccessGrant.created_at.asc()).all()


def role_from_grants(grants: list[ConnectionAccessGrant]) -> str:
    if any(grant.role == "client_approver" for grant in grants):
        return "client_approver"
    return "client_viewer"


def login_workspace(db: Session, user: User) -> tuple[str, str]:
    """Workspace a password or OAuth login should open.

    A consultant membership in a workspace that already has connections wins.
    An empty personal workspace from signup does not hide a client grant —
    otherwise an invited approver would log into a blank workspace as owner.
    """
    from app.db_models import OdooConnection

    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.user_id == user.id)
        .order_by(WorkspaceMembership.created_at.asc())
        .all()
    )
    grants = grants_for_user(db, user.id)
    if grants:
        grant_workspace = grants[0].workspace_id
        member_of_grant_workspace = any(row.workspace_id == grant_workspace for row in memberships)
        consultant_elsewhere = any(
            db.query(OdooConnection).filter(OdooConnection.workspace_id == row.workspace_id).count() > 0
            for row in memberships
            if row.workspace_id != grant_workspace
        )
        if not member_of_grant_workspace and not consultant_elsewhere:
            scoped = [grant for grant in grants if grant.workspace_id == grant_workspace]
            return grant_workspace, role_from_grants(scoped)
    if memberships:
        return memberships[0].workspace_id, memberships[0].role
    if not grants:
        raise AccountError("no_workspace", "No workspace membership.", 400)
    workspace_id = grants[0].workspace_id
    scoped = [grant for grant in grants if grant.workspace_id == workspace_id]
    return workspace_id, role_from_grants(scoped)


def grant_connection_access(
    db: Session,
    *,
    workspace_id: str,
    connection_id: str,
    user_id: str,
    role: str,
    actor_user_id: str | None = None,
) -> ConnectionAccessGrant:
    actor = actor_user_id or "system"

    def _fail(code: str, message: str, status: int = 400) -> None:
        record_auth_event(
            db,
            kind="grant",
            actor=actor,
            target_user=user_id,
            provider=None,
            result="failure",
            extra={"action": "create", "role": role, "connection_id": connection_id},
        )
        raise AccountError(code, message, status)

    if role not in CLIENT_GRANT_ROLES:
        _fail("invalid_role", "Client grant role must be client_approver or client_viewer.")
    from app.db_models import OdooConnection

    connection = db.get(OdooConnection, connection_id)
    if connection is None or connection.workspace_id != workspace_id:
        _fail("not_found", "Connection is not in this workspace.", 404)
    user = db.get(User, user_id)
    if user is None:
        _fail("not_found", "User not found.", 404)
    if (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        .first()
        is not None
    ):
        _fail(
            "already_member",
            "This person already has a workspace role. Client Approver is a separate grant, not an extra role on a consultant.",
            409,
        )
    existing = (
        db.query(ConnectionAccessGrant)
        .filter(
            ConnectionAccessGrant.connection_id == connection_id,
            ConnectionAccessGrant.user_id == user_id,
        )
        .first()
    )
    if existing is not None:
        existing.role = role
        existing.workspace_id = workspace_id
        db.add(existing)
        record_auth_event(
            db,
            kind="grant",
            actor=actor,
            target_user=user_id,
            provider=None,
            result="success",
            extra={"action": "create", "role": role, "connection_id": connection_id},
        )
        db.refresh(existing)
        return existing
    row = ConnectionAccessGrant(
        workspace_id=workspace_id,
        connection_id=connection_id,
        user_id=user_id,
        role=role,
    )
    db.add(row)
    record_auth_event(
        db,
        kind="grant",
        actor=actor,
        target_user=user_id,
        provider=None,
        result="success",
        extra={"action": "create", "role": role, "connection_id": connection_id},
    )
    db.refresh(row)
    return row


def revoke_connection_access(
    db: Session,
    *,
    workspace_id: str,
    grant_id: str,
    actor_user_id: str | None = None,
) -> None:
    actor = actor_user_id or "system"
    grant = db.get(ConnectionAccessGrant, grant_id)
    if grant is None or grant.workspace_id != workspace_id:
        record_auth_event(
            db,
            kind="revoke",
            actor=actor,
            target_user=None,
            provider=None,
            result="failure",
            extra={"action": "revoke", "grant_id": grant_id},
        )
        raise AccountError("not_found", "Grant not found.", 404)
    target = grant.user_id
    connection_id = grant.connection_id
    db.delete(grant)
    record_auth_event(
        db,
        kind="revoke",
        actor=actor,
        target_user=target,
        provider=None,
        result="success",
        extra={"action": "revoke", "grant_id": grant_id, "connection_id": connection_id},
    )


def enroll_totp(db: Session, user: User | None, *, actor_user_id: str | None = None) -> tuple[str, str]:
    import pyotp

    actor = actor_user_id or (user.id if user is not None else "anonymous")
    if user is None:
        record_auth_event(
            db,
            kind="totp",
            actor=actor,
            target_user=None,
            provider="totp",
            result="failure",
            extra={"action": "enroll"},
        )
        raise AccountError("not_found", "User not found.", 404)
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_enabled = False
    db.add(user)
    record_auth_event(
        db,
        kind="totp",
        actor=actor,
        target_user=user.id,
        provider="totp",
        result="success",
        extra={"action": "enroll"},
    )
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Odoo Custom")
    return secret, uri


def disable_totp(db: Session, user: User | None, *, actor_user_id: str | None = None) -> None:
    actor = actor_user_id or (user.id if user is not None else "anonymous")
    if user is None or not user.totp_enabled:
        record_auth_event(
            db,
            kind="totp",
            actor=actor,
            target_user=user.id if user is not None else None,
            provider="totp",
            result="failure",
            extra={"action": "disable"},
        )
        raise AccountError("totp_not_enabled", "TOTP is not enabled.", 400)
    user.totp_enabled = False
    user.totp_secret = None
    db.query(TotpRecoveryCode).filter(TotpRecoveryCode.user_id == user.id).delete()
    db.add(user)
    record_auth_event(
        db,
        kind="totp",
        actor=actor,
        target_user=user.id,
        provider="totp",
        result="success",
        extra={"action": "disable"},
    )


def change_membership_role(
    db: Session,
    *,
    workspace_id: str,
    target_user_id: str,
    role: str,
    actor_user_id: str | None = None,
) -> WorkspaceMembership:
    actor = actor_user_id or "system"

    def _fail(code: str, message: str, status: int = 400) -> None:
        record_auth_event(
            db,
            kind="grant",
            actor=actor,
            target_user=target_user_id,
            provider=None,
            result="failure",
            extra={"action": "role_change", "role": role},
        )
        raise AccountError(code, message, status)

    if role not in VALID_ROLES or role == "owner":
        _fail("invalid_role", "Invalid membership role.")
    membership = (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == target_user_id,
        )
        .first()
    )
    if membership is None:
        _fail("not_found", "Membership not found.", 404)
    if membership.role == "owner":
        _fail("invalid_role", "Owner role cannot be changed here.")
    membership.role = role
    db.add(membership)
    record_auth_event(
        db,
        kind="grant",
        actor=actor,
        target_user=target_user_id,
        provider=None,
        result="success",
        extra={"action": "role_change", "role": role},
    )
    db.refresh(membership)
    return membership


def create_session(
    db: Session,
    *,
    user: User,
    workspace_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[UserSession, str]:
    if workspace_id is None:
        workspace_id, _role = login_workspace(db, user)
    else:
        membership = (
            db.query(WorkspaceMembership)
            .filter(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
            .first()
        )
        grants = grants_for_user(db, user.id, workspace_id)
        if membership is None and not grants and not user.is_superadmin:
            raise AccountError("no_workspace", "User has no workspace membership.", 400)

    raw = generate_token()
    session = UserSession(
        user_id=user.id,
        workspace_id=workspace_id,
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(days=SESSION_DAYS),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, raw


def resolve_session(db: Session, raw_token: str | None) -> SessionContext | None:
    if not raw_token:
        return None
    digest = hash_token(raw_token)
    row = (
        db.query(UserSession)
        .filter(
            UserSession.token_hash == digest,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > _now(),
        )
        .first()
    )
    if row is None:
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    role = "owner"
    connection_scope: frozenset[str] | None = None
    if row.workspace_id and not user.is_superadmin:
        membership = (
            db.query(WorkspaceMembership)
            .filter(
                WorkspaceMembership.workspace_id == row.workspace_id,
                WorkspaceMembership.user_id == user.id,
            )
            .first()
        )
        if membership is not None:
            role = membership.role
        else:
            grants = grants_for_user(db, user.id, row.workspace_id)
            if not grants:
                return None
            role = role_from_grants(grants)
            connection_scope = frozenset(grant.connection_id for grant in grants)
    return SessionContext(
        user_id=user.id,
        email=user.email,
        workspace_id=row.workspace_id or "",
        role=role,
        is_superadmin=user.is_superadmin,
        session_id=row.id,
        connection_scope=connection_scope,
    )


def revoke_session(db: Session, raw_token: str) -> None:
    digest = hash_token(raw_token)
    row = db.query(UserSession).filter(UserSession.token_hash == digest).first()
    if row and row.revoked_at is None:
        row.revoked_at = _now()
        db.add(row)
        db.commit()


def revoke_all_sessions(db: Session, user_id: str) -> None:
    rows = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .all()
    )
    now = _now()
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()


def request_password_reset(db: Session, email: str) -> None:
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return
    raw = generate_token()
    row = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(hours=RESET_HOURS),
    )
    db.add(row)
    db.commit()
    reset_url = f"{settings.app_public_url.rstrip('/')}/reset-password?token={raw}"
    send_email(
        to=email,
        subject="Reset your Ingenium password",
        body=f"Reset link (expires in {RESET_HOURS}h):\n\n{reset_url}\n",
        html=receipt_html(title="Reset your password", lead=f"Choose a new password. The link works for {RESET_HOURS} hours.", button_label="Reset password", button_url=reset_url, footnote="If you didn't ask for this, your password stays as it is."),
    )


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    validate_password_policy(new_password)
    digest = hash_token(raw_token)
    row = (
        db.query(PasswordReset)
        .filter(PasswordReset.token_hash == digest, PasswordReset.used_at.is_(None))
        .first()
    )
    if row is None or row.expires_at < _now():
        raise AccountError("invalid_token", "Reset link is invalid or expired.", 400)
    user = db.get(User, row.user_id)
    if user is None:
        raise AccountError("invalid_token", "Reset link is invalid.", 400)
    row.used_at = _now()
    user.password_hash = hash_password(new_password)
    user.password_login_enabled = True
    user.failed_login_count = 0
    user.locked_until = None
    db.add(row)
    db.add(user)
    revoke_all_sessions(db, user.id)
    db.refresh(user)
    return user


def create_invitation(
    db: Session,
    *,
    workspace_id: str,
    email: str,
    role: str,
    invited_by_user_id: str,
) -> str:
    if role not in VALID_ROLES or role == "owner":
        raise AccountError("invalid_role", "Invalid invitation role.")
    email = normalize_email(email)
    validate_email(email)
    raw = generate_token()
    row = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(days=INVITE_DAYS),
        invited_by_user_id=invited_by_user_id,
    )
    db.add(row)
    db.commit()
    invite_url = f"{settings.app_public_url.rstrip('/')}/accept-invite?token={raw}"
    send_email(
        to=email,
        subject="You're invited to an Ingenium workspace",
        body=f"Accept invitation (expires in {INVITE_DAYS} days):\n\n{invite_url}\n",
        html=receipt_html(title="You're invited to a workspace", lead=f"Join the workspace to work on its Odoo databases. The invitation works for {INVITE_DAYS} days.", button_label="Accept invitation", button_url=invite_url),
    )
    return raw


def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    password: str | None = None,
    name: str | None = None,
) -> tuple[User, Workspace]:
    digest = hash_token(raw_token)
    invite = (
        db.query(WorkspaceInvitation)
        .filter(
            WorkspaceInvitation.token_hash == digest,
            WorkspaceInvitation.accepted_at.is_(None),
        )
        .first()
    )
    if invite is None or invite.expires_at < _now():
        raise AccountError("invalid_token", "Invitation is invalid or expired.", 400)

    workspace = db.get(Workspace, invite.workspace_id)
    if workspace is None:
        raise AccountError("invalid_token", "Invitation workspace not found.", 400)

    user = db.query(User).filter(User.email == invite.email).first()
    if user is None:
        if not password:
            raise AccountError("password_required", "Password required for new account.", 400)
        validate_password_policy(password)
        user = User(
            email=invite.email,
            password_hash=hash_password(password),
            email_verified=True,
        )
        db.add(user)
        db.flush()
    else:
        existing = (
            db.query(WorkspaceMembership)
            .filter(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )
            .first()
        )
        if existing:
            raise AccountError("already_member", "Already a member of this workspace.", 409)

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role=invite.role,
    )
    invite.accepted_at = _now()
    db.add(membership)
    db.add(invite)
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace


def ensure_default_workspace_for_legacy_rows(db: Session) -> str | None:
    """Backfill workspace_id on connections/projects when missing."""
    from app.db_models import CustomizationProject, OdooConnection

    needs = (
        db.query(OdooConnection).filter(OdooConnection.workspace_id.is_(None)).first()
        or db.query(CustomizationProject).filter(CustomizationProject.workspace_id.is_(None)).first()
    )
    if needs is None:
        return None

    ws = db.query(Workspace).filter(Workspace.slug == "default").first()
    if ws is None:
        ws = Workspace(name="Default workspace", slug="default", plan="free_solo")
        db.add(ws)
        db.flush()

    db.query(OdooConnection).filter(OdooConnection.workspace_id.is_(None)).update(
        {OdooConnection.workspace_id: ws.id},
        synchronize_session=False,
    )
    db.query(CustomizationProject).filter(CustomizationProject.workspace_id.is_(None)).update(
        {CustomizationProject.workspace_id: ws.id},
        synchronize_session=False,
    )
    db.commit()
    return ws.id


def timing_safe_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
