"""Background leave + purge for Live Demo Co-Pilot sessions."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.db import SessionLocal
from app.db_models import LiveDemoCopilotSession
from app.jobs import create_job, enqueue
from app.job_runner import JOB_TIMEOUTS
from app.live_demo_copilot.attendee_client import leave_and_purge_with_retries
from app.live_demo_copilot.events import EVENT_BUS
from app.live_demo_copilot import service as ldc

logger = logging.getLogger(__name__)

# Register timeout for this kind
JOB_TIMEOUTS.setdefault("live_demo_leave_purge", 120.0)


def enqueue_leave_purge(db, session: LiveDemoCopilotSession, *, purge: bool) -> str | None:
    """Enqueue async leave/purge; returns job id. Mock sessions skip Attendee calls."""
    if session.mock_mode or not session.attendee_bot_id:
        if purge:
            ldc.purge_transcript(db, session)
        session.leave_purge_status = "succeeded"
        session.last_ops_error = None
        db.add(session)
        db.commit()
        return None

    session.leave_purge_status = "pending"
    session.last_ops_error = None
    job = create_job(db, kind="live_demo_leave_purge", connection_id=session.connection_id)
    session.leave_purge_job_id = job.id
    db.add(session)
    db.commit()

    session_id = session.id
    bot_id = session.attendee_bot_id
    do_purge = purge

    def _run() -> dict[str, Any]:
        result = leave_and_purge_with_retries(bot_id, purge=do_purge)
        db2 = SessionLocal()
        try:
            row = db2.get(LiveDemoCopilotSession, session_id)
            if row is None:
                return result
            ok = bool(result.get("leave_ok")) and (result.get("purge_ok") in (True, None))
            if do_purge and result.get("purge_ok") is False:
                ok = False
            if do_purge and result.get("leave_ok"):
                # Local transcript purge even if Attendee purge failed (minimize local retention)
                try:
                    ldc.purge_transcript(db2, row)
                    row = db2.get(LiveDemoCopilotSession, session_id) or row
                except Exception as exc:  # noqa: BLE001
                    result.setdefault("errors", []).append(f"local_purge: {exc}")
                    ok = False
            row.leave_purge_status = "succeeded" if ok else "failed"
            if not ok:
                row.last_ops_error = "; ".join(result.get("errors") or ["leave/purge failed"])[:2000]
            else:
                row.last_ops_error = None
            db2.add(row)
            db2.commit()
            EVENT_BUS.publish(
                session_id,
                {
                    "type": "status",
                    "data": {
                        "bot_state": row.bot_state,
                        "leave_purge_status": row.leave_purge_status,
                        "last_ops_error": row.last_ops_error,
                    },
                },
            )
        finally:
            db2.close()
        return result

    enqueue(job.id, _run)
    return job.id
