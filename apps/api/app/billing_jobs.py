"""Billing maintenance jobs — pass expiry, trial reminders (MON-2)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.billing_models import ProjectPass, WorkspaceSubscription
from app.email_transport import send_email

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def expire_project_passes(db: Session) -> int:
    """Mark expired passes; downgrade is implicit via resolve_entitlements."""
    now = _now()
    rows = (
        db.query(ProjectPass)
        .filter(ProjectPass.status == "active", ProjectPass.expires_at <= now)
        .all()
    )
    for row in rows:
        row.status = "expired"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def send_pass_expiry_reminders(db: Session) -> int:
    """Email workspaces whose pass expires within 7 days."""
    now = _now()
    window_end = now + timedelta(days=7)
    rows = (
        db.query(ProjectPass)
        .filter(
            ProjectPass.status == "active",
            ProjectPass.expires_at > now,
            ProjectPass.expires_at <= window_end,
        )
        .all()
    )
    sent = 0
    for row in rows:
        from app.account_models import WorkspaceMembership, User

        membership = (
            db.query(WorkspaceMembership)
            .filter(WorkspaceMembership.workspace_id == row.workspace_id, WorkspaceMembership.role == "owner")
            .first()
        )
        if not membership:
            continue
        user = db.get(User, membership.user_id)
        if not user:
            continue
        send_email(
            to=user.email,
            subject="Your Project Pass expires soon",
            body=(
                f"Your Project Pass expires on {row.expires_at.date().isoformat()}. "
                "Upgrade to keep full build access on that project."
            ),
        )
        sent += 1
    return sent


def apply_past_due_downgrades(db: Session, *, grace_days: int = 7) -> int:
    """After grace, canceled subscriptions re-gate to free_solo."""
    cutoff = _now() - timedelta(days=grace_days)
    rows = (
        db.query(WorkspaceSubscription)
        .filter(
            WorkspaceSubscription.status == "past_due",
            WorkspaceSubscription.updated_at <= cutoff,
        )
        .all()
    )
    n = 0
    for sub in rows:
        sub.status = "canceled"
        sub.plan_id = "free_solo"
        sub.canceled_at = _now()
        db.add(sub)
        n += 1
    if n:
        db.commit()
    return n


def run_billing_jobs_on_boot(db: Session) -> dict[str, int]:
    expired = expire_project_passes(db)
    reminders = send_pass_expiry_reminders(db)
    downgraded = apply_past_due_downgrades(db)
    if expired or reminders or downgraded:
        logger.info(
            "Billing jobs: expired_passes=%s reminders=%s downgraded=%s",
            expired,
            reminders,
            downgraded,
        )
    return {"expired_passes": expired, "reminders": reminders, "downgraded": downgraded}
