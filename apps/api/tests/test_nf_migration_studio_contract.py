"""MIG-01 contract tests: migration studio types, routes, B5 envelope, tenancy, safety, TS mirror.

Runs with a fake engine and a fake workspace scope, plus a real-gate tenancy check.
No Odoo: the import route is the first NF route marked odoo_mutation=True, and here
it only ever reaches a fake engine.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.migration_studio import contract as t
from app.routers import migrations as mg
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ERROR_HTTP, ScanError, ScanScope
from app.security import idor_registry as reg
from app.workspace_auth import require_app_auth

CONN_A = "conn-a"
CONN_B = "conn-b"
CONN_LIVE = "conn-live"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b", CONN_LIVE: "ws-a"}
LIVE = {CONN_LIVE}
MID = "mig-1"
MID_OWNER = {MID: CONN_A, "mig-b": CONN_B}
BASE = "/api/connections/{cid}/migrations"
MBASE = BASE + "/{mid}"
SOURCES = (
    "QuickBooks Online export",
    "Sage 50 CSV",
    "Zoho Books export",
    "Excel workbook",
    "Other ERP CSV",
)

# Field lists copied from docs/build-plan/new-features/INTEGRATE.md §MIG §6 (pinned 2026-10-22).
DOC_FIELDS = {
    "MigrationCreate": {"source"},
    "MigrationJob": {"id", "connection_id", "source", "created_at"},
    "MigrationFile": {"filename"},
    "MappingSet": {"mappings"},
    "EntityMapping": {"source", "entity", "column_map", "transforms"},
    "DryRunResult": {"entities"},
    "DryRunEntity": {"entity", "rows", "errors"},
    "RowError": {"row", "column", "message"},
    "ImportRequest": {"target_connection_id", "confirm"},
    "ImportResult": {"target_connection_id", "failed"},
    "ReconcileReport": {"lines"},
    "ReconcileLine": {"entity", "file_count", "odoo_count", "file_sum", "odoo_sum", "equal"},
}

MAPPING = {
    "mappings": [
        {
            "source": "Sage 50 CSV",
            "entity": "partners",
            "column_map": {"Name": "name", "Email": "email"},
            "transforms": {"Name": "strip"},
        }
    ]
}
IMPORT = {"target_connection_id": CONN_A, "confirm": False}
FILE = {"file": ("customers.csv", b"Name,Email\nAda,ada@example.com\n", "text/csv")}
# (method, path, json, files, key)
ROUTES = [
    ("POST", BASE, {"source": "Sage 50 CSV"}, None, "create"),
    ("POST", MBASE + "/files", None, FILE, "files"),
    ("GET", MBASE + "/mapping", None, None, "get_mapping"),
    ("PUT", MBASE + "/mapping", MAPPING, None, "put_mapping"),
    ("POST", MBASE + "/dry-run", None, None, "dry_run"),
    ("POST", MBASE + "/import", IMPORT, None, "import_"),
    ("GET", MBASE + "/reconcile", None, None, "reconcile"),
]
ENGINE_DEPS = {
    "create": "create_engine",
    "files": "files_engine",
    "get_mapping": "get_mapping_engine",
    "put_mapping": "put_mapping_engine",
    "dry_run": "dry_run_engine",
    "import_": "import_engine",
    "reconcile": "reconcile_engine",
}
SHAPES = {
    "create": "MigrationJob",
    "files": "MigrationFile",
    "get_mapping": "MappingSet",
    "put_mapping": "MappingSet",
    "dry_run": "DryRunResult",
    "import_": "ImportResult",
    "reconcile": "ReconcileReport",
}


def _err() -> t.RowError:
    return t.RowError(row=2, column="Email", message="Not an email address.")


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.uploads: list[tuple[str, bytes]] = []

    def _mid(self, scope, mid):
        if MID_OWNER.get(mid) != scope.connection_id:
            raise ScanError("NOT_FOUND", "Migration not found.")

    def create(self, scope, body):
        self.calls.append("create")
        return t.MigrationJob(
            id=MID,
            connection_id=scope.connection_id,
            source=body.source,
            created_at=datetime(2026, 10, 22, tzinfo=UTC),
        )

    def files(self, scope, mid, file):
        self._mid(scope, mid)
        self.calls.append("files")
        self.uploads.append((file.filename, file.file.read()))
        return t.MigrationFile(filename=file.filename)

    def get_mapping(self, scope, mid):
        self._mid(scope, mid)
        self.calls.append("get_mapping")
        return t.MappingSet.model_validate(MAPPING)

    def put_mapping(self, scope, mid, body):
        self._mid(scope, mid)
        self.calls.append("put_mapping")
        return body

    def dry_run(self, scope, mid):
        self._mid(scope, mid)
        self.calls.append("dry_run")
        return t.DryRunResult(entities=[t.DryRunEntity(entity="partners", rows=1, errors=[_err()])])

    def import_(self, scope, mid, target, body):
        self._mid(scope, mid)
        self.calls.append("import_")
        return t.ImportResult(target_connection_id=target.connection_id, failed=[_err()])

    def reconcile(self, scope, mid):
        self._mid(scope, mid)
        self.calls.append("reconcile")
        line = t.ReconcileLine(
            entity="opening balances",
            file_count=3,
            odoo_count=3,
            file_sum="1250.10",
            odoo_sum="1250.10",
            equal=True,
        )
        return t.ReconcileReport(lines=[line])


def _fake_scope(connection_id: str, x_ws: str = Header("ws-a"), x_role: str = Header("admin")):
    if x_role == "viewer":
        raise HTTPException(status_code=403, detail="Requires builder role or higher.")
    if OWNER.get(connection_id) != x_ws:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ScanScope(workspace_id=x_ws, connection_id=connection_id)


def _fake_target(x_ws: str = Header("ws-a")):
    def resolve(target_connection_id: str) -> t.ImportTarget:
        if OWNER.get(target_connection_id) != x_ws:
            raise HTTPException(status_code=404, detail="Connection not found")
        return t.ImportTarget(connection_id=target_connection_id, live=target_connection_id in LIVE)

    return resolve


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


def _install(eng: FakeEngine) -> None:
    for key, dep in ENGINE_DEPS.items():
        app.dependency_overrides[getattr(mg, dep)] = _provide(getattr(eng, key))


def _fake_deps() -> None:
    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[mg.mig_scope] = _fake_scope
    o[mg.import_target_resolver] = _fake_target


@pytest.fixture
def engine():
    eng = FakeEngine()
    _fake_deps()
    _install(eng)
    return eng


@pytest.fixture
def client(engine):
    return TestClient(app)


def _call(c, method, path, body, files, cid=CONN_A, mid=MID, **kw):
    return c.request(method, path.format(cid=cid, mid=mid), json=body, files=files, **kw)


def _assert_envelope(res, status: int, code: str):
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail", "retry_after_s"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    return body["error"]


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(DOC_FIELDS))
def test_ac1_model_fields_match_epic_doc(name):
    assert set(getattr(t, name).model_fields) == DOC_FIELDS[name]


def test_ac1_pinned_types():
    from typing import get_args

    assert set(get_args(t.MigrationSource)) == set(SOURCES)
    f = t.MigrationJob.model_fields
    assert f["id"].annotation is str and f["connection_id"].annotation is str
    assert f["created_at"].annotation is datetime
    assert f["source"].annotation == t.MigrationSource
    assert t.EntityMapping.model_fields["source"].annotation == t.MigrationSource
    assert t.EntityMapping.model_fields["column_map"].annotation == dict[str, str]
    assert t.EntityMapping.model_fields["transforms"].annotation == dict[str, str]
    assert t.DryRunEntity.model_fields["rows"].annotation is int
    assert t.RowError.model_fields["row"].annotation is int
    assert t.ImportRequest.model_fields["confirm"].annotation is bool
    assert t.ImportResult.model_fields["failed"].annotation == list[t.RowError]
    for k in ("file_sum", "odoo_sum"):
        assert t.ReconcileLine.model_fields[k].annotation is str
    assert set(t.MIG_ERROR_CODES) <= set(ERROR_HTTP)
    assert "CONFLICT" in t.MIG_ERROR_CODES and ERROR_HTTP["CONFLICT"] == 409


def test_ac1_row_is_one_based_and_sums_are_decimal_strings():
    with pytest.raises(ValueError):
        t.RowError(row=0, column="A", message="m")
    with pytest.raises(ValueError):
        t.ReconcileLine(
            entity="x", file_count=1, odoo_count=1, file_sum="abc", odoo_sum="1", equal=False
        )


# AC2 / AC6 -----------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    for method, path, body, files, key in ROUTES:
        r = _call(client, method, path, body, files)
        assert r.status_code == 200, (key, r.text)
        model = getattr(t, SHAPES[key])
        model.model_validate(r.json())
        assert set(r.json()) == DOC_FIELDS[SHAPES[key]], key
    assert engine.calls == [k for *_, k in ROUTES]


def test_ac2_files_is_multipart_file_part_and_bytes_not_echoed(client, engine):
    r = _call(client, "POST", MBASE + "/files", None, FILE)
    assert r.json() == {"filename": "customers.csv"}
    assert engine.uploads == [("customers.csv", FILE["file"][1])]
    params = app.openapi()["paths"]["/api/connections/{connection_id}/migrations/{mid}/files"]
    content = params["post"]["requestBody"]["content"]
    assert list(content) == ["multipart/form-data"]


def test_ac2_import_live_without_confirm_is_409_conflict(client, engine):
    body = {"target_connection_id": CONN_LIVE, "confirm": False}
    err = _assert_envelope(_call(client, "POST", MBASE + "/import", body, None), 409, "CONFLICT")
    assert "confirm" in (err["message"] + str(err["detail"]))
    assert engine.calls == []


def test_ac2_import_live_with_confirm_is_not_409(client, engine):
    body = {"target_connection_id": CONN_LIVE, "confirm": True}
    r = _call(client, "POST", MBASE + "/import", body, None)
    assert r.status_code == 200, r.text
    assert r.json()["target_connection_id"] == CONN_LIVE
    assert engine.calls == ["import_"]


def test_ac2_import_non_live_needs_no_confirm(client, engine):
    r = _call(client, "POST", MBASE + "/import", IMPORT, None)
    assert r.status_code == 200 and engine.calls == ["import_"]


@pytest.mark.parametrize("method,path,body,files,key", ROUTES)
def test_ac2_403_envelope(client, method, path, body, files, key):
    r = _call(client, method, path, body, files, headers={"x-role": "viewer"})
    _assert_envelope(r, 403, "ROLE_DENIED")


@pytest.mark.parametrize("method,path,body,files,key", ROUTES)
def test_ac2_404_envelope_unknown_connection(client, method, path, body, files, key):
    _assert_envelope(_call(client, method, path, body, files, cid="conn-missing"), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "method,suffix,body,files,field",
    [
        ("POST", "", {}, None, "source"),
        ("POST", "", {"source": "Tally"}, None, "source"),
        ("POST", "", {"source": "Sage 50 CSV", "x": 1}, None, "x"),
        ("POST", "/{mid}/files", None, None, "file"),
        ("PUT", "/{mid}/mapping", {"mappings": [{"entity": "partners"}]}, None, "source"),
        ("PUT", "/{mid}/mapping", {}, None, "mappings"),
        ("POST", "/{mid}/import", {"confirm": False}, None, "target_connection_id"),
        ("POST", "/{mid}/import", {"target_connection_id": CONN_A}, None, "confirm"),
        ("POST", "/{mid}/import", dict(IMPORT, x=1), None, "x"),
    ],
)
def test_ac2_422_envelope_names_field(client, engine, method, suffix, body, files, field):
    r = client.request(method, (BASE + suffix).format(cid=CONN_A, mid=MID), json=body, files=files)
    err = _assert_envelope(r, 422, "VALIDATION")
    assert field in str(err["detail"]) or field in err["message"]
    assert engine.calls == []


def test_ac6_default_engine_is_not_ready_envelope():
    _fake_deps()
    c = TestClient(app)
    for method, path, body, files, _key in ROUTES:
        _assert_envelope(_call(c, method, path, body, files), 404, "NOT_FOUND")


# AC3 -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path,body,files,key", ROUTES)
def test_ac3_cross_workspace_404(client, engine, method, path, body, files, key):
    r = _call(client, method, path, body, files, headers={"x-ws": "ws-b"})
    _assert_envelope(r, 404, "NOT_FOUND")
    assert engine.calls == []


@pytest.mark.parametrize("method,path,body,files,key", ROUTES[1:])
def test_ac3_foreign_mid_404_same_as_random(client, engine, method, path, body, files, key):
    foreign = _call(client, method, path, body, files, mid="mig-b")
    ghost = _call(client, method, path, body, files, mid="mig-ghost")
    _assert_envelope(foreign, 404, "NOT_FOUND")
    assert foreign.content == ghost.content


def test_ac3_foreign_import_target_404_same_as_random(client, engine):
    def go(target):
        body = {"target_connection_id": target, "confirm": True}
        return _call(client, "POST", MBASE + "/import", body, None)

    foreign, ghost = go(CONN_B), go("conn-ghost")
    _assert_envelope(foreign, 404, "NOT_FOUND")
    assert foreign.content == ghost.content
    assert engine.calls == []


def test_ac3_every_mig_route_in_idor_registry():
    paths = app.openapi()["paths"]
    live = {(m.upper(), p) for p, ops in paths.items() if "/migrations" in p for m in ops}
    live = {x for x in live if x[1].startswith("/api/connections/{connection_id}/migrations")}
    assert live == set(reg.NF_MIG_ROUTES) and len(live) == 7
    assert not reg.missing_registered_routes(paths, reg.NF_MIG_ROUTES)
    assert all(p in reg.connection_scoped_paths(paths) for _, p in reg.NF_MIG_ROUTES)


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
        a_email, b_email = f"mig-a-{tag}@example.com", f"mig-b-{tag}@example.com"
        _a, ws_a, _ = signup_user(db, email=a_email, password="alice-pass-99", workspace_name="A")
        _b, ws_b, _ = signup_user(db, email=b_email, password="bob-pass-99", workspace_name="B")
        for email in (a_email, b_email):
            u = db.query(User).filter(User.email == email).one()
            u.email_verified = True
            db.add(u)
        ids = {}
        for key, ws in (("a", ws_a), ("b", ws_b)):
            conn = OdooConnection(
                name=f"mig {key}",
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
    eng = FakeEngine()
    _install(eng)
    with TestClient(app) as bob:
        r = bob.post("/api/accounts/login", json={"email": b_email, "password": "bob-pass-99"})
        assert r.status_code == 200, r.text
        for method, path, body, files, _key in ROUTES:
            real = _call(bob, method, path, body, files, cid=ids["a"])
            fake = _call(bob, method, path, body, files, cid=ghost)
            _assert_envelope(real, 404, "NOT_FOUND")
            assert real.status_code == fake.status_code and real.content == fake.content, path
        # Bob's own source connection, Alice's connection as import target.
        body = {"target_connection_id": ids["a"], "confirm": True}
        real = _call(bob, "POST", MBASE + "/import", body, None, cid=ids["b"])
        body["target_connection_id"] = ghost
        fake = _call(bob, "POST", MBASE + "/import", body, None, cid=ids["b"])
        assert real.status_code == fake.status_code and real.content == fake.content
    assert eng.calls == []


# AC4 -----------------------------------------------------------------------
def test_ac4_owned_paused_connection_refuses_writes(monkeypatch):
    """Owner A, writes paused: POST/PUT refuse (403 writes_paused); GETs still read."""
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    _b, ids, a_email = _seed_two_workspaces(paused=True)
    eng = FakeEngine()
    _install(eng)
    MID_OWNER[MID] = ids["a"]
    try:
        with TestClient(app) as alice:
            r = alice.post(
                "/api/accounts/login", json={"email": a_email, "password": "alice-pass-99"}
            )
            assert r.status_code == 200, r.text
            for method, path, body, files, key in ROUTES:
                res = _call(alice, method, path, body, files, cid=ids["a"])
                if method in ("POST", "PUT"):
                    err = _assert_envelope(res, 403, "ROLE_DENIED")
                    assert err["detail"]["error"] == "writes_paused", key
                else:
                    assert res.status_code == 200, (key, res.text)
    finally:
        MID_OWNER[MID] = CONN_A
    assert eng.calls == ["get_mapping", "reconcile"]


def _fields(spec):
    return asdict(spec) if is_dataclass(spec) else spec.model_dump()


def test_ac4_mig_safety_specs_pinned():
    from app.safety_registry import ROUTE_OVERRIDES

    pre = "/api/connections/{connection_id}/migrations"
    plans = _fields(ROUTE_OVERRIDES["POST:/api/inbox/plans"])
    for key in ("POST:" + pre, "POST:" + pre + "/{mid}/files", "PUT:" + pre + "/{mid}/mapping"):
        assert _fields(ROUTE_OVERRIDES[key]) == plans, key
    dry = ROUTE_OVERRIDES["POST:" + pre + "/{mid}/dry-run"]
    assert (dry.risk, dry.odoo_mutation, dry.confirm, dry.bypass_writes_paused) == (
        "read",
        False,
        "none",
        False,
    )
    imp = ROUTE_OVERRIDES["POST:" + pre + "/{mid}/import"]
    assert imp.odoo_mutation is True
    assert imp.risk == "reversible" and imp.bypass_writes_paused is False
    # Live confirmation is the body's confirm flag (409 CONFLICT), not a gate header.
    assert imp.confirm == "none" and imp.dry_run_first is False


# AC5 -----------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "migration.ts"
TS_KEY_FIXTURE = dict(DOC_FIELDS)


def _ts_type_keys(src: str, name: str) -> set[str]:
    m = re.search(r"export type " + name + r" =\s*(.*?);\n\n", src, re.S)
    assert m, f"{name} missing from migration.ts"
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
    for s in SOURCES:
        assert f'"{s}"' in src, s
    for fn in (
        "createMigration",
        "uploadMigrationFile",
        "getMigrationMapping",
        "putMigrationMapping",
        "dryRunMigration",
        "importMigration",
        "reconcileMigration",
    ):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -----------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    src = Path(mg.__file__).read_text() + Path(t.__file__).read_text()
    assert "odoo_client" not in src and "execute_kw" not in src and "_client(" not in src
    assert "xmlrpc" not in src
    for dep in ENGINE_DEPS.values():
        assert src.count(f"Depends({dep})") == 1, dep


# AC2 fail-safe Live check (Reviewer B1): the real resolver, not the fake one.
def _real_resolver_client(monkeypatch, eng, mode):
    from types import SimpleNamespace

    from app.db import get_db

    _fake_deps()
    del app.dependency_overrides[mg.import_target_resolver]
    app.dependency_overrides[get_db] = lambda: None
    monkeypatch.setattr(mg, "get_workspace_auth", lambda request: None)
    monkeypatch.setattr(
        mg,
        "get_scoped_connection_or_404",
        lambda db, cid, auth: SimpleNamespace(id=cid, write_mode=mode, workspace_id="ws-a"),
    )
    _install(eng)
    return TestClient(app)


@pytest.mark.parametrize("mode", [None, "", "PRODUCTION", " production ", "unknown"])
def test_ac2_unknown_write_mode_is_live_409_without_confirm(monkeypatch, mode):
    eng = FakeEngine()
    c = _real_resolver_client(monkeypatch, eng, mode)
    _assert_envelope(_call(c, "POST", MBASE + "/import", IMPORT, None), 409, "CONFLICT")
    assert eng.calls == []


@pytest.mark.parametrize("mode", ["standard", "observer", " Standard "])
def test_ac2_safe_write_mode_imports_without_confirm(monkeypatch, mode):
    eng = FakeEngine()
    c = _real_resolver_client(monkeypatch, eng, mode)
    r = _call(c, "POST", MBASE + "/import", IMPORT, None)
    assert r.status_code == 200, r.text
    assert eng.calls == ["import_"]
