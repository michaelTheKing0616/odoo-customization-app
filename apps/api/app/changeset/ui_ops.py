"""UI-family inherit checks and the public ORM payload for the executor.

``_view_issues`` still owns the view-inherit anchor count and the blanket
ban on ``position=replace``. This module adds RT-22 (an XPath that replaces
the root or a large subtree), the same one-anchor rule for
``report.inherit``, and the create/write values the existing change-set
dispatcher sends. It does not call Odoo.
"""

from __future__ import annotations

import re
from typing import Any

XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE = "xpath replaces the root or a large subtree"

_INHERIT_OPS = frozenset({"view.inherit.create", "view.inherit.update", "report.inherit"})

# View roots and the containers that hold most of a form or QWeb page.
_ROOT_OR_LARGE_NODES = frozenset(
    {
        "form",
        "tree",
        "list",
        "kanban",
        "search",
        "calendar",
        "graph",
        "pivot",
        "activity",
        "map",
        "gantt",
        "cohort",
        "grid",
        "qweb",
        "template",
        "templates",
        "t",
        "sheet",
        "notebook",
    }
)
# An unpredicated replace of these nodes hits many nodes at once.
_WIDE_NODES = frozenset({"div", "field", "group", "table", "span", "tr", "td", "tbody", "thead", "arch"})
_WILD_EXPRS = frozenset({"/", "/*", "//", "//*", ".", "//."})

_XPATH_TAG = re.compile(r"<xpath\b([^>]*)>", re.IGNORECASE)
_ATTR = re.compile(r"""\b(expr|position)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)
_TEMPLATE_ROOT = re.compile(
    r"^(?:/|//)t(?:\[@t-(?:name|call)=(['\"])[^'\"]+\1\])?$"
)
_TEMPLATES_ROOT = re.compile(
    r"^//templates(?:/t(?:\[@t-name=(['\"])[^'\"]+\1\])?)?$"
)
_PAGE_OR_ARTICLE = re.compile(
    r"^//div\[(?:"
    r"@class=(['\"])(?:page|article)\1"
    r"|contains\(@class,(['\"])(?:page|article)\2\)"
    r")\]$"
)


def _norm_expr(expr: str) -> str:
    return "".join(expr.split())


def _strip_first_predicate(expr: str) -> str:
    if expr.endswith("[1]"):
        return expr[:-3]
    return expr


def is_root_or_large_expr(expr: str) -> bool:
    """True when ``expr`` selects the document root or a large subtree.

    Inputs: an XPath expression string.
    Outputs: True for ``/``, wildcards, a view root (``//form``, ``//list``,
    ``//t[@t-name=...]``), or a large container (``//sheet``, ``//notebook``,
    the report page or article div). A field or span with a predicate is False.
    Side effects: none.
    """
    norm = _strip_first_predicate(_norm_expr(expr))
    if not norm or norm in _WILD_EXPRS:
        return bool(norm)
    if _TEMPLATE_ROOT.match(norm) or _TEMPLATES_ROOT.match(norm) or _PAGE_OR_ARTICLE.match(norm):
        return True
    body = norm[2:] if norm.startswith("//") else norm[1:] if norm.startswith("/") else ""
    if not body or body.startswith("/") or "[" in body:
        return False
    parts = body.split("/")
    if not parts or any(not part for part in parts):
        return False
    return all(part in _ROOT_OR_LARGE_NODES or part in _WIDE_NODES for part in parts)


def _is_replace(position: object) -> bool:
    return isinstance(position, str) and position.strip().lower() == "replace"


def _arch_pairs(arch: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in _XPATH_TAG.finditer(arch):
        attrs = {name.lower(): value for name, _quote, value in _ATTR.findall(match.group(1))}
        expr = attrs.get("expr")
        position = attrs.get("position")
        if expr and position:
            pairs.append((expr, position))
    return pairs


def _replace_exprs(params: dict[str, Any]) -> list[str]:
    exprs: list[str] = []
    position = params.get("position")
    if _is_replace(position):
        for key in ("xpath", "anchor"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                exprs.append(value)
    for key in ("arch", "arch_db"):
        raw = params.get(key)
        if isinstance(raw, str) and raw:
            exprs.extend(expr for expr, pos in _arch_pairs(raw) if _is_replace(pos))
    return exprs


def root_or_large_replace_issues(params: dict[str, Any]) -> list[str]:
    """RT-22 issues for one inherit op.

    Inputs: op params. A replace may be ``position`` plus ``xpath`` or
    ``anchor``, or an ``<xpath position="replace">`` inside ``arch`` or
    ``arch_db``.
    Outputs: one issue when any replace targets the root or a large subtree,
    otherwise an empty list.
    Side effects: none. Does not parse XML and does not call Odoo.
    """
    if any(is_root_or_large_expr(expr) for expr in _replace_exprs(params)):
        return [XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE]
    return []


def root_or_large_replace_reason(params: dict[str, Any]) -> str | None:
    """Refuse reason for RT-22, or None when the xpath is not that replace.

    Inputs: op params, same shape as ``root_or_large_replace_issues``.
    Outputs: the RT-22 message, or None.
    Side effects: none.
    """
    issues = root_or_large_replace_issues(params)
    return issues[0] if issues else None


def report_inherit_issues(params: dict[str, Any]) -> list[str]:
    """Preconditions for ``report.inherit``.

    Inputs: op params. An anchor is ``anchor`` or ``xpath``. ``expect_matches``
    defaults to 1, matching the view-inherit rule.
    Outputs: a missing-anchor issue, an expect-matches issue, and RT-22.
    A positioned replace of one small node is not an issue.
    Side effects: none.
    """
    issues: list[str] = []
    if not (params.get("anchor") or params.get("xpath")):
        issues.append("inherit requires an anchor")
    if params.get("expect_matches", 1) != 1:
        issues.append("anchor must match exactly one node")
    issues.extend(root_or_large_replace_issues(params))
    return issues


def inherit_op(op_type: str) -> bool:
    """True for the inherit ops that carry an XPath anchor.

    Inputs: catalog op type.
    Outputs: True for view inherit create/update and ``report.inherit``.
    Side effects: none.
    """
    return op_type in _INHERIT_OPS


UI_OP_TYPES: tuple[str, ...] = (
    "view.inherit.create",
    "view.inherit.update",
    "view.archive",
    "view.create_base",
    "action.window.create",
    "action.window.update",
    "menu.create",
    "menu.update",
    "menu.archive",
    "filter.create",
    "filter.update",
    "report.inherit",
    "report.action.create",
    "report.action.update",
)

_WRITE_OPS = frozenset(
    {
        "view.inherit.update",
        "view.archive",
        "action.window.update",
        "menu.update",
        "menu.archive",
        "filter.update",
        "report.action.update",
    }
)

_TARGET_MODELS: dict[str, str] = {
    "view.inherit.create": "ir.ui.view",
    "view.inherit.update": "ir.ui.view",
    "view.archive": "ir.ui.view",
    "view.create_base": "ir.ui.view",
    "action.window.create": "ir.actions.act_window",
    "action.window.update": "ir.actions.act_window",
    "menu.create": "ir.ui.menu",
    "menu.update": "ir.ui.menu",
    "menu.archive": "ir.ui.menu",
    "filter.create": "ir.filters",
    "filter.update": "ir.filters",
    "report.inherit": "ir.ui.view",
    "report.action.create": "ir.actions.report",
    "report.action.update": "ir.actions.report",
}


def ui_write_op(op_type: str) -> bool:
    """True when the op writes an existing row instead of creating one.

    Inputs: catalog op type.
    Outputs: True for the update and archive UI ops.
    Side effects: none.
    """
    return op_type in _WRITE_OPS


def ui_target_model(op_type: str) -> str:
    """Public ORM model the executor writes for one UI op.

    Inputs: catalog op type.
    Outputs: ``ir.ui.view``, ``ir.actions.act_window``, ``ir.ui.menu``,
    ``ir.filters``, or ``ir.actions.report``.
    Side effects: none.
    """
    return _TARGET_MODELS[op_type]


def ui_write_ids(params: dict[str, Any]) -> list[int]:
    """Read write ids from UI-op params.

    Inputs: op params. ``ids`` is a list of ints. ``id`` is one int. Bools
    are ignored.
    Outputs: the ids, or an empty list when none are usable.
    Side effects: none.
    """
    raw = params.get("ids")
    if isinstance(raw, list) and raw:
        ids: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int):
                return []
            ids.append(item)
        return ids
    item = params.get("id")
    if isinstance(item, bool) or not isinstance(item, int):
        return []
    return [item] if item else []


def ui_values(op_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Public ORM values for one UI-family op.

    Inputs: catalog type and resolved params.
    Outputs: a values dict the existing port can create or write. Archive
    ops write ``active`` false. Inherit create writes ``mode`` extension.
    Side effects: none. Does not call Odoo.
    """
    if op_type in {"view.archive", "menu.archive"}:
        return {"active": False}
    values: dict[str, Any] = {}
    name = params.get("name")
    if name:
        values["name"] = name
    model = params.get("model")
    if op_type.startswith("view.") or op_type == "report.inherit":
        if model:
            values["model"] = model
        if op_type in {"view.inherit.create", "report.inherit"}:
            values["mode"] = "extension"
            inherit_id = params.get("inherit_id")
            if inherit_id:
                values["inherit_id"] = inherit_id
        if op_type == "view.create_base":
            values["mode"] = "primary"
        if op_type == "report.inherit":
            values["type"] = "qweb"
        arch = _arch_for(op_type, params)
        if arch:
            values["arch"] = arch
    if op_type.startswith("action.window.") and model:
        values["res_model"] = model
    if op_type.startswith("filter.") and model:
        values["model_id"] = model
    if op_type.startswith("report.action.") and model:
        values["model"] = model
    if params.get("domain") is not None and op_type.startswith(("action.window.", "filter.")):
        values["domain"] = params["domain"]
    if not values:
        values["name"] = name or op_type
    return values


def _arch_for(op_type: str, params: dict[str, Any]) -> str | None:
    """Arch string for a view or report inherit, or None when unused.

    Inputs: op type and params. ``arch`` or ``arch_db`` wins. Inherit ops
    without one get a single xpath node from ``xpath`` or ``anchor``.
    Outputs: the arch, or None for ops that do not write arch.
    Side effects: none.
    """
    for key in ("arch", "arch_db"):
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw
    if op_type not in _INHERIT_OPS and op_type != "view.create_base":
        return None
    if op_type == "view.create_base":
        return None
    expr = params.get("xpath") or params.get("anchor")
    if not isinstance(expr, str) or not expr.strip():
        return None
    position = params.get("position") or "after"
    return f'<data><xpath expr="{expr}" position="{position}"/></data>'
