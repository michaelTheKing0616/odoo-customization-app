"""FITGAP-01 contract tests: fit-gap types, routes, B5 envelope, tenancy, safety, TS mirror.

Runs with a fake engine and a fake workspace scope, plus a real-gate tenancy check.
No Odoo.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.delivery import fit_gap_types as t
from app.main import app
from app.routers import fit_gap as fg
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ERROR_HTTP, ScanError, ScanScope
from app.security import idor_registry as reg
from app.workspace_auth import require_app_auth

CONN_A = "conn-a"
CONN_B = "conn-b"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b"}
BASE = "/api/connections/{cid}/fitgap"

# Field lists copied from docs/build-plan/new-features/DELIVERY.md §FITGAP §6.
DOC_FIELDS = {
    "FitGapDoc": {"id", "doc_sha256", "catalog_version", "lines"},
    "FitGapLine": {"id", "quote", "cls", "evidence", "effort_h", "confidence", "override"},
    "Evidence": {"module", "model", "field", "setting", "not_in_community"},
    "LineOverride": {"cls", "reason"},
}


def _line(lid: str = "l-1", cls: str | None = "standard") -> t.FitGapLine:
    return t.FitGapLine(
        id=lid,
        quote="Track customer credit limits.",
        cls=cls,
        evidence=[t.Evidence(module="account", model="res.partner", field="credit_limit")],
        effort_h=(0.5, 1.0),
        confidence=0.9,
        override=None,
    )


def _doc(did: str = "doc-1") -> t.FitGapDoc:
    return t.FitGapDoc(
        id=did, doc_sha256="a" * 64, catalog_version="cat-1", lines=[_line(), _line("l-2", None)]
    )


class FakeEngine:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], t.FitGapDoc] = {(CONN_A, "doc-1"): _doc()}
        self.calls: list[str] = []

    def _own(self, scope: ScanScope, did: str) -> t.FitGapDoc:
        doc = self.docs.get((scope.connection_id, did))
        if doc is None:
            raise ScanError("NOT_FOUND", "That fit-gap doesn't exist.")
        return doc

    def create(self, scope, body):
        self.calls.append("create")
        if body.text == "same":
            return self._own(scope, "doc-1"), False
        doc = _doc("doc-new")
        self.docs[(scope.connection_id, doc.id)] = doc
        return doc, True

    def get(self, scope, did):
        self.calls.append("get")
        return self._own(scope, did)

    def override(self, scope, did, lid, body):
        self.calls.append("override")
        doc = self._own(scope, did)
        for ln in doc.lines:
            if ln.id == lid:
                return ln.model_copy(update={"override": body})
        raise ScanError("NOT_FOUND", "That line doesn't exist.")


def _fake_scope(connection_id: str, x_ws: str = Header("ws-a"), x_role: str = Header("admin")):
    if x_role == "viewer":
        raise HTTPException(status_code=403, detail="Requires builder role or higher.")
    if OWNER.get(connection_id) != x_ws:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ScanScope(workspace_id=x_ws, connection_id=connection_id)


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


@pytest.fixture
def engine():
    eng = FakeEngine()
    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[fg.fitgap_scope] = _fake_scope
    o[fg.create_engine] = lambda: eng.create
    o[fg.get_engine] = lambda: eng.get
    o[fg.override_engine] = lambda: eng.override
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


OVR = {"cls": "custom", "reason": "Client needs approval steps."}
ROUTES = [
    ("POST", BASE, {"text": "Track credit limits."}),
    ("GET", BASE + "/doc-1", None),
    ("PATCH", BASE + "/doc-1/lines/l-1", OVR),
]


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(DOC_FIELDS))
def test_ac1_model_fields_match_epic_doc(name):
    assert set(getattr(t, name).model_fields) == DOC_FIELDS[name]


def test_ac1_post_body_is_exactly_one_of_upload_id_or_text():
    assert set(t.FitGapRequest.model_fields) == {"upload_id", "text"}
    t.FitGapRequest(text="x")
    t.FitGapRequest(upload_id="u-1")
    for bad in ({}, {"text": "x", "upload_id": "u"}):
        with pytest.raises(ValueError):
            t.FitGapRequest(**bad)


def test_ac1_enums_and_ranges():
    assert _line(cls=None).cls is None
    with pytest.raises(ValueError):
        _line(cls="maybe")
    with pytest.raises(ValueError):
        t.FitGapLine(**{**_line().model_dump(), "effort_h": (3, 1)})
    with pytest.raises(ValueError):
        t.FitGapLine(**{**_line().model_dump(), "confidence": 1.5})
    with pytest.raises(ValueError):
        t.LineOverride(cls=None, reason="x")
    assert set(t.FITGAP_ERROR_CODES) <= set(ERROR_HTTP)


# AC2 / AC6 -----------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    r = client.post(BASE.format(cid=CONN_A), json={"text": "Track credit limits."})
    assert r.status_code == 202, r.text
    t.FitGapDoc.model_validate(r.json())
    r = client.post(BASE.format(cid=CONN_A), json={"text": "same"})
    assert r.status_code == 200 and r.json()["id"] == "doc-1"
    r = client.get(BASE.format(cid=CONN_A) + "/doc-1")
    assert r.status_code == 200
    doc = t.FitGapDoc.model_validate(r.json())
    assert set(r.json()) == DOC_FIELDS["FitGapDoc"] and doc.lines[1].cls is None
    assert set(r.json()["lines"][0]) == DOC_FIELDS["FitGapLine"]
    assert set(r.json()["lines"][0]["evidence"][0]) == DOC_FIELDS["Evidence"]
    r = client.patch(BASE.format(cid=CONN_A) + "/doc-1/lines/l-1", json=OVR)
    assert r.status_code == 200 and r.json()["override"] == OVR
    t.FitGapLine.model_validate(r.json())
    assert engine.calls == ["create", "create", "get", "override"]


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac2_403_envelope(client, method, path, body):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-role": "viewer"})
    _assert_envelope(r, 403, "ROLE_DENIED")


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac2_404_envelope_unknown_ids(client, method, path, body):
    p = path.format(cid=CONN_A).replace("doc-1", "nope")
    if p == path.format(cid=CONN_A):
        p = path.format(cid="conn-missing")
    _assert_envelope(client.request(method, p, json=body), 404, "NOT_FOUND")


def test_ac2_404_envelope_unknown_line(client):
    r = client.patch(BASE.format(cid=CONN_A) + "/doc-1/lines/nope", json=OVR)
    _assert_envelope(r, 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "method,suffix,body,field",
    [
        ("POST", "", {}, "upload_id"),
        ("POST", "", {"text": "a", "upload_id": "u"}, "upload_id"),
        ("POST", "", {"text": "a", "model": "x"}, "model"),
        ("PATCH", "/doc-1/lines/l-1", {"cls": "custom"}, "reason"),
        ("PATCH", "/doc-1/lines/l-1", {"cls": "nope", "reason": "r"}, "cls"),
    ],
)
def test_ac2_422_envelope_names_field(client, method, suffix, body, field):
    r = client.request(method, BASE.format(cid=CONN_A) + suffix, json=body)
    err = _assert_envelope(r, 422, "VALIDATION")
    assert field in str(err["detail"]) or field in err["message"]


# AC3 -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac3_cross_workspace_404(client, method, path, body):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-ws": "ws-b"})
    _assert_envelope(r, 404, "NOT_FOUND")
    if "doc-1" in path:  # B on its own connection with A's doc id
        r = client.request(method, path.format(cid=CONN_B), json=body, headers={"x-ws": "ws-b"})
        _assert_envelope(r, 404, "NOT_FOUND")


def test_ac3_every_fitgap_route_in_idor_registry():
    paths = app.openapi()["paths"]
    live = {(m.upper(), p) for p, ops in paths.items() if "/fitgap" in p for m in ops}
    assert live == set(reg.NF_FITGAP_ROUTES) and len(live) == 3
    assert not reg.missing_registered_routes(paths, reg.NF_FITGAP_ROUTES)
    assert all(p in reg.connection_scoped_paths(paths) for _, p in reg.NF_FITGAP_ROUTES)


def _seed_two_workspaces(paused: bool):
    import uuid

    from app.account_models import User
    from app.account_service import signup_user
    from app.crypto import encrypt_secret
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.entitlements import seed_plan_features

    init_db()
    db = SessionLocal()
    try:
        seed_plan_features(db)
        tag = uuid.uuid4().hex[:8]
        a_email, b_email = f"fg-a-{tag}@example.com", f"fg-b-{tag}@example.com"
        _a, ws_a, _ = signup_user(db, email=a_email, password="alice-pass-99", workspace_name="A")
        _b, ws_b, _ = signup_user(db, email=b_email, password="bob-pass-99", workspace_name="B")
        for email in (a_email, b_email):
            u = db.query(User).filter(User.email == email).one()
            u.email_verified = True
            db.add(u)
        ids = {}
        for key, ws in (("a", ws_a), ("b", ws_b)):
            conn = OdooConnection(
                name=f"fg {key}",
                url="http://127.0.0.1:1",
                db_name="ingenium_wt_none",
                username="admin",
                secret_encrypted=encrypt_secret("x"),
                workspace_id=ws.id,
            )
            if key == "a" and paused:
                conn.writes_paused = True
            db.add(conn)
            db.flush()
            ids[key] = conn.id
        db.commit()
        return b_email, ids, a_email
    finally:
        db.close()


@pytest.mark.parametrize("paused", [False, True], ids=["victim-normal", "victim-paused"])
def test_ac3_real_gate_cross_workspace_404_no_existence_leak(monkeypatch, paused):
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    b_email, ids, _ = _seed_two_workspaces(paused)
    ghost = "00000000-0000-0000-0000-000000000000"
    with TestClient(app) as bob:
        r = bob.post("/api/accounts/login", json={"email": b_email, "password": "bob-pass-99"})
        assert r.status_code == 200, r.text
        for method, path, body in ROUTES:
            real = bob.request(method, path.format(cid=ids["a"]), json=body)
            fake = bob.request(method, path.format(cid=ghost), json=body)
            _assert_envelope(real, 404, "NOT_FOUND")
            assert real.json() == fake.json(), f"{method} {path} differs for a real id"


# AC4 -----------------------------------------------------------------------
def _provide(fn):
    def provider():
        return fn

    return provider


def test_ac4_owned_paused_connection_refuses_writes(monkeypatch):
    """Owner A, writes paused: POST and PATCH refuse (403 writes_paused); GET still reads."""
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    _b, ids, a_email = _seed_two_workspaces(paused=True)
    eng = FakeEngine()
    eng.docs[(ids["a"], "doc-1")] = _doc()
    o = app.dependency_overrides
    for dep, fn in (
        (fg.create_engine, eng.create),
        (fg.get_engine, eng.get),
        (fg.override_engine, eng.override),
    ):
        o[dep] = _provide(fn)
    base = BASE.format(cid=ids["a"])
    with TestClient(app) as alice:
        r = alice.post("/api/accounts/login", json={"email": a_email, "password": "alice-pass-99"})
        assert r.status_code == 200, r.text
        for method, suffix, body in (
            ("POST", "", {"text": "x"}),
            ("PATCH", "/doc-1/lines/l-1", OVR),
        ):
            err = _assert_envelope(
                alice.request(method, base + suffix, json=body), 403, "ROLE_DENIED"
            )
            assert err["detail"]["error"] == "writes_paused", method
        r = alice.get(base + "/doc-1")
        assert r.status_code == 200, r.text
    assert eng.calls == ["get"]


def test_ac4_fitgap_safety_specs_pinned():
    from app.safety_registry import ROUTE_OVERRIDES

    def fields(spec):
        return asdict(spec) if is_dataclass(spec) else spec.model_dump()

    inbox = fields(ROUTE_OVERRIDES["POST:/api/inbox/plans"])
    pre = "/api/connections/{connection_id}/fitgap"
    for key in ("POST:" + pre, "PATCH:" + pre + "/{doc_id}/lines/{lid}"):
        spec = ROUTE_OVERRIDES[key]
        assert fields(spec) == inbox, key
        assert spec.odoo_mutation is False and spec.bypass_writes_paused is False, key


# AC5 -----------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "fit-gap.ts"
TS_KEY_FIXTURE = {**DOC_FIELDS, "FitGapRequest": {"upload_id", "text"}}


def _ts_type_keys(src: str, name: str) -> set[str]:
    m = re.search(r"export type " + name + r" =\s*(.*?);\n\n", src, re.S)
    assert m, f"{name} missing from fit-gap.ts"
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
    for fn in ("createFitGap", "getFitGap", "overrideLine"):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -----------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    src = Path(fg.__file__).read_text() + Path(t.__file__).read_text()
    assert "odoo_client" not in src and "execute_kw" not in src and "_client(" not in src
    for dep in ("create_engine", "get_engine", "override_engine"):
        assert src.count(f"Depends({dep})") == 1, dep
