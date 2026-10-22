"""DOC-QWEB — unsafe gate on general QWeb view save (PDF-05 family)."""

from __future__ import annotations

import os
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

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.qweb_view_blocks import (  # noqa: E402
    QwebViewBlock,
    compile_qweb_view_blocks,
    default_qweb_view_blocks,
    extract_t_call_targets,
    gate_qweb_view_save,
    refuse_root_replace,
    refuse_unsafe_qweb_view_arch,
    refuse_unsafe_qweb_view_blocks,
    try_parse_qweb_view_blocks,
)


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def connection_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="qweb-gate-test",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_refuse_script_t_raw_xxe() -> None:
    with pytest.raises(ValueError, match="script"):
        refuse_unsafe_qweb_view_arch("<div><script>x</script></div>")
    with pytest.raises(ValueError, match="t-raw"):
        refuse_unsafe_qweb_view_arch('<div t-raw="object.x"/>')
    with pytest.raises(ValueError, match="external entities|DOCTYPE"):
        refuse_unsafe_qweb_view_arch(
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><t/>'
        )


def test_refuse_invented_t_call_allow_grandfather() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        refuse_unsafe_qweb_view_arch('<t t-call="evil.template"/>')
    refuse_unsafe_qweb_view_arch(
        '<t t-call="sale.report_saleorder_document"><div/></t>',
        allow_existing_t_calls=["sale.report_saleorder_document"],
    )
    refuse_unsafe_qweb_view_arch('<t t-call="web.external_layout"><div/></t>')


def test_refuse_root_replace() -> None:
    with pytest.raises(ValueError, match="root or a large subtree"):
        refuse_root_replace("/", "replace")
    refuse_root_replace("//div[hasclass('page')]", "inside")
    refuse_root_replace("//div[@id='x']", "after")


def test_refuse_on_handlers_and_js_urls() -> None:
    with pytest.raises(ValueError, match="event handlers"):
        refuse_unsafe_qweb_view_arch('<p onclick="alert(1)">x</p>')
    with pytest.raises(ValueError, match="javascript:"):
        refuse_unsafe_qweb_view_arch('<a href="javascript:alert(1)">x</a>')


def test_block_text_qweb_markers() -> None:
    with pytest.raises(ValueError, match="QWeb"):
        refuse_unsafe_qweb_view_blocks(
            [QwebViewBlock(id="1", kind="paragraph", text="Hello {{ object.x }}")]
        )


def test_compile_and_roundtrip_parse() -> None:
    blocks = default_qweb_view_blocks("Invoice header")
    arch = compile_qweb_view_blocks(blocks, wrap_external_layout=False)
    parsed = try_parse_qweb_view_blocks(arch)
    assert parsed is not None
    assert [b.kind for b in parsed] == ["heading", "paragraph", "field"]
    assert parsed[0].text == "Invoice header"
    assert parsed[2].field == "display_name"


def test_extract_t_call_targets() -> None:
    arch = '<t t-call="web.external_layout"><t t-call="sale.report_saleorder_document"/></t>'
    assert extract_t_call_targets(arch) == frozenset(
        {"web.external_layout", "sale.report_saleorder_document"}
    )


def test_gate_save_ok() -> None:
    blocks = default_qweb_view_blocks()
    arch = compile_qweb_view_blocks(blocks, wrap_external_layout=True)
    gate_qweb_view_save(blocks, arch)


def _fake_client_for_save():
    fake = MagicMock()
    state = {"arch": '<div class="page"><p>Hi</p></div>'}

    def execute_kw(model, method, args, kwargs=None):
        if model == "ir.actions.report" and method == "search_read":
            return []
        if model == "ir.ui.view" and method == "read":
            return [
                {
                    "id": 9,
                    "name": "Custom QWeb",
                    "key": "x_mod.doc",
                    "model": "res.partner",
                    "type": "qweb",
                    "arch": state["arch"],
                    "mode": "primary",
                    "priority": 16,
                    "inherit_id": False,
                }
            ]
        if model == "ir.ui.view" and method == "search":
            return []
        if model == "ir.ui.view" and method == "write":
            state["arch"] = args[1]["arch"]
            return True
        if model == "ir.ui.view" and method == "create":
            return 99
        raise AssertionError(f"unexpected {model}.{method}")

    fake.execute_kw = execute_kw
    return fake


def test_api_save_refuses_script(client: TestClient, connection_id: str) -> None:
    fake = _fake_client_for_save()
    with patch("app.routers.qweb_views.client_from_connection", return_value=fake):
        with patch(
            "app.routers.qweb_views.snapshot_view",
            return_value=MagicMock(id="snap"),
        ):
            res = client.put(
                f"/api/connections/{connection_id}/qweb-views/9",
                json={
                    "arch": "<div><script>bad</script></div>",
                    "strategy": "overwrite",
                    "confirm_advanced": True,
                    "confirm_phrase": "I understand the risks",
                },
            )
    assert res.status_code == 400
    assert "script" in res.json()["detail"].lower()


def test_api_save_inherit_blocks(client: TestClient, connection_id: str) -> None:
    fake = _fake_client_for_save()
    with patch("app.routers.qweb_views.client_from_connection", return_value=fake):
        with patch(
            "app.routers.qweb_views.snapshot_view",
            return_value=MagicMock(id="snap"),
        ):
            res = client.put(
                f"/api/connections/{connection_id}/qweb-views/9",
                json={
                    "strategy": "inherit",
                    "inherit_xpath": "//div[hasclass('page')]",
                    "inherit_position": "inside",
                    "blocks": [
                        {
                            "id": "h-1",
                            "kind": "heading",
                            "text": "Extra",
                            "level": 2,
                        }
                    ],
                },
            )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["strategy"] == "inherit"
    assert body["id"] == 99
