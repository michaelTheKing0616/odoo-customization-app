"""OAuth token refresh for Bridge connectors (spec Bridge 3).

The vault keeps the refresh token (encrypted, live_probe store). ``access_token_for`` returns a
working access token: the stored one while it has more than two minutes left, otherwise a new one
from the provider's token endpoint. Rotated refresh tokens are saved straight away. Tokens never
appear in logs, traces or errors.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from app.bridge import live_probe as lp
from app.code_runner import store
from app.crypto import encrypt_secret

TOKEN_URLS = {
    "quickbooks": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
    "xero": "https://identity.xero.com/connect/token",
    "hubspot": "https://api.hubapi.com/oauth/v1/token",
    "salesforce": "https://login.salesforce.com/services/oauth2/token",
    "teams": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "google_sheets": "https://oauth2.googleapis.com/token",
}
EARLY_S = 120


class SignInAgain(Exception):
    """The provider refused the refresh token: a person has to sign in to the app again."""


def _save(ws: str | None, key: str, values: dict[str, str]) -> None:
    with store.lock():
        data = store.load("vault", lp._vkey(ws), {})
        slot = data.setdefault(key, {})
        for k, v in values.items():
            slot[k] = {"v": encrypt_secret(str(v)), "by": "token refresh", "at": time.time()}
        store.save("vault", lp._vkey(ws), data)


def access_token_for(ws: str | None, key: str, *, post: Callable[..., httpx.Response] = httpx.post,
                     now: float | None = None, force: bool = False) -> dict[str, Any]:
    now = now or time.time()
    url = TOKEN_URLS.get(key)
    if not url:
        raise ValueError(f"{key} doesn't use sign-in tokens that expire.")
    sec = lp._secrets(ws, key)
    exp = float(sec.get("expires_at") or 0)
    if not force and sec.get("access_token") and exp - now > EARLY_S:
        return {"access_token": sec["access_token"], "expires_in_s": int(exp - now), "refreshed": False}
    if not sec.get("refresh_token"):
        raise SignInAgain("Sign in to the app again: Ingenium has no refresh token for it.")
    form = {"grant_type": "refresh_token", "refresh_token": sec["refresh_token"]}
    if sec.get("client_id"):
        form["client_id"] = sec["client_id"]
    if sec.get("client_secret"):
        form["client_secret"] = sec["client_secret"]
    try:
        r = post(url, data=form, headers={"Accept": "application/json"}, timeout=15)
    except httpx.HTTPError as exc:
        raise ConnectionError(f"Couldn't reach the app's sign-in service ({exc.__class__.__name__}). Ingenium will try again.") from exc
    if r.status_code in (400, 401):
        raise SignInAgain("The app refused the saved sign-in (it may have been revoked or expired). Sign in again.")
    if r.status_code >= 400:
        raise ConnectionError(f"The app's sign-in service answered {r.status_code}. Ingenium will try again.")
    body = r.json()
    token = body.get("access_token")
    if not token:
        raise ConnectionError("The app's sign-in service answered without a token. Ingenium will try again.")
    new = {"access_token": token, "expires_at": str(now + float(body.get("expires_in") or 3600))}
    if body.get("refresh_token") and body["refresh_token"] != sec["refresh_token"]:
        new["refresh_token"] = body["refresh_token"]  # rotated: the old one stops working
    _save(ws, key, new)
    return {"access_token": token, "expires_in_s": int(float(new["expires_at"]) - now), "refreshed": True,
            "rotated": "refresh_token" in new}
