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
            )
        )
    return out


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
