"""Deny-by-default policy for module data on the security core.

Any data record (XML <record>, CSV row, JSON/YAML data) or Python create/write that
touches a sensitive model or field is a HIGH "needs L3 approval" finding, unless the
record is in one of the narrow allow shapes below. Each allow shape is tested in
tests/test_nf_bot_code_audit_6.py. Shape-by-shape deny lists elsewhere still add
their specific explanation; this policy is the floor that catches everything else.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Callable

# Models whose records change who can do what, what code runs, or what the browser loads.
SENSITIVE_MODELS: frozenset[str] = frozenset(
    {
        "res.users",
        "res.users.apikeys",
        "res.users.settings",
        "auth.totp.device",
        "res.groups",
        "ir.model.access",
        "ir.rule",
        "ir.config_parameter",
        "ir.cron",
        "ir.actions.server",
        "ir.server.object.lines",
        "base.automation",
        "ir.mail_server",
        "fetchmail.server",
        "mail.alias",
        "ir.http",
        "ir.module.module",
        "ir.model.data",
        "ir.model",
        "ir.model.fields",
        "ir.default",
        "ir.actions.act_url",
        "ir.actions.report",
        "ir.asset",
        "ir.attachment",
        "ir.ui.view",
        "website",
        "website.rewrite",
        "website.menu",
        "website.page",
        "mail.template",
        "res.company",
    }
)

# Fields that are sensitive on any model (stored web content, privilege and code fields).
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "custom_code_head",
        "custom_code_footer",
        "custom_code_body",
        "alias_defaults",
        "groups_id",
        "group_ids",
        "implied_ids",
        "password",
        "new_password",
        "code",
        "compute",
        "domain_force",
        "url_to",
        "url_from",
        "smtp_host",
        "webhook_url",
        "json_value",
    }
)

# Models where the sensitive-field rule applies even when the model itself is ordinary.
_FIELD_ANY_MODEL = frozenset({"custom_code_head", "custom_code_footer", "custom_code_body", "alias_defaults"})

_PUBLIC = re.compile(r"\bgroup_(?:public|portal)\b")
_ADMIN = re.compile(r"\bbase\.group_(?:system|erp_manager|no_one)\b|\bgroup_system\b")
_SCRIPT = re.compile(
    r"<\s*(?:script|iframe|object|embed|link|meta|base)\b|\bon[a-z]+\s*=|javascript\s*:|data\s*:\s*text/html|"
    r"\bt-raw\b|\bt-out\s*=\s*['\"][^'\"]*\bMarkup\b|srcdoc",
    re.I,
)
_SAFE_REPORT_EXPR = re.compile(r"""^[\w\s.'"%()+,/:-]*$""")
_REPORT_BAD = re.compile(r"\b(?:env|sudo|eval|exec|__\w+__|import|request|cr|pool|write|create|unlink)\b")
_SINGLE_CALL = re.compile(r"^\s*(?:action\s*=\s*)?(?:model|records|record)\.(_?[a-z]\w*)\(\s*\)\s*$")
_WRITE_METHODS = re.compile(
    r"^(?:write|create|unlink|sudo|with_user|copy|set_param|toggle_active|action_archive|"
    r"action_unarchive|button_\w+|_set_password|method_direct_trigger|run)$"
)
_SECURITY_VIEWS = re.compile(
    r"\bbase\.(?:view_users_\w+|view_groups_\w+|view_res_users\w*|ir_access_view_\w+|view_rule_\w+|"
    r"view_server_action_\w+|ir_cron_view\w*|view_ir_config\w*|res_users_view\w*)\b"
)
_PRIV_KEYS = re.compile(r"\b(?:groups_id|group_ids|implied_ids|share|active|password|login|company_ids|sel_groups_\w+|in_group_\w+)\b")


def own_ref(ref: str, module: str) -> bool:
    ref = (ref or "").strip()
    if not ref:
        return False
    return "." not in ref or ref.split(".", 1)[0] == module


def _own_model_ref(ref: str, module: str) -> bool:
    """model_id refs: own module, and the target is a module model (model_x_..., not a core
    one); or search="[('model','=','x_...')]" naming a manual x_ model."""
    m = re.fullmatch(r"\s*\[\s*\(\s*'model'\s*,\s*'='\s*,\s*'(x_[\w.]+)'\s*\)\s*\]\s*", ref or "")
    if m:
        return True
    return own_ref(ref, module) and ref.split(".")[-1].startswith("model_")


def _literal(text: str):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return _UNPARSED


_UNPARSED = object()


def _relative_url(u: str) -> bool:
    u = (u or "").strip()
    return u.startswith("/") and not u.startswith("//") and not re.search(r"[\\\s]|javascript:|data:", u, re.I)


def _simple_server_code(v: dict[str, str]) -> bool:
    """Approved server-code shapes: one non-write method call on model/records, or a
    `for rec in records:` loop that only sets x_ fields to literals and posts a literal
    chatter message (what req2mod generates)."""
    code = (v.get("code") or "").strip()
    lines = [ln for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(lines) == 1:
        m = _SINGLE_CALL.match(lines[0])
        if m and not _WRITE_METHODS.match(m.group(1)):
            return True
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.For):
        return False
    loop = tree.body[0]
    if not (
        isinstance(loop.target, ast.Name)
        and isinstance(loop.iter, ast.Name)
        and loop.iter.id == "records"
        and not loop.orelse
    ):
        return False
    var = loop.target.id

    def lit(n: ast.AST) -> bool:
        return _literal(ast.unparse(n)) is not _UNPARSED

    for st in loop.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and lit(st.value):
            t = st.targets[0]
            if (
                isinstance(t, ast.Subscript)
                and isinstance(t.value, ast.Name)
                and t.value.id == var
                and isinstance(t.slice, ast.Constant)
                and str(t.slice.value).startswith("x_")
            ):
                continue
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == var and t.attr.startswith("x_"):
                continue
            return False
        if (
            isinstance(st, ast.Expr)
            and isinstance(st.value, ast.Call)
            and isinstance(st.value.func, ast.Attribute)
            and isinstance(st.value.func.value, ast.Name)
            and st.value.func.value.id == var
            and st.value.func.attr == "message_post"
            and not st.value.args
            and all(k.arg in ("body", "subject") and lit(k.value) for k in st.value.keywords)
        ):
            continue
        return False
    return True


def _allow(model: str, v: dict[str, str], module: str, rid: str) -> str:
    """Return the allow shape name, or "" when the record needs L3 approval."""
    own_id = own_ref(rid, module) if rid else True
    mid = v.get("model_id", "")
    if model == "ir.model.access":
        g = v.get("group_id", "")
        if not own_id or not _own_model_ref(mid, module):
            return ""
        if g and _PUBLIC.search(g):
            return ""
        if not g and any(v.get(p) in ("1", "True", "true") for p in ("perm_write", "perm_create", "perm_unlink")):
            return ""
        return "own-model-access"
    if model == "ir.rule":
        dom = v.get("domain_force", "")
        if own_id and _own_model_ref(mid, module) and dom and not re.fullmatch(
            r"\s*\[\s*(?:\(\s*1\s*,\s*['\"]=['\"]\s*,\s*1\s*\)\s*,?\s*)?\]\s*", dom
        ) and "__" not in dom:
            return "own-model-rule"
        return ""
    if model == "res.groups":
        if not own_id:
            return ""
        if any(k in v for k in ("users", "user_ids")):
            return ""
        if _ADMIN.search(v.get("implied_ids", "")):
            return ""
        return "own-group"
    if model in ("ir.cron", "ir.actions.server", "base.automation"):
        if model == "base.automation":
            acts = v.get("action_server_ids", "")
            refs = re.findall(r"ref\(\s*['\"]([\w.]+)['\"]\s*\)", acts)
            if (
                own_id
                and _own_model_ref(mid, module)
                and refs
                and all(own_ref(r, module) for r in refs)
                and not re.sub(r"\(\s*[46]\s*,\s*ref\(\s*['\"][\w.]+['\"]\s*\)\s*\)|[\[\],\s]", "", acts)
                and v.get("trigger", "") in ("on_create", "on_write", "on_create_or_write", "on_change", "on_unlink", "on_time", "on_stage_set", "on_state_set", "on_priority_set", "on_tag_set", "on_user_set")
                and "__" not in v.get("filter_domain", "") + v.get("filter_pre_domain", "")
                and not v.get("code")
            ):
                return "own-model-automation"
            return ""
        if own_id and _own_model_ref(mid, module) and v.get("state", "code") == "code" and _simple_server_code(v):
            if model == "ir.actions.server" and v.get("child_ids"):
                return ""
            return "own-model-single-method"
        if model == "ir.actions.server" and v.get("state") in ("object_write", "object_create") and own_id and _own_model_ref(mid, module):
            return "own-model-field-update"
        return ""
    if model == "ir.ui.view":
        arch = " ".join(v.get(k, "") for k in ("arch", "arch_db", "arch_base"))
        inh = v.get("inherit_id", "")
        if _SCRIPT.search(arch) or _SECURITY_VIEWS.search(inh):
            return ""
        if _PUBLIC.search(arch) and re.search(r"groups_id|group_ids|implied_ids|password", arch):
            return ""
        if v.get("type", "").strip() == "qweb" and re.search(r"\bt-(?:raw|out)\b", arch) and not own_id:
            return ""
        return "inert-view"
    if model == "ir.actions.report":
        for k in ("print_report_name", "attachment"):
            x = v.get(k, "")
            if x and (not _SAFE_REPORT_EXPR.match(x) or _REPORT_BAD.search(x)):
                return ""
        return "plain-report"
    if model == "ir.attachment":
        if v.get("public") in ("1", "True", "true"):
            return ""
        name = v.get("name", "") + " " + v.get("mimetype", "")
        if re.search(r"javascript|ecmascript|html|svg|xml|\.m?js\b|\.htm", name, re.I):
            return ""
        if _SCRIPT.search(v.get("raw", "")):
            return ""
        return "private-inert-attachment"
    if model == "ir.model.fields":
        if v.get("compute") or v.get("related") or v.get("depends"):
            return ""
        return "plain-manual-field" if own_id else ""
    if model == "ir.model":
        return "manual-model" if (v.get("model", "").startswith("x_") and own_id) else ""
    if model == "ir.default":
        fid = v.get("field_id", "")
        if re.search(r"field_(?:res_users|res_groups|ir_|res_company|auth_|mail_alias|website_)", fid):
            return ""
        jv = v.get("json_value", "")
        if jv:
            try:
                val = json.loads(jv)
            except ValueError:
                return ""
            if isinstance(val, (dict, list)) and _PRIV_KEYS.search(json.dumps(val)):
                return ""
        return "plain-default"
    if model == "ir.actions.act_url":
        return "relative-url" if _relative_url(v.get("url", "")) else ""
    if model == "website.menu":
        u = v.get("url", "")
        return "relative-menu" if (not u or _relative_url(u)) else ""
    if model == "website.page":
        return "inert-page" if not _SCRIPT.search(v.get("arch", "") + v.get("arch_db", "")) else ""
    if model == "ir.asset":
        p = v.get("path", "")
        return "own-static-asset" if (p.split("/", 1)[0].lstrip("/") == module and "://" not in p and not p.startswith("//")) else ""
    if model == "mail.template":
        body = v.get("body_html", "") + v.get("subject", "")
        return "inert-template" if not re.search(r"<\s*script|javascript\s*:|\bon[a-z]+\s*=", body, re.I) else ""
    if model == "mail.alias":
        d = v.get("alias_defaults", "")
        if d:
            lit = _literal(d)
            if lit is _UNPARSED or not isinstance(lit, dict) or _PRIV_KEYS.search(" ".join(map(str, lit))):
                return ""
        if re.search(r"model_res_(?:users|groups|company)\b", v.get("alias_model_id", "")):
            return ""
        return "plain-alias" if own_id else ""
    if model == "website":
        if any(v.get(k) for k in ("custom_code_head", "custom_code_footer", "custom_code_body")):
            return ""
        return "plain-website" if own_id else ""
    if model == "res.company":
        return "plain-company" if own_id and not (set(v) & {"user_ids", "parent_id"}) else ""
    # res.users, apikeys, totp, ir.config_parameter, ir.mail_server, fetchmail.server,
    # website.rewrite, ir.module.module, ir.model.data, ir.http, ir.server.object.lines:
    # no allow shape, always L3.
    return ""


def data_record_policy(
    add: Callable[..., None],
    sev_high: str,
    path: str,
    line: int,
    model: str,
    vals: dict[str, str],
    module: str,
) -> None:
    """Grade one data record (XML/CSV/JSON/YAML). vals maps field -> text/eval/ref."""
    v = {k.split("/")[0].split(":")[0]: (x or "").strip() for k, x in vals.items()}
    rid = (vals.get("id") or vals.get("__id__") or "").strip()
    hit_fields = sorted(k for k in v if k in _FIELD_ANY_MODEL and v[k])
    if model not in SENSITIVE_MODELS and not hit_fields:
        return
    if model in SENSITIVE_MODELS:
        shape = _allow(model, v, module, rid)
    else:  # an ordinary model carrying alias defaults / custom code: same field rules
        shape = (
            _allow("mail.alias", {"alias_defaults": v.get("alias_defaults", "")}, module, "")
            if hit_fields == ["alias_defaults"]
            else ""
        )
    if shape:
        return
    what = model + (f" ({', '.join(hit_fields)})" if hit_fields else "")
    add(
        sev_high,
        "sensitive-data-unapproved",
        path,
        line,
        f"Data record {rid or ''} on {what} touches the security core / stored web content"
        " and matches no approved shape: needs L3 approval.",
        "Use an approved shape (own-model access/rule, own group, single-method cron on an own"
        " model, inert view, relative URL) or get L3 approval for this record.",
    )


def python_write_needs_l3(model: str) -> bool:
    return model in SENSITIVE_MODELS


def records_from_structured(obj, depth: int = 0):
    """Yield (model, vals) for dicts that look like data records in JSON/YAML."""
    if depth > 40:
        yield ("__too_deep__", {})
        return
    if isinstance(obj, dict):
        m = obj.get("model") or obj.get("_model")
        if isinstance(m, str):
            vals = obj.get("values") or obj.get("vals") or obj.get("fields") or {
                k: x for k, x in obj.items() if k not in ("model", "_model")
            }
            if isinstance(vals, dict):
                yield (m, {str(k): (x if isinstance(x, str) else json.dumps(x, default=str)) for k, x in vals.items()} | (
                    {"id": str(obj["id"])} if isinstance(obj.get("id"), str) else {}
                ))
        elif any(k in _FIELD_ANY_MODEL for k in obj):
            yield ("", {str(k): (x if isinstance(x, str) else json.dumps(x, default=str)) for k, x in obj.items()})
        for x in obj.values():
            yield from records_from_structured(x, depth + 1)
    elif isinstance(obj, list):
        for x in obj:
            yield from records_from_structured(x, depth + 1)
