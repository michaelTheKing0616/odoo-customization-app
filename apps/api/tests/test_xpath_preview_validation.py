"""XPath preview + resolve-field validation (upgrade-safe locators).

Uses the views router without app.main lifespan so these tests do not need Postgres.
"""

from __future__ import annotations

import os

os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("FERNET_KEY", "dev-only-test")

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.routers.views import (  # noqa: E402
    OverlayApplyBody,
    _raise_if_blocking_xpath,
    overlay_preview,
    router,
)

pytestmark = pytest.mark.no_app_db

PARTNER_ARCH = """
<form>
  <sheet>
    <group id="header_left_group">
      <field name="partner_id"/>
    </group>
    <group string="Other">
      <field name="ref"/>
    </group>
    <notebook>
      <page string="Lines">
        <field name="line_ids">
          <list>
            <field name="partner_id"/>
          </list>
        </field>
      </page>
    </notebook>
  </sheet>
</form>
"""


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_xpath_preview_classifies_parent_arch() -> None:
    client = _client()
    missing = client.post(
        "/api/connections/fake/views/xpath/preview",
        json={
            "expr": "//field[@name='nope']",
            "body_xml": "<field name='x_extra'/>",
            "parent_arch": PARTNER_ARCH,
        },
    )
    assert missing.status_code == 200, missing.text
    body = missing.json()
    assert body["blocking"] is True
    codes = {i["code"] for i in body["locator_issues"]}
    assert "missing_node" in codes
    assert any("matches no node" in msg for msg in body["issues"])

    positional = client.post(
        "/api/connections/fake/views/xpath/preview",
        json={
            "expr": "//group[2]",
            "body_xml": "<field name='x_extra'/>",
            "parent_arch": PARTNER_ARCH,
        },
    )
    assert positional.status_code == 200
    pos = positional.json()
    assert pos["blocking"] is False
    assert pos["suggested_expr"] == "//group[@string='Other']"
    assert any(i["code"] == "positional_fragility" for i in pos["locator_issues"])
    assert pos["default_inject_expr"] == "//group[@id='header_left_group']"

    ok = client.post(
        "/api/connections/fake/views/xpath/preview",
        json={
            "expr": "//group[@id='header_left_group']//field[@name='partner_id']",
            "body_xml": "<field name='x_extra'/>",
            "parent_arch": PARTNER_ARCH,
        },
    )
    assert ok.status_code == 200
    clean = ok.json()
    assert clean["blocking"] is False
    assert clean["match_count"] == 1
    assert not any(i["severity"] == "error" for i in clean["locator_issues"])


def test_resolve_field_returns_distinct_semantic_candidates() -> None:
    client = _client()
    res = client.post(
        "/api/connections/fake/views/resolve-field",
        json={"view_type": "form", "arch": PARTNER_ARCH, "field_name": "partner_id"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    xpaths = [c["xpath"] for c in body["candidates"]]
    assert len(xpaths) >= 2
    assert len(set(xpaths)) == len(xpaths)
    assert xpaths[0] == "//group[@id='header_left_group']//field[@name='partner_id']"
    assert body["candidates"][0]["match_count"] == 1
    assert body["candidates"][0]["fragile"] is False
    assert body["ambiguous"] is True


def test_overlay_preview_flags_positional_without_parent() -> None:
    out = overlay_preview(
        "fake",
        OverlayApplyBody(
            model="res.partner",
            view_type="form",
            operation="hide",
            expr="//group[2]/field[1]",
        ),
    )
    codes = {i.code for i in out.locator_issues}
    assert "positional_fragility" in codes
    assert out.issues


def test_raise_if_blocking_xpath_on_missing_node() -> None:
    arch = (
        "<data>"
        "<xpath expr=\"//field[@name='missing']\" position=\"inside\">"
        "<field name=\"x_extra\"/>"
        "</xpath>"
        "</data>"
    )
    parent = '<form><sheet><field name="email"/></sheet></form>'
    try:
        _raise_if_blocking_xpath(arch, parent)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail["code"] == "missing_node"
        assert exc.detail["expr"] == "//field[@name='missing']"
        return
    raise AssertionError("expected 422 for missing locator")


def test_raise_if_blocking_xpath_allows_warnings() -> None:
    arch = (
        "<data>"
        "<xpath expr=\"//group[1]\" position=\"inside\">"
        "<field name=\"x_extra\"/>"
        "</xpath>"
        "</data>"
    )
    _raise_if_blocking_xpath(arch, PARTNER_ARCH)
