"""TRUST-1 write-mode API tests."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from odoo_client.client import ObserverModeError  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    from app.account_service import ensure_default_workspace_for_legacy_rows
    from app.account_models import Workspace
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        ensure_default_workspace_for_legacy_rows(db)
        ws = db.query(Workspace).first()
        if ws is not None and ws.writes_paused:
            ws.writes_paused = False
            db.add(ws)
            db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c


def test_odoo_service_passes_write_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db_models import OdooConnection
    from app.odoo_service import client_from_connection

    row = OdooConnection(
        id="wm-pass-through",
        name="x",
        url="http://127.0.0.1:8069",
        db_name="odoo",
        username="admin",
        secret_encrypted="enc",
        write_mode="observer",
    )

    captured: dict[str, str] = {}

    class FakeClient:
        config = None

        def connect(self):
            return 1

    def fake_client(config):
        captured["write_mode"] = config.write_mode
        inst = FakeClient()
        inst.config = config
        return inst

    monkeypatch.setattr("app.odoo_service.decrypt_secret", lambda _x: "secret")
    monkeypatch.setattr("app.odoo_service.OdooClient", fake_client)
    client_from_connection(row)
    assert captured["write_mode"] == "observer"


def test_new_connection_defaults_observer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TEST_DEFAULT_WRITE_MODE", raising=False)
    init_db()
    resp = client.post(
        "/api/connections",
        json={
            "name": "Observer default",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["write_mode"] == "observer"


def test_unlock_write_mode(client: TestClient) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Unlock me",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201
    conn_id = create.json()["id"]
    patch = client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "standard"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["write_mode"] == "standard"


def test_production_mode_blocked_until_trust9(client: TestClient) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Prod gate",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    conn_id = create.json()["id"]
    resp = client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "production"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "production_readiness_required"


def test_client_from_connection_blocks_mutations_in_observer() -> None:
    from odoo_client import ConnectionConfig, OdooClient

    client = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:8069",
            db="odoo",
            username="admin",
            password="admin",
            write_mode="observer",
        )
    )
    client._uid = 1
    with pytest.raises(ObserverModeError):
        client.execute_kw("res.partner", "write", [[1], {"name": "blocked"}])


def test_probe_allowed_in_observer_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Probe observer",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201
    conn_id = create.json()["id"]
    patch = client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "observer", "confirm_advanced": True},
    )
    assert patch.status_code == 200, patch.text

    monkeypatch.setattr(
        "app.routers.connections.probe_credentials",
        lambda *_a, **_k: (1, "19.0"),
    )
    monkeypatch.setattr(
        "app.version_watch.observe_server_version",
        lambda *_a, **_k: type(
            "Watch",
            (),
            {"upgrade_detected": False, "health_job_id": None},
        )(),
    )

    class FakeOdooClient:
        pass

    monkeypatch.setattr(
        "app.odoo_service.client_from_connection",
        lambda _row: FakeOdooClient(),
    )
    monkeypatch.setattr(
        "app.capabilities.sample_installed_modules",
        lambda _c: ["base", "contacts"],
    )
    monkeypatch.setattr(
        "app.capabilities.probe_web_base_url",
        lambda _c: "http://127.0.0.1:8069",
    )
    monkeypatch.setattr(
        "app.routers.connections._refresh_protected_manifest_for_row",
        lambda row, client=None: {},
    )
    monkeypatch.setattr(
        "app.routers.connections.tier_matrix_response",
        lambda **_k: {},
    )

    resp = client.post(f"/api/connections/{conn_id}/probe")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
