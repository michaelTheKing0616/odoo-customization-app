"""Op handlers. One handler per catalog type. R4 ops refuse. Unmapped Odoo writes fail closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.changeset.logic_ops import safe_eval_issues_in_params
from app.changeset.ops import OP_CATALOG
from app.changeset.protected_registry import protected_denial
from app.changeset.schema_ops import (
    CONSTRAINT_X_MODELS_ONLY,
    TYPE_CHANGE_UNSUPPORTED,
    constraint_sql_issues,
    field_update_issues,
    is_x_model,
    type_change_requested,
)
from app.changeset.ui_ops import (
    inherit_op,
    report_inherit_issues,
    root_or_large_replace_issues,
    root_or_large_replace_reason,
)

Issues = list[str]
IssueFn = Callable[[dict[str, Any]], Issues]


def _params(params: dict[str, Any] | None) -> dict[str, Any]:
    return params if isinstance(params, dict) else {}


def _need(params: dict[str, Any], *keys: str) -> Issues:
    missing = [key for key in keys if not params.get(key)]
    return [f"missing {key}" for key in missing]


def _field_issues(params: dict[str, Any]) -> Issues:
    issues = _need(params, "model", "name")
    name = str(params.get("name") or "")
    if name and (not name.startswith("x_") or name.startswith("x_studio_")):
        issues.append("field name must start with x_ and must not use the x_studio_ prefix")
    if len(name.encode("utf-8")) > 63:
        issues.append("field name exceeds 63 bytes")
    ttype = str(params.get("ttype") or params.get("field_type") or "char")
    if ttype == "monetary" and not params.get("currency_field"):
        issues.append("monetary field requires currency_field")
    if ttype == "many2one" and not params.get("relation"):
        issues.append("many2one field requires relation")
    if str(params.get("on_delete") or "") == "cascade":
        issues.append("on_delete cascade is forbidden")
    return issues


def _view_issues(params: dict[str, Any]) -> Issues:
    issues = _need(params, "model")
    anchor = params.get("anchor") or params.get("xpath")
    if not anchor:
        issues.append("view inherit requires an anchor")
    expect = params.get("expect_matches", 1)
    if expect != 1:
        issues.append("anchor must match exactly one node")
    if str(params.get("position") or "after") == "replace":
        issues.append("position replace is forbidden")
    return issues


def _view_inherit_issues(params: dict[str, Any]) -> Issues:
    """View-inherit preconditions plus an RT-22 issue when one applies.

    Inputs: op params. ``_view_issues`` still decides the anchor count and the
    blanket ``position=replace`` ban.
    Outputs: those issues, with the RT-22 message appended when the xpath
    replaces the root or a large subtree.
    Side effects: none.
    """
    issues = _view_issues(params)
    for item in root_or_large_replace_issues(params):
        if item not in issues:
            issues.append(item)
    return issues


def _access_issues(params: dict[str, Any]) -> Issues:
    issues = _need(params, "model")
    if not params.get("group"):
        issues.append("group-less access is forbidden")
    return issues


def _code_issues(params: dict[str, Any]) -> Issues:
    code = str(params.get("code") or "")
    if code:
        lowered = code.lower()
        for token in ("import ", "__import__", "sudo(", "eval(", "exec(", "commit(", "__class__"):
            if token in lowered or token in code:
                issues_token = token.strip()
                return [f"server action code contains forbidden token {issues_token}"]
    return safe_eval_issues_in_params(params)


def _sequence_issues(params: dict[str, Any]) -> Issues:
    if params.get("accounting") or params.get("legal"):
        return ["accounting or legal sequences are refused"]
    nxt = params.get("number_next")
    if isinstance(nxt, int) and nxt < 0:
        return ["number_next cannot be lowered"]
    return []


_ALWAYS_REFUSE = frozenset({"module.uninstall", "data.delete", "rpc.write"})

_INVERSE: dict[str, str] = {
    "field.create": "field.deprecate",
    "field.update": "field.update",
    "view.inherit.create": "view.archive",
    "view.inherit.update": "view.inherit.update",
    "view.create_base": "view.archive",
    "menu.create": "menu.archive",
    "menu.update": "menu.update",
    "automation.create": "automation.disable",
    "automation.update": "automation.update",
    "cron.create": "cron.disable",
    "cron.update": "cron.update",
    "mail_template.create": "mail_template.update",
    "mail_template.update": "mail_template.update",
    "filter.create": "filter.update",
    "filter.update": "filter.update",
    "stage.upsert": "stage.archive",
    "access.update": "access.update",
    "rule.update": "rule.update",
}

_ISSUE_FNS: dict[str, IssueFn] = {
    "field.create": _field_issues,
    "field.update": field_update_issues,
    "field.deprecate": lambda p: _need(p, "model", "name"),
    "field.delete": lambda p: _need(p, "model", "name"),
    "constraint.sql": constraint_sql_issues,
    "view.inherit.create": _view_inherit_issues,
    "view.inherit.update": _view_inherit_issues,
    "report.inherit": report_inherit_issues,
    "access.create": _access_issues,
    "access.update": _access_issues,
    "server_action.create": _code_issues,
    "server_action.update": _code_issues,
    "automation.create": safe_eval_issues_in_params,
    "automation.update": safe_eval_issues_in_params,
    "sequence.create": _sequence_issues,
    "sequence.update": _sequence_issues,
    "module.install": lambda p: _need(p, "module"),
    "module.upgrade": lambda p: _need(p, "module"),
    "data.update_batch": lambda p: _need(p, "model", "domain", "values") + (
        ["unbounded domain is forbidden"] if p.get("domain") == [] else []
    ),
    "data.unlink": lambda p: _need(p, "model", "ids"),
    "data.import_upsert": lambda p: _need(p, "model"),
    "rule.create": lambda p: _need(p, "model", "domain_force") + (
        ["group-less global rule needs an explicit global flag"] if not p.get("groups") and not p.get("global") else []
    ),
    "company.update": lambda p: ["lock dates are refused"] if p.get("lock_date") else [],
    "user.groups.assign": lambda p: ["admin group assignment is refused"] if p.get("admin") else _need(p, "user"),
    "config_param.set": lambda p: ["protected parameter"] if p.get("key") in {
        "database.secret",
        "database.uuid",
        "web.base.url",
        "database.enterprise_code",
    } else _need(p, "key"),
}


@dataclass(frozen=True, slots=True)
class OpHandler:
    op_type: str

    def issues(self, params: dict[str, Any] | None) -> Issues:
        fn = _ISSUE_FNS.get(self.op_type)
        if fn is None:
            return []
        return fn(_params(params))

    def refuse_reason(
        self,
        params: dict[str, Any] | None,
        tenant: dict[str, Any] | None = None,
        document: list[dict[str, Any]] | None = None,
    ) -> str | None:
        if self.op_type in _ALWAYS_REFUSE:
            return f"{self.op_type} is prohibited"
        entry = OP_CATALOG.get(self.op_type)
        if entry is not None and entry.risk_base == "R4":
            return f"{self.op_type} is prohibited"
        body = _params(params)
        if self.op_type == "company.update" and body.get("lock_date"):
            return "lock dates are prohibited"
        if self.op_type == "user.groups.assign" and body.get("admin"):
            return "admin group assignment is prohibited"
        if self.op_type.startswith("sequence.") and (body.get("accounting") or body.get("legal")):
            return "accounting sequences are prohibited"
        if self.op_type in {"access.create", "access.update"} and not body.get("group"):
            return "group-less access is forbidden"
        if self.op_type == "config_param.set" and body.get("key") in {
            "database.secret",
            "database.uuid",
            "web.base.url",
            "database.enterprise_code",
        }:
            return "protected parameter"
        if self.op_type == "field.update" and type_change_requested(body):
            return TYPE_CHANGE_UNSUPPORTED
        if self.op_type == "constraint.sql" and not is_x_model(str(body.get("model") or "")):
            return CONSTRAINT_X_MODELS_ONLY
        if inherit_op(self.op_type):
            replaced = root_or_large_replace_reason(body)
            if replaced:
                return replaced
        op = {"type": self.op_type, "params": body}
        if protected_denial(op, tenant=tenant, document=document if document is not None else [op]):
            return "protected_deny"
        return None

    def describe(self, params: dict[str, Any] | None) -> str:
        body = _params(params)
        target = body.get("model") or body.get("module") or body.get("name") or ""
        entry = OP_CATALOG[self.op_type]
        return (
            f"{self.op_type} on {target}: risk {entry.risk_base}, "
            f"reversible {entry.reversible}, ddl {entry.ddl}"
        )

    def inverse(
        self,
        params: dict[str, Any] | None,
        document: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if self.refuse_reason(params, document=document) is not None:
            return None
        entry = OP_CATALOG[self.op_type]
        if entry.reversible == "N":
            return None
        inverse_type = _INVERSE.get(self.op_type)
        if inverse_type is None:
            return None
        return {"type": inverse_type, "params": dict(_params(params)), "inverse_of": self.op_type}

    def memory_key(self, params: dict[str, Any] | None) -> str:
        body = _params(params)
        return f"{self.op_type}:{body.get('model', '')}:{body.get('name', body.get('module', ''))}"


def handler_for(op_type: str) -> OpHandler:
    if op_type not in OP_CATALOG:
        raise KeyError(op_type)
    return OpHandler(op_type)


def all_handlers() -> dict[str, OpHandler]:
    return {op_type: OpHandler(op_type) for op_type in OP_CATALOG}


def apply_memory(store: dict[str, dict[str, Any]], op: dict[str, Any]) -> None:
    """Record a validated op. Refused ops raise and do not write."""
    op_type = str(op.get("type") or "")
    handler = handler_for(op_type)
    params = op.get("params") if isinstance(op.get("params"), dict) else {}
    reason = handler.refuse_reason(params)
    if reason:
        raise PermissionError(reason)
    issues = handler.issues(params)
    if issues:
        raise ValueError("; ".join(issues))
    store[handler.memory_key(params)] = {"type": op_type, "params": dict(params)}


def compensate_memory(store: dict[str, dict[str, Any]], op: dict[str, Any]) -> None:
    op_type = str(op.get("type") or "")
    handler = handler_for(op_type)
    params = op.get("params") if isinstance(op.get("params"), dict) else {}
    inverse = handler.inverse(params)
    if inverse is None:
        raise PermissionError(f"{op_type} has no inverse")
    store.pop(handler.memory_key(params), None)
