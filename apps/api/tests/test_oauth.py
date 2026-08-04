"""REM-13 OAuth login tests (mocked provider profile + state)."""

from __future__ import annotations

import os
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_models import OAuthIdentity, User  # noqa: E402
from app.account_service import SESSION_COOKIE, hash_password, signup_user  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.oauth_service import (  # noqa: E402
    OAuthProfile,
    complete_oauth_totp,
    create_oauth_start,
    enabled_oauth_providers,
    exchange_oauth_code,
    resolve_oauth_login,
    unlink_oauth_identity,
)
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _email(local: str) -> str:
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


def _enable_google_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "oauth_providers", "google,github")
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-client-secret")
    monkeypatch.setattr(settings, "github_oauth_client_id", "github-client-id")
    monkeypatch.setattr(settings, "github_oauth_client_secret", "github-client-secret")
    monkeypatch.setattr(settings, "app_public_url", "http://127.0.0.1:3000")


def test_oauth_providers_off_by_default(client: TestClient) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "oauth_providers", "")
    assert enabled_oauth_providers() == []
    resp = client.get("/api/accounts/oauth/providers")
    assert resp.status_code == 200
    assert resp.json()["providers"] == []
    monkeypatch.undo()


def test_oauth_new_user_create(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    email = _email("oauth-new")
    db = SessionLocal()
    try:
        result = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject=f"google-sub-1-{uuid.uuid4().hex[:8]}", email=email),
        )
        assert result.totp_pending_token is None
        user = db.get(User, result.user.id)
        assert user is not None
        assert user.email_verified is True
        assert user.password_login_enabled is False
        identity = (
            db.query(OAuthIdentity)
            .filter(OAuthIdentity.user_id == user.id, OAuthIdentity.provider == "google")
            .first()
        )
        assert identity is not None
    finally:
        db.close()


def test_oauth_links_verified_existing_email(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    email = _email("oauth-link")
    subject = f"google-sub-link-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        result = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject=subject, email=user.email),
        )
        assert result.user.id == user.id
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user.id).count() == 1
    finally:
        db.close()


def test_oauth_refuses_unverified_email_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    email = _email("oauth-unverified")
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="secure-pass-99")
        assert user.email_verified is False
        with pytest.raises(Exception) as exc:
            resolve_oauth_login(
                db,
                OAuthProfile(provider="google", subject="google-sub-unverified", email=email),
            )
        assert getattr(exc.value, "code", "") == "oauth_unverified_collision"
    finally:
        db.close()


def test_oauth_totp_after_login(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    email = _email("oauth-totp")
    db = SessionLocal()
    try:
        result = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject="google-sub-totp", email=email),
        )
        user = db.get(User, result.user.id)
        assert user is not None
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        db.add(user)
        db.commit()
        result2 = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject="google-sub-totp", email=email),
        )
        assert result2.totp_pending_token is not None
        code = pyotp.TOTP(secret).now()
        completed = complete_oauth_totp(db, raw_token=result2.totp_pending_token, totp_code=code)
        assert completed.id == user.id
    finally:
        db.close()


def test_oauth_unlink_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    email = _email("oauth-unlink")
    db = SessionLocal()
    try:
        result = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject="google-sub-unlink", email=email),
        )
        user = db.get(User, result.user.id)
        assert user is not None
        with pytest.raises(Exception) as exc:
            unlink_oauth_identity(db, user=user, provider="google")
        assert getattr(exc.value, "code", "") == "oauth_last_method"
    finally:
        db.close()


def test_oauth_forged_state_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    db = SessionLocal()
    try:
        with pytest.raises(Exception) as exc:
            exchange_oauth_code(
                db,
                provider="google",
                code="fake-code",
                raw_state="forged-state",
            )
        assert getattr(exc.value, "code", "") == "invalid_oauth_state"
    finally:
        db.close()


def test_oauth_start_redirects_when_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    resp = client.get("/api/accounts/oauth/google/start", follow_redirects=False)
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["location"]


def test_oauth_callback_sets_session(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_google_oauth(monkeypatch)
    init_db()
    db = SessionLocal()
    try:
        _, raw_state = create_oauth_start(db, provider="google")
    finally:
        db.close()

    email = _email("oauth-callback")
    profile = OAuthProfile(provider="google", subject="google-sub-callback", email=email)

    def fake_exchange(db_session, *, provider: str, code: str, raw_state: str, transport=None):
        assert provider == "google"
        assert code == "test-code"
        assert raw_state == raw_state_arg
        return profile

    raw_state_arg = raw_state
    monkeypatch.setattr("app.routers.accounts.exchange_oauth_code", fake_exchange)

    resp = client.get(
        "/api/accounts/oauth/google/callback",
        params={"code": "test-code", "state": raw_state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert SESSION_COOKIE in resp.cookies
    assert resp.headers["location"].endswith("/connect")
