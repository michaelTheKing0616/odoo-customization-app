"""BOT-PROCESS-FITGAP: parsers, fit-gap honesty, dry-run plan, one-vision budget.

The rice-mill workbook below is a SYNTHETIC EXAMPLE fixture (Zyn Mills style layout:
all content as drawn shapes, connectors mostly unlinked). It contains no client data.
"""

from __future__ import annotations

import base64
import gzip
import io
import re
import resource
import time
import urllib.parse
import zipfile
import zlib
from itertools import pairwise
from xml.sax.saxutils import escape

import pytest

from app.bots.process import fitgap as fg
from app.bots.process import ingest as ig
from app.bots.process import plan as pl
from app.bots.process import report as rp
from app.catalogue import loader

pytestmark = pytest.mark.no_app_db

W, H, GAP = 2_000_000, 400_000, 300_000
XDR = (
    'xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
)

ZYN_STEPS = [
    "Paddy Arrival (Truck)",
    "Weighbridge - Gross / Tare",
    "Moisture Test",
    "Paddy Quality Test (Impurities)",
    "Moisture Deduction / Net Weight Pricing",
    "Paddy Cleaning (Pre-cleaner)",
    "Destoner - Stones Removed",
    "Silo Tempering (Dwell Time)",
    "Husker - Husk Removed",
    "Paddy Separator",
    "Whitening - Bran Removed",
    "Polishing",
    "Grading",
    "Colour Sorter",
    "Metal Detector",
    "Weighing Scale Check",
    "Packing 5kg / 10kg / 25kg / 50kg Bags",
    "Lot Coding & Labelling",
    "Finished Goods Warehouse",
    "Distribution to Depots",
]
REJECT = "Rejected - Return to Supplier"
YIELD = "Milling Yield / Loss Report"
GAPS = {"weighbridge", "moisture_pricing", "tempering_gate", "yield_dashboard"}
QUALITY = {
    "Moisture Test",
    "Paddy Quality Test (Impurities)",
    "Metal Detector",
    "Weighing Scale Check",
}


def _sp(i: int, text: str, x: int, y: int) -> str:
    return (
        f"<xdr:twoCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row>"
        f"<xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:to><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>"
        f"<xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to><xdr:sp><xdr:nvSpPr>"
        f'<xdr:cNvPr id="{i}" name="Flowchart: Process {i}"/><xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{W}" cy="{H}"/></a:xfrm></xdr:spPr>'
        f"<xdr:txBody><a:p><a:r><a:t>{escape(text)}</a:t></a:r></a:p></xdr:txBody></xdr:sp>"
        f"<xdr:clientData/></xdr:twoCellAnchor>"
    )


def _cx(
    i: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    st: int | None = None,
    en: int | None = None,
    reverse: bool = False,
) -> str:
    """Straight connector x0,y0 -> x1,y1; reverse=True draws it backwards, arrow at start."""
    if reverse:
        x0, y0, x1, y1 = x1, y1, x0, y0
    fh = ' flipH="1"' if x1 < x0 else ""
    fv = ' flipV="1"' if y1 < y0 else ""
    link = (f'<a:stCxn id="{st}" idx="2"/>' if st else "") + (
        f'<a:endCxn id="{en}" idx="0"/>' if en else ""
    )
    arrow = '<a:headEnd type="triangle"/>' if reverse else '<a:tailEnd type="triangle"/>'
    return (
        f"<xdr:twoCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row>"
        f"<xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:to><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>"
        "<xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff>"
        '</xdr:to><xdr:cxnSp macro=""><xdr:nvCxnSpPr>'
        f'<xdr:cNvPr id="{i}" name="Straight Arrow Connector {i}"/>'
        f"<xdr:cNvCxnSpPr>{link}</xdr:cNvCxnSpPr>"
        f'</xdr:nvCxnSpPr><xdr:spPr><a:xfrm{fh}{fv}><a:off x="{min(x0, x1)}" y="{min(y0, y1)}"/>'
        f'<a:ext cx="{abs(x1 - x0)}" cy="{abs(y1 - y0)}"/>'
        f'</a:xfrm><a:ln w="12700">{arrow}</a:ln></xdr:spPr>'
        f"</xdr:cxnSp><xdr:clientData/></xdr:twoCellAnchor>"
    )


def _xlsx(drawing: str, cells: dict[str, str] | None = None) -> bytes:
    rows = "".join(
        f'<row r="{re.sub(r"[A-Z]", "", r)}"><c r="{r}" t="inlineStr">'
        f"<is><t>{escape(v)}</t></is></c></row>"
        for r, v in (cells or {}).items()
    )
    files = {
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "xl/workbook.xml": '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
        f'spreadsheetml/2006/main"><sheetData>{rows}</sheetData></worksheet>',
        "xl/drawings/drawing1.xml": f'<?xml version="1.0"?><xdr:wsDr {XDR}>{drawing}</xdr:wsDr>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


def zyn_mills_example_xlsx() -> bytes:
    """Synthetic example: title + 20 column steps + reject branch + unconnected yield report."""
    parts = [_sp(900, "Zyn Mills - Manufacturing Process Flow Diagram (example)", 0, 0)]
    x, top = 3_000_000, 800_000
    ys = [top + k * (H + GAP) for k in range(len(ZYN_STEPS))]
    for k, text in enumerate(ZYN_STEPS):
        parts.append(_sp(k + 1, text, x, ys[k]))
    for k in range(len(ZYN_STEPS) - 1):
        cid = 100 + k
        cxm = x + W // 2
        a, b = ys[k] + H + 20_000, ys[k + 1] - 20_000
        if k in (0, 5, 12):  # a few properly linked
            parts.append(_cx(cid, cxm, a, cxm, b, st=k + 1, en=k + 2))
        elif k == 8:  # drawn backwards with the arrow at its start point
            parts.append(_cx(cid, cxm, a, cxm, b, reverse=True))
        else:
            parts.append(_cx(cid, cxm, a, cxm, b))
    q = ys[3] + H // 2
    parts.append(_sp(50, REJECT, x + W + 1_500_000, ys[3]))
    parts.append(_cx(150, x + W + 20_000, q, x + W + 1_480_000, q))
    parts.append(_sp(51, YIELD, x + W + 1_500_000, ys[-1]))
    return _xlsx("".join(parts))


ENTERPRISE = fg.OdooEnv.from_modules(
    18,
    {"base", "web_enterprise", "stock", "mrp", "product", "purchase", "quality_control"},
    {
        "repair",
        "maintenance",
        "mrp_subcontracting",
        "stock_dropshipping",
        "mrp_plm",
        "purchase_stock",
    },
)
COMMUNITY = fg.OdooEnv.from_modules(17, {"base", "stock", "mrp", "product", "purchase"}, {"repair"})


class FakeVision:
    def __init__(self, out=None):
        self.calls, self.out = 0, out

    def __call__(self, png, mime, hint):
        self.calls += 1
        if self.out is not None:
            return self.out
        ids = [s["id"] for s in hint["steps"]]
        return {
            "steps": hint["steps"],
            "edges": [{"src": a, "dst": b, "confidence": 0.99} for a, b in pairwise(ids)],
        }


def _fake_render(data, graph):
    return b"\x89PNG\r\n\x1a\nfake"


def _texts(g):
    return [s.text for s in g.order()]


# ---------------------------------------------------------------- parsers


def test_zyn_mills_unlinked_connectors_recover_true_order():
    g = ig.ingest(zyn_mills_example_xlsx(), "Zyn Mills Process Flow.xlsx")
    assert g.fmt == "xlsx" and g.confident and g.render_request is None
    assert any("title/legend" in n for n in g.notes)
    order = _texts(g)
    main = [t for t in order if t in ZYN_STEPS]
    assert main == ZYN_STEPS
    hows = {e.how for e in g.edges}
    assert {"linked", "nearest"} <= hows
    by = {s.id: s.text for s in g.steps}
    pairs = {(by[e.src], by[e.dst]) for e in g.edges}
    assert ("Paddy Quality Test (Impurities)", REJECT) in pairs
    assert ("Silo Tempering (Dwell Time)", "Husker - Husk Removed") in pairs  # reversed drawing
    assert all(s.locator.startswith("xl/drawings/drawing1.xml shape id=") for s in g.steps)


def test_linked_connectors_full_confidence():
    d = _sp(1, "Receive", 0, 0) + _sp(2, "Mill", 0, 1_000_000) + _cx(9, 5, 5, 5, 5, st=1, en=2)
    g = ig.ingest(_xlsx(d), "a.xlsx")
    assert [(e.how, e.confidence) for e in g.edges] == [("linked", 1.0)] and g.confident


def test_shape_only_xlsx_is_low_confidence_and_spends_one_vision_read():
    d = _sp(1, "Receive", 0, 0) + _sp(2, "Mill", 2_500_000, 0) + _sp(3, "Pack", 5_000_000, 0)
    data = _xlsx(d)
    g = ig.ingest(data, "b.xlsx")
    assert not g.confident and g.render_request["marker"] == "RENDER_REQUEST"
    assert (
        "soffice" in g.render_request["pipeline"][0]
        and "pdftoppm" in g.render_request["pipeline"][1]
    )
    assert _texts(g) == ["Receive", "Mill", "Pack"]
    v = FakeVision()
    g = ig.resolve(g, data, v, _fake_render)
    g = ig.resolve(g, data, v, _fake_render)
    assert v.calls == 1 and g.vision_calls == 1 and g.confident
    assert {e.how for e in g.edges} == {"vision"} and max(
        e.confidence for e in g.edges
    ) <= ig.VISION_EDGE_CAP


def test_cells_only_xlsx():
    g = ig.ingest(_xlsx("", {"A1": "Receive paddy", "A2": "Clean", "A3": "12.5"}), "c.xlsx")
    assert _texts(g) == ["Receive paddy", "Clean"] and g.steps[0].locator.endswith("cell A1")


def test_bpmn():
    x = (
        '<?xml version="1.0"?>'
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p">'
        '<startEvent id="s"/><task id="t1" name="Receive paddy"/>'
        '<exclusiveGateway id="g" name="OK?"/>'
        '<userTask id="t2" name="Clean"/><endEvent id="e"/>'
        '<sequenceFlow id="f1" sourceRef="s" targetRef="t1"/>'
        '<sequenceFlow id="f2" sourceRef="t1" targetRef="g"/>'
        '<sequenceFlow id="f3" sourceRef="g" targetRef="t2"/>'
        '<sequenceFlow id="f4" sourceRef="t2" targetRef="e"/>'
        "</process></definitions>"
    )
    g = ig.ingest(x.encode(), "p.bpmn")
    assert g.confident and _texts(g) == ["startEvent", "Receive paddy", "OK?", "Clean", "endEvent"]
    fit = fg.classify(g, ENTERPRISE)
    assert [f.verdict for f in fit.steps][0] is None and fit.steps[2].verdict is None


def _drawio_model(unlinked: bool) -> str:
    edge = (
        '<mxCell id="e" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
        '<mxPoint x="60" y="42" as="sourcePoint"/>'
        '<mxPoint x="60" y="98" as="targetPoint"/></mxGeometry></mxCell>'
        if unlinked
        else '<mxCell id="e" edge="1" source="a" target="b" parent="1">'
        '<mxGeometry as="geometry"/></mxCell>'
    )
    return (
        '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="a" value="Receive &lt;b&gt;paddy&lt;/b&gt;" vertex="1" parent="1">'
        '<mxGeometry x="0" y="0" width="120" height="40" as="geometry"/></mxCell>'
        '<mxCell id="b" value="Clean" vertex="1" parent="1">'
        '<mxGeometry x="0" y="100" width="120" height="40" as="geometry"/>'
        f"</mxCell>{edge}</root></mxGraphModel>"
    )


@pytest.mark.parametrize("unlinked", [False, True])
def test_drawio_plain(unlinked):
    g = ig.ingest(
        f"<mxfile><diagram>{_drawio_model(unlinked)}</diagram></mxfile>".encode(), "d.drawio"
    )
    assert _texts(g) == ["Receive paddy", "Clean"] and g.edges[0].how == (
        "nearest" if unlinked else "linked"
    )


def test_drawio_compressed():
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = c.compress(urllib.parse.quote(_drawio_model(False)).encode()) + c.flush()
    g = ig.ingest(
        f"<mxfile><diagram>{base64.b64encode(raw).decode()}</diagram></mxfile>".encode(), "d.drawio"
    )
    assert _texts(g) == ["Receive paddy", "Clean"] and g.confident


def test_minimal_vsdx():
    page = (
        '<?xml version="1.0"?><PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main"><Shapes>'
        '<Shape ID="1"><Cell N="PinX" V="2"/><Cell N="PinY" V="8"/>'
        '<Cell N="Width" V="1"/><Cell N="Height" V="0.5"/>'
        "<Text>Receive paddy</Text></Shape>"
        '<Shape ID="2"><Cell N="PinX" V="2"/><Cell N="PinY" V="6"/>'
        '<Cell N="Width" V="1"/><Cell N="Height" V="0.5"/>'
        "<Text>Clean</Text></Shape>"
        '<Shape ID="3"><Cell N="BeginX" V="2"/><Cell N="BeginY" V="7.7"/>'
        '<Cell N="EndX" V="2"/><Cell N="EndY" V="6.3"/></Shape>'
        '</Shapes><Connects><Connect FromSheet="3" FromCell="BeginX" ToSheet="2"/>'
        '<Connect FromSheet="3" FromCell="EndX" ToSheet="1"/></Connects></PageContents>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("visio/document.xml", "<VisioDocument/>")
        z.writestr("visio/pages/page1.xml", page)
    g = ig.ingest(buf.getvalue(), "m.vsdx")
    assert g.fmt == "vsdx" and _texts(g) == [
        "Clean",
        "Receive paddy",
    ]  # connect order wins over position
    assert g.edges[0].how == "linked"


def test_docx_and_text():
    body = "".join(
        f"<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>{t}</w:t></w:r></w:p>"
        for t in ("Receive", "Clean", "Pack")
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>',
        )
    g = ig.ingest(buf.getvalue(), "p.docx")
    assert g.fmt == "docx" and _texts(g) == ["Receive", "Clean", "Pack"] and g.confident
    t = ig.ingest(b"Receive paddy -> Clean -> Pack\nClean -> Reject", "flow.txt")
    assert t.confident and len(t.edges) == 3 and _texts(t)[0] == "Receive paddy"


def _pdf(lines):
    stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({x}) Tj 0 -16 Td" for x in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()


def test_pdf_text():
    g = ig.ingest(_pdf(["1. Receive paddy", "2. Clean", "3. Pack"]), "p.pdf")
    assert g.fmt == "pdf" and _texts(g) == ["Receive paddy", "Clean", "Pack"] and g.confident


def test_image_needs_exactly_one_read_and_rejects_bad_output():
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    g = ig.ingest(png, "flow.png")
    assert g.render_request["pipeline"] == ["image as-is"]
    bad = FakeVision({"steps": "nope", "edges": []})
    g = ig.resolve(g, png, bad, _fake_render)
    g = ig.resolve(g, png, bad, _fake_render)
    assert bad.calls == 1 and not g.confident and any("rejected" in n for n in g.notes)
    good = FakeVision(
        {
            "steps": [{"id": "x", "text": "Receive"}, {"id": "y", "text": "Mill"}],
            "edges": [{"src": "x", "dst": "y", "confidence": 2}, {"src": "x", "dst": "zz"}],
        }
    )
    g2 = ig.resolve(ig.ingest(png, "flow.png"), png, good, _fake_render)
    assert (
        good.calls == 1
        and _texts(g2) == ["Receive", "Mill"]
        and g2.edges[0].confidence == ig.VISION_EDGE_CAP
    )


def test_confident_parse_never_calls_model(monkeypatch):
    monkeypatch.setattr(ig, "gateway_vision", lambda *a: pytest.fail("model called"))
    v = FakeVision()
    data = zyn_mills_example_xlsx()
    g = ig.resolve(ig.ingest(data, "z.xlsx"), data, v, lambda *a: pytest.fail("rendered"))
    assert v.calls == 0 and g.vision_calls == 0


@pytest.mark.parametrize(
    "bad", [b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', b"PK\x03\x04junk"]
)
def test_unsafe_or_broken_input_fails_closed(bad):
    with pytest.raises(ig.IngestError):
        ig.ingest(bad, "x.bpmn")


# ---------------------------------------------------------------- fit-gap


def _fit(env):
    return fg.classify(ig.ingest(zyn_mills_example_xlsx(), "Zyn Mills Process Flow.xlsx"), env)


def test_zyn_mills_end_to_end_enterprise():
    fit = _fit(ENTERPRISE)
    v = {f.text: f for f in fit.steps}
    assert fit.verdict == "custom" and set(fit.gaps) == GAPS
    assert {f.gap for f in fit.steps if f.verdict == "custom"} == GAPS
    assert v[REJECT].verdict == "stock"
    assert not any(f.needs_human for f in fit.steps)
    expect = {
        "Paddy Arrival (Truck)": {"receipt"},
        "Moisture Test": {"quality_point"},
        "Destoner - Stones Removed": {"manufacturing", "by_product"},
        "Husker - Husk Removed": {"manufacturing", "by_product"},
        "Whitening - Bran Removed": {"manufacturing", "by_product"},
        "Metal Detector": {"quality_passfail"},
        "Weighing Scale Check": {"quality_measure", "quality_point"},
        "Packing 5kg / 10kg / 25kg / 50kg Bags": {"manufacturing", "variant"},
        "Lot Coding & Labelling": {"lot"},
        "Finished Goods Warehouse": {"warehouse"},
        "Distribution to Depots": {"resupply", "warehouse"},
    }
    for text, cs in expect.items():
        assert {c.concept for c in v[text].concepts} == cs, text
        assert v[text].verdict == (
            "stock" if text == "Paddy Arrival (Truck)" else "stock-with-config"
        ), text
    assert fit.questions == [
        "Is milling run in separate batches or as one continuous line?",
        "Are scales and detectors connected to a computer, or are readings typed in by hand?",
    ]
    plan = pl.build_plan(fit)
    assert plan.dry_run and not plan.executed
    models = {a.model for a in plan.actions if a.bot_can_do}
    assert {
        "mrp.workcenter",
        "mrp.bom",
        "mrp.routing.workcenter",
        "mrp.bom.byproduct",
        "product.attribute",
        "stock.lot",
        "stock.warehouse",
        "stock.route",
    } <= models
    assert all(a.tier == 1 for a in plan.actions if a.bot_can_do)
    human = [a for a in plan.actions if not a.bot_can_do]
    assert human and all(a.tier is None and a.reasons for a in human)
    assert any(a.model == "quality.point" for a in human)
    from app.module_spec_codec import draft_dict_to_module_spec

    spec = draft_dict_to_module_spec(plan.module_spec)
    assert {m.model for m in spec.models} == {
        "ingenium.weighbridge.ticket",
        "ingenium.moisture.adjustment",
        "ingenium.tempering.batch",
        "ingenium.milling.yield",
    }
    out = rp.to_json(
        g := ig.ingest(zyn_mills_example_xlsx(), "Zyn Mills Process Flow.xlsx"), fit, plan
    )
    assert out["flow_order"][0] == g.order()[0].id and out["fitgap"]["verdict"] == "custom"
    text = out["summary"]
    assert "Odoo 18 Enterprise" in text and "nothing changed yet" in text
    assert not re.search(
        r"\b(ir|res|mrp|stock)\.[a-z_]+|\bm:|\bR\dW?\b|quality_control|L\d\b", text
    )


def test_community_is_honest_about_enterprise_only_quality():
    fit = _fit(COMMUNITY)
    v = {f.text: f for f in fit.steps}
    for t in QUALITY:
        assert v[t].verdict == "custom", t
        assert any("Enterprise only" in r for r in v[t].reasons)
    assert {g for g in fit.gaps if g.startswith("unavailable:")} == {
        "unavailable:quality_point",
        "unavailable:quality_measure",
        "unavailable:quality_passfail",
    }
    assert v["Polishing"].verdict == "stock-with-config"
    plan = pl.build_plan(fit)
    assert not any(a.model == "quality.point" for a in plan.actions)


def test_unknown_step_falls_back_to_human_or_custom():
    g = ig.ingest(b"1. Bless the harvest\n2. Clean paddy", "x.txt")
    fit = fg.classify(g, ENTERPRISE)
    f = fit.steps[0]
    assert f.verdict == "custom" and f.needs_human and fit.verdict == "custom"
    assert fit.gaps == [f"unknown:{f.step_id}"]


def test_no_env_asks_version_and_never_claims_ready():
    fit = fg.classify(ig.ingest(b"1. Receive paddy\n2. Clean (batch)", "x.txt"), None)
    assert fit.questions == [
        "Which Odoo version and edition (Community or Enterprise) will you run?"
    ]
    assert all(c.status == "unverified" for f in fit.steps for c in f.concepts)
    assert fit.verdict == "stock-with-config"


def test_read_env_is_one_read_and_fails_closed():
    seen = []

    def call(model, method, args, kw):
        seen.append((model, method))
        return [
            {"name": "base", "state": "installed", "latest_version": "20.0.1.3"},
            {"name": "mrp", "state": "installed"},
            {"name": "repair", "state": "uninstalled"},
            {"name": "web_enterprise", "state": "uninstalled"},
        ]

    env = fg.read_env(call)
    assert seen == [("ir.module.module", "search_read")]
    assert (env.major, env.edition, "repair" in env.installable) == (20, "enterprise", True)
    with pytest.raises(ValueError):
        fg.read_env(lambda *a: [{"name": "base", "state": "installed", "latest_version": "16.0.1"}])
    with pytest.raises(ValueError):
        fg.read_env(lambda *a: False)


def test_fitgap_table_drift_against_catalogue():
    t = fg.load_table()
    cat = loader.load()
    cat_modules = {
        p for task in cat.tasks for p in task.prerequisites.replace(";", " ").split()
    } | {task.area for task in cat.tasks}
    for c in t.concepts:
        if c.edition == "community":
            assert c.module in cat_modules, c.module
        else:  # Enterprise modules are absent from the Community-derived catalogue: keep it honest
            assert c.module not in cat_modules, c.module
        for s in c.setup:
            if s["task"] is None:
                continue
            task = cat.index[s["task"]]
            assert task.object == s["model"] and task.verb == "create", s
            assert set(range(c.min_major, 21)) <= set(task.versions), s
    for g in t.gaps:
        assert g.spec["model"].startswith("ingenium.") and all(
            d in cat_modules for d in g.spec["depends"]
        )
    assert {g.id for g in t.gaps} == GAPS


# ---------------------------------------------------------------- review round 1


def test_drawio_decompression_bomb_is_bounded():
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    comp = c.compress(b"A" * (300 * 1024 * 1024)) + c.flush()
    doc = b"<mxfile><diagram>" + base64.b64encode(comp) + b"</diagram></mxfile>"
    r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with pytest.raises(ig.IngestError):
        ig.ingest(doc, "x.drawio")
    grew = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - r0
    assert grew < 100 * 2**20  # bytes on macOS (KB on Linux): bounded either way


@pytest.mark.parametrize("wbits", [-15, 15, 31])
def test_inflate_bounded_every_container(wbits):
    raw = b"x" * 5000
    if wbits == 31:
        comp = gzip.compress(raw)
    else:
        c = zlib.compressobj(6, zlib.DEFLATED, wbits)
        comp = c.compress(raw) + c.flush()
    assert ig.inflate(comp, wbits, cap=5000) == raw
    with pytest.raises(ig.IngestError):
        ig.inflate(comp, wbits, cap=4999)


def test_zip_member_read_is_capped(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w/>" + " " * 5000)
    monkeypatch.setattr(ig, "MAX_MEMBER", 1000)
    with pytest.raises(ig.IngestError):
        ig.ingest(buf.getvalue(), "a.docx")


def test_doctype_anywhere_is_refused():
    doc = (
        b'<?xml version="1.0"?><!--' + b"x" * 5000 + b"-->"
        b'<!DOCTYPE r SYSTEM "file:///etc/passwd"><mxfile/>'
    )
    with pytest.raises(ig.IngestError):
        ig.ingest(doc, "x.drawio")


ENV17 = fg.OdooEnv.from_modules(17, {"base", "stock", "purchase", "mrp", "account"}, set())
ADVERSARIAL = [
    "Receive payment from customer",
    "Check payment",
    "Upgrade software",
    "Produce invoice",
    "Label the email",
    "Send invoice to customer",
    "Process payroll",
    "Grade student essays",
    "Sort emails by date",
    "Pack my suitcase",
    "Dry run the software release",
    "Return the rental car",
    "Test the website login",
    "Clean the office kitchen",
    "Blend ideas in the team meeting",
    "Ship the software update",
    "Store passwords securely",
    "Check the bank statement",
    "Approve vacation request",
    "Weigh the options",
    "Recepción de arroz",
    "Contrôle qualité du riz",
    "米の受け入れ",
    "Annahme der Ware",
]


@pytest.mark.parametrize("phrase", ADVERSARIAL)
def test_adversarial_phrases_never_get_a_stock_verdict(phrase):
    fit = fg.classify(ig.ingest(f"1. {phrase}".encode(), "a.txt"), ENV17)
    (f,) = fit.steps
    assert f.verdict == "custom" and f.needs_human and not f.concepts, phrase


@pytest.mark.parametrize(
    "txt",
    [
        "1. Receive payment from customer\n2. Check payment\n3. Upgrade software",
        "1. Produce invoice\n2. Label the email",
    ],
)
def test_probe_loose_keywords(txt):
    steps = fg.classify(ig.ingest(txt.encode(), "a.txt"), ENV17).steps
    assert all(s.verdict == "custom" for s in steps)


def test_weak_keyword_with_material_context_is_accepted():
    fit = fg.classify(ig.ingest(b"1. Receive rice at gate", "a.txt"), ENV17)
    assert fit.steps[0].verdict == "stock" and fit.steps[0].concepts[0].concept == "receipt"


def test_repeated_labels_stay_distinct_steps():
    g = ig.ingest(b"1. Weigh truck\n2. Unload\n3. Weigh truck", "a.txt")
    assert len(g.steps) == 3 and len({s.id for s in g.steps}) == 3 and len(g.edges) == 2
    t = ig.ingest(b"A -> B\nB -> C", "a.txt")
    assert len(t.steps) == 3  # arrow chains still name shared nodes


def test_no_database_says_enterprise_unless_confirmed():
    fit = fg.classify(ig.ingest(b"1. Metal detector", "a.txt"), None)
    f = fit.steps[0]
    assert f.verdict == "custom"
    assert any("needs Enterprise unless confirmed" in r for r in f.reasons)


def test_module_install_maps_to_catalogue_task_and_tier():
    env = fg.OdooEnv.from_modules(17, {"base", "stock"}, {"repair"})
    plan = pl.build_plan(fg.classify(ig.ingest(b"1. Repair the husker machine", "a.txt"), env))
    a = next(x for x in plan.actions if x.model == "ir.module.module")
    assert a.task_id == "mod:repair:install"
    assert loader.load().index["mod:repair:install"].risk_class == "R7"
    assert a.bot_can_do and a.tier is not None and a.tier >= 2


# ---------------------------------------------------------------- review round 2

ENV_R2 = fg.OdooEnv.from_modules(
    17, {"base", "stock", "purchase", "mrp", "account", "product", "maintenance", "repair"}, set()
)
OFFICE = [
    "Ship the report to the warehouse manager",
    "Inter-warehouse football match",
    "Mill street office visit",
    "Mill machines photo for the newsletter",
    "Lot code of conduct review",
    "Return to supplier the unused brochures",
    "Receive invoice from supplier",
    "Pack the report",
    "Check email with scale",
    "Transfer funds",
    "Approve order",
    "Lot of work",
    "Receive payment for rice",
    "Check the return policy",
    "Buy a test kit for the office",
    "Ship the newsletter",
    "Sort the mail",
    "Grade the exam",
    "Dry run of the presentation",
    "Store the contract in the cabinet",
    "Deliver the speech",
    "Produce the monthly report",
    "Trace the bug",
    "Receive visitors at reception",
    "Label the files",
]
MILL_PREFIX = "1. Paddy intake at gate\n2. Moisture test\n3. Purchase order to farmer\n"


def _custom_human(txt):
    fit = fg.classify(ig.ingest(txt.encode(), "a.txt"), ENV_R2)
    return {s.text: (s.verdict, s.needs_human) for s in fit.steps}


@pytest.mark.parametrize("phrase", OFFICE)
def test_office_phrase_alone_needs_human(phrase):
    assert _custom_human(f"1. {phrase}")[phrase] == ("custom", True)


def test_office_phrases_inside_a_real_mill_document_still_need_human():
    txt = MILL_PREFIX + "".join(f"{i + 4}. {p}\n" for i, p in enumerate(OFFICE))
    v = _custom_human(txt)
    assert all(v[p] == ("custom", True) for p in OFFICE)
    assert v["Paddy intake at gate"][0] == "stock"


# Reviewed lists: weak-keyword verbs x office nouns. None may ever get a stock verdict.
WEAK_VERBS = [
    "Receive",
    "Pack",
    "Check",
    "Transfer",
    "Store",
    "Deliver",
    "Produce",
    "Trace",
    "Label",
    "Sort",
    "Grade",
    "Ship",
    "Buy",
    "Return",
    "Test",
    "Clean",
    "Dry",
    "Blend",
    "Weigh",
    "Inspect",
    "Dispatch",
    "Distribute",
    "Measure",
    "Sample",
    "Separate",
    "Grind",
    "Procure",
]
OFFICE_NOUNS = [
    "the report",
    "the file",
    "the folder",
    "the contract",
    "the presentation",
    "the visitors",
    "the exam",
    "the newsletter",
    "the policy",
    "the idea",
    "the document",
    "the slides",
    "the agenda",
    "the form",
    "the memo",
    "the spreadsheet",
    "the budget",
    "the proposal",
    "the survey results",
    "the feedback",
    "a lot of tasks",
    "the test results",
]


def test_property_office_cross_product_never_stock():
    phrases = [f"{v} {n}" for v in WEAK_VERBS for n in OFFICE_NOUNS]
    txt = MILL_PREFIX + "\n".join(f"{i + 4}. {p}" for i, p in enumerate(phrases[:400]))
    v = _custom_human(txt)
    bad = [p for p in phrases[:400] if v[p] != ("custom", True)]
    assert not bad
    rest = phrases[400:]
    v2 = _custom_human("\n".join(f"{i + 1}. {p}" for i, p in enumerate(rest)))
    assert not [p for p in rest if v2[p] != ("custom", True)]


def test_weak_never_confirms_weak_and_vocab_confirms():
    v = _custom_human("1. Pack bags\n2. Trace lot\n3. Clean paddy\n4. Store rice")
    assert v["Pack bags"] == ("custom", True)  # bag is itself a keyword match
    assert v["Trace lot"] == ("custom", True)  # lot is itself a keyword match
    assert v["Clean paddy"][0] == "stock-with-config" and v["Store rice"][0] == "stock-with-config"


def _drawio_grid(n, linked=False):
    cells = "".join(
        f'<mxCell id="v{i}" value="step {i}" vertex="1"><mxGeometry x="{(i % 40) * 150}" '
        f'y="{(i // 40) * 100}" width="100" height="50" as="geometry"/></mxCell>'
        for i in range(n)
    )
    edges = "".join(
        f'<mxCell id="e{i}" edge="1"><mxGeometry as="geometry"><mxPoint x="{(i % 40) * 150 + 100}" '
        f'y="{(i // 40) * 100 + 25}" as="sourcePoint"/><mxPoint x="{(i % 40) * 150 + 150}" '
        f'y="{(i // 40) * 100 + 25}" as="targetPoint"/></mxGeometry></mxCell>'
        for i in range(n)
    )
    body = f"<root>{cells}{edges}</root>"
    return f"<mxfile><diagram><mxGraphModel>{body}</mxGraphModel></diagram></mxfile>"


def test_shape_count_refused_before_geometry_and_grid_is_fast():
    t0 = time.perf_counter()
    with pytest.raises(ig.IngestError, match="too large"):
        ig.ingest(_drawio_grid(3000).encode(), "big.drawio")
    assert time.perf_counter() - t0 < 2
    t0 = time.perf_counter()
    with pytest.raises(ig.IngestError, match="too many steps"):  # 1000 + 1000 under the count cap
        ig.ingest(_drawio_grid(1000).encode(), "ok.drawio")
    assert time.perf_counter() - t0 < 2
    ig_steps = ig.MAX_STEPS
    try:
        ig.MAX_STEPS = 1000
        t0 = time.perf_counter()
        g = ig.ingest(_drawio_grid(1000).encode(), "ok.drawio")
        assert time.perf_counter() - t0 < 3 and len(g.edges) >= 900
    finally:
        ig.MAX_STEPS = ig_steps


def test_zip_member_count_cap():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(ig.MAX_MEMBERS + 1):
            z.writestr(f"x/{i}", "")
    with pytest.raises(ig.IngestError, match="too many members"):
        ig.ingest(buf.getvalue(), "a.docx")


def test_summary_and_json_label_keyword_verdicts_as_suggestions():
    env = fg.OdooEnv.from_modules(17, {"base", "stock", "purchase", "mrp", "product"}, set())
    g = ig.ingest(zyn_mills_example_xlsx(), "Zyn Mills Process Flow.xlsx")
    fit = fg.classify(g, env)
    out = rp.to_json(g, fit, pl.build_plan(fit))
    text = out["summary"]
    assert text.splitlines()[0] == rp.HEADER
    assert "look like they work as is (suggested)" in text
    assert "after setup (suggested)" in text
    ok = [s for s in fit.steps if s.verdict in ("stock", "stock-with-config")]
    assert ok and all(f"{s.text}: " in text for s in ok)
    assert text.count(rp.SUGGESTED) == len(ok)
    allowed = {"strong pattern", "strong + context", "weak + context", "needs human"}
    steps = out["fitgap"]["steps"]
    assert all(s["match_confidence"] in allowed for s in steps)
    for s in steps:
        if s["verdict"] in ("stock", "stock-with-config"):
            assert s["match_confidence"] != "needs human"
        if s["needs_human"]:
            assert s["match_confidence"] == "needs human"
