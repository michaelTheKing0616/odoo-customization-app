"""Builders stage 2b, view side: library, widgets, screen settings, checks."""

from __future__ import annotations

import pytest

from app import view_engine as ve
from app import view_engine_library as lib
from app.routers.view_engine import _cleanup_layer, _touched_access_fields
from app.routers.view_engine_logic import merge_descriptions

FIELDS = {
    "name": {"type": "char", "string": "Name", "required": True},
    "email": {"type": "char", "string": "Email"},
    "phone": {"type": "char", "string": "Phone"},
    "fax": {"type": "char", "string": "Fax"},
    "notes": {"type": "text", "string": "Notes"},
    "stage_id": {"type": "many2one", "string": "Stage", "relation": "crm.stage"},
    "state": {"type": "selection", "string": "Status", "selection": [["draft", "Draft"], ["done", "Done"]]},
    "priority": {"type": "selection", "string": "Priority", "selection": [["0", "Low"], ["3", "High"]]},
    "tag_ids": {"type": "many2many", "string": "Tags", "relation": "crm.tag"},
    "probability": {"type": "float", "string": "Probability"},
    "amount": {"type": "monetary", "string": "Amount"},
    "currency_id": {"type": "many2one", "string": "Currency", "relation": "res.currency"},
    "date_deadline": {"type": "date", "string": "Deadline"},
    "active": {"type": "boolean", "string": "Active"},
    "message_ids": {"type": "one2many", "string": "Messages", "relation": "mail.message"},
    "message_follower_ids": {"type": "one2many", "string": "Followers", "relation": "mail.followers"},
    "activity_ids": {"type": "one2many", "string": "Activities", "relation": "mail.activity"},
    "image_128": {"type": "binary", "string": "Image"},
    "computed_x": {"type": "char", "string": "Worked out", "store": False, "depends": ["name"]},
    "color": {"type": "integer", "string": "Colour"},
}

FORM = (
    "<form><header/><sheet>"
    "<div class='oe_button_box' name='button_box'/>"
    "<group name='main'><group name='left'><field name='name'/><field name='email'/><field name='phone'/>"
    "<field name='fax'/><field name='notes'/><field name='stage_id'/></group><group name='right'><field name='state'/></group></group>"
    "<notebook><page name='p1' string='Info'><field name='probability'/></page>"
    "<page name='p2' string='More'><group name='more'><field name='date_deadline'/></group></page></notebook>"
    "</sheet></form>"
)
LIST = "<list><field name='name'/><field name='probability'/><field name='computed_x'/></list>"
LIST17 = "<tree><field name='name'/><field name='probability'/></tree>"
KANBAN18 = "<kanban><templates><t t-name='card'><field name='name'/></t></templates></kanban>"
KANBAN17 = "<kanban><templates><t t-name='kanban-box'><div class='oe_kanban_card'><field name='name'/></div></t></templates></kanban>"
SEARCH = "<search><field name='name'/><filter name='mine' string='Mine' domain=\"[('active', '=', True)]\"/></search>"


def test_widget_catalog_is_version_specific_and_typed() -> None:
    w17 = {w["name"] for w in lib.widgets_for("many2many", 17)}
    assert "many2many_tags" in w17
    assert "priority" in {w["name"] for w in lib.widgets_for("selection", 19)}
    assert "progressbar" not in {w["name"] for w in lib.widgets_for("char", 18)}
    assert len(lib.widget_catalog(20)["registered"]) > len(lib.widget_catalog(17)["registered"])
    with pytest.raises(ve.EngineError):
        lib.check_widget("progressbar", "char", 18)
    with pytest.raises(ve.EngineError):
        lib.check_widget("not_a_widget", "char", 18)
    lib.check_widget("many2many_tags", "many2many", 17)


def test_field_types_and_new_field_plans() -> None:
    keys = {t["key"] for t in lib.field_types_for(17)}
    assert {"text", "money", "tags", "priority", "signature", "related", "lines"} <= keys
    plan = lib.plan_new_field({"type": "choice", "label": "Delivery method", "choices": ["Truck", "Bike"]}, FIELDS, 7, 18)
    assert plan["name"] == "x_delivery_method" and plan["values"]["ttype"] == "selection"
    assert [r[2]["name"] for r in plan["values"]["selection_ids"]] == ["Truck", "Bike"]
    money = lib.plan_new_field({"type": "money", "label": "Deposit"}, FIELDS, 7, 17)
    assert money["values"]["currency_field"] == "currency_id"
    pri = lib.plan_new_field({"type": "priority", "label": "Urgency"}, FIELDS, 7, 19)
    assert pri["widget"] == "priority" and len(pri["values"]["selection_ids"]) == 4
    rel = lib.plan_new_field({"type": "related", "label": "Stage fold", "related": "stage_id.fold"}, FIELDS, 7, 20,
                             related_meta={"type": "boolean"})
    assert rel["values"]["related"] == "stage_id.fold" and rel["values"]["store"] is False
    with pytest.raises(ve.EngineError):
        lib.plan_new_field({"type": "link", "label": "Owner", "relation": "nope.model"}, FIELDS, 7, 17, relation_models=set())
    with pytest.raises(ve.EngineError):
        lib.plan_new_field({"type": "money", "label": "X"}, {"name": {"type": "char"}}, 7, 17)


def test_stock_first_similar_fields() -> None:
    sim = lib.similar_fields("E-mail", "char", FIELDS)
    assert sim and sim[0]["name"] == "email"
    assert lib.similar_fields("Warehouse capacity", "integer", FIELDS) == []


def test_library_elements_compile() -> None:
    ops = [
        {"op": "insert_element", "element": "separator", "target": "field:fax", "position": "after", "props": {"label": "Contact"}},
        {"op": "insert_element", "element": "ribbon", "target": "root/sheet", "position": "inside", "props": {"label": "Lost", "color": "red"}},
        {"op": "insert_element", "element": "statusbar", "target": "root/header", "position": "inside", "props": {"field": "state"}},
        {"op": "insert_element", "element": "chatter", "target": "root/sheet", "position": "after", "props": {}},
        {"op": "insert_element", "element": "smart_button", "target": "div:button_box", "position": "inside",
         "props": {"label": "Leads", "action_id": 42, "icon": "fa-star", "count_field": "color"}},
        {"op": "insert_element", "element": "group", "target": "group:main", "position": "after", "props": {"label": "Extra", "columns": 2}},
    ]
    tree = ve.normalize(FORM, FIELDS).tree
    by_tag = {c["tag"]: c["id"] for c in tree["children"]}
    for op in ops:
        op["target"] = {"root/sheet": by_tag["sheet"], "root/header": by_tag["header"]}.get(op["target"], op["target"])
    res = ve.compile_ops(FORM, FIELDS, ops, major=18, actions={42})
    exp = res.expected_arch
    assert 'widget="statusbar"' in exp and "<chatter" in exp and 'name="web_ribbon"' in exp
    assert 'class="oe_stat_button"' in exp and 'widget="statinfo"' in exp
    assert "ingenium_layer_group_extra" in exp and "position=\"replace\"" not in res.arch
    res17 = ve.compile_ops(FORM, FIELDS, [ops[3]], major=17)
    assert "oe_chatter" in res17.expected_arch and "message_follower_ids" in res17.expected_arch
    with pytest.raises(ve.EngineError, match="button box"):
        ve.compile_ops(FORM, FIELDS, [{**ops[4], "target": "group:main"}], major=18, actions={42})
    with pytest.raises(ve.EngineError, match="list"):
        ve.compile_ops(FORM, FIELDS, [{**ops[4], "props": {**ops[4]["props"], "action_id": 7}}], major=18, actions={42})
    with pytest.raises(ve.EngineError, match="actions"):
        ve.compile_ops(FORM, FIELDS, [{"op": "insert_element", "element": "action_button", "target": by_tag["header"], "position": "inside",
                                       "props": {"label": "Go", "method": "unlink"}}], major=18, methods={"action_confirm"})


def test_insert_field_with_widget_and_list_settings() -> None:
    res = ve.compile_ops(FORM, FIELDS, [{"op": "insert_field", "field": "tag_ids", "target": "field:fax", "position": "after",
                                         "widget": "many2many_tags", "placeholder": "Pick tags"}], major=17)
    assert 'widget="many2many_tags"' in res.expected_arch and 'placeholder="Pick tags"' in res.expected_arch
    with pytest.raises(ve.EngineError):
        ve.compile_ops(FORM, FIELDS, [{"op": "insert_field", "field": "email", "target": "field:fax", "widget": "progressbar"}], major=17)
    ops = [
        {"op": "set_attr", "node": "root", "attr": "editable", "value": "bottom"},
        {"op": "set_attr", "node": "root", "attr": "default_group_by", "value": "stage_id"},
        {"op": "set_attr", "node": "field:probability", "attr": "sum", "value": "Total"},
        {"op": "set_attr", "node": "field:name", "attr": "width", "value": "220px"},
        {"op": "set_attr", "node": "field:computed_x", "attr": "optional", "value": "hide"},
        {"op": "set_decoration", "node": "root", "style": "danger", "condition": {"match": "all", "rules": [{"field": "probability", "op": "lt", "value": 10}]}},
    ]
    res = ve.compile_ops(LIST, FIELDS, ops, major=18)
    exp = res.expected_arch
    for want in ('editable="bottom"', 'default_group_by="stage_id"', 'sum="Total"', 'width="220px"', 'optional="hide"', 'decoration-danger="probability &lt; 10"'):
        assert want in exp
    assert "//list" in res.arch
    assert "//tree" in ve.compile_ops(LIST17, FIELDS, [ops[0]], major=17).arch
    with pytest.raises(ve.EngineError):
        ve.compile_ops(LIST, FIELDS, [{"op": "set_attr", "node": "field:name", "attr": "sum", "value": "Total"}], major=18)
    with pytest.raises(ve.EngineError):
        ve.compile_ops(LIST, FIELDS, [{"op": "set_attr", "node": "root", "attr": "default_group_by", "value": "computed_x"}], major=18)
    with pytest.raises(ve.EngineError):
        ve.compile_ops(LIST, FIELDS, [{"op": "set_attr", "node": "root", "attr": "limit", "value": "9999"}], major=18)


def test_kanban_card_items_per_version() -> None:
    cond = {"match": "all", "rules": [{"field": "priority", "op": "is", "value": "3"}]}
    ops = [{"op": "kanban_add", "kind": "tags", "props": {"field": "tag_ids"}},
           {"op": "kanban_add", "kind": "progress", "props": {"field": "probability"}},
           {"op": "kanban_add", "kind": "colour", "props": {"style": "danger"}, "condition": cond}]
    r18 = ve.compile_ops(KANBAN18, FIELDS, ops, major=18)
    assert "//t[@t-name='card']" in r18.arch and 'widget="many2many_tags"' in r18.expected_arch
    assert "record.priority.raw_value === &quot;3&quot;" in r18.expected_arch
    assert "o_ingenium_card_flag" in r18.expect
    r17 = ve.compile_ops(KANBAN17, FIELDS, ops[:1], major=17)
    assert "//t[@t-name='kanban-box']/div" in r17.arch
    with pytest.raises(ve.EngineError, match="linked"):
        ve.compile_ops(KANBAN18, FIELDS, [{"op": "kanban_add", "kind": "colour", "props": {}, "condition":
                                            {"match": "all", "rules": [{"field": "stage_id", "op": "is", "value": 1}]}}],
                       major=18, record_names={"stage_id": {1: "New"}})
    cover = ve.compile_ops(KANBAN18, FIELDS, [{"op": "kanban_add", "kind": "cover", "props": {"field": "image_128"}}], major=18)
    assert "<aside" in cover.expected_arch


def test_search_filters_and_groupbys() -> None:
    cond = {"match": "any", "rules": [{"field": "state", "op": "is", "value": "done"}, {"field": "probability", "op": "gt", "value": 50}]}
    res = ve.compile_ops(SEARCH, FIELDS, [
        {"op": "search_add_filter", "label": "Done or likely", "condition": cond},
        {"op": "search_add_groupby", "label": "Stage", "field": "stage_id"},
        {"op": "search_add_field", "field": "email"},
    ], major=19)
    exp = res.expected_arch
    assert "'|', ('state', '=', 'done'), ('probability', '&gt;', 50)" in exp
    assert "{'group_by': 'stage_id'}" in exp and '<field name="email"' in exp
    assert lib.compile_domain({"match": "all", "rules": [{"field": "active", "op": "is_true"}]}) == "[('active', '=', True)]"
    with pytest.raises(ve.EngineError):
        ve.compile_ops(SEARCH, FIELDS, [{"op": "search_add_groupby", "label": "X", "field": "computed_x"}], major=19)
    tree = ve.normalize(SEARCH, FIELDS).tree
    assert tree["kind"] == "root" and any(c["tag"] == "filter" for c in tree["children"])


def test_usage_suggestions_counts_only() -> None:
    tree = ve.normalize(FORM, FIELDS).tree
    counts = {"name": 1000, "email": 900, "phone": 950, "fax": 10, "notes": 100, "stage_id": 1000, "state": 1000, "probability": 500, "date_deadline": 50}
    sugg = lib.usage_suggestions(tree, FIELDS, counts, 1000)
    rare = [s for s in sugg if s["kind"] == "rarely_filled"]
    assert any(s["node"] == "field:fax" and s["rate"] == 1 and s["ops"] == [{"op": "hide", "node": "field:fax"}] for s in rare)
    assert "Rarely filled: Fax (1% of 1,000)" in [s["text"] for s in rare]
    assert any(s["kind"] == "most_used_first" for s in sugg)
    few = lib.usage_suggestions(tree, FIELDS, counts, 5)
    assert all(s["kind"] in {"note", "required_hidden"} for s in few)
    hidden_req = "<form><sheet><group name='g'><field name='name' invisible='1'/><field name='email'/></group></sheet></form>"
    s2 = lib.usage_suggestions(ve.normalize(hidden_req, FIELDS).tree, FIELDS, {}, 0)
    assert s2[0]["kind"] == "required_hidden" and s2[0]["ops"][0]["value"] == "False"


def test_layout_checks_health_and_tidy() -> None:
    many = "".join(f"<field name='f{i}'/>" for i in range(14))
    fields = {**FIELDS, **{f"f{i}": {"type": "char", "string": f"F{i}"} for i in range(14)}}
    arch = (f"<form><sheet><notebook><page name='big' string='Big'>{many}</page></notebook>"
            "<group name='cols'><group name='l'><field name='name'/><field name='email'/><field name='phone'/><field name='fax'/>"
            "<field name='notes'/></group><group name='r'><field name='state'/></group></group>"
            "<group name='g2'><field name='probability' style='color: #ffdd00'/></group></sheet></form>")
    tree = ve.normalize(arch, fields).tree
    issues = lib.layout_checks(tree, fields, "form")
    kinds = {i["kind"] for i in issues}
    assert {"crowded", "unbalanced", "contrast"} <= kinds
    crowded = next(i for i in issues if i["kind"] == "crowded")
    assert crowded["ops"][0]["op"] == "wrap" and crowded["ops"][0]["kind"] == "page"
    ve.compile_ops(arch, fields, crowded["ops"], major=18)  # the fix compiles
    unbal = next(i for i in issues if i["kind"] == "unbalanced")
    ve.compile_ops(arch, fields, unbal["ops"], major=18)
    contrast = next(i for i in issues if i["kind"] == "contrast")
    assert lib._contrast(contrast["ops"][0]["value"].split(":")[1].strip()) >= 4.5
    ve.compile_ops(arch, fields, contrast["ops"], major=18)
    health = lib.health_score(issues, [], 20, 2)
    assert 0 <= health["score"] < 100 and {p["key"] for p in health["parts"]} == {"crowding", "hidden_required", "empty_fields", "accessibility"}
    plan = lib.tidy_plan(tree, fields, {"name": 10, "email": 90, "phone": 95, "fax": 1, "notes": 5}, 100,
                         {"email": "Contact", "phone": "Contact"})
    assert plan["ops"] and plan["descriptions"]
    ve.compile_ops(arch, fields, plan["ops"], major=18)
    assert lib.validate_sections({"sections": [{"title": "Contact", "fields": ["email", "ghost"]}]}, tree) == {"email": "Contact"}


def test_reading_order_and_performance_hints() -> None:
    fields = {**FIELDS, "date_deadline": {"type": "date", "string": "Deadline", "required": True}}
    tree = ve.normalize(FORM, fields).tree
    ro = [i for i in lib.layout_checks(tree, fields, "form") if i["kind"] == "reading_order"]
    assert ro and ro[0]["node"] == "field:date_deadline" and ro[0]["ops"]
    ve.compile_ops(FORM, fields, ro[0]["ops"], major=18)
    lt = ve.normalize(LIST, FIELDS).tree
    hints = lib.performance_hints(lt, FIELDS, "list")
    assert any(h["kind"] == "computed_column" and h["ops"][0]["value"] == "hide" for h in hints)
    big = lib.performance_hints(ve.normalize("<form><sheet><field name='message_ids'/></sheet></form>", FIELDS).tree, FIELDS, "form",
                                {"message_ids": {"max": 1240}})
    assert big[0]["kind"] == "big_lines" and "1,240" in big[0]["text"]


def test_screen_level_group_limits() -> None:
    views = [
        {"id": 1, "inherit_id": None, "arch": "<form><field name='name'/></form>", "groups": []},
        {"id": 2, "inherit_id": 1, "arch": "<xpath expr='//field[@name=\"name\"]' position='after'><field name='amount'/></xpath>", "groups": [9]},
        {"id": 3, "inherit_id": 1, "arch": "<data><field name='name' position='after'><field name='email'/></field></data>", "groups": []},
        {"id": 4, "inherit_id": 2, "arch": "<xpath expr='//field[@name=\"amount\"]' position='after'><field name='fax'/></xpath>", "groups": []},
    ]
    out = lib.restricted_parts(views, 1, {"base.group_user"}, {9: "sales_team.group_sale_manager"}, {"sales_team.group_sale_manager": "Sales Manager"})
    assert out["hidden_fields"] == {"amount": ["Sales Manager"], "fax": ["Sales Manager"]}
    assert out["base_ok"]
    mgr = lib.restricted_parts(views, 1, {"sales_team.group_sale_manager"}, {9: "sales_team.group_sale_manager"}, {})
    assert mgr["hidden_fields"] == {}


def test_merge_duplicate_descriptions() -> None:
    assert merge_descriptions(["Hide Phone", "Hide Phone", "Rename Email to Mail"]) == ["Hide Phone (2 copies)", "Rename Email to Mail"]


def test_cleanup_of_stale_see_only_copies() -> None:
    prev = ("<data><xpath expr=\"//field[@name='phone']\" position=\"attributes\"><attribute name=\"groups\">a.b</attribute></xpath>"
            "<xpath expr=\"//field[@name='phone']\" position=\"after\"><field name=\"phone\" groups=\"c.d\" readonly=\"1\"/></xpath>"
            "<xpath expr=\"//field[@name='email']\" position=\"attributes\"><attribute name=\"invisible\">1</attribute></xpath></data>")
    assert _touched_access_fields([{"op": "set_access", "node": "field:phone~2"}]) == {"phone"}
    cleaned = _cleanup_layer(prev, {"phone"})
    assert cleaned is not None and "phone" not in cleaned and "email" in cleaned
    assert _cleanup_layer(prev, {"name"}) is None
