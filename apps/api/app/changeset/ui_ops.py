"""UI-family inherit checks that the view handler does not already enforce.

``_view_issues`` still owns the view-inherit anchor count and the blanket
ban on ``position=replace``. This module adds RT-22 (an XPath that replaces
the root or a large subtree) and the same one-anchor rule for
``report.inherit``. It does not call Odoo.
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
