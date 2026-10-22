"""NG-01 contract tests: Nigeria pack types, routes, B5 envelope, tenancy, safety, TS mirror.

Runs with a fake engine and a fake workspace scope, plus a real-gate tenancy check.
No Odoo.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from app.l10n_ng import contract as t
from app.main import app
from app.routers import l10n_ng as ng
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ERROR_HTTP, Finding, ScanScope
from app.security import idor_registry as reg
from app.workspace_auth import require_app_auth

CONN_A = "conn-a"
CONN_B = "conn-b"
OWNER = {CONN_A: "ws-a", CONN_B: "ws-b"}
BASE = "/api/connections/{cid}/l10n-ng"

# Field lists copied from docs/build-plan/new-features/LOCALIZATION.md §NG §6 (pinned 2026-10-22).
DOC_FIELDS = {
    "NgDetect": {"country", "l10n_ng_installed", "l10n_ng_available", "taxes"},
    "NgTax": {"id", "name", "amount", "type_tax_use"},
    "NgPlanResponse": {"plan_id"},
    "EinvoiceReadiness": {"items", "sample_payload"},
    "PayrollCompute": {"rows", "rules_version"},
    "PayrollRow": {"employee_ref", "gross", "paye", "pension_employee", "pension_employer"},
    "BankConvert": {"bank", "rows", "csv_id", "try_loading"},
    "TryLoading": {"ok", "messages"},
    "PayrollComputeRequest": {"upload_id", "from_hr", "period"},
    "BankConvertRequest": {"upload_id", "bank"},
}

PAY = {"from_hr": True, "period": "2026-09"}
BANK = {"upload_id": "up-1", "bank": "gtbank"}
ROUTES = [
    ("GET", BASE + "/detect", None, "detect"),
    ("POST", BASE + "/plan", None, "plan"),
    ("GET", BASE + "/einvoice-readiness", None, "readiness"),
    ("POST", BASE + "/payroll-compute", PAY, "payroll"),
    ("POST", BASE + "/bank/convert", BANK, "bank"),
]
ENGINE_DEPS = {
    "detect": "detect_engine",
    "plan": "plan_engine",
    "readiness": "readiness_engine",
    "payroll": "payroll_engine",
    "bank": "bank_engine",
}


def _finding() -> Finding:
    return Finding(
        id="f-1",
        scan_id="einvoice_ng",
        area="tax",
        severity="medium",
        title="Customers without a TIN",
        plain_why="E-invoices need a TIN.",
        count=3,
        sample_ids=[1, 2, 3],
        model="res.partner",
    )


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def detect(self, scope):
        self.calls.append("detect")
        return t.NgDetect(
            country="NG",
            l10n_ng_installed=False,
            l10n_ng_available=True,
            taxes=[t.NgTax(id=1, name="VAT 7.5%", amount=Decimal("7.5"), type_tax_use="sale")],
        )

    def plan(self, scope):
        self.calls.append("plan")
        return t.NgPlanResponse(plan_id="plan-1")

    def readiness(self, scope):
        self.calls.append("readiness")
        return t.EinvoiceReadiness(items=[_finding()], sample_payload={"invoice": "INV/1"})

    def payroll(self, scope, body):
        self.calls.append("payroll")
        row = t.PayrollRow(
            employee_ref="E1",
            gross=Decimal("500000.00"),
            paye=Decimal("41250.10"),
            pension_employee=Decimal("40000.00"),
            pension_employer=Decimal("50000.00"),
        )
        return t.PayrollCompute(rows=[row], rules_version="ng-2026.1")

    def bank(self, scope, body):
        self.calls.append("bank")
        return t.BankConvert(
            bank=body.bank,
            rows=[{"date": "2026-09-01", "amount": "100.00"}],
            csv_id="csv-1",
            try_loading=t.TryLoading(ok=True, messages=[]),
        )


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


def _provide(fn):
    def provider():
        return fn

    return provider


def _install(eng: FakeEngine) -> None:
    for key, dep in ENGINE_DEPS.items():
        app.dependency_overrides[getattr(ng, dep)] = _provide(getattr(eng, key))


@pytest.fixture
def engine():
    eng = FakeEngine()
    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[ng.ng_scope] = _fake_scope
    _install(eng)
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


# AC1 -----------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(DOC_FIELDS))
def test_ac1_model_fields_match_epic_doc(name):
    assert set(getattr(t, name).model_fields) == DOC_FIELDS[name]


def test_ac1_readiness_items_are_shared_finding():
    assert t.EinvoiceReadiness.model_fields["items"].annotation == list[Finding]


def test_ac1_payroll_exactly_one_source_and_money_decimal():
    t.PayrollComputeRequest(upload_id="u-1", period="2026-09")
    t.PayrollComputeRequest(from_hr=True, period="2026-09")
    for bad in (
        {"period": "2026-09"},
        {"upload_id": "u", "from_hr": True, "period": "2026-09"},
        {"from_hr": True, "period": "2026-13"},
        {"from_hr": True},
    ):
        with pytest.raises(ValueError):
            t.PayrollComputeRequest(**bad)
    for f in ("gross", "paye", "pension_employee", "pension_employer"):
        assert t.PayrollRow.model_fields[f].annotation is Decimal, f
    assert t.NgTax.model_fields["amount"].annotation is Decimal
    assert set(t.NG_ERROR_CODES) <= set(ERROR_HTTP)


# AC2 / AC6 -----------------------------------------------------------------
def test_ac2_ac6_routes_return_documented_shapes(client, engine):
    shapes = {
        "detect": t.NgDetect,
        "plan": t.NgPlanResponse,
        "readiness": t.EinvoiceReadiness,
        "payroll": t.PayrollCompute,
        "bank": t.BankConvert,
    }
    for method, path, body, key in ROUTES:
        r = client.request(method, path.format(cid=CONN_A), json=body)
        assert r.status_code == 200, (key, r.text)
        shapes[key].model_validate(r.json())
        assert set(r.json()) == DOC_FIELDS[shapes[key].__name__], key
    assert engine.calls == [k for *_, k in ROUTES]


def test_ac2_money_keeps_exact_figures(client):
    r = client.post(BASE.format(cid=CONN_A) + "/payroll-compute", json=PAY)
    assert Decimal(r.json()["rows"][0]["paye"]) == Decimal("41250.10")


def test_ac2_plan_takes_no_body(client, engine):
    r = client.post(BASE.format(cid=CONN_A) + "/plan")
    assert r.status_code == 200 and r.json() == {"plan_id": "plan-1"}


@pytest.mark.parametrize("method,path,body,key", ROUTES)
def test_ac2_403_envelope(client, method, path, body, key):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-role": "viewer"})
    _assert_envelope(r, 403, "ROLE_DENIED")


@pytest.mark.parametrize("method,path,body,key", ROUTES)
def test_ac2_404_envelope_unknown_connection(client, method, path, body, key):
    r = client.request(method, path.format(cid="conn-missing"), json=body)
    _assert_envelope(r, 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "suffix,body,field",
    [
        ("/payroll-compute", {"period": "2026-09"}, "upload_id"),
        ("/payroll-compute", {"upload_id": "u", "from_hr": True, "period": "2026-09"}, "upload_id"),
        ("/payroll-compute", {"from_hr": True}, "period"),
        ("/payroll-compute", {"from_hr": True, "period": "2026-09", "x": 1}, "x"),
        ("/bank/convert", {"bank": "gtbank"}, "upload_id"),
        ("/bank/convert", {"upload_id": "u", "rows": []}, "rows"),
    ],
)
def test_ac2_422_envelope_names_field(client, suffix, body, field):
    r = client.post(BASE.format(cid=CONN_A) + suffix, json=body)
    err = _assert_envelope(r, 422, "VALIDATION")
    assert field in str(err["detail"]) or field in err["message"]


def test_ac6_default_engine_is_not_ready_envelope(monkeypatch):
    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[ng.ng_scope] = _fake_scope
    c = TestClient(app)
    for method, path, body, _key in ROUTES:
        _assert_envelope(c.request(method, path.format(cid=CONN_A), json=body), 404, "NOT_FOUND")


# AC3 -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path,body,key", ROUTES)
def test_ac3_cross_workspace_404(client, engine, method, path, body, key):
    r = client.request(method, path.format(cid=CONN_A), json=body, headers={"x-ws": "ws-b"})
    _assert_envelope(r, 404, "NOT_FOUND")
    assert engine.calls == []


def test_ac3_every_ng_route_in_idor_registry():
    paths = app.openapi()["paths"]
    live = {(m.upper(), p) for p, ops in paths.items() if "/l10n-ng/" in p for m in ops}
    assert live == set(reg.NF_NG_ROUTES) and len(live) == 5
    assert not reg.missing_registered_routes(paths, reg.NF_NG_ROUTES)
    assert all(p in reg.connection_scoped_paths(paths) for _, p in reg.NF_NG_ROUTES)


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
        a_email, b_email = f"ng-a-{tag}@example.com", f"ng-b-{tag}@example.com"
        _a, ws_a, _ = signup_user(db, email=a_email, password="alice-pass-99", workspace_name="A")
        _b, ws_b, _ = signup_user(db, email=b_email, password="bob-pass-99", workspace_name="B")
        for email in (a_email, b_email):
            u = db.query(User).filter(User.email == email).one()
            u.email_verified = True
            db.add(u)
        ids = {}
        for key, ws in (("a", ws_a), ("b", ws_b)):
            conn = OdooConnection(
                name=f"ng {key}",
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
        for method, path, body, _key in ROUTES:
            real = bob.request(method, path.format(cid=ids["a"]), json=body)
            fake = bob.request(method, path.format(cid=ghost), json=body)
            _assert_envelope(real, 404, "NOT_FOUND")
            assert real.status_code == fake.status_code and real.content == fake.content, path
    assert eng.calls == []


# AC4 -----------------------------------------------------------------------
def test_ac4_owned_paused_connection_refuses_writes(monkeypatch):
    """Owner A, writes paused: the three POSTs refuse (403 writes_paused); GETs still read."""
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    _b, ids, a_email = _seed_two_workspaces(paused=True)
    eng = FakeEngine()
    _install(eng)
    with TestClient(app) as alice:
        r = alice.post("/api/accounts/login", json={"email": a_email, "password": "alice-pass-99"})
        assert r.status_code == 200, r.text
        for method, path, body, key in ROUTES:
            res = alice.request(method, path.format(cid=ids["a"]), json=body)
            if method == "POST":
                err = _assert_envelope(res, 403, "ROLE_DENIED")
                assert err["detail"]["error"] == "writes_paused", key
            else:
                assert res.status_code == 200, (key, res.text)
    assert eng.calls == ["detect", "readiness"]


def test_ac4_ng_safety_specs_pinned():
    from app.safety_registry import ROUTE_OVERRIDES

    def fields(spec):
        return asdict(spec) if is_dataclass(spec) else spec.model_dump()

    pre = "POST:/api/connections/{connection_id}/l10n-ng"
    assert fields(ROUTE_OVERRIDES[pre + "/plan"]) == fields(
        ROUTE_OVERRIDES["POST:/api/inbox/plans"]
    )
    for key in (pre + "/payroll-compute", pre + "/bank/convert"):
        spec = ROUTE_OVERRIDES[key]
        assert (spec.risk, spec.odoo_mutation, spec.confirm) == ("read", False, "none"), key
        assert spec.bypass_writes_paused is False, key


# AC5 -----------------------------------------------------------------------
TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "nigeria.ts"
TS_KEY_FIXTURE = dict(DOC_FIELDS)


def _ts_type_keys(src: str, name: str) -> set[str]:
    m = re.search(r"export type " + name + r" =\s*(.*?);\n\n", src, re.S)
    assert m, f"{name} missing from nigeria.ts"
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
    for fn in ("detect", "plan", "einvoiceReadiness", "payrollCompute", "bankConvert"):
        assert re.search(rf"\b{fn}\s*[:(]", src), fn


# AC6 -----------------------------------------------------------------------
def test_ac6_one_engine_dependency_per_route_and_no_odoo_import():
    src = Path(ng.__file__).read_text() + Path(t.__file__).read_text()
    assert "odoo_client" not in src and "execute_kw" not in src and "_client(" not in src
    assert "xmlrpc" not in src
    for dep in ENGINE_DEPS.values():
        assert src.count(f"Depends({dep})") == 1, dep
