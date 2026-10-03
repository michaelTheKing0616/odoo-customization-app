"""Odoo 19+ External JSON-2 HTTP transport (``POST /json/2/<model>/<method>``).

Does not replace XML-RPC for majors ≤18. Callers go through ``OdooClient``;
this module only speaks HTTP + Bearer API keys.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body

logger = logging.getLogger(__name__)


class Json2TransportError(Exception):
    """JSON-2 HTTP or application error — full body preserved on ``.body``."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: Any = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url


class Json2Transport:
    """Stateless External JSON-2 client for one base URL + API key."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        database: str | None = None,
        send_db_header: bool = False,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.database = database
        self.send_db_header = send_db_header
        self.timeout = timeout

    def call(self, model: str, method: str, body: dict[str, Any] | None = None) -> Any:
        """POST ``/json/2/<model>/<method>`` with a named JSON body."""
        path = f"json/2/{model}/{method}"
        url = urljoin(self.base_url + "/", path)
        payload = json.dumps(body or {}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.send_db_header and self.database:
            headers["X-Odoo-Database"] = self.database
        req = Request(url, data=payload, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                status = getattr(resp, "status", 200) or 200
        except HTTPError as exc:
            err_raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            parsed: Any
            try:
                parsed = json.loads(err_raw) if err_raw else {"message": exc.reason}
            except json.JSONDecodeError:
                parsed = {"message": err_raw or str(exc.reason)}
            logger.error(
                "JSON-2 HTTP %s at %s body=%s",
                exc.code,
                url,
                err_raw[:4000],
            )
            raise Json2TransportError(
                _format_error_message(parsed, fallback=str(exc.reason)),
                status=exc.code,
                body=parsed,
                url=url,
            ) from exc
        except URLError as exc:
            raise Json2TransportError(
                f"JSON-2 connection failed at {url}: {exc}",
                status=None,
                body=None,
                url=url,
            ) from exc

        if not raw:
            return None
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Json2TransportError(
                f"JSON-2 non-JSON 200 body at {url}: {raw[:500]}",
                status=status,
                body=raw,
                url=url,
            ) from exc
        return result

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        body = execute_kw_to_json2_body(method, args, kwargs)
        return self.call(model, method, body)

    def context_get(self) -> dict[str, Any]:
        """Resolve the API key to a user context (replaces common.authenticate)."""
        raw = self.call("res.users", "context_get", {})
        if not isinstance(raw, dict):
            raise Json2TransportError(
                f"context_get returned non-dict: {raw!r}",
                status=200,
                body=raw,
            )
        return raw


def _format_error_message(body: Any, *, fallback: str) -> str:
    if isinstance(body, dict):
        parts = [
            str(body.get("name") or ""),
            str(body.get("message") or fallback),
        ]
        args = body.get("arguments")
        if args:
            parts.append(f"arguments={args!r}")
        return " | ".join(p for p in parts if p)
    return fallback
