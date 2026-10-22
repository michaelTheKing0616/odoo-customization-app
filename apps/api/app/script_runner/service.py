"""DEV-3 / DEV-SR — script run orchestration, journal, saved scripts."""

from __future__ import annotations

import ast
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.crypto import decrypt_secret
from app.db_models import OdooConnection, ScriptRun
from app.jobs import create_job, enqueue
from app.script_runner.executor import run_script_in_subprocess
from app.script_runner.templates import SCRIPT_TEMPLATES
from app.snapshots import require_advanced_confirmation, save_snapshot

_READ_METHODS = frozenset(
    {
        "search",
        "search_read",
        "read",
        "search_count",
        "fields_get",
        "name_search",
        "default_get",
        "read_group",
        "formatted_read_group",
        "context_get",
        "exists",
        "get_views",
    }
)

RESTORE_NOTE = (
    "Open the journal and restore a view, automation, or server action if this script changed one. "
    "This snapshot does not undo record writes. Dropped columns cannot be restored."
)


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


def script_performs_write(script: str) -> bool:
    """True when the script calls a non-read ``execute_kw`` or the method is dynamic."""
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "execute_kw":
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            return True
        method = node.args[1].value
        if not isinstance(method, str) or method not in _READ_METHODS:
            return True
    return False


def total_write_count(counts: dict[str, Any] | None) -> int:
    total = 0
    if not isinstance(counts, dict):
        return 0
    for bucket in counts.values():
        if not isinstance(bucket, dict):
            continue
        for key in ("create", "write", "unlink"):
            value = bucket.get(key)
            if isinstance(value, int):
                total += value
    return total


def _crash_error(exc: BaseException) -> str:
    return f"Script runner crashed ({type(exc).__name__})"


def _attach_write_snapshot(db: Session, run: ScriptRun, script: str) -> None:
    if not script_performs_write(script):
        return
    snap = save_snapshot(
        db,
        connection_id=run.connection_id,
        resource_type="script_run",
        resource_key=f"script:{run.id}",
        label="Script Runner write",
        payload={
            "script_hash": run.script_hash,
            "run_id": run.id,
            "restore": RESTORE_NOTE,
        },
        reversible="partial",
    )
    run.snapshot_id = snap.id
    db.add(run)
    db.commit()


def _run_or_fail(
    *,
    script: str,
    connection_config: dict[str, Any],
    job_id: str,
    count_writes: bool,
) -> dict[str, Any]:
    try:
        return run_script_in_subprocess(
            script=script,
            connection_config=connection_config,
            job_id=job_id,
            count_writes=count_writes,
        )
    except Exception as exc:  # noqa: BLE001 — a crash must become a failed journal row
        return {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "error": _crash_error(exc),
            "write_counts": {},
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
    _attach_write_snapshot(db, run, script)
    config = connection_config_dict(connection)

    def _work() -> dict[str, Any]:
        from app.db import SessionLocal

        result = _run_or_fail(
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
    _attach_write_snapshot(db, run, script)
    result = _run_or_fail(
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
