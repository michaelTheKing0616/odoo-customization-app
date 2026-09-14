"""Orchestrate sandbox Job Autopilot: packet → stock → connectors → custom → ingest → smoke."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.job_autopilot.bootstrap import bootstrap_stock
from app.job_autopilot.client_index import retrieve_grounding, upsert_client_docs
from app.job_autopilot.connectors import run_connectors
from app.job_autopilot.custom import apply_custom_residual
from app.job_autopilot.ingest_bridge import ingest_job_files
from app.job_autopilot.packet import AutopilotResult, IngestReport, JobPacket, SCORECARD_IS_NOT_GOLIVE
from app.job_autopilot.planner import build_job_packet, file_excerpts_from_bytes
from app.job_autopilot.report import attach_reports
from app.job_autopilot.sandbox_gate import (
    AutopilotRefused,
    assert_autopilot_run_allowed,
    classify_connection,
    is_sandbox_connection,
)
from app.job_autopilot.scorecard import score_job
from app.job_autopilot.smoke import run_process_smoke
from app.snapshots import ConfirmationRequired

MAX_SMOKE_RETRIES = 2


def _index_and_ground(
    packet: JobPacket,
    *,
    connection_id: str,
    files: list[tuple[str, bytes, str | None]],
) -> None:
    if not connection_id:
        return
    excerpts = file_excerpts_from_bytes([(n, b) for n, b, _m in files]) if files else []
    if excerpts:
        upsert_client_docs(connection_id, excerpts)
    grounding = retrieve_grounding(connection_id, packet.prompt)
    if grounding:
        packet.grounding = grounding


def _retry_after_smoke_fail(
    *,
    client: Any,
    packet: JobPacket,
    result: AutopilotResult,
    db: Session | None,
    connection_id: str,
    draft_fn: Any | None,
    progress_job_id: str | None = None,
) -> None:
    """Re-run process smoke (and one spec re-apply, no Expert LLM). Never seeds walkthrough data."""
    if result.smoke is None or result.smoke.ok:
        return
    for attempt in range(1, MAX_SMOKE_RETRIES + 1):
        result.retry_count = attempt
        _mark_stage(result, f"smoke_retry_{attempt}", progress_job_id=progress_job_id)
        if (
            attempt == 1
            and packet.has_custom_residual
            and result.custom
            and result.custom.spec
        ):
            result.custom = apply_custom_residual(
                client,
                packet,
                spec=result.custom.spec,
                db=db,
                connection_id=connection_id,
                draft_fn=draft_fn,
                skip_expert=True,
            )
        result.smoke = run_process_smoke(client, packet, ingest=result.ingest)
        if result.smoke.ok:
            return
    result.walkthrough_seeded = False


def _mark_stage(result: AutopilotResult, name: str, *, progress_job_id: str | None) -> None:
    result.stages.append(name)
    if not progress_job_id:
        return
    from app.job_runner import update_job_progress

    update_job_progress(
        progress_job_id,
        {"step_label": name, "stages": list(result.stages)},
    )


def run_autopilot_job(
    *,
    client: Any,
    connection: Any,
    prompt: str,
    files: list[tuple[str, bytes, str | None]] | None = None,
    packet: JobPacket | None = None,
    spec: dict[str, Any] | None = None,
    db: Session | None = None,
    confirm_advanced: bool = False,
    confirm_phrase: str | None = None,
    use_llm: bool | None = None,
    draft_fn: Any | None = None,
    progress_job_id: str | None = None,
) -> AutopilotResult:
    """Execute Autopilot on a sandbox (or confirmed staging). Never production."""
    files = files or []
    try:
        kind = assert_autopilot_run_allowed(
            connection,
            confirm_advanced=confirm_advanced,
            confirm_phrase=confirm_phrase,
        )
    except AutopilotRefused as exc:
        empty = packet or JobPacket(prompt=prompt or "")
        refused_kind, _ = classify_connection(connection)
        refused = AutopilotResult(
            ok=False,
            refused=True,
            refuse_reason=exc.reason,
            connection_kind=refused_kind,
            packet=empty,
            message=exc.reason,
            scorecard_note=SCORECARD_IS_NOT_GOLIVE,
        )
        refused.job_scorecard = score_job(refused)
        return attach_reports(refused)
    except ConfirmationRequired:
        raise

    sandbox = is_sandbox_connection(connection)
    connection_id = str(getattr(connection, "id", "") or "")
    if packet is None:
        excerpts = file_excerpts_from_bytes([(n, b) for n, b, _m in files])
        packet = build_job_packet(prompt, file_excerpts=excerpts, use_llm=use_llm)
    _index_and_ground(packet, connection_id=connection_id, files=files)

    result = AutopilotResult(
        packet=packet,
        connection_kind=kind,
        sandbox=sandbox,
        clone_required=False,
    )
    _mark_stage(result, "packet", progress_job_id=progress_job_id)

    _mark_stage(result, "stock", progress_job_id=progress_job_id)
    result.bootstrap = bootstrap_stock(client, packet)

    _mark_stage(result, "connectors", progress_job_id=progress_job_id)
    result.connectors = run_connectors(client, packet, result.bootstrap)

    _mark_stage(result, "custom", progress_job_id=progress_job_id)

    def _custom_progress(label: str) -> None:
        if not progress_job_id:
            return
        from app.job_runner import update_job_progress

        update_job_progress(
            progress_job_id,
            {"step_label": label, "stages": list(result.stages)},
        )

    result.custom = apply_custom_residual(
        client,
        packet,
        spec=spec,
        db=db,
        connection_id=connection_id,
        draft_fn=draft_fn,
        on_progress=_custom_progress,
    )

    _mark_stage(result, "data", progress_job_id=progress_job_id)
    if files and db is not None:
        result.ingest = ingest_job_files(
            db,
            client,
            packet,
            files,
            connection_id=connection_id,
            allow_commit=sandbox or kind == "staging",
        )
    else:
        result.ingest = IngestReport(skipped=True, reason="No files or no database session.")
        try:
            from app.job_autopilot.demo_seed import seed_brief_master_data

            extra = seed_brief_master_data(client, packet)
            if extra:
                result.ingest.warnings = [s.detail for s in extra]
                if result.bootstrap:
                    result.bootstrap.probes.extend(extra)
        except Exception as exc:  # noqa: BLE001
            if result.bootstrap:
                result.bootstrap.warnings.append(f"Brief master data seed skipped: {exc}")

    _mark_stage(result, "smoke", progress_job_id=progress_job_id)
    result.smoke = run_process_smoke(client, packet, ingest=result.ingest)
    _retry_after_smoke_fail(
        client=client,
        packet=packet,
        result=result,
        db=db,
        connection_id=connection_id,
        draft_fn=draft_fn,
        progress_job_id=progress_job_id,
    )

    try:
        from app.config_packet.capture import capture_config_packet

        packet_doc = capture_config_packet(client, result)
        result.config_packet = packet_doc.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        note = f"Config Packet capture skipped: {exc}"
        boot = result.bootstrap
        warnings = getattr(boot, "warnings", None)
        if isinstance(warnings, list):
            warnings.append(note)

    result.job_scorecard = score_job(result)
    result.promote_ready = bool(result.smoke and result.smoke.ok) and not result.refused
    result.ok = result.promote_ready
    if result.ok:
        result.message = (
            "Sandbox Autopilot finished. Process smoke passed. Promote stays a human step. "
            f"Job scorecard overall {result.job_scorecard.overall:.1f}/10 "
            "(not ModuleSpec completeness)."
        )
    else:
        result.message = (
            result.smoke.message
            if result.smoke
            else "Autopilot did not pass process smoke — do not Promote."
        )
    return attach_reports(result)


__all__ = ["MAX_SMOKE_RETRIES", "run_autopilot_job"]
