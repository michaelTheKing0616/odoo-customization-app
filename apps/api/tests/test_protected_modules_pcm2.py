"""PCM-2 tests: protected manifest retrieval, merge, endpoint."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.main import app  # noqa: E402
from app.protected_modules import (  # noqa: E402
    fetch_community_modules_from_source,
    load_vendored_community_modules,
    merge_connection_manifest,
    refresh_connection_protected_manifest,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_vendored_snapshot_fallback_has_account_and_base() -> None:
    mods = load_vendored_community_modules("19.0")
    assert mods
    assert "account" in mods
    assert "base" in mods


def test_fetch_community_modules_offline_uses_snapshot() -> None:
    with patch("app.protected_modules.subprocess.run", side_effect=OSError("offline")):
        mods, label = fetch_community_modules_from_source("19.0")
    assert "account" in mods
    assert label.startswith("vendored_snapshot:19.0")


def test_merge_connection_manifest_paths() -> None:
    merged = merge_connection_manifest(
        version="19.0",
        community_modules=["account", "crm", "l10n_ng"],
        live_modules=["account", "sale", "payment_stripe"],
        community_source_label="test:community",
        live_source_label="test:live",
    )
    assert merged["community_source"]["source"] == "test:community"
    assert merged["live_instance"]["source"] == "test:live"
    assert "account" in merged["tier_1_never_generate_logic"]["accounting_core"]
    assert merged["module_counts"]["union"] >= 4


def test_refresh_with_fake_rpc_client() -> None:
    class FakeClient:
        def list_modules(self, *, installed_only: bool, applications_only: bool):
            _ = installed_only, applications_only
            return [
                SimpleNamespace(name="account"),
                SimpleNamespace(name="sale"),
                SimpleNamespace(name="crm"),
            ]

    manifest = refresh_connection_protected_manifest(
        server_version="19.0",
        client=FakeClient(),
    )
    assert manifest["module_counts"]["live_instance"] == 3
    assert "account" in manifest["tier_1_never_generate_logic"]["accounting_core"]


def test_protected_modules_endpoint_offline(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "PCM2 Offline",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo_dev",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201
    cid = create.json()["id"]
    # Seed version + manifest without live Odoo
    patch_row = client.patch(
        f"/api/connections/{cid}",
        json={"verify": False},
    )
    assert patch_row.status_code == 200

    from app.db import SessionLocal
    from app.db_models import OdooConnection
    from app.protected_modules import manifest_to_json, refresh_connection_protected_manifest

    db = SessionLocal()
    try:
        row = db.get(OdooConnection, cid)
        assert row is not None
        row.server_version = "19.0"
        manifest = refresh_connection_protected_manifest(server_version="19.0", client=None)
        row.protected_manifest_json = manifest_to_json(manifest)
        row.protected_manifest_version = "19.0"
        db.commit()
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}/protected-modules")
    assert res.status_code == 200
    body = res.json()
    assert body["connection_id"] == cid
    assert "account" in body["manifest"]["tier_1_never_generate_logic"]["accounting_core"]
    assert body["tier_summary"]["tier_1_modules"] >= 1

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_protected_modules_live_odoo19(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "PCM2 Live",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    probe = client.post(f"/api/connections/{cid}/probe")
    assert probe.status_code == 200

    res = client.get(f"/api/connections/{cid}/protected-modules")
    assert res.status_code == 200
    body = res.json()
    assert "account" in body["manifest"]["tier_1_never_generate_logic"]["accounting_core"]

    client.delete(f"/api/connections/{cid}")
