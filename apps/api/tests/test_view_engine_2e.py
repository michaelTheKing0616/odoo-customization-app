"""Stage 2e: approval rule on own layers, role layouts living with normal publishes, scanned PDFs, chat test send, compare."""
from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import view_engine_2d as v2d
from app import view_engine_store as vs
from app.routers import view_engine_2c as r2c
from app.routers import view_engine_2d as r2d


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    vs._ensure_tables(session)
    yield session
    session.close()


class FakeOdoo:
    def __init__(self, layers: list[dict[str, Any]]) -> None:
        self.layers = {int(x["id"]): dict(x) for x in layers}
        self.calls: list[tuple] = []

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        self.calls.append((method, args))
        if method == "search_read":
            return [dict(x) for x in self.layers.values() if x["active"]]
        if method == "write":
            vals = args[1]
            for i in args[0]:
                self.layers[int(i)].update({("arch_db" if k == "arch" else k): v for k, v in vals.items()})
            return True
        if method == "get_combined_arch":
            raise RuntimeError("not used")
        return True


def test_own_layers_follow_the_approval_rule(db) -> None:
    vs.save_item(db, connection_id="c1", kind="policy", key="approval", name="p", payload={"required": True}, replace_key=True)
    with pytest.raises(HTTPException) as e:
        r2d._own_layer(FakeOdoo([]), db, "c1", model="sale.order", vt="form", view={"id": 1}, name="x", arch="<data/>", summary="s", expect=[])
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        r2c._scoped_publish(FakeOdoo([]), db, "c1", model="sale.order", vt="form", view={"id": 1}, view_id=None, name="x", arch="<data/>",
                            role="g.r", cat=None, summary="s", expect=[])  # type: ignore[arg-type]
    assert {"checklist_publish", "steps_publish"} <= set(r2c.APPROVAL_ACTIONS)


def test_role_layers_pause_and_restore(db) -> None:
    odoo = FakeOdoo([{"id": 7, "name": "ingenium_steps_x", "arch_db": "<data>old</data>", "active": True}])
    with pytest.raises(ValueError), r2c.role_layers_paused(odoo, db, "c1", "sale.order", 1):
        assert odoo.layers[7]["active"] is False
        raise ValueError("publish failed")
    assert odoo.layers[7]["active"] is True and odoo.layers[7]["arch_db"] == "<data>old</data>"
    with r2c.role_layers_paused(odoo, db, "c1", "sale.order", 1) as notes:
        assert odoo.layers[7]["active"] is False
    assert odoo.layers[7]["active"] is True and "as it was" in notes[0]


def test_scanned_pdf_pages_render() -> None:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, format="PDF")
    pngs = v2d.pdf_page_pngs(buf.getvalue())
    assert len(pngs) == 1 and pngs[0][:4] == b"\x89PNG"


def test_chat_test_send_reports_the_reply(db, monkeypatch) -> None:
    import urllib.error

    with pytest.raises(HTTPException) as e:
        r2d.digest_chat_send("c1", db)
    assert e.value.status_code == 422  # nothing configured, nothing sent
    vs.save_item(db, connection_id="c1", kind="digest_chat", key="weekly", name="Chat digest",
                 payload={"on": True, "url": "https://hooks.slack.com/services/T/B/secretx", "kind": "slack"}, replace_key=True)
    monkeypatch.setattr(r2c, "build_digest", lambda db, cid, days: {"text": "hello"})
    sent: list[str] = []

    def fake_send(p, title, text):
        sent.append(title)
        raise urllib.error.HTTPError(p["url"], 403, "Forbidden", None, io.BytesIO(b"invalid_token"))  # type: ignore[arg-type]

    monkeypatch.setattr(r2d, "send_chat", fake_send)
    with pytest.raises(HTTPException) as e2:
        r2d.digest_chat_send("c1", db)
    assert e2.value.status_code == 502 and "403: invalid_token" in e2.value.detail["message"] and "secretx" not in str(e2.value.detail)
    assert sent == ["[Test] Weekly screen changes"]


def test_outline_lists_visible_items() -> None:
    tree = {"id": "form", "tag": "form", "children": [{"id": "page:a", "tag": "page", "label": "A", "children": [
        {"id": "field:x", "tag": "field", "name": "x", "label": "X"}, {"id": "field:y", "tag": "field", "name": "y", "attrs": {"invisible": "1"}}]}]}
    out = v2d.outline(tree)
    assert [o["label"] for o in out] == ["A", "X", "y"] and out[2]["hidden"]


def test_chat_reply_must_confirm() -> None:
    assert v2d.chat_accepted("https://hooks.slack.com/services/a", 200, "ok")
    assert not v2d.chat_accepted("https://hooks.slack.com/services/a", 200, "<html>")
    assert v2d.chat_accepted("https://x.webhook.office.com/a", 200, "1")
    assert not v2d.chat_accepted("https://outlook.office.com/webhook/a", 200, "<!DOCTYPE html>")
    assert not v2d.chat_accepted("https://outlook.office.com/webhook/a", 200, "")
    assert v2d.chat_accepted("https://prod-1.westus.logic.azure.com/a", 202, "")


def test_cross_diff_ignores_version_naming() -> None:
    def scr(fid: str, label: str, inv: str, extra: bool) -> dict:
        kids = [{"id": f"{fid}:a", "tag": "field", "name": "partner_id", "label": label, "attrs": {"invisible": inv}},
                {"id": f"{fid}:g", "tag": "group", "attrs": {}, "children": []}]
        if extra:
            kids.append({"id": f"{fid}:b", "tag": "field", "name": "x_note", "label": "Note", "attrs": {"required": "True"}})
        return {"id": f"{fid}:root", "tag": "form", "children": kids}
    same = v2d.cross_diff(scr("v18", "Customer", "state != 'draft'", False), scr("v20", "Client", "state not in ('draft',)", False))
    assert same == []
    real = v2d.cross_diff(scr("v18", "Customer", "1", False), scr("v20", "Client", "", True))
    # hidden on one side only = shown only there; the new field is shown only there too
    assert sorted(d["text"] for d in real) == ["Only there: Client", "Only there: Note"]
    always_hidden = v2d.cross_diff(scr("v18", "Customer", "1", False), scr("v20", "Client", "True", False))
    assert always_hidden == []


def test_teams_workflow_links() -> None:
    url = "https://prod-01.westeurope.logic.azure.com/workflows/abc/triggers/manual/paths/invoke?sig=x"
    assert v2d.check_webhook(url) == "teams_workflow"
    assert v2d.check_webhook("https://default1.environment.api.powerplatform.com/powerautomate/automations/direct/x") == "teams_workflow"
    assert v2d.chat_accepted(url, 202, "")
    assert v2d.chat_payload("teams_workflow", "T", "x")["attachments"][0]["content"]["type"] == "AdaptiveCard"


def test_layout_test_start_and_stop_follow_the_approval_rule(db, monkeypatch) -> None:
    monkeypatch.setattr(r2c, "approval_policy", lambda _db, _cid: True)
    monkeypatch.setattr(r2c, "_client", lambda *_a: pytest.fail("must not reach Odoo"))
    with pytest.raises(HTTPException) as e:
        r2c.abtest_stop("c1", r2c.ItemRef(item_id="x"), db)
    assert e.value.status_code == 403 and e.value.detail["needs_approval"]
    body = r2c.ABStartBody(model="res.partner", view_type="form", ops=[{"op": "hide", "node": "n"}], role_b="1", metric_field="phone")
    with pytest.raises(HTTPException):
        r2c.abtest_start("c1", body, db)
    assert {"abtest_start", "abtest_stop"} <= set(r2c.APPROVAL_ACTIONS)
