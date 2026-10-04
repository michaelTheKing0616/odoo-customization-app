"""XML-RPC adapter. Each send goes through the transport contract.

The contract decides TLS, timeout, concurrency, and write redirects. This
module performs one HTTP POST per attempt and does not request a redirect
target. Application faults are parsed after the contract returns so they
stay ``xmlrpc.client.Fault``.
"""

from __future__ import annotations

import http.client
import ssl
import xml.etree.ElementTree as ET
import xmlrpc.client
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from odoo_client.transport.contract import (
    REDIRECT_STATUSES,
    PreparedCall,
    RedirectHop,
    TransportPolicyError,
    run_send,
)


@dataclass(frozen=True)
class _HttpStatus:
    status: int
    reason: str
    headers: dict[str, str]
    body: bytes


class ContractXmlRpcTransport(xmlrpc.client.Transport):
    """One XML-RPC endpoint. ``request`` is the stdlib hook ``ServerProxy`` calls."""

    def __init__(self, *, scheme: str, database: str) -> None:
        super().__init__()
        self.scheme = scheme
        self.database = database
        self._call_timeout = 120.0
        self.accept_gzip_encoding = False

    def request(self, host: str, handler: str, request_body: bytes, verbose: bool = False) -> Any:
        self.verbose = verbose
        model, method = _rpc_target(request_body)
        url = _absolute(self.scheme, host, handler)

        def send(prepared: PreparedCall) -> RedirectHop | _HttpStatus | bytes:
            return self._exchange(prepared, host, handler, request_body)

        result = run_send(
            send,
            database=self.database,
            model=model,
            method=method,
            url=url,
            verify=True,
        )
        if isinstance(result, RedirectHop):
            raise xmlrpc.client.ProtocolError(
                url,
                result.status,
                "redirect refused",
                {"Location": result.location},
            )
        if isinstance(result, _HttpStatus):
            raise xmlrpc.client.ProtocolError(url, result.status, result.reason, result.headers)
        loaded, _method = xmlrpc.client.loads(result)
        return loaded

    def make_connection(self, host: str) -> http.client.HTTPConnection:
        chost, self._extra_headers, x509 = self.get_host_info(host)
        extra = x509 or {}
        timeout = self._call_timeout
        if self.scheme == "https":
            context = ssl.create_default_context()
            if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
                raise TransportPolicyError("verify=false is refused")
            return http.client.HTTPSConnection(chost, timeout=timeout, context=context, **extra)
        return http.client.HTTPConnection(chost, timeout=timeout)

    def _exchange(
        self,
        prepared: PreparedCall,
        host: str,
        handler: str,
        body: bytes,
    ) -> RedirectHop | _HttpStatus | bytes:
        if prepared.verify is not True:
            raise TransportPolicyError("verify=false is refused")
        self._call_timeout = prepared.timeout
        conn = self.make_connection(host)
        try:
            conn.request(
                "POST",
                handler,
                body,
                {"Content-Type": "text/xml", "User-Agent": self.user_agent},
            )
            resp = conn.getresponse()
            raw = resp.read()
            if resp.status in REDIRECT_STATUSES:
                location = resp.getheader("Location") or ""
                return RedirectHop(resp.status, location)
            if resp.status != 200:
                return _HttpStatus(resp.status, resp.reason or "", dict(resp.getheaders()), raw)
            return raw
        finally:
            conn.close()


def contract_server_proxy(url: str, *, database: str) -> xmlrpc.client.ServerProxy:
    """Server proxy whose HTTP send is the transport contract."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    transport = ContractXmlRpcTransport(scheme=scheme, database=database)
    return xmlrpc.client.ServerProxy(url, transport=transport, allow_none=True)


def _absolute(scheme: str, host: str, handler: str) -> str:
    path = handler if handler.startswith("/") else f"/{handler}"
    return f"{scheme}://{host}{path}"


def _rpc_target(body: bytes | str) -> tuple[str, str]:
    """Return ``(model, method)`` for an XML-RPC body.

    ``execute_kw`` carries the Odoo model and method in the parameter list.
    ``version`` and ``authenticate`` keep the XML-RPC method name. A body that
    cannot be read is treated as a write so a redirect is not followed.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return "object", "execute_kw"
    method_name = (root.findtext("methodName") or "").strip()
    if method_name != "execute_kw":
        return "common", method_name or "execute_kw"
    strings = [value for value in _direct_param_strings(root) if value is not None]
    if len(strings) >= 4:
        return strings[2], strings[3]
    return "object", "execute_kw"


def _direct_param_strings(root: ET.Element) -> list[str | None]:
    params = root.find("params")
    if params is None:
        return []
    found: list[str | None] = []
    for param in params.findall("param"):
        value = param.find("value")
        if value is None:
            found.append(None)
            continue
        string_el = value.find("string")
        if string_el is not None:
            found.append(string_el.text or "")
        else:
            found.append(None)
    return found
