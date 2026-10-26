"""BOT-REQ2MOD: turn a structured client requirement into a module spec (read-only).

Input: a generic requirement (records to keep, extra fields on stock models, roles and their
access, automatic rules). Output: a ``module_generator.ModuleSpec`` (models, fields, views,
actions, menus, groups, access, record rules, automations) plus Odoo test files, and a trace
from every requirement item to the spec elements that satisfy it. The spec feeds module
authoring; this module never writes to Odoo, renders nothing to a database and never switches
T3 on: ``runnable`` stays False until tiers reports T3 ready (module authoring + module test
gate). Fail closed: any item that cannot be mapped with certainty is an error and no spec is
returned. Automation code comes only from a closed vocabulary (set a field to a literal, post a
note), never from requirement text.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass, field
from typing import Any

from module_generator import (
    AccessRuleSpec,
    ActionSpec,
    FieldSpec,
    GroupSpec,
    MenuSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    RecordRuleSpec,
    ViewSpec,
    ensure_monetary_currency_fields,
    list_view_for_major,
    manifest_version_for_major,
)

from app.bots import tiers as tt
from app.bots.versioncaps import caps

VERSIONS = (17, 18, 19, 20)
KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")
TECH_RE = re.compile(r"x_[a-z0-9_]{1,38}")
PG_NAME_MAX = 63
SCALAR_TYPES = frozenset(
    {"char", "text", "html", "integer", "float", "monetary", "boolean", "date", "datetime"}
)
TYPES = SCALAR_TYPES | {"selection", "many2one", "many2many"}
TRIGGERS = frozenset({"on_create", "on_write", "on_create_or_write"})
OPS = frozenset({"=", "!=", ">", ">=", "<", "<=", "in", "not in", "ilike"})
PERMS = {"r": "perm_read", "w": "perm_write", "c": "perm_create", "d": "perm_unlink"}
MAX_ENTITIES, MAX_FIELDS = 15, 60
_RESERVED = frozenset(
    {
        "id",
        "name",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "display_name",
        "active",
        "state",
        "company_id",
        "currency_id",
    }
)


class Req2ModError(ValueError):
    pass


@dataclass
class Result:
    ok: bool
    errors: tuple[str, ...]
    spec: ModuleSpec | None = None
    trace: dict[str, tuple[str, ...]] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    runnable: bool = False
    blocked_reason: str = ""


def _blocked() -> tuple[bool, str]:
    if tt.tier_ready(tt.T3):
        return True, ""
    return False, (
        "The module spec is ready, but bots cannot author or install module code (T3) yet: "
        "module authoring and the module test gate are not built. A developer can build it "
        "from this spec now."
    )


def _key(v: Any, where: str, errs: list[str]) -> str:
    if not isinstance(v, str) or not KEY_RE.fullmatch(v) or keyword.iskeyword(v):
        errs.append(f"{where}: key must be lower_snake_case (a-z, 0-9, _), max 40 characters")
        return "invalid"
    return v


def _label(v: Any, where: str, errs: list[str]) -> str:
    if (
        not isinstance(v, str)
        or not v.strip()
        or len(v) > 80
        or any(c in v for c in "<>\"'")
        or any(ord(c) < 0x20 or ord(c) == 0x7F for c in v)
    ):
        errs.append(f"{where}: label must be plain text, 1-80 characters")
        return "Invalid"
    return v.strip()


def _lit(v: Any) -> str:
    if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str) and len(v) <= 200 and "]]>" not in v:
        return repr(v)
    raise Req2ModError(
        "literal must be a number, boolean, empty, or text up to 200 characters without ']]>'"
    )


class _Builder:
    def __init__(self, req: dict[str, Any], version: int, installed: frozenset[str]):
        self.req, self.v, self.inst = req, version, installed
        self.errs: list[str] = []
        self.trace: dict[str, list[str]] = {}
        self.assume: list[str] = []
        self.depends: set[str] = {"base"}
        self.fields_of: dict[str, dict[str, str]] = {}  # model -> field -> ttype
        self.chatter: set[str] = set()
        self.model_of: dict[str, str] = {}  # "entities[i]"/"extend[i]" -> model

    def tr(self, item: str, element: str) -> None:
        self.trace.setdefault(item, []).append(element)

    def model_exists(self, model: str) -> bool:
        return caps.model_info(self.v, model) is not None

    def stock_dep(self, model: str, where: str) -> None:
        mod = caps.find_module_for(self.v, model)
        if not mod:
            self.errs.append(f"{where}: {model} is not a stock model in Odoo {self.v}")
            return
        self.depends.add(mod)
        if mod not in self.inst:
            self.assume.append(f"{mod} must be installed first (needed for {model})")

    def field(self, f: Any, where: str, own_models: set[str]) -> FieldSpec | None:
        if not isinstance(f, dict):
            self.errs.append(f"{where}: field must be an object")
            return None
        k = _key(f.get("key"), where, self.errs)
        lab = _label(f.get("label", k.replace("_", " ").title()), where, self.errs)
        t = f.get("type")
        if t not in TYPES:
            self.errs.append(f"{where}: type must be one of {sorted(TYPES)}")
            return None
        unknown = set(f) - {"key", "label", "type", "required", "options", "relation", "help"}
        if unknown:
            self.errs.append(f"{where}: unknown keys {sorted(unknown)}")
        kw: dict[str, Any] = {"required": f.get("required") is True}
        if t == "selection":
            opts = f.get("options")
            if not isinstance(opts, list) or not opts or len(opts) > 30:
                self.errs.append(f"{where}: selection needs 1-30 options")
                return None
            labels = [_label(o, f"{where}.options", self.errs) for o in opts]
            keys = [re.sub(r"[^a-z0-9]+", "_", o.lower()).strip("_") for o in labels]
            if len(set(keys)) != len(keys) or not all(keys):
                self.errs.append(f"{where}: selection options must be distinct")
                return None
            kw["selection"] = repr(list(zip(keys, labels, strict=True)))
        elif t in ("many2one", "many2many"):
            rel = f.get("relation")
            if not isinstance(rel, str) or not (rel in own_models or self.model_exists(rel)):
                self.errs.append(f"{where}: relation {rel!r} is not a stock or new model")
                return None
            if rel not in own_models:
                self.stock_dep(rel, where)
            kw["relation"] = rel
            if t == "many2many":
                # Odoo default: "<a>_<b>_rel" from sorted table names; Postgres caps names at 63.
                me = where.split(".", 1)[0]
                tables = sorted([self.model_of.get(me, ""), rel])
                tables = [x.replace(".", "_") for x in tables]
                if len(f"{tables[0]}_{tables[1]}_rel") > PG_NAME_MAX:
                    self.errs.append(
                        f"{where}: link table name would exceed {PG_NAME_MAX} characters; "
                        "use shorter record type keys"
                    )
                    return None
            if t == "many2one":
                kw["on_delete"] = "restrict" if kw["required"] else "set null"
        elif "options" in f or "relation" in f:
            self.errs.append(f"{where}: options/relation only apply to selection/relations")
        if isinstance(f.get("help"), str):
            kw["help"] = _label(f["help"], where, self.errs)
        return FieldSpec(name=f"x_{k}", ttype=t, string=lab, **kw)


def build(req: Any, *, version: Any, installed_modules: Any, technical_name: Any) -> Result:
    """Map ``req`` to a ModuleSpec for Odoo ``version``. Never raises on bad input."""
    try:
        return _build(req, version, installed_modules, technical_name)
    except Req2ModError as e:
        return Result(False, (str(e),))
    except Exception as e:  # noqa: BLE001 - fail closed
        return Result(False, (f"could not map the requirement ({type(e).__name__})",))


def _build(req: Any, version: Any, installed: Any, tech: Any) -> Result:
    if type(version) is not int or version not in VERSIONS:
        raise Req2ModError(f"Odoo version must be one of {VERSIONS}")
    if not isinstance(req, dict):
        raise Req2ModError("requirement must be an object")
    if not isinstance(installed, (list, tuple, set, frozenset)) or not all(
        isinstance(m, str) for m in installed
    ):
        raise Req2ModError("installed modules must be a list of names")
    if not isinstance(tech, str) or not TECH_RE.fullmatch(tech):
        raise Req2ModError("technical name must be x_ plus lower_snake_case, max 40 characters")
    if caps.module_info(version, tech):
        raise Req2ModError(f"technical name {tech} is a stock Odoo {version} module")
    unknown = set(req) - {"name", "summary", "entities", "extend", "roles", "rules"}
    if unknown:
        raise Req2ModError(f"unknown requirement keys {sorted(unknown)}")
    b = _Builder(req, version, frozenset(installed))
    errs = b.errs
    title = _label(req.get("name"), "name", errs)
    ents = req.get("entities", [])
    exts = req.get("extend", [])
    roles = req.get("roles", [])
    rules = req.get("rules", [])
    for nm, val in (("entities", ents), ("extend", exts), ("roles", roles), ("rules", rules)):
        if not isinstance(val, list):
            raise Req2ModError(f"{nm} must be a list")
    if not ents and not exts:
        raise Req2ModError("requirement has nothing to build (no entities or extensions)")
    if len(ents) + len(exts) > MAX_ENTITIES:
        raise Req2ModError(f"more than {MAX_ENTITIES} record types: split the requirement")

    keys = [e.get("key") if isinstance(e, dict) else None for e in ents]
    own = {f"x_{k}" for k in keys if isinstance(k, str)}
    if len(set(keys)) != len(keys):
        errs.append("entities: keys must be unique")
    models: list[ModelSpec] = []
    views: list[ViewSpec] = []
    actions: list[ActionSpec] = []
    menus: list[MenuSpec] = []
    list_type, list_tag = list_view_for_major(version)
    root_menu = MenuSpec(name=title, technical_name=f"{tech}_root", sequence=50)
    nfields = 0
    for i, e in enumerate(ents):
        w = f"entities[{i}]"
        if not isinstance(e, dict) or set(e) - {"key", "label", "fields", "states", "chatter"}:
            errs.append(f"{w}: needs key, label, fields; optional states, chatter")
            continue
        k = _key(e.get("key"), w, errs)
        lab = _label(e.get("label"), w, errs)
        model = f"x_{k}"
        b.model_of[w] = model
        fl = e.get("fields", [])
        if not isinstance(fl, list) or not fl:
            errs.append(f"{w}: needs at least one field")
            continue
        specs = [FieldSpec(name="x_name", ttype="char", string="Name", required=True)]
        seen = {"name"}
        for j, f in enumerate(fl):
            fs = b.field(f, f"{w}.fields[{j}]", own)
            nfields += 1
            if fs is None:
                continue
            raw = fs.name[2:]
            if raw in seen or raw in _RESERVED:
                errs.append(f"{w}.fields[{j}]: {raw} is duplicate or reserved")
                continue
            seen.add(raw)
            specs.append(fs)
            b.tr(f"{w}.fields[{j}]", f"field {model}.{fs.name}")
        mixins: list[str] = []
        if e.get("chatter") is True:
            mixins = ["mail.thread", "mail.activity.mixin"]
            b.chatter.add(model)
            b.depends.add("mail")
        st = e.get("states")
        state_field = None
        if st is not None:
            if not isinstance(st, list) or not 2 <= len(st) <= 10:
                errs.append(f"{w}: states needs 2-10 names")
            else:
                sl = [_label(s, f"{w}.states", errs) for s in st]
                sk = [re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") for s in sl]
                if len(set(sk)) != len(sk) or not all(sk):
                    errs.append(f"{w}: states must be distinct")
                specs.append(
                    FieldSpec(
                        name="x_state",
                        ttype="selection",
                        string="Status",
                        selection=repr(list(zip(sk, sl, strict=True))),
                    )
                )
                state_field = {"name": "x_state", "values": sk}
                b.tr(f"{w}.states", f"field {model}.x_state")
        models.append(
            ModelSpec(
                model=model, description=lab, fields=specs, mixins=mixins, state_field=state_field
            )
        )
        b.fields_of[model] = {f.name: f.ttype for f in specs}
        cols = "".join(f'<field name="{f.name}"/>' for f in specs if f.ttype != "html")
        form = "".join(f'<field name="{f.name}"/>' for f in specs)
        header = '<header><field name="x_state" widget="statusbar"/></header>' if st else ""
        chat = (
            "<chatter/>"
            if mixins and version >= 18
            else (
                '<div class="oe_chatter"><field name="message_follower_ids"/>'
                '<field name="message_ids"/></div>'
                if mixins
                else ""
            )
        )
        views += [
            ViewSpec(
                name=f"{tech} {k} list",
                model=model,
                type=list_type,
                arch=f"<{list_tag}>{cols}</{list_tag}>",
            ),
            ViewSpec(
                name=f"{tech} {k} form",
                model=model,
                type="form",
                arch=f"<form>{header}<sheet><group>{form}</group></sheet>{chat}</form>",
            ),
            ViewSpec(
                name=f"{tech} {k} search",
                model=model,
                type="search",
                arch='<search><field name="x_name"/></search>',
            ),
        ]
        act = ActionSpec(name=lab, model=model, technical_name=f"action_{tech}_{k}")
        actions.append(act)
        menus.append(
            MenuSpec(
                name=lab,
                action_xml_id=act.xml_id(),
                parent_xml_id=root_menu.xml_id(),
                technical_name=f"{tech}_{k}",
            )
        )
        for el in (f"model {model}", f"views {model}", f"menu {lab}"):
            b.tr(w, el)
    if nfields > MAX_FIELDS:
        errs.append(f"more than {MAX_FIELDS} fields: split the requirement")

    for i, x in enumerate(exts):
        w = f"extend[{i}]"
        if not isinstance(x, dict) or set(x) - {"model", "fields"}:
            errs.append(f"{w}: needs model and fields")
            continue
        m = x.get("model")
        if not isinstance(m, str) or not b.model_exists(m):
            errs.append(f"{w}: {m!r} is not a stock model in Odoo {version}")
            continue
        b.stock_dep(m, w)
        b.model_of[w] = m
        existing = set((caps.model_info(version, m) or {}).get("fields", {}))
        specs = []
        for j, f in enumerate(x.get("fields") or []):
            fs = b.field(f, f"{w}.fields[{j}]", own)
            if fs is None:
                continue
            if fs.name in existing or fs.name in {s.name for s in specs}:
                errs.append(f"{w}.fields[{j}]: {fs.name} already exists on {m}")
                continue
            specs.append(fs)
            b.tr(f"{w}.fields[{j}]", f"field {m}.{fs.name}")
        if not specs:
            errs.append(f"{w}: needs at least one valid field")
            continue
        models.append(ModelSpec(model=m, description="", fields=specs, mode="inherit", inherit=m))
        b.fields_of[m] = {f.name: f.ttype for f in specs}
        b.tr(w, f"inherit {m}")
        b.assume.append(
            f"new fields on {m} are not placed on its screens; place them with the view "
            "designer (T2) after install"
        )

    groups, access, rrules = _security(b, tech, title, roles, own)
    autos = _automations(b, rules)
    if errs:
        return Result(False, tuple(dict.fromkeys(errs)))
    if models and any(mm.mode == "new" for mm in models):
        menus.insert(0, root_menu)
    if autos:
        b.depends.add("base_automation")
        if not caps.module_info(version, "base_automation"):
            return Result(False, (f"automations are not available in Odoo {version}",))
    spec = ModuleSpec(
        technical_name=tech,
        display_name=title,
        version=manifest_version_for_major(version),
        depends=sorted(b.depends),
        author="Ingenium",
        odoo_major=version,
        models=models,
        views=views,
        actions=actions,
        menus=menus,
        groups=groups,
        python_automations=autos,
        access_rules=access,
        record_rules=rrules,
        custom_code_blocks=_tests(tech, models, roles, access),
    )
    ensure_monetary_currency_fields(spec)  # monetary needs a currency field (x_currency_id)
    runnable, why = _blocked()
    return Result(
        True,
        (),
        spec,
        {k: tuple(v) for k, v in b.trace.items()},
        tuple(dict.fromkeys(b.assume)),
        runnable,
        why,
    )


def _security(b: _Builder, tech: str, title: str, roles: list, own: set[str]):
    errs, v = b.errs, b.v
    groups: list[GroupSpec] = []
    access: list[AccessRuleSpec] = []
    rrules: list[RecordRuleSpec] = []
    if own and not roles:
        errs.append("roles: new record types need at least one role with access")
    seen: set[str] = set()
    for i, r in enumerate(roles):
        w = f"roles[{i}]"
        if not isinstance(r, dict) or set(r) - {"key", "label", "access", "own_only"}:
            errs.append(f"{w}: needs key, label, access; optional own_only")
            continue
        k = _key(r.get("key"), w, errs)
        if k in seen:
            errs.append(f"{w}: duplicate role")
        seen.add(k)
        gid = f"group_{tech}_{k}"
        groups.append(
            GroupSpec(
                id=gid,
                name=f"{title} / {_label(r.get('label'), w, errs)}",
                category_id="base.module_category_customizations" if v <= 18 else None,
                implied_ids=["base.group_user"],
            )
        )
        b.tr(w, f"group {gid}")
        acc = r.get("access")
        if not isinstance(acc, dict) or not acc:
            errs.append(f"{w}: access must map record types to letters r, w, c, d")
            continue
        for ek, letters in acc.items():
            model = f"x_{ek}"
            if model not in own:
                errs.append(f"{w}.access: {ek} is not a record type in this requirement")
                continue
            if not isinstance(letters, str) or not letters or set(letters) - set(PERMS):
                errs.append(f"{w}.access.{ek}: use letters r, w, c, d")
                continue
            if "r" not in letters:
                errs.append(f"{w}.access.{ek}: write, create or delete needs read (r)")
                continue
            perms = {p: int(c in letters) for c, p in PERMS.items()}
            aid = f"access_{model}_{k}"
            access.append(
                AccessRuleSpec(
                    id=aid, name=f"{model}.{k}", model=f"model_{model}", group=gid, **perms
                )
            )
            b.tr(f"{w}.access.{ek}", f"access {aid}")
        oo = r.get("own_only", [])
        if not isinstance(oo, list):
            errs.append(f"{w}.own_only must be a list")
            continue
        for ek in oo:
            model = f"x_{ek}"
            if model not in own or ek not in acc:
                errs.append(f"{w}.own_only: {ek} needs access first")
                continue
            if not caps.model_info(v, "ir.rule"):
                errs.append(
                    f"{w}.own_only: Odoo {v} replaced record rules with domain access rights "
                    "(ir.access); generating those is not supported yet"
                )
                continue
            rid = f"rule_{model}_{k}_own"
            rrules.append(
                RecordRuleSpec(
                    name=f"{model} own ({k})",
                    model_xml_id=f"model_{model}",
                    domain_force="[('create_uid', '=', user.id)]",
                    group_xml_ids=[gid],
                    technical_name=rid,
                )
            )
            b.tr(f"{w}.own_only", f"record rule {rid}")
    for m in sorted(own):
        if not any(a.model == f"model_{m}" for a in access):
            errs.append(f"no role can open {m[2:]}: give at least one role access")
    return groups, access, rrules


def _automations(b: _Builder, rules: list) -> list[PythonAutomationSpec]:
    errs, out = b.errs, []
    for i, r in enumerate(rules):
        w = f"rules[{i}]"
        if not isinstance(r, dict) or set(r) - {"label", "entity", "when", "if", "then"}:
            errs.append(f"{w}: needs label, entity, when, then; optional if")
            continue
        model = f"x_{r.get('entity')}" if isinstance(r.get("entity"), str) else ""
        flds = b.fields_of.get(model)
        if flds is None:
            errs.append(f"{w}: entity is not a new record type in this requirement")
            continue
        if r.get("when") not in TRIGGERS:
            errs.append(f"{w}: when must be one of {sorted(TRIGGERS)}")
            continue
        dom = []
        for c in r.get("if", []) or []:
            if not isinstance(c, list) or len(c) != 3 or f"x_{c[0]}" not in flds or c[1] not in OPS:
                errs.append(f"{w}.if: each condition is [field, operator, value] on this record")
                continue
            try:
                dom.append(f"({_lit('x_' + c[0])}, {_lit(c[1])}, {_lit(c[2])})")
            except Req2ModError as e:
                errs.append(f"{w}.if: {e}")
        then = r.get("then")
        if not isinstance(then, list) or not then:
            errs.append(f"{w}: then needs at least one action")
            continue
        lines = ["for rec in records:"]
        for a in then:
            if isinstance(a, dict) and set(a) == {"set"} and isinstance(a["set"], dict):
                for fk, val in a["set"].items():
                    fn = f"x_{fk}"
                    if fn not in flds or flds[fn] in ("many2one", "many2many"):
                        errs.append(f"{w}.then: {fk} is not a plain field on this record")
                        continue
                    try:
                        lines.append(f"    rec[{fn!r}] = {_lit(val)}")
                    except Req2ModError as e:
                        errs.append(f"{w}.then: {e}")
            elif isinstance(a, dict) and set(a) == {"note"} and isinstance(a["note"], str):
                if model not in b.chatter:
                    errs.append(f"{w}.then: notes need the record type to have chatter")
                    continue
                lines.append(f"    rec.message_post(body={_lit(a['note'])})")
            else:
                errs.append(
                    f"{w}.then: actions are {{'set': {{field: value}}}} or {{'note': text}}"
                )
        label = _label(r.get("label"), w, errs)
        out.append(
            PythonAutomationSpec(
                name=label,
                model=model,
                trigger=r["when"],
                code="\n".join(lines),
                filter_domain=f"[{', '.join(dom)}]" if dom else None,
            )
        )
        b.tr(w, f"automation {label}")
    return out


def _tests(tech: str, models: list[ModelSpec], roles: list, access: list[AccessRuleSpec]):
    """Odoo tests the module test gate will run: create each new record type with its required
    fields, and check every role's access matches the requirement."""
    samples = {
        "char": "'Sample'",
        "text": "'Sample'",
        "html": "'<p>Sample</p>'",
        "integer": "1",
        "float": "1.0",
        "monetary": "1.0",
        "boolean": "True",
        "date": "'2026-01-01'",
        "datetime": "'2026-01-01 00:00:00'",
    }
    body = [
        "from odoo.tests.common import TransactionCase, tagged",
        "",
        "",
        "@tagged('post_install', '-at_install')",
        f"class Test{''.join(p.title() for p in tech.split('_'))}(TransactionCase):",
    ]
    n = 0
    for m in models:
        if m.mode != "new":
            continue
        vals = []
        for f in m.fields:
            if f.required and f.ttype in samples:
                vals.append(f"{f.name!r}: {samples[f.ttype]}")
            elif f.required and f.ttype == "selection":
                vals.append(f"{f.name!r}: {eval(f.selection)[0][0]!r}")  # noqa: S307 - own repr
            elif f.required and f.ttype == "many2one":
                vals.append(f"{f.name!r}: self.env[{f.relation!r}].search([], limit=1).id")
        n += 1
        body += [
            "",
            f"    def test_create_{m.model}(self):",
            f"        rec = self.env[{m.model!r}].create({{{', '.join(vals)}}})",
            "        self.assertTrue(rec.exists())",
        ]
    for a in access:
        n += 1
        model = a.model.removeprefix("model_")
        body += [
            "",
            f"    def test_{a.id}(self):",
            f"        group = self.env.ref('{tech}.{a.group}')",
            f"        user = self.env['res.users'].with_context(no_reset_password=True).create("
            f"{{'name': 'T', 'login': 't_{a.id}'}})",
            "        user.write({'group_ids' if 'group_ids' in user._fields else 'groups_id': "
            "[(4, group.id)]})",
            f"        model = self.env[{model!r}].with_user(user)",
        ]
        for op, perm in (
            ("read", a.perm_read),
            ("write", a.perm_write),
            ("create", a.perm_create),
            ("unlink", a.perm_unlink),
        ):
            body.append(
                f"        self.assertEqual(model.has_access({op!r}) if hasattr(model, "
                f"'has_access') else model.check_access_rights({op!r}, raise_exception=False), "
                f"{bool(perm)})"
            )
    if not n:
        return []
    return [
        {"path": "tests/__init__.py", "content": f"from . import test_{tech}\n"},
        {"path": f"tests/test_{tech}.py", "content": "\n".join(body) + "\n"},
    ]
