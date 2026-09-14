"""Sandbox ingest: dry-run then auto-commit; staging/prod keep confirm."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingest.constants import CLASSIFY_MIN_CONFIDENCE
from app.ingest.pipeline import run_pipeline
from app.ingest.store import create_job
from app.job_autopilot.packet import IngestReport, JobPacket


def _source_rows(batch: Any) -> int:
    total = 0
    for table in getattr(batch, "tables", None) or []:
        rows = getattr(table, "rows", None)
        if rows is None and isinstance(table, dict):
            rows = table.get("rows")
        total += len(rows or [])
    return total


def _loaded_rows(batch: Any) -> int:
    log = getattr(batch, "commit_log", None)
    if log is None:
        return 0
    created = int(getattr(log, "created", 0) or 0)
    updated = int(getattr(log, "updated", 0) or 0)
    return created + updated


def _unmatched_m2o(batch: Any, gaps: list[str]) -> list[str]:
    out: list[str] = []
    for ref in getattr(batch, "refs", None) or []:
        resolved = getattr(ref, "resolved", True)
        if resolved:
            continue
        model = getattr(ref, "to_model", "") or ""
        field = getattr(ref, "field", "") or ""
        value = getattr(ref, "to_value", "") or ""
        out.append(f"{model}.{field}={value}")
    for table in getattr(batch, "tables", None) or []:
        model = getattr(table, "model", "") or ""
        for row in getattr(table, "rows", None) or []:
            for flag in getattr(row, "flags", None) or []:
                if str(flag).startswith("unresolved_m2o"):
                    out.append(f"{model}:{flag}")
    for g in gaps:
        low = g.lower()
        if "m2o" in low or "unresolved" in low or "unmatched" in low:
            out.append(g)
    return list(dict.fromkeys(out))


def _gap_messages(batch: Any) -> list[str]:
    gaps: list[str] = []
    plan = getattr(batch, "plan", None)
    raw = []
    if plan is not None:
        raw = getattr(plan, "gaps", None) or []
    if not raw:
        raw = getattr(batch, "gaps", None) or []
    for g in raw:
        if isinstance(g, str):
            gaps.append(g)
        elif isinstance(g, dict):
            gaps.append(str(g.get("message") or g.get("detail") or g))
        else:
            msg = getattr(g, "message", None) or getattr(g, "detail", None)
            gaps.append(str(msg or g))
    return gaps


def ingest_job_files(
    db: Session,
    client: Any,
    packet: JobPacket,
    files: list[tuple[str, bytes, str | None]],
    *,
    connection_id: str,
    allow_commit: bool,
) -> IngestReport:
    if not files:
        return IngestReport(skipped=True, reason="No client files attached.")
    report = IngestReport()
    row, _blobs = create_job(db, connection_id=connection_id, files=files)
    report.ingest_job_id = row.id
    try:
        batch = run_pipeline(db, row.id, client=client, through="dry_run")
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(str(exc))
        report.status = "error"
        report.message = f"Ingest dry-run failed: {exc}"
        report.dry_run_only = True
        return report
    report.gaps = _gap_messages(batch)
    report.source_rows = _source_rows(batch)
    report.unmatched_m2o = _unmatched_m2o(batch, report.gaps)
    report.status = getattr(batch, "status", None) or "dry_run"
    low_conf = [
        f.filename
        for f in packet.data_files
        if f.confidence < CLASSIFY_MIN_CONFIDENCE and f.doc_type == "other"
    ]
    needs_confirm = any(getattr(f, "needs_user_confirm", False) for f in batch.files)
    if report.gaps:
        report.dry_run_only = True
        report.message = "Dry-run blocked on gaps — not committing."
        report.warnings.extend(report.gaps)
        return report
    if needs_confirm or low_conf:
        report.dry_run_only = True
        report.message = (
            "Dry-run complete; classification needs operator confirm — not auto-committing."
        )
        return report
    if not allow_commit:
        report.dry_run_only = True
        report.message = (
            "Dry-run complete. Ingest commit is sandbox-auto or staging-with-confirm; skipped here."
        )
        return report
    try:
        batch = run_pipeline(db, row.id, client=client, through="commit")
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(str(exc))
        report.dry_run_only = True
        report.message = f"Ingest commit failed: {exc}"
        return report
    report.committed = True
    report.status = "committed"
    report.source_rows = _source_rows(batch) or report.source_rows
    report.loaded_rows = _loaded_rows(batch)
    report.unmatched_m2o = _unmatched_m2o(batch, report.gaps) or report.unmatched_m2o
    report.message = (
        f"Sandbox ingest committed after dry-run "
        f"({report.loaded_rows}/{report.source_rows or report.loaded_rows} rows)."
    )
    return report


__all__ = ["ingest_job_files"]
