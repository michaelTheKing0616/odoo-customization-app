"""Thin HTTP client for self-hosted / hosted Attendee bot API."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class AttendeeError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def attendee_configured() -> bool:
    return bool(settings.attendee_api_key and settings.attendee_api_base)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Token {settings.attendee_api_key}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> httpx.Response:
    if not attendee_configured():
        raise AttendeeError("Attendee is not configured (set ATTENDEE_API_BASE and ATTENDEE_API_KEY)", status_code=503)
    url = settings.attendee_api_base.rstrip("/") + path
    try:
        with httpx.Client(timeout=30.0) as client:
            return client.request(method, url, headers=_headers(), json=json_body)
    except httpx.HTTPError as exc:
        raise AttendeeError(f"Attendee unreachable: {exc}") from exc


def create_bot(*, meeting_url: str, bot_name: str) -> dict[str, Any]:
    res = _request("POST", "/api/v1/bots", json_body={"meeting_url": meeting_url, "bot_name": bot_name})
    if res.status_code >= 400:
        raise AttendeeError(f"Attendee create bot failed: {res.status_code} {res.text[:400]}", status_code=502)
    return res.json()


def get_bot(bot_id: str) -> dict[str, Any]:
    res = _request("GET", f"/api/v1/bots/{bot_id}")
    if res.status_code >= 400:
        raise AttendeeError(f"Attendee get bot failed: {res.status_code} {res.text[:400]}", status_code=502)
    return res.json()


def leave_bot(bot_id: str) -> dict[str, Any]:
    res = _request("POST", f"/api/v1/bots/{bot_id}/leave")
    if res.status_code >= 400:
        raise AttendeeError(f"Attendee leave failed: {res.status_code} {res.text[:400]}", status_code=502)
    if res.content:
        try:
            return res.json()
        except Exception:  # noqa: BLE001
            return {"ok": True}
    return {"ok": True}


def delete_bot_data(bot_id: str) -> dict[str, Any]:
    """Retention minimization — Attendee POST /bots/{id}/delete_data."""
    res = _request("POST", f"/api/v1/bots/{bot_id}/delete_data")
    if res.status_code >= 400:
        raise AttendeeError(f"Attendee delete_data failed: {res.status_code} {res.text[:400]}", status_code=502)
    if res.content:
        try:
            return res.json()
        except Exception:  # noqa: BLE001
            return {"ok": True}
    return {"ok": True}


def leave_and_purge_with_retries(
    bot_id: str,
    *,
    purge: bool,
    attempts: int = 3,
    backoff_s: float = 1.5,
) -> dict[str, Any]:
    """Best-effort leave + optional delete_data with bounded retries."""
    out: dict[str, Any] = {"bot_id": bot_id, "leave_ok": False, "purge_ok": None, "errors": []}
    last_exc: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            leave_bot(bot_id)
            out["leave_ok"] = True
            last_exc = None
            break
        except AttendeeError as exc:
            last_exc = exc
            out["errors"].append(f"leave[{i}]: {exc}")
            time.sleep(backoff_s * (i + 1))
    if not out["leave_ok"] and last_exc is not None:
        logger.warning("Attendee leave ultimately failed for %s: %s", bot_id, last_exc)

    if purge:
        out["purge_ok"] = False
        for i in range(max(1, attempts)):
            try:
                delete_bot_data(bot_id)
                out["purge_ok"] = True
                break
            except AttendeeError as exc:
                out["errors"].append(f"purge[{i}]: {exc}")
                time.sleep(backoff_s * (i + 1))
    return out
