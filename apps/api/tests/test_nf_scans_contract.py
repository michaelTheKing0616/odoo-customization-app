"""SCAN-01 contract tests: scan types, routes, B5 error envelope, tenancy, TS mirror.

Runs with a fake engine and a fake workspace scope. No app Postgres, no Odoo.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402
from app.routers import scans as scans_router  # noqa: E402
from app.safety_dependency import enforce_safety_gate  # noqa: E402
from app.scans import contract as c  # noqa: E402
from app.security import idor_registry as reg  # noqa: E402
from app.workspace_auth import require_app_auth  # noqa: E402

CONN_A = "conn-a"
CONN_B = "conn-b"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b"}
BASE = "/api/connections/{cid}"

# Field lists copied from docs/build-plan/new-features/00_BASELINE.md B5 (L105-108).
B5_FIELDS = {
    "ScanRun": {
        "id", "connection_id", "scan_id", "status", "started_at", "finished_at",
        "areas", "budget_ms", "odoo_version", "schema_fingerprint",
    },
    "AreaResult": {
        "area", "status", "rows_read", "sampled", "duration_ms", "findings_count", "error_code",
    },
    "Finding": {
        "id", "scan_id", "area", "severity", "title", "plain_why", "count", "sample_ids",
        "model", "evidence", "fix", "docs_url",
    },
    "FixRef": {"kind", "plan_template", "params"},
}


def _run(conn: str, run_id: str = "run-1", status: str = "running") -> c.ScanRun:
    return c.ScanRun(
        id=run_id,
        connection_id=conn,
        scan_id="debt",
        status=status,
        started_at=datetime(2026, 10, 22, tzinfo=UTC),
        finished_at=None,
        areas=[
            c.AreaResult(
                area="views", status="done", rows_read=10, sampled=False,
                duration_ms=12, findings_count=2, error_code=None,
            )
        ],
        budget_ms=60000,
        odoo_version="18.0",
        schema_fingerprint="abc",
    )


def _finding(i: int, sev: str = "high", area: str = "views") -> c.Finding:
    return c.Finding(
        id=f"f-{i}", scan_id="debt", area=area, severity=sev, title=f"Finding {i}",
        plain_why="Why it matters.", count=1, sample_ids=[1, 2], model="res.partner",
        evidence={"k": "v"}, fix=c.FixRef(kind="plan", plan_template="hide_field", params={}),
        docs_url=None,
    )


class FakeEngine:
    """Runs belong to the connection that started them."""

    def __init__(self) -> None:
        self.runs: dict[str, c.ScanRun] = {"run-1": _run(CONN_A)}
        self.findings = [_finding(i, "high" if i % 2 else "low", "views" if i < 300 else "menus")
                         for i in range(450)]
        self.calls: list[str] = []

    def _own(self, scope: c.ScanScope, run_id: str) -> c.ScanRun:
        run = self.runs.get(run_id)
        if run is None or run.connection_id != scope.connection_id:
            raise c.ScanError("NOT_FOUND", "That scan doesn't exist.")
        return run

    def start(self, scope, body):
        self.calls.append("start")
        if body.params.get("reuse"):
            return self.runs["run-1"], False
        run = _run(scope.connection_id, "run-new", "queued")
        self.runs[run.id] = run
        return run, True

    def get(self, scope, run_id):
        self.calls.append("get")
        return self._own(scope, run_id)

    def findings_page(self, scope, run_id, q):
        self.calls.append("findings")
        self._own(scope, run_id)
        rows = [f for f in self.findings
                if (q.severity is None or f.severity == q.severity)
                and (q.area is None or f.area == q.area)]
        page = rows[q.offset: q.offset + q.limit]
        return page, q.offset + q.limit < len(rows)

    def cancel(self, scope, run_id):
        self.calls.append("cancel")
        run = self._own(scope, run_id)
        if run.status in ("done", "failed", "cancelled"):
            raise c.ScanError("CONFLICT", "This scan has already finished.")
        return run.model_copy(update={"status": "cancelled"})

    def plan(self, scope, fid):
        self.calls.append("plan")
        if fid != "f-1" or scope.connection_id != CONN_A:
            raise c.ScanError("NOT_FOUND", "That finding doesn't exist.")
        return c.PlanDraftRef(draft_id="draft-1")


def _fake_scope(connection_id: str, x_ws: str = Header("ws-a"), x_role: str = Header("admin")):
    if x_role == "viewer":
        raise HTTPException(status_code=403, detail="Requires builder role or higher.")
    if OWNER.get(connection_id) != x_ws:
        raise HTTPException(status_code=404, detail="Connection not found")
    return c.ScanScope(workspace_id=x_ws, connection_id=connection_id)


@pytest.fixture(autouse=True)
def _isolate_shared_state(monkeypatch):
    """Other test modules stub the gate registry at import (test_reg_np_dev sets
    safety_dependency._REGISTRY to one route). Force a full rebuild for this module's
    tests and restore the previous registry and dependency overrides afterwards."""
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
    o[scans_router.scan_scope] = _fake_scope
    o[scans_router.start_engine] = lambda: eng.start
    o[scans_router.get_engine] = lambda: eng.get
    o[scans_router.findings_engine] = lambda: eng.findings_page
    o[scans_router.cancel_engine] = lambda: eng.cancel
    o[scans_router.plan_engine] = lambda: eng.plan
    yield eng


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


ROUTES = [
    ("POST", BASE + "/scans", {"scan_id": "debt", "params": {}}),
    ("GET", BASE + "/scans/run-1", None),
    ("GET", BASE + "/scans/run-1/findings", None),
    ("POST", BASE + "/scans/run-1/cancel", None),
    ("POST", BASE + "/findings/f-1/plan", None),
]


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(B5_FIELDS))
def test_ac1_model_fields_match_b5(name):
    assert set(getattr(c, name).model_fields) == B5_FIELDS[name]


def test_ac1_enums_and_limits():
    with pytest.raises(ValueError):
        c.AreaResult(area="x", status="bogus", rows_read=0, sampled=False, duration_ms=0,
                     findings_count=0, error_code=None)
    with pytest.raises(ValueError):
        _finding(1).model_copy(update={}).model_validate(
            {**_finding(1).model_dump(), "sample_ids": list(range(21))})
    with pytest.raises(ValueError):
        c.FixRef(kind="other", plan_template="x", params={})
    assert set(c.ERROR_HTTP) <= {
        "ODOO_UNREACHABLE", "ODOO_ACCESS_MISSING", "ROLE_DENIED", "HOSTING_NOT_SUPPORTED",
        "MONEY_GUARD_REFUSED", "RECEIPT_REQUIRED", "RATE_LIMITED", "VALIDATION", "NOT_FOUND",
        "CONFLICT",
    }
    assert c.ERROR_HTTP["NOT_FOUND"] == 404 and c.ERROR_HTTP["VALIDATION"] == 422


# AC2 / AC5 -------------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    r = client.post(BASE.format(cid=CONN_A) + "/scans", json={"scan_id": "debt", "params": {}})
    assert r.status_code == 202, r.text
    c.ScanRun.model_validate(r.json())
    r = client.post(BASE.format(cid=CONN_A) + "/scans",
                    json={"scan_id": "debt", "params": {"reuse": True}})
    assert r.status_code == 200 and r.json()["id"] == "run-1"
    r = client.get(BASE.format(cid=CONN_A) + "/scans/run-1")
    assert r.status_code == 200 and c.ScanRun.model_validate(r.json()).id == "run-1"
    r = client.get(BASE.format(cid=CONN_A) + "/scans/run-1/findings")
    assert r.status_code == 200
    page = c.FindingsPage.model_validate(r.json())
    assert set(r.json()) == {"items", "next_cursor"} and page.items
    r = client.post(BASE.format(cid=CONN_A) + "/scans/run-1/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    r = client.post(BASE.format(cid=CONN_A) + "/findings/f-1/plan")
    assert r.status_code == 200 and r.json() == {"draft_id": "draft-1"}
    assert engine.calls == ["start", "start", "get", "findings", "cancel", "plan"]


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac2_403_envelope(client, method, path, body):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-role": "viewer"})
    _assert_envelope(r, 403, "ROLE_DENIED")


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac2_404_envelope_unknown_ids(client, method, path, body):
    p = path.format(cid=CONN_A).replace("run-1", "nope").replace("f-1", "nope")
    if p == path.format(cid=CONN_A):  # POST /scans has no child id: unknown connection
        p = path.format(cid="conn-missing")
    _assert_envelope(client.request(method, p, json=body), 404, "NOT_FOUND")


def test_ac2_422_envelope_names_field(client):
    err = _assert_envelope(client.post(BASE.format(cid=CONN_A) + "/scans", json={"params": {}}),
                           422, "VALIDATION")
    assert "scan_id" in str(err["detail"])


@pytest.mark.parametrize("q", ["limit=201", "limit=0", "severity=urgent", "cursor=%%%bad"])
def test_ac2_ac7_422_envelope_findings_query(client, q):
    r = client.get(BASE.format(cid=CONN_A) + f"/scans/run-1/findings?{q}")
    _assert_envelope(r, 422, "VALIDATION")


def test_ac2_engine_conflict_envelope(client, engine):
    engine.runs["run-1"] = _run(CONN_A, status="done")
    _assert_envelope(client.post(BASE.format(cid=CONN_A) + "/scans/run-1/cancel"),
                     409, "CONFLICT")


# AC3 -------------------------------------------------------------------------
@pytest.mark.parametrize("method,path,body", ROUTES)
def test_ac3_cross_workspace_404(client, engine, method, path, body):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-ws": "ws-b"})
    _assert_envelope(r, 404, "NOT_FOUND")
    # B using its own connection with A's run/finding ids also gets 404
    if "run-1" in path or "f-1" in path:
        r = client.request(method, path.format(cid=CONN_B), json=body, headers={"x-ws": "ws-b"})
        _assert_envelope(r, 404, "NOT_FOUND")


def test_ac3_every_scan_route_in_idor_registry():
    paths = app.openapi()["paths"]
    live = {
        (m.upper(), p) for p, ops in paths.items() if "/scans" in p or "/findings/" in p
        for m in ops if p.startswith("/api/connections/")
    }
    assert len(live) == 5
    assert live == set(reg.NF_SCAN_ROUTES)
    assert not reg.missing_registered_routes(paths, reg.NF_SCAN_ROUTES)
    assert all(p in reg.connection_scoped_paths(paths) for _, p in reg.NF_SCAN_ROUTES)


# AC5 -------------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "scans.ts"
TS_KEY_FIXTURE = {
    **B5_FIELDS,
    "StartScanRequest": {"scan_id", "params"},
    "FindingsPage": {"items", "next_cursor"},
    "PlanDraftRef": {"draft_id"},
    "ScanErrorBody": {"code", "message", "detail", "retry_after_s"},
}


def _ts_type_keys(src: str, name: str) -> set[str]:
    m = re.search(r"export type " + name + r" = \{(.*?)\n\};", src, re.S)
    assert m, f"{name} missing from scans.ts"
    return set(re.findall(r"^\s+([a-z_]+)\??:", m.group(1), re.M))


def test_ac5_openapi_components_match_ts_fixture():
    comps = app.openapi()["components"]["schemas"]
    for name, keys in TS_KEY_FIXTURE.items():
        assert name in comps, name
        assert set(comps[name]["properties"]) == keys, name


def test_ac5_ts_mirror_matches_fixture():
    src = TS_FILE.read_text()
    for name, keys in TS_KEY_FIXTURE.items():
        assert _ts_type_keys(src, name) == keys, name
    for fn in ("startScan", "getScan", "listFindings", "cancelScan", "planFinding"):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -------------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    src = Path(scans_router.__file__).read_text() + Path(c.__file__).read_text()
    assert "odoo_client" not in src and "execute_kw" not in src and "_client(" not in src
    for dep in ("start_engine", "get_engine", "findings_engine", "cancel_engine", "plan_engine"):
        assert src.count(f"Depends({dep})") == 1, dep


# AC7 -------------------------------------------------------------------------
def test_ac7_cursor_paging_and_filters(client):
    url = BASE.format(cid=CONN_A) + "/scans/run-1/findings"
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        r = client.get(url, params={"limit": 200, **({"cursor": cursor} if cursor else {})})
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) <= 200
        seen += [f["id"] for f in body["items"]]
        cursor = body["next_cursor"]
        pages += 1
        if cursor is None:
            break
        assert not cursor.isdigit()  # opaque, not a raw offset
    assert pages == 3 and len(seen) == 450 and len(set(seen)) == 450
    r = client.get(url, params={"severity": "high", "area": "menus"})
    items = r.json()["items"]
    assert items and all(f["severity"] == "high" and f["area"] == "menus" for f in items)
    assert client.get(url).json()["items"].__len__() == c.DEFAULT_PAGE_SIZE


def test_ac7_cursor_bound_to_filters(client):
    url = BASE.format(cid=CONN_A) + "/scans/run-1/findings"
    cur = client.get(url, params={"severity": "high"}).json()["next_cursor"]
    r = client.get(url, params={"severity": "low", "cursor": cur})
    _assert_envelope(r, 422, "VALIDATION")


# Real gate + real scope: workspace B probing workspace A's ids ------------------
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
        a_email, b_email = f"scan-a-{tag}@example.com", f"scan-b-{tag}@example.com"
        _a, ws_a, _ = signup_user(db, email=a_email, password="alice-pass-99", workspace_name="A")
        _b, ws_b, _ = signup_user(db, email=b_email, password="bob-pass-99", workspace_name="B")
        for email in (a_email, b_email):
            u = db.query(User).filter(User.email == email).one()
            u.email_verified = True
            db.add(u)
        ids = {}
        for key, ws in (("a", ws_a), ("b", ws_b)):
            conn = OdooConnection(
                name=f"scan {key}", url="http://127.0.0.1:1", db_name="ingenium_wt_none",
                username="admin", secret_encrypted=encrypt_secret("x"), workspace_id=ws.id,
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
    b_email, ids, _a_email = _seed_two_workspaces(paused)
    ghost = "00000000-0000-0000-0000-000000000000"
    with TestClient(app) as bob:
        r = bob.post("/api/accounts/login", json={"email": b_email, "password": "bob-pass-99"})
        assert r.status_code == 200, r.text
        for method, path, body in ROUTES:
            for cid in (ids["a"], ids["b"]):
                if cid == ids["b"] and "run-1" not in path and "f-1" not in path:
                    continue
                real = bob.request(method, path.format(cid=cid), json=body)
                fake_cid = ghost if cid == ids["a"] else cid
                fake_path = path.format(cid=fake_cid).replace("run-1", "ghost-run")
                fake = bob.request(method, fake_path.replace("f-1", "ghost-f"), json=body)
                _assert_envelope(real, 404, "NOT_FOUND")
                assert real.json() == fake.json(), f"{method} {path} differs for a real id"


def _provide(fn):
    def provider():
        return fn

    return provider


def test_ac4_owned_paused_connection_gate(monkeypatch):
    """Owner A, writes paused: cancel and plan refuse (403 writes_paused); start still runs."""
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    _b, ids, a_email = _seed_two_workspaces(paused=True)
    eng = FakeEngine()
    eng.runs["run-1"] = _run(ids["a"])
    o = app.dependency_overrides
    for dep, fn in (
        (scans_router.start_engine, eng.start),
        (scans_router.cancel_engine, eng.cancel),
        (scans_router.plan_engine, eng.plan),
    ):
        o[dep] = _provide(fn)
    base = BASE.format(cid=ids["a"])
    with TestClient(app) as alice:
        r = alice.post("/api/accounts/login", json={"email": a_email, "password": "alice-pass-99"})
        assert r.status_code == 200, r.text
        for path in ("/scans/run-1/cancel", "/findings/f-1/plan"):
            err = _assert_envelope(alice.post(base + path), 403, "ROLE_DENIED")
            assert err["detail"]["error"] == "writes_paused", path
        r = alice.post(base + "/scans", json={"scan_id": "debt", "params": {}})
        assert r.status_code == 202, r.text
        c.ScanRun.model_validate(r.json())
    assert eng.calls == ["start"]


# AC4: pin the scan SafetySpecs ---------------------------------------------------
def test_ac4_scan_safety_specs_pinned():
    from dataclasses import asdict, is_dataclass

    from app.safety_registry import ROUTE_OVERRIDES

    def fields(spec):
        return asdict(spec) if is_dataclass(spec) else spec.model_dump()

    pre = "POST:/api/connections/{connection_id}"
    start = ROUTE_OVERRIDES[pre + "/scans"]
    assert (start.risk, start.odoo_mutation, start.confirm, start.bypass_writes_paused) == (
        "read", False, "none", True)
    cancel = ROUTE_OVERRIDES[pre + "/scans/{run_id}/cancel"]
    assert (cancel.risk, cancel.odoo_mutation, cancel.confirm, cancel.bypass_writes_paused) == (
        "read", False, "none", False)
    plan = ROUTE_OVERRIDES[pre + "/findings/{fid}/plan"]
    inbox = ROUTE_OVERRIDES["POST:/api/inbox/plans"]
    assert fields(plan) == fields(inbox)
    assert plan.bypass_writes_paused is False
