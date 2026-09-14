"""Edge hardware — install stock POS/IoT modules when present; never invent x_kds."""

from __future__ import annotations

from typing import Any

from app.job_autopilot.bootstrap import _install
from app.job_autopilot.connectors import rpcutil
from app.job_autopilot.packet import BootstrapReport, ProbeResult

_HARDWARE_MODULES = ("pos_restaurant", "pos_iot", "iot", "pos_self_order")
_HARDWARE_MODELS = (
    "pos.prep.display",
    "pos.preparation.display",
    "iot.device",
    "pos.config",
)


def run_hardware(client: Any, report: BootstrapReport) -> ProbeResult:
    attempted: list[str] = []
    for name in _HARDWARE_MODULES:
        before_skip = list(report.skipped)
        _install(client, name, report)
        if name in report.installed or name in report.already_installed:
            attempted.append(name)
        elif name in report.skipped and name not in before_skip:
            # Not on addons path — drop from skipped so scorecard is not capped
            report.skipped = [s for s in report.skipped if s != name]
            report.warnings = [
                w for w in report.warnings if f"Could not install {name}" not in w
                and f"Module {name!r} not found" not in w
            ]
    found_models = [m for m in _HARDWARE_MODELS if rpcutil.exists(client, m)]
    if "pos.config" in found_models or attempted:
        return ProbeResult(
            name="hardware",
            ok=True,
            detail=(
                f"modules={attempted or 'none-new'} models={found_models or ['pos.config missing']}. "
                "KDS/IoT Box are hardware — Autopilot installs Community modules when present."
            ),
        )
    return ProbeResult(
        name="hardware",
        ok=False,
        detail="No POS/IoT module on this instance. Install point_of_sale (and pos_restaurant if Community).",
    )
