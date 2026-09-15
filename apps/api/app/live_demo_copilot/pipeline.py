"""Transcript → Stage 1 → Stage 2 pipeline (async, non-blocking for webhooks)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from app.db import SessionLocal
from app.db_models import LiveDemoAnswer, LiveDemoCopilotSession, LiveDemoTranscriptLine
from app.live_demo_copilot.events import EVENT_BUS
from app.live_demo_copilot.stage1_filter import (
    is_likely_bot_or_system_speaker,
    is_presenter_speaker,
    parse_presenter_speakers,
    stage1_filter,
)
from app.live_demo_copilot.stage2_answer import generate_live_answer

logger = logging.getLogger(__name__)


def _answer_payload(row: LiveDemoAnswer) -> dict[str, Any]:
    try:
        bullets = json.loads(row.bullets_json or "[]")
    except json.JSONDecodeError:
        bullets = []
    try:
        citations = json.loads(row.citations_json or "[]")
    except json.JSONDecodeError:
        citations = []
    return {
        "id": row.id,
        "session_id": row.session_id,
        "question": row.question,
        "speaker_name": row.speaker_name,
        "bullets": bullets if isinstance(bullets, list) else [],
        "confidence": row.confidence,
        "confidence_flag": row.confidence_flag,
        "grounded": row.grounded,
        "declined": row.declined,
        "citations": citations if isinstance(citations, list) else [],
        "status": row.status,
        "stage1_reason": row.stage1_reason,
        "stage1_score": row.stage1_score,
        "model_used": row.model_used,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_answers(db, session_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(LiveDemoAnswer)
        .filter(LiveDemoAnswer.session_id == session_id)
        .order_by(LiveDemoAnswer.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_answer_payload(r) for r in rows]


def process_transcript_line(session_id: str, line_id: str) -> None:
    db = SessionLocal()
    try:
        session = db.get(LiveDemoCopilotSession, session_id)
        line = db.get(LiveDemoTranscriptLine, line_id)
        if session is None or line is None:
            return
        if is_likely_bot_or_system_speaker(line.speaker_name, session.bot_name):
            return
        presenters = parse_presenter_speakers(getattr(session, "presenter_speakers_json", None) or "[]")
        if is_presenter_speaker(line.speaker_name, presenters):
            return
        s1 = stage1_filter(line.text)
        if not s1.triggered:
            return

        # Dedup: same question text on this session in last N answers
        recent = (
            db.query(LiveDemoAnswer)
            .filter(LiveDemoAnswer.session_id == session_id)
            .order_by(LiveDemoAnswer.created_at.desc())
            .limit(5)
            .all()
        )
        qnorm = " ".join(line.text.lower().split())
        if any(" ".join((r.question or "").lower().split()) == qnorm for r in recent):
            return

        pending = LiveDemoAnswer(
            session_id=session.id,
            workspace_id=session.workspace_id,
            transcript_line_id=line.id,
            question=line.text.strip(),
            speaker_name=line.speaker_name,
            stage1_reason=s1.reason[:200],
            stage1_score=f"{s1.score:.2f}",
            status="pending",
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        EVENT_BUS.publish(session.id, {"type": "answer", "data": _answer_payload(pending)})

        live = generate_live_answer(
            db,
            question=line.text.strip(),
            connection_id=session.connection_id,
        )
        pending.bullets_json = json.dumps(live.bullets)
        pending.confidence = live.confidence
        pending.confidence_flag = live.confidence_flag
        pending.grounded = live.grounded
        pending.declined = live.declined
        pending.citations_json = json.dumps(live.citations)
        pending.answer_markdown = live.answer_markdown or ""
        pending.model_used = live.model_used
        pending.status = "ready"
        db.add(pending)
        db.commit()
        db.refresh(pending)
        EVENT_BUS.publish(session.id, {"type": "answer", "data": _answer_payload(pending)})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live demo pipeline failed session=%s line=%s: %s", session_id, line_id, exc)
        try:
            row = (
                db.query(LiveDemoAnswer)
                .filter(
                    LiveDemoAnswer.session_id == session_id,
                    LiveDemoAnswer.transcript_line_id == line_id,
                    LiveDemoAnswer.status == "pending",
                )
                .order_by(LiveDemoAnswer.created_at.desc())
                .first()
            )
            if row is not None:
                row.status = "failed"
                row.error = str(exc)[:2000]
                row.confidence = "low"
                row.bullets_json = json.dumps(
                    ["Live answer failed.", "Park the question for follow-up."]
                )
                db.add(row)
                db.commit()
                EVENT_BUS.publish(session_id, {"type": "answer", "data": _answer_payload(row)})
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def schedule_pipeline(session_id: str, line_id: str) -> None:
    threading.Thread(
        target=process_transcript_line,
        args=(session_id, line_id),
        name=f"ldc-pipeline-{line_id[:8]}",
        daemon=True,
    ).start()
