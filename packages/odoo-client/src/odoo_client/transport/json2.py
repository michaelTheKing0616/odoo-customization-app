"""Odoo 19+ External JSON-2 HTTP transport (``POST /json/2/<model>/<method>``).

Does not replace XML-RPC for majors ≤18. Callers go through ``OdooClient``;
this module only speaks HTTP + Bearer API keys.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
    urlopen,
)

from odoo_client.compat.read_group import resolve_aggregate_rpc_method
from odoo_client.rpc_transport_errors import OdooRpcError
from odoo_client.transport.contract import (
    REDIRECT_STATUSES,
    PreparedCall,
    RedirectHop,
    TransportPolicyError,
    run_send,
)
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


class _RedirectRefused(Exception):
    """The opener saw a redirect and did not request the next URL."""

    def __init__(self, status: int, location: str) -> None:
        self.status = status
        self.location = location
        super().__init__(location)


class _RefuseRedirect(HTTPRedirectHandler):
    """Surface the redirect and do not call ``parent.open`` on the next URL."""

    def http_error_302(self, req: Request, fp: Any, code: int, msg: str, headers: Any) -> None:
        location = ""
        if headers is not None:
            location = headers.get("location") or headers.get("uri") or ""
        try:
            fp.read()
        finally:
            fp.close()
        raise _RedirectRefused(int(code), str(location))

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _verifying_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise TransportPolicyError("verify=false is refused")
    return context


def open_http(req: Request, timeout: float, *, allow_redirects: bool) -> Any:
    """Open one request. A write passes ``allow_redirects=False`` and stops on 3xx."""
    scheme = urlparse(req.full_url).scheme
    context = _verifying_context() if scheme == "https" else None
    if allow_redirects:
        if context is None:
            return urlopen(req, timeout=timeout)
        return urlopen(req, timeout=timeout, context=context)
    handlers: list[Any] = [_RefuseRedirect()]
    if context is not None:
        handlers.append(HTTPSHandler(context=context))
    opener = build_opener(*handlers)
    try:
        return opener.open(req, timeout=timeout)
    except _RedirectRefused as exc:
        return RedirectHop(exc.status, exc.location)


def _redirect_from_response(resp: Any) -> RedirectHop | None:
    status = getattr(resp, "status", None)
    if status is None:
        status = getattr(resp, "code", None)
    if status not in REDIRECT_STATUSES:
        return None
    headers = getattr(resp, "headers", None)
    location = ""
    if headers is not None and hasattr(headers, "get"):
        location = headers.get("Location") or headers.get("location") or ""
    if not location and hasattr(resp, "getheader"):
        location = resp.getheader("Location") or ""
    return RedirectHop(int(status), str(location))


def _rpc_names(http_method: str, path: str, model: str | None, method: str | None) -> tuple[str, str]:
    if method:
        return model or "res.users", method
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) >= 4 and parts[0] == "json" and parts[1] == "2":
        return parts[2], parts[3]
    # A GET such as ``/doc`` is an idempotent read. The contract classifies
    # timeouts by RPC method name, so this uses a read-plane method.
    if http_method.upper() == "GET":
        return "ir.model", "fields_get"
    return "ir.model", "execute"


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

    def _database_key(self) -> str:
        if isinstance(self.database, str) and self.database.strip():
            return self.database.strip()
        return urlparse(self.base_url).hostname or "sandbox"

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        rpc_model: str | None = None,
        rpc_method: str | None = None,
    ) -> tuple[int, str]:
        """HTTP request that returns ``(status, text)`` for error responses too.

        The bytes go out through the transport contract. A non-local host must
        be HTTPS. A write does not follow a redirect.
        """
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json, text/html"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.send_db_header and self.database:
            headers["X-Odoo-Database"] = self.database
        req = Request(url, data=data, headers=headers, method=method)
        model_name, rpc_name = _rpc_names(method, path, rpc_model, rpc_method)

        def send(prepared: PreparedCall) -> tuple[int, str] | RedirectHop:
            return self._read_response(req, prepared)

        try:
            result = run_send(
                send,
                database=self._database_key(),
                model=model_name,
                method=rpc_name,
                url=url,
                verify=True,
            )
        except TransportPolicyError:
            raise
        except OdooRpcError as exc:
            raise Json2TransportError(
                f"JSON-2 connection failed at {url}: {exc}",
                status=None,
                body=None,
                url=url,
                error_class="transport",
            ) from exc
        if isinstance(result, RedirectHop):
            raise Json2TransportError(
                f"JSON-2 redirect refused ({result.status})",
                status=result.status,
                body={"location": result.location},
                url=url,
                error_class="transport",
            )
        status, raw = result
        if status >= 400:
            logger.error(
                "JSON-2 HTTP %s at %s body=%s",
                status,
                url,
                self._redact(raw[:500]),
            )
        return status, raw

    def _read_response(self, req: Request, prepared: PreparedCall) -> tuple[int, str] | RedirectHop:
        try:
            opened = open_http(
                req,
                timeout=prepared.timeout,
                allow_redirects=prepared.allow_redirects,
            )
        except HTTPError as exc:
            err_raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return int(exc.code), err_raw
        if isinstance(opened, RedirectHop):
            return opened
        with opened as resp:
            hop = _redirect_from_response(resp)
            if hop is not None:
                return hop
            raw = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200) or 200
            return int(status), raw

    def call(self, model: str, method: str, body: dict[str, Any] | None = None) -> Any:
        """POST ``/json/2/<model>/<method>`` with a named JSON body."""
        path = f"json/2/{model}/{method}"
        url = urljoin(self.base_url + "/", path)
        status, raw = self.request("POST", path, body, rpc_model=model, rpc_method=method)
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
        method = resolve_aggregate_rpc_method(method, self.odoo_major)
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
