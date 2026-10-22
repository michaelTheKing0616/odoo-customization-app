"""One door for the meeting bot. Vexa (Apache-2.0, self-hosted) is the default; the older
Attendee client stays only for existing self-hosted internal setups (MEETING_BOT_PROVIDER=attendee)."""
from __future__ import annotations

from typing import Any

from app.live_demo_copilot import attendee_client as att
from app.live_demo_copilot import vexa_client as vx
from app.settings import settings


class BotError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def provider() -> str:
    return "attendee" if (settings.meeting_bot_provider or "vexa").lower() == "attendee" else "vexa"


def _wrap(fn, *a: Any, **k: Any) -> Any:
    try:
        return fn(*a, **k)
    except (vx.VexaError, att.AttendeeError) as exc:
        raise BotError(str(exc), status_code=getattr(exc, "status_code", 502)) from exc


def bot_configured() -> bool:
    return vx.vexa_configured() if provider() == "vexa" else att.attendee_configured()


def _mod(bot_id: str | None = None):
    if bot_id is not None:
        return vx if bot_id.startswith("vexa:") else att
    return vx if provider() == "vexa" else att


def create_bot(*, meeting_url: str, bot_name: str) -> dict[str, Any]:
    return _wrap(_mod().create_bot, meeting_url=meeting_url, bot_name=bot_name)


def get_bot(bot_id: str) -> dict[str, Any]:
    return _wrap(_mod(bot_id).get_bot, bot_id)


def leave_and_purge_with_retries(bot_id: str, *, purge: bool, **kw: Any) -> dict[str, Any]:
    return _mod(bot_id).leave_and_purge_with_retries(bot_id, purge=purge, **kw)


def pull_segments(bot_id: str) -> list[dict[str, Any]]:
    """Vexa is polled for transcript segments; Attendee pushes them by webhook (returns [])."""
    if not bot_id.startswith("vexa:"):
        return []
    return _wrap(vx.transcript_segments, bot_id)


def capabilities() -> dict[str, bool]:
    """What the chosen bot can do today. Checked Oct 20, 2026 against docs.vexa.ai (interactive-bots, roadmap/status):
    Vexa 0.12 serves chat READ only; POST .../chat and POST .../speak are contract-sealed but return 404
    (speak also ignores voice_agent_enabled). Flip these when Vexa wires them."""
    if provider() == "vexa":
        return {"private_whisper": True, "meeting_chat": False, "speak_aloud": False}
    return {"private_whisper": True, "meeting_chat": False, "speak_aloud": False}
