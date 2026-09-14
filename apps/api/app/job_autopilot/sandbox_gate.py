"""Refuse Autopilot writes on production / observer connections."""

from __future__ import annotations

from app.promote import is_local_docker_connection
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation


class AutopilotRefused(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def classify_connection(row: object) -> tuple[str, bool]:
    """Return (kind, unattended) for a stored connection row.

    kind: sandbox | staging | production | observer
    unattended: True only for sandbox (standard + local Docker URL).
    """
    mode = str(getattr(row, "write_mode", None) or "standard").strip().lower()
    url = str(getattr(row, "url", "") or "")
    if mode == "production":
        return "production", False
    if mode == "observer":
        return "observer", False
    if is_local_docker_connection(url):
        return "sandbox", True
    return "staging", False


def assert_autopilot_run_allowed(
    row: object,
    *,
    confirm_advanced: bool = False,
    confirm_phrase: str | None = None,
) -> str:
    """Raise AutopilotRefused or ConfirmationRequired. Returns connection kind."""
    kind, unattended = classify_connection(row)
    if kind == "production":
        raise AutopilotRefused(
            "Job Autopilot refuses write_mode=production. Clone a sandbox, run Autopilot "
            "there, then Promote with a human confirm."
        )
    if kind == "observer":
        raise AutopilotRefused(
            "Observer connections cannot install modules or apply metadata. "
            "Switch write_mode to standard on a sandbox."
        )
    if unattended:
        return kind
    require_advanced_confirmation(
        confirm_advanced=confirm_advanced,
        confirm_phrase=confirm_phrase,
        warning=(
            "This connection is not a local sandbox. Autopilot will install stock apps, "
            "optionally apply custom residual metadata, and may commit ingest. "
            "Production remains blocked; Promote stays a separate human step."
        ),
        risks=[
            "Installs Community modules on this database",
            "May create warehouse/company records",
            "May apply custom x_* models if the packet has residual",
            "May auto-commit ingest after dry-run only when sandbox; staging still confirmed here",
            "Never auto-promotes to a customer production database",
        ],
    )
    return kind


def is_sandbox_connection(row: object) -> bool:
    kind, unattended = classify_connection(row)
    return kind == "sandbox" and unattended


__all__ = [
    "AutopilotRefused",
    "CONFIRM_PHRASE",
    "ConfirmationRequired",
    "assert_autopilot_run_allowed",
    "classify_connection",
    "is_sandbox_connection",
]
