"""External JSON-2 transport + execute_kw mapping — strict contracts."""

from __future__ import annotations

import json
import ssl
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

import pytest

from odoo_client.models import ConnectionConfig
from odoo_client.transport.contract import TransportPolicyError, WritePlaneRedirectError
from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body
from odoo_client.transport.json2 import (
    Json2Transport,
    Json2TransportError,
    classify_json2_error,
    is_retryable_json2,
    json2_origin,
)
from odoo_client.transport.json2_probe import probe_json2
from odoo_client.client import OdooClient, OdooClientError


# --- execute_kw → named body -------------------------------------------------


def test_map_search_read_domain_and_kwargs() -> None:
    body = execute_kw_to_json2_body(
        "search_read",
        [[("name", "=", "x")]],
        {"fields": ["id", "name"], "limit": 10},
    )
    assert body == {
        "domain": [("name", "=", "x")],
        "fields": ["id", "name"],
        "limit": 10,
    }


def test_map_create_single_dict_becomes_vals_list() -> None:
    body = execute_kw_to_json2_body("create", [{"name": "A"}])
    assert body == {"vals_list": [{"name": "A"}]}


def test_map_create_already_list_of_dicts() -> None:
    body = execute_kw_to_json2_body("create", [[{"name": "A"}, {"name": "B"}]])
    assert body == {"vals_list": [{"name": "A"}, {"name": "B"}]}


def test_map_write_ids_and_vals() -> None:
    body = execute_kw_to_json2_body("write", [[3, 4], {"name": "B"}])
    assert body == {"ids": [3, 4], "vals": {"name": "B"}}


def test_map_unlink_nested_ids() -> None:
    body = execute_kw_to_json2_body("unlink", [[[9]]])
    assert body == {"ids": [9]}


def test_map_fields_get_attributes_kwargs() -> None:
    body = execute_kw_to_json2_body(
        "fields_get", [], {"attributes": ["string", "type"]}
    )
    assert body == {"attributes": ["string", "type"]}


def test_map_button_immediate_install_ids() -> None:
    body = execute_kw_to_json2_body("button_immediate_install", [[42]])
    assert body == {"ids": [42]}


def test_map_create_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="create"):
        execute_kw_to_json2_body("create", ["not-a-dict"])


def test_map_write_requires_vals() -> None:
    with pytest.raises(ValueError, match="vals"):
        execute_kw_to_json2_body("write", [[1]])


def test_map_unknown_method_with_ambiguous_args_fails() -> None:
    with pytest.raises(ValueError, match="Cannot map"):
        execute_kw_to_json2_body("custom_thing", [1, 2, 3], {"x": 1})


# --- Json2Transport HTTP -----------------------------------------------------


class _FakeHTTPResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        if isinstance(self._payload, (bytes, bytearray)):
            return bytes(self._payload)
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_json2_success_returns_raw_value_not_envelope() -> None:
    transport = Json2Transport("https://odoo.test", "KEY")
    with patch(
        "odoo_client.transport.json2.urlopen",
        return_value=_FakeHTTPResponse([{"id": 1, "name": "A"}]),
    ) as mock_open:
        out = transport.call(
            "res.partner",
            "search_read",
            {"domain": [], "fields": ["id"], "limit": 1},
        )
    assert out == [{"id": 1, "name": "A"}]
    req = mock_open.call_args[0][0]
    assert req.full_url.endswith("/json/2/res.partner/search_read")
    assert req.get_header("Authorization") == "Bearer KEY"
    assert req.get_header("Content-type") == "application/json"
    assert b"domain" in req.data


def test_json2_does_not_send_db_header_by_default() -> None:
    transport = Json2Transport("https://odoo.test", "KEY", database="mydb")
    with patch(
        "odoo_client.transport.json2.urlopen",
        return_value=_FakeHTTPResponse({}),
    ) as mock_open:
        transport.context_get()
    req = mock_open.call_args[0][0]
    assert req.get_header("X-odoo-database") is None or req.get_header(
        "X-Odoo-Database"
    ) is None
    # urllib normalizes header names; check Request.headers
    assert "X-Odoo-Database" not in req.headers
    assert "X-odoo-database" not in {k.lower(): k for k in req.headers}


def test_json2_sends_db_header_when_enabled() -> None:
    transport = Json2Transport(
        "https://odoo.test", "KEY", database="mydb", send_db_header=True
    )
    with patch(
        "odoo_client.transport.json2.urlopen",
        return_value=_FakeHTTPResponse({"uid": 2}),
    ) as mock_open:
        transport.context_get()
    req = mock_open.call_args[0][0]
    # Request stores headers with capitalization quirks
    header_items = {k.lower(): v for k, v in req.headers.items()}
    assert header_items.get("x-odoo-database") == "mydb"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
def test_json2_http_errors_raise_with_full_body(status: int) -> None:
    err_body = {
        "name": "werkzeug.exceptions.HTTPException",
        "message": f"boom-{status}",
        "arguments": ["boom", status],
        "context": {},
    }
    fp = BytesIO(json.dumps(err_body).encode("utf-8"))
    http_err = HTTPError(
        "http://odoo.test/json/2/res.partner/search",
        status,
        "err",
        hdrs=None,  # type: ignore[arg-type]
        fp=fp,
    )
    transport = Json2Transport("https://odoo.test", "KEY")
    with patch("odoo_client.transport.json2.urlopen", side_effect=http_err):
        with pytest.raises(Json2TransportError) as caught:
            transport.call("res.partner", "search", {"domain": []})
    assert caught.value.status == status
    assert caught.value.body == err_body
    assert "boom" in str(caught.value)


def test_json2_execute_kw_uses_mapper() -> None:
    transport = Json2Transport("https://odoo.test", "KEY")
    with patch.object(transport, "call", return_value=7) as call:
        out = transport.execute_kw("res.partner", "create", [{"name": "Z"}])
    assert out == 7
    call.assert_called_once_with(
        "res.partner", "create", {"vals_list": [{"name": "Z"}]}
    )


class _Closed:
    def __init__(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    def read(self) -> bytes:
        if isinstance(self._payload, (bytes, bytearray)):
            return bytes(self._payload)
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _Closed:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.mark.parametrize("base_url", ["http://127.0.0.1:8069", "http://localhost:8069"])
def test_json2_local_http_sandbox_sends(base_url: str) -> None:
    seen: list[str] = []

    def fake_urlopen(req: Any, timeout: float | None = None, context: Any = None) -> _Closed:
        assert context is None
        assert timeout == 30.0
        seen.append(req.full_url)
        return _Closed(200, [{"id": 1}])

    transport = Json2Transport(base_url, "KEY", database="sandbox")
    with patch("odoo_client.transport.json2.urlopen", fake_urlopen):
        out = transport.call("res.partner", "search_read", {"domain": []})
    assert out == [{"id": 1}]
    assert seen == [f"{base_url}/json/2/res.partner/search_read"]


def test_json2_nonlocal_http_does_not_send() -> None:
    def fake_urlopen(req: Any, timeout: float | None = None, context: Any = None) -> _Closed:
        raise AssertionError(f"send was called for {req.full_url}")

    transport = Json2Transport("http://odoo.example", "KEY", database="db")
    with patch("odoo_client.transport.json2.urlopen", fake_urlopen):
        with pytest.raises(TransportPolicyError, match="TLS required"):
            transport.call("res.partner", "search_read", {"domain": []})


def test_json2_https_read_uses_a_verifying_context() -> None:
    seen: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None, context: Any = None) -> _Closed:
        seen["timeout"] = timeout
        seen["context"] = context
        seen["url"] = req.full_url
        return _Closed(200, [{"id": 1}])

    transport = Json2Transport("https://odoo.example", "KEY", database="db")
    with patch("odoo_client.transport.json2.urlopen", fake_urlopen):
        assert transport.call("res.partner", "search_read", {"domain": []}) == [{"id": 1}]
    assert seen["timeout"] == 30.0
    assert seen["url"] == "https://odoo.example/json/2/res.partner/search_read"
    assert seen["context"].verify_mode == ssl.CERT_REQUIRED
    assert seen["context"].check_hostname is True


def test_json2_write_does_not_follow_a_redirect() -> None:
    requested: list[str] = []

    def fake_urlopen(req: Any, timeout: float | None = None, context: Any = None) -> _Closed:
        raise AssertionError(f"write followed redirects via urlopen for {req.full_url}")

    class _Opener:
        def open(self, req: Any, timeout: float | None = None) -> _Closed:
            requested.append(req.full_url)
            assert timeout == 120.0
            return _Closed(302, b"", {"Location": "https://evil.example/json/2/res.partner/create"})

    transport = Json2Transport("https://odoo.example", "KEY", database="db")
    with patch("odoo_client.transport.json2.urlopen", fake_urlopen):
        with patch("odoo_client.transport.json2.build_opener", return_value=_Opener()):
            with pytest.raises(WritePlaneRedirectError) as caught:
                transport.call("res.partner", "create", {"vals_list": [{"name": "A"}]})
    assert caught.value.status == 302
    assert caught.value.location == "https://evil.example/json/2/res.partner/create"
    assert requested == ["https://odoo.example/json/2/res.partner/create"]


def test_json2_redirect_handler_does_not_request_the_next_url() -> None:
    from odoo_client.transport.json2 import _RedirectRefused, _RefuseRedirect

    class _Body:
        def read(self) -> bytes:
            return b""

        def close(self) -> None:
            return None

    handler = _RefuseRedirect()
    with pytest.raises(_RedirectRefused) as caught:
        handler.http_error_302(
            None,
            _Body(),
            302,
            "Found",
            {"location": "https://evil.example/next"},
        )
    assert caught.value.status == 302
    assert caught.value.location == "https://evil.example/next"


# --- OdooClient dual-protocol selection --------------------------------------


def _cfg(**kwargs: Any) -> ConnectionConfig:
    base = dict(
        url="http://127.0.0.1:8069",
        db="odoo",
        username="admin",
        password="admin",
    )
    base.update(kwargs)
    return ConnectionConfig(**base)  # type: ignore[arg-type]


def test_local_auto_stays_xmlrpc_even_on_major_19() -> None:
    client = OdooClient(_cfg(rpc_protocol="auto"))
    assert client._should_use_json2(major=19, hosting="self_hosted") is False
    assert client._should_use_json2(major=19, hosting="online") is True
    assert client._should_use_json2(major=18, hosting="online") is False


def test_forced_json2_on_major_18_still_false() -> None:
    client = OdooClient(_cfg(rpc_protocol="json2"))
    assert client._should_use_json2(major=18, hosting="online") is False


def test_execute_kw_json2_path_does_not_touch_xmlrpc_object() -> None:
    client = OdooClient(_cfg(rpc_protocol="json2"))
    client._uid = 2
    client._rpc_protocol = "json2"
    fake = Json2Transport("https://odoo.test", "KEY")
    client._json2 = fake
    with patch.object(fake, "execute_kw", return_value=[{"id": 1}]) as j2:
        with patch.object(client, "_object") as obj:
            out = client.execute_kw(
                "res.partner", "search_read", [[]], {"fields": ["id"], "limit": 1}
            )
    assert out == [{"id": 1}]
    j2.assert_called_once()
    obj.execute_kw.assert_not_called()


def test_execute_kw_xmlrpc_path_does_not_send_bearer() -> None:
    client = OdooClient(_cfg(rpc_protocol="xmlrpc"))
    client._uid = 1
    client._rpc_protocol = "xmlrpc"
    with patch.object(client._object, "execute_kw", return_value=[]) as xml:
        client.execute_kw("res.partner", "search", [[]])
    xml.assert_called_once()
    # positional legacy shape — no Authorization anywhere in args
    called = xml.call_args[0]
    assert called[0] == "odoo"
    assert called[3] == "res.partner"


def test_json2_auth_failure_surfaces_odoo_client_error() -> None:
    client = OdooClient(_cfg(rpc_protocol="json2", password="bad-key"))
    with patch(
        "odoo_client.client.Json2Transport.context_get",
        side_effect=Json2TransportError("Invalid apikey", status=401, body={"message": "Invalid apikey"}),
    ):
        with pytest.raises(OdooClientError, match="JSON-2 auth failed"):
            client._connect_json2(major=19)


def test_json2_origin_strips_web_client_path() -> None:
    assert json2_origin("https://aonb.odoo.com/odoo") == "https://aonb.odoo.com"
    assert json2_origin("https://odoo.example/web/") == "https://odoo.example"
    assert json2_origin("https://odoo.example/custom") == "https://odoo.example/custom"


def test_domain_typeerror_500_is_a_caller_error_and_is_not_retryable() -> None:
    body = {
        "name": "builtins.TypeError",
        "message": "Domain() invalid argument type for domain: 'not-a-domain'",
    }
    assert classify_json2_error(500, body) == "caller"
    assert classify_json2_error(422, {"message": "missing a required argument: 'vals_list'"}) == "caller"
    assert classify_json2_error(401, {"message": "Invalid apikey"}) == "auth"
    assert classify_json2_error(500, {"name": "werkzeug.exceptions.InternalServerError", "message": "boom"}) == "server"
    exc = Json2TransportError("domain", status=500, body=body)
    assert is_retryable_json2(exc) is False


def test_probe_ignores_website_doc_and_keeps_live_parameters() -> None:
    website = b"<!DOCTYPE html><html data-website-id=\"1\"><body>create a page</body></html>"
    responses = [
        _FakeHTTPResponse(website),
        _FakeHTTPResponse([]),
        _FakeHTTPResponse({"id": {"string": "ID", "type": "integer"}}),
        _http_error(422, {"message": "missing a required argument: 'vals_list'"}),
    ]
    transport = Json2Transport("https://aonb.odoo.com/odoo", "secret-key")
    with patch("odoo_client.transport.json2.open_http", side_effect=responses):
        probe = probe_json2(transport)
    assert transport.base_url == "https://aonb.odoo.com"
    assert probe["doc_route"] == "website"
    assert probe["parameters"]["search_read"] == ["domain", "fields", "limit"]
    assert probe["parameters"]["fields_get"] == ["attributes"]
    assert probe["parameters"]["create"] == ["vals_list"]
    assert probe["disagreements"] == []
    assert "secret-key" not in json.dumps(probe)


def test_probe_live_parameters_win_when_doc_disagrees() -> None:
    api_doc = b"search_read fields_get create allfields domain"
    responses = [
        _FakeHTTPResponse(api_doc),
        _FakeHTTPResponse([]),
        _FakeHTTPResponse({"id": {"string": "ID", "type": "integer"}}),
        _http_error(422, {"message": "missing a required argument: 'vals_list'"}),
    ]
    transport = Json2Transport("https://odoo.example", "secret-key")
    with patch("odoo_client.transport.json2.open_http", side_effect=responses):
        probe = probe_json2(transport)
    assert probe["doc_route"] == "api"
    assert probe["parameters"]["fields_get"] == ["attributes"]
    assert any("fields_get" in note for note in probe["disagreements"])


def test_connect_json2_stores_the_probe() -> None:
    client = OdooClient(_cfg(rpc_protocol="json2", password="secret-key", url="https://aonb.odoo.com/odoo"))
    with patch(
        "odoo_client.client.Json2Transport.context_get",
        return_value={"uid": 2},
    ):
        with patch(
            "odoo_client.client.probe_json2",
            return_value={"doc_route": "website", "parameters": {"create": ["vals_list"]}},
        ) as probed:
            uid = client._connect_json2(major=20)
    assert uid == 2
    assert client.json2_probe["doc_route"] == "website"
    assert client.production_probe["protocol"] == "json2"
    assert client.production_probe["major"] == 20
    probed.assert_called_once()


def test_legacy_probe_learns_17_and_does_not_call_create() -> None:
    from odoo_client.transport.production_probe import probe_legacy

    seen: list[str] = []

    def execute(model: str, method: str, args: list | None, kwargs: dict | None):
        seen.append(method)
        assert model == "res.partner"
        if method == "search_read":
            assert args == [[("id", "=", 0)]]
            assert kwargs == {"fields": ["id"], "limit": 1}
            return []
        if method == "fields_get":
            assert kwargs == {"attributes": ["string", "type"]}
            return {"id": {"string": "ID", "type": "integer"}}
        raise AssertionError(method)

    for protocol, major in (("xmlrpc", 17), ("jsonrpc", 18), ("xmlrpc", 19)):
        probe = probe_legacy(execute, protocol=protocol, major=major)
        assert probe["protocol"] == protocol
        assert probe["major"] == major
        assert probe["doc_route"] == "not_applicable"
        assert probe["parameters"]["search_read"] == ["domain", "fields", "limit"]
        assert probe["parameters"]["fields_get"] == ["attributes"]
        assert probe["parameters"]["create"] == ["vals"]
        assert probe["calls"]["search_read"] == 200
    assert "create" not in seen


def test_xmlrpc_connect_stores_a_17_probe() -> None:
    client = OdooClient(_cfg())
    with patch.object(client._common, "version", return_value={"server_version": "17.0+e"}):
        with patch.object(client._common, "authenticate", return_value=5):
            with patch.object(client, "execute_kw", return_value=[]) as execute:
                uid = client.connect()
    assert uid == 5
    assert client.production_probe["protocol"] == "xmlrpc"
    assert client.production_probe["major"] == 17
    assert client.production_probe["parameters"]["create"] == ["vals"]
    methods = [call.args[1] for call in execute.call_args_list]
    assert methods == ["search_read", "fields_get"]
    assert "create" not in methods


def _http_error(status: int, body: dict) -> HTTPError:
    return HTTPError(
        "https://odoo.example/json/2/res.partner/create",
        status,
        "err",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(json.dumps(body).encode("utf-8")),
    )
