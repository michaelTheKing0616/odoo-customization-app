"""Refuse live writes until the same body was previewed.

JSON bodies that include ``dry_run: false`` are refused until that body was seen
with ``dry_run: true``. Write-capable T1 tools are also refused when the key is
omitted. A ``dry_run: true`` on those tools is stored and is not executed.
"""

from __future__ import annotations

import json
import re
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.dry_run_ledger import dry_run_was_seen, remember_dry_run

_SKIP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Odoo writes in T1 that do not carry their own dry-run handler.
# T3 bridge validate and queue enqueue, and T4 dashboard / offline / skills,
# are not in this list: they are not customer Odoo writes. The inventory
# comment lives in tests/test_dry_run_ledger.py.
GATED_ROUTE_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/ai/sessions/{session_id}/apply"),
    ("POST", "/api/ai/sessions/{session_id}/install-apps"),
    ("POST", "/api/ai/sessions/{session_id}/stock-app"),
    ("POST", "/api/connections/{connection_id}/module-spec/apply"),
    ("POST", "/api/connections/{connection_id}/module-spec/seed-walkthrough"),
    ("POST", "/api/connections/{connection_id}/modules/install-community"),
    ("POST", "/api/connections/{connection_id}/modules/promote"),
    ("POST", "/api/connections/{connection_id}/modules/uninstall"),
)


def _compile(template: str) -> re.Pattern[str]:
    pieces: list[str] = []
    for piece in template.split("/"):
        if piece.startswith("{") and piece.endswith("}") and len(piece) > 2:
            pieces.append("[^/]+")
        else:
            pieces.append(re.escape(piece))
    return re.compile("^" + "/".join(pieces) + "$")


_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (method, _compile(template)) for method, template in GATED_ROUTE_TEMPLATES
)


def is_write_capable(method: str | None, path: str | None) -> bool:
    method_name = (method or "").upper()
    path_name = path or ""
    return any(routed == method_name and pattern.match(path_name) for routed, pattern in _COMPILED)


def _tool_name(scope: Scope) -> str:
    path = scope.get("path") or ""
    method = scope.get("method") or ""
    return f"{method}:{path}"


def _json_response(status: int, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = json.dumps(payload).encode("utf-8")
    start = {
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(raw)).encode("ascii")),
        ],
    }
    body = {"type": "http.response.body", "body": raw}
    return start, body


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
        if "json" not in headers.get("content-type", "").lower():
            # A gated Odoo write must not slip past the preview rule by sending form data,
            # plain text or no content type at all: it needs the same receipt as JSON.
            if is_write_capable(scope.get("method"), scope.get("path")) and _action(scope, None) == "reject":
                start, response_body = _json_response(403, {"detail": {
                    "error": "dry_run_receipt_required",
                    "message": "Run the same request with dry_run true before a live write.",
                    "options": ["POST JSON with dry_run=true, then retry with the same parameters"],
                }})
                await send(start)
                await send(response_body)
                return
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

        action = _action(scope, payload)
        if action == "reject":
            start, response_body = _json_response(
                403,
                {
                    "detail": {
                        "error": "dry_run_receipt_required",
                        "message": "Run the same request with dry_run true before a live write.",
                        "options": ["POST with dry_run=true, then retry with the same parameters"],
                    }
                },
            )
            await send(start)
            await send(response_body)
            return
        if action == "preview":
            start, response_body = _json_response(200, {"ok": True, "dry_run": True})
            await send(start)
            await send(response_body)
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


def _is_stock_app_decline(scope: Scope, payload: Any) -> bool:
    """True when this body only stops the stock-app confirm. Not an Odoo write."""
    if not isinstance(payload, dict) or payload.get("decision") != "decline":
        return False
    method_name = (scope.get("method") or "").upper()
    path_name = scope.get("path") or ""
    for (routed, template), (_, pattern) in zip(GATED_ROUTE_TEMPLATES, _COMPILED, strict=True):
        if routed == "POST" and template.endswith("/stock-app"):
            return method_name == routed and pattern.match(path_name) is not None
    return False


def _action(scope: Scope, payload: Any) -> str:
    """Return ``reject``, ``preview``, or ``pass``.

    ``preview`` stores the hash and does not call the route. Used for gated
    tools whose handlers would otherwise perform the Odoo write.

    Stock-app ``decision=decline`` returns ``pass`` with no stored preview.
    ``install`` and every other body on that route stay behind the receipt.
    """
    if _is_stock_app_decline(scope, payload):
        return "pass"
    tool = _tool_name(scope)
    gated = is_write_capable(scope.get("method"), scope.get("path"))
    if isinstance(payload, dict) and payload.get("dry_run") is True:
        remember_dry_run(tool, payload)
        if gated:
            return "preview"
        return "pass"
    if isinstance(payload, dict) and "dry_run" in payload:
        if not dry_run_was_seen(tool, payload):
            return "reject"
        return "pass"
    if gated:
        args = payload if isinstance(payload, dict) else {}
        if not dry_run_was_seen(tool, args):
            return "reject"
    return "pass"
