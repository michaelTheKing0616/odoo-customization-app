"""Builders stage 2b: report and email blocks, page checks, compare, gallery."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app import view_engine as ve
from app import view_engine_report_blocks as rb

FIELDS = {
    "name": {"type": "char", "string": "Number"},
    "payment_reference": {"type": "char", "string": "Payment Reference"},
    "state": {"type": "selection", "string": "Status", "selection": [["draft", "Draft"], ["posted", "Posted"]]},
    "partner_id": {"type": "many2one", "string": "Customer", "relation": "res.partner"},
    "invoice_date": {"type": "date", "string": "Invoice Date"},
    "amount_total": {"type": "monetary", "string": "Total"},
    "invoice_line_ids": {"type": "one2many", "string": "Lines", "relation": "account.move.line"},
    "signature": {"type": "binary", "string": "Signature"},
    "signed_by": {"type": "char", "string": "Signed By"},
    "narration": {"type": "html", "string": "Terms"},
}
LINES = {"name": {"type": "char", "string": "Label"}, "quantity": {"type": "float", "string": "Quantity"},
         "price_subtotal": {"type": "monetary", "string": "Subtotal"}, "product_id": {"type": "many2one", "string": "Product"}}
DOC = (
    '<t t-name="account.report_invoice_document"><t t-call="web.external_layout"><div class="page">'
    '<h2><span t-field="o.name"/></h2><div id="informations" class="row"><div name="invoice_date"><span t-field="o.invoice_date"/></div></div>'
    '<table class="table o_main_table" name="invoice_line_table"><tbody><tr t-foreach="o.invoice_line_ids" t-as="line">'
    '<td><span t-field="line.name"/></td><td name="qty"><span t-field="line.quantity"/></td></tr></tbody></table>'
    '<div id="total" class="row"><span t-field="o.amount_total"/></div><p name="payment_communication"/></div></t></t>'
)


def _slots() -> list[dict[str, str]]:
    return rb.slots_anywhere(DOC, FIELDS, "o")


def test_slots_anywhere_are_stable_unique_and_never_inside_line_loops() -> None:
    slots = _slots()
    ids = [s["id"] for s in slots]
    assert {"top", "bottom"} <= set(ids)
    xps = {s["xpath"] for s in slots}
    assert "//div[@id='informations']" in xps and "//div[@id='total']" in xps
    assert "//table[@name='invoice_line_table']" in xps
    assert "//span[@t-field='o.invoice_date']" in xps
    assert not any("line." in x or "@name='qty'" in x for x in xps)  # inside the per-line loop
    labels = {s["label"] for s in slots}
    assert "After 'Invoice Date'" in labels
    assert len(ids) == len(set(ids))


def test_every_block_type_compiles_and_passes_the_unsafe_gate() -> None:
    blocks = [
        {"type": "heading", "text": "How to pay", "level": 4},
        {"type": "text", "text": "Thanks & see you <soon>"},
        {"type": "field", "field": "partner_id.name"},
        {"type": "label_field", "field": "payment_reference"},
        {"type": "divider"}, {"type": "spacer", "size": "large"},
        {"type": "line_table", "field": "invoice_line_ids", "columns": [{"field": "name"}, {"field": "quantity", "sum": True},
                                                                       {"field": "price_subtotal", "sum": True, "label": "Amount"}]},
        {"type": "qr", "field": "payment_reference"}, {"type": "barcode", "field": "name"},
        {"type": "signature", "field": "signature", "signed_by": "signed_by"},
        {"type": "watermark", "text": "DRAFT", "colour": "red", "condition": {"match": "all", "rules": [{"field": "state", "op": "is", "value": "draft"}]}},
        {"type": "page_break"},
    ]
    placements = rb.validate_placements([{"slot": "after_div_id_total", "blocks": blocks}], _slots(), FIELDS, {"invoice_line_ids": LINES})
    arch = rb.compile_layer(placements, _slots(), "o", FIELDS)
    root = ET.fromstring(arch)
    assert root.find("xpath").get("expr") == "//div[@id='total']" and root.find("xpath").get("position") == "after"
    assert "sum(o.invoice_line_ids.mapped('price_subtotal'))" in arch
    assert "'symbology': 'QR'" in arch and "image_data_uri(o.signature)" in arch
    assert [t.get("t-if") for t in root.iter("t")] == ["o.state == 'draft'"]
    assert "&lt;soon&gt;" in arch
    assert f"{rb.BLOCK_CLASS}_1" in arch
    assert rb.published_markers(arch) == [f"{rb.BLOCK_CLASS}_1"]
    assert "How to pay" in rb.expected_texts(placements) and "Amount" in rb.expected_texts(placements)


def test_condition_expressions_on_the_record() -> None:
    cond = {"match": "any", "rules": [{"field": "state", "op": "is", "value": "draft"}, {"field": "partner_id", "op": "set"}]}
    assert rb.condition_expr(cond, FIELDS, "o") == "(o.state == 'draft') or (o.partner_id)"
    with pytest.raises(ve.EngineError):
        rb.condition_expr({"match": "all", "rules": [{"field": "invoice_date", "op": "gt", "value": "2026-01-01"}]}, FIELDS, "o")


def test_bad_blocks_are_refused_plainly() -> None:
    slots = _slots()
    with pytest.raises(ve.EngineError):
        rb.validate_placements([{"slot": "nowhere", "blocks": [{"type": "divider"}]}], slots, FIELDS)
    with pytest.raises(ve.EngineError):
        rb.validate_blocks([{"type": "text", "text": "<t t-esc='1'/>"}], FIELDS)
    with pytest.raises(ve.EngineError):
        rb.validate_blocks([{"type": "qr", "field": "amount_total"}], FIELDS)
    with pytest.raises(ve.EngineError):
        rb.validate_blocks([{"type": "line_table", "field": "invoice_line_ids", "columns": [{"field": "name", "sum": True}]}], FIELDS,
                           {"invoice_line_ids": LINES})
    with pytest.raises(ve.EngineError):
        rb.validate_blocks([{"type": "watermark", "text": "X"}], FIELDS, email=True)


def test_draft_layer_hides_each_published_wrapper_and_needs_the_token() -> None:
    slots = _slots()
    placements = rb.validate_placements([{"slot": "bottom", "blocks": [{"type": "text", "text": "Hi"}]}], slots, FIELDS)
    arch = rb.compile_layer(placements, slots, "o", FIELDS, token="abcdef0123456789", hide_published=[f"{rb.BLOCK_CLASS}_1", f"{rb.BLOCK_CLASS}_2"])
    assert arch.count('position="attributes"') == 2
    assert "ingenium_draft') == 'abcdef0123456789'" in arch
    with pytest.raises(ve.EngineError):
        rb.compile_layer(placements, slots, "o", FIELDS, token="nope")


def test_email_body_add_replace_and_strip_keeps_odoo_text() -> None:
    body = '<div style="margin:0"><p>Dear <t t-esc="object.partner_id.name"/>,</p><p>Here is your invoice.</p></div>'
    placements = rb.validate_placements([{"slot": "top", "blocks": [{"type": "heading", "text": "Hello"}]},
                                         {"slot": "bottom", "blocks": [{"type": "label_field", "field": "payment_reference"}]}],
                                        rb.EMAIL_SLOTS, FIELDS, email=True)
    out = rb.email_body(body, placements, FIELDS)
    assert out.index("Hello") < out.index("Here is your invoice.") < out.index("object.payment_reference")
    again = rb.email_body(out, placements[:1], FIELDS)
    assert again.count("Hello") == 1 and "object.payment_reference" not in again
    assert rb.strip_email_blocks(out) == body


def _pdf(pages: list[list[tuple[float, float, str]]]) -> bytes:
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    kids = []
    font_id = 3
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for runs in pages:
        stream = "".join(f"BT /F1 10 Tf {x} {y} Td ({t}) Tj ET\n" for x, y, t in runs).encode()
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
        cid = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (font_id, cid))
        kids.append(len(objs))
    objs[1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids) + b"] /Count %d >>" % len(kids)
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def test_page_checks_flag_split_lines_overflow_and_page_count() -> None:
    one = _pdf([[(72, 700, "Line Alpha Widget"), (72, 680, "Total 10")]])
    two = _pdf([[(72, 700, "Line Alpha Widget")], [(72, 700, "Line Omega Gadget"), (560, 650, "OVERFLOWING TEXT HERE")]])
    assert rb.page_checks(one, line_markers=["Line Alpha Widget", "Line Omega Gadget"]) == []
    kinds = {i["kind"] for i in rb.page_checks(two, line_markers=["Line Alpha Widget", "Line Omega Gadget"], published_pages=1)}
    assert kinds == {"split", "overflow", "pages"}
    diff = rb.compare_texts(one, two)
    assert diff["pages_before"] == 1 and diff["pages_after"] == 2 and not diff["same"]
    assert "Total 10" in diff["pages"][0]["removed"]


def test_gallery_only_shows_starters_that_fit() -> None:
    slots = _slots()
    keys = {s["key"] for s in rb.gallery_for("account.move", FIELDS, {}, slots)}
    assert {"invoice_payment_qr", "invoice_thanks", "invoice_draft_watermark"} <= keys
    no_ref = {k: v for k, v in FIELDS.items() if k != "payment_reference"}
    assert "invoice_payment_qr" not in {s["key"] for s in rb.gallery_for("account.move", no_ref, {}, slots)}
    assert rb.gallery_for("res.partner", FIELDS, {}, slots) == []
    for s in rb.STARTERS:
        if s["model"] == "account.move":
            rb.validate_placements(s["placements"], slots, FIELDS)


def test_visual_compare_highlights_new_and_gone_ink_per_page() -> None:
    import base64

    before = _pdf([[(50, 800, "Invoice INV-001"), (50, 100, "Old footer text here")]])
    after = _pdf([[(50, 800, "Invoice INV-001"), (50, 700, "NEW BLOCK ADDED HERE")], [(50, 800, "Second page")]])
    out = rb.visual_compare(before, after, scale=0.5)
    assert out["page_counts"] == {"published": 1, "draft": 2} and not out["same"]
    p1, p2 = out["pages"]
    assert p1["changed_percent"] > 0 and p1["only_in"] is None and "changed" in p1["summary"]
    assert p2["only_in"] == "draft"
    assert base64.b64decode(p1["overlay_png"]).startswith(b"\x89PNG")
    same = rb.visual_compare(before, before, scale=0.5)
    assert same["same"] and same["pages"][0]["summary"].endswith("looks the same.")
