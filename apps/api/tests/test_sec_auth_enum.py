"""SEC-AUTH-ENUM AC1. Login, reset, and MFA stay rate-limited and non-enumerable.

Handover §6.1 AC3 and §6.10: ``POST /api/accounts/login``,
``POST /api/accounts/request-password-reset``, ``POST /api/accounts/reset-password``,
``POST /api/accounts/totp/enroll``, ``POST /api/accounts/totp/verify``, and
``POST /api/accounts/oauth/complete-2fa`` each have their own per-IP bucket and,
where the body names an email, a per-account bucket. The account key is the
normalized email. Five attempts are served. The sixth returns 429 with a
``Retry-After`` delta-seconds value. A different IP paired with a different
email is not limited by that bucket.

This cap stays in force when ``settings.rate_limit_per_minute`` is 0. The
general mutating limiter is a different control.

Under the cap, a failed login, a password-reset request, and a failed MFA
login return the same status and body for an unknown email and a known email.
That includes a correct password on an unverified account, a correct password
with no TOTP code, and a correct password with a wrong TOTP code. The body
must not set the session cookie. A verified account with the right password
still opens a session on a fresh IP.

The three login responses that still differ are strict xfails prefixed
``SEC-6.1-ENUM``. Each sixth attempt that is not 429 with ``Retry-After`` is
a strict xfail prefixed ``SEC-6.1-RATELIMIT``. Checks that already hold stay
ordinary asserts.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.account_service import SESSION_COOKIE, enroll_totp, signup_user
from app.db import SessionLocal, init_db
from app.main import app
from app.settings import settings

_ALLOWED_ATTEMPTS = 5
_PASSWORD = "enum-pass-99"
_WRONG = "wrong-pass-99"
_TOTP = "000000"

_LOGIN = "/api/accounts/login"
_RESET = "/api/accounts/request-password-reset"
_RESET_CONFIRM = "/api/accounts/reset-password"
_MFA_ENROLL = "/api/accounts/totp/enroll"
_MFA_VERIFY = "/api/accounts/totp/verify"
_MFA_OAUTH = "/api/accounts/oauth/complete-2fa"

_IP_SEQ = iter(range(1, 10_000))


def _next_ip() -> str:
    number = next(_IP_SEQ)
    host = (number - 1) % 250 + 1
    third = 113 + (number - 1) // 250
    return f"203.0.{third}.{host}"


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:12]}@example.com"


def _preview(response) -> str:
    return response.content.decode("utf-8", errors="replace")[:180]


def _has_session(response) -> bool:
    if SESSION_COOKIE in response.cookies:
        return True
    return SESSION_COOKIE in (response.headers.get("set-cookie") or "")


def _post(client: TestClient, ip: str, path: str, payload: dict | None) -> object:
    headers = {"X-Forwarded-For": ip}
    if payload is None:
        return client.post(path, headers=headers)
    return client.post(path, json=payload, headers=headers)


def _login_body(email: str, password: str, totp: str | None = None) -> dict:
    body = {"email": email, "password": password}
    if totp is not None:
        body["totp_code"] = totp
    return body


def _add_user(*, verified: bool, mfa: bool) -> str:
    email = _email("mfa" if mfa else "known" if verified else "new")
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password=_PASSWORD, workspace_name="Enum check")
        if verified or mfa:
            user.email_verified = True
        if mfa:
            enroll_totp(db, user, actor_user_id=user.id)
            user.totp_enabled = True
        db.add(user)
        db.commit()
        return email
    finally:
        db.close()


def _retry_after_problem(response, label: str) -> str | None:
    if response.status_code != 429:
        return f"{label}: expected 429, got {response.status_code} {_preview(response)}"
    retry = (response.headers.get("retry-after") or "").strip()
    if not retry.isdigit() or int(retry) < 1:
        return f"{label}: Retry-After must be a positive integer, got {retry!r}"
    return None


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch):
    """Accounts mode, general limiter off, forwarded IPs honoured by client_ip."""
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    monkeypatch.setattr(settings, "trusted_proxy", True)
    monkeypatch.setattr(settings, "email_transport", "console")
    init_db()
    with TestClient(app) as client:
        yield client


def _pair_problems(
    client: TestClient,
    label: str,
    known_body: dict,
    unknown_body: dict,
    *,
    login_failure: bool,
    check_match: bool,
) -> list[str]:
    """Checks for one known/unknown pair. Match is optional when that case is pinned."""
    problems: list[str] = []
    ip = _next_ip()
    path = _LOGIN if login_failure else _RESET
    known = _post(client, ip, path, known_body)
    unknown_res = _post(client, ip, path, unknown_body)
    if known.status_code == 429 or unknown_res.status_code == 429:
        problems.append(f"{label}: limited before the sixth attempt")
    if check_match and (known.status_code, known.content) != (
        unknown_res.status_code,
        unknown_res.content,
    ):
        problems.append(
            f"{label}: known {known.status_code} {_preview(known)} "
            f"!= unknown {unknown_res.status_code} {_preview(unknown_res)}"
        )
    if _has_session(known) or _has_session(unknown_res):
        problems.append(f"{label}: failure set a session cookie")
    if login_failure and (known.status_code == 200 or unknown_res.status_code == 200):
        problems.append(f"{label}: a failed login returned 200")
    if not login_failure and not (200 <= known.status_code < 300):
        problems.append(f"{label}: reset was not accepted ({known.status_code})")
    return problems


def test_ac1_positive_same_response_for_unknown_and_known_email(auth_client: TestClient) -> None:
    """Wrong-password login and a reset request match. A verified login opens a session.

    Unverified login and both MFA login failures still must not set a session
    cookie or return 200. Their body match is pinned on the SEC-6.1-ENUM xfails.
    """
    verified = _add_user(verified=True, mfa=False)
    unverified = _add_user(verified=False, mfa=False)
    mfa_user = _add_user(verified=True, mfa=True)
    unknown = _email("missing")
    problems: list[str] = []

    success_ip = _next_ip()
    success = _post(auth_client, success_ip, _LOGIN, _login_body(verified, _PASSWORD))
    if success.status_code != 200 or not _has_session(success):
        problems.append(
            "verified login should open a session "
            f"(status {success.status_code}, session={_has_session(success)})"
        )

    matched: tuple[tuple[str, dict, dict, bool], ...] = (
        (
            "login wrong password",
            _login_body(verified, _WRONG),
            _login_body(unknown, _WRONG),
            True,
        ),
        (
            "password reset request",
            {"email": verified},
            {"email": _email("missing")},
            False,
        ),
    )
    held_open: tuple[tuple[str, dict, dict, bool], ...] = (
        (
            "login correct password before email is verified",
            _login_body(unverified, _PASSWORD),
            _login_body(_email("missing"), _PASSWORD),
            True,
        ),
        (
            "MFA login correct password without a code",
            _login_body(mfa_user, _PASSWORD),
            _login_body(_email("missing"), _PASSWORD),
            True,
        ),
        (
            "MFA login correct password with a wrong code",
            _login_body(mfa_user, _PASSWORD, _TOTP),
            _login_body(_email("missing"), _PASSWORD, _TOTP),
            True,
        ),
    )
    for label, known_body, unknown_body, login_failure in matched:
        problems.extend(
            _pair_problems(
                auth_client,
                label,
                known_body,
                unknown_body,
                login_failure=login_failure,
                check_match=True,
            )
        )
    for label, known_body, unknown_body, login_failure in held_open:
        problems.extend(
            _pair_problems(
                auth_client,
                label,
                known_body,
                unknown_body,
                login_failure=login_failure,
                check_match=False,
            )
        )

    assert not problems, "AC1 same response for unknown and known emails:\n" + "\n".join(problems)


def _assert_login_bodies_match(client: TestClient, known_body: dict, unknown_body: dict) -> None:
    ip = _next_ip()
    known = _post(client, ip, _LOGIN, known_body)
    unknown_res = _post(client, ip, _LOGIN, unknown_body)
    assert (known.status_code, known.content) == (unknown_res.status_code, unknown_res.content)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.1-ENUM: unverified login returns 403 email_unverified for a known "
        "email and 401 invalid_credentials for an unknown email"
    ),
)
def test_ac1_positive_unverified_login_matches_unknown_email(auth_client: TestClient) -> None:
    """A correct password before verification matches the unknown-email login response."""
    unverified = _add_user(verified=False, mfa=False)
    _assert_login_bodies_match(
        auth_client,
        _login_body(unverified, _PASSWORD),
        _login_body(_email("missing"), _PASSWORD),
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.1-ENUM: MFA login without a code returns totp_required for a known "
        "email and invalid_credentials for an unknown email"
    ),
)
def test_ac1_positive_mfa_without_code_matches_unknown_email(auth_client: TestClient) -> None:
    """A correct password with no TOTP code matches the unknown-email login response."""
    mfa_user = _add_user(verified=True, mfa=True)
    _assert_login_bodies_match(
        auth_client,
        _login_body(mfa_user, _PASSWORD),
        _login_body(_email("missing"), _PASSWORD),
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.1-ENUM: MFA login with a wrong code returns invalid_2fa for a known "
        "email and invalid_credentials for an unknown email"
    ),
)
def test_ac1_positive_mfa_wrong_code_matches_unknown_email(auth_client: TestClient) -> None:
    """A correct password with a wrong TOTP code matches the unknown-email login response."""
    mfa_user = _add_user(verified=True, mfa=True)
    _assert_login_bodies_match(
        auth_client,
        _login_body(mfa_user, _PASSWORD, _TOTP),
        _login_body(_email("missing"), _PASSWORD, _TOTP),
    )


def _burn(
    client: TestClient,
    *,
    label: str,
    path: str,
    payload_for_ip: Callable[[str], dict | None],
    ips: list[str],
) -> list[str]:
    """Return problems when one of the first five calls is already limited.

    The sixth call is issued so a later probe sees a full bucket. Its 429
    contract is pinned on the SEC-6.1-RATELIMIT xfails.
    """
    problems: list[str] = []
    allowed_ips = ips[:_ALLOWED_ATTEMPTS]
    blocked_ip = ips[_ALLOWED_ATTEMPTS]
    for index, ip in enumerate(allowed_ips, start=1):
        response = _post(client, ip, path, payload_for_ip(ip))
        if response.status_code == 429:
            problems.append(f"{label}: attempt {index} returned 429 {_preview(response)}")
    _post(client, blocked_ip, path, payload_for_ip(blocked_ip))
    return problems


def test_ac1_negative_sixth_attempt_is_429_and_does_not_spill(auth_client: TestClient) -> None:
    """Five attempts are served, and another IP and email is not limited.

    After the login bucket is full, a known email and an unknown email still
    share one body. The 429 responses are pinned on the SEC-6.1-RATELIMIT xfails.
    """
    problems: list[str] = []
    login_account = _add_user(verified=True, mfa=False)
    login_bucket = _add_user(verified=True, mfa=False)
    reset_account = _add_user(verified=True, mfa=False)
    mfa_account = _add_user(verified=True, mfa=True)

    def check_spill(label: str, path: str, payload: dict | None) -> None:
        spilled = _post(auth_client, _next_ip(), path, payload)
        if spilled.status_code == 429:
            problems.append(f"{label}: a different IP and email was limited")

    login_ip = _next_ip()
    problems.extend(
        _burn(
            auth_client,
            label="login per IP",
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(_email("miss"), _WRONG),
            ips=[login_ip] * (_ALLOWED_ATTEMPTS + 1),
        )
    )
    known_limited = _post(auth_client, login_ip, _LOGIN, _login_body(login_account, _WRONG))
    unknown_limited = _post(auth_client, login_ip, _LOGIN, _login_body(_email("miss"), _WRONG))
    if (known_limited.status_code, known_limited.content) != (
        unknown_limited.status_code,
        unknown_limited.content,
    ):
        problems.append(
            "login over the cap still distinguishes emails: "
            f"known {known_limited.status_code} {_preview(known_limited)} "
            f"!= unknown {unknown_limited.status_code} {_preview(unknown_limited)}"
        )
    check_spill("login per IP", _LOGIN, _login_body(_email("miss"), _WRONG))

    problems.extend(
        _burn(
            auth_client,
            label="login per account",
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(login_bucket, _WRONG),
            ips=[_next_ip() for _ in range(_ALLOWED_ATTEMPTS + 1)],
        )
    )
    check_spill("login per account", _LOGIN, _login_body(_email("miss"), _WRONG))

    mfa_ip = _next_ip()
    problems.extend(
        _burn(
            auth_client,
            label="MFA login per IP",
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(_email("miss"), _WRONG, _TOTP),
            ips=[mfa_ip] * (_ALLOWED_ATTEMPTS + 1),
        )
    )
    check_spill("MFA login per IP", _LOGIN, _login_body(_email("miss"), _WRONG, _TOTP))

    problems.extend(
        _burn(
            auth_client,
            label="MFA login per account",
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(mfa_account, _PASSWORD, _TOTP),
            ips=[_next_ip() for _ in range(_ALLOWED_ATTEMPTS + 1)],
        )
    )
    check_spill(
        "MFA login per account",
        _LOGIN,
        _login_body(_email("miss"), _PASSWORD, _TOTP),
    )

    reset_ip = _next_ip()
    problems.extend(
        _burn(
            auth_client,
            label="reset request per IP",
            path=_RESET,
            payload_for_ip=lambda _ip: {"email": _email("miss")},
            ips=[reset_ip] * (_ALLOWED_ATTEMPTS + 1),
        )
    )
    check_spill("reset request per IP", _RESET, {"email": _email("miss")})

    problems.extend(
        _burn(
            auth_client,
            label="reset request per account",
            path=_RESET,
            payload_for_ip=lambda _ip: {"email": reset_account},
            ips=[_next_ip() for _ in range(_ALLOWED_ATTEMPTS + 1)],
        )
    )
    check_spill("reset request per account", _RESET, {"email": _email("miss")})

    confirm_body = {"token": "not-a-reset-token", "password": _PASSWORD}
    confirm_ip = _next_ip()
    problems.extend(
        _burn(
            auth_client,
            label="reset confirm per IP",
            path=_RESET_CONFIRM,
            payload_for_ip=lambda _ip: confirm_body,
            ips=[confirm_ip] * (_ALLOWED_ATTEMPTS + 1),
        )
    )
    check_spill("reset confirm per IP", _RESET_CONFIRM, confirm_body)

    for label, path, payload in (
        ("MFA enroll per IP", _MFA_ENROLL, None),
        ("MFA verify per IP", _MFA_VERIFY, {"code": _TOTP}),
        ("MFA complete per IP", _MFA_OAUTH, {"token": "not-a-token", "totp_code": _TOTP}),
    ):
        ip = _next_ip()
        problems.extend(
            _burn(
                auth_client,
                label=label,
                path=path,
                payload_for_ip=lambda _ip, body=payload: body,
                ips=[ip] * (_ALLOWED_ATTEMPTS + 1),
            )
        )
        check_spill(label, path, payload)

    assert not problems, "AC1 rate limit:\n" + "\n".join(problems)


def _last_of_six(
    client: TestClient,
    *,
    path: str,
    payload_for_ip: Callable[[str], dict | None],
    shared_ip: bool,
) -> object:
    """Six calls. The last one is the attempt that should be 429."""
    if shared_ip:
        ip = _next_ip()
        ips = [ip] * (_ALLOWED_ATTEMPTS + 1)
    else:
        ips = [_next_ip() for _ in range(_ALLOWED_ATTEMPTS + 1)]
    response: object = None
    for ip in ips:
        response = _post(client, ip, path, payload_for_ip(ip))
    return response


def _open_sixth(client: TestClient, case_id: str) -> object:
    """Reproduce one open sixth-attempt probe from the rate-limit oracle."""
    if case_id == "login-per-ip":
        return _last_of_six(
            client,
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(_email("miss"), _WRONG),
            shared_ip=True,
        )
    if case_id == "login-per-ip-known":
        account = _add_user(verified=True, mfa=False)
        ip = _next_ip()
        for _ in range(_ALLOWED_ATTEMPTS + 1):
            _post(client, ip, _LOGIN, _login_body(_email("miss"), _WRONG))
        return _post(client, ip, _LOGIN, _login_body(account, _WRONG))
    if case_id == "login-per-ip-unknown":
        account = _add_user(verified=True, mfa=False)
        ip = _next_ip()
        for _ in range(_ALLOWED_ATTEMPTS + 1):
            _post(client, ip, _LOGIN, _login_body(_email("miss"), _WRONG))
        _post(client, ip, _LOGIN, _login_body(account, _WRONG))
        return _post(client, ip, _LOGIN, _login_body(_email("miss"), _WRONG))
    if case_id == "login-per-account":
        account = _add_user(verified=True, mfa=False)
        return _last_of_six(
            client,
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(account, _WRONG),
            shared_ip=False,
        )
    if case_id == "mfa-login-per-ip":
        return _last_of_six(
            client,
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(_email("miss"), _WRONG, _TOTP),
            shared_ip=True,
        )
    if case_id == "mfa-login-per-account":
        account = _add_user(verified=True, mfa=True)
        return _last_of_six(
            client,
            path=_LOGIN,
            payload_for_ip=lambda _ip: _login_body(account, _PASSWORD, _TOTP),
            shared_ip=False,
        )
    if case_id == "reset-request-per-ip":
        return _last_of_six(
            client,
            path=_RESET,
            payload_for_ip=lambda _ip: {"email": _email("miss")},
            shared_ip=True,
        )
    if case_id == "reset-request-per-account":
        account = _add_user(verified=True, mfa=False)
        return _last_of_six(
            client,
            path=_RESET,
            payload_for_ip=lambda _ip: {"email": account},
            shared_ip=False,
        )
    if case_id == "reset-confirm-per-ip":
        body = {"token": "not-a-reset-token", "password": _PASSWORD}
        return _last_of_six(
            client,
            path=_RESET_CONFIRM,
            payload_for_ip=lambda _ip: body,
            shared_ip=True,
        )
    if case_id == "mfa-enroll-per-ip":
        return _last_of_six(
            client,
            path=_MFA_ENROLL,
            payload_for_ip=lambda _ip: None,
            shared_ip=True,
        )
    if case_id == "mfa-verify-per-ip":
        return _last_of_six(
            client,
            path=_MFA_VERIFY,
            payload_for_ip=lambda _ip: {"code": _TOTP},
            shared_ip=True,
        )
    if case_id == "mfa-complete-per-ip":
        body = {"token": "not-a-token", "totp_code": _TOTP}
        return _last_of_six(
            client,
            path=_MFA_OAUTH,
            payload_for_ip=lambda _ip: body,
            shared_ip=True,
        )
    raise AssertionError(f"unknown rate-limit case {case_id}")


_OPEN_SIXTH: tuple[tuple[str, str], ...] = (
    (
        "login-per-ip",
        "SEC-6.1-RATELIMIT: login per IP sixth attempt returns 401 "
        "invalid_credentials, not 429 with Retry-After",
    ),
    (
        "login-per-ip-known",
        "SEC-6.1-RATELIMIT: login per IP known email after the cap returns 401 "
        "invalid_credentials, not 429 with Retry-After",
    ),
    (
        "login-per-ip-unknown",
        "SEC-6.1-RATELIMIT: login per IP unknown email after the cap returns 401 "
        "invalid_credentials, not 429 with Retry-After",
    ),
    (
        "login-per-account",
        "SEC-6.1-RATELIMIT: login per account sixth attempt returns 401 "
        "invalid_credentials, not 429 with Retry-After",
    ),
    (
        "mfa-login-per-ip",
        "SEC-6.1-RATELIMIT: MFA login per IP sixth attempt returns 401 "
        "invalid_credentials, not 429 with Retry-After",
    ),
    (
        "mfa-login-per-account",
        "SEC-6.1-RATELIMIT: MFA login per account sixth attempt returns 401 "
        "invalid_2fa, not 429 with Retry-After",
    ),
    (
        "reset-request-per-ip",
        "SEC-6.1-RATELIMIT: reset request per IP sixth attempt returns 204, "
        "not 429 with Retry-After",
    ),
    (
        "reset-request-per-account",
        "SEC-6.1-RATELIMIT: reset request per account sixth attempt returns 204, "
        "not 429 with Retry-After",
    ),
    (
        "reset-confirm-per-ip",
        "SEC-6.1-RATELIMIT: reset confirm per IP sixth attempt returns 400 "
        "invalid_token, not 429 with Retry-After",
    ),
    (
        "mfa-enroll-per-ip",
        "SEC-6.1-RATELIMIT: MFA enroll per IP sixth attempt returns 401 "
        "unauthorized, not 429 with Retry-After",
    ),
    (
        "mfa-verify-per-ip",
        "SEC-6.1-RATELIMIT: MFA verify per IP sixth attempt returns 401 "
        "unauthorized, not 429 with Retry-After",
    ),
    (
        "mfa-complete-per-ip",
        "SEC-6.1-RATELIMIT: MFA complete per IP sixth attempt returns 400 "
        "invalid_oauth_state, not 429 with Retry-After",
    ),
)


def _xfail_sixth(case_id: str, reason: str):
    return pytest.param(
        case_id,
        id=case_id,
        marks=pytest.mark.xfail(strict=True, reason=reason),
    )


@pytest.mark.parametrize(
    "case_id",
    [_xfail_sixth(case_id, reason) for case_id, reason in _OPEN_SIXTH],
)
def test_ac1_negative_open_sixth_attempt_is_429(auth_client: TestClient, case_id: str) -> None:
    """This sixth auth attempt returns 429 with a positive Retry-After."""
    problem = _retry_after_problem(_open_sixth(auth_client, case_id), case_id)
    assert problem is None, problem
