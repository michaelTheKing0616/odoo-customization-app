"""Phase 7 — app API key auth (Bearer / X-API-Key)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import AppApiKey
from app.settings import settings

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

KEY_PREFIX = "oc_"


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def extract_raw_key(
    credentials: HTTPAuthorizationCredentials | None,
    x_api_key: str | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials.strip()
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    return None


def key_matches_env(raw: str) -> bool:
    expected = (settings.app_api_key or "").strip()
    if not expected:
        return False
    return hmac.compare_digest(raw, expected)


def verify_api_key(db: Session, raw: str) -> AppApiKey | None:
    digest = hash_api_key(raw)
    row = (
        db.query(AppApiKey)
        .filter(AppApiKey.key_hash == digest, AppApiKey.revoked_at.is_(None))
        .first()
    )
    if row:
        row.last_used_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
        return row
    return None


def create_api_key_record(db: Session, *, name: str, raw: str | None = None) -> tuple[AppApiKey, str]:
    plaintext = raw or generate_api_key()
    row = AppApiKey(
        name=name,
        key_prefix=plaintext[:12],
        key_hash=hash_api_key(plaintext),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plaintext


def ensure_env_bootstrap_key(db: Session) -> None:
    """If APP_API_KEY is set, ensure its hash exists so it can be listed/revoked later."""
    raw = (settings.app_api_key or "").strip()
    if not raw:
        return
    digest = hash_api_key(raw)
    existing = db.query(AppApiKey).filter(AppApiKey.key_hash == digest).first()
    if existing:
        return
    create_api_key_record(db, name="env bootstrap", raw=raw)


def count_active_keys(db: Session) -> int:
    return (
        db.query(AppApiKey)
        .filter(AppApiKey.revoked_at.is_(None))
        .count()
    )


async def require_api_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    x_api_key: str | None = Security(_api_key_header),
    db: Session = Depends(get_db),
) -> None:
    """Dependency: enforce API key when auth_mode enables it."""
    if not settings.auth_enabled:
        return

    # Public paths (also skip if router is mounted under /api — health is outside)
    path = request.url.path
    if path in {"/health", "/api/auth/status", "/api/auth/bootstrap"}:
        return

    raw = extract_raw_key(credentials, x_api_key)
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Missing API key. Send Authorization: Bearer <key> or X-API-Key.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if key_matches_env(raw):
        request.state.api_key_prefix = raw[:12]
        return

    row = verify_api_key(db, raw)
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or revoked API key.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.api_key_prefix = row.key_prefix
