"""Run inferred connector recipes in CONNECTOR_ORDER on a sandbox."""

from __future__ import annotations

from typing import Any

from app.job_autopilot.connectors.catalog import CONNECTOR_ORDER, detected_brands, spec_for
from app.job_autopilot.connectors.hardware import run_hardware
from app.job_autopilot.connectors.inbound import run_inbound_orders
from app.job_autopilot.connectors.messaging import run_messaging
from app.job_autopilot.connectors.payments import run_payments
from app.job_autopilot.connectors.statutory import compute, has_pack
from app.job_autopilot.packet import (
    BootstrapReport,
    ConnectorReport,
    JobPacket,
    ProbeResult,
)


def _payroll_step(packet: JobPacket) -> ProbeResult:
    cc = packet.country_code
    if not has_pack(cc):
        return ProbeResult(
            name="statutory_payroll",
            ok=False,
            detail=(
                f"No statutory pack for country {cc or 'unknown'}. "
                "Add a golden-file pack — do not LLM payslip math."
            ),
        )
    result = compute(cc, 500_000.0)
    assert result is not None
    return ProbeResult(
        name="statutory_payroll",
        ok=True,
        detail=(
            f"{result.country} fixture gross={result.gross} PAYE={result.paye} "
            f"pension_ee={result.employee_pension} NHF={result.nhf} net={result.net}. "
            + " ".join(result.notes[:2])
        ),
    )


def run_connectors(client: Any, packet: JobPacket, bootstrap: BootstrapReport | None) -> ConnectorReport:
    report = ConnectorReport()
    boot = bootstrap or BootstrapReport()
    wanted = [c for c in CONNECTOR_ORDER if c in packet.connectors]
    if not wanted:
        report.skipped = True
        report.message = "No connector needles in the brief."
        return report
    for cid in wanted:
        spec = spec_for(cid)
        brands = detected_brands(packet.prompt, cid)
        if cid == "payments":
            step = run_payments(client, packet.prompt)
        elif cid == "inbound_orders":
            step = run_inbound_orders(client, packet.prompt)
        elif cid == "messaging":
            step = run_messaging(client, packet.prompt)
        elif cid == "hardware":
            step = run_hardware(client, boot)
        elif cid == "statutory_payroll":
            step = _payroll_step(packet)
        else:
            step = ProbeResult(name=cid, ok=False, detail="unknown connector")
        if brands and spec:
            step.detail = f"{spec.title} [{', '.join(brands)}]. {step.detail}"
        report.steps.append(step)
        if step.ok:
            report.ran.append(cid)
        elif cid == "statutory_payroll" and not has_pack(packet.country_code):
            report.skipped_ids.append(cid)
            report.warnings.append(step.detail)
        else:
            report.failed.append(cid)
            report.warnings.append(step.detail)
    report.ok = bool(report.steps) and not report.failed
    skipped_bit = f"; skipped {', '.join(report.skipped_ids)}" if report.skipped_ids else ""
    report.message = (
        f"Connectors {', '.join(report.ran) or 'none'} ok; "
        f"failed {', '.join(report.failed) or 'none'}{skipped_bit}."
    )
    return report


__all__ = ["run_connectors"]
