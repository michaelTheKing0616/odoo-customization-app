"""Simple in-process rate limiting for mutating API routes."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.client_ip import client_ip
from app.settings import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window per client IP for POST/PUT/PATCH/DELETE."""

    def __init__(self, app, *, limit: int | None = None, window_s: float | None = None) -> None:
        super().__init__(app)
        self.limit = limit if limit is not None else settings.rate_limit_per_minute
        self.window_s = window_s if window_s is not None else 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_key(self, request: Request) -> str:
        return client_ip(request) or "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.limit <= 0 or request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if request.url.path in {"/health", "/api/auth/status"}:
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window_s:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "error": "rate_limited",
                            "message": f"Too many mutating requests — max {self.limit}/min",
                        }
                    },
                )
            bucket.append(now)

        return await call_next(request)
