"""Auth status, bootstrap, and API key management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    count_active_keys,
    create_api_key_record,
    ensure_env_bootstrap_key,
    require_api_auth,
)
from app.db import get_db
from app.db_models import AppApiKey
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusOut(BaseModel):
    auth_mode: str
    auth_enabled: bool
    active_keys: int
    env_key_configured: bool
    bootstrap_available: bool


class BootstrapOut(BaseModel):
    api_key: str
    key_id: str
    name: str
    note: str


class CreateKeyBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class CreateKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    api_key: str
    note: str = "Store this key now — it will not be shown again."


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/status", response_model=AuthStatusOut)
def auth_status(db: Session = Depends(get_db)) -> AuthStatusOut:
    if settings.auth_enabled and settings.app_api_key:
        ensure_env_bootstrap_key(db)
    active = count_active_keys(db)
    env_set = bool((settings.app_api_key or "").strip())
    return AuthStatusOut(
        auth_mode=settings.auth_mode,
        auth_enabled=settings.auth_enabled,
        active_keys=active,
        env_key_configured=env_set,
        bootstrap_available=settings.auth_enabled and active == 0 and not env_set,
    )


@router.post("/bootstrap", response_model=BootstrapOut)
def bootstrap_first_key(db: Session = Depends(get_db)) -> BootstrapOut:
    """Create the first API key when auth is on and no keys / env key exist yet."""
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=400,
            detail="Auth is off (AUTH_MODE=off). Set AUTH_MODE=api_key to enable.",
        )
    if (settings.app_api_key or "").strip():
        ensure_env_bootstrap_key(db)
        raise HTTPException(
            status_code=400,
            detail="APP_API_KEY is already configured in the environment — use that key.",
        )
    if count_active_keys(db) > 0:
        raise HTTPException(
            status_code=409,
            detail="Keys already exist — bootstrap is only for the first key.",
        )
    row, plaintext = create_api_key_record(db, name="bootstrap")
    return BootstrapOut(
        api_key=plaintext,
        key_id=row.id,
        name=row.name,
        note="Store this key now — it will not be shown again.",
    )


@router.get("/keys", response_model=list[ApiKeyOut], dependencies=[Depends(require_api_auth)])
def list_keys(db: Session = Depends(get_db)) -> list[ApiKeyOut]:
    rows = db.query(AppApiKey).order_by(AppApiKey.created_at.desc()).limit(100).all()
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.post("/keys", response_model=CreateKeyOut, dependencies=[Depends(require_api_auth)])
def create_key(body: CreateKeyBody, db: Session = Depends(get_db)) -> CreateKeyOut:
    row, plaintext = create_api_key_record(db, name=body.name)
    return CreateKeyOut(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        api_key=plaintext,
    )


@router.delete("/keys/{key_id}", status_code=204, dependencies=[Depends(require_api_auth)])
def revoke_key(key_id: str, db: Session = Depends(get_db)) -> None:
    row = db.get(AppApiKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
