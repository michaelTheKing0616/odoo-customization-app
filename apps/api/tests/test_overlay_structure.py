"""Track D overlay structure ops — no app Postgres required."""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.routers.views import (  # noqa: E402
    OverlayApplyBody,
    ResolveStructureBody,
    _build_overlay_fragment,
    _raise_if_blocking_xpath,
    overlay_preview,
    resolve_structure_nodes,
)

pytestmark = pytest.mark.no_app_db

FORM_WITH_NOTEBOOK = (
    '<form><sheet><group id="g"><field name="email"/></group>'
    '<notebook><page string="Main"><field name="name"/></page></notebook>'
    "</sheet></form>"
)


def test_overlay_preview_add_page() -> None:
    out = overlay_preview(
        "unused",
        OverlayApplyBody(
            model="res.partner",
            view_type="form",
            operation="add_page",
            string="Notes",
            parent_arch=FORM_WITH_NOTEBOOK,
        ),
    )
    assert "x_page_notes" in out.xpath_arch
    assert "//notebook" in out.xpath_arch
    assert not any(i.severity == "error" for i in out.locator_issues)


def test_overlay_preview_add_group() -> None:
    out = overlay_preview(
        "unused",
        OverlayApplyBody(
            model="res.partner",
            view_type="form",
            operation="add_group",
            string="Flags",
            expr="//group[@id='g']",
            add_position="after",
            parent_arch=FORM_WITH_NOTEBOOK,
        ),
    )
    assert "x_group_flags" in out.xpath_arch
    assert not any(i.severity == "error" for i in out.locator_issues)


def test_move_inside_missing_group_blocks() -> None:
    fragment = _build_overlay_fragment(
        OverlayApplyBody(
            model="res.partner",
            view_type="form",
            operation="move",
            expr="//field[@name='email']",
            anchor_expr="//group[@id='missing']",
            move_position="inside",
            parent_arch=FORM_WITH_NOTEBOOK,
        )
    )
    with pytest.raises(HTTPException) as exc:
        _raise_if_blocking_xpath(fragment, FORM_WITH_NOTEBOOK)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "missing_node"


def test_resolve_structure_ranks_named_group() -> None:
    body = resolve_structure_nodes(ResolveStructureBody(arch=FORM_WITH_NOTEBOOK))
    xpaths = [c["xpath"] for c in body["candidates"]]
    assert "//group[@id='g']" in xpaths
    assert any(c["tag"] == "notebook" for c in body["candidates"])
