"""XML-RPC adapter through the transport contract. No socket is opened."""

from __future__ import annotations

import ssl
import xmlrpc.client
from typing import Any, ClassVar

import pytest
from odoo_client.transport.contract import TransportPolicyError, WritePlaneRedirectError
from odoo_client.transport.xmlrpc_adapter import contract_server_proxy


class _Response:
    def __init__(self, status: int, body: bytes, *, location: str = "") -> None:
        self.status = status
        self.reason = "OK" if status == 200 else "Found"
        self._body = body
        self._location = location

    def read(self) -> bytes:
        return self._body

    def getheader(self, name: str, default: str | None = None) -> str | None:
        if name.lower() == "location":
            return self._location or default
        return default

    def getheaders(self) -> list[tuple[str, str]]:
        if self._location:
            return [("Location", self._location)]
        return []


class _Connection:
    instances: ClassVar[list[_Connection]] = []

    def __init__(
        self,
        host: str,
        timeout: float | None = None,
        context: ssl.SSLContext | None = None,
        **kwargs: Any,
    ) -> None:
        self.host = host
        self.timeout = timeout
        self.context = context
        self.kwargs = kwargs
        self.handlers: list[str] = []
        self.response = _Response(200, b"")
        _Connection.instances.append(self)

    def request(self, method: str, handler: str, body: bytes, headers: dict[str, str]) -> None:
        self.handlers.append(handler)
        self.method = method
        self.body = body
        self.headers = headers

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        return None


def _patch_connections(monkeypatch: pytest.MonkeyPatch, *, https: bool) -> None:
    _Connection.instances = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("unexpected connection")

    if https:
        monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPSConnection", _Connection)
        monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPConnection", refuse)
    else:
        monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPConnection", _Connection)
        monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPSConnection", refuse)


def _ok(value: Any) -> bytes:
    return xmlrpc.client.dumps((value,), methodresponse=True).encode()


def _answer(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    original = _Connection.request

    def request_with_body(self: _Connection, method: str, handler: str, payload: bytes, headers: dict[str, str]) -> None:
        original(self, method, handler, payload, headers)
        self.response = _Response(200, body)

    monkeypatch.setattr(_Connection, "request", request_with_body)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8069/xmlrpc/2/object",
        "http://localhost:8069/xmlrpc/2/object",
    ],
)
def test_xmlrpc_local_http_sandbox_sends(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    _patch_connections(monkeypatch, https=False)
    _answer(monkeypatch, _ok([{"id": 1}]))
    proxy = contract_server_proxy(url, database="sandbox")
    result = proxy.execute_kw("sandbox", 1, "pw", "sale.order", "search_read", [[]], {"fields": ["id"]})
    assert result == [{"id": 1}]
    assert len(_Connection.instances) == 1
    conn = _Connection.instances[0]
    assert conn.timeout == 30.0
    assert conn.context is None
    assert conn.handlers == ["/xmlrpc/2/object"]


def test_xmlrpc_nonlocal_http_does_not_open_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("socket")

    monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPConnection", refuse)
    monkeypatch.setattr("odoo_client.transport.xmlrpc_adapter.http.client.HTTPSConnection", refuse)
    proxy = contract_server_proxy("http://odoo.example/xmlrpc/2/object", database="db")
    with pytest.raises(TransportPolicyError, match="TLS required"):
        proxy.execute_kw("db", 1, "pw", "sale.order", "search_read", [[]], {})


def test_xmlrpc_https_uses_a_verifying_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connections(monkeypatch, https=True)
    _answer(monkeypatch, _ok([{"id": 2}]))
    proxy = contract_server_proxy("https://odoo.example/xmlrpc/2/object", database="db")
    result = proxy.execute_kw("db", 1, "pw", "sale.order", "read", [[1]], {"fields": ["id"]})
    assert result == [{"id": 2}]
    conn = _Connection.instances[0]
    assert conn.timeout == 30.0
    assert conn.context is not None
    assert conn.context.verify_mode == ssl.CERT_REQUIRED
    assert conn.context.check_hostname is True


def test_xmlrpc_write_does_not_follow_a_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connections(monkeypatch, https=True)
    proxy = contract_server_proxy("https://odoo.example/xmlrpc/2/object", database="db")
    _Connection.instances.clear()
    original_request = _Connection.request

    def request_redirect(self: _Connection, method: str, handler: str, body: bytes, headers: dict[str, str]) -> None:
        original_request(self, method, handler, body, headers)
        self.response = _Response(302, b"", location="https://evil.example/xmlrpc/2/object")

    monkeypatch.setattr(_Connection, "request", request_redirect)
    with pytest.raises(WritePlaneRedirectError) as caught:
        proxy.execute_kw("db", 1, "pw", "sale.order", "create", [{"name": "A"}], {})
    assert caught.value.status == 302
    assert caught.value.location == "https://evil.example/xmlrpc/2/object"
    assert len(_Connection.instances) == 1
    assert _Connection.instances[0].handlers == ["/xmlrpc/2/object"]
    assert _Connection.instances[0].timeout == 120.0
