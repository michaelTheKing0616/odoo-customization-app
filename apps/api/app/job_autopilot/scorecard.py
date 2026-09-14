"""Implementation-job scorecard — not ModuleSpec completeness 10.0."""

from __future__ import annotations

from app.job_autopilot.packet import AutopilotResult, JobScorecard, SCORECARD_IS_NOT_GOLIVE


def _clamp(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 1)


def score_job(result: AutopilotResult) -> JobScorecard:
    """Four dimensions; overall is the min. Smoke fail is never go-live."""
    findings: list[str] = []
    packet = result.packet

    if result.refused:
        findings.append(result.refuse_reason or "Autopilot refused this connection.")
        return JobScorecard(
            stack_fit=0.0,
            stock_coverage=0.0,
            data_load=0.0,
            process_smoke=0.0,
            overall=0.0,
            findings=findings,
            modulespec_completeness_note=SCORECARD_IS_NOT_GOLIVE,
        )

    stack = 10.0 if packet.stock_apps else 3.0
    if packet.has_custom_residual:
        stack = min(stack, 8.5)
        findings.append(
            f"Custom residual {', '.join(r.model for r in packet.custom_residuals)} — "
            "stock apps do not cover this document."
        )
    else:
        findings.append("Stock-only packet — no custom x_* residual.")
    if not packet.stock_apps:
        findings.append("No stock apps inferred — stack fit is weak.")

    boot = result.bootstrap
    if boot is None:
        coverage = 0.0
        findings.append("Stock bootstrap did not run.")
    else:
        probes = list(getattr(boot, "probes", None) or [])
        installed = list(getattr(boot, "installed", None) or [])
        already = list(getattr(boot, "already_installed", None) or [])
        skipped = list(getattr(boot, "skipped", None) or [])
        warnings = list(getattr(boot, "warnings", None) or [])
        if probes:
            coverage = 10.0 * (sum(1 for p in probes if getattr(p, "ok", False)) / len(probes))
        elif installed or already:
            coverage = 8.0
        else:
            coverage = 2.0
        if skipped:
            findings.append(f"Modules skipped: {', '.join(str(s) for s in skipped[:8])}")
            coverage = min(coverage, 7.0)
        if warnings:
            coverage = min(coverage, 8.0)

    ingest = result.ingest
    if ingest is None or ingest.skipped:
        if packet.data_files:
            data = 0.0
            findings.append("Client files were classified but ingest did not run.")
        else:
            data = 7.0
            findings.append("No client files — data-load is N/A (scored 7, not 10).")
    elif ingest.gaps or ingest.unmatched_m2o:
        data = 2.0 if ingest.gaps else 5.0
        if ingest.unmatched_m2o:
            data = min(data, 5.0)
            findings.append(f"Unmatched M2O: {len(ingest.unmatched_m2o)}")
        if ingest.gaps:
            findings.append(f"Ingest gaps: {len(ingest.gaps)}")
    elif ingest.committed:
        source = max(int(ingest.source_rows or 0), 0)
        loaded = max(int(ingest.loaded_rows or 0), 0)
        if source <= 0:
            data = 10.0 if loaded >= 0 else 8.0
        else:
            data = 10.0 * (loaded / source)
            if loaded < source:
                findings.append(f"Loaded {loaded}/{source} source rows.")
        if ingest.unmatched_m2o:
            data = min(data, 6.0)
    elif ingest.dry_run_only:
        data = 4.0
        findings.append("Ingest stayed dry-run — not auto-committed.")
    else:
        data = 3.0

    smoke = result.smoke
    if smoke is None:
        process = 0.0
        findings.append("Process smoke did not run.")
    elif smoke.ok:
        process = 10.0
        findings.append(
            f"Process smoke passed ({smoke.named_process or 'default'})."
        )
    else:
        process = 0.0
        failed = [s.name for s in (smoke.steps or []) if not s.ok]
        findings.append(
            "Process smoke failed"
            + (f": {', '.join(failed[:6])}" if failed else "")
            + " — not go-live."
        )

    conn = result.connectors
    if conn and not conn.skipped:
        if conn.ran:
            findings.append("Connectors ran: " + ", ".join(conn.ran))
        if conn.skipped_ids:
            findings.append("Connectors skipped: " + ", ".join(conn.skipped_ids))
        if conn.failed:
            findings.append("Connectors failed: " + ", ".join(conn.failed))
            findings.append(
                "Connector failures do not zero process smoke — they are residual partner/hardware gaps."
            )
        elif conn.ran:
            findings.append(
                "Connectors landed sandbox fixtures only — not live Paystack/WhatsApp/FIRS APIs."
            )

    overall = min(stack, coverage, data, process)
    findings.append(SCORECARD_IS_NOT_GOLIVE)
    return JobScorecard(
        stack_fit=_clamp(stack),
        stock_coverage=_clamp(coverage),
        data_load=_clamp(data),
        process_smoke=_clamp(process),
        overall=_clamp(overall),
        findings=findings[:20],
        modulespec_completeness_note=SCORECARD_IS_NOT_GOLIVE,
    )


__all__ = ["score_job"]
