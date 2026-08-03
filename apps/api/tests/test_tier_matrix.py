"""TIER-1 four-tier capability matrix — truth-table + endpoint tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.capabilities import tier_matrix_response  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.hosting import python_modules_allowed  # noqa: E402
from app.main import app  # noqa: E402
from app.tier_matrix import (  # noqa: E402
    TierCapabilityKey,
    build_tier_context,
    detect_edition,
    detect_hosting,
    evaluate_full_matrix,
    evaluate_tier_matrix,
    invalidate_matrix_cache,
    python_modules_allowed_from_matrix,
)


def _cap(ctx, key: TierCapabilityKey) -> str:
    rows = evaluate_tier_matrix(ctx)
    row = next(r for r in rows if r.key == key.value)
    return row.available


@pytest.mark.parametrize(
    ("url", "expected_hosting"),
    [
        ("https://acme.odoo.com", "online"),
        ("https://branch.odoo.sh", "sh"),
        ("http://127.0.0.1:8069", "onprem"),
        ("https://erp.example.com", "onprem"),
        (None, "unknown"),
    ],
)
def test_detect_hosting_url_combos(url: str | None, expected_hosting: str) -> None:
    hosting, _ = detect_hosting(url)
    assert hosting == expected_hosting


@pytest.mark.parametrize(
    ("server_version", "modules", "expected_edition"),
    [
        ("19.0", [], "community"),
        ("19.0+e", [], "enterprise"),
        ("19.0", ["web_enterprise"], "enterprise"),
        ("19.0", ["enterprise"], "enterprise"),
        (None, [], "unknown"),
    ],
)
def test_detect_edition_combos(
    server_version: str | None, modules: list[str], expected_edition: str
) -> None:
    assert detect_edition(server_version, modules) == expected_edition


@pytest.mark.parametrize(
    ("hosting_hint", "expected"),
    [
        ("online", False),
        ("odoo_sh", True),
        ("self_hosted", True),
        ("unknown", True),
    ],
)
def test_python_modules_shim(hosting_hint: str, expected: bool) -> None:
    assert python_modules_allowed(hosting_hint) is expected


def test_matrix_online_module_deploy_no() -> None:
    ctx = build_tier_context(
        url="https://x.odoo.com", server_version="19.0", installed_modules=["base"]
    )
    assert _cap(ctx, TierCapabilityKey.MODULE_DEPLOY) == "no"
    assert _cap(ctx, TierCapabilityKey.PYTHON_MODULE_INSTALL) == "no"
    assert _cap(ctx, TierCapabilityKey.SANDBOX_PARITY) == "verify"


def test_matrix_sh_module_deploy_yes() -> None:
    ctx = build_tier_context(
        url="https://x.odoo.sh", server_version="19.0", installed_modules=["base"]
    )
    assert _cap(ctx, TierCapabilityKey.MODULE_DEPLOY) == "yes"
    assert python_modules_allowed_from_matrix(ctx) is True


def test_matrix_onprem_module_deploy_yes() -> None:
    ctx = build_tier_context(
        url="http://127.0.0.1:8069", server_version="19.0", installed_modules=["base"]
    )
    assert _cap(ctx, TierCapabilityKey.MODULE_DEPLOY) == "yes"
    assert _cap(ctx, TierCapabilityKey.SANDBOX_PARITY) == "yes"


def test_matrix_direct_sql_always_no() -> None:
    for url in ("https://x.odoo.com", "https://x.odoo.sh", "http://127.0.0.1:8069"):
        ctx = build_tier_context(url=url, server_version="19.0")
        assert _cap(ctx, TierCapabilityKey.DIRECT_SQL) == "no"


def test_matrix_base_automation_module_presence() -> None:
    with_mod = build_tier_context(
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base_automation"],
    )
    without = build_tier_context(
        url="http://127.0.0.1:8069", server_version="19.0", installed_modules=["base"]
    )
    assert _cap(with_mod, TierCapabilityKey.BASE_AUTOMATION) == "yes"
    assert _cap(without, TierCapabilityKey.BASE_AUTOMATION) == "no"


def test_matrix_approval_rules_enterprise_vs_community() -> None:
    ee = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0+e")
    comm = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    assert _cap(ee, TierCapabilityKey.APPROVAL_RULES_STUDIO) == "verify"
    assert _cap(comm, TierCapabilityKey.APPROVAL_RULES_STUDIO) == "no"


def test_matrix_studio_modules_approval_verify() -> None:
    ctx = build_tier_context(
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["web_studio"],
    )
    assert _cap(ctx, TierCapabilityKey.APPROVAL_RULES_STUDIO) == "verify"


def test_matrix_views_enterprise_edition_gated() -> None:
    ee = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0+e")
    comm = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    assert _cap(ee, TierCapabilityKey.VIEWS_ENTERPRISE_TYPES) == "yes"
    assert _cap(comm, TierCapabilityKey.VIEWS_ENTERPRISE_TYPES) == "no"


def test_matrix_property_fields_19_yes() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    assert _cap(ctx, TierCapabilityKey.PROPERTY_FIELDS) == "yes"


def test_matrix_property_fields_16_no() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="16.0")
    assert _cap(ctx, TierCapabilityKey.PROPERTY_FIELDS) == "no"


def test_matrix_financial_online_plan_gated() -> None:
    ctx = build_tier_context(url="https://x.odoo.com", server_version="19.0")
    assert _cap(ctx, TierCapabilityKey.FINANCIAL_LINK_ONLY) == "plan_gated"


def test_matrix_financial_onprem_yes() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    assert _cap(ctx, TierCapabilityKey.FINANCIAL_LINK_ONLY) == "yes"


def test_matrix_report_merge_ga_major() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    assert _cap(ctx, TierCapabilityKey.REPORT_MERGE_PRINT) == "yes"


def test_matrix_report_merge_old_major_verify() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="16.0")
    assert _cap(ctx, TierCapabilityKey.REPORT_MERGE_PRINT) == "verify"


def test_matrix_core_rows_always_yes() -> None:
    ctx = build_tier_context(url="https://x.odoo.com", server_version="19.0")
    for key in (
        TierCapabilityKey.CUSTOM_MODELS,
        TierCapabilityKey.CUSTOM_FIELDS,
        TierCapabilityKey.VIEWS_COMMUNITY,
        TierCapabilityKey.MENUS_ACTIONS,
        TierCapabilityKey.SECURITY_ACL_RULES,
        TierCapabilityKey.QWEB_REPORTS,
        TierCapabilityKey.XPATH_INHERIT,
        TierCapabilityKey.IMAGES_MEDIA,
        TierCapabilityKey.BULK_RPC_SUITE,
    ):
        assert _cap(ctx, key) == "yes"


def test_matrix_web_base_url_hosting_fallback() -> None:
    hosting, hint = detect_hosting(
        "http://127.0.0.1:8069",
        web_base_url="https://tenant.odoo.com",
    )
    assert hosting == "onprem"
    hosting2, _ = detect_hosting(None, web_base_url="https://tenant.odoo.com")
    assert hosting2 == "online"


def test_evaluate_full_matrix_cache() -> None:
    invalidate_matrix_cache()
    first = evaluate_full_matrix(
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base"],
        connection_id="cache-test",
        use_cache=True,
    )
    second = evaluate_full_matrix(
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base"],
        connection_id="cache-test",
        use_cache=True,
    )
    assert first is second
    invalidate_matrix_cache("cache-test")
    third = evaluate_full_matrix(
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base"],
        connection_id="cache-test",
        use_cache=True,
    )
    assert third is not first


def test_tier_matrix_response_shape() -> None:
    out = tier_matrix_response(
        connection_id="cid",
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base", "mail"],
    )
    assert out is not None
    assert out.connection_id == "cid"
    assert out.hosting == "onprem"
    assert out.major == 19
    assert len(out.capabilities) >= 18
    assert any(c.key == "module_deploy" for c in out.capabilities)


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_capability_matrix_endpoint(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier-matrix",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}/capability-matrix")
    assert res.status_code == 200
    body = res.json()
    assert body["hosting"] == "onprem"
    assert body["major"] == 19
    keys = {c["key"] for c in body["capabilities"]}
    assert "direct_sql" in keys
    assert "module_deploy" in keys
    deploy = next(c for c in body["capabilities"] if c["key"] == "module_deploy")
    assert deploy["available"] == "yes"


def test_capability_matrix_endpoint_requires_version(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier-no-version",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}/capability-matrix")
    assert res.status_code == 409
