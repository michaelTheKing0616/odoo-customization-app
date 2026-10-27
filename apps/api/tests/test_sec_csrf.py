"""SEC-CSRF AC1. CSRF token on every state-changing cookie-authenticated request.

Handover §6.1 AC4 (INGENIUM_MASTER_HANDOVER.md line 737).

A request is cookie-authenticated when the ``oc_session`` cookie resolves to a
session. POST, PUT, PATCH, and DELETE of such a request must send header
``X-CSRF-Token`` equal to the token issued for that session. The test client
sends no Origin and no Referer, so an Origin allow-list cannot pass.

The token is issued on the login response or on ``GET /api/accounts/me``, as
a response header ``X-CSRF-Token``, a JSON ``csrf_token``, or a Set-Cookie
``oc_csrf`` that is not HttpOnly. When more than one of those is present they
are the same value. The token is at least 22 characters and is not the
session cookie. A readable HttpOnly-only cookie does not count: the client
has to be able to copy the token into the header.

Missing header, blank header, or a different value is 403 and the body
contains ``csrf``. The handler does not run. Logout leaves the session
resolvable. Invitations inserts no row. The check is global: an unknown
``/api`` path is 403, not 404. Sending ``oc_csrf`` without the header is
still a rejection, including when that cookie is the issued token.

These are not CSRF rejections: GET, HEAD, and OPTIONS; a session cookie that
does not resolve; an API key with no resolved session; credential posts that
authorize by the posted secret (signup, login, verify-email,
request-password-reset, reset-password, accept-invite), including when a
resolved session cookie is also on the request.

The allow path sends the issued token in ``X-CSRF-Token`` and in ``oc_csrf``.
``POST /api/accounts/invitations`` then returns 201, an unknown path returns
404, and ``POST /api/accounts/logout`` returns 204 and the session no longer
resolves.

Runs on this process's ``ingenium_`` database only. Does not bind port 8001.

Passing checks stay ordinary asserts. Each missing behaviour is its own
``pytest.mark.xfail(strict=True)`` and the reason starts with a SEC-6.1 id.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.account_models import WorkspaceInvitation
from app.account_service import SESSION_COOKIE, normalize_email, resolve_session, signup_user
from app.auth import create_api_key_record
from app.db import SessionLocal, init_db
from app.main import app
from app.settings import settings

_PASSWORD = "csrf-oracle-session-99"
_LOGIN = "/api/accounts/login"
_LOGOUT = "/api/accounts/logout"
_ME = "/api/accounts/me"
_SIGNUP = "/api/accounts/signup"
_INVITE = "/api/accounts/invitations"
_CSRF_HEADER = "X-CSRF-Token"
_CSRF_COOKIE = "oc_csrf"
_MIN_TOKEN = 22
_FORGED = "forged-csrf-token-value"
_UNSAFE = ("POST", "PUT", "PATCH", "DELETE")
_SAFE = ("GET", "HEAD", "OPTIONS")
_CREDENTIAL_POSTS = (
    ("/api/accounts/verify-email", {"token": "not-a-token"}),
    ("/api/accounts/request-password-reset", {"email": "nobody-csrf@example.com"}),
    ("/api/accounts/reset-password", {"token": "not-a-token", "password": _PASSWORD}),
    ("/api/accounts/accept-invite", {"token": "not-a-token", "password": _PASSWORD}),
)


def _require_ingenium_database() -> None:
    """Refuse any database whose name does not start with ingenium_.

    Inputs: ``settings.database_url``. Output: none.
    Side effects: raises before a connection when the host is not loopback
    or the database name is not disposable.
    """
    parsed = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql", 1))
    name = (parsed.path or "/").lstrip("/").split("?", 1)[0]
    host = (parsed.hostname or "").rstrip(".").lower()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("refusing a non-loopback database host")
    if not name.startswith("ingenium_"):
        raise RuntimeError("refusing a database whose name does not start with ingenium_")


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:12]}@example.com"


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return {}
    return body if isinstance(body, dict) else {}


def _brief(response) -> str:
    text = " ".join(response.text.split())
    if len(text) > 180:
        text = text[:180] + "..."
    return f"{response.status_code} {text}"


def _set_cookie_headers(response) -> list[str]:
    getter = getattr(response.headers, "get_list", None)
    if callable(getter):
        values = [value for value in getter("set-cookie") if value]
        if values:
            return list(values)
    single = response.headers.get("set-cookie")
    return [single] if single else []


def _named_set_cookie(response, name: str) -> str | None:
    prefix = f"{name.lower()}="
    for header in _set_cookie_headers(response):
        if header.lower().startswith(prefix):
            return header
    return None


def _cookie_value(header: str | None) -> str | None:
    if not header or "=" not in header:
        return None
    value = header.split(";", 1)[0].split("=", 1)[1].strip().strip('"')
    return value or None


def _is_httponly(header: str | None) -> bool:
    if not header:
        return False
    parts = {part.strip().lower().replace(" ", "") for part in header.split(";")[1:]}
    return "httponly" in parts


def _issued_csrf(response) -> tuple[str | None, str | None]:
    """Read the CSRF token carried on this response.

    Inputs: one response. Output: ``(token, problem)``. Side effects: none.
    A problem is set when the channels disagree or the only channel is an
    HttpOnly cookie.
    """
    header = (response.headers.get(_CSRF_HEADER) or "").strip()
    raw_json = _json(response).get("csrf_token")
    json_token = raw_json.strip() if isinstance(raw_json, str) else ""
    cookie_header = _named_set_cookie(response, _CSRF_COOKIE)
    cookie_token = _cookie_value(cookie_header) or ""
    if cookie_token and _is_httponly(cookie_header) and not header and not json_token:
        return None, "oc_csrf is HttpOnly, so the client cannot copy it into X-CSRF-Token"
    usable_cookie = "" if _is_httponly(cookie_header) else cookie_token
    values = [value for value in (header, json_token, usable_cookie) if value]
    if not values:
        return None, None
    first = values[0]
    if any(value != first for value in values):
        return None, "response issued more than one CSRF token value"
    return first, None


def _is_csrf_rejection(response) -> bool:
    return response.status_code == 403 and "csrf" in response.text.lower()


def _expect_rejected(response, label: str, problems: list[str]) -> None:
    if _is_csrf_rejection(response):
        return
    problems.append(f"{label}: expected 403 csrf, got {_brief(response)}")


def _expect_allowed(response, label: str, problems: list[str]) -> None:
    if not _is_csrf_rejection(response):
        return
    problems.append(f"{label}: rejected as CSRF ({_brief(response)})")


def _use(client: TestClient, session: str, csrf_cookie: str | None = None) -> None:
    """Send only this session cookie, plus ``oc_csrf`` when a value is given.

    Inputs: client, session token, optional csrf cookie. Output: none.
    Side effects: replaces the client cookie jar.
    """
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, session)
    if csrf_cookie is not None:
        client.cookies.set(_CSRF_COOKIE, csrf_cookie)


def _headers(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    return {_CSRF_HEADER: token}


def _resolves(token: str) -> bool:
    db = SessionLocal()
    try:
        return resolve_session(db, token) is not None
    finally:
        db.close()


def _invite_count(email: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(WorkspaceInvitation)
            .filter(WorkspaceInvitation.email == normalize_email(email))
            .count()
        )
    finally:
        db.close()


def _open_owner(client: TestClient, tag: str) -> tuple[str, str, httpx.Response]:
    """Create a verified owner and log in. Returns email, session, response.

    Inputs: client and an email tag. Output: email, raw session, login response.
    Side effects: one user and one session in the process ingenium_ database.
    """
    db = SessionLocal()
    try:
        user, _workspace, _verify = signup_user(
            db,
            email=_email(tag),
            password=_PASSWORD,
            workspace_name=tag,
        )
        user.email_verified = True
        db.add(user)
        db.commit()
        email = user.email
    finally:
        db.close()
    response = client.post(_LOGIN, json={"email": email, "password": _PASSWORD})
    if response.status_code != 200:
        raise AssertionError(f"test setup: login failed ({_brief(response)})")
    session = _cookie_value(_named_set_cookie(response, SESSION_COOKIE))
    if not session or not _resolves(session):
        raise AssertionError("test setup: login did not open a session")
    return email, session, response


def _harvest(session: str, responses: list[httpx.Response]) -> tuple[str | None, list[str]]:
    """Collect one issued CSRF token from login and/or GET /me.

    Inputs: the session cookie value and the responses that may carry it.
    Output: token or None, and the issuance problems. Side effects: none.
    """
    problems: list[str] = []
    found: str | None = None
    for response in responses:
        token, problem = _issued_csrf(response)
        if problem:
            problems.append(problem)
        if token and found and token != found:
            problems.append("CSRF token changed between the responses that issued it")
        elif token:
            found = token
    issuance_broken = any(
        "HttpOnly" in problem or "more than one" in problem for problem in problems
    )
    if found is None and not issuance_broken:
        problems.append("no CSRF token on login or GET /api/accounts/me")
    if found is not None and len(found) < _MIN_TOKEN:
        problems.append(f"CSRF token is {len(found)} characters; need at least {_MIN_TOKEN}")
    if found is not None and found == session:
        problems.append("CSRF token is the session cookie")
    return found, problems


def _finish(problems: list[str]) -> None:
    assert not problems, "; ".join(problems)


@pytest.fixture
def accounts(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Accounts mode on this process's ingenium_ database. No port 8001."""
    _require_ingenium_database()
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "email_transport", "console")
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    init_db()
    with TestClient(app) as client:
        yield client


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.1-CSRF-GATE: cookie mutation without a matching X-CSRF-Token "
        "is not 403, and the handler still runs"
    ),
)
def test_ac1_positive_cookie_mutation_without_csrf_token_is_rejected(
    accounts: TestClient,
) -> None:
    """A resolved session cannot change state unless X-CSRF-Token matches.

    Fails when the server-side check is missing: the unknown path stays 404,
    invitations inserts a row, or logout revokes the session.
    """
    client = accounts
    _email_owner, session, _login_response = _open_owner(client, "csrf-deny")
    probe = f"/api/sec-csrf-{uuid.uuid4().hex}"
    problems: list[str] = []
    issued, _issue_problems = _issued_csrf(_login_response)
    cookie_without_header = issued or _FORGED

    for method in _UNSAFE:
        _use(client, session)
        response = client.request(method, probe)
        _expect_rejected(response, f"{method} {probe} with only the session cookie", problems)

    _use(client, session)
    form = client.post(
        probe,
        content=b"n=1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    _expect_rejected(form, "form POST with only the session cookie", problems)

    _use(client, session)
    json_post = client.post(probe, json={})
    _expect_rejected(json_post, "JSON POST with only the session cookie", problems)

    _use(client, session, csrf_cookie=cookie_without_header)
    cookie_only = client.post(probe)
    _expect_rejected(
        cookie_only,
        "POST with oc_csrf and no X-CSRF-Token",
        problems,
    )

    _use(client, session, csrf_cookie=issued)
    mismatched = client.post(probe, headers=_headers(_FORGED))
    _expect_rejected(mismatched, "POST with a CSRF token that was not issued", problems)

    invite_email = _email("csrf-deny-invite")
    before = _invite_count(invite_email)
    _use(client, session)
    invite = client.post(_INVITE, json={"email": invite_email, "role": "builder"})
    _expect_rejected(invite, "POST /api/accounts/invitations", problems)
    if _invite_count(invite_email) != before:
        problems.append("POST /api/accounts/invitations wrote a row without a CSRF token")

    _use(client, session)
    logout = client.post(_LOGOUT)
    _expect_rejected(logout, "POST /api/accounts/logout", problems)
    if not _resolves(session):
        problems.append("POST /api/accounts/logout without a CSRF token revoked the session")
    else:
        _use(client, session)
        me = client.get(_ME)
        if me.status_code != 200:
            problems.append(f"session did not survive the logout attempt ({_brief(me)})")

    _finish(problems)


def test_ac1_negative_safe_methods_credentials_and_non_session_are_not_csrf_rejections(
    accounts: TestClient,
) -> None:
    """Safe methods, credential posts, an API key, and an unknown session are not CSRF rejections.

    Fails when one of those responses is 403 and the body contains csrf, when
    GET /api/accounts/me is not 200, when signup is not 201, or when login is not 200.
    """
    client = accounts
    email, session, _login = _open_owner(client, "csrf-allow")
    _use(client, session)
    me = client.get(_ME)
    problems: list[str] = []
    _expect_allowed(me, "GET /api/accounts/me with a session and no CSRF token", problems)
    if me.status_code != 200:
        problems.append(f"GET /api/accounts/me with a session and no CSRF token ({_brief(me)})")

    probe = f"/api/sec-csrf-{uuid.uuid4().hex}"
    for method in _SAFE:
        _use(client, session)
        response = client.request(method, probe)
        _expect_allowed(response, f"{method} {probe}", problems)

    for path, body in _CREDENTIAL_POSTS:
        _use(client, session)
        response = client.post(path, json=body)
        _expect_allowed(response, f"POST {path} with a session cookie", problems)

    _use(client, session)
    signup = client.post(
        _SIGNUP,
        json={"email": _email("csrf-signup"), "password": _PASSWORD, "workspace_name": "csrf"},
    )
    _expect_allowed(signup, "POST /api/accounts/signup with a session cookie", problems)
    if signup.status_code != 201:
        problems.append(f"POST /api/accounts/signup ({_brief(signup)})")

    _use(client, session)
    relogin = client.post(_LOGIN, json={"email": email, "password": _PASSWORD})
    _expect_allowed(relogin, "POST /api/accounts/login with a session cookie", problems)
    if relogin.status_code != 200:
        problems.append(f"POST /api/accounts/login with a session cookie ({_brief(relogin)})")
    else:
        rotated = _cookie_value(_named_set_cookie(relogin, SESSION_COOKIE))
        if rotated and _resolves(rotated):
            session = rotated
        _use(client, session)
        me_after = client.get(_ME)
        _expect_allowed(me_after, "GET /api/accounts/me after login", problems)
        if me_after.status_code != 200:
            problems.append(f"GET /api/accounts/me after login ({_brief(me_after)})")

    db = SessionLocal()
    try:
        _row, raw_key = create_api_key_record(db, name="sec-csrf")
    finally:
        db.close()
    client.cookies.clear()
    api_key = client.post(
        _INVITE,
        json={"email": _email("csrf-api-key"), "role": "builder"},
        headers={"X-API-Key": raw_key},
    )
    _expect_allowed(api_key, "POST invitations with an API key and no session", problems)

    _use(client, "not-a-real-session")
    anonymous = client.post(_LOGOUT)
    _expect_allowed(anonymous, "POST logout with a session cookie that does not resolve", problems)

    _finish(problems)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.1-CSRF-ISSUE: login and GET /api/accounts/me do not issue a CSRF token, "
        "so the matching-token path cannot succeed"
    ),
)
def test_ac1_negative_issued_token_allows_cookie_mutation(accounts: TestClient) -> None:
    """An issued token allows invitations, an unknown path, and logout.

    Fails while login and GET /api/accounts/me issue no token. The allow path
    runs only after a token exists, so a handler that already succeeds without
    a token does not pass this test.
    """
    client = accounts
    email, session, login = _open_owner(client, "csrf-issue")
    _use(client, session)
    me = client.get(_ME)
    token, problems = _harvest(session, [login, me])
    _use(client, session)
    relogin = client.post(_LOGIN, json={"email": email, "password": _PASSWORD})
    if relogin.status_code == 200:
        rotated = _cookie_value(_named_set_cookie(relogin, SESSION_COOKIE))
        if rotated and _resolves(rotated):
            session = rotated
        _use(client, session)
        me_after = client.get(_ME)
        if me_after.status_code == 200:
            token, more = _harvest(session, [relogin, me_after])
            problems.extend(problem for problem in more if problem not in problems)
    assert token is not None and not problems, "; ".join(problems) or "no CSRF token"

    probe = f"/api/sec-csrf-{uuid.uuid4().hex}"
    invite_email = _email("csrf-allow-invite")
    before = _invite_count(invite_email)
    _use(client, session, csrf_cookie=token)
    invite = client.post(
        _INVITE,
        json={"email": invite_email, "role": "builder"},
        headers=_headers(token),
    )
    _expect_allowed(invite, "POST /api/accounts/invitations with the issued token", problems)
    if invite.status_code != 201:
        problems.append(
            f"POST /api/accounts/invitations with the issued token ({_brief(invite)})"
        )
    elif _invite_count(invite_email) != before + 1:
        problems.append("issued CSRF token returned 201 without writing the invitation")

    _use(client, session, csrf_cookie=token)
    probed = client.post(probe, headers=_headers(token))
    _expect_allowed(probed, "POST unknown path with the issued token", problems)
    if not _is_csrf_rejection(probed) and probed.status_code != 404:
        problems.append(f"POST unknown path with the issued token ({_brief(probed)})")

    _use(client, session, csrf_cookie=token)
    logout = client.post(_LOGOUT, headers=_headers(token))
    _expect_allowed(logout, "POST /api/accounts/logout with the issued token", problems)
    if logout.status_code != 204:
        problems.append(f"POST /api/accounts/logout with the issued token ({_brief(logout)})")
    elif _resolves(session):
        problems.append("logout with the issued token left the session resolvable")

    _finish(problems)
