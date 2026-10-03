"""Refuse JSON live writes that carry dry_run false until the same body was previewed."""

from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.dry_run_ledger import dry_run_was_seen, remember_dry_run

_SKIP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _tool_name(scope: Scope) -> str:
    path = scope.get("path") or ""
    method = scope.get("method") or ""
    return f"{method}:{path}"


class DryRunHashMiddleware:
    """ASGI middleware so the JSON body can be replayed to the route."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in _SKIP_METHODS:
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers") or []
        }
        if "application/json" not in headers.get("content-type", ""):
            await self.app(scope, receive, send)
            return

        body = b""
        messages: list[Message] = []
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        payload: Any
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = None

        reject = False
        if isinstance(payload, dict) and "dry_run" in payload:
            tool = _tool_name(scope)
            if payload.get("dry_run") is True:
                remember_dry_run(tool, payload)
            elif not dry_run_was_seen(tool, payload):
                reject = True

        if reject:
            raw = json.dumps(
                {
                    "detail": {
                        "error": "dry_run_receipt_required",
                        "message": "Run the same request with dry_run true before a live write.",
                        "options": ["POST with dry_run=true, then retry with the same parameters"],
                    }
                }
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(raw)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": raw})
            return

        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return {"type": "http.disconnect"}

        await self.app(scope, replay, send)
