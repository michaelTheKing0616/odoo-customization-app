"""TRUST-9 — design-partner beta gating for production write mode."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db_models import OdooConnection
from app.production_readiness import production_readiness_passed
from app.settings import settings


def production_write_mode_allowed(db: Session, connection: OdooConnection) -> tuple[bool, str | None]:
    """Return (allowed, error_code) for production write mode beyond readiness checklist."""
    if not settings.beta_production_gating_enabled:
        return True, None
    if settings.production_write_mode_ga_unlocked:
        return True, None
    if not connection.workspace_id:
        return False, "beta_partner_required"
    ws = db.get(Workspace, connection.workspace_id)
    if ws is None or not getattr(ws, "beta_partner", False):
        return False, "beta_partner_required"
    return True, None


def can_unlock_production_write_mode(db: Session, connection: OdooConnection) -> tuple[bool, str | None]:
    """Full gate: TRUST-8 readiness + TRUST-9 beta partner (unless GA unlocked)."""
    if not production_readiness_passed(db, connection):
        return False, "production_readiness_required"
    allowed, code = production_write_mode_allowed(db, connection)
    if not allowed:
        return False, code or "beta_partner_required"
    return True, None
