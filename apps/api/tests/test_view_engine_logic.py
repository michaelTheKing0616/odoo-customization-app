"""Builders stage 2a: conditions, access, unlock, AI validation, history compare."""

from __future__ import annotations

import json
import random

import pytest

from app import view_engine as ve
from app import view_engine_access as va
from app import view_engine_ai as vai
from app import view_engine_logic as vl
from app import view_engine_report as vr

FIELDS = {
    "name": {"string": "Opportunity", "type": "char", "required": True},
    "stage_id": {"string": "Stage", "type": "many2one", "relation": "crm.stage"},
    "priority": {"string": "Priority", "type": "selection", "selection": [["0", "Low"], ["1", "Medium"], ["2", "High"]]},
    "active": {"string": "Active", "type": "boolean"},
    "expected_revenue": {"string": "Expected Revenue", "type": "monetary"},
    "tag_ids": {"string": "Tags", "type": "many2many", "relation": "crm.tag"},
    "phone": {"string": "Phone", "type": "char"},
    "email_from": {"string": "Email", "type": "char"},
    "date_deadline": {"string": "Expected Closing", "type": "date"},
}
NAMES = {"stage_id": {4: "Won", 1: "New"}}

FORM = """<form><sheet>
<div class="oe_title"><h1><field name="name"/></h1></div>
<group name="main"><field name="phone"/><field name="email_from" widget="email"/><field name="stage_id"/></group>
<group><field name="priority"/></group>
<notebook><page name="extra" string="Extra"><field name="name" readonly="1"/><label for="tag_ids"/><field name="tag_ids"/></page></notebook>
</sheet></form>"""


# ---- conditions -------------------------------------------------------------

def test_show_when_stage_is_won_compiles_to_inline_expression():
    cond = vl.validate_condition({"rules": [{"field": "stage_id", "op": "is", "value": 4}]}, FIELDS, record_names=NAMES)
    expr = vl.compile_condition(cond)
    assert expr == "stage_id == 4"
    assert vl.condition_sentence(cond, FIELDS, NAMES) == "Stage is Won"
    assert vl.rule_expression("invisible", "show", expr, None, True) == "not (stage_id == 4)"
    assert vl.rule_sentence("invisible", "show", "Stage is Won") == "Shown only when Stage is Won"


def test_condition_keeps_odoo_rule_and_never_uses_attrs():
    expr = vl.rule_expression("invisible", "show", "stage_id == 4", "not active", True)
    assert expr == "(not active) or (not (stage_id == 4))"
    assert "attrs" not in expr
    assert vl.rule_expression("required", "show", "priority == '2'", None, True) == "priority == '2'"


@pytest.mark.parametrize("cond,msg", [
    ({"rules": [{"field": "nope", "op": "is", "value": 1}]}, "no field called"),
    ({"rules": [{"field": "stage_id", "op": "is", "value": 99}]}, "wasn't found"),
    ({"rules": [{"field": "priority", "op": "is", "value": "9"}]}, "isn't a choice"),
    ({"rules": [{"field": "active", "op": "contains", "value": "x"}]}, "can't be compared"),
    ({"rules": [{"field": "expected_revenue", "op": "gt", "value": "lots"}]}, "needs a number"),
    ({"rules": []}, "at least one part"),
])
def test_condition_validator_refuses_bad_input(cond, msg):
    with pytest.raises(ve.EngineError, match=msg):
        vl.validate_condition(cond, FIELDS, record_names=NAMES)


def test_condition_any_and_types():
    cond = vl.validate_condition({"match": "any", "rules": [
        {"field": "priority", "op": "in", "value": ["1", "2"]},
        {"field": "active", "op": "is_false"},
        {"field": "expected_revenue", "op": "ge", "value": "1000"},
        {"field": "email_from", "op": "contains", "value": "@acme"},
    ]}, FIELDS)
    assert vl.compile_condition(cond) == "priority in ['1', '2'] or not active or expected_revenue >= 1000 or ('@acme' in (email_from or ''))"
    assert vl.condition_sentence(cond, FIELDS) == (
        "Priority is Medium or High or Active is not ticked or Expected Revenue is at least 1000 or Email contains @acme")


def test_explain_existing_expressions():
    assert vl.why_sentence("invisible", "stage_id == 4", FIELDS, NAMES) == "Hidden when Stage is Won."
    assert vl.why_sentence("invisible", "not active or priority in ['2']", FIELDS) == "Hidden when Active is not ticked or Priority is one of High."
    assert vl.why_sentence("readonly", "1", FIELDS) == "Always read-only."
    assert vl.why_sentence("invisible", "context.get('x') and foo(bar)", FIELDS) is None
    assert vl.expression_m2o_ids("stage_id in [1, 4]", FIELDS) == {"stage_id": {1, 4}}


# ---- unlock duplicates / unnamed --------------------------------------------

def test_unlock_duplicate_and_unnamed_elements():
    norm = ve.normalize(FORM, FIELDS)
    first = norm.by_id["field:name"]
    second = norm.by_id["field:name~2"]
    assert first["anchor"] == "//div[hasclass('oe_title')]//field[@name='name']"
    assert second["anchor"] == "//page[@name='extra']//field[@name='name']"
    assert first.get("anchor_note") == ve.SETTINGS_NOTE
    title = next(n for n in norm.by_id.values() if n["tag"] == "div")
    assert title["anchor"] == "//div[hasclass('oe_title')]"
    label = next(n for n in norm.by_id.values() if n["tag"] == "label")
    assert label["anchor"] == "//label[@for='tag_ids']"
    unnamed_group = next(n for n in norm.by_id.values() if n["tag"] == "group" and not n["name"])
    assert unnamed_group["anchor"] == "//field[@name='priority']/.."
    for n in norm.by_id.values():
        if n["anchor"]:
            assert len(ve._find(ve.parse_arch(FORM), n["anchor"].replace(ve.TOP_LEVEL, ""))) >= 1


def test_unlock_by_distinguishing_setting():
    arch = "<form><sheet><group name='g'><field name='phone'/><field name='phone' widget='phone' readonly='1'/></group></sheet></form>"
    norm = ve.normalize(arch, FIELDS)
    assert norm.by_id["field:phone"]["anchor"] == "//field[@name='phone'][not(@widget)]"
    assert norm.by_id["field:phone~2"]["anchor"] == "//field[@name='phone'][@widget='phone']"


def test_moving_an_unlocked_duplicate_compiles_and_applies():
    res = ve.compile_ops(FORM, FIELDS, [{"op": "move", "node": "field:name~2", "target": "field:phone", "position": "before"}])
    assert "[1]" not in res.arch and "replace" not in res.arch
    tree = ve.normalize(res.expected_arch, FIELDS).tree
    main = next(c for c in tree["children"][0]["children"] if c.get("name") == "main")
    assert [c["name"] for c in main["children"]][:2] == ["name", "phone"]


# ---- set_condition / set_access ops ----------------------------------------

def test_set_condition_op_publishable_arch():
    res = ve.compile_ops(FORM, FIELDS, [{"op": "set_condition", "node": "field:phone", "attr": "invisible", "sense": "show",
                                          "condition": {"rules": [{"field": "stage_id", "op": "is", "value": 4}]}}], record_names=NAMES)
    assert '<attribute name="invisible">not (stage_id == 4)</attribute>' in res.arch
    phone = ve.normalize(res.expected_arch, FIELDS).by_id["field:phone"]
    assert phone["attrs"]["invisible"] == "not (stage_id == 4)"


def test_set_condition_refuses_unknown_record():
    with pytest.raises(ve.EngineError):
        ve.compile_ops(FORM, FIELDS, [{"op": "set_condition", "node": "field:phone", "attr": "invisible",
                                        "condition": {"rules": [{"field": "stage_id", "op": "is", "value": 77}]}}], record_names=NAMES)


def test_set_access_edit_and_see_only():
    known = {"sales_team.group_sale_manager", "sales_team.group_sale_salesman", "base.group_system"}
    res = ve.compile_ops(FORM, FIELDS, [{"op": "set_access", "node": "field:phone",
                                          "edit": ["sales_team.group_sale_manager", "base.group_system"],
                                          "see": ["sales_team.group_sale_salesman"]}], known_groups=known)
    norm = ve.normalize(res.expected_arch, FIELDS)
    a, b = norm.by_id["field:phone"], norm.by_id["field:phone~2"]
    assert a["attrs"]["groups"] == "base.group_system,sales_team.group_sale_manager"
    assert b["attrs"] == {"groups": "sales_team.group_sale_salesman", "readonly": "1"}
    assert a["anchor"] and b["anchor"], "both copies stay editable"
    with pytest.raises(ve.EngineError, match="no longer exists"):
        ve.compile_ops(FORM, FIELDS, [{"op": "set_access", "node": "field:phone", "edit": ["x.y"]}], known_groups=known)


def test_groups_rule_and_prune():
    assert vl.groups_allow("a.b,c.d", {"c.d"})
    assert not vl.groups_allow("a.b", {"c.d"})
    assert vl.groups_allow("!a.b", {"c.d"})
    root = ve.parse_arch("<form><field name='a' groups='x.y'/><field name='b' groups='z.z'/></form>")
    vl.prune_for(root, {"x.y"})
    assert [(c.get("name"), c.get("groups")) for c in root] == [("a", None)]


def test_visibility_for_role_with_reasons():
    tree = ve.normalize("<form><group name='g' groups='sales_team.group_sale_manager'><field name='phone'/></group><field name='email_from'/></form>", FIELDS).tree
    vis = vl.visibility_for(tree, {"base.group_user"}, {"email_from": "base.group_system"}, {"sales_team.group_sale_manager": "Sales / Administrator", "base.group_system": "Settings"})
    assert vis["group:g"] == {"visible": False, "reason": "Only Sales / Administrator can see it."}
    assert vis["field:phone"]["reason"] == "The section it sits in is hidden."
    assert vis["field:email_from"]["reason"] == "The field itself is limited to Settings."


# ---- impact and blocks -------------------------------------------------------

def _cat():
    cat = va.GroupCatalog()
    for gid, x, name, implied in [
        (1, "base.group_user", "Internal User", set()), (2, "base.group_system", "Settings", {1, 3}),
        (3, "sales_team.group_sale_salesman", "Sales / User", {1}), (4, "sales_team.group_sale_manager", "Sales / Administrator", {1, 3}),
    ]:
        cat.by_id[gid] = {"id": gid, "name": name}
        cat.xmlid_of[gid] = x
        cat.id_of[x] = gid
        cat.closure[gid] = {gid, *implied}
    return cat


USERS = [
    {"id": 2, "name": "Admin", "member_of": {"base.group_user", "base.group_system", "sales_team.group_sale_salesman", "sales_team.group_sale_manager"}},
    {"id": 7, "name": "Ada", "member_of": {"base.group_user", "sales_team.group_sale_salesman"}},
    {"id": 8, "name": "Ben", "member_of": {"base.group_user"}},
]


def test_field_impact_blocks_admin_lockout_and_hidden_required():
    r = va.field_access_impact(label="Opportunity", users=USERS, before_groups=None, edit=["sales_team.group_sale_salesman"], see=[],
                               field_required=True, has_default=False, can_create_member=lambda m: True, connection_uid=2, cat=_cat())
    assert r["impact"][0] == "1 person loses sight of Opportunity: Ben."
    assert any("can create records but wouldn't see it" in b for b in r["blocks"])
    r2 = va.field_access_impact(label="Phone", users=USERS, before_groups=None, edit=["sales_team.group_sale_manager"], see=[],
                                field_required=False, has_default=False, can_create_member=lambda m: True, connection_uid=99, cat=_cat())
    assert not any("Administrators" in b for b in r2["blocks"])
    r3 = va.field_access_impact(label="Phone", users=USERS, before_groups=None, edit=["sales_team.group_sale_salesman"], see=[],
                                field_required=False, has_default=False, can_create_member=lambda m: True, connection_uid=99, cat=_cat())
    assert r3["blocks"] == []
    r4 = va.field_access_impact(label="Phone", users=USERS, before_groups=None, edit=["base.group_user"], see=[],
                                field_required=False, has_default=False, can_create_member=lambda m: True, connection_uid=2, cat=_cat())
    assert r4["impact"] == ["Nobody's view of Phone changes."]
    lock = va.field_access_impact(label="Phone", users=[{"id": 2, "name": "Admin", "member_of": {"base.group_system"}}], before_groups=None,
                                  edit=["sales_team.group_sale_manager"], see=[], field_required=False, has_default=False,
                                  can_create_member=lambda m: True, connection_uid=2, cat=_cat())
    assert any("Administrators (Admin)" in b for b in lock["blocks"])


def test_see_only_overlap_is_blocked():
    r = va.field_access_impact(label="Phone", users=USERS, before_groups=None, edit=["sales_team.group_sale_manager"],
                               see=["sales_team.group_sale_salesman"], field_required=False, has_default=False,
                               can_create_member=lambda m: True, connection_uid=99, cat=_cat())
    assert any("show them the field twice" in b for b in r["blocks"])


def test_model_access_plan_grant_revoke_and_lockout():
    cat = _cat()
    rows = [
        {"id": 10, "group": "sales_team.group_sale_salesman", "group_id": 3, "group_name": "Sales / User", "read": True, "write": True, "create": True, "unlink": False},
        {"id": 11, "group": "sales_team.group_sale_manager", "group_id": 4, "group_name": "Sales / Administrator", "read": True, "write": True, "create": True, "unlink": True},
    ]
    actions, blocks = va.model_access_plan(rows, [{"group": "sales_team.group_sale_salesman", "unlink": True}], cat)
    assert blocks == [] and actions == [{"type": "create", "group": "sales_team.group_sale_salesman", "group_id": 3,
                                         "perms": {"read": True, "write": True, "create": True, "unlink": True}}]
    actions, blocks = va.model_access_plan(rows, [{"group": "sales_team.group_sale_manager", "write": False}], cat)
    assert blocks and "through 'Sales / User'" in blocks[0]
    actions, blocks = va.model_access_plan(rows, [{"group": "sales_team.group_sale_salesman", "create": False}], cat)
    assert blocks == [] and actions[0] == {"type": "deactivate", "id": 10, "group": "sales_team.group_sale_salesman"}
    after = va.apply_plan_to_rows(rows, actions)
    impact, blocks = va.model_access_impact("Leads", USERS, rows, after, connection_uid=2)
    assert any("can no longer create Leads: Ada" in i for i in impact)
    assert blocks == []  # admin still creates through Sales / Administrator


def test_explain_domain():
    assert va.explain_domain("[('user_id', '=', user.id)]") == "user is the person themself"
    assert va.explain_domain("[(1, '=', 1)]") == "All records"
    assert va.explain_domain("[('x', '=', some_func())]") is None


# ---- AI proposals: validator rejects anything not in the input --------------

TREE = ve.normalize(FORM, FIELDS).tree
IDS = set(ve.normalize(FORM, FIELDS).by_id)


def test_ai_unknown_field_returns_no_ops_and_plain_unclear():
    ops, unclear = vai.validate_edit_proposal({"ops": [], "unclear": "There is no Fax field on this screen."}, IDS, FIELDS)
    assert ops == [] and unclear == "There is no Fax field on this screen."
    ops, unclear = vai.validate_edit_proposal({"ops": [], "unclear": None}, IDS, FIELDS)
    assert ops == [] and unclear


def _injections(n: int = 300) -> list[dict]:
    rnd = random.Random(7)
    bad_fields = ["x_fax", "password", "fax", "../etc", "stage_id.name", "name; drop", "", "Phone"]
    bad_nodes = ["field:fax", "group:nope", "root/../x", "field:name~9", "", "sheet"]
    out = []
    for _ in range(n):
        kind = rnd.choice(["insert_field", "move", "hide", "wrap", "set_condition"])
        if kind == "insert_field":
            out.append({"op": kind, "field": rnd.choice(bad_fields), "target": rnd.choice(sorted(IDS)), "position": "after"})
        elif kind == "move":
            out.append({"op": kind, "node": rnd.choice(bad_nodes), "target": rnd.choice(sorted(IDS)), "position": "after"})
        elif kind == "hide":
            out.append({"op": kind, "node": rnd.choice(bad_nodes)})
        elif kind == "wrap":
            out.append({"op": kind, "nodes": ["field:phone", rnd.choice(bad_nodes)], "kind": "group"})
        else:
            out.append({"op": kind, "node": "field:phone", "condition": {"rules": [{"field": rnd.choice(bad_fields), "op": "set"}]}})
    return out


def test_ai_validator_rejects_every_injected_unknown_field_or_node():
    injections = _injections()
    rejected = 0
    for bad in injections:
        good = {"op": "hide", "node": "field:phone"}
        with pytest.raises(ve.EngineError):
            vai.validate_edit_proposal({"ops": [good, bad], "unclear": None}, IDS, FIELDS)
        rejected += 1
    assert rejected == len(injections) == 300


def test_ai_validator_rejects_disallowed_ops():
    for bad in [{"op": "replace", "node": "field:phone"}, {"op": "set_access", "node": "field:phone", "edit": ["base.group_system"]},
                {"op": "publish"}, "not a dict"]:
        with pytest.raises(ve.EngineError):
            vai.validate_edit_proposal({"ops": [bad], "unclear": None}, IDS, FIELDS)


def test_ai_condition_proposal_resolved_and_written_by_code():
    def lookup(relation, name, ids):
        table = {4: "Won", 1: "New"}
        if ids:
            return [(i, table[i]) for i in ids if i in table]
        return [(i, n) for i, n in table.items() if (name or "").lower() in n.lower()]

    raw = {"readings": [{"description": "x", "sense": "show", "match": "all", "rules": [{"field": "stage_id", "op": "is", "value": "Won"}]}]}
    readings, unclear = vai.validate_condition_proposal(raw, FIELDS, lookup)
    assert unclear is None and readings[0]["expression"] == "stage_id == 4" and readings[0]["sentence"] == "Stage is Won"
    raw_bad = {"readings": [{"description": "x", "match": "all", "rules": [{"field": "fax", "op": "set"}]}]}
    readings, unclear = vai.validate_condition_proposal(raw_bad, FIELDS, lookup)
    assert readings == [] and "no field called" in unclear


def test_prompts_are_spec_verbatim():
    assert vai.EDIT_SYSTEM_PROMPT.startswith("You turn one request about an Odoo screen into edit operations.")
    assert vai.EDIT_SYSTEM_PROMPT.endswith("Do not change anything the request did not mention.")
    assert vai.CONDITION_SYSTEM_PROMPT.endswith("each with a one-line plain description, and no others.")


def test_propose_edit_with_stub_provider(monkeypatch):
    monkeypatch.setattr(vai, "_call", lambda *a, **k: {"ops": [{"op": "insert_field", "field": "x_fax", "target": "field:phone"}], "unclear": None})
    with pytest.raises(ve.EngineError, match="doesn't exist here"):
        vai.propose_edit("add fax", TREE, FIELDS)
    monkeypatch.setattr(vai, "_call", lambda *a, **k: {"ops": [{"op": "hide", "node": "field:phone"}], "unclear": None})
    assert vai.propose_edit("hide phone", TREE, FIELDS) == ([{"op": "hide", "node": "field:phone"}], None)


# ---- history compare / catalogue / report draft -----------------------------

def test_compare_trees_markers():
    old = ve.normalize(FORM, FIELDS).tree
    res = ve.compile_ops(FORM, FIELDS, [
        {"op": "move", "node": "field:stage_id", "target": "field:priority", "position": "after"},
        {"op": "hide", "node": "field:email_from"},
        {"op": "insert_field", "field": "active", "target": "field:phone", "position": "after"},
    ])
    diff = vl.compare_trees(old, ve.normalize(res.expected_arch, FIELDS).tree)
    assert diff["markers"]["field:stage_id"] == "moved"
    assert diff["markers"]["field:email_from"] == "hidden"
    assert diff["markers"]["field:active"] == "added"


def test_ops_fields_for_version_check():
    ops = [{"op": "insert_field", "field": "x_new"}, {"op": "set_condition", "node": "field:phone", "condition": {"rules": [{"field": "stage_id"}]}}]
    assert vl.ops_fields(ops) == {"x_new", "phone", "stage_id"}


def test_report_draft_is_gated_by_token():
    slot = {"xpath": "//div[hasclass('page')]", "position": "inside"}
    arch = vr.compile_report_draft(slot, [{"type": "text", "text": "Draft thanks"}], "o", "abcdef0123456789", hide_published=True)
    assert "o.env.context.get('ingenium_draft') == 'abcdef0123456789'" in arch
    assert "!= 'abcdef0123456789'" in arch and "Draft thanks" in arch
    with pytest.raises(ve.EngineError):
        vr.compile_report_draft(slot, [], "o", "bad token!", hide_published=False)


def test_developer_mode_items_count_as_shown_with_note():
    tree = {"id": "root", "tag": "form", "attrs": {}, "children": [
        {"id": "group:email", "tag": "group", "attrs": {"groups": "base.group_no_one"}, "children": [
            {"id": "field:message_bounce", "tag": "field", "name": "message_bounce", "attrs": {}, "children": []}]},
        {"id": "field:x", "tag": "field", "name": "x", "attrs": {}, "helper": True, "children": []},
    ]}
    vis = vl.visibility_for(tree, {"base.group_user"})
    assert vis["field:message_bounce"]["visible"] is True
    assert vis["group:email"]["note"] == "Only shown in developer mode."
    assert vis["field:x"]["visible"] is False


def test_odoo20_access_operation_round_trip():
    from app import view_engine_access as va

    assert va.perms_to_operation({"read": True, "write": True, "create": True, "unlink": False}) == "cru"
    assert va.operation_to_perms("rd") == {"create": False, "read": True, "write": False, "unlink": True}
    assert va.row_values("ir.access", {"read": False}) == {"active": False}
    assert va.row_values("ir.model.access", {"perm_read": True}) == {
        "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False}


def test_odoo20_grant_keeps_the_roles_record_limit():
    from app import view_engine_access as va

    rows = [
        {"group": "sales_team.group_sale_salesman", "group_id": 1, "read": True, "domain": "[('user_id','=',user.id)]"},
        {"group": "sales_team.group_sale_manager", "group_id": 2, "read": True, "domain": ""},
    ]
    assert va.grant_domain(rows, {"sales_team.group_sale_salesman"}) == ("[('user_id','=',user.id)]", True)
    assert va.grant_domain(rows, {"sales_team.group_sale_salesman", "sales_team.group_sale_manager"}) == (None, True)
    rows.append({"group": "sales_team.group_sale_salesman", "group_id": 1, "read": True, "domain": "[('team_id','=',1)]"})
    assert va.grant_domain(rows, {"sales_team.group_sale_salesman"}) == (None, False)


def test_field_used_elsewhere_on_screen():
    from app.routers.view_engine_logic import _used_elsewhere

    arch = ('<form><field name="partner_id" context="{\'default_phone\': phone}"/>'
            '<field name="phone" widget="phone"/><field name="phone_sanitized"/></form>')
    assert _used_elsewhere(arch, "phone") is True
    assert _used_elsewhere('<form><field name="phone"/><field name="phone_sanitized"/></form>', "phone") is False


def test_copy_rules_reuses_the_exact_rule_from_another_item():
    arch = ('<form><sheet><group name="g"><field name="name"/>'
            '<field name="email" invisible="not is_company"/></group></sheet></form>')
    fields = {"name": {"type": "char", "string": "Name"}, "email": {"type": "char", "string": "Email"},
              "is_company": {"type": "boolean", "string": "Is a company"}}
    out = ve.compile_ops(arch, fields, [{"op": "set_condition", "node": "field:name", "attr": "invisible",
                                         "sense": "show", "condition": None, "copy_from": "field:email"}])
    assert "field[@name='name']" in out.arch and ">not is_company</attribute>" in out.arch


def test_developer_mode_items_hidden_before_19_even_for_members() -> None:
    member = {"base.group_user", "base.group_no_one"}
    assert vl.groups_allow("base.group_no_one", member, dev_kept=True)
    assert not vl.groups_allow("base.group_no_one", member, dev_kept=False)
    assert vl.groups_allow("base.group_no_one,base.group_user", member, dev_kept=False)
    tree = {"id": "root", "tag": "form", "attrs": {}, "children": [
        {"id": "field:email_cc", "tag": "field", "name": "email_cc", "attrs": {"groups": "base.group_no_one"}, "children": []}]}
    vis = vl.visibility_for(tree, member, dev_kept=False)
    assert vis["field:email_cc"] == {"visible": False, "reason": "Only shown in developer mode."}
    vis19 = vl.visibility_for(tree, member, dev_kept=True)
    assert vis19["field:email_cc"]["visible"] and vis19["field:email_cc"]["note"] == "Only shown in developer mode."
