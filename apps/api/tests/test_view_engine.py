"""Shared view engine (Builders stage 1): normalize, compile, local inheritance."""

from __future__ import annotations

import pytest

from app import view_engine as ve
from app import view_engine_report as vr

FORM = """<form string="Contact">
  <header><button name="action_x" string="Do it" type="object"/></header>
  <sheet>
    <div class="oe_title"><h1><field name="name"/></h1></div>
    <group>
      <group name="contact">
        <field name="phone"/>
        <field name="mobile"/>
        <field name="email"/>
      </group>
      <group>
        <field name="vat"/>
        <field name="website"/>
      </group>
    </group>
    <notebook>
      <page name="internal" string="Internal notes">
        <field name="comment"/>
      </page>
      <page string="Lines">
        <field name="child_ids"><list><field name="name"/></list></field>
      </page>
    </notebook>
    <mystery_widget foo="1"/>
  </sheet>
</form>"""

FIELDS = {
    "name": {"string": "Name", "type": "char", "required": True},
    "phone": {"string": "Phone", "type": "char"},
    "mobile": {"string": "Mobile", "type": "char"},
    "email": {"string": "Email", "type": "char"},
    "vat": {"string": "Tax ID", "type": "char"},
    "website": {"string": "Website", "type": "char"},
    "comment": {"string": "Notes", "type": "html"},
    "child_ids": {"string": "Contacts", "type": "one2many", "relation": "res.partner"},
    "ref": {"string": "Reference", "type": "char"},
    "lang": {"string": "Language", "type": "selection", "selection": [["en_US", "English"]]},
}


def _ids(tree):
    out = [tree["id"]]
    for c in tree["children"]:
        out.extend(_ids(c))
    return out


def test_normalize_keeps_unknown_nodes_as_blocks_and_ids_stable():
    a = ve.normalize(FORM, FIELDS)
    b = ve.normalize(FORM, FIELDS)
    assert _ids(a.tree) == _ids(b.tree)
    block = next(n for n in a.by_id.values() if n["tag"] == "mystery_widget")
    assert block["kind"] == "block" and block["label"] == "Odoo element: mystery_widget"
    assert a.by_id["field:phone"]["anchor"] == "//field[@name='phone']"
    assert a.by_id["group:contact"]["anchor"] == "//group[@name='contact']"
    # unnamed group reachable through a unique field directly inside it
    unnamed = a.el_by_id[next(k for k, v in a.by_id.items() if v["tag"] == "group" and v["name"] is None and any(c["name"] == "vat" for c in v["children"]))]
    assert unnamed is not None
    # subview field never addressable; never positional anywhere
    for node in a.by_id.values():
        assert not node["anchor"] or "[1]" not in node["anchor"]


def test_list_tree_root_variants_normalize_the_same_kind():
    t17 = ve.normalize('<tree><field name="name"/></tree>', FIELDS).tree
    t18 = ve.normalize('<list><field name="name"/></list>', FIELDS).tree
    assert t17["kind"] == t18["kind"] == "root"
    assert t17["children"][0]["id"] == t18["children"][0]["id"] == "field:name"


def test_move_insert_hide_compile_to_minimal_safe_xpath():
    ops = [
        {"op": "move", "node": "field:email", "target": "field:phone", "position": "before"},
        {"op": "insert_field", "field": "ref", "target": "field:website", "position": "after"},
        {"op": "hide", "node": "field:vat"},
    ]
    res = ve.compile_ops(FORM, FIELDS, ops)
    assert "replace" not in res.arch
    assert "[1]" not in res.arch and "[2]" not in res.arch
    assert 'position="move"' in res.arch
    exp = ve.normalize(res.expected_arch, FIELDS)
    contact = [c["name"] for c in exp.by_id["group:contact"]["children"]]
    assert contact == ["email", "phone", "mobile"]
    assert exp.by_id["field:ref"]
    assert exp.by_id["field:vat"]["attrs"]["invisible"] == "1"


def test_local_inheritance_matches_compiled_expectation():
    ops = [{"op": "move", "node": "field:website", "target": "group:contact", "position": "inside"}]
    res = ve.compile_ops(FORM, FIELDS, ops)
    again = ve.apply_inherit_local(FORM, res.arch)
    assert ve.signature(ve.normalize(again, FIELDS).tree) == ve.signature(ve.normalize(res.expected_arch, FIELDS).tree)


def test_wrap_group_and_page_and_set_attr():
    res = ve.compile_ops(FORM, FIELDS, [
        {"op": "wrap", "nodes": ["field:phone", "field:mobile"], "kind": "group", "label": "Call"},
        {"op": "set_attr", "node": "field:email", "attr": "string", "value": "Work email"},
        {"op": "wrap", "nodes": ["field:comment"], "kind": "page", "label": "More"},
    ])
    exp = ve.normalize(res.expected_arch, FIELDS)
    grp = next(n for n in exp.by_id.values() if n["tag"] == "group" and n["attrs"].get("string") == "Call")
    assert [c["name"] for c in grp["children"]] == ["phone", "mobile"]
    assert exp.by_id["field:email"]["attrs"]["string"] == "Work email"
    page = next(n for n in exp.by_id.values() if n["tag"] == "page" and n["attrs"].get("string") == "More")
    assert [c["name"] for c in page["children"]] == ["comment"]
    assert "replace" not in res.arch


def test_redundant_ops_collapse():
    res = ve.compile_ops(FORM, FIELDS, [
        {"op": "move", "node": "field:email", "target": "field:phone", "position": "before"},
        {"op": "move", "node": "field:email", "target": "field:mobile", "position": "after"},
        {"op": "insert_field", "field": "ref", "target": "field:website", "position": "after"},
        {"op": "hide", "node": "field:ref"},
    ])
    assert res.arch.count('position="move"') == 1
    assert "ref" not in res.arch
    assert any("neither is saved" in d for d in res.dropped)


@pytest.mark.parametrize(
    "op,msg",
    [
        ({"op": "move", "node": "page:internal", "target": "group:contact", "position": "inside"}, "can't go inside"),
        ({"op": "insert_field", "field": "nope", "target": "field:phone"}, "no field called"),
        ({"op": "insert_field", "field": "phone", "target": "field:email"}, "already on this screen"),
        ({"op": "move", "node": "group:contact", "target": "field:phone", "position": "after"}, "inside itself"),
        ({"op": "set_attr", "node": "field:phone", "attr": "t-att-class", "value": "x"}, "can't be changed"),
        ({"op": "set_attr", "node": "field:phone", "attr": "readonly", "value": "maybe"}, "yes or no"),
        ({"op": "hide", "node": "root"}, "whole screen"),
        ({"op": "move", "node": "gone", "target": "field:phone"}, "no longer on this screen"),
    ],
)
def test_illegal_ops_refused_in_plain_words(op, msg):
    with pytest.raises(ve.EngineError) as exc:
        ve.compile_ops(FORM, FIELDS, [op])
    assert msg in str(exc.value)


def test_duplicate_field_is_locked_not_positional():
    arch = "<form><sheet><group><field name='phone'/></group><group><field name='phone'/></group></sheet></form>"
    norm = ve.normalize(arch, FIELDS)
    second = norm.by_id["field:phone~2"] if "field:phone~2" in norm.by_id else None
    assert second is not None and second["anchor"] is None and second["locked_reason"]
    with pytest.raises(ve.EngineError):
        ve.compile_ops(arch, FIELDS, [{"op": "hide", "node": "field:phone~2"}])


def test_hide_required_field_warns():
    res = ve.compile_ops(FORM, FIELDS, [{"op": "hide", "node": "field:name"}])
    assert res.warnings and "must be filled in" in res.warnings[0]


def test_list_hide_uses_column_invisible():
    res = ve.compile_ops('<list><field name="name"/><field name="phone"/></list>', FIELDS, [{"op": "hide", "node": "field:phone"}])
    assert 'name="column_invisible"' in res.arch


def test_merge_layers_appends_steps():
    a = ve.compile_ops(FORM, FIELDS, [{"op": "hide", "node": "field:vat"}]).arch
    b = ve.compile_ops(FORM, FIELDS, [{"op": "hide", "node": "field:website"}]).arch
    merged = ve.merge_layers(a, b)
    assert ve.count_layer_steps(merged) == 2


def test_signature_diff_reports_plainly():
    exp = ve.signature(ve.normalize(FORM, FIELDS).tree)
    other = FORM.replace('<field name="mobile"/>', "")
    act = ve.signature(ve.normalize(other, FIELDS).tree)
    diffs = ve.diff_signatures(exp, act)
    assert diffs and "Odoo shows" in diffs[0] or "expected" in diffs[0]


def test_records_display_and_stress_picks():
    recs = [
        {"id": 1, "name": "A", "phone": ""},
        {"id": 2, "name": "A much longer name here", "phone": "+234 800"},
    ]
    picks = ve.stress_picks(recs, ["name", "phone"])
    assert picks == {"longest": 2, "emptiest": 1}
    assert ve.display_value([3, "Lagos"], {"type": "many2one"}) == "Lagos"
    assert ve.display_value([1, 2], {"type": "one2many"}) == "2 items"
    assert ve.display_value("en_US", FIELDS["lang"]) == "English"
    assert ve.display_value("<p>Hi <b>there</b></p>", {"type": "html"}) == "Hi there"


INVOICE_DOC = """<t t-name="account.report_invoice_document"><t t-call="web.external_layout">
<t t-set="o" t-value="o.with_context(lang=lang)"/>
<div class="mt-5 clearfix"><div class="page mb-4"><h2><span t-field="o.name"/></h2></div></div></t></t>"""


def test_report_slots_and_layer_compile():
    slots = vr.slots_for(INVOICE_DOC)
    assert [s["id"] for s in slots] == ["top", "bottom"]
    assert vr.record_var(INVOICE_DOC) == "o"
    blocks = vr.validate_blocks([{"type": "text", "text": "Thank you"}, {"type": "field", "field": "name"}], {"name": {"string": "Number"}})
    arch = vr.compile_report_layer(slots[1], blocks, "o")
    assert "hasclass('page')" in arch and 'position="inside"' in arch and "replace" not in arch
    assert 't-field="o.name"' in arch
    with pytest.raises(ve.EngineError):
        vr.validate_blocks([{"type": "field", "field": "secret"}], {"name": {}})
    with pytest.raises(ve.EngineError):
        vr.validate_blocks([{"type": "o2m_table"}], {})


def test_document_template_key():
    main = '<t t-name="account.report_invoice"><t t-call="web.html_container"><t t-foreach="docs" t-as="o"><t t-call="account.report_invoice_document" t-lang="lang"/></t></t></t>'
    assert vr.document_template_key("account.report_invoice", main) == "account.report_invoice_document"


def test_copies_inside_lines_tables_use_top_level_anchor():
    arch = (
        "<form><sheet><group><field name='phone'/></group>"
        "<field name='child_ids'><form><sheet><group><field name='phone'/></group></sheet></form></field>"
        "</sheet></form>"
    )
    norm = ve.normalize(arch, FIELDS)
    assert norm.by_id["field:phone"]["anchor"] == "//field[@name='phone']" + ve.TOP_LEVEL
    sheet = next(n for n in norm.by_id.values() if n["tag"] == "sheet")
    assert sheet["anchor"] == "//sheet" + ve.TOP_LEVEL
    res = ve.compile_ops(arch, FIELDS, [{"op": "set_attr", "node": "field:phone", "attr": "string", "value": "Call"}])
    exp = ve.normalize(res.expected_arch, FIELDS)
    assert exp.by_id["field:phone"]["attrs"]["string"] == "Call"
    # the copy inside the lines table is untouched
    assert res.expected_arch.count('string="Call"') == 1
