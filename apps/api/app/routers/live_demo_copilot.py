"""Live Demo Co-Pilot — consent-gated Attendee capture (durable, workspace-scoped)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.live_demo_copilot import DISCLOSURE_VERSION
from app.live_demo_copilot.attendee_client import (
    AttendeeError,
    attendee_configured,
    create_bot,
    get_bot,
)
from app.live_demo_copilot.bot_status import bot_status_view, normalize_raw_state
from app.live_demo_copilot.leave_purge import enqueue_leave_purge
from app.live_demo_copilot.events import EVENT_BUS
from app.live_demo_copilot import service as ldc
from app.live_demo_copilot.pipeline import list_answers, process_transcript_line
from app.live_demo_copilot.stage1_filter import stage1_filter
from app.live_demo_copilot.webhook_crypto import verify_signature
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-demo-copilot", tags=["live-demo-copilot"])
webhook_router = APIRouter(prefix="/live-demo-copilot", tags=["live-demo-copilot-webhooks"])


class SessionCreateBody(BaseModel):
    meeting_url: str = Field(min_length=8, max_length=2000)
    bot_name: str = Field(default="Odoo Demo Co-Pilot", max_length=120)
    connection_id: str | None = None
    presenter_speakers: list[str] = Field(default_factory=list)


class PresenterSpeakersBody(BaseModel):
    presenter_speakers: list[str] = Field(default_factory=list)


class ConsentBody(BaseModel):
    disclosure_accepted: bool
    attendees_notified: bool
    retention_opt_in: bool = False
    disclosure_version: str = DISCLOSURE_VERSION


class BotStatusOut(BaseModel):
    raw: str
    phase: str
    label: str
    hint: str
    severity: str
    needs_host_action: bool = False
    is_terminal: bool = False


class SessionOut(BaseModel):
    id: str
    workspace_id: str | None
    connection_id: str | None
    meeting_url: str
    bot_name: str
    disclosure_accepted: bool
    disclosure_version: str
    attendees_notified: bool
    retention_opt_in: bool
    declined: bool
    attendee_bot_id: str | None
    bot_state: str
    bot_status: BotStatusOut
    mock_mode: bool
    attendee_configured: bool
    disclosure_required_version: str = DISCLOSURE_VERSION
    transcript_count: int
    meeting_url_hash: str
    leave_purge_status: str = "idle"
    last_ops_error: str | None = None
    leave_purge_job_id: str | None = None
    presenter_speakers: list[str] = Field(default_factory=list)


def _session_out(db: Session, s) -> SessionOut:
    count = len(ldc.list_transcript(db, s.id))
    view = bot_status_view(s.bot_state)
    return SessionOut(
        id=s.id,
        workspace_id=s.workspace_id,
        connection_id=s.connection_id,
        meeting_url=s.meeting_url,
        bot_name=s.bot_name,
        disclosure_accepted=s.disclosure_accepted,
        disclosure_version=s.disclosure_version,
        attendees_notified=s.attendees_notified,
        retention_opt_in=s.retention_opt_in,
        declined=s.declined,
        attendee_bot_id=s.attendee_bot_id,
        bot_state=s.bot_state,
        bot_status=BotStatusOut(
            raw=view.raw,
            phase=view.phase,
            label=view.label,
            hint=view.hint,
            severity=view.severity,
            needs_host_action=view.needs_host_action,
            is_terminal=view.is_terminal,
        ),
        mock_mode=s.mock_mode,
        attendee_configured=attendee_configured(),
        transcript_count=count,
        meeting_url_hash=s.meeting_url_hash,
        leave_purge_status=getattr(s, "leave_purge_status", None) or "idle",
        last_ops_error=getattr(s, "last_ops_error", None),
        leave_purge_job_id=getattr(s, "leave_purge_job_id", None),
        presenter_speakers=ldc.presenter_speakers_list(s),
    )


def _require_session(db: Session, session_id: str):
    try:
        return ldc.get_session_for_request(db, session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/disclosure")
def get_disclosure() -> dict[str, Any]:
    return {
        "version": DISCLOSURE_VERSION,
        "title": "Live meeting assistance disclosure",
        "summary": (
            "This session can join your meeting with a visible bot that listens to "
            "audio so we can detect Odoo-related questions and show private answers "
            "only to you (the presenter)."
        ),
        "bullets": [
            "A named meeting bot will appear in Zoom, Google Meet, or Microsoft Teams.",
            "All participants must be told the meeting content is being processed for live assistance.",
            "Answers are private to the presenter — never posted to meeting chat.",
            "By default we do not retain transcripts or audio after the session ends.",
            "WhatsApp calls are not supported and will never be.",
        ],
        "opt_out": "Decline stops the session. No bot joins and no audio is processed.",
        "retention_default": "do_not_retain",
    }


@router.post("/sessions", response_model=SessionOut)
def create_session(body: SessionCreateBody, db: Session = Depends(get_db)) -> SessionOut:
    url = body.meeting_url.strip()
    if "whatsapp" in url.lower():
        raise HTTPException(
            status_code=422,
            detail="WhatsApp is permanently out of scope — use Zoom, Google Meet, or Microsoft Teams.",
        )
    try:
        session = ldc.create_session(
            db,
            meeting_url=url,
            bot_name=body.bot_name,
            connection_id=body.connection_id,
            presenter_speakers=body.presenter_speakers,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _session_out(db, session)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    return _session_out(db, _require_session(db, session_id))


@router.patch("/sessions/{session_id}/presenter-speakers", response_model=SessionOut)
def patch_presenter_speakers(
    session_id: str, body: PresenterSpeakersBody, db: Session = Depends(get_db)
) -> SessionOut:
    """Set meeting display names for presenters whose questions should be ignored."""
    session = _require_session(db, session_id)
    session = ldc.update_presenter_speakers(db, session, body.presenter_speakers)
    return _session_out(db, session)


@router.post("/sessions/{session_id}/consent", response_model=SessionOut)
def record_consent(
    session_id: str, body: ConsentBody, db: Session = Depends(get_db)
) -> SessionOut:
    session = _require_session(db, session_id)
    if session.declined and session.bot_state == "declined":
        # Allow re-read; new accept after decline requires new session for audit clarity
        raise HTTPException(status_code=409, detail="Session was declined; create a new session")
    if body.disclosure_version != DISCLOSURE_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Stale disclosure version; required {DISCLOSURE_VERSION}",
        )
    accepted = bool(body.disclosure_accepted and body.attendees_notified)
    session = ldc.record_consent(
        db,
        session,
        accepted=accepted,
        attendees_notified=body.attendees_notified,
        retention_opt_in=body.retention_opt_in,
        disclosure_version=body.disclosure_version,
    )
    return _session_out(db, session)


@router.post("/sessions/{session_id}/launch", response_model=SessionOut)
def launch_bot(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    session = _require_session(db, session_id)
    if session.declined:
        raise HTTPException(status_code=403, detail="Session declined — processing blocked")
    if not session.disclosure_accepted or not session.attendees_notified:
        raise HTTPException(
            status_code=403,
            detail="Consent gate: accept disclosure and confirm attendees were notified before launch",
        )
    if session.disclosure_version != DISCLOSURE_VERSION:
        raise HTTPException(status_code=403, detail="Consent gate: re-accept current disclosure version")
    if session.attendee_bot_id:
        raise HTTPException(status_code=409, detail="Bot already launched for this session")

    if not attendee_configured():
        if not ldc.mock_allowed():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Attendee not configured. Set ATTENDEE_API_BASE + ATTENDEE_API_KEY. "
                    "Mock launch is disabled in production (APP_ENVIRONMENT=production)."
                ),
            )
        session = ldc.bind_bot(
            db,
            session,
            f"mock_bot_{session.id}",
            mock=True,
            state="joined_recording",
        )
        return _session_out(db, session)

    try:
        bot = create_bot(meeting_url=session.meeting_url, bot_name=session.bot_name)
    except AttendeeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    bot_id = str(bot.get("id") or bot.get("bot_id") or "")
    if not bot_id:
        raise HTTPException(status_code=502, detail=f"Attendee response missing bot id: {bot}")
    session = ldc.bind_bot(
        db,
        session,
        bot_id,
        mock=False,
        state=normalize_raw_state(str(bot.get("state") or "joining")),
    )
    return _session_out(db, session)


@router.post("/sessions/{session_id}/leave", response_model=SessionOut)
def leave_session(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    session = _require_session(db, session_id)
    purge = not session.retention_opt_in
    # Mark ended immediately for presenter UX; Attendee teardown retries in background.
    session = ldc.mark_ended(db, session)
    enqueue_leave_purge(db, session, purge=purge)
    db.refresh(session)
    return _session_out(db, session)


@router.post("/sessions/{session_id}/refresh-status", response_model=SessionOut)
def refresh_status(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    """Poll Attendee for current bot state (waiting room / fatal error / recording)."""
    session = _require_session(db, session_id)
    if not session.attendee_bot_id:
        raise HTTPException(status_code=409, detail="No bot launched for this session")
    if session.mock_mode:
        return _session_out(db, session)
    try:
        bot = get_bot(session.attendee_bot_id)
    except AttendeeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    state = str(bot.get("state") or session.bot_state)
    session = ldc.set_bot_state(db, session, state)
    return _session_out(db, session)


@router.post("/sessions/{session_id}/retry-leave-purge", response_model=SessionOut)
def retry_leave_purge(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    session = _require_session(db, session_id)
    if session.bot_state not in {"ended", "data_deleted", "leaving", "post_processing", "fatal_error"}:
        # Still allow retry if previous purge failed after end
        if session.leave_purge_status != "failed":
            raise HTTPException(status_code=409, detail="Session is not in a leave/purge retry state")
    purge = not session.retention_opt_in
    enqueue_leave_purge(db, session, purge=purge)
    db.refresh(session)
    return _session_out(db, session)


@router.get("/sessions/{session_id}/transcript")
def get_transcript(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    session = _require_session(db, session_id)
    lines = ldc.list_transcript(db, session.id)
    return {
        "session_id": session.id,
        "lines": [
            {
                "speaker_name": t.speaker_name,
                "speaker_uuid": t.speaker_uuid,
                "text": t.text,
                "timestamp_ms": t.timestamp_ms,
            }
            for t in lines
        ],
    }




@router.get("/sessions/{session_id}/answers")
def get_answers(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    session = _require_session(db, session_id)
    return {"session_id": session.id, "answers": list_answers(db, session.id)}


@router.post("/sessions/{session_id}/stage1-preview")
def stage1_preview(session_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """Dev/test helper — run Stage 1 on arbitrary text without Attendee."""
    _require_session(db, session_id)
    text = str(body.get("text") or "")
    result = stage1_filter(text)
    return {
        "is_question": result.is_question,
        "is_odoo_relevant": result.is_odoo_relevant,
        "triggered": result.triggered,
        "reason": result.reason,
        "score": result.score,
    }


@router.post("/sessions/{session_id}/run-pipeline-sync")
def run_pipeline_sync(session_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """Test helper: append utterance then run Stage 1/2 synchronously."""
    session = _require_session(db, session_id)
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text required")
    if not session.mock_mode and not ldc.mock_allowed():
        # Still allow when session already mock-launched; otherwise require mock/dev
        from app.live_demo_copilot.service import mock_allowed
        if not mock_allowed():
            raise HTTPException(status_code=403, detail="Sync pipeline helper is for mock/dev only")
    line = ldc.append_transcript(
        db,
        session,
        speaker_name=str(body.get("speaker_name") or "Client"),
        speaker_uuid=None,
        text=text,
        timestamp_ms=None,
        schedule=False,
    )
    # append already schedules async; run sync for deterministic tests
    process_transcript_line(session.id, line.id)
    return {"session_id": session.id, "answers": list_answers(db, session.id)}

@router.get("/sessions/{session_id}/consent-audit")
def get_consent_audit(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.db_models import LiveDemoConsentAudit

    session = _require_session(db, session_id)
    rows = (
        db.query(LiveDemoConsentAudit)
        .filter(LiveDemoConsentAudit.session_id == session.id)
        .order_by(LiveDemoConsentAudit.created_at.asc())
        .all()
    )
    return {
        "session_id": session.id,
        "events": [
            {
                "id": r.id,
                "action": r.action,
                "disclosure_version": r.disclosure_version,
                "attendees_notified": r.attendees_notified,
                "retention_opt_in": r.retention_opt_in,
                "meeting_url_hash": r.meeting_url_hash,
                "actor_user_id": r.actor_user_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/sessions/{session_id}/mock-utterance", response_model=SessionOut)
def mock_utterance(
    session_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> SessionOut:
    session = _require_session(db, session_id)
    if not session.mock_mode and not ldc.mock_allowed():
        raise HTTPException(status_code=403, detail="Mock utterances disabled")
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text required")
    ldc.append_transcript(
        db,
        session,
        speaker_name=str(body.get("speaker_name") or "Client"),
        speaker_uuid=None,
        text=text,
        timestamp_ms=int(body.get("timestamp_ms") or 0) or None,
    )
    db.refresh(session)
    return _session_out(db, session)


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    _require_session(db, session_id)
    q = EVENT_BUS.subscribe(session_id)

    async def gen() -> AsyncIterator[str]:
        try:
            hello = {"type": "hello", "session_id": session_id}
            yield f"data: {json.dumps(hello)}\n\n"
            while True:
                try:
                    event = await asyncio.to_thread(q.get, True, 15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except Exception:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            EVENT_BUS.unsubscribe(session_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")


def _parse_webhook_timestamp(header: str | None) -> float | None:
    if not header:
        return None
    try:
        return float(header.strip())
    except ValueError:
        return None


@webhook_router.post("/webhooks/attendee")
async def attendee_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
    x_webhook_timestamp: str | None = Header(default=None, alias="X-Webhook-Timestamp"),
) -> dict[str, Any]:
    """Public Attendee webhook — HMAC required (except explicit non-prod mock without secret)."""
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    secret = (settings.attendee_webhook_secret or "").strip()
    env = settings.app_environment.strip().lower()
    production = env in {"production", "prod"}

    if not secret:
        if production or not ldc.mock_allowed():
            raise HTTPException(status_code=503, detail="ATTENDEE_WEBHOOK_SECRET not configured")
        logger.warning("Attendee webhook accepted without secret (non-prod mock only)")
    elif not verify_signature(payload, secret, x_webhook_signature or ""):
        raise HTTPException(status_code=400, detail="invalid signature")

    ts = _parse_webhook_timestamp(x_webhook_timestamp)
    if ts is not None:
        skew = abs(time.time() - ts)
        if skew > max(30, int(settings.attendee_webhook_max_skew_s)):
            raise HTTPException(status_code=400, detail="webhook timestamp skew too large")

    trigger = str(payload.get("trigger") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    bot_obj = data.get("bot") if isinstance(data.get("bot"), dict) else {}
    bot_id = str(
        data.get("bot_id") or payload.get("bot_id") or bot_obj.get("id") or ""
    ) or None

    session = ldc.by_bot(db, bot_id) if bot_id else None
    is_new, _digest = ldc.register_webhook_receipt(
        db,
        payload,
        trigger=trigger,
        bot_id=bot_id,
        session_id=session.id if session else None,
    )
    if not is_new:
        return {"ok": "true", "duplicate": True}

    if trigger == "bot.state_change" and session:
        state = normalize_raw_state(str(data.get("state") or data.get("new_state") or session.bot_state))
        ldc.set_bot_state(db, session, state)
    elif trigger == "transcript.update" and session:
        text = (
            data.get("transcription")
            or data.get("transcript")
            or data.get("text")
            or ""
        )
        if isinstance(text, dict):
            text = text.get("transcript") or text.get("text") or ""
        participant = data.get("participant") if isinstance(data.get("participant"), dict) else {}
        speaker = (
            data.get("speaker_name")
            or data.get("speaker")
            or participant.get("name")
            or "Unknown"
        )
        ts_ms = data.get("timestamp_ms")
        body = str(text).strip()
        if body:
            ldc.append_transcript(
                db,
                session,
                speaker_name=str(speaker),
                speaker_uuid=str(data.get("speaker_uuid") or "") or None,
                text=body,
                timestamp_ms=ts_ms if isinstance(ts_ms, int) else None,
            )
    else:
        logger.debug("Attendee webhook ignored trigger=%s bot_id=%s", trigger, bot_id)

    return {"ok": "true", "duplicate": False}
