"""REM-13 OAuth login tests (mocked provider profile + state)."""

from __future__ import annotations

import os
import uuid

import httpx
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
    _fetch_profile,
    _provider_config,
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


def _enable_microsoft_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "oauth_providers", "google,microsoft")
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-client-secret")
    monkeypatch.setattr(settings, "microsoft_oauth_client_id", "ms-client-id")
    monkeypatch.setattr(settings, "microsoft_oauth_client_secret", "ms-client-secret")
    monkeypatch.setattr(settings, "app_public_url", "http://127.0.0.1:3000")


def _mock_oauth_exchange(
    monkeypatch: pytest.MonkeyPatch,
    profile: OAuthProfile,
    *,
    expected_code: str = "test-code",
) -> None:
    def fake_exchange(db_session, *, provider: str, code: str, raw_state: str, transport=None):
        assert provider == profile.provider
        assert code == expected_code
        return profile

    monkeypatch.setattr("app.routers.accounts.exchange_oauth_code", fake_exchange)


def _oauth_callback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    profile: OAuthProfile,
    *,
    code: str = "test-code",
):
    db = SessionLocal()
    try:
        _, raw_state = create_oauth_start(db, provider=profile.provider)
    finally:
        db.close()
    _mock_oauth_exchange(monkeypatch, profile, expected_code=code)
    return client.get(
        f"/api/accounts/oauth/{profile.provider}/callback",
        params={"code": code, "state": raw_state},
        follow_redirects=False,
    )


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


def test_microsoft_callback_new_user(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_microsoft_oauth(monkeypatch)
    init_db()
    email = _email("ms-new")
    profile = OAuthProfile(
        provider="microsoft",
        subject=f"ms-sub-new-{uuid.uuid4().hex[:8]}",
        email=email,
        email_verified=True,
    )
    resp = _oauth_callback(client, monkeypatch, profile)
    assert resp.status_code == 302
    assert SESSION_COOKIE in resp.cookies
    assert resp.headers["location"].endswith("/connect")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        assert user.email_verified is True
        assert user.password_login_enabled is False
        identities = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user.id).all()
        assert len(identities) == 1
        assert identities[0].provider == "microsoft"
        assert identities[0].subject == profile.subject
    finally:
        db.close()


def test_microsoft_callback_links_verified_existing_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_microsoft_oauth(monkeypatch)
    init_db()
    email = _email("ms-link")
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    profile = OAuthProfile(
        provider="microsoft",
        subject=f"ms-sub-link-{uuid.uuid4().hex[:8]}",
        email=email,
        email_verified=True,
    )
    resp = _oauth_callback(client, monkeypatch, profile)
    assert resp.status_code == 302
    assert SESSION_COOKIE in resp.cookies
    assert resp.headers["location"].endswith("/connect")

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == email).count() == 1
        identities = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user_id).all()
        assert len(identities) == 1
        assert identities[0].provider == "microsoft"
        assert identities[0].subject == profile.subject
    finally:
        db.close()


def test_microsoft_callback_second_provider_on_google_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_microsoft_oauth(monkeypatch)
    init_db()
    email = _email("ms-second")
    google_subject = f"google-sub-second-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        result = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject=google_subject, email=email, email_verified=True),
        )
        user_id = result.user.id
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user_id).count() == 1
    finally:
        db.close()

    ms_profile = OAuthProfile(
        provider="microsoft",
        subject=f"ms-sub-second-{uuid.uuid4().hex[:8]}",
        email=email,
        email_verified=True,
    )
    resp = _oauth_callback(client, monkeypatch, ms_profile)
    assert resp.status_code == 302
    assert SESSION_COOKIE in resp.cookies
    assert resp.headers["location"].endswith("/connect")

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == email).count() == 1
        identities = (
            db.query(OAuthIdentity)
            .filter(OAuthIdentity.user_id == user_id)
            .order_by(OAuthIdentity.provider.asc())
            .all()
        )
        assert [row.provider for row in identities] == ["google", "microsoft"]
        assert {row.subject for row in identities} == {google_subject, ms_profile.subject}
    finally:
        db.close()


def _microsoft_profile_from_userinfo(*, email: str, subject: str) -> OAuthProfile:
    """Build a profile the way live Microsoft OAuth does: Graph userinfo has email, no email_verified."""
    body = {"sub": subject, "email": email}
    assert "email_verified" not in body

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://graph.microsoft.com/oidc/userinfo"
        return httpx.Response(200, json=body)

    cfg = _provider_config("microsoft")
    assert cfg is not None
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        profile = _fetch_profile(cfg, {"access_token": "ms-access-token"}, transport=transport)
    assert profile.provider == "microsoft"
    assert profile.subject == subject
    assert profile.email == email
    assert profile.email_verified is True
    return profile


def test_microsoft_userinfo_without_email_verified_claim_allows_create_and_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_microsoft_oauth(monkeypatch)
    init_db()

    email_create = _email("ms-userinfo-create")
    create_subject = f"ms-sub-userinfo-create-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        created = resolve_oauth_login(
            db,
            _microsoft_profile_from_userinfo(email=email_create, subject=create_subject),
        )
        assert created.totp_pending_token is None
        created_user = db.get(User, created.user.id)
        assert created_user is not None
        assert created_user.email == email_create
        assert created_user.email_verified is True
        assert created_user.password_login_enabled is False
        create_identities = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == created_user.id).all()
        assert len(create_identities) == 1
        assert create_identities[0].provider == "microsoft"
        assert create_identities[0].subject == create_subject
    finally:
        db.close()

    email_link = _email("ms-userinfo-link")
    link_subject = f"ms-sub-userinfo-link-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        existing, _, _ = signup_user(db, email=email_link, password="secure-pass-99")
        existing.email_verified = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        linked = resolve_oauth_login(
            db,
            _microsoft_profile_from_userinfo(email=existing.email, subject=link_subject),
        )
        assert linked.user.id == existing.id
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == existing.id).count() == 1
        identity = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == existing.id).one()
        assert identity.provider == "microsoft"
        assert identity.subject == link_subject
    finally:
        db.close()

    email_second = _email("ms-userinfo-second")
    google_subject = f"google-sub-userinfo-second-{uuid.uuid4().hex[:8]}"
    ms_subject = f"ms-sub-userinfo-second-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        first = resolve_oauth_login(
            db,
            OAuthProfile(provider="google", subject=google_subject, email=email_second, email_verified=True),
        )
        user_id = first.user.id
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user_id).count() == 1
        second = resolve_oauth_login(
            db,
            _microsoft_profile_from_userinfo(email=email_second, subject=ms_subject),
        )
        assert second.user.id == user_id
        identities = (
            db.query(OAuthIdentity)
            .filter(OAuthIdentity.user_id == user_id)
            .order_by(OAuthIdentity.provider.asc())
            .all()
        )
        assert [row.provider for row in identities] == ["google", "microsoft"]
        assert {row.subject for row in identities} == {google_subject, ms_subject}
    finally:
        db.close()


def test_microsoft_unverified_provider_email_does_not_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_microsoft_oauth(monkeypatch)
    init_db()
    email = _email("ms-unverified-provider")
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    profile = OAuthProfile(
        provider="microsoft",
        subject=f"ms-sub-unverified-{uuid.uuid4().hex[:8]}",
        email=email,
        email_verified=False,
    )
    resp = _oauth_callback(client, monkeypatch, profile)
    assert resp.status_code == 302
    assert SESSION_COOKIE not in resp.cookies
    assert "oauth_error=oauth_unverified_email" in resp.headers["location"]

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.id == user_id).one().email == email
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user_id).count() == 0
        assert db.query(User).filter(User.email == email).count() == 1
    finally:
        db.close()


def test_password_signup_totp_enroll_and_login(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    email = _email("pw-totp")
    password = "secure-pass-99"

    signup = client.post(
        "/api/accounts/signup",
        json={"email": email, "password": password, "workspace_name": "TOTP Workspace"},
    )
    assert signup.status_code == 201, signup.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.email_verified = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert SESSION_COOKIE in login.cookies

    enroll = client.post("/api/accounts/totp/enroll")
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert secret
    code = pyotp.TOTP(secret).now()

    verify = client.post("/api/accounts/totp/verify", json={"code": code})
    assert verify.status_code == 200, verify.text
    assert len(verify.json()["recovery_codes"]) == 8

    logout = client.post("/api/accounts/logout")
    assert logout.status_code == 204

    missing_totp = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert missing_totp.status_code == 401
    assert missing_totp.json()["detail"]["error"] == "totp_required"

    totp_login = client.post(
        "/api/accounts/login",
        json={"email": email, "password": password, "totp_code": pyotp.TOTP(secret).now()},
    )
    assert totp_login.status_code == 200, totp_login.text
    assert SESSION_COOKIE in totp_login.cookies
    assert totp_login.json()["user"]["email"] == email
    assert totp_login.json()["user"]["totp_enabled"] is True
