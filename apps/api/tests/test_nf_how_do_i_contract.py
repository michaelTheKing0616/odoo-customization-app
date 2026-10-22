"""HOWDO-01 contract tests: how-do-I assistant types, routes, B5 envelope, token tenancy,
safety, TS mirror. Fake engines and fake auth only. No Odoo, no real token checks.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.assist import auth as howdo_auth
from app.assist import contract as t
from app.auth import require_api_auth
from app.main import app
from app.routers import assist as rt
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ERROR_HTTP, ScanError
from app.security import idor_registry as reg

# Field lists copied from docs/build-plan/new-features/AI_IN_ODOO.md §HOWDO §6 (pinned 2026-10-22).
DOC_FIELDS = {
    "AssistTokenRequest": {"connection_id", "odoo_uid"},
    "HowdoToken": {"token", "expires_at", "scope"},
    "AssistAsk": {"question", "page_context"},
    "AssistAnswer": {"answer_md", "steps", "citations", "refused"},
    "AssistStep": {"text", "menu_path", "deep_link"},
    "AssistCitation": {"kind", "tech_name"},
}
TOKEN = "/api/bridge-assist/token"
ASK = "/api/bridge-assist/ask"
CONN_A, CONN_B = "conn-a", "conn-b"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b"}
MENUS = {CONN_A: "Purchase / Orders / Approve (A)", CONN_B: "Sales / Quotations (B)"}
TOKENS = {"tok-a": (CONN_A, "ask"), "tok-b": (CONN_B, "ask"), "tok-ro": (CONN_A, "read"),
          "tok-gone": ("conn-deleted", "ask")}
ASK_BODY = {"question": "How do I approve this PO?", "page_context": {"model": "purchase.order"}}
ENGINE_DEPS = {"mint": "mint_engine", "ask": "ask_engine"}


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def mint(self, caller_ws, body):
        self.calls.append("mint")
        if OWNER.get(body.connection_id) != caller_ws:
            raise ScanError("NOT_FOUND", "Connection not found.")
        return t.HowdoToken(token="tok-a", expires_at=datetime(2026, 10, 22, tzinfo=UTC),
                            scope="ask")

    def ask(self, principal, body):
        self.calls.append("ask")
        if principal.connection_id not in MENUS:
            raise ScanError("NOT_FOUND", "Connection not found.")
        menu = MENUS[principal.connection_id]
        return t.AssistAnswer(
            answer_md=f"Open **{menu}**.",
            steps=[t.AssistStep(text="Open the menu", menu_path=menu, deep_link="/odoo/action-1")],
            citations=[t.AssistCitation(kind="menu", tech_name="purchase.menu_purchase_rfq")],
            refused=None,
        )


def _fake_api_auth(x_ws: str = Header("ws-a"), x_role: str = Header("admin"),
                   authorization: str | None = Header(None)):
    if authorization != "Bearer key":
        raise HTTPException(status_code=401, detail="Missing API key.")
    if x_role == "viewer":
        raise HTTPException(status_code=403, detail="Requires builder role or higher.")
    return x_ws


def _fake_howdo_token(authorization: str | None = Header(None)):
    raw = (authorization or "").removeprefix("Bearer ").strip()
    if raw not in TOKENS:
        raise HTTPException(status_code=401, detail="Missing or bad assistant token.")
    conn, scope = TOKENS[raw]
    return howdo_auth.HowdoPrincipal(connection_id=conn, odoo_uid=7, scope=scope)


@pytest.fixture(autouse=True)
def _isolate_shared_state(monkeypatch):
    """Force a fresh gate registry and restore dependency overrides afterwards."""
    from app import safety_dependency

    monkeypatch.setattr(safety_dependency, "_REGISTRY", None)
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _provide(fn):
    def provider():
        return fn

    return provider


@pytest.fixture
def engine():
    eng = FakeEngine()
    o = app.dependency_overrides
    o[enforce_safety_gate] = lambda: None
    o[rt.token_caller] = _fake_api_auth
    o[howdo_auth.require_howdo_token] = _fake_howdo_token
    for key, dep in ENGINE_DEPS.items():
        o[getattr(rt, dep)] = _provide(getattr(eng, key))
    return eng


@pytest.fixture
def client(engine):
    return TestClient(app)


def _assert_envelope(res, status: int, code: str):
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail", "retry_after_s"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    return body["error"]


def _tok(body=None, **h):
    return {"json": body or {"connection_id": CONN_A, "odoo_uid": 7},
            "headers": {"authorization": "Bearer key", **h}}


def _ask(token="tok-a", body=None):
    return {"json": body or ASK_BODY, "headers": {"authorization": f"Bearer {token}"}}


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(DOC_FIELDS))
def test_ac1_model_fields_match_epic_doc(name):
    assert set(getattr(t, name).model_fields) == DOC_FIELDS[name]


def test_ac1_pinned_types():
    f = t.AssistAsk.model_fields
    assert f["page_context"].annotation == dict[str, str] | None
    assert t.AssistTokenRequest.model_fields["odoo_uid"].annotation == int | None
    assert t.AssistAnswer.model_fields["refused"].annotation == str | None
    assert t.HowdoToken.model_fields["expires_at"].annotation is datetime
    t.AssistCitation(kind="field", tech_name="x")
    with pytest.raises(ValueError):
        t.AssistCitation(kind="action", tech_name="x")
    with pytest.raises(ValueError):
        t.HowdoToken(token="x", expires_at=datetime.now(UTC), scope="admin")
    assert "connection_id" not in t.AssistAsk.model_fields
    assert set(t.HOWDO_ERROR_CODES) <= set(ERROR_HTTP)


# AC2 / AC6 -----------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    r = client.post(TOKEN, **_tok())
    assert r.status_code == 200, r.text
    t.HowdoToken.model_validate(r.json())
    assert set(r.json()) == DOC_FIELDS["HowdoToken"] and r.json()["scope"] == "ask"
    r = client.post(ASK, **_ask())
    assert r.status_code == 200, r.text
    t.AssistAnswer.model_validate(r.json())
    assert set(r.json()) == DOC_FIELDS["AssistAnswer"] and r.json()["refused"] is None
    assert engine.calls == ["mint", "ask"]


def test_ac2_ask_page_context_optional(client):
    assert client.post(ASK, **_ask(body={"question": "Where?"})).status_code == 200


def test_ac2_missing_or_bad_token_is_401(client, engine):
    assert client.post(TOKEN, json={"connection_id": CONN_A}).status_code == 401
    assert client.post(ASK, json=ASK_BODY).status_code == 401
    assert client.post(ASK, **_ask(token="forged")).status_code == 401
    assert engine.calls == []


def test_ac2_403_envelope(client, engine):
    _assert_envelope(client.post(TOKEN, **_tok(**{"x-role": "viewer"})), 403, "ROLE_DENIED")
    _assert_envelope(client.post(ASK, **_ask(token="tok-ro")), 403, "ROLE_DENIED")
    assert engine.calls == []


def test_ac2_404_envelope(client):
    _assert_envelope(client.post(TOKEN, **_tok({"connection_id": "nope"})), 404, "NOT_FOUND")
    _assert_envelope(client.post(ASK, **_ask(token="tok-gone")), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "path,body,field",
    [
        (TOKEN, {"odoo_uid": 7}, "connection_id"),
        (TOKEN, {"connection_id": CONN_A, "x": 1}, "x"),
        (ASK, {"page_context": {}}, "question"),
        (ASK, {"question": "q", "connection_id": CONN_A}, "connection_id"),
        (ASK, {"question": "q", "page_context": {"action_id": 5}}, "page_context"),
    ],
)
def test_ac2_422_envelope_names_field(client, path, body, field):
    kw = _tok(body) if path == TOKEN else _ask(body=body)
    err = _assert_envelope(client.post(path, **kw), 422, "VALIDATION")
    assert field in str(err["detail"]) or field in err["message"]


def test_ac6_default_engine_is_not_ready_envelope():
    o = app.dependency_overrides
    o[enforce_safety_gate] = lambda: None
    o[rt.token_caller] = _fake_api_auth
    o[howdo_auth.require_howdo_token] = _fake_howdo_token
    c = TestClient(app)
    _assert_envelope(c.post(TOKEN, **_tok()), 404, "NOT_FOUND")
    _assert_envelope(c.post(ASK, **_ask()), 404, "NOT_FOUND")


def test_ac6_stub_token_dependency_refuses_everything_401():
    o = app.dependency_overrides
    o[enforce_safety_gate] = lambda: None
    c = TestClient(app)
    for h in ({}, {"authorization": "Bearer anything"}, {"authorization": "Basic x"}):
        r = c.post(ASK, json=ASK_BODY, headers=h)
        assert r.status_code == 401, r.text


# AC3 -----------------------------------------------------------------------
def test_ac3_cross_tenant_token(client, engine):
    a = client.post(ASK, **_ask("tok-a")).json()
    b = client.post(ASK, **_ask("tok-b")).json()
    assert MENUS[CONN_A] in a["answer_md"] and MENUS[CONN_B] not in a["answer_md"]
    assert MENUS[CONN_B] in b["answer_md"] and MENUS[CONN_A] not in b["answer_md"]


def test_ac3_cross_workspace_token_mint_404_byte_identical(client):
    foreign = client.post(TOKEN, **_tok({"connection_id": CONN_B}))
    ghost = client.post(TOKEN, **_tok({"connection_id": "conn-ghost"}))
    _assert_envelope(foreign, 404, "NOT_FOUND")
    assert foreign.content == ghost.content


def test_ac3_every_howdo_route_in_idor_registry_token_scoped():
    paths = app.openapi()["paths"]
    live = {(m.upper(), p) for p, ops in paths.items() if "/bridge-assist/" in p for m in ops}
    assert live == set(reg.NF_HOWDO_ROUTES) == {("POST", TOKEN), ("POST", ASK)}
    assert not reg.missing_registered_routes(paths, reg.NF_HOWDO_ROUTES)
    scoped = reg.connection_scoped_paths(paths)
    assert all(p not in scoped for _, p in reg.NF_HOWDO_ROUTES)
    src = Path(rt.__file__).read_text()
    assert "get_scoped_connection_or_404" not in src


def test_ac3_routes_use_pinned_auth_dependencies():
    deps = {}
    for r in rt.router.routes:  # app.routes wraps included routers lazily (FastAPI)
        if "/api" + r.path in (TOKEN, ASK):
            stack, seen = [r.dependant], set()
            while stack:
                d = stack.pop()
                if d.call is not None:
                    seen.add(d.call)
                stack.extend(d.dependencies)
            deps["/api" + r.path] = seen
    assert rt.token_caller in deps[TOKEN] and require_api_auth in deps[TOKEN]
    assert howdo_auth.require_howdo_token in deps[ASK]
    assert require_api_auth not in deps[ASK]


# AC4 -----------------------------------------------------------------------
def test_ac4_howdo_safety_specs_pinned():
    from app.safety_registry import ROUTE_OVERRIDES

    def fields(spec):
        return asdict(spec) if is_dataclass(spec) else spec.model_dump()

    for key in ("POST:" + TOKEN, "POST:" + ASK):
        spec = ROUTE_OVERRIDES[key]
        assert (spec.risk, spec.odoo_mutation, spec.confirm) == ("read", False, "none"), key
        assert spec.bypass_writes_paused is False, key
        assert fields(spec)


# AC5 -----------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "assist.ts"
TS_KEY_FIXTURE = dict(DOC_FIELDS)


def _ts_type_keys(src: str, name: str) -> set[str]:
    m = re.search(r"export type " + name + r" =\s*(.*?);\n\n", src, re.S)
    assert m, f"{name} missing from assist.ts"
    return set(re.findall(r"\b([a-z_0-9]+)\??:", m.group(1)))


def test_ac5_openapi_components_match_ts_fixture():
    comps = app.openapi()["components"]["schemas"]
    for name, keys in TS_KEY_FIXTURE.items():
        assert name in comps, name
        assert set(comps[name]["properties"]) == keys, name


def test_ac5_ts_mirror_matches_fixture():
    src = TS_FILE.read_text()
    for name, keys in TS_KEY_FIXTURE.items():
        assert _ts_type_keys(src, name) == keys, name
    for fn in ("mintAssistToken", "askAssist"):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -----------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    src = Path(rt.__file__).read_text() + Path(t.__file__).read_text()
    src += Path(howdo_auth.__file__).read_text()
    for bad in ("odoo_client", "execute_kw", "_client(", "xmlrpc"):
        assert bad not in src, bad
    for dep in ENGINE_DEPS.values():
        assert src.count(f"Depends({dep})") == 1, dep
