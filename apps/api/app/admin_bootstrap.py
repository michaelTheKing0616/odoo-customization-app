"""Superadmin bootstrap from env (MON-3)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.account_models import User, Workspace, WorkspaceMembership
from app.account_service import hash_password, slugify
from app.billing_models import WorkspaceSubscription
from app.settings import settings

logger = logging.getLogger(__name__)


def bootstrap_superadmin_from_env(db: Session) -> bool:
    """Create superadmin + internal workspace when env vars set and none exists."""
    if settings.auth_mode.strip().lower() != "accounts":
        return False

    email = (settings.app_admin_email or "").strip().lower()
    password = (settings.app_admin_password or "").strip()
    if not email or not password:
        return False

    existing = db.query(User).filter(User.is_superadmin.is_(True)).first()
    if existing:
        return False

    user = User(
        email=email,
        password_hash=hash_password(password),
        email_verified=True,
        is_superadmin=True,
    )
    db.add(user)
    db.flush()

    slug_base = slugify(email.split("@")[0] + "-internal")
    ws = Workspace(name="Internal Admin", slug=slug_base, plan="internal")
    db.add(ws)
    db.flush()

    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role="owner"))
    sub = WorkspaceSubscription(workspace_id=ws.id, plan_id="internal", status="active")
    db.add(sub)
    db.commit()
    logger.info("Bootstrapped superadmin account for %s (password from env — not logged)", email)
    return True
