"""Durable Live Demo Co-Pilot session operations (workspace-scoped)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    LiveDemoConsentAudit,
    LiveDemoCopilotSession,
    LiveDemoTranscriptLine,
    LiveDemoWebhookReceipt,
    OdooConnection,
)
from app.live_demo_copilot.events import EVENT_BUS
from app.live_demo_copilot.pipeline import schedule_pipeline
from app.live_demo_copilot.stage1_filter import parse_presenter_speakers
from app.live_demo_copilot.webhook_crypto import meeting_url_sha256, payload_sha256
from app.workspace_auth import WorkspaceAuth, current_workspace_auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_workspace_id(db: Session, connection_id: str | None) -> str | None:
    auth = current_workspace_auth()
    if auth and auth.workspace_id:
        return auth.workspace_id
    if connection_id:
        row = db.get(OdooConnection, connection_id)
        if row is not None:
            return row.workspace_id
    return None


def assert_session_tenant(session: LiveDemoCopilotSession, auth: WorkspaceAuth | None) -> None:
    """IDOR choke — workspace-scoped accounts may only see their sessions."""
    if auth is None or not auth.workspace_scoped:
        return
    if session.workspace_id and session.workspace_id != auth.workspace_id:
        raise PermissionError("Session not found in this workspace")


def create_session(
    db: Session,
    *,
    meeting_url: str,
    bot_name: str,
    connection_id: str | None,
    presenter_speakers: list[str] | None = None,
) -> LiveDemoCopilotSession:
    auth = current_workspace_auth()
    workspace_id = resolve_workspace_id(db, connection_id)
    if connection_id and auth and auth.workspace_scoped:
        row = db.get(OdooConnection, connection_id)
        if row is None or row.workspace_id != auth.workspace_id:
            raise LookupError("Connection not found")
        workspace_id = auth.workspace_id

    sid = f"ldc_{uuid.uuid4().hex[:16]}"
    names = parse_presenter_speakers(presenter_speakers)
    session = LiveDemoCopilotSession(
        id=sid,
        workspace_id=workspace_id,
        connection_id=connection_id,
        created_by_user_id=auth.user_id if auth else None,
        meeting_url=meeting_url.strip(),
        meeting_url_hash=meeting_url_sha256(meeting_url),
        bot_name=(bot_name.strip() or "Odoo Demo Co-Pilot")[:120],
        presenter_speakers_json=json.dumps(names),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> LiveDemoCopilotSession | None:
    return db.get(LiveDemoCopilotSession, session_id)


def get_session_for_request(db: Session, session_id: str) -> LiveDemoCopilotSession:
    session = get_session(db, session_id)
    if session is None:
        raise LookupError("Session not found")
    try:
        assert_session_tenant(session, current_workspace_auth())
    except PermissionError as exc:
        raise LookupError("Session not found") from exc
    return session


def record_consent(
    db: Session,
    session: LiveDemoCopilotSession,
    *,
    accepted: bool,
    attendees_notified: bool,
    retention_opt_in: bool,
    disclosure_version: str,
) -> LiveDemoCopilotSession:
    auth = current_workspace_auth()
    action = "accepted" if accepted and attendees_notified else "declined"
    if action == "declined":
        session.declined = True
        session.disclosure_accepted = False
        session.attendees_notified = False
        session.retention_opt_in = False
        session.bot_state = "declined"
    else:
        session.declined = False
        session.disclosure_accepted = True
        session.attendees_notified = True
        session.disclosure_version = disclosure_version
        session.disclosure_accepted_at = _utcnow()
        session.retention_opt_in = bool(retention_opt_in)

    audit = LiveDemoConsentAudit(
        session_id=session.id,
        workspace_id=session.workspace_id,
        actor_user_id=auth.user_id if auth else None,
        action=action,
        disclosure_version=disclosure_version,
        attendees_notified=bool(attendees_notified) if action == "accepted" else False,
        retention_opt_in=bool(retention_opt_in) if action == "accepted" else False,
        meeting_url_hash=session.meeting_url_hash,
    )
    db.add(audit)
    db.add(session)
    db.commit()
    db.refresh(session)
    EVENT_BUS.publish(session.id, {"type": "status", "data": {"bot_state": session.bot_state, "consent": action}})
    return session


def bind_bot(db: Session, session: LiveDemoCopilotSession, bot_id: str, *, mock: bool, state: str) -> LiveDemoCopilotSession:
    session.attendee_bot_id = bot_id
    session.mock_mode = mock
    session.bot_state = state
    db.add(session)
    db.commit()
    db.refresh(session)
    EVENT_BUS.publish(session.id, {"type": "status", "data": {"bot_state": state, "mock": mock}})
    return session


def set_bot_state(db: Session, session: LiveDemoCopilotSession, state: str) -> LiveDemoCopilotSession:
    session.bot_state = state
    db.add(session)
    db.commit()
    db.refresh(session)
    EVENT_BUS.publish(session.id, {"type": "status", "data": {"bot_state": state}})
    return session


def by_bot(db: Session, bot_id: str) -> LiveDemoCopilotSession | None:
    return (
        db.query(LiveDemoCopilotSession)
        .filter(LiveDemoCopilotSession.attendee_bot_id == bot_id)
        .one_or_none()
    )


def append_transcript(
    db: Session,
    session: LiveDemoCopilotSession,
    *,
    speaker_name: str,
    speaker_uuid: str | None,
    text: str,
    timestamp_ms: int | None,
    schedule: bool = True,
) -> LiveDemoTranscriptLine:
    line = LiveDemoTranscriptLine(
        session_id=session.id,
        workspace_id=session.workspace_id,
        speaker_name=speaker_name[:200] or "Unknown",
        speaker_uuid=speaker_uuid,
        text=text,
        timestamp_ms=timestamp_ms,
    )
    db.add(line)
    db.add(session)  # touch updated_at
    db.commit()
    db.refresh(line)
    EVENT_BUS.publish(
        session.id,
        {
            "type": "transcript",
            "data": {
                "speaker_name": line.speaker_name,
                "speaker_uuid": line.speaker_uuid,
                "text": line.text,
                "timestamp_ms": line.timestamp_ms,
            },
        },
    )
    if schedule:
        schedule_pipeline(session.id, line.id)
    return line


def list_transcript(db: Session, session_id: str) -> list[LiveDemoTranscriptLine]:
    return (
        db.query(LiveDemoTranscriptLine)
        .filter(LiveDemoTranscriptLine.session_id == session_id)
        .order_by(LiveDemoTranscriptLine.created_at.asc())
        .all()
    )


def purge_transcript(db: Session, session: LiveDemoCopilotSession) -> int:
    q = db.query(LiveDemoTranscriptLine).filter(LiveDemoTranscriptLine.session_id == session.id)
    n = q.count()
    q.delete(synchronize_session=False)
    session.data_purged_at = _utcnow()
    db.add(session)
    db.commit()
    return n


def mark_ended(db: Session, session: LiveDemoCopilotSession) -> LiveDemoCopilotSession:
    session.bot_state = "ended"
    session.ended_at = _utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    EVENT_BUS.publish(session.id, {"type": "status", "data": {"bot_state": "ended"}})
    return session


def register_webhook_receipt(
    db: Session,
    payload: dict[str, Any],
    *,
    trigger: str,
    bot_id: str | None,
    session_id: str | None,
) -> tuple[bool, str]:
    """Return (is_new, payload_hash). is_new False means replay / duplicate."""
    digest = payload_sha256(payload)
    existing = (
        db.query(LiveDemoWebhookReceipt)
        .filter(LiveDemoWebhookReceipt.payload_hash == digest)
        .one_or_none()
    )
    if existing is not None:
        return False, digest
    db.add(
        LiveDemoWebhookReceipt(
            payload_hash=digest,
            trigger=trigger[:64],
            bot_id=bot_id,
            session_id=session_id,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        return False, digest
    return True, digest


def mock_allowed() -> bool:
    from app.settings import settings

    env = settings.app_environment.strip().lower()
    if env in {"production", "prod"}:
        return False
    return bool(settings.attendee_allow_mock)


def set_ops_fields(
    db: Session,
    session: LiveDemoCopilotSession,
    *,
    leave_purge_status: str | None = None,
    last_ops_error: str | None = None,
    leave_purge_job_id: str | None = None,
) -> LiveDemoCopilotSession:
    if leave_purge_status is not None:
        session.leave_purge_status = leave_purge_status
    if last_ops_error is not None:
        session.last_ops_error = last_ops_error
    if leave_purge_job_id is not None:
        session.leave_purge_job_id = leave_purge_job_id
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_presenter_speakers(
    db: Session,
    session: LiveDemoCopilotSession,
    speakers: list[str] | str,
) -> LiveDemoCopilotSession:
    names = parse_presenter_speakers(speakers)
    session.presenter_speakers_json = json.dumps(names)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def presenter_speakers_list(session: LiveDemoCopilotSession) -> list[str]:
    return parse_presenter_speakers(getattr(session, "presenter_speakers_json", None) or "[]")
