"""Hosting hint + Online Python promote contract tests (mastery M1)."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.capabilities import capabilities_from_version
from app.hosting import hosting_hint_from_url, python_modules_allowed
from app.promote import promote_module_zip
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError


def test_hosting_hint_online() -> None:
    assert hosting_hint_from_url("https://myco.odoo.com") == "online"
    assert python_modules_allowed("online") is False


def test_hosting_hint_odoo_sh() -> None:
    assert hosting_hint_from_url("https://myco.odoo.sh") == "odoo_sh"
    assert python_modules_allowed("odoo_sh") is True


def test_hosting_hint_self() -> None:
    assert hosting_hint_from_url("http://127.0.0.1:8069") == "self_hosted"
    assert hosting_hint_from_url("https://erp.example.com") == "self_hosted"


def test_capabilities_online_url_sets_python_flag() -> None:
    matrix = capabilities_from_version(
        "19.0",
        url="https://acme.odoo.com",
        installed_modules=["base", "web", "mail"],
    )
    assert matrix is not None
    assert matrix.hosting_hint == "online"
    assert matrix.python_module_install is False
    assert any("Python" in w for w in matrix.warnings)
    assert "Odoo Online" in (matrix.message or "")


def test_capabilities_enterprise_online_combined() -> None:
    matrix = capabilities_from_version("19.0+e", url="https://acme.odoo.com")
    assert matrix is not None
    assert matrix.edition == "enterprise"
    assert matrix.hosting_hint == "online"
    assert matrix.python_module_install is False


def test_capabilities_studio_module_warning() -> None:
    matrix = capabilities_from_version(
        "19.0+e",
        url="https://erp.example.com",
        installed_modules=["base", "web_studio"],
    )
    assert matrix is not None
    assert any("Studio" in w for w in matrix.warnings)


def _python_model_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "x_m1_online_py/__manifest__.py",
            "{'name': 'M1', 'version': '19.0.1.0.0', 'installable': True}",
        )
        zf.writestr("x_m1_online_py/models/__init__.py", "from . import models\n")
        zf.writestr(
            "x_m1_online_py/models/models.py",
            "from odoo import models, fields\n\n"
            "class X(models.Model):\n"
            "    _name = 'x.m1.online.py'\n"
            "    name = fields.Char()\n",
        )
    return buf.getvalue()


def test_promote_python_zip_online_error_contract() -> None:
    zip_bytes = _python_model_zip()
    client = OdooClient(
        ConnectionConfig(
            url="https://acme.odoo.com",
            db="acme",
            username="admin",
            password="admin",
        )
    )
    with pytest.raises(OdooClientError, match="Odoo Online cannot install custom Python"):
        promote_module_zip(client, zip_bytes, prefer_filesystem=False)
