"""Connection write-mode helpers (TRUST-1)."""

from __future__ import annotations

from app.account_service import AccountError

VALID_WRITE_MODES = frozenset({"observer", "standard", "production"})


def normalize_write_mode(value: str) -> str:
    mode = value.strip().lower()
    if mode not in VALID_WRITE_MODES:
        raise AccountError(
            "invalid_write_mode",
            "write_mode must be observer, standard, or production.",
            400,
        )
    return mode


def can_unlock_production(*, readiness_passed: bool = False) -> bool:
    """Production unlock requires TRUST-8 production readiness checklist."""
    return readiness_passed
