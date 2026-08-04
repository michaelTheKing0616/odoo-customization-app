"""DEV-3 — script run orchestration, journal, saved scripts."""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.crypto import decrypt_secret
from app.db_models import OdooConnection, SavedScript, ScriptRun
from app.jobs import create_job, enqueue
from app.script_runner.executor import run_script_in_subprocess
from app.script_runner.templates import SCRIPT_TEMPLATES
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation


def script_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def connection_config_dict(row: OdooConnection) -> dict[str, Any]:
    return {
        "url": row.url,
        "db": row.db_name,
        "username": row.username,
        "password": decrypt_secret(row.secret_encrypted),
        "write_mode": row.write_mode or "standard",
    }


def require_script_confirm(
    *,
    confirm_advanced: bool,
    confirm_phrase: str | None,
    script: str,
) -> None:
    require_advanced_confirmation(
        confirm_advanced=confirm_advanced,
        confirm_phrase=confirm_phrase,
        warning=(
            "Script Runner executes Python against this Odoo connection with your credentials. "
            "Review the script — it can read and write any data your user can access."
        ),
        risks=[
            "Runs in an isolated subprocess but uses real Odoo RPC",
            "Write counts are reported but side effects are not auto-reversed",
            "Observer mode and kill switch still apply at the API gate",
        ],
    )


def create_script_run_row(
    db: Session,
    *,
    connection_id: str,
    workspace_id: str | None,
    script: str,
    saved_script_id: str | None = None,
    job_id: str | None = None,
) -> ScriptRun:
    row = ScriptRun(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        connection_id=connection_id,
        job_id=job_id,
        saved_script_id=saved_script_id,
        script_content=script,
        script_hash=script_hash(script),
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def finish_script_run(db: Session, run_id: str, result: dict[str, Any]) -> ScriptRun:
    row = db.get(ScriptRun, run_id)
    if row is None:
        raise LookupError("Script run not found")
    row.status = "succeeded" if result.get("ok") else "failed"
    row.stdout = (result.get("stdout") or "")[:500000]
    row.stderr = (result.get("stderr") or "")[:200000]
    row.error = result.get("error")
    import json

    row.write_counts_json = json.dumps(result.get("write_counts") or {})
    row.finished_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def enqueue_script_run(
    db: Session,
    *,
    connection: OdooConnection,
    script: str,
    workspace_id: str | None,
    saved_script_id: str | None = None,
    count_writes: bool = True,
) -> tuple[ScriptRun, str]:
    job = create_job(db, kind="script_run", connection_id=connection.id)
    run = create_script_run_row(
        db,
        connection_id=connection.id,
        workspace_id=workspace_id,
        script=script,
        saved_script_id=saved_script_id,
        job_id=job.id,
    )
    config = connection_config_dict(connection)

    def _work() -> dict[str, Any]:
        from app.db import SessionLocal

        result = run_script_in_subprocess(
            script=script,
            connection_config=config,
            job_id=job.id,
            count_writes=count_writes,
        )
        wdb = SessionLocal()
        try:
            finish_script_run(wdb, run.id, result)
        finally:
            wdb.close()
        return {
            "run_id": run.id,
            "ok": result.get("ok"),
            "stdout": (result.get("stdout") or "")[-8000:],
            "stderr": (result.get("stderr") or "")[-4000:],
            "write_counts": result.get("write_counts") or {},
            "error": result.get("error"),
        }

    enqueue(job.id, _work)
    return run, job.id


def run_script_sync(
    db: Session,
    *,
    connection: OdooConnection,
    script: str,
    workspace_id: str | None,
    count_writes: bool = True,
) -> ScriptRun:
    run = create_script_run_row(
        db,
        connection_id=connection.id,
        workspace_id=workspace_id,
        script=script,
    )
    result = run_script_in_subprocess(
        script=script,
        connection_config=connection_config_dict(connection),
        job_id=run.id,
        count_writes=count_writes,
    )
    return finish_script_run(db, run.id, result)


def list_templates() -> list[dict[str, str]]:
    return list(SCRIPT_TEMPLATES)


def audit_detail_for_run(*, script: str, run_id: str, operation: str = "script_run") -> dict[str, Any]:
    return {
        "operation": operation,
        "run_id": run_id,
        "code": script,
        "script_hash": script_hash(script),
    }
