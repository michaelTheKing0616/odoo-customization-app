"""Shared client IP extraction with optional trusted-proxy mode."""

from __future__ import annotations

from starlette.requests import Request

from app.settings import settings


def client_ip(request: Request) -> str | None:
    """
    When trusted_proxy is True, honour the left-most X-Forwarded-For hop
    (set by a reverse proxy you control). Otherwise ignore XFF to prevent spoofing.
    """
    if settings.trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None
