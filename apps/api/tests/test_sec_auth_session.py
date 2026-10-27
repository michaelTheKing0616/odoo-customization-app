"""SEC-AUTH-SESSION AC1. Accounts-mode passwords, cookies, session lifetime, MFA.

Handover §6.1 AC2 (master handover line 735). In ``accounts`` mode:

- A new password hash is Argon2id (``$argon2id$``) or bcrypt cost 12 or more.
- Login sets ``oc_session`` with ``HttpOnly``, ``Secure``, and ``SameSite=Lax``.
  ``Max-Age``, when present, is at most 7 days. ``Secure`` is set even when
  ``settings.session_cookie_secure`` is false.
- Login rotates the presented session: the new cookie value differs, and the
  previous token no longer resolves.
- Idle lifetime is 12 hours from the last use of that session. Absolute
  lifetime is 7 days from the session's start. Use inside the idle window
  extends idle time and cannot extend the absolute cap.
- Session age uses ``app.account_service._now``, the same clock as
  ``create_session``.
- TOTP is available before a session exists:
  ``POST /api/accounts/totp/enroll`` with ``{"email", "password"}`` returns
  ``secret`` and an ``otpauth://`` ``provisioning_uri``, and does not open a
  session. ``POST /api/accounts/totp/verify`` with ``{"email", "password",
  "code"}`` enables TOTP and does not open a session.
- A wrong password does not enroll TOTP.
- Owners and client approvers do not get a session from password login until
  TOTP is enabled. With a valid ``totp_code``, login opens a session.
- Passkeys are required only when a passkey or WebAuthn route is registered.
  None is registered, so this module does not invent a passkey failure.

Passing checks stay ordinary asserts. Each missing behaviour is its own
``pytest.mark.xfail(strict=True)`` and the reason starts with a SEC-6.1 id.

The fixture database is the process ``ingenium_`` database. This module does
not open another database and does not bind port 8001.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pyotp
import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from app import account_service
from app.account_models import User, UserSession, WorkspaceMembership
from app.account_service import (
    SESSION_COOKIE,
    AccountError,
    authenticate_user,
    enroll_totp,
    grant_connection_access,
    hash_password,
    login_workspace,
    resolve_session,
    signup_user,
    verify_password,
)
from app.crypto import encrypt_secret
from app.db import SessionLocal, init_db
from app.db_models import OdooConnection
from app.main import app
from app.settings import settings

_OWNER_PASSWORD = "owner-session-99"
_APPROVER_PASSWORD = "approver-session-99"
_WRONG_PASSWORD = "wrong-session-99"
_IDLE = timedelta(hours=12)
_ABSOLUTE = timedelta(days=7)
_ABSOLUTE_COOKIE_SECONDS = 7 * 24 * 3600
_ENROLL = "/api/accounts/totp/enroll"
_VERIFY = "/api/accounts/totp/verify"
_LOGIN = "/api/accounts/login"
_ME = "/api/accounts/me"
_BCRYPT = re.compile(r"^\$(2[aby])\$(\d{2})\$")


def _require_ingenium_database() -> None:
    """Refuse to run unless the app URL names a loopback ingenium_ database."""
    parsed = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql", 1))
    name = (parsed.path or "/").lstrip("/").split("?", 1)[0]
    host = (parsed.hostname or "").rstrip(".").lower()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("refusing a non-loopback database host")
    if not name.startswith("ingenium_"):
        raise RuntimeError("refusing a database whose name does not start with ingenium_")


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:12]}@example.com"


def _json(response) -> dict:
    try:
        body = response.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _set_cookie_headers(response) -> list[str]:
    getter = getattr(response.headers, "get_list", None)
    if getter is not None:
        values = [value for value in getter("set-cookie") if value]
        if values:
            return list(values)
    single = response.headers.get("set-cookie")
    return [single] if single else []


def _session_cookie_header(response) -> str | None:
    prefix = f"{SESSION_COOKIE}="
    for header in _set_cookie_headers(response):
        if header.lower().startswith(prefix.lower()):
            return header
    return None


def _cookie_value(header: str | None) -> str | None:
    if not header or "=" not in header:
        return None
    value = header.split(";", 1)[0].split("=", 1)[1].strip().strip('"')
    return value or None


def _cookie_attributes(header: str | None) -> set[str]:
    if not header:
        return set()
    return {part.strip().lower().replace(" ", "") for part in header.split(";")[1:] if part.strip()}


def _cookie_problems(header: str | None) -> list[str]:
    """Missing flags, or a Max-Age longer than the 7-day absolute cap."""
    if header is None:
        return ["login did not set the session cookie"]
    attributes = _cookie_attributes(header)
    problems: list[str] = []
    if "httponly" not in attributes:
        problems.append("session cookie is missing HttpOnly")
    if "secure" not in attributes:
        problems.append("session cookie is missing Secure")
    if "samesite=lax" not in attributes:
        problems.append("session cookie SameSite is not Lax")
    for attribute in attributes:
        if not attribute.startswith("max-age="):
            continue
        seconds = int(attribute.split("=", 1)[1])
        if seconds > _ABSOLUTE_COOKIE_SECONDS:
            problems.append(f"session cookie Max-Age {seconds}s exceeds 7 days")
    return problems


def _hash_policy_problem(value: str) -> str | None:
    if value.startswith("$argon2id$"):
        return None
    match = _BCRYPT.match(value)
    if match and int(match.group(2)) >= 12:
        return None
    return "password hash is not Argon2id or bcrypt cost 12 or more"


def _live_session_count(user_id: str) -> int:
    db = SessionLocal()
    try:
        now = account_service._now()
        count = 0
        rows = (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .all()
        )
        for row in rows:
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > now:
                count += 1
        return count
    finally:
        db.close()


def _resolved(token: str | None) -> bool:
    if not token:
        return False
    db = SessionLocal()
    try:
        return resolve_session(db, token) is not None
    finally:
        db.close()


def _login(client: TestClient, email: str, password: str, totp: str | None = None, present: str | None = None):
    client.cookies.clear()
    if present:
        client.cookies.set(SESSION_COOKIE, present)
    body: dict[str, str] = {"email": email, "password": password}
    if totp is not None:
        body["totp_code"] = totp
    return client.post(_LOGIN, json=body)


def _me(client: TestClient, token: str):
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, token)
    return client.get(_ME)


def _looks_logged_in(response) -> bool:
    if _session_cookie_header(response) is not None:
        return True
    if response.status_code != 200:
        return False
    body = _json(response)
    return "user" in body and "workspace" in body


def _verified_owner(db, tag: str, password: str) -> User:
    user, _workspace, _token = signup_user(
        db,
        email=_email(tag),
        password=password,
        workspace_name=tag,
    )
    user.email_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_approver(db, password: str) -> User:
    """A client approver with no workspace membership, so login is not as owner."""
    owner = _verified_owner(db, "agency", _OWNER_PASSWORD)
    approver = _verified_owner(db, "approver", password)
    _workspace_id, owner_role = login_workspace(db, owner)
    if owner_role != "owner":
        raise AssertionError(f"test setup: agency login role is {owner_role}")
    connection = OdooConnection(
        name="Session approver client",
        url="http://127.0.0.1:9",
        db_name=f"ingenium_sec_auth_{uuid.uuid4().hex[:8]}",
        username="unused",
        secret_encrypted=encrypt_secret("unused"),
        workspace_id=_workspace_id,
    )
    db.add(connection)
    db.commit()
    grant_connection_access(
        db,
        workspace_id=_workspace_id,
        connection_id=connection.id,
        user_id=approver.id,
        role="client_approver",
        actor_user_id=owner.id,
    )
    deleted = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.user_id == approver.id)
        .delete()
    )
    db.commit()
    if deleted != 1:
        raise AssertionError("test setup: approver membership was not removed")
    db.refresh(approver)
    _grant_workspace, role = login_workspace(db, approver)
    if role != "client_approver":
        raise AssertionError(f"test setup: approver login role is {role}")
    return approver


def _enable_totp(db, user: User) -> str:
    db.refresh(user)
    secret, _uri = enroll_totp(db, user, actor_user_id=user.id)
    user.totp_enabled = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return secret


def _password_accepted(db, email: str, password: str) -> bool:
    try:
        return authenticate_user(db, email=email, password=password) is not None
    except AccountError:
        db.rollback()
        return False
    except Exception:
        db.rollback()
        return False


def _foreign_hash(password: str, kind: Type) -> str:
    """Fixture hash from the already-installed argon2 package. Not a new dependency."""
    return PasswordHasher(
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        hash_len=16,
        salt_len=8,
        type=kind,
    ).hash(password)


def _open(client: TestClient, token: str, label: str, problems: list[str]) -> bool:
    response = _me(client, token)
    if response.status_code == 200:
        return True
    problems.append(f"{label}: expected 200, got {response.status_code}")
    return False


def _closed(client: TestClient, token: str, label: str, problems: list[str]) -> None:
    response = _me(client, token)
    resolved = _resolved(token)
    if response.status_code == 401 and not resolved:
        return
    problems.append(
        f"{label}: expected 401 and no resolved session, "
        f"got {response.status_code}, resolved={resolved}"
    )


def _open_totp_session(client: TestClient, db, tag: str, password: str):
    """Turn on TOTP in the service, then log in. HTTP enroll is a separate check."""
    user = _verified_owner(db, tag, password)
    secret = _enable_totp(db, user)
    response = _login(client, user.email, password, pyotp.TOTP(secret).now())
    header = _session_cookie_header(response)
    return user, secret, response, header, _cookie_value(header)


def _use_inside_absolute_window(
    client: TestClient,
    clock: dict,
    token: str,
    started: datetime,
) -> bool:
    """Touch the session through 6 days 12 hours. True when every touch is still open."""
    moment = timedelta(0)
    inside = timedelta(days=6, hours=12)
    while moment + timedelta(hours=11) <= inside:
        moment += timedelta(hours=11)
        clock["now"] = started + moment
        if _me(client, token).status_code != 200:
            return False
    clock["now"] = started + inside
    return _me(client, token).status_code == 200


@pytest.fixture
def accounts_session(monkeypatch: pytest.MonkeyPatch):
    """Accounts mode on this process's ingenium_ database. Clock is ``_now``."""
    _require_ingenium_database()
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "email_transport", "console")
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    clock = {"now": datetime.now(timezone.utc)}
    monkeypatch.setattr(account_service, "_now", lambda: clock["now"])
    init_db()
    with TestClient(app) as client:
        yield client, clock


def test_ac1_argon2id_verifies_password(accounts_session) -> None:
    """A new password hash is Argon2id and verifies only that password."""
    _client, _clock = accounts_session
    db = SessionLocal()
    try:
        owner = _verified_owner(db, "owner-hash", _OWNER_PASSWORD)
        stored = owner.password_hash or ""
        fresh = hash_password(_OWNER_PASSWORD)
        assert stored.startswith("$argon2id$")
        assert fresh.startswith("$argon2id$")
        assert _hash_policy_problem(stored) is None
        assert _hash_policy_problem(fresh) is None
        assert stored != _OWNER_PASSWORD
        assert fresh != _OWNER_PASSWORD
        assert verify_password(stored, _OWNER_PASSWORD)
        assert verify_password(fresh, _OWNER_PASSWORD)
        assert not verify_password(stored, _WRONG_PASSWORD)
        assert not verify_password(fresh, _WRONG_PASSWORD)
    finally:
        db.close()


def test_ac1_session_cookie_is_httponly_and_samesite_lax(accounts_session) -> None:
    """Login sets oc_session with HttpOnly and SameSite=Lax."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, header, token = _open_totp_session(
            client, db, "cookie-flags", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token and header
        attributes = _cookie_attributes(header)
        assert "httponly" in attributes
        assert "samesite=lax" in attributes
    finally:
        db.close()


def test_ac1_plaintext_password_hash_does_not_authenticate(accounts_session) -> None:
    """A password hash that is the plaintext password does not authenticate."""
    _client, _clock = accounts_session
    db = SessionLocal()
    try:
        user = _verified_owner(db, "plain", _OWNER_PASSWORD)
        user.password_hash = _OWNER_PASSWORD
        db.add(user)
        db.commit()
        assert not _password_accepted(db, user.email, _OWNER_PASSWORD)
    finally:
        db.close()


def test_ac1_wrong_password_does_not_enroll_totp(accounts_session) -> None:
    """A wrong password does not enroll TOTP or open a session."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        user = _verified_owner(db, "wrong-enroll", _OWNER_PASSWORD)
        wrong = client.post(
            _ENROLL,
            json={"email": user.email, "password": _WRONG_PASSWORD},
        )
        db.expire_all()
        db.refresh(user)
        assert not _json(wrong).get("secret")
        assert not user.totp_secret
        assert _session_cookie_header(wrong) is None
    finally:
        db.close()


def test_ac1_login_issues_a_different_resolving_session(accounts_session) -> None:
    """A second login issues a new session token, and that token resolves."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        user, secret, first, _header, first_token = _open_totp_session(
            client, db, "rotate-new", _OWNER_PASSWORD
        )
        assert first.status_code == 200 and first_token
        rotated = _login(
            client,
            user.email,
            _OWNER_PASSWORD,
            pyotp.TOTP(secret).now(),
            present=first_token,
        )
        rotated_token = _cookie_value(_session_cookie_header(rotated))
        assert rotated.status_code == 200 and rotated_token
        assert rotated_token != first_token
        assert _resolved(rotated_token)
    finally:
        db.close()


def test_ac1_session_resolves_11h_after_login(accounts_session) -> None:
    """A session still resolves 11 hours after it was opened."""
    client, clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, _header, token = _open_totp_session(
            client, db, "idle-11h", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token
        started = clock["now"]
        clock["now"] = started + timedelta(hours=11)
        problems: list[str] = []
        assert _open(client, token, "session at 11h idle", problems)
        assert not problems
    finally:
        db.close()


def test_ac1_approver_with_totp_opens_client_approver_session(accounts_session) -> None:
    """A client approver with a valid TOTP code gets that role's session."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        approver = _make_approver(db, _APPROVER_PASSWORD)
        secret = _enable_totp(db, approver)
        response = _login(
            client,
            approver.email,
            _APPROVER_PASSWORD,
            pyotp.TOTP(secret).now(),
        )
        token = _cookie_value(_session_cookie_header(response))
        role = (_json(response).get("workspace") or {}).get("role")
        assert response.status_code == 200 and token
        assert role == "client_approver"
        assert _resolved(token)
    finally:
        db.close()


def test_ac1_session_stays_open_inside_absolute_window(accounts_session) -> None:
    """Use through 6 days 12 hours leaves the session open."""
    client, clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, _header, token = _open_totp_session(
            client, db, "absolute-open", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token
        assert _use_inside_absolute_window(client, clock, token, clock["now"])
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-PRESESSION: TOTP enroll or verify without a session is not 200",
)
def test_ac1_totp_enroll_and_verify_without_a_session(accounts_session) -> None:
    """Email and password enroll TOTP, then verify it, without opening a session."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        owner = _verified_owner(db, "presession", _OWNER_PASSWORD)
        enrolled = client.post(
            _ENROLL,
            json={"email": owner.email, "password": _OWNER_PASSWORD},
        )
        body = _json(enrolled)
        secret = body.get("secret")
        uri = body.get("provisioning_uri")
        enroll_ok = (
            enrolled.status_code == 200
            and isinstance(secret, str)
            and bool(secret)
            and isinstance(uri, str)
            and uri.startswith("otpauth://")
            and _session_cookie_header(enrolled) is None
            and _live_session_count(owner.id) == 0
        )
        db.expire_all()
        db.refresh(owner)
        if isinstance(secret, str) and secret:
            code = pyotp.TOTP(secret).now()
        else:
            code = "000000"
        verified = client.post(
            _VERIFY,
            json={"email": owner.email, "password": _OWNER_PASSWORD, "code": code},
        )
        db.expire_all()
        db.refresh(owner)
        verify_ok = (
            verified.status_code == 200
            and bool(owner.totp_enabled)
            and _session_cookie_header(verified) is None
            and _live_session_count(owner.id) == 0
        )
        assert enroll_ok and verify_ok, (
            f"enroll status {enrolled.status_code}, verify status {verified.status_code}, "
            f"enabled={owner.totp_enabled}"
        )
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-COOKIE: cookie missing Secure, or Max-Age over 7 days",
)
def test_ac1_session_cookie_is_secure_and_within_seven_days(accounts_session) -> None:
    """The session cookie is Secure, and Max-Age is at most 7 days when set."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, header, token = _open_totp_session(
            client, db, "cookie-secure", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token and header
        problems = [
            problem
            for problem in _cookie_problems(header)
            if "Secure" in problem or "Max-Age" in problem
        ]
        assert not problems, "; ".join(problems)
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-ROTATE: previous session still resolves after login",
)
def test_ac1_login_stops_the_previous_session(accounts_session) -> None:
    """Login rotates the presented session so the previous token no longer resolves."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        user, secret, first, _header, first_token = _open_totp_session(
            client, db, "rotate-old", _OWNER_PASSWORD
        )
        assert first.status_code == 200 and first_token
        rotated = _login(
            client,
            user.email,
            _OWNER_PASSWORD,
            pyotp.TOTP(secret).now(),
            present=first_token,
        )
        rotated_token = _cookie_value(_session_cookie_header(rotated))
        assert rotated.status_code == 200 and rotated_token
        assert rotated_token != first_token
        assert not _resolved(first_token)
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-HASH: argon2i or argon2d authenticates",
)
def test_ac1_argon2i_and_argon2d_do_not_authenticate(accounts_session) -> None:
    """Argon2i and Argon2d password hashes do not authenticate."""
    _client, _clock = accounts_session
    db = SessionLocal()
    try:
        accepted: list[str] = []
        for kind, label in ((Type.I, "argon2i"), (Type.D, "argon2d")):
            user = _verified_owner(db, label, _OWNER_PASSWORD)
            user.password_hash = _foreign_hash(_OWNER_PASSWORD, kind)
            db.add(user)
            db.commit()
            if _password_accepted(db, user.email, _OWNER_PASSWORD):
                accepted.append(label)
        assert not accepted, f"{', '.join(accepted)} password hash authenticated"
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-MFA-ROLE: owner or approver password-only login opens a session",
)
def test_ac1_owner_and_approver_require_mfa(accounts_session) -> None:
    """Owners and client approvers do not get a session from a password alone."""
    client, _clock = accounts_session
    db = SessionLocal()
    try:
        owner = _verified_owner(db, "no-mfa", _OWNER_PASSWORD)
        owner_login = _login(client, owner.email, _OWNER_PASSWORD)
        owner_open = _looks_logged_in(owner_login) or bool(_live_session_count(owner.id))
        approver = _make_approver(db, _APPROVER_PASSWORD)
        approver_login = _login(client, approver.email, _APPROVER_PASSWORD)
        approver_open = _looks_logged_in(approver_login) or bool(_live_session_count(approver.id))
        assert not owner_open and not approver_open
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-IDLE: session still resolves 12h 10m after last use",
)
def test_ac1_idle_timeout_closes_session(accounts_session) -> None:
    """A session closes 12 hours 10 minutes after its last use."""
    client, clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, _header, token = _open_totp_session(
            client, db, "idle-cap", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token
        started = clock["now"]
        problems: list[str] = []
        assert _open(client, token, "idle session at login", problems)
        clock["now"] = started + _IDLE + timedelta(minutes=10)
        _closed(client, token, "idle session 12h 10m after its last use", problems)
        assert not problems
    finally:
        db.close()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.1-ABSOLUTE: session still resolves 7d 10m after it started",
)
def test_ac1_absolute_timeout_closes_session(accounts_session) -> None:
    """A session closes 7 days 10 minutes after it started, even after recent use."""
    client, clock = accounts_session
    db = SessionLocal()
    try:
        _user, _secret, response, _header, token = _open_totp_session(
            client, db, "absolute-cap", _OWNER_PASSWORD
        )
        assert response.status_code == 200 and token
        started = clock["now"]
        assert _use_inside_absolute_window(client, clock, token, started)
        clock["now"] = started + _ABSOLUTE - timedelta(hours=1)
        problems: list[str] = []
        assert _open(client, token, "absolute session inside day 7", problems)
        clock["now"] = started + _ABSOLUTE + timedelta(minutes=10)
        _closed(
            client,
            token,
            "absolute session 7d 10m after it started, with recent use",
            problems,
        )
        assert not problems
    finally:
        db.close()
