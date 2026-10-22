"""Builders stage 2b part 2: new screens, sections, upgrade guard, packages."""

from __future__ import annotations

import pytest

from app import view_engine as ve
from app import view_engine_portable as vp
from tests.test_view_engine_studio import FIELDS, FORM


@pytest.mark.parametrize("major", [17, 18, 19, 20])
@pytest.mark.parametrize("vt,template", [("form", "blank"), ("form", "two_columns"), ("form", "tabs"), ("list", "basic"),
                                         ("kanban", "card"), ("search", "basic"), ("calendar", "basic")])
def test_new_screen_templates_build_valid_arch_per_version(major: int, vt: str, template: str) -> None:
    arch = vp.build_screen_arch(vt, template, FIELDS, major, "My screen")
    root = ve.parse_arch(arch)
    ve.normalize(arch, FIELDS)
    if vt == "list":
        assert root.tag == ("list" if major >= 18 else "tree")
    if vt == "kanban":
        assert ("t-name=\"card\"" in arch) == (major >= 18)
    if vt == "form":
        assert ("<chatter" in arch) == (major >= 18)
        assert root.find(".//h1/field").get("name") == "name"


def test_calendar_needs_a_date_and_bad_template_is_refused() -> None:
    no_date = {k: v for k, v in FIELDS.items() if v["type"] not in {"date", "datetime"}}
    assert not next(t for t in vp.screen_templates(no_date) if t["view_type"] == "calendar")["available"]
    with pytest.raises(ve.EngineError):
        vp.build_screen_arch("calendar", "basic", no_date, 18, "Cal")
    with pytest.raises(ve.EngineError):
        vp.build_screen_arch("form", "nope", FIELDS, 18, "X")


def test_section_extract_strips_rules_and_reinserts_safely() -> None:
    norm = ve.normalize(FORM.replace("<field name='email'/>", "<field name='email' invisible='state == \"done\"' groups='base.group_system'/>"), FIELDS)
    sec = vp.extract_section(norm.el_by_id["group:left"], FIELDS)
    assert "invisible" not in sec["xml"] and "groups" not in sec["xml"]
    assert [f["name"] for f in sec["fields"]][:2] == ["name", "email"]
    # Into a screen that lacks those fields: fit check and insert with skips
    small_fields = {k: FIELDS[k] for k in ("name", "email", "state", "phone", "fax", "notes", "stage_id")}
    assert vp.section_fit(sec, small_fields)["fits"]
    target = "<form><sheet><group name='g'><field name='state'/></group></sheet></form>"
    res = ve.compile_ops(target, small_fields, [{"op": "insert_section", "xml": sec["xml"], "target": "group:g", "position": "after"}])
    assert res.expected_arch.count("<field name=\"name\"") == 1
    assert "ingenium_layer_sec_" in res.arch
    # Already on the screen -> refused; skip list avoids it
    with pytest.raises(ve.EngineError):
        ve.compile_ops(FORM, FIELDS, [{"op": "insert_section", "xml": sec["xml"], "target": "group:right", "position": "after"}])


def test_section_leaves_out_fields_already_on_the_screen_and_says_so() -> None:
    target = "<form><sheet><group name='g'><field name='email'/></group></sheet></form>"
    xml = ("<group name='s'><field name='name'/><field name='email'/><field name='nope'/>"
           "<group name='inner'><field name='email'/></group><field name='phone'/></group>")
    res = ve.compile_ops(target, FIELDS, [{"op": "insert_section", "xml": xml, "target": "group:g", "position": "after"}])
    assert res.expected_arch.count('<field name="email"') == 1
    assert '<field name="name"' in res.expected_arch and '<field name="phone"' in res.expected_arch
    assert "ingenium_layer_sec_inner" not in res.arch  # emptied group dropped
    note = next(w for w in res.warnings if w.startswith("Left out of the section"))
    assert "already on this screen" in note and "not on this record type" in note
    with pytest.raises(ve.EngineError, match="Everything in that section"):
        ve.compile_ops(target, FIELDS, [{"op": "insert_section", "xml": "<group><field name='email'/></group>", "target": "group:g", "position": "after"}])


def test_section_refuses_foreign_tags_and_unknown_fields() -> None:
    root = ve.parse_arch("<form><sheet><group name='g'/></sheet></form>")
    with pytest.raises(ve.EngineError):
        vp.validate_section_xml("<group><script>x</script></group>", FIELDS, root, 1)
    with pytest.raises(ve.EngineError):
        vp.validate_section_xml("<group><field name='nope'/></group>", FIELDS, root, 1)
    el = vp.validate_section_xml("<group name='a' onclick='x'><field name='email' widget='email' invisible='1'/></group>", FIELDS, root, 1)
    assert "onclick" not in el.attrib and "invisible" not in el.find("field").attrib


def test_set_attr_force_keeps_identical_label() -> None:
    res = ve.compile_ops("<form><field name='email' string='Mail'/></form>", FIELDS,
                         [{"op": "set_attr", "node": "field:email", "attr": "string", "value": "Mail", "force": True}])
    assert 'name="string">Mail<' in res.arch


def _layer(ops: list[dict]) -> tuple[str, str]:
    res = ve.compile_ops(FORM, FIELDS, ops)
    return res.arch, res.expected_arch


def test_guard_report_ok_overridden_missing() -> None:
    arch, combined = _layer([
        {"op": "set_attr", "node": "field:email", "attr": "string", "value": "E-mail"},
        {"op": "move", "node": "field:fax", "target": "group:right", "position": "inside"},
        {"op": "insert_field", "field": "amount", "target": "field:state", "position": "after"},
    ])
    rep = vp.guard_report(arch, combined)
    assert [s["status"] for s in rep] == ["ok", "ok", "ok"]
    # Another view later sets the label again / moves fax back / an upgrade removed state
    overridden = combined.replace('string="E-mail"', 'string="Mail address"')
    assert vp.guard_report(arch, overridden)[0]["status"] == "overridden"
    root = ve.parse_arch(combined)
    fax = root.find(".//field[@name='fax']")
    right = root.find(".//group[@name='right']")
    right.remove(fax)
    root.find(".//group[@name='left']").append(fax)
    import xml.etree.ElementTree as ET

    assert vp.guard_report(arch, ET.tostring(root, encoding="unicode"))[1]["status"] == "overridden"
    no_amount = combined.replace('<field name="amount" />', "").replace('<field name="amount"/>', "")
    assert vp.guard_report(arch, no_amount)[2]["status"] == "missing"


def test_guard_ignores_steps_replaced_by_later_own_steps() -> None:
    a1 = ve.compile_ops(FORM, FIELDS, [{"op": "set_attr", "node": "field:email", "attr": "string", "value": "One"}]).arch
    a2 = ve.compile_ops(FORM, FIELDS, [{"op": "set_attr", "node": "field:email", "attr": "string", "value": "Two"}]).arch
    merged = ve.merge_layers(a1, a2)
    combined = ve.apply_inherit_local(FORM, merged)
    assert [s["status"] for s in vp.guard_report(merged, combined)] == ["ok", "ok"]


def test_package_checksum_adapter_and_refusals() -> None:
    arch = ve.compile_ops("<list><field name='name'/><field name='email'/></list>", FIELDS,
                          [{"op": "move", "node": "field:email", "target": "field:name", "position": "before"}]).arch
    pkg = {"format": vp.PACKAGE_FORMAT, "model": "res.partner", "view_type": "list", "odoo_major": 18, "layer_arch": arch,
           "base_view_xmlid": "base.view_partner_tree", "custom_fields": []}
    pkg["checksum"] = vp.package_checksum(pkg)
    assert vp.check_package(pkg)
    tampered = {**pkg, "layer_arch": arch.replace("before", "after")}
    with pytest.raises(ve.EngineError):
        vp.check_package(tampered)
    to17 = vp.adapt_layer(arch, 18, 17)
    ve.apply_inherit_local("<tree><field name='name'/><field name='email'/></tree>", to17)
    with pytest.raises(ve.EngineError):
        vp.adapt_layer("<data><xpath expr=\"//sheet\" position=\"after\"><chatter/></xpath></data>", 18, 17)
    assert vp.referenced_fields(arch) >= {"email", "name"}


def test_packages_carry_buttons_and_counts_by_meaning_not_by_id() -> None:
    arch = ("<data><xpath expr=\"//div[@name='button_box']\" position=\"inside\">"
            "<button type=\"action\" name=\"533\" class=\"oe_stat_button\"><field name=\"x_tasks_count\" widget=\"statinfo\"/></button>"
            "</xpath></data>")
    assert vp.action_refs(arch) == {533}
    out = vp.rewrite_action_ids(arch, {533: 77})
    assert 'name="77"' in out and 'name="533"' not in out
    code = vp.count_compute("x_tasks_count", "project.task", "partner_id")
    assert vp.count_spec("x_tasks_count", code) == {"relation": "project.task", "link_field": "partner_id"}
    assert vp.count_spec("x_tasks_count", code + "\nimport os") is None  # anything else is code we won't carry
    assert vp.count_spec("x_other", code) is None
    with pytest.raises(ve.EngineError):
        vp.count_compute("x_a'] = 1#", "project.task", "partner_id")
    assert vp.link_action_spec({"name": "Tasks", "res_model": "project.task", "domain": "[('partner_id', '=', active_id)]"}) == {
        "name": "Tasks", "res_model": "project.task", "link_field": "partner_id"}
    assert vp.link_action_spec({"name": "X", "res_model": "a.b", "domain": "[('x', 'in', [1])]"}) is None


def test_package_check_refuses_undescribed_buttons_and_code() -> None:
    arch = "<data><xpath expr=\"//sheet\" position=\"inside\"><button type=\"action\" name=\"9\"/></xpath></data>"
    base = {"format": vp.PACKAGE_FORMAT, "model": "res.partner", "view_type": "form", "layer_arch": arch, "odoo_major": 18}
    bad = dict(base, actions=[])
    bad["checksum"] = vp.package_checksum(bad)
    with pytest.raises(ve.EngineError, match="doesn't describe"):
        vp.check_package(bad)
    good = dict(base, actions=[{"id": 9, "xmlid": "sale.action_orders", "model": "ir.actions.act_window"}])
    good["checksum"] = vp.package_checksum(good)
    assert vp.check_package(good)
    code = dict(good, custom_fields=[{"name": "x_n", "ttype": "integer", "compute": "import os"}])
    code["checksum"] = vp.package_checksum(code)
    with pytest.raises(ve.EngineError, match="calculation code"):
        vp.check_package(code)
