"""OAuth login — Google + GitHub via authlib (REM-13)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from sqlalchemy.orm import Session

from app.account_models import OAuthIdentity, OAuthPendingState, OAuthTotpPending, User, Workspace, WorkspaceMembership
from app.account_service import (
    AccountError,
    _now,
    _unique_slug,
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_email,
)
from app.settings import settings

SUPPORTED_PROVIDERS = frozenset({"google", "github"})
STATE_MINUTES = 10
TOTP_PENDING_MINUTES = 10


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scope: str
    userinfo_url: str
    email_from_userinfo: bool = True


@dataclass(frozen=True)
class OAuthProfile:
    provider: str
    subject: str
    email: str


@dataclass(frozen=True)
class OAuthLoginResult:
    user: User
    totp_pending_token: str | None = None


def enabled_oauth_providers() -> list[str]:
    if settings.auth_mode.strip().lower() != "accounts":
        return []
    configured = [p.strip().lower() for p in settings.oauth_providers.split(",") if p.strip()]
    out: list[str] = []
    for name in configured:
        if name not in SUPPORTED_PROVIDERS:
            continue
        cfg = _provider_config(name)
        if cfg and cfg.client_id and cfg.client_secret:
            out.append(name)
    return out


def _redirect_uri(provider: str) -> str:
    base = (settings.oauth_redirect_base or settings.app_public_url).rstrip("/")
    return f"{base}/api/accounts/oauth/{provider}/callback"


def _provider_config(provider: str) -> ProviderConfig | None:
    if provider == "google":
        return ProviderConfig(
            name="google",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        )
    if provider == "github":
        return ProviderConfig(
            name="github",
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
            userinfo_url="https://api.github.com/user",
            email_from_userinfo=False,
        )
    return None


def create_oauth_start(db: Session, *, provider: str) -> tuple[str, str]:
    """Return (authorization_url, raw_state) after persisting PKCE verifier."""
    provider = provider.strip().lower()
    if provider not in enabled_oauth_providers():
        raise AccountError("oauth_disabled", "OAuth provider is not enabled.", 404)

    cfg = _provider_config(provider)
    assert cfg is not None

    raw_state = generate_token()
    code_verifier = secrets.token_urlsafe(64)
    pending = OAuthPendingState(
        state_hash=hash_token(raw_state),
        provider=provider,
        code_verifier=code_verifier,
        expires_at=_now() + timedelta(minutes=STATE_MINUTES),
    )
    db.add(pending)
    db.commit()

    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": _redirect_uri(provider),
        "scope": cfg.scope,
        "state": raw_state,
        "code_challenge": _pkce_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{cfg.authorize_url}?{urlencode(params)}", raw_state


def _pkce_challenge(verifier: str) -> str:
    import base64
    import hashlib

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _consume_pending_state(db: Session, *, provider: str, raw_state: str) -> OAuthPendingState:
    row = (
        db.query(OAuthPendingState)
        .filter(
            OAuthPendingState.state_hash == hash_token(raw_state),
            OAuthPendingState.provider == provider,
        )
        .first()
    )
    if row is None or row.expires_at < _now():
        raise AccountError("invalid_oauth_state", "OAuth state is invalid or expired.", 400)
    db.delete(row)
    db.commit()
    return row


def _build_oauth_client(cfg: ProviderConfig) -> OAuth2Client:
    return OAuth2Client(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        redirect_uri=_redirect_uri(cfg.name),
    )


def _fetch_profile(
    cfg: ProviderConfig,
    token: dict[str, Any],
    *,
    transport: httpx.Client | None = None,
) -> OAuthProfile:
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    client = transport or httpx.Client(timeout=15.0)
    own_client = transport is None
    try:
        user_resp = client.get(cfg.userinfo_url, headers=headers)
        user_resp.raise_for_status()
        data = user_resp.json()
        subject = str(data.get("sub") or data.get("id") or "")
        if not subject:
            raise AccountError("oauth_profile", "Provider profile missing subject.", 502)

        email = ""
        if cfg.email_from_userinfo:
            email = normalize_email(str(data.get("email") or ""))
        else:
            emails_resp = client.get(
                "https://api.github.com/user/emails",
                headers={**headers, "Accept": "application/vnd.github+json"},
            )
            emails_resp.raise_for_status()
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            verified = next((e for e in emails if e.get("verified")), None)
            picked = primary or verified or (emails[0] if emails else None)
            if picked:
                email = normalize_email(str(picked.get("email") or ""))

        if not email:
            raise AccountError("oauth_profile", "Provider did not return a verified email.", 502)
        validate_email(email)
        return OAuthProfile(provider=cfg.name, subject=subject, email=email)
    finally:
        if own_client:
            client.close()


def exchange_oauth_code(
    db: Session,
    *,
    provider: str,
    code: str,
    raw_state: str,
    transport: httpx.Client | None = None,
) -> OAuthProfile:
    provider = provider.strip().lower()
    pending = _consume_pending_state(db, provider=provider, raw_state=raw_state)
    cfg = _provider_config(provider)
    if cfg is None:
        raise AccountError("oauth_disabled", "OAuth provider is not enabled.", 404)

    client = _build_oauth_client(cfg)
    own_transport = transport is None
    http = transport or httpx.Client(timeout=15.0)
    try:
        token = client.fetch_token(
            cfg.token_url,
            code=code,
            code_verifier=pending.code_verifier,
            client=http,
        )
        return _fetch_profile(cfg, token, transport=http)
    finally:
        if own_transport:
            http.close()


def resolve_oauth_login(db: Session, profile: OAuthProfile) -> OAuthLoginResult:
    email = normalize_email(profile.email)
    profile = OAuthProfile(provider=profile.provider, subject=profile.subject, email=email)
    identity = (
        db.query(OAuthIdentity)
        .filter(
            OAuthIdentity.provider == profile.provider,
            OAuthIdentity.subject == profile.subject,
        )
        .first()
    )
    if identity is not None:
        user = db.get(User, identity.user_id)
        if user is None:
            raise AccountError("oauth_profile", "Linked account is missing.", 500)
        return _maybe_totp_pending(db, user)

    existing = db.query(User).filter(User.email == profile.email).first()
    if existing is not None:
        if not existing.email_verified:
            raise AccountError(
                "oauth_unverified_collision",
                "An unverified account exists for this email — verify it or use password login first.",
                409,
            )
        db.add(
            OAuthIdentity(
                user_id=existing.id,
                provider=profile.provider,
                subject=profile.subject,
                email=profile.email,
            )
        )
        db.commit()
        db.refresh(existing)
        return _maybe_totp_pending(db, existing)

    user = User(
        email=profile.email,
        password_hash=hash_password(generate_token()),
        password_login_enabled=False,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    ws_name = f"{profile.email.split('@')[0]}'s workspace"[:200]
    workspace = Workspace(name=ws_name, slug=_unique_slug(db, ws_name))
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    db.add(
        OAuthIdentity(
            user_id=user.id,
            provider=profile.provider,
            subject=profile.subject,
            email=profile.email,
        )
    )
    db.commit()
    db.refresh(user)
    return _maybe_totp_pending(db, user)


def _maybe_totp_pending(db: Session, user: User) -> OAuthLoginResult:
    if not user.totp_enabled:
        return OAuthLoginResult(user=user, totp_pending_token=None)
    raw = generate_token()
    db.add(
        OAuthTotpPending(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(minutes=TOTP_PENDING_MINUTES),
        )
    )
    db.commit()
    return OAuthLoginResult(user=user, totp_pending_token=raw)


def complete_oauth_totp(db: Session, *, raw_token: str, totp_code: str) -> User:
    import pyotp

    row = (
        db.query(OAuthTotpPending)
        .filter(
            OAuthTotpPending.token_hash == hash_token(raw_token),
        )
        .first()
    )
    if row is None or row.expires_at < _now():
        raise AccountError("invalid_oauth_state", "OAuth 2FA token is invalid or expired.", 400)
    user = db.get(User, row.user_id)
    if user is None or not user.totp_secret:
        raise AccountError("invalid_oauth_state", "OAuth 2FA token is invalid.", 400)
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(totp_code.strip(), valid_window=1):
        raise AccountError("invalid_2fa", "Invalid 2FA code.", 401)
    db.delete(row)
    db.commit()
    return user


def list_oauth_identities(db: Session, user_id: str) -> list[OAuthIdentity]:
    return (
        db.query(OAuthIdentity)
        .filter(OAuthIdentity.user_id == user_id)
        .order_by(OAuthIdentity.created_at.asc())
        .all()
    )


def count_login_methods(db: Session, user: User) -> int:
    oauth_count = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user.id).count()
    password = 1 if user.password_login_enabled else 0
    return oauth_count + password


def unlink_oauth_identity(db: Session, *, user: User, provider: str) -> None:
    provider = provider.strip().lower()
    identity = (
        db.query(OAuthIdentity)
        .filter(OAuthIdentity.user_id == user.id, OAuthIdentity.provider == provider)
        .first()
    )
    if identity is None:
        raise AccountError("oauth_not_linked", f"{provider} is not linked to this account.", 404)
    if count_login_methods(db, user) <= 1:
        raise AccountError(
            "oauth_last_method",
            "Cannot unlink your only sign-in method.",
            400,
        )
    db.delete(identity)
    db.commit()
