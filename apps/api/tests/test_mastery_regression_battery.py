"""Adversarial mastery regression battery (checker — strict contracts).

Covers thin spots across M1–M5 without duplicating soft asserts from per-phase files:
- Online refuse message exactness
- capabilities hosting_hint / python_module_install fields
- EE playbooks grey-out reason exactness
- config uom / fiscal unavailable honesty
- pipeline major resolution edge cases
- promote Online Python error substring
"""

from __future__ import annotations

import io
import os
import zipfile
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.capabilities import capabilities_from_version  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.hosting import (  # noqa: E402
    hosting_hint_from_url,
    hosting_operator_message,
    python_modules_allowed,
)
from app.main import app  # noqa: E402
from app.promote import promote_module_zip  # noqa: E402
from app.routers.environments import _pipeline_sandbox_major  # noqa: E402
from app.snapshots import CONFIRM_PHRASE  # noqa: E402
from odoo_client import ConnectionConfig, OdooClient  # noqa: E402
from odoo_client.client import OdooClientError  # noqa: E402

ONLINE_REFUSE_EXACT = (
    "Hosting looks like Odoo Online: metadata customization and data/XML "
    "module import are OK; custom Python modules cannot be installed on Online — "
    "export install_mode=data or use Odoo.sh / self-host for Option A Python."
)

PROMOTE_ONLINE_SUBSTRING = "Odoo Online cannot install custom Python modules"


# ---------------------------------------------------------------------------
# M1 — hosting Online refuse + capabilities hosting fields
# ---------------------------------------------------------------------------


def test_online_operator_message_exact() -> None:
    assert hosting_operator_message("online", edition="community") == ONLINE_REFUSE_EXACT


def test_online_operator_message_enterprise_appends_studio_warn() -> None:
    msg = hosting_operator_message("online", edition="enterprise")
    assert msg.startswith(ONLINE_REFUSE_EXACT)
    assert "Enterprise edition detected" in msg
    assert "Studio" in msg
    assert "never used" in msg.lower() or "never" in msg.lower()


def test_hosting_hint_adversarial_urls() -> None:
    assert hosting_hint_from_url("https://ACME.ODOO.COM/web") == "online"
    assert hosting_hint_from_url("myco.odoo.com") == "online"  # scheme-less
    assert hosting_hint_from_url("https://build.odoo.sh") == "odoo_sh"
    assert hosting_hint_from_url("https://foo.odoo.sh/path") == "odoo_sh"
    assert hosting_hint_from_url(None) == "unknown"
    assert hosting_hint_from_url("") == "unknown"
    assert hosting_hint_from_url("   ") == "unknown"
    assert hosting_hint_from_url("http://127.0.0.1:8069") == "self_hosted"
    assert hosting_hint_from_url("http://localhost:8070") == "self_hosted"
    assert hosting_hint_from_url("http://host.docker.internal:8069") == "self_hosted"
    # Custom domain must NOT be classified as Online
    assert hosting_hint_from_url("https://odoo.mycompany.com") == "self_hosted"
    assert python_modules_allowed("online") is False
    assert python_modules_allowed("unknown") is True


def test_capabilities_hosting_hint_fields_exact_contract() -> None:
    online = capabilities_from_version("19.0", url="https://tenant.odoo.com")
    assert online is not None
    assert online.hosting_hint == "online"
    assert online.python_module_install is False
    assert ONLINE_REFUSE_EXACT in (online.message or "")
    assert any("Odoo Online" in w for w in online.warnings)
    assert any("Python" in w for w in online.warnings)

    sh = capabilities_from_version("18.0", url="https://proj.odoo.sh")
    assert sh is not None
    assert sh.hosting_hint == "odoo_sh"
    assert sh.python_module_install is True
    assert "Odoo.sh" in (sh.message or "")

    self_h = capabilities_from_version("17.0", url="http://127.0.0.1:8071")
    assert self_h is not None
    assert self_h.hosting_hint == "self_hosted"
    assert self_h.python_module_install is True
    assert "self-hosted" in (self_h.message or "").lower()

    no_url = capabilities_from_version("19.0")
    assert no_url is not None
    assert no_url.hosting_hint == "unknown"
    assert no_url.python_module_install is True


def test_promote_online_python_error_substring_and_guidance() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "x_adv_online/__manifest__.py",
            "{'name': 'Adv', 'version': '19.0.1.0.0', 'installable': True}",
        )
        zf.writestr("x_adv_online/models/__init__.py", "from . import models\n")
        zf.writestr(
            "x_adv_online/models/models.py",
            "from odoo import models\n\nclass X(models.Model):\n    _name = 'x.adv.online'\n",
        )
    client = OdooClient(
        ConnectionConfig(
            url="https://acme.odoo.com",
            db="acme",
            username="admin",
            password="admin",
        )
    )
    with pytest.raises(OdooClientError) as excinfo:
        promote_module_zip(client, buf.getvalue(), prefer_filesystem=False)
    err = str(excinfo.value)
    assert PROMOTE_ONLINE_SUBSTRING in err
    assert "install_mode=data" in err
    assert "Odoo.sh" in err or "self-hosted" in err.lower()
    # Must not soft-succeed or claim filesystem install
    assert "Installed" not in err


def test_confirm_phrase_locked() -> None:
    assert CONFIRM_PHRASE == "I understand the risks"


# ---------------------------------------------------------------------------
# M3 — config uom / fiscal unavailable (exact reasons)
# ---------------------------------------------------------------------------


class _FakeConfigHonesty:
    """Minimal fake: currencies OK; uom + fiscal absent."""

    def model_exists(self, model: str) -> bool:
        if model in {"uom.uom", "account.fiscal.position"}:
            return False
        if model == "res.currency.rate":
            return True
        return True

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        kwargs = kwargs or {}
        if method == "fields_get":
            return {"name": {}, "symbol": {}, "active": {}, "rate": {}}
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            name = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "name":
                    name = clause[2]
            if name in ("uom", "account"):
                return [{"id": 1, "state": "uninstalled"}]
            return []
        if model == "res.currency" and method == "search_read":
            return [{"id": 1, "name": "EUR", "symbol": "€", "active": True, "rate": 1.0}]
        raise AssertionError(f"unexpected {model}.{method}")


@pytest.fixture
def api_client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_conn(*, url: str = "http://127.0.0.1:8069", version: str = "19.0") -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="mastery-battery",
            url=url,
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version=version,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_config_uom_fiscal_unavailable_exact_reasons(api_client: TestClient) -> None:
    cid = _mk_conn()
    fake = _FakeConfigHonesty()
    with patch("app.routers.config_ops.client_from_connection", return_value=fake):
        uom = api_client.get(f"/api/connections/{cid}/config/uom")
        fiscal = api_client.get(f"/api/connections/{cid}/config/fiscal-positions")
        currencies = api_client.get(f"/api/connections/{cid}/config/currencies")

    assert uom.status_code == 200
    uom_body = uom.json()
    assert uom_body["available"] is False
    assert uom_body["rows"] in (None, [])
    assert uom_body["reason"] == "uom module / uom.uom not installed"

    assert fiscal.status_code == 200
    fiscal_body = fiscal.json()
    assert fiscal_body["available"] is False
    assert fiscal_body["reason"] == "account module / account.fiscal.position not installed"

    # Currencies must remain available when uom/account absent (honesty isolation)
    assert currencies.status_code == 200
    assert currencies.json()["available"] is True
    assert currencies.json()["rows"][0]["name"] == "EUR"


# ---------------------------------------------------------------------------
# M4 — pipeline major resolution (adversarial)
# ---------------------------------------------------------------------------


def test_pipeline_major_prefers_sandbox_when_stg_prod_empty() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id=None,
        prod_connection_id=None,
        sandbox_connection_id="sbx",
    )
    with patch(
        "app.routers.environments.get_connection_or_404",
        return_value=SimpleNamespace(server_version="16.0"),
    ):
        assert _pipeline_sandbox_major(MagicMock(), pipeline) == 16


def test_pipeline_major_skips_missing_connection_and_bad_version() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id="stg",
        prod_connection_id="prd",
        sandbox_connection_id="sbx",
    )

    def _get(_db, cid):
        if cid == "stg":
            raise LookupError("missing")
        if cid == "prd":
            return SimpleNamespace(server_version="15.0")  # unsupported → skip
        return SimpleNamespace(server_version="19.0-20260101")

    with patch("app.routers.environments.get_connection_or_404", side_effect=_get):
        assert _pipeline_sandbox_major(MagicMock(), pipeline) == 19


def test_pipeline_major_staging_beats_prod() -> None:
    pipeline = SimpleNamespace(
        staging_connection_id="stg",
        prod_connection_id="prd",
        sandbox_connection_id="sbx",
    )

    def _get(_db, cid):
        versions = {"stg": "17.0", "prd": "19.0", "sbx": "18.0"}
        return SimpleNamespace(server_version=versions[cid])

    with patch("app.routers.environments.get_connection_or_404", side_effect=_get):
        assert _pipeline_sandbox_major(MagicMock(), pipeline) == 17


# ---------------------------------------------------------------------------
# M5 — EE playbooks grey-out exact reasons
# ---------------------------------------------------------------------------


class _FakeEe:
    def __init__(self, states: dict[str, str]) -> None:
        self.states = states

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            name = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and len(clause) >= 3 and clause[0] == "name":
                    name = clause[2]
            if name and name in self.states:
                return [{"name": name, "state": self.states[name]}]
            if name:
                return []  # absent
            return []
        raise AssertionError(f"unexpected {model}.{method}")


def test_ee_playbooks_grey_out_exact_reasons(api_client: TestClient) -> None:
    cid = _mk_conn()
    fake = _FakeEe(states={"base": "installed", "web": "installed"})
    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = api_client.get(f"/api/connections/{cid}/ee-playbooks")
    assert res.status_code == 200
    by_id = {r["id"]: r for r in res.json()}

    assert by_id["sign_templates"]["available"] is False
    assert by_id["sign_templates"]["warn_only"] is False
    assert by_id["sign_templates"]["reason"] == "Modules not installed: sign=absent"

    assert by_id["documents_folders"]["available"] is False
    assert by_id["documents_folders"]["reason"] == "Modules not installed: documents=absent"

    assert by_id["studio_presence"]["available"] is False
    assert by_id["studio_presence"]["warn_only"] is True
    assert by_id["studio_presence"]["reason"] == "Modules not installed: web_studio=absent"


def test_ee_playbooks_studio_warn_only_when_installed(api_client: TestClient) -> None:
    cid = _mk_conn()
    fake = _FakeEe(
        states={
            "sign": "installed",
            "documents": "installed",
            "web_studio": "installed",
        }
    )
    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = api_client.get(f"/api/connections/{cid}/ee-playbooks")
    by_id = {r["id"]: r for r in res.json()}
    assert by_id["sign_templates"]["available"] is True
    assert by_id["sign_templates"]["reason"] == "RPC available"
    assert by_id["studio_presence"]["available"] is True
    assert by_id["studio_presence"]["warn_only"] is True
    assert "Studio" in by_id["studio_presence"]["reason"]
    assert "never used" in by_id["studio_presence"]["reason"].lower()
    # warn_only playbooks must not reuse the generic "RPC available" string
    assert by_id["studio_presence"]["reason"] != "RPC available"
