"""Odoo 19+ External JSON-2 HTTP transport (``POST /json/2/<model>/<method>``).

Does not replace XML-RPC for majors ≤18. Callers go through ``OdooClient``;
this module only speaks HTTP + Bearer API keys.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body

logger = logging.getLogger(__name__)


class Json2TransportError(Exception):
    """JSON-2 HTTP or application error — full body preserved on ``.body``.

    ``error_class`` is ``auth``, ``caller``, ``server``, or ``transport``.
    Caller and auth errors are not retryable. A 500 whose body is a
    ``TypeError`` or ``Domain()`` fault is a caller error.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: Any = None,
        url: str | None = None,
        error_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url
        self.error_class = error_class or classify_json2_error(status, body)


def json2_origin(url: str) -> str:
    """JSON-2 is mounted at the host root. A pasted ``/odoo`` or ``/web`` path is the web client."""
    raw = (url or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    path = parsed.path.rstrip("/")
    if path in {"/odoo", "/web"}:
        path = ""
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def classify_json2_error(status: int | None, body: Any) -> str:
    """Group a JSON-2 failure so production hosts can be handled the same way."""
    if status is None:
        return "transport"
    if status in {401, 403}:
        return "auth"
    if status in {400, 404, 422}:
        return "caller"
    if status == 500 and _caller_fault(body):
        return "caller"
    if status >= 500:
        return "server"
    return "caller"


def is_retryable_json2(exc: Json2TransportError) -> bool:
    """Reads may retry server and transport failures. Caller and auth errors must not."""
    return exc.error_class in {"server", "transport"}


def _caller_fault(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    name = str(body.get("name") or "")
    message = str(body.get("message") or "")
    if name in {"builtins.TypeError", "builtins.ValueError"}:
        return True
    return message.startswith("Domain()") or "invalid argument type for domain" in message


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
        odoo_major: int = 19,
    ) -> None:
        self.base_url = json2_origin(base_url)
        self.api_key = api_key
        self.database = database
        self.send_db_header = send_db_header
        self.timeout = timeout
        self.odoo_major = odoo_major

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, str]:
        """HTTP request that returns ``(status, text)`` for error responses too."""
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json, text/html"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.send_db_header and self.database:
            headers["X-Odoo-Database"] = self.database
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200) or 200
                return int(status), raw
        except HTTPError as exc:
            err_raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error(
                "JSON-2 HTTP %s at %s body=%s",
                exc.code,
                url,
                self._redact(err_raw[:500]),
            )
            return int(exc.code), err_raw
        except URLError as exc:
            raise Json2TransportError(
                f"JSON-2 connection failed at {url}: {exc}",
                status=None,
                body=None,
                url=url,
                error_class="transport",
            ) from exc

    def call(self, model: str, method: str, body: dict[str, Any] | None = None) -> Any:
        """POST ``/json/2/<model>/<method>`` with a named JSON body."""
        path = f"json/2/{model}/{method}"
        url = urljoin(self.base_url + "/", path)
        status, raw = self.request("POST", path, body)
        if status >= 400:
            parsed: Any
            try:
                parsed = json.loads(raw) if raw else {"message": ""}
            except json.JSONDecodeError:
                parsed = {"message": raw}
            raise Json2TransportError(
                _format_error_message(parsed, fallback=raw or str(status)),
                status=status,
                body=parsed,
                url=url,
            )
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Json2TransportError(
                f"JSON-2 non-JSON 200 body at {url}: {self._redact(raw[:500])}",
                status=status,
                body=self._redact(raw[:500]),
                url=url,
                error_class="server",
            ) from exc

    def _redact(self, text: str) -> str:
        if self.api_key:
            return text.replace(self.api_key, "[redacted]")
        return text

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        body = execute_kw_to_json2_body(method, args, kwargs, major=self.odoo_major)
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
