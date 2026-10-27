"""SEC-TENANCY oracle. Red until workspace isolation is enforced.

AC1 calls every OpenAPI operation as workspace A with workspace B's connection id
in the path, query, and JSON body. Each call must return 404 or 403. The sweep
covers every router included on the app (the handover's 75 is the floor; the live
app has more).

AC2 requires one shared dependency, ``apply_workspace_query_scope`` /
``install_workspace_query_scope`` / ``stamp_workspace_id`` in
``app.workspace_auth``. ``app.main.lifespan`` must call
``install_workspace_query_scope``. Routers do not grow their own copy.

AC3 freezes today's static cross-tenant gaps in
``app.security.idor_registry.CROSS_TENANT_GAP_BASELINE``. The sweep fails when a
gap appears that is not listed, and when a listed gap no longer appears.

Product lines whose deletion fails these tests:
- the denial in front of OpenAPI routes when the request carries another
  workspace's connection id (404 or 403, before the handler)
- ``app.workspace_auth.apply_workspace_query_scope``
- ``app.workspace_auth.stamp_workspace_id``
- ``app.workspace_auth.install_workspace_query_scope`` (Session ``do_orm_execute``)
- the ``install_workspace_query_scope`` call in ``app.main.lifespan``
- ``app.security.idor_registry.CROSS_TENANT_GAP_BASELINE``
"""

from __future__ import annotations

import ast
import re
import sys
import uuid
import warnings
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import select

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
_MAIN_PATH = _APP_DIR / "main.py"
_ROUTERS = _APP_DIR / "routers"
_HTTP = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})
_DENIAL = frozenset({403, 404})
_FILTER_FUNCS = frozenset({"filter", "where", "filter_by"})
_PASSWORD = "workspace-a-pass"
_PARAM = re.compile(r"\{[^}/]+\}")
_CONVERTER = re.compile(r"\{([^}/]+):[^}]+\}")
_PLANTED_REL = "routers/planted.py"
_PLANTED_HAND_FILTER = (
    "def list_rows(db, auth):\n"
    "    return db.query(Row).filter(Row.workspace_id == auth.workspace_id)\n"
)
_APP = None


def _allow_boot() -> None:
    """Loopback ``--host`` as its own argv token so auth-off boot is not the failure."""
    if "--host" in sys.argv:
        return
    sys.argv.extend(["--host", "127.0.0.1"])


def _load_app():
    global _APP
    if _APP is None:
        _allow_boot()
        from app.main import app as fastapi_app

        _APP = fastapi_app
    return _APP


def _is_cross_tenant_denial(status: int) -> bool:
    return status in _DENIAL


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _calls_from(node: ast.AST) -> list[ast.Call]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return []
    found: list[ast.Call] = []
    if isinstance(node, ast.Call):
        found.append(node)
    for child in ast.iter_child_nodes(node):
        found.extend(_calls_from(child))
    return found


def _lifespan_call_names() -> list[str]:
    tree = ast.parse(_MAIN_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            return [_call_name(call) or "" for stmt in node.body for call in _calls_from(stmt)]
    raise AssertionError("app.main lifespan is missing")


def _function_def(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{path.name} has no function {name}")


def _called_names(fn: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name:
            found.add(name)
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.add(arg.value)
    return found


def _definitions(name: str) -> list[str]:
    found: list[str] = []
    for path in sorted(_APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                found.append(path.relative_to(_APP_DIR).as_posix())
    return found


def _normalize_path(path: str) -> str:
    """Starlette `{name:path}` and OpenAPI `{name}` are the same template."""
    return _CONVERTER.sub(r"{\1}", path)


def _join(prefix: str, path: str) -> str:
    prefix = (prefix or "").rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    if not prefix or path == prefix or path.startswith(prefix + "/"):
        full = path or "/"
    else:
        full = f"{prefix}{path}"
    return _normalize_path(full)


def _router_paths(included, prefix: str | None = None) -> set[str]:
    if prefix is None:
        prefix = getattr(included.include_context, "prefix", "") or ""
    found: set[str] = set()
    router = included.original_router
    for route in router.routes:
        if hasattr(route, "original_router") and hasattr(route, "include_context"):
            child_prefix = getattr(route.include_context, "prefix", "") or ""
            found |= _router_paths(route, _join(prefix, child_prefix) if child_prefix else prefix)
            continue
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            found.add(_join(prefix, path))
    return found


def _router_label(included) -> str:
    for route in included.original_router.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None:
            module = getattr(endpoint, "__module__", "?")
            prefix = getattr(included.original_router, "prefix", "") or ""
            return f"{module} {prefix}"
    return getattr(included.include_context, "prefix", "") or "?"


def _openapi_ops(app) -> list[tuple[str, str]]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate Operation ID")
        paths = app.openapi()["paths"]
    ops: list[tuple[str, str]] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() in _HTTP and isinstance(operation, dict):
                ops.append((method.upper(), _normalize_path(path)))
    return sorted(ops)


def _included_routers(app) -> list:
    return [
        route
        for route in app.routes
        if hasattr(route, "original_router") and hasattr(route, "include_context")
    ]


def _db_port() -> int:
    from app.settings import settings

    raw = settings.database_url.replace("postgresql+psycopg", "postgresql", 1)
    return urlparse(raw).port or 5432


@contextmanager
def _block_outbound_except_app_db() -> Iterator[None]:
    """Fail closed on non-database sockets so a route cannot wait on Odoo."""
    import socket

    allowed = _db_port()
    real = socket.create_connection

    def guarded(address, *args, **kwargs):
        port = address[1] if isinstance(address, tuple) and len(address) >= 2 else None
        if port != allowed:
            raise OSError(f"tenancy sweep blocked outbound port {port}")
        return real(address, *args, **kwargs)

    socket.create_connection = guarded
    try:
        yield
    finally:
        socket.create_connection = real


def _connection_shell():
    from app.db_models import OdooConnection

    return OdooConnection(
        name="tenancy",
        url="http://127.0.0.1:9",
        db_name="ingenium_tenancy",
        username="tenancy",
        secret_encrypted="not-a-credential",
    )


def _values(obj, found: set) -> None:
    if isinstance(obj, dict):
        for value in obj.values():
            _values(value, found)
    elif isinstance(obj, (list, tuple, set)):
        for value in obj:
            _values(value, found)
    else:
        found.add(obj)


def _scoped_to(statement, workspace_id: str) -> bool:
    compiled = statement.compile()
    sql = str(compiled).lower()
    if "workspace_id" not in sql:
        return False
    found: set = set()
    _values(compiled.params, found)
    return workspace_id in found or workspace_id in str(compiled)


def _seed_pair() -> dict[str, str]:
    from app.account_service import signup_user
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import OdooConnection

    email_a = f"tenancy-a-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"tenancy-b-{uuid.uuid4().hex[:8]}@example.com"
    secret = encrypt_secret("not-a-credential")
    db = SessionLocal()
    try:
        user_a, ws_a, _token_a = signup_user(
            db, email=email_a, password=_PASSWORD, workspace_name="Workspace A"
        )
        user_b, ws_b, _token_b = signup_user(
            db, email=email_b, password=_PASSWORD, workspace_name="Workspace B"
        )
        user_a.email_verified = True
        user_b.email_verified = True
        db.add(user_a)
        db.add(user_b)
        owned = OdooConnection(
            name="A connection",
            url="http://127.0.0.1:9",
            db_name="ingenium_tenancy_a",
            username="tenancy",
            secret_encrypted=secret,
            workspace_id=ws_a.id,
        )
        victim = OdooConnection(
            name="B connection",
            url="http://127.0.0.1:9",
            db_name="ingenium_tenancy_b",
            username="tenancy",
            secret_encrypted=secret,
            workspace_id=ws_b.id,
        )
        db.add(owned)
        db.add(victim)
        db.commit()
        return {
            "email": email_a,
            "a_connection_id": str(owned.id),
            "b_connection_id": str(victim.id),
            "b_workspace_id": str(ws_b.id),
        }
    finally:
        db.close()


def _ensure_victim(creds: dict[str, str]) -> None:
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import OdooConnection

    db = SessionLocal()
    try:
        if db.get(OdooConnection, creds["b_connection_id"]) is not None:
            return
        db.add(
            OdooConnection(
                id=creds["b_connection_id"],
                name="B connection",
                url="http://127.0.0.1:9",
                db_name="ingenium_tenancy_b",
                username="tenancy",
                secret_encrypted=encrypt_secret("not-a-credential"),
                workspace_id=creds["b_workspace_id"],
            )
        )
        db.commit()
    finally:
        db.close()


def _accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "ai_assist", "off")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)


def _login(client, email: str) -> None:
    response = client.post(
        "/api/accounts/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert response.status_code == 200, response.text[:200]


def _cross_tenant_request(client, method: str, path: str, creds: dict[str, str]):
    _ensure_victim(creds)
    url = _PARAM.sub(creds["b_connection_id"], path)
    foreign = {
        "connection_id": creds["b_connection_id"],
        "workspace_id": creds["b_workspace_id"],
        "id": creds["b_connection_id"],
        "project_id": creds["b_connection_id"],
        "target_connection_id": creds["b_connection_id"],
    }
    kwargs: dict = {"params": foreign}
    if method in {"POST", "PUT", "PATCH"}:
        kwargs["json"] = foreign
    try:
        return client.request(method, url, **kwargs).status_code
    except Exception as exc:  # noqa: BLE001 — one handler must not hide the rest of the sweep
        return type(exc).__name__


def _mentions_workspace_id(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "workspace_id":
            return True
        if isinstance(child, ast.Name) and child.id == "workspace_id":
            return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if "workspace_id" in child.value:
                return True
    return False


def _call_filters_workspace(node: ast.Call) -> bool:
    if _call_name(node) not in _FILTER_FUNCS:
        return False
    if any(_mentions_workspace_id(arg) for arg in node.args):
        return True
    for keyword in node.keywords:
        if keyword.arg == "workspace_id":
            return True
        if keyword.value is not None and _mentions_workspace_id(keyword.value):
            return True
    return False


def _scan_source(rel: str, source: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if _call_filters_workspace(node):
                qual = ".".join(stack) or "<module>"
                found.add(f"hand:{rel}:{qual}")
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _hand_filter_gaps() -> set[str]:
    found: set[str] = set()
    for path in sorted(_ROUTERS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(_APP_DIR).as_posix()
        found |= _scan_source(rel, path.read_text(encoding="utf-8"))
    return found


def _connection_column(name: str) -> bool:
    return name == "connection_id" or name.endswith("_connection_id")


def _schema_gaps() -> set[str]:
    import app.db_models  # noqa: F401
    from app.db import Base

    found: set[str] = set()
    for mapper in Base.registry.mappers:
        model = mapper.class_
        table = getattr(model, "__table__", None)
        if table is None:
            continue
        names = {column.name for column in table.columns}
        if "workspace_id" in names:
            if table.c.workspace_id.nullable:
                found.add(f"nullable-workspace-id:{table.name}")
        elif any(_connection_column(name) for name in names):
            found.add(f"missing-workspace-id:{table.name}")
    return found


def _live_gaps() -> set[str]:
    return _hand_filter_gaps() | _schema_gaps()


def _ratchet(live: set[str], baseline: set[str]) -> list[str]:
    failures: list[str] = []
    for key in sorted(live - baseline):
        failures.append(f"new gap: {key}")
    for key in sorted(baseline - live):
        failures.append(f"baseline entry that now passes: {key}")
    return failures


def _require(module: str, name: str):
    import importlib

    mod = importlib.import_module(module)
    fn = getattr(mod, name, None)
    if not callable(fn):
        raise AssertionError(
            f"{module}.{name} is missing; deleting it must fail this tenancy test"
        )
    return fn


def test_ac1_positive_workspace_a_every_openapi_route_denies_workspace_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace A calling every OpenAPI route with B's ids gets 404 or 403."""
    from fastapi.testclient import TestClient

    app = _load_app()
    _accounts(monkeypatch)
    included = _included_routers(app)
    ops = _openapi_ops(app)
    openapi_paths = {path for _method, path in ops}
    assert len(included) >= 75, f"expected the OpenAPI routers, found {len(included)}"
    assert ops, "OpenAPI has no operations to call"
    missing: list[str] = []
    for router in included:
        paths = _router_paths(router)
        extra = paths - openapi_paths
        if extra:
            sample = ", ".join(sorted(extra)[:3])
            missing.append(f"{_router_label(router)} -> {sample}")
    assert not missing, "routers outside the OpenAPI sweep: " + "; ".join(missing[:8])
    creds = _seed_pair()
    leaks: list[str] = []
    with TestClient(app) as client, _block_outbound_except_app_db():
        _login(client, creds["email"])
        for method, path in ops:
            status = _cross_tenant_request(client, method, path, creds)
            if not isinstance(status, int) or not _is_cross_tenant_denial(status):
                leaks.append(f"{status} {method} {path}")
    counts = Counter(item.split(" ", 1)[0] for item in leaks)
    assert not leaks, (
        f"{len(leaks)} of {len(ops)} cross-tenant calls across {len(included)} "
        f"routers were not 404 or 403 ({dict(counts)}). First: {leaks[:12]}"
    )


def test_ac1_negative_own_workspace_ids_are_not_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace A's own connection is not hidden. 200 is not a cross-tenant denial."""
    from fastapi.testclient import TestClient

    app = _load_app()
    _accounts(monkeypatch)
    creds = _seed_pair()
    assert not _is_cross_tenant_denial(200)
    assert not _is_cross_tenant_denial(401)
    assert not _is_cross_tenant_denial(422)
    assert _is_cross_tenant_denial(403)
    assert _is_cross_tenant_denial(404)
    with TestClient(app) as client:
        _login(client, creds["email"])
        response = client.get(f"/api/connections/{creds['a_connection_id']}")
    assert response.status_code == 200, response.text[:200]
    assert not _is_cross_tenant_denial(response.status_code)


@pytest.mark.no_app_db
def test_ac2_positive_workspace_rows_use_one_shared_query_dependency() -> None:
    """Workspace-owned rows carry the workspace id and one dependency filters queries."""
    from app.billing_models import WorkspaceSubscription
    from app.db_models import BridgeConnection, OdooConnection, SavedScript

    apply_scope = _require("app.workspace_auth", "apply_workspace_query_scope")
    stamp = _require("app.workspace_auth", "stamp_workspace_id")
    install = _require("app.workspace_auth", "install_workspace_query_scope")
    assert apply_scope.__module__ == "app.workspace_auth"
    assert stamp.__module__ == "app.workspace_auth"
    assert install.__module__ == "app.workspace_auth"
    definitions = _definitions("apply_workspace_query_scope")
    assert definitions == ["workspace_auth.py"], definitions
    for model in (OdooConnection, BridgeConnection, SavedScript, WorkspaceSubscription):
        scoped = apply_scope(select(model), "ws-a")
        assert _scoped_to(scoped, "ws-a"), model.__name__
    row = _connection_shell()
    assert row.workspace_id is None
    stamp(row, "ws-a")
    assert row.workspace_id == "ws-a"
    stamp(row, "ws-a")
    assert row.workspace_id == "ws-a"
    install_def = _function_def(_APP_DIR / "workspace_auth.py", "install_workspace_query_scope")
    names = _called_names(install_def)
    assert "do_orm_execute" in names
    assert "apply_workspace_query_scope" in names
    assert "listens_for" in names or "listen" in names
    assert "install_workspace_query_scope" in _lifespan_call_names()


@pytest.mark.no_app_db
def test_ac2_negative_router_hand_filter_and_foreign_stamp_are_rejected() -> None:
    """A hand filter is not the shared dependency, and a foreign row is not restamped."""
    from fastapi import HTTPException

    from app.db_models import BridgeConnection, OdooConnection

    planted = _scan_source(_PLANTED_REL, _PLANTED_HAND_FILTER)
    assert planted == {"hand:routers/planted.py:list_rows"}
    assert not any(key.startswith("hand:workspace_auth.py:") for key in planted)
    bare = select(OdooConnection)
    assert not _scoped_to(bare, "ws-a")
    assert _scoped_to(bare.where(OdooConnection.workspace_id == "ws-a"), "ws-a")
    apply_scope = _require("app.workspace_auth", "apply_workspace_query_scope")
    stamp = _require("app.workspace_auth", "stamp_workspace_id")
    scoped = apply_scope(select(OdooConnection), "ws-a")
    assert _scoped_to(scoped, "ws-a")
    assert not _scoped_to(scoped, "ws-b")
    foreign = BridgeConnection(
        workspace_id="ws-b",
        kind="odoo",
        display_name="B",
        secret_ref="ref",
    )
    with pytest.raises(HTTPException) as raised:
        stamp(foreign, "ws-a")
    assert raised.value.status_code in _DENIAL
    assert foreign.workspace_id == "ws-b"


@pytest.mark.no_app_db
def test_ac3_positive_ratchet_baseline_matches_todays_cross_tenant_gaps() -> None:
    """The baseline lists today's gaps. New gaps and fixed entries fail the sweep."""
    live = _live_gaps()
    assert "hand:routers/bridge.py:_ws_connection_ids" in live
    assert "nullable-workspace-id:odoo_connections" in live
    assert "missing-workspace-id:metadata_snapshots" in live
    assert "missing-workspace-id:verify_artifacts" in live
    assert "nullable-workspace-id:verify_runs" in live
    from app.security import idor_registry

    baseline = getattr(idor_registry, "CROSS_TENANT_GAP_BASELINE", None)
    if baseline is None:
        listed = "\n".join(sorted(live))
        raise AssertionError(
            "CROSS_TENANT_GAP_BASELINE is missing. Today's cross-tenant gaps:\n" + listed
        )
    failures = _ratchet(live, set(baseline))
    assert not failures, "\n".join(failures[:40])


@pytest.mark.no_app_db
def test_ac3_negative_new_gap_and_fixed_baseline_entry_fail_the_sweep() -> None:
    """The sweep fails on a new hand filter and on a baseline entry that now passes."""
    planted = _scan_source(_PLANTED_REL, _PLANTED_HAND_FILTER)
    assert planted == {"hand:routers/planted.py:list_rows"}
    new_gap = _ratchet(planted, set())
    assert new_gap == ["new gap: hand:routers/planted.py:list_rows"]
    fixed = _ratchet(set(), planted)
    assert fixed == ["baseline entry that now passes: hand:routers/planted.py:list_rows"]
    assert _ratchet(planted, planted) == []
    still = _live_gaps()
    assert _ratchet(still, still) == []
    assert _ratchet(still | planted, still) == ["new gap: hand:routers/planted.py:list_rows"]

