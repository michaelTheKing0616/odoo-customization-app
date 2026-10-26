"""BOT-CONFIG-VERIFY live: Odoo 17 (18117) and 20 (18120), ODOO_LIVE=1. Setup records are made
with the admin caller; verification runs only through configverify's read-only caller."""

from __future__ import annotations

import uuid

import pytest

from app.bots import configverify as cv
from tests.test_nf_bot_sinkhole_live import LIVE, Json

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="set ODOO_LIVE=1")]


@pytest.mark.parametrize("v", [17, 20])
def test_live_verify(v) -> None:
    o, tag = Json(v), uuid.uuid4().hex[:6]
    par = o("res.partner.category", "create", [{"name": f"cv par {tag}"}])  # setup
    kid = o(
        "res.partner.category", "create", [{"name": f"cv kid {tag}", "parent_id": par}]
    )  # setup
    pn = o(
        "res.partner", "create", [{"name": f"cv p {tag}", "category_id": [(6, 0, [kid])]}]
    )  # setup
    kdn = o("res.partner.category", "read", [[kid]], {"fields": ["display_name"]})[0][
        "display_name"
    ]
    seen: list[str] = []

    def spy(m, meth, a, kw=None):
        seen.append(meth)
        return o(m, meth, a, kw)

    pref = f"res.partner.category:name=cv par {tag}"
    kref = f"res.partner.category:name=cv kid {tag}"
    items = [
        {
            "kind": "module",
            "model": "ir.module.module",
            "key": {"name": "base"},
            "expected": {"state": "installed"},
            "ref": "m",
        },
        {
            "kind": "record",
            "model": "res.partner.category",
            "key": {"name": f"cv par {tag}"},
            "expected": {"active": True},
            "ref": pref,
        },
        {
            "kind": "record",
            "model": "res.partner.category",
            "key": {"name": f"cv kid {tag}"},
            "expected": {},
            "relations": {"parent_id": pref},
            "ref": kref,
        },
        {
            "kind": "record",
            "model": "res.partner",
            "key": {"name": f"cv p {tag}"},
            "expected": {"category_id": [kdn]},
            "relations": {"category_id": [kref]},
            "ref": "p",
        },
        {
            "kind": "record",
            "model": "res.partner",
            "key": {"name": f"cv absent {tag}"},
            "expected": {},
            "ref": "a",
        },
        {
            "kind": "record",
            "model": "x.no.such.model",
            "key": {"name": "x"},
            "expected": {},
            "ref": "x",
        },
        {
            "kind": "record",
            "model": "res.partner",
            "key": {"name": f"cv p {tag}"},
            "expected": {"no_field_x": 1},
            "ref": "f",
        },
    ]
    try:
        out = cv.verify(
            {"spec_version": 1, "status": "designed", "items": items}, spy, companies=[1]
        )
        got = [i["status"] for i in out["items"]]
        assert got == ["matches"] * 4 + ["missing", "cannot-read", "cannot-read"], [
            (i["status"], i.get("reason"), i["diffs"]) for i in out["items"]
        ]
        assert set(seen) <= cv.READ_METHODS
        o(
            "res.partner.category", "write", [[par], {"name": f"cv par2 {tag}"}]
        )  # setup: break link target
        out = cv.verify(
            {"spec_version": 1, "status": "designed", "items": items[1:4]}, spy, companies=[1]
        )
        assert [i["status"] for i in out["items"]] == ["missing", "differs", "differs"]
    finally:
        o("res.partner", "unlink", [[pn]])  # cleanup
        o("res.partner.category", "unlink", [[kid, par]])  # cleanup
