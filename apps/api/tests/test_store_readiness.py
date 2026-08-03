"""Store readiness checker tests (TIER-3)."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from app.store_readiness import (
    ODOO_MODULE_CATEGORIES,
    check_store_readiness,
    check_zip_store_readiness,
    parse_manifest_py,
)
from app.store_packaging import apply_store_packaging
from module_generator import build_module_zip, library_module_spec


GOOD_MANIFEST = """
{
    "name": "Demo App",
    "version": "19.0.1.0.0",
    "category": "Customization",
    "summary": "A solid summary line for the Apps listing",
    "description": "A long enough description for the Odoo Apps store listing page scaffold and review.",
    "depends": ["base"],
    "installable": True,
    "license": "LGPL-3",
    "author": "Acme Corp",
    "website": "https://example.com",
}
"""


def test_parse_manifest_py() -> None:
    data = parse_manifest_py(GOOD_MANIFEST)
    assert data["name"] == "Demo App"
    assert data["license"] == "LGPL-3"


def test_check_store_readiness_good_manifest() -> None:
    manifest = parse_manifest_py(GOOD_MANIFEST)
    members = {
        "demo_app/__manifest__.py",
        "demo_app/static/description/icon.png",
        "demo_app/static/description/index.html",
    }
    report = check_store_readiness(
        manifest=manifest,
        zip_members=members,
        technical_name="demo_app",
        major=19,
    )
    assert report.fail_count == 0


def test_check_store_readiness_bad_version_fails() -> None:
    manifest = parse_manifest_py(GOOD_MANIFEST)
    manifest["version"] = "1.0.0"
    report = check_store_readiness(
        manifest=manifest,
        zip_members={"demo_app/static/description/icon.png"},
        technical_name="demo_app",
        major=19,
    )
    assert any(i.key == "version" and i.status == "fail" for i in report.items)


def test_category_allowlist_includes_customization() -> None:
    assert "Customization" in ODOO_MODULE_CATEGORIES


def test_library_store_ready_export_zero_fails() -> None:
    spec = library_module_spec("library_mgmt", "Library Management")
    zip_bytes = build_module_zip(spec)
    zip_bytes, _, report = apply_store_packaging(zip_bytes, spec, major=19)
    assert report["fail_count"] == 0
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert "library_mgmt/STORE_READINESS.json" in names
    assert "library_mgmt/static/description/icon.png" in names
    assert "library_mgmt/static/description/index.html" in names
    readiness = check_zip_store_readiness(
        zip_bytes,
        technical_name="library_mgmt",
        major=19,
        icon_is_placeholder=True,
    )
    assert readiness.fail_count == 0
    assert readiness.warn_count >= 1  # placeholder icon
