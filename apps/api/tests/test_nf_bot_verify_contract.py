"""BV-01 contract tests: verify-run types, routes, B5 envelope, tenancy, safety, TS mirror.

Fake engines and a fake workspace scope, plus a real-gate tenancy check. No Odoo call:
the Odoo client factory is patched to raise for every route call.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.changeset.verify import CHECKS
from app.main import app
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ERROR_HTTP, ScanScope
from app.security import idor_registry as reg
from app.workspace_auth import require_app_auth

CONN_A, CONN_B = "conn-a", "conn-b"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b"}
RUN, ART = "run-1", "art-1"
RUN_OWNER = {RUN: CONN_A, "run-b": CONN_B}
ART_OWNER = {(RUN, ART): CONN_A, ("run-b", "art-b"): CONN_B}
PNG = b"\x89PNG\r\n\x1a\nfake"
BASE = "/api/connections/{cid}/verify-runs"
RBASE = BASE + "/{rid}"
ABASE = RBASE + "/artifacts/{aid}"
REQ = {"changeset_id": "cs-1", "layers": ["live", "walkthrough"], "target": "disposable_clone"}

DOC_FIELDS = {
    "VerifyRunRequest": {"changeset_id", "layers", "target"},
    "CheckResult": {"check", "op_index", "passed", "evidence"},
    "WalkStep": {
        "index",
        "op_index",
        "action",
        "target",
        "passed",
        "screenshot_id",
        "dom_assertion",
    },
    "LayerResult": {"layer", "status", "reason", "checks", "steps"},
    "VerifyRun": {"run_id", "changeset_id", "status", "layers", "started_at", "finished_at"},
}
ENGINE_DEPS = {"start": "start_engine", "get": "get_engine", "artifact": "artifact_engine"}
ROUTES = [
    ("POST", BASE, REQ, "start"),
    ("GET", RBASE, None, "get"),
    ("GET", ABASE, None, "artifact"),
]


def _t():
    from app.bot_verify import contract

    return contract


def _r():
    from app.routers import bot_verify

    return bot_verify


def _run(t, changeset_id="cs-1"):
    check = t.CheckResult(check=CHECKS[0], op_index=0, passed=True, evidence={"k": "v"})
    step = t.WalkStep(
        index=0,
        op_index=0,
        action="open",
        target="/odoo/sale",
        passed=True,
        screenshot_id=ART,
        dom_assertion=None,
    )
    layer = t.LayerResult(layer="live", status="passed", reason=None, checks=[check], steps=[step])
    return t.VerifyRun(
        run_id=RUN,
        changeset_id=changeset_id,
        status="queued",
        layers=[layer],
        started_at=datetime(2026, 10, 23, tzinfo=UTC),
        finished_at=None,
    )


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.mode: str | None = None

    def start(self, scope, body):
        t = _t()
        if body.changeset_id == "cs-ghost":
            raise t.BVError("NOT_FOUND", "Change set not found.")
        if self.mode == "target":
            raise t.BVError("TARGET_NOT_ALLOWED", "This connection isn't approved for that.")
        if self.mode == "applied":
            raise t.BVError("CHANGESET_NOT_APPLIED", "Apply the change set first.")
        self.calls.append("start")
        return _run(t, body.changeset_id)

    def get(self, scope, run_id):
        if RUN_OWNER.get(run_id) != scope.connection_id:
            raise _t().BVError("NOT_FOUND", "Verify run not found.")
        self.calls.append("get")
        return _run(_t())

    def artifact(self, scope, run_id, artifact_id):
        if ART_OWNER.get((run_id, artifact_id)) != scope.connection_id:
            raise _t().BVError("NOT_FOUND", "Artifact not found.")
        self.calls.append("artifact")
        return PNG


def _fake_scope(connection_id: str, x_ws: str = Header("ws-a"), x_role: str = Header("admin")):
    if x_role == "viewer":
        raise HTTPException(status_code=403, detail="Requires builder role or higher.")
    if OWNER.get(connection_id) != x_ws:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ScanScope(workspace_id=x_ws, connection_id=connection_id)


@pytest.fixture(autouse=True)
def _isolate_shared_state(monkeypatch):
    """Fresh gate registry, no Odoo client, dependency overrides restored afterwards."""
    from app import odoo_service, safety_dependency

    def _no_odoo(*_a, **_k):
        raise AssertionError("BV-01 must not build an Odoo client")

    monkeypatch.setattr(safety_dependency, "_REGISTRY", None)
    monkeypatch.setattr(odoo_service, "client_from_connection", _no_odoo)
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _provide(fn):
    def provider():
        return fn

    return provider


def _install(eng):
    r = _r()
    for key, dep in ENGINE_DEPS.items():
        app.dependency_overrides[getattr(r, dep)] = _provide(getattr(eng, key))


def _fake_deps():
    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[_r().bv_scope] = _fake_scope


@pytest.fixture
def engine():
    eng = FakeEngine()
    _fake_deps()
    _install(eng)
    return eng


@pytest.fixture
def client(engine):
    return TestClient(app)


def _call(c, method, path, body, cid=CONN_A, rid=RUN, aid=ART, **kw):
    return c.request(method, path.format(cid=cid, rid=rid, aid=aid), json=body, **kw)


def _env(res, status, code):
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail", "retry_after_s"}
    assert body["error"]["code"] == code and body["error"]["message"]
    return body["error"]


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(DOC_FIELDS))
def test_ac1_model_fields_match_epic_doc(name):
    assert set(getattr(_t(), name).model_fields) == DOC_FIELDS[name]


def test_ac1_pinned_literals_and_types():
    from typing import get_args

    t = _t()
    assert set(get_args(t.Layer)) == {"live", "walkthrough", "flows"}
    assert set(get_args(t.VerifyTarget)) == {"disposable_clone", "approved_connection"}
    assert set(get_args(t.RunStatus)) == {
        "queued",
        "running",
        "passed",
        "failed",
        "needs_human",
        "rolled_back",
    }
    assert set(get_args(t.LayerStatus)) == {"passed", "failed", "skipped"}
    assert set(get_args(t.StepAction)) == {"open", "click", "fill", "assert"}
    assert t.CheckResult.model_fields["evidence"].annotation == dict[str, str]
    assert t.VerifyRun.model_fields["started_at"].annotation is datetime


def test_ac1_check_must_be_known_and_extra_forbidden():
    t = _t()
    with pytest.raises(ValueError):
        t.CheckResult(check="made_up", op_index=0, passed=True, evidence={})
    with pytest.raises(ValueError):
        t.VerifyRunRequest(**REQ, x=1)


@pytest.mark.parametrize("layers", [[], ["live", "live"]])
def test_ac1_layers_min_one_no_duplicates(layers):
    with pytest.raises(ValueError):
        _t().VerifyRunRequest(**dict(REQ, layers=layers))


# AC2 / AC6 -----------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    r = _call(client, "POST", BASE, REQ)
    assert r.status_code == 202, r.text
    assert set(r.json()) == DOC_FIELDS["VerifyRun"]
    _t().VerifyRun.model_validate(r.json())
    g = _call(client, "GET", RBASE, None)
    assert g.status_code == 200 and set(g.json()) == DOC_FIELDS["VerifyRun"]
    a = _call(client, "GET", ABASE, None)
    assert a.status_code == 200 and a.headers["content-type"] == "image/png"
    assert a.content == PNG
    assert engine.calls == ["start", "get", "artifact"]


@pytest.mark.parametrize(
    "body,field",
    [
        ({k: v for k, v in REQ.items() if k != "changeset_id"}, "changeset_id"),
        (dict(REQ, layers=["smoke"]), "layers"),
        (dict(REQ, layers=[]), "layers"),
        (dict(REQ, target="production"), "target"),
        (dict(REQ, x=1), "x"),
    ],
)
def test_ac2_422_envelope(client, engine, body, field):
    err = _env(_call(client, "POST", BASE, body), 422, "VALIDATION")
    assert field in str(err["detail"]) or field in err["message"]
    assert engine.calls == []


@pytest.mark.parametrize(
    "mode,code", [("target", "TARGET_NOT_ALLOWED"), ("applied", "CHANGESET_NOT_APPLIED")]
)
def test_ac2_409_new_codes(client, engine, mode, code):
    engine.mode = mode
    _env(_call(client, "POST", BASE, REQ), 409, code)


@pytest.mark.parametrize("method,path,body,key", ROUTES)
def test_ac2_403_envelope(client, method, path, body, key):
    _env(_call(client, method, path, body, headers={"x-role": "viewer"}), 403, "ROLE_DENIED")


def test_ac2_only_new_codes():
    t = _t()
    new = set(t.BV_ERROR_CODES) - set(ERROR_HTTP)
    assert new == {"TARGET_NOT_ALLOWED", "CHANGESET_NOT_APPLIED"}
    assert set(t.BV_ERROR_CODES) == {
        "ROLE_DENIED",
        "VALIDATION",
        "NOT_FOUND",
        "TARGET_NOT_ALLOWED",
        "CHANGESET_NOT_APPLIED",
    }
    assert t.BVError("TARGET_NOT_ALLOWED", "m").status_code == 409
    with pytest.raises(ValueError):
        t.BVError("CONFLICT", "m")


def test_ac2_unknown_changeset_is_404(client, engine):
    _env(_call(client, "POST", BASE, dict(REQ, changeset_id="cs-ghost")), 404, "NOT_FOUND")


def test_ac6_default_engines_not_ready():
    _fake_deps()
    c = TestClient(app)
    for method, path, body, _ in ROUTES:
        _env(_call(c, method, path, body), 404, "NOT_FOUND")


# AC3 -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path,body,key", ROUTES)
def test_ac3_foreign_connection_404_same_as_random(client, engine, method, path, body, key):
    foreign = _call(client, method, path, body, cid=CONN_B)
    ghost = _call(client, method, path, body, cid="conn-ghost")
    _env(foreign, 404, "NOT_FOUND")
    assert foreign.content == ghost.content and engine.calls == []


def test_ac3_foreign_run_and_artifact_404_same_as_random(client, engine):
    for path, f, g in (
        (RBASE, {"rid": "run-b"}, {"rid": "run-ghost"}),
        (ABASE, {"rid": "run-b", "aid": "art-b"}, {"rid": "run-ghost", "aid": "art-ghost"}),
        (ABASE, {"aid": "art-b"}, {"aid": "art-ghost"}),
    ):
        foreign, ghost = (
            _call(client, "GET", path, None, **f),
            _call(client, "GET", path, None, **g),
        )
        _env(foreign, 404, "NOT_FOUND")
        assert foreign.content == ghost.content
    assert engine.calls == []


def test_ac3_every_bv_route_in_idor_registry():
    paths = app.openapi()["paths"]
    live = {
        (m.upper(), p)
        for p, ops in paths.items()
        if p.startswith("/api/connections/{connection_id}/verify-runs")
        for m in ops
    }
    assert live == set(reg.NF_BV_ROUTES) and len(live) == 4
    assert not reg.missing_registered_routes(paths, reg.NF_BV_ROUTES)
    assert all(p in reg.connection_scoped_paths(paths) for _, p in reg.NF_BV_ROUTES)


def _seed_two_workspaces():
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
        a_email, b_email = f"bv-a-{tag}@example.com", f"bv-b-{tag}@example.com"
        _a, ws_a, _ = signup_user(db, email=a_email, password="alice-pass-99", workspace_name="A")
        _b, _ws_b, _ = signup_user(db, email=b_email, password="bob-pass-99", workspace_name="B")
        for email in (a_email, b_email):
            u = db.query(User).filter(User.email == email).one()
            u.email_verified = True
            db.add(u)
        conn = OdooConnection(
            name="bv a",
            url="http://127.0.0.1:1",
            db_name="ingenium_wt_none",
            username="admin",
            secret_encrypted=encrypt_secret("x"),
            workspace_id=ws_a.id,
        )
        db.add(conn)
        db.commit()
        return b_email, conn.id
    finally:
        db.close()


def test_ac3_real_gate_cross_workspace_404_no_existence_leak(monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    b_email, victim = _seed_two_workspaces()
    ghost = "00000000-0000-0000-0000-000000000000"
    eng = FakeEngine()
    _install(eng)
    with TestClient(app) as bob:
        r = bob.post("/api/accounts/login", json={"email": b_email, "password": "bob-pass-99"})
        assert r.status_code == 200, r.text
        for method, path, body, _ in ROUTES:
            real, fake = (
                _call(bob, method, path, body, cid=victim),
                _call(bob, method, path, body, cid=ghost),
            )
            _env(real, 404, "NOT_FOUND")
            assert real.content == fake.content, path
    assert eng.calls == []


# AC4 -----------------------------------------------------------------------
def test_ac4_post_safety_spec_pinned():
    from app.safety_registry import ROUTE_OVERRIDES

    spec = ROUTE_OVERRIDES["POST:/api/connections/{connection_id}/verify-runs"]
    assert asdict(spec) == {
        "risk": "reversible",
        "snapshot": False,
        "dry_run_first": False,
        "confirm": "none",
        "odoo_mutation": False,
        "entitlement": None,
        "bypass_writes_paused": False,
    }


# AC5 -----------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "botVerify.ts"
TS_KEY_FIXTURE = dict(DOC_FIELDS)


def _ts_type_keys(src, name):
    m = re.search(r"export type " + name + r" =\s*(.*?);\n\n", src, re.S)
    assert m, f"{name} missing from botVerify.ts"
    return set(re.findall(r"\b([a-z_0-9]+)\??:", m.group(1)))


def test_ac5_openapi_components_match_ts_fixture():
    comps = app.openapi()["components"]["schemas"]
    for name, keys in TS_KEY_FIXTURE.items():
        assert set(comps[name]["properties"]) == keys, name


def test_ac5_ts_mirror_matches_fixture():
    src = TS_FILE.read_text()
    for name, keys in TS_KEY_FIXTURE.items():
        assert _ts_type_keys(src, name) == keys, name
    for code in ("TARGET_NOT_ALLOWED", "CHANGESET_NOT_APPLIED"):
        assert f'"{code}"' in src
    for fn in ("startVerifyRun", "getVerifyRun", "verifyArtifactUrl"):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -----------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    r, t = _r(), _t()
    src = Path(r.__file__).read_text() + Path(t.__file__).read_text()
    for bad in ("odoo_service", "client_from_connection", "execute_kw", "xmlrpc"):
        assert bad not in src, bad
    for dep in ENGINE_DEPS.values():
        assert src.count(f"Depends({dep})") == 1, dep
    assert len(set(ENGINE_DEPS.values())) == 3
