"""BOT-REQ2MOD: requirement -> module spec. Offline (versioncaps data); never touches Odoo."""

from __future__ import annotations

import ast
import copy
import dataclasses
import io
import zipfile
from pathlib import Path
from types import MappingProxyType

import pytest
from module_generator import build_module_zip
from module_generator.ispec import ispec_to_module_spec, module_spec_to_ispec

from app.bots import req2mod as rm
from app.bots import tiers as tt

BASE = ["base", "web", "mail", "contacts", "base_automation"]

# Two unrelated, neutral fixtures: the mapper has no domain knowledge.
REQUESTS = {
    "name": "Requests",
    "summary": "Track incoming requests and who handles them",
    "entities": [
        {
            "key": "request",
            "label": "Request",
            "chatter": True,
            "states": ["New", "In Progress", "Done"],
            "fields": [
                {"key": "contact", "type": "many2one", "relation": "res.partner", "required": True},
                {"key": "priority", "type": "selection", "options": ["Low", "High"]},
                {"key": "due", "type": "date"},
                {"key": "notes", "type": "html"},
                {"key": "topic", "type": "many2one", "relation": "x_topic"},
            ],
        },
        {"key": "topic", "label": "Topic", "fields": [{"key": "code", "type": "char"}]},
    ],
    "extend": [{"model": "res.partner", "fields": [{"key": "request_ref", "type": "char"}]}],
    "roles": [
        {
            "key": "member",
            "label": "Member",
            "access": {"request": "rwc", "topic": "r"},
            "own_only": ["request"],
        },
        {"key": "lead", "label": "Lead", "access": {"request": "rwcd", "topic": "rwcd"}},
    ],
    "rules": [
        {
            "label": "Flag urgent",
            "entity": "request",
            "when": "on_create",
            "if": [["priority", "=", "high"]],
            "then": [{"set": {"state": "in_progress"}}, {"note": "Marked urgent"}],
        },
    ],
}
ASSETS = {
    "name": "Asset Register",
    "entities": [
        {
            "key": "asset",
            "label": "Asset",
            "fields": [
                {"key": "serial", "type": "char", "required": True},
                {"key": "value", "type": "float"},
                {"key": "in_use", "type": "boolean"},
            ],
        }
    ],
    "roles": [{"key": "keeper", "label": "Keeper", "access": {"asset": "rwcd"}}],
}


def mk(req=REQUESTS, v=17, tech="x_requests_app", inst=BASE):
    return rm.build(copy.deepcopy(req), version=v, installed_modules=inst, technical_name=tech)


def items(req):
    """Every requirement item path the trace must cover."""
    out = []
    for i, e in enumerate(req.get("entities", [])):
        out.append(f"entities[{i}]")
        out += [f"entities[{i}].fields[{j}]" for j in range(len(e["fields"]))]
        if "states" in e:
            out.append(f"entities[{i}].states")
    for i, x in enumerate(req.get("extend", [])):
        out.append(f"extend[{i}]")
        out += [f"extend[{i}].fields[{j}]" for j in range(len(x["fields"]))]
    for i, r in enumerate(req.get("roles", [])):
        out.append(f"roles[{i}]")
        out += [f"roles[{i}].access.{k}" for k in r["access"]]
        if r.get("own_only"):
            out.append(f"roles[{i}].own_only")
    out += [f"rules[{i}]" for i in range(len(req.get("rules", [])))]
    return out


# AC1 trace: every requirement item maps to at least one spec element
@pytest.mark.parametrize("req", [REQUESTS, ASSETS])
def test_every_item_traced(req):
    r = mk(req, tech="x_app_" + req["name"].split()[0].lower())
    assert r.ok, r.errors
    assert set(items(req)) <= set(r.trace) and all(r.trace.values())


# AC2 spec renders for every supported version; ISPEC round-trips; python parses
@pytest.mark.parametrize("v", rm.VERSIONS)
def test_renders_and_roundtrips(v):
    req = REQUESTS if v <= 19 else _no_own(REQUESTS)
    r = mk(req, v=v)
    assert r.ok, r.errors
    assert ispec_to_module_spec(module_spec_to_ispec(r.spec)) == r.spec
    with zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec, odoo_major=v))) as z:
        names = z.namelist()
        for n in names:
            if n.endswith(".py"):
                ast.parse(z.read(n).decode())
        assert "x_requests_app/tests/test_x_requests_app.py" in names
        man = z.read("x_requests_app/__manifest__.py").decode()
    assert f"'{v}.0.1.0.0'" in man or f'"{v}.0.1.0.0"' in man
    lt = [x for x in r.spec.views if x.name.endswith("list")][0]
    assert lt.type == ("tree" if v == 17 else "list")
    assert {"base", "base_automation", "mail"} <= set(r.spec.depends)


def _no_own(req):
    req = copy.deepcopy(req)
    for ro in req["roles"]:
        ro.pop("own_only", None)
    return req


# AC3 security: every new model has access; letters validated; own-only rule; version gate
def test_security_shape():
    r = mk()
    acl = {
        (a.model, a.group): (a.perm_read, a.perm_write, a.perm_create, a.perm_unlink)
        for a in r.spec.access_rules
    }
    assert acl[("model_x_request", "group_x_requests_app_member")] == (1, 1, 1, 0)
    assert acl[("model_x_topic", "group_x_requests_app_member")] == (1, 0, 0, 0)
    (rule,) = r.spec.record_rules
    assert "create_uid" in rule.domain_force and rule.group_xml_ids
    assert all(g.category_id for g in r.spec.groups)
    assert all(g.category_id is None for g in mk(v=19).spec.groups)  # 19+: privilege_id


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda q: [ro["access"].pop("topic") for ro in q["roles"]], "no role can open topic"),
        (lambda q: q["roles"][0]["access"].update(request="wc"), "needs read"),
        (lambda q: q["roles"][0]["access"].update(request="rx"), "letters"),
        (lambda q: q["roles"][0]["access"].update(ghost="r"), "not a record type"),
        (lambda q: q.update(roles=[]), "at least one role"),
    ],
)
def test_security_fail_closed(mutate, needle):
    q = copy.deepcopy(REQUESTS)
    mutate(q)
    r = mk(q)
    assert not r.ok and r.spec is None and any(needle in e for e in r.errors), r.errors


def test_own_only_refused_where_record_rules_absent():
    r = mk(v=20)
    assert not r.ok and any("ir.access" in e for e in r.errors)


# AC4 automations: closed vocabulary; requirement text is only ever a literal
def test_automation_code_is_closed_vocabulary():
    q = copy.deepcopy(REQUESTS)
    evil = "x'); env['res.users'].unlink(); ('"
    q["rules"][0]["then"] = [{"note": evil}, {"set": {"state": "done"}}]
    r = mk(q)
    (a,) = r.spec.python_automations
    tree = ast.parse(a.code)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert calls == {"message_post"}
    assert any(isinstance(n, ast.Constant) and n.value == evil for n in ast.walk(tree))
    assert a.filter_domain == "[('x_priority', '=', 'high')]"
    assert a.trigger == "on_create"


@pytest.mark.parametrize(
    "rule,needle",
    [
        ({"label": "a", "entity": "request", "when": "daily", "then": [{"note": "x"}]}, "when"),
        ({"label": "a", "entity": "ghost", "when": "on_create", "then": [{"note": "x"}]}, "entity"),
        (
            {"label": "a", "entity": "request", "when": "on_create", "then": [{"code": "x"}]},
            "actions are",
        ),
        (
            {
                "label": "a",
                "entity": "request",
                "when": "on_create",
                "then": [{"set": {"contact": 1}}],
            },
            "plain field",
        ),
        (
            {
                "label": "a",
                "entity": "request",
                "when": "on_create",
                "if": [["priority", "like; drop", "x"]],
                "then": [{"note": "x"}],
            },
            "condition",
        ),
        (
            {"label": "a", "entity": "topic", "when": "on_create", "then": [{"note": "x"}]},
            "chatter",
        ),
    ],
)
def test_automation_fail_closed(rule, needle):
    q = copy.deepcopy(REQUESTS)
    q["rules"] = [rule]
    r = mk(q)
    assert not r.ok and any(needle in e for e in r.errors), r.errors


# AC5 bad input fails closed with a reason, never raises, never returns a partial spec
@pytest.mark.parametrize(
    "req,kw,needle",
    [
        ("text", {}, "object"),
        ({"name": "A"}, {}, "nothing to build"),
        ({**ASSETS, "extra": 1}, {}, "unknown requirement keys"),
        (ASSETS, {"v": 16}, "version"),
        (ASSETS, {"tech": "Bad-Name"}, "technical name"),
        (ASSETS, {"inst": "base"}, "installed"),
        ({**ASSETS, "entities": [{**ASSETS["entities"][0], "key": "class"}]}, {}, "key"),
        (
            {
                **ASSETS,
                "entities": [{**ASSETS["entities"][0], "fields": [{"key": "a", "type": "python"}]}],
            },
            {},
            "type",
        ),
        (
            {
                **ASSETS,
                "entities": [
                    {**ASSETS["entities"][0], "fields": [{"key": "name", "type": "char"}]}
                ],
            },
            {},
            "reserved",
        ),
        (
            {
                **ASSETS,
                "entities": [
                    {
                        **ASSETS["entities"][0],
                        "fields": [{"key": "r", "type": "many2one", "relation": "x_nowhere"}],
                    }
                ],
            },
            {},
            "relation",
        ),
        ({**ASSETS, "entities": [{**ASSETS["entities"][0], "label": "<b>x</b>"}]}, {}, "label"),
        (
            {
                **ASSETS,
                "extend": [{"model": "no.such.model", "fields": [{"key": "a", "type": "char"}]}],
            },
            {},
            "not a stock model",
        ),
        (
            {
                **ASSETS,
                "extend": [
                    {"model": "res.partner", "fields": [{"key": "a", "type": "char"}]},
                ]
                * 15,
            },
            {},
            "split the requirement",
        ),
    ],
)
def test_bad_input_fails_closed(req, kw, needle):
    r = mk(req, **kw)
    assert not r.ok and r.spec is None and any(needle in e for e in r.errors), r.errors


def test_existing_stock_field_not_redefined():
    q = copy.deepcopy(ASSETS)
    q["extend"] = [{"model": "res.partner", "fields": [{"key": "a", "type": "char"}] * 2}]
    assert not mk(q).ok


# AC6 does not switch T3 on: spec only; runnable follows tiers, never the requirement
def test_t3_stays_off_and_runnable_follows_tiers(monkeypatch):
    r = mk(ASSETS)
    assert r.ok and r.runnable is False and "not built" in r.blocked_reason
    assert tt.tier_ready(tt.T3) is False
    assert tt._CAPABILITIES["module-authoring"] is False
    assert tt._CAPABILITIES["module-test-gate"] is False
    on = dict(tt._CAPABILITIES, **{"module-authoring": True, "module-test-gate": True})
    monkeypatch.setattr(tt, "_CAPABILITIES", MappingProxyType(on))
    r2 = mk(ASSETS)
    assert r2.runnable is True and r2.blocked_reason == ""


# AC7 read-only: no Odoo client, no RPC, no writes from this module
def test_module_is_read_only():
    src = Path(rm.__file__).read_text()
    tree = ast.parse(src)
    mods = {
        getattr(n, "module", None) or ""
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
    }
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(
        m.startswith(("odoo_client", "app.changeset", "xmlrpc", "httpx", "requests")) for m in mods
    )
    assert "execute_kw" not in src


# AC8 version-aware: relations, extensions and dependencies come from that version's catalogue
def test_version_aware_dependencies():
    q = copy.deepcopy(ASSETS)
    q["entities"][0]["fields"].append(
        {"key": "order", "type": "many2one", "relation": "sale.order"}
    )
    r = mk(q, inst=BASE)
    assert r.ok and "sale" in r.spec.depends
    assert any("sale must be installed first" in a for a in r.assumptions)


# AC9 generated tests: create each new record type and check every role's access
def test_generated_tests_cover_create_and_access():
    r = mk()
    src = next(
        b["content"]
        for b in r.spec.custom_code_blocks
        if b["path"].endswith(".py") and "test_" in b["path"]
    )
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {"test_create_x_request", "test_create_x_topic"} <= names
    assert {f"test_{a.id}" for a in r.spec.access_rules} <= names
    assert "'x_contact': self.env['res.partner']" in src


# Review fixes (64579245)
@pytest.mark.parametrize("v", [17, 18])
def test_group_category_is_real_xmlid(v):
    r = mk(v=v)
    assert {g.category_id for g in r.spec.groups} == {"base.module_category_customizations"}


@pytest.mark.parametrize("bad", ["x_app\n", "abc", "x_", "X_app", "x_app ", 17])
def test_technical_name_exact_and_x_prefixed(bad):
    assert not mk(tech=bad).ok


def test_technical_name_cannot_be_stock_module(monkeypatch):
    monkeypatch.setattr(
        rm.caps, "module_info", lambda v, n: {"name": n} if n == "x_stock" else None
    )
    r = mk(req=ASSETS, tech="x_stock")
    assert not r.ok and "stock" in r.errors[0]


@pytest.mark.parametrize("v", [17.0, True, "17", 17.5])
def test_version_must_be_exact_int(v):
    assert not mk(v=v).ok


def test_keys_reject_trailing_newline():
    q = copy.deepcopy(ASSETS)
    q["entities"][0]["key"] = "asset\n"
    assert not mk(req=q, tech="x_assets").ok


def test_monetary_gets_currency_field():
    q = copy.deepcopy(ASSETS)
    q["entities"][0]["fields"].append({"key": "cost", "type": "monetary"})
    r = mk(req=q, tech="x_assets")
    m = r.spec.models[0]
    cost = next(f for f in m.fields if f.name == "x_cost")
    cur = next(f for f in m.fields if f.name == cost.currency_field)
    assert cur.ttype == "many2one" and cur.relation == "res.currency"


def test_many2many_link_table_name_capped():
    q = copy.deepcopy(ASSETS)
    long_key = "a" * 39
    q["entities"].append({"key": long_key, "label": "L", "fields": [{"key": "c", "type": "char"}]})
    q["entities"][1]["fields"].append(
        {"key": "peers", "type": "many2many", "relation": f"x_{long_key}"}
    )
    q["entities"][0]["fields"].append(
        {"key": "ls", "type": "many2many", "relation": f"x_{long_key}"}
    )
    q["roles"][0]["access"][long_key] = "r"
    r = mk(req=q, tech="x_assets")
    assert r.ok, r.errors  # explicit per-field tables, hash-shortened, never over 63
    tables = [f.relation_table for m in r.spec.models for f in m.fields if f.ttype == "many2many"]
    assert len(tables) == 2 and len(set(tables)) == 2
    assert all(len(t) <= rm.PG_NAME_MAX and t.startswith("x_") for t in tables)
    q["entities"][1]["key"] = "tag"
    q["entities"][1]["fields"][-1]["relation"] = "x_tag"
    q["entities"][0]["fields"][-1]["relation"] = "x_tag"
    q["roles"][0]["access"] = {"asset": "rwcd", "tag": "r"}
    assert mk(req=q, tech="x_assets").ok


PAYLOADS = ["a\nb", "trail\n", "x]]>y", "q'\"q", "Ünï ✓ 日本", "\x00", "\x1b[31m"]
SLOTS = (
    "name",
    "entity_label",
    "field_label",
    "option",
    "state",
    "role_label",
    "rule_label",
    "note",
    "value",
)


def _put(slot, p):
    q = copy.deepcopy(REQUESTS)
    e = q["entities"][0]
    {
        "name": lambda: q.__setitem__("name", p),
        "entity_label": lambda: e.__setitem__("label", p),
        "field_label": lambda: e["fields"][2].__setitem__("label", p),
        "option": lambda: e["fields"][1].__setitem__("options", ["Low", p]),
        "state": lambda: e.__setitem__("states", ["New", p]),
        "role_label": lambda: q["roles"][1].__setitem__("label", p),
        "rule_label": lambda: q["rules"][0].__setitem__("label", p),
        "note": lambda: q["rules"][0]["then"][1].__setitem__("note", p),
        "value": lambda: q["rules"][0]["if"][0].__setitem__(2, p),
    }[slot]()
    q["roles"][0].pop("own_only")
    q["rules"][0]["then"] = [a for a in q["rules"][0]["then"] if "set" not in a]
    return q


@pytest.mark.parametrize("v", [17, 19])
@pytest.mark.parametrize("slot", SLOTS)
@pytest.mark.parametrize("p", PAYLOADS)
def test_hostile_free_text_renders_parseable(v, slot, p):
    import xml.etree.ElementTree as ET

    r = mk(req=_put(slot, p), v=v)
    if not r.ok:
        return  # refused is safe
    with zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec, odoo_major=v))) as z:
        for n in z.namelist():
            body = z.read(n)
            if n.endswith(".py"):
                ast.parse(body)
            elif n.endswith(".xml"):
                ET.fromstring(body)


# ---------------------------------------------------------------- review round 2


@pytest.mark.parametrize("bad", ["a\\b", "trail\\", "\\u0041", "x\\n"])
def test_r2_r1_backslash_label_refused(bad):
    q = copy.deepcopy(ASSETS)
    q["name"] = bad
    assert not mk(req=q, tech="x_assets").ok
    q = copy.deepcopy(ASSETS)
    q["entities"][0]["label"] = bad
    assert not mk(req=q, tech="x_assets").ok


@pytest.mark.parametrize("name", ["a\\b", 'q"q', "x\ny", "\\", "Ünï ✓"])
def test_r2_r1_manifest_values_are_safe_literals(name):
    r = mk(tech="x_assets")
    spec = dataclasses.replace(r.spec, display_name=name, author=name)
    raw = build_module_zip(spec)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        man = next(n for n in z.namelist() if n.endswith("__manifest__.py"))
        d = ast.literal_eval(z.read(man).decode())
    assert d["name"] == name and d["author"] == name


def test_r2_r2_two_many2many_to_same_target_get_own_tables():
    q = copy.deepcopy(ASSETS)
    q["entities"][0]["fields"] += [
        {"key": "tags_a", "type": "many2many", "relation": "x_tag"},
        {"key": "tags_b", "type": "many2many", "relation": "x_tag"},
    ]
    q["entities"].append({"key": "tag", "label": "Tag", "fields": [{"key": "c", "type": "char"}]})
    q["roles"][0]["access"] = {"asset": "rwcd", "tag": "r"}
    r = mk(req=q, tech="x_assets")
    assert r.ok, r.errors
    m2m = [f for m in r.spec.models for f in m.fields if f.ttype == "many2many"]
    tables = [f.relation_table for f in m2m]
    assert len(tables) == len(set(tables)) >= 2 and all(tables)
    src = "".join(
        zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec))).read(n).decode()
        for n in zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec))).namelist()
        if n.endswith(".py")
    )
    for t in tables:
        assert f"relation={t!r}, column1='x_src_id', column2='x_dst_id'" in src


def test_r2_r2_table_name_hash_shortened_stable():
    long = rm.m2m_table("x_" + "a" * 60, "x_" + "b" * 38)
    assert len(long) <= rm.PG_NAME_MAX and long == rm.m2m_table("x_" + "a" * 60, "x_" + "b" * 38)
    assert long != rm.m2m_table("x_" + "a" * 60, "x_" + "b" * 37 + "c")
    assert rm.m2m_table("x_asset", "x_tags") == "x_x_asset_x_tags_rel"
