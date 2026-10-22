"""Q7: Vexa is the default meeting bot; ids address platform+meeting; states map; drafts skipped."""

from __future__ import annotations

import httpx
import pytest

from app.live_demo_copilot import bot_backend as bb
from app.live_demo_copilot import vexa_client as vx
from app.settings import settings

pytestmark = pytest.mark.no_app_db


@pytest.fixture
def vexa(monkeypatch):
    monkeypatch.setattr(settings, "meeting_bot_provider", "vexa")
    monkeypatch.setattr(settings, "vexa_api_base", "http://vexa.test")
    monkeypatch.setattr(settings, "vexa_api_key", "k")
    calls: list[tuple[str, str, dict | None]] = []
    replies: dict[tuple[str, str], tuple[int, dict]] = {}

    def fake(method, path, *, json_body=None):
        calls.append((method, path, json_body))
        code, body = replies.get((method, path), (200, {}))
        return httpx.Response(code, json=body, request=httpx.Request(method, "http://vexa.test" + path))

    monkeypatch.setattr(vx, "_request", fake)
    return calls, replies


def test_create_status_transcript_leave(vexa):
    calls, replies = vexa
    replies[("POST", "/bots")] = (201, {"platform": "google_meet", "native_meeting_id": "abc-defg-hij", "status": "requested"})
    bot = bb.create_bot(meeting_url="https://meet.google.com/abc-defg-hij", bot_name="Ingenium notes")
    assert bot == {"id": "vexa:google_meet:abc-defg-hij", "state": "joining"}
    assert calls[0][2]["recording_enabled"] is False  # transcript only, no audio kept
    replies[("GET", "/bots/status")] = (200, {"running": [{"platform": "google_meet", "native_meeting_id": "abc-defg-hij", "status": "awaiting_admission"}]})
    assert bb.get_bot(bot["id"])["state"] == "waiting_room"
    replies[("GET", "/transcripts/google_meet/abc-defg-hij")] = (200, {"segments": [
        {"speaker": "Ada (client)", "text": "Can Odoo track deposits?", "start": 3.2, "completed": True},
        {"speaker": "Ada (client)", "text": "draft...", "start": 5.0, "completed": False},
    ]})
    segs = bb.pull_segments(bot["id"])
    assert [s["text"] for s in segs] == ["Can Odoo track deposits?"]
    out = bb.leave_and_purge_with_retries(bot["id"], purge=True, attempts=1, backoff_s=0)
    assert out["leave_ok"] and out["purge_ok"]
    assert ("DELETE", "/bots/google_meet/abc-defg-hij", None) in calls
    assert ("DELETE", "/meetings/google_meet/abc-defg-hij", None) in calls


def test_not_configured_and_errors(monkeypatch):
    monkeypatch.setattr(settings, "meeting_bot_provider", "vexa")
    monkeypatch.setattr(settings, "vexa_api_key", "")
    assert bb.bot_configured() is False
    with pytest.raises(bb.BotError) as e:
        bb.create_bot(meeting_url="https://zoom.us/j/1", bot_name="x")
    assert e.value.status_code == 503
    assert bb.pull_segments("attendee-bot-1") == []  # Attendee pushes by webhook
    assert bb.capabilities()["meeting_chat"] is False
