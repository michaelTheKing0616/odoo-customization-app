"""Audit log for mutating API requests."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.client_ip import client_ip
from app.db import SessionLocal
from app.db_models import AuditLog
from app.settings import settings

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Persist one row per mutating request (POST/PUT/PATCH/DELETE)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.audit_log_enabled:
            return await call_next(request)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if request.url.path in {"/health", "/api/auth/status"}:
            return await call_next(request)

        started = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            try:
                db = SessionLocal()
                try:
                    detail = getattr(request.state, "audit_detail", None)
                    detail_json = None
                    if detail is not None:
                        import json

                        detail_json = json.dumps(detail, default=str)[:50000]
                    row = AuditLog(
                        method=request.method,
                        path=request.url.path[:500],
                        status_code=status_code,
                        client_ip=client_ip(request),
                        api_key_prefix=getattr(request.state, "api_key_prefix", None),
                        duration_ms=duration_ms,
                        detail_json=detail_json,
                    )
                    db.add(row)
                    db.commit()
                finally:
                    db.close()
            except Exception:  # noqa: BLE001
                logger.exception("failed to write audit log")
