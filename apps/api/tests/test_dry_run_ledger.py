"""Dry-run hash is required before the matching live write.

5A-02 route table. Tool name is ``METHOD:path``. The hash is
``(tool, args minus dry_run)``. Approval fields are ignored.
Classification is one of: gated (Odoo write; live call refused until the
hash was seen), not_odoo_write (no customer Odoo mutation). None of these
routes go through the change-set executor.

T1 generate apply
  POST /api/ai/sessions/{session_id}/apply
      gated — apply_module_spec_ui writes ir.model / fields / views / menus
  POST /api/connections/{connection_id}/module-spec/apply
      gated — same live apply
  POST /api/connections/{connection_id}/module-spec/seed-walkthrough
      gated — creates sample records on the connection
  POST /api/ai/sessions/{session_id}/generate
      not_odoo_write — draft job in the app database

T1 module install
  POST /api/connections/{connection_id}/modules/install-community
      gated — stock Community install on the connection
  POST /api/connections/{connection_id}/modules/promote
      gated — installs a sandbox-validated zip on the connection
  POST /api/connections/{connection_id}/modules/uninstall
      gated — uninstalls a module on the connection
  POST /api/connections/{connection_id}/sandbox/run
      not_odoo_write — ephemeral sandbox, not the customer connection

T3 bridge
  POST /api/bridge/contracts/validate
      not_odoo_write — Tier I contract check
  bridge.queue.enqueue
      not_odoo_write — inserts integration_events; the connector does not write Odoo

T4 dashboard, offline, skills/triggers
  POST /api/dashboard-studio/preview
      not_odoo_write — progress stub; dash_save does not persist
  offline claim_db
      not_odoo_write — app idempotency row; no flush route writes Odoo
  GET /api/connections/{connection_id}/automations/triggers
      not_odoo_write — read
  skills route_skills / mcp_call
      not_odoo_write — skill load narrows a grant; MCP writes are refused elsewhere
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db_models import DryRunSeen
from app.dry_run_ledger import (
    TTL_S,
    DryRunRequired,
    SqlDryRunStore,
    bind_store,
    enforce_dry_run,
)
from app.dry_run_middleware import GATED_ROUTE_TEMPLATES, DryRunHashMiddleware

pytestmark = pytest.mark.no_app_db


def _concrete(template: str) -> str:
    return template.replace("{session_id}", "s1").replace("{connection_id}", "c1")


@pytest.fixture(autouse=True)
def _shared_sqlite_ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/dry_run_seen.db")
    DryRunSeen.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    bind_store(SqlDryRunStore(factory))
    yield
    bind_store(None)


def test_live_write_without_preview_is_refused() -> None:
    args = {"recipe_id": "mass_archive", "ids": [1]}
    with pytest.raises(DryRunRequired):
        enforce_dry_run("tool", args, dry_run=False)


def test_preview_then_live_write_matches() -> None:
    args = {"recipe_id": "mass_archive", "ids": [1], "confirm_phrase": "I understand the risks"}
    enforce_dry_run("tool", args, dry_run=True)
    enforce_dry_run(
        "tool",
        {**args, "receipt_token": "abc", "confirm_advanced": True},
        dry_run=False,
    )


def test_middleware_refuses_then_allows_the_same_body() -> None:
    app = FastAPI()
    app.add_middleware(DryRunHashMiddleware)

    @app.post("/write")
    async def write(request: Request) -> dict:
        await request.json()
        return {"ok": True}

    client = TestClient(app)
    blocked = client.post("/write", json={"model": "res.partner", "dry_run": False})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "dry_run_receipt_required"
    preview = client.post("/write", json={"model": "res.partner", "dry_run": True})
    assert preview.status_code == 200
    live = client.post(
        "/write",
        json={
            "model": "res.partner",
            "dry_run": False,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert live.status_code == 200


def test_gated_templates_are_the_odoo_writes() -> None:
    assert GATED_ROUTE_TEMPLATES == (
            ("POST", "/api/ai/sessions/{session_id}/apply"),
        ("POST", "/api/ai/sessions/{session_id}/install-apps"),
        ("POST", "/api/ai/sessions/{session_id}/stock-app"),
        ("POST", "/api/connections/{connection_id}/module-spec/apply"),
        ("POST", "/api/connections/{connection_id}/module-spec/seed-walkthrough"),
        ("POST", "/api/connections/{connection_id}/modules/install-community"),
        ("POST", "/api/connections/{connection_id}/modules/promote"),
        ("POST", "/api/connections/{connection_id}/modules/uninstall"),
    )


@pytest.mark.parametrize(("method", "template"), GATED_ROUTE_TEMPLATES)
def test_each_gated_tool_refuses_until_the_same_args_were_seen(method: str, template: str) -> None:
    path = _concrete(template)
    app = FastAPI()
    app.add_middleware(DryRunHashMiddleware)

    @app.api_route(path, methods=[method])
    async def write() -> dict:
        return {"wrote": True}

    client = TestClient(app)
    blocked = client.request(method, path, json={"name": "x"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "dry_run_receipt_required"
    preview = client.request(method, path, json={"name": "x", "dry_run": True})
    assert preview.status_code == 200
    assert preview.json() == {"ok": True, "dry_run": True}
    live = client.request(method, path, json={"name": "x"})
    assert live.status_code == 200
    assert live.json() == {"wrote": True}


def test_bridge_validate_without_dry_run_is_not_an_odoo_write() -> None:
    app = FastAPI()
    app.add_middleware(DryRunHashMiddleware)

    @app.post("/api/bridge/contracts/validate")
    async def validate() -> dict:
        return {"ok": True, "tier": "I"}

    client = TestClient(app)
    res = client.post("/api/bridge/contracts/validate", json={"contract": {}})
    assert res.status_code == 200
    assert res.json()["tier"] == "I"


def test_dashboard_preview_without_dry_run_is_not_an_odoo_write() -> None:
    app = FastAPI()
    app.add_middleware(DryRunHashMiddleware)

    @app.post("/api/dashboard-studio/preview")
    async def preview() -> dict:
        return {"status": "stub"}

    client = TestClient(app)
    res = client.post("/api/dashboard-studio/preview", json={"prompt": "sales"})
    assert res.status_code == 200
    assert res.json()["status"] == "stub"


def test_worker_b_live_write_succeeds_when_the_ledger_is_shared(tmp_path) -> None:
    url = f"sqlite:///{tmp_path}/shared.db"
    engine_a = create_engine(url)
    DryRunSeen.__table__.create(bind=engine_a)
    engine_b = create_engine(url)
    worker_a = SqlDryRunStore(sessionmaker(bind=engine_a, autoflush=False, autocommit=False))
    worker_b = SqlDryRunStore(sessionmaker(bind=engine_b, autoflush=False, autocommit=False))
    args = {"module_name": "sale"}
    tool = "POST:/api/connections/c1/modules/install-community"
    enforce_dry_run(tool, args, dry_run=True, store=worker_a)
    enforce_dry_run(tool, {**args, "dry_run": False}, dry_run=False, store=worker_b)


def test_worker_b_refuses_when_ledgers_are_separate(tmp_path) -> None:
    engine_a = create_engine(f"sqlite:///{tmp_path}/a.db")
    engine_b = create_engine(f"sqlite:///{tmp_path}/b.db")
    DryRunSeen.__table__.create(bind=engine_a)
    DryRunSeen.__table__.create(bind=engine_b)
    worker_a = SqlDryRunStore(sessionmaker(bind=engine_a, autoflush=False, autocommit=False))
    worker_b = SqlDryRunStore(sessionmaker(bind=engine_b, autoflush=False, autocommit=False))
    args = {"module_name": "sale"}
    tool = "POST:/api/connections/c1/modules/install-community"
    enforce_dry_run(tool, args, dry_run=True, store=worker_a)
    with pytest.raises(DryRunRequired):
        enforce_dry_run(tool, args, dry_run=False, store=worker_b)


def test_shared_receipt_expires_after_one_hour(tmp_path) -> None:
    assert TTL_S == 60 * 60
    engine = create_engine(f"sqlite:///{tmp_path}/ttl.db")
    DryRunSeen.__table__.create(bind=engine)
    store = SqlDryRunStore(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    start = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    args = {"module_name": "sale"}
    tool = "POST:/api/connections/c1/modules/install-community"
    enforce_dry_run(tool, args, dry_run=True, store=store, now=start)
    enforce_dry_run(
        tool,
        args,
        dry_run=False,
        store=store,
        now=start + timedelta(seconds=TTL_S - 1),
    )
    with pytest.raises(DryRunRequired):
        enforce_dry_run(
            tool,
            args,
            dry_run=False,
            store=store,
            now=start + timedelta(seconds=TTL_S + 1),
        )
