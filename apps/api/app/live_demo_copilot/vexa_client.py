"""Thin HTTP client for a self-hosted Vexa meeting bot (Apache-2.0, github.com/Vexa-ai/vexa).

Chosen over Attendee (Elastic License 2.0 in its LICENSE: no offering it to third parties as a
hosted or managed service, which is what Ingenium does) and MeetingBaaS (github.com/Meeting-BaaS/
meeting-bot-as-a-service has no LICENSE file, so no open-source grant; it is example apps for their
paid hosted API, not a self-hostable bot). Licences checked against each repo on 2026-10-20. See PROGRESS.md Q7 spec.

Bot ids are stored as ``vexa:<platform>:<native_meeting_id>`` so every call can be addressed.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)

# Vexa meeting status -> the Co-Pilot's normalised bot states (bot_status.normalize_raw_state)
STATE_MAP = {
    "requested": "joining",
    "joining": "joining",
    "awaiting_admission": "waiting_room",
    "active": "joined_recording",
    "stopping": "leaving",
    "completed": "ended",
    "failed": "fatal_error",
}


class VexaError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def vexa_configured() -> bool:
    return bool(settings.vexa_api_key and settings.vexa_api_base)


def _request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> httpx.Response:
    if not vexa_configured():
        raise VexaError("The meeting bot is not set up (set VEXA_API_BASE and VEXA_API_KEY)", status_code=503)
    url = settings.vexa_api_base.rstrip("/") + path
    try:
        with httpx.Client(timeout=30.0) as client:
            return client.request(method, url, headers={"X-API-Key": settings.vexa_api_key}, json=json_body)
    except httpx.HTTPError as exc:
        raise VexaError(f"The meeting bot server is unreachable: {exc}") from exc


def split_id(bot_id: str) -> tuple[str, str]:
    parts = bot_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "vexa":
        raise VexaError(f"Not a Vexa bot id: {bot_id}", status_code=400)
    return parts[1], parts[2]


def create_bot(*, meeting_url: str, bot_name: str) -> dict[str, Any]:
    res = _request(
        "POST",
        "/bots",
        json_body={
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "recording_enabled": False,  # transcript only; no audio kept
            "automatic_leave": {"max_time_left_alone": 300000},
        },
    )
    if res.status_code >= 400:
        raise VexaError(f"The bot could not be sent: {res.status_code} {res.text[:400]}")
    body = res.json()
    platform = body.get("platform")
    native = body.get("native_meeting_id")
    if not platform or not native:
        raise VexaError(f"Bot server reply had no meeting id: {str(body)[:300]}")
    return {"id": f"vexa:{platform}:{native}", "state": STATE_MAP.get(str(body.get("status") or "requested"), "joining")}


def get_bot(bot_id: str) -> dict[str, Any]:
    platform, native = split_id(bot_id)
    res = _request("GET", "/bots/status")
    if res.status_code >= 400:
        raise VexaError(f"Bot status failed: {res.status_code} {res.text[:400]}")
    body = res.json()
    rows = body.get("running") or body.get("running_bots") or []
    for row in rows:
        if row.get("platform") == platform and str(row.get("native_meeting_id")) == native:
            return {"id": bot_id, "state": STATE_MAP.get(str(row.get("status") or "active"), "joined_recording")}
    return {"id": bot_id, "state": "ended"}


def leave_bot(bot_id: str) -> dict[str, Any]:
    platform, native = split_id(bot_id)
    res = _request("DELETE", f"/bots/{platform}/{native}")
    if res.status_code >= 400 and res.status_code != 404:
        raise VexaError(f"Bot leave failed: {res.status_code} {res.text[:400]}")
    return {"ok": True}


def delete_bot_data(bot_id: str) -> dict[str, Any]:
    """Retention minimisation: erase the meeting's transcript on the bot server."""
    platform, native = split_id(bot_id)
    res = _request("DELETE", f"/meetings/{platform}/{native}")
    if res.status_code >= 400 and res.status_code != 404:
        raise VexaError(f"Bot data delete failed: {res.status_code} {res.text[:400]}")
    return {"ok": True}


def transcript_segments(bot_id: str) -> list[dict[str, Any]]:
    """Completed, speaker-attributed segments so far (drafts are skipped)."""
    platform, native = split_id(bot_id)
    res = _request("GET", f"/transcripts/{platform}/{native}")
    if res.status_code >= 400:
        raise VexaError(f"Transcript read failed: {res.status_code} {res.text[:400]}")
    return [s for s in (res.json().get("segments") or []) if s.get("completed", True) and (s.get("text") or "").strip()]


def leave_and_purge_with_retries(bot_id: str, *, purge: bool, attempts: int = 3, backoff_s: float = 1.5) -> dict[str, Any]:
    out: dict[str, Any] = {"bot_id": bot_id, "leave_ok": False, "purge_ok": None, "errors": []}
    for i in range(max(1, attempts)):
        try:
            leave_bot(bot_id)
            out["leave_ok"] = True
            break
        except VexaError as exc:
            out["errors"].append(f"leave[{i}]: {exc}")
            time.sleep(backoff_s * (i + 1))
    if purge:
        out["purge_ok"] = False
        for i in range(max(1, attempts)):
            try:
                delete_bot_data(bot_id)
                out["purge_ok"] = True
                break
            except VexaError as exc:
                out["errors"].append(f"purge[{i}]: {exc}")
                time.sleep(backoff_s * (i + 1))
    return out
