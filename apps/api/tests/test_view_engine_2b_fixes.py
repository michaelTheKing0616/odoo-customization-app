"""Builders stage 2b: fixes found in live runs on Odoo 17-20 (report resolver, email gate, brand preview)."""

from __future__ import annotations

from typing import Any

import pytest

from app import view_engine_report as vr
from app import view_engine_report_blocks as rb
from app.routers import view_engine as ver
from app.routers import view_engine_reports2 as r2

FIELDS = {"payment_reference": {"type": "char", "string": "Payment Reference"}}


def test_draws_page_finds_the_template_with_the_page() -> None:
    assert vr.draws_page('<t><div class="page"><p/></div></t>')
    assert vr.draws_page('<t><div class="article o_x page mt-2"/></t>')
    assert not vr.draws_page('<t><t t-foreach="docs" t-as="o"><t t-call="account.report_invoice"/></t></t>')
    assert not vr.draws_page('<t><div class="pagebreak"/></t>')


class ChainClient:
    """Fake Odoo: report_invoice_with_payments -> report_invoice -> report_invoice_document."""

    VIEWS = {
        "account.report_invoice_with_payments": '<t><t t-call="account.report_invoice"/></t>',
        "account.report_invoice": '<t><t t-foreach="docs" t-as="o"><t t-call="account.report_invoice_document"/></t></t>',
        "account.report_invoice_document": '<t><t t-call="web.external_layout"><div class="page"><h2 t-field="o.name"/></div></t></t>',
        "loop.a": '<t><t t-call="loop.b"/></t>',
        "loop.b": '<t><t t-call="loop.a"/></t>',
    }

    def __init__(self, report_name: str) -> None:
        self.report_name = report_name

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        if model == "ir.actions.report":
            return [{"id": 1, "name": "Invoice", "report_name": self.report_name, "model": "account.move", "report_type": "qweb-pdf"}]
        key = dict((d[0], d[2]) for d in args[0])["key"]
        arch = self.VIEWS.get(key)
        return [{"id": list(self.VIEWS).index(key) + 10, "key": key, "arch": arch}] if arch else []


def test_report_context_follows_the_call_chain_to_the_page() -> None:
    ctx = ver._report_context(ChainClient("account.report_invoice_with_payments"), 1)
    assert ctx["document"]["key"] == "account.report_invoice_document"
    assert ctx["record_var"] == "o"


def test_report_context_stops_on_call_loops() -> None:
    ctx = ver._report_context(ChainClient("loop.a"), 1)
    assert ctx["document"]["key"] in {"loop.a", "loop.b"}


def test_email_body_keeps_odoo_text_that_uses_t_out() -> None:
    body = '<div><p>Dear <t t-out="object.partner_id.name or \'\'"/>,</p><t t-if="object.state">x</t></div>'
    placements = rb.validate_placements([{"slot": "top", "blocks": [{"type": "heading", "text": "Hello"}]}],
                                        rb.EMAIL_SLOTS, FIELDS, email=True)
    out = rb.email_body(body, placements, FIELDS)
    assert "Hello" in out and 't-out="object.partner_id.name' in out


class BrandClient:
    """Fake Odoo whose wizard writes the colour through to the company (worst case)."""

    def __init__(self) -> None:
        self.company = {"id": 1, "name": "Co", "external_report_layout_id": False, "primary_color": False,
                        "secondary_color": False, "font": "Lato", "report_header": False, "report_footer": False,
                        "layout_background": "Blank"}
        self.created: dict[str, Any] = {}
        self.writes: list[dict[str, Any]] = []

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        if (model, method) == ("base.document.layout", "fields_get"):
            return {k: {"type": "char"} for k in r2.BRAND_FIELDS}
        if (model, method) == ("res.company", "fields_get"):
            return {k: {"type": "char"} for k in r2.BRAND_FIELDS if k != "layout_background"}  # like Odoo 20
        if (model, method) == ("res.company", "search_read"):
            assert "layout_background" not in kw["fields"]
            return [{k: v for k, v in self.company.items() if k in kw["fields"]}]
        if (model, method) == ("ir.model.data", "search_read"):
            return [{"res_id": 77}]
        if (model, method) == ("report.layout", "search"):
            return [5] if ("view_id", "=", 77) in args[0] else [9]
        if (model, method) == ("base.document.layout", "create"):
            self.created = args[0]
            self.company["primary_color"] = args[0].get("primary_color", self.company["primary_color"])
            return 3
        if (model, method) == ("base.document.layout", "read"):
            return [{"preview": "<div style='color:%s'>preview</div>" % self.created.get("primary_color")}]
        if (model, method) == ("res.company", "write"):
            self.writes.append(args[1])
            self.company.update(args[1])
            return True
        raise AssertionError((model, method))


def test_brand_preview_picks_a_layout_and_never_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = BrandClient()
    monkeypatch.setattr(r2, "_client", lambda cid, db: fake)
    out = r2.brand_preview("c1", r2.BrandBody(company_id=1, values={"primary_color": "#112233"}), db=None)
    assert "#112233" in out["html"]
    assert fake.created["report_layout_id"] == 5
    assert fake.company["primary_color"] is False and fake.writes == [{"primary_color": False}]


def test_brand_undo_uses_what_the_server_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = BrandClient()
    monkeypatch.setattr(r2, "_client", lambda cid, db: fake)

    class Row:
        pass

    monkeypatch.setattr(r2.vs, "list_items", lambda db, cid, kind, key=None: [Row()])
    monkeypatch.setattr(r2.vs, "item_out", lambda row: {"payload": {"previous": {"primary_color": "#000000"}}})
    out = r2.brand_undo("c1", r2.BrandUndoBody(company_id=1, previous={"report_header": "<script>"}), db=None)
    assert out["restored"] == {"primary_color": "#000000"} and fake.writes == [{"primary_color": "#000000"}]
    monkeypatch.setattr(r2.vs, "list_items", lambda db, cid, kind, key=None: [])
    with pytest.raises(r2.HTTPException) as exc:
        r2.brand_undo("c1", r2.BrandUndoBody(company_id=1, previous={}), db=None)
    assert exc.value.status_code == 409


def test_email_blocks_go_into_every_language_copy() -> None:
    placements = rb.validate_placements([{"slot": "top", "blocks": [{"type": "heading", "text": "Hello"}]}],
                                        rb.EMAIL_SLOTS, FIELDS, email=True)
    out = r2._with_blocks({"en_US": "<div><p>Dear</p></div>", "fr_FR": "<div><p>Cher</p></div>"}, placements, FIELDS)
    assert "Hello" in out["en_US"] and "Dear" in out["en_US"]
    assert "Hello" in out["fr_FR"] and "Cher" in out["fr_FR"]
    assert r2._with_blocks(out, [], FIELDS) == {"en_US": "<div><p>Dear</p></div>", "fr_FR": "<div><p>Cher</p></div>"}


def test_block_conditions_on_linked_records_are_checked_against_odoo(monkeypatch: pytest.MonkeyPatch) -> None:
    fields = {"partner_id": {"type": "many2one", "relation": "res.partner", "string": "Customer"}}
    seen = {}

    def names(client: Any, flds: dict, ids: dict) -> dict:
        seen.update(ids)
        return {"partner_id": {7: "Ada"}}

    monkeypatch.setattr(r2, "_record_names", names)
    pl = [{"slot": "top", "blocks": [{"type": "text", "text": "x", "condition": {"match": "all", "rules": [{"field": "partner_id", "op": "is", "value": 7}]}}]}]
    assert r2._condition_names(None, fields, pl) == {"partner_id": {7: "Ada"}} and seen == {"partner_id": {7}}
    clean = rb.validate_placements(pl, rb.EMAIL_SLOTS, fields, email=True, record_names={"partner_id": {7: "Ada"}})
    assert clean[0]["blocks"][0]["condition"]["rules"][0]["value"] == 7


def test_places_inside_odoo_conditions_are_marked_and_listed_last() -> None:
    doc = ('<t t-name="x"><div class="page"><div t-if="o.state == \'draft\'"><span t-field="o.name"/></div>'
           '<div id="always"/></div></t>')
    slots = [s for s in rb.slots_anywhere(doc, {"name": {"type": "char", "string": "Number"}}, "o") if s["id"] not in ("top", "bottom")]
    assert [s["label"] for s in slots] == ["Before 'Always'", "After 'Always'",
                                           "Before 'Number' (only on some documents)", "After 'Number' (only on some documents)"]
    assert slots[2]["conditional"] is True and "conditional" not in slots[0]


class CoClient:
    uid = 2

    def __init__(self, rec_co: int | None) -> None:
        self.rec_co = rec_co

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        if model == "res.users":
            return [{"company_ids": [1, 2]}]
        return [{"company_id": [self.rec_co, "Co"] if self.rec_co else False}]


def test_prints_use_the_records_company_first() -> None:
    from app.routers import view_engine_logic as vel

    assert vel._print_companies(CoClient(2), "account.move", 5, None) == [2, 1]
    assert vel._print_companies(CoClient(2), "account.move", 5, [2]) == [2, 1]
    assert vel._print_companies(CoClient(None), "res.partner", 5, None) is None
    with pytest.raises(vel.HTTPException) as exc:
        vel._print_companies(CoClient(1), "account.move", 5, [2])
    assert exc.value.status_code == 422
    with pytest.raises(vel.HTTPException) as exc:
        vel._print_companies(CoClient(None), "res.partner", 5, [3])
    assert exc.value.status_code == 403


class DomClient:
    def __init__(self, has_field: bool, rows: list[dict]) -> None:
        self.has_field, self.rows = has_field, rows

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        if method == "fields_get":
            return {"domain": {"type": "char"}} if self.has_field else {}
        return self.rows


def test_print_domain_comes_from_the_report_chain_and_ignores_unsafe_text() -> None:
    rows = [{"domain": "[('move_type', '!=', 'entry')]"}, {"domain": "[]"}, {"domain": False}, {"domain": "__import__('os')"}]
    assert ver._print_domain(DomClient(True, rows), ["a", "b"]) == [["move_type", "!=", "entry"]]
    assert ver._print_domain(DomClient(False, rows), ["a"]) == []  # Odoo 17 has no report filter
    two = [{"domain": "['|', ('a', '=', 1), ('b', '=', 2)]"}, {"domain": "[('c', '=', 3)]"}]
    assert ver._print_domain(DomClient(True, two), ["a"]) == ["|", ["a", "=", 1], ["b", "=", 2], ["c", "=", 3]]


def test_odoo_print_refusal_is_shown_in_plain_words() -> None:
    import io as _io
    from urllib.error import HTTPError

    from app.routers import view_engine_logic as vel

    page = b"<html><main><p><pre>Only invoices could be printed.</pre></p></main></html>"
    exc = HTTPError("http://x/report/pdf/a/1", 422, "UNPROCESSABLE ENTITY", {}, _io.BytesIO(page))
    assert vel._odoo_print_reason(exc) == "Only invoices could be printed."
    assert vel._odoo_print_reason(HTTPError("u", 500, "x", {}, _io.BytesIO(b"<html>boom</html>"))) is None


class LayoutClient:
    def __init__(self, views: dict[str, str]) -> None:
        self.views = views

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        key = dict((d[0], d[2]) for d in args[0])["key"]
        return [{"arch": self.views[key]}] if key in self.views else []


def test_page_numbers_found_in_called_footer_template_like_odoo_20() -> None:
    v20 = ('<t t-name="web.external_layout_standard"><div t-attf-class="footer o_company_#{company.id}_layout">'
           '<t t-call="web.external_layout_footer_content"/></div></t>')
    called = {"web.external_layout_footer_content": '<div><div t-if="report_type == \'pdf\'">Page <span class="page"/> / <span class="topage"/></div></div>'}
    assert r2._shows_page_numbers(LayoutClient(called), v20)
    assert not r2._shows_page_numbers(LayoutClient({}), v20)
    assert r2._footer_expr(v20) == "//div[starts-with(@t-attf-class, 'footer')]"
    assert r2._footer_expr('<t><div class="footer o_standard_footer"/></t>') == "//div[hasclass('footer')]"
    assert r2._footer_expr('<t><div class="header"/></t>') is None
