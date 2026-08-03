"""Plan feature registry and workspace entitlement resolution (MON-2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.billing_models import BillingPlan, EntitlementOverride, PlanFeature, ProjectPass, WorkspaceSubscription
from app.db import get_db
from app.db_models import CustomizationProject, OdooConnection
from app.settings import settings
from app.workspace_auth import WorkspaceAuth, get_workspace_auth

FEATURE_KEYS = frozenset(
    {
        "connections_limit",
        "active_projects_limit",
        "designer",
        "automations",
        "approvals",
        "reports_designer",
        "import",
        "ai_draft",
        "module_export",
        "sandbox",
        "snapshots_full",
        "id_generator",
        "bulk_suite",
        "power_ops",
        "health_check",
        "pipelines",
        "expert",
        "audit_export",
        "store_packaging",
        "migration_assist",
        "bulk_security",
        "api_keys",
        "white_label",
        "workspaces_multi",
    }
)

PLAN_SEED: list[dict[str, Any]] = [
    {"id": "free_solo", "display_name": "Free Solo", "sort_order": 0},
    {"id": "pro", "display_name": "Pro", "sort_order": 1},
    {"id": "business", "display_name": "Business", "sort_order": 2},
    {"id": "agency", "display_name": "Agency", "sort_order": 3},
    {"id": "internal", "display_name": "Internal", "sort_order": 99},
    {"id": "project_pass", "display_name": "Project Pass", "sort_order": 10},
]

# feature_key -> plan_id -> value
FEATURE_MATRIX: dict[str, dict[str, str]] = {
    "connections_limit": {
        "free_solo": "1",
        "pro": "5",
        "business": "5",
        "agency": "unlimited",
        "internal": "unlimited",
        "project_pass": "1",
    },
    "active_projects_limit": {
        "free_solo": "1",
        "pro": "3",
        "business": "10",
        "agency": "25",
        "internal": "unlimited",
        "project_pass": "1",
    },
    "designer": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "automations": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "approvals": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "reports_designer": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "import": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "ai_draft": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "module_export": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "sandbox": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "snapshots_full": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "id_generator": {"free_solo": "false", "pro": "true", "business": "true", "agency": "true", "internal": "true", "project_pass": "true"},
    "bulk_suite": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "power_ops": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "health_check": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "pipelines": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "expert": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "audit_export": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "store_packaging": {"free_solo": "false", "pro": "false", "business": "false", "agency": "true", "internal": "true", "project_pass": "false"},
    "migration_assist": {"free_solo": "false", "pro": "false", "business": "false", "agency": "true", "internal": "true", "project_pass": "false"},
    "bulk_security": {"free_solo": "false", "pro": "false", "business": "true", "agency": "true", "internal": "true", "project_pass": "false"},
    "api_keys": {"free_solo": "false", "pro": "false", "business": "false", "agency": "true", "internal": "true", "project_pass": "false"},
    "white_label": {"free_solo": "false", "pro": "false", "business": "false", "agency": "true", "internal": "true", "project_pass": "false"},
    "workspaces_multi": {"free_solo": "false", "pro": "false", "business": "false", "agency": "true", "internal": "true", "project_pass": "false"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed_plan_features(db: Session) -> None:
    for plan in PLAN_SEED:
        if db.get(BillingPlan, plan["id"]) is None:
            db.add(
                BillingPlan(
                    id=plan["id"],
                    display_name=plan["display_name"],
                    sort_order=plan["sort_order"],
                    is_public=plan["id"] not in {"internal", "project_pass"},
                )
            )
    db.flush()
    for feature_key, per_plan in FEATURE_MATRIX.items():
        for plan_id, value in per_plan.items():
            existing = (
                db.query(PlanFeature)
                .filter(PlanFeature.plan_id == plan_id, PlanFeature.feature_key == feature_key)
                .first()
            )
            if existing is None:
                db.add(PlanFeature(plan_id=plan_id, feature_key=feature_key, value=value))
    db.commit()


def ensure_workspace_subscription(db: Session, workspace_id: str) -> WorkspaceSubscription:
    row = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == workspace_id).first()
    if row:
        return row
    ws = db.get(Workspace, workspace_id)
    plan_id = ws.plan if ws and ws.plan in {p["id"] for p in PLAN_SEED} else "free_solo"
    trial_end = None
    status = "active"
    if settings.business_trial_enabled and plan_id == "free_solo":
        plan_id = "business"
        status = "trialing"
        trial_end = _now() + timedelta(days=settings.business_trial_days)
        if ws:
            ws.plan = "business"
            db.add(ws)
    row = WorkspaceSubscription(
        workspace_id=workspace_id,
        plan_id=plan_id,
        status=status,
        trial_ends_at=trial_end,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def plan_feature_diff(db: Session, from_plan: str, to_plan: str) -> list[dict[str, str]]:
    """Features lost when downgrading from_plan → to_plan (for honest downgrade UX)."""
    seed_plan_features(db)
    rows = db.query(PlanFeature).filter(PlanFeature.plan_id.in_([from_plan, to_plan])).all()
    by_plan: dict[str, dict[str, str]] = {from_plan: {}, to_plan: {}}
    for r in rows:
        by_plan.setdefault(r.plan_id, {})[r.feature_key] = r.value
    lost: list[dict[str, str]] = []
    for key in FEATURE_KEYS:
        fv = by_plan.get(from_plan, {}).get(key, "false")
        tv = by_plan.get(to_plan, {}).get(key, "false")
        if _feature_value_rank(fv) > _feature_value_rank(tv):
            lost.append({"feature_key": key, "from": fv, "to": tv})
    return lost


def _feature_value_rank(val: str) -> int:
    if val == "unlimited":
        return 3
    if val == "true":
        return 2
    try:
        return 1 if int(val) > 0 else 0
    except ValueError:
        return 0


def effective_plan_id(sub: WorkspaceSubscription) -> str:
    if sub.status == "canceled":
        return "free_solo"
    if sub.status == "past_due":
        return sub.plan_id  # grace — keep plan during past_due
    return sub.plan_id


@dataclass
class WorkspaceEntitlements:
    workspace_id: str
    plan_id: str
    subscription_status: str
    features: dict[str, str] = field(default_factory=dict)
    extra_project_slots: int = 0
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None

    def feature_enabled(self, key: str) -> bool:
        val = self.features.get(key, "false")
        return val in {"true", "unlimited"}

    def numeric_limit(self, key: str) -> int | None:
        val = self.features.get(key, "0")
        if val == "unlimited":
            return None
        try:
            return int(val)
        except ValueError:
            return 0

    def active_project_slot_limit(self) -> int | None:
        base = self.numeric_limit("active_projects_limit")
        if base is None:
            return None
        return base + self.extra_project_slots


def resolve_entitlements(db: Session, workspace_id: str) -> WorkspaceEntitlements:
    seed_plan_features(db)
    sub = ensure_workspace_subscription(db, workspace_id)
    plan_id = effective_plan_id(sub)

    # Active project pass may elevate build features to pro-level
    now = _now()
    active_pass = (
        db.query(ProjectPass)
        .filter(
            ProjectPass.workspace_id == workspace_id,
            ProjectPass.status == "active",
            ProjectPass.expires_at > now,
        )
        .first()
    )
    if active_pass and plan_id == "free_solo":
        plan_id = "project_pass"

    rows = db.query(PlanFeature).filter(PlanFeature.plan_id == plan_id).all()
    features = {r.feature_key: r.value for r in rows}

    overrides = (
        db.query(EntitlementOverride)
        .filter(
            EntitlementOverride.workspace_id == workspace_id,
            (EntitlementOverride.expires_at.is_(None)) | (EntitlementOverride.expires_at > now),
        )
        .all()
    )
    for ov in overrides:
        features[ov.feature_key] = ov.value

    return WorkspaceEntitlements(
        workspace_id=workspace_id,
        plan_id=plan_id,
        subscription_status=sub.status,
        features=features,
        extra_project_slots=sub.extra_project_slots,
        trial_ends_at=sub.trial_ends_at,
        current_period_end=sub.current_period_end,
    )


def entitlements_bypassed(auth: WorkspaceAuth | None = None) -> bool:
    mode = settings.auth_mode.strip().lower()
    if mode in {"off", ""}:
        return True
    if auth and auth.api_key_authenticated:
        return True
    return False


def require_entitlements_bypass_internal(db: Session, workspace_id: str | None) -> bool:
    if not workspace_id:
        return entitlements_bypassed()
    ent = resolve_entitlements(db, workspace_id)
    return ent.plan_id == "internal" or entitlements_bypassed()


def count_active_projects(db: Session, workspace_id: str) -> int:
    return (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.workspace_id == workspace_id,
            CustomizationProject.lifecycle_status == "active",
        )
        .count()
    )


def count_connections(db: Session, workspace_id: str) -> int:
    return db.query(OdooConnection).filter(OdooConnection.workspace_id == workspace_id).count()


def assert_feature(db: Session, workspace_id: str | None, feature_key: str, auth: WorkspaceAuth | None = None) -> None:
    if entitlements_bypassed(auth) or (workspace_id and require_entitlements_bypass_internal(db, workspace_id)):
        return
    from app.billing_models import FeatureFlag

    flag = db.get(FeatureFlag, feature_key)
    if flag is not None and not flag.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "feature_disabled",
                "feature_key": feature_key,
                "message": "This feature is temporarily disabled.",
            },
        )
    if not workspace_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_gated",
                "feature_key": feature_key,
                "message": "Workspace required for entitlement check.",
                "upgrade_hint": "Sign in to a workspace or upgrade your plan.",
            },
        )
    ent = resolve_entitlements(db, workspace_id)
    if ent.feature_enabled(feature_key):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": "feature_gated",
            "feature_key": feature_key,
            "plan_id": ent.plan_id,
            "message": f"Feature '{feature_key}' is not included in your {ent.plan_id} plan.",
            "upgrade_hint": "Upgrade your plan to unlock this feature.",
        },
    )


def assert_connection_limit(db: Session, workspace_id: str | None, auth: WorkspaceAuth | None = None) -> None:
    if entitlements_bypassed(auth) or (workspace_id and require_entitlements_bypass_internal(db, workspace_id)):
        return
    if not workspace_id:
        return
    ent = resolve_entitlements(db, workspace_id)
    limit = ent.numeric_limit("connections_limit")
    if limit is None:
        return
    current = count_connections(db, workspace_id)
    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_gated",
                "feature_key": "connections_limit",
                "plan_id": ent.plan_id,
                "limit": limit,
                "current": current,
                "upgrade_hint": "Upgrade for more Odoo connections.",
            },
        )


def assert_active_project_slot(
    db: Session,
    workspace_id: str | None,
    *,
    auth: WorkspaceAuth | None = None,
    excluding_project_id: str | None = None,
) -> None:
    """Gate BUILD surfaces only — creating drafts or un-archiving."""
    if entitlements_bypassed(auth) or (workspace_id and require_entitlements_bypass_internal(db, workspace_id)):
        return
    if not workspace_id:
        return
    ent = resolve_entitlements(db, workspace_id)
    limit = ent.active_project_slot_limit()
    if limit is None:
        return
    q = db.query(CustomizationProject).filter(
        CustomizationProject.workspace_id == workspace_id,
        CustomizationProject.lifecycle_status == "active",
    )
    if excluding_project_id:
        q = q.filter(CustomizationProject.id != excluding_project_id)
    current = q.count()
    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_gated",
                "feature_key": "active_projects_limit",
                "plan_id": ent.plan_id,
                "limit": limit,
                "current": current,
                "upgrade_hint": "Archive a project, add an extra slot, or upgrade your plan.",
            },
        )


def require_feature(feature_key: str):
    """FastAPI dependency factory."""

    def _dep(
        request: Request,
        db: Session = Depends(get_db),
        auth: WorkspaceAuth = Depends(get_workspace_auth),
    ) -> None:
        workspace_id = auth.workspace_id if auth.workspace_scoped else None
        assert_feature(db, workspace_id, feature_key, auth)

    return _dep
