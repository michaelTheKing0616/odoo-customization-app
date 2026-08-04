"""Superadmin admin console API (MON-3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.account_models import User, Workspace
from app.db_models import AuditLog
from app.billing_models import BillingWebhookEvent, EntitlementOverride, WorkspaceSubscription
from app.db import get_db
from app.entitlements import seed_plan_features
from app.workspace_auth import WorkspaceAuth, require_app_auth

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(db: Session, *, method: str, path: str, status_code: int, actor: str, detail: str) -> None:
    db.add(
        AuditLog(
            method=method,
            path=path[:500],
            status_code=status_code,
            client_ip=actor[:64],
            api_key_prefix=(detail[:16] if detail else None),
            duration_ms=0,
        )
    )


def require_superadmin(auth: WorkspaceAuth = Depends(require_app_auth), db: Session = Depends(get_db)) -> User:
    if not auth.user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(User, auth.user_id)
    if user is None or not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin required")
    return user


class UserAdminOut(BaseModel):
    id: str
    email: str
    email_verified: bool
    is_superadmin: bool
    created_at: datetime | None


class WorkspaceAdminOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    subscription_status: str | None
    beta_partner: bool = False
    writes_paused: bool = False


class BetaPartnerBody(BaseModel):
    enabled: bool
    reason: str = Field(..., min_length=1, max_length=500)


class WritesPausedBody(BaseModel):
    paused: bool
    reason: str = Field(..., min_length=1, max_length=500)


class OverrideBody(BaseModel):
    workspace_id: str
    feature_key: str
    value: str
    reason: str = Field(..., min_length=1, max_length=500)
    expires_at: datetime | None = None


class GrantPlanBody(BaseModel):
    workspace_id: str
    plan_id: str
    reason: str = Field(..., min_length=1, max_length=500)


class GrantSlotsBody(BaseModel):
    workspace_id: str
    slots: int = Field(..., ge=1, le=100)
    reason: str = Field(..., min_length=1, max_length=500)


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    q: str = "",
    _admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> list[UserAdminOut]:
    query = db.query(User)
    if q.strip():
        query = query.filter(User.email.ilike(f"%{q.strip()}%"))
    rows = query.order_by(User.created_at.desc()).limit(200).all()
    return [
        UserAdminOut(
            id=r.id,
            email=r.email,
            email_verified=r.email_verified,
            is_superadmin=r.is_superadmin,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/users/{user_id}/verify", status_code=204)
def verify_user(
    user_id: str,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    db.add(user)
    _audit(db, method="POST", path=f"/api/admin/users/{user_id}/verify", status_code=204, actor=admin.email, detail="admin verify user")
    db.commit()


@router.get("/workspaces", response_model=list[WorkspaceAdminOut])
def list_workspaces(
    _admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> list[WorkspaceAdminOut]:
    rows = db.query(Workspace).order_by(Workspace.created_at.desc()).limit(200).all()
    out = []
    for ws in rows:
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws.id).first()
        out.append(
            WorkspaceAdminOut(
                id=ws.id,
                name=ws.name,
                slug=ws.slug,
                plan=ws.plan,
                subscription_status=sub.status if sub else None,
                beta_partner=bool(getattr(ws, "beta_partner", False)),
                writes_paused=bool(getattr(ws, "writes_paused", False)),
            )
        )
    return out


@router.patch("/workspaces/{workspace_id}/beta-partner", response_model=WorkspaceAdminOut)
def set_beta_partner(
    workspace_id: str,
    body: BetaPartnerBody,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> WorkspaceAdminOut:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.beta_partner = body.enabled
    db.add(ws)
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws.id).first()
    _audit(
        db,
        method="PATCH",
        path=f"/api/admin/workspaces/{workspace_id}/beta-partner",
        status_code=200,
        actor=admin.email,
        detail=f"beta_partner={body.enabled}: {body.reason[:80]}",
    )
    db.commit()
    return WorkspaceAdminOut(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        plan=ws.plan,
        subscription_status=sub.status if sub else None,
        beta_partner=bool(ws.beta_partner),
        writes_paused=bool(ws.writes_paused),
    )


@router.patch("/workspaces/{workspace_id}/writes-paused", response_model=WorkspaceAdminOut)
def set_writes_paused(
    workspace_id: str,
    body: WritesPausedBody,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> WorkspaceAdminOut:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.writes_paused = body.paused
    db.add(ws)
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws.id).first()
    _audit(
        db,
        method="PATCH",
        path=f"/api/admin/workspaces/{workspace_id}/writes-paused",
        status_code=200,
        actor=admin.email,
        detail=f"writes_paused={body.paused}: {body.reason[:80]}",
    )
    db.commit()
    return WorkspaceAdminOut(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        plan=ws.plan,
        subscription_status=sub.status if sub else None,
        beta_partner=bool(ws.beta_partner),
        writes_paused=bool(ws.writes_paused),
    )


@router.get("/trust-telemetry")
def trust_telemetry(
    _admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    from app.beta_telemetry import ga_evidence_summary

    return ga_evidence_summary(db)


@router.get("/ga-criteria")
def ga_criteria(_admin: User = Depends(require_superadmin)) -> dict:
    from app.settings import settings

    return {
        "beta_production_gating_enabled": settings.beta_production_gating_enabled,
        "production_write_mode_ga_unlocked": settings.production_write_mode_ga_unlocked,
        "min_beta_partner_workspaces": settings.beta_ga_min_workspaces,
        "min_weeks_per_workspace": settings.beta_ga_min_weeks,
        "exit_criteria": [
            f">= {settings.beta_ga_min_workspaces} beta_partner workspaces",
            f">= {settings.beta_ga_min_weeks} calendar weeks of active use each",
            "Zero unrecoverable-data incidents (operator-attested)",
            "Zero SafetyGate bypasses (route meta-test + audit review)",
        ],
        "launch_env": "Set PRODUCTION_WRITE_MODE_GA_UNLOCKED=1 to open production mode globally",
        "runbook": "docs/BETA_PROTOCOL.md",
    }


@router.post("/overrides", status_code=201)
def grant_override(
    body: OverrideBody,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    seed_plan_features(db)
    row = EntitlementOverride(
        workspace_id=body.workspace_id,
        feature_key=body.feature_key,
        value=body.value,
        reason=body.reason,
        expires_at=body.expires_at,
    )
    db.add(row)
    _audit(db, method="POST", path="/api/admin/overrides", status_code=201, actor=admin.email, detail=f"override {body.feature_key}={body.value}")
    db.commit()
    return {"id": row.id}


@router.post("/grant-plan")
def grant_plan(
    body: GrantPlanBody,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ws = db.get(Workspace, body.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.plan = body.plan_id
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws.id).first()
    if sub is None:
        sub = WorkspaceSubscription(workspace_id=ws.id, plan_id=body.plan_id, status="active")
        db.add(sub)
    else:
        sub.plan_id = body.plan_id
        sub.status = "active"
        db.add(sub)
    db.add(ws)
    _audit(db, method="POST", path="/api/admin/grant-plan", status_code=200, actor=admin.email, detail=f"grant {body.plan_id}")
    db.commit()
    return {"workspace_id": ws.id, "plan_id": body.plan_id}


@router.post("/grant-slots")
def grant_slots(
    body: GrantSlotsBody,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    from app.entitlements import grant_extra_project_slots

    ws = db.get(Workspace, body.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    sub = grant_extra_project_slots(db, body.workspace_id, body.slots)
    _audit(
        db,
        method="POST",
        path="/api/admin/grant-slots",
        status_code=200,
        actor=admin.email,
        detail=f"+{body.slots} slots: {body.reason[:80]}",
    )
    db.commit()
    return {"workspace_id": ws.id, "extra_project_slots": sub.extra_project_slots}


@router.post("/users/{user_id}/deactivate", status_code=204)
def deactivate_user(
    user_id: str,
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = False
    user.locked_until = datetime(2099, 1, 1, tzinfo=timezone.utc)
    db.add(user)
    _audit(db, method="POST", path=f"/api/admin/users/{user_id}/deactivate", status_code=204, actor=admin.email, detail="deactivate")
    db.commit()


@router.get("/feature-flags")
def list_feature_flags(_admin: User = Depends(require_superadmin), db: Session = Depends(get_db)) -> list[dict]:
    from app.billing_models import FeatureFlag

    rows = db.query(FeatureFlag).order_by(FeatureFlag.key).all()
    return [{"key": r.key, "enabled": r.enabled} for r in rows]


@router.put("/feature-flags/{key}")
def set_feature_flag(
    key: str,
    body: dict[str, bool],
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    from app.billing_models import FeatureFlag

    row = db.get(FeatureFlag, key)
    enabled = bool(body.get("enabled", True))
    if row is None:
        row = FeatureFlag(key=key, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
        db.add(row)
    _audit(db, method="PUT", path=f"/api/admin/feature-flags/{key}", status_code=200, actor=admin.email, detail=str(enabled))
    db.commit()
    return {"key": key, "enabled": str(enabled)}


@router.get("/billing-events")
def billing_events(
    _admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.query(BillingWebhookEvent).order_by(BillingWebhookEvent.processed_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "processor": r.processor,
            "event_id": r.event_id,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]


@router.get("/revenue-snapshot")
def revenue_snapshot(
    _admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    """Computed MRR estimate from subscription rows — no external API calls."""
    subs = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.status.in_(["active", "trialing", "past_due"])).all()
    by_plan: dict[str, int] = {}
    for s in subs:
        by_plan[s.plan_id] = by_plan.get(s.plan_id, 0) + 1
    # Placeholder MRR table — real prices live in processors
    mrr_cents = {
        "pro": 3900,
        "business": 14900,
        "agency": 39900,
    }
    total = sum(by_plan.get(p, 0) * mrr_cents.get(p, 0) for p in by_plan)
    return {"by_plan": by_plan, "estimated_mrr_cents": total, "computed_at": datetime.now(timezone.utc).isoformat()}
