"""Upgrade-safe Odoo inherit locators — prefer named attrs over positional [n].

Clean-room helper. ElementTree xpath is a subset of Odoo/lxml; unsupported
predicates return match_count=None (warning), never a false missing-node error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal
from xml.etree.ElementTree import Element, ParseError, fromstring, tostring

Severity = Literal["error", "warning"]

POSITIONAL_RE = re.compile(r"\[\s*(?:\d+|last\(\)|last\(\)\s*-\s*\d+)\s*\]")
NAME_OR_ID_RE = re.compile(r"\[@(?:name|id)\s*=")
STRING_RE = re.compile(r"\[@string\s*=")
STABLE_ROOTS = frozenset({"//sheet", "//form", "//list", "//tree", "//search", "//kanban"})

BLOCKING_CODES = frozenset(
    {
        "invalid_xml",
        "invalid_body_xml",
        "missing_expr",
        "empty_body",
        "missing_node",
        "ambiguous_match",
    }
)


@dataclass(frozen=True)
class LocatorIssue:
    severity: Severity
    code: str
    message: str
    expr: str | None = None
    suggestion: str | None = None

    def as_text(self) -> str:
        if self.suggestion:
            return f"{self.message} Suggestion: {self.suggestion}"
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "expr": self.expr,
            "suggestion": self.suggestion,
        }


@dataclass
class FieldLocatorCandidate:
    xpath: str
    match: str = ""
    score: int = 0
    fragile: bool = False
    match_count: int | None = None
    order: int = 0


def is_positional(expr: str) -> bool:
    return bool(POSITIONAL_RE.search(expr or ""))


def is_fragile(expr: str) -> bool:
    raw = (expr or "").strip()
    if not raw:
        return True
    if is_positional(raw):
        return True
    if STRING_RE.search(raw) and not NAME_OR_ID_RE.search(raw):
        return True
    return False


def score_locator(expr: str) -> int:
    """Higher is more upgrade-safe."""
    raw = (expr or "").strip()
    if not raw:
        return 0
    score = 10
    if NAME_OR_ID_RE.search(raw):
        score += 50
    if "field[@name=" in raw.replace('"', "'"):
        score += 10
    if STRING_RE.search(raw):
        score += 5
    if raw in STABLE_ROOTS:
        score += 25
    if is_positional(raw):
        score -= 45
    if re.search(r"/(?:group|page|div|field|sheet)\[\d+\]", raw):
        score -= 8
    return score


def _to_etree_path(expr: str) -> str:
    """Map Odoo inherit locators onto ElementTree.

    Odoo xpath inherits use document-rooted ``//field``. ElementTree
    rejects absolute paths on an element (``cannot use absolute path``),
    so evaluation uses ``.//field``. Generated inherit XML still emits
    the Odoo ``//`` form — this helper is eval-only.
    """
    q = (expr or "").strip()
    if q.startswith("//"):
        return "." + q
    return q


def _findall(root: Element, expr: str) -> list[Element] | None:
    q = _to_etree_path(expr)
    if not q:
        return []
    try:
        return list(root.findall(q))
    except (SyntaxError, Exception):  # noqa: BLE001
        return None


def count_xpath_matches(parent_arch: str, expr: str) -> int | None:
    """Return hit count, or None when the expr is outside ElementTree xpath."""
    tree = _parse_root(parent_arch)
    if tree is None:
        return None
    query = (expr or "").strip()
    if not query:
        return 0
    nodes = _findall(tree, query)
    if nodes is None:
        return None
    return len(nodes)


def rewrite_locator(expr: str, parent_arch: str | None) -> str:
    """Rewrite positional / weak locators toward named attrs when a unique node exists."""
    raw = (expr or "").strip()
    if not raw or not parent_arch:
        return raw
    tree = _parse_root(parent_arch)
    if tree is None:
        return raw
    hits = _findall(tree, raw)
    if hits is None or len(hits) != 1:
        return raw
    semantic = semantic_xpath_for_element(tree, hits[0])
    if not semantic:
        return raw
    if score_locator(semantic) >= score_locator(raw):
        return semantic
    return raw


def semantic_inject_expr(parent_arch: str | None, view_type: str = "form") -> str:
    """Stable inside-target for create-field inherit inject."""
    vt = "list" if view_type == "tree" else view_type
    if vt == "list":
        if parent_arch and "<tree" in parent_arch and "<list" not in parent_arch:
            return "//tree"
        return "//list"
    if vt == "search":
        return "//search"
    if vt != "form":
        return f"//{vt}"
    if not parent_arch:
        return "//sheet"
    tree = _parse_root(parent_arch)
    if tree is None:
        if "<sheet" in parent_arch:
            return "//sheet"
        return "//form"
    groups = [el for el in tree.iter() if el.tag == "group"]
    if groups:
        named = _unique_named_xpath(tree, groups[0], ("name", "id", "string"))
        if named:
            return named
        if len(groups) == 1:
            return "//group"
    if any(el.tag == "sheet" for el in tree.iter()):
        return "//sheet"
    return "//form"


def semantic_field_candidates(parent_arch: str, field_name: str) -> list[FieldLocatorCandidate]:
    """Ranked locators for every <field name=field_name> in parent arch."""
    name = (field_name or "").strip()
    tree = _parse_root(parent_arch)
    if not name or tree is None:
        fallback = f"//field[@name='{_esc(name)}']" if name else ""
        return (
            [
                FieldLocatorCandidate(
                    xpath=fallback,
                    score=score_locator(fallback),
                    fragile=is_fragile(fallback),
                    match_count=None,
                )
            ]
            if fallback
            else []
        )
    out: list[FieldLocatorCandidate] = []
    seen: set[str] = set()
    for order, el in enumerate(tree.iter()):
        if el.tag != "field" or (el.get("name") or "") != name:
            continue
        xpath = semantic_xpath_for_element(tree, el) or f"//field[@name='{_esc(name)}']"
        if xpath in seen:
            continue
        seen.add(xpath)
        count = count_xpath_matches(parent_arch, xpath)
        out.append(
            FieldLocatorCandidate(
                xpath=xpath,
                match=_snippet(el),
                score=score_locator(xpath),
                fragile=is_fragile(xpath) or (count is not None and count != 1),
                match_count=count,
                order=order,
            )
        )
    out.sort(key=lambda c: (-c.score, c.order, len(c.xpath)))
    if not out:
        xpath = f"//field[@name='{_esc(name)}']"
        out.append(
            FieldLocatorCandidate(
                xpath=xpath,
                score=score_locator(xpath),
                fragile=True,
                match_count=0,
            )
        )
    return out


def semantic_xpath_for_element(root: Element, el: Element) -> str | None:
    tag = el.tag if isinstance(el.tag, str) else "node"
    name = el.get("name")
    if name:
        simple = f"//{tag}[@name='{_esc(name)}']"
        if _unique(root, simple):
            return simple
        for anc in _ancestors(root, el):
            for attr in ("name", "id"):
                aval = anc.get(attr)
                if not aval:
                    continue
                cand = f"//{anc.tag}[@{attr}='{_esc(aval)}']//{tag}[@name='{_esc(name)}']"
                if _unique(root, cand):
                    return cand
            sval = anc.get("string")
            if sval and "'" not in sval:
                cand = f"//{anc.tag}[@string='{_esc(sval)}']//{tag}[@name='{_esc(name)}']"
                if _unique(root, cand):
                    return cand
        return simple
    named = _unique_named_xpath(root, el, ("name", "id", "string"))
    if named:
        return named
    return None


def classify_locator(
    expr: str,
    *,
    parent_arch: str | None = None,
    body_xml: str | None = None,
    position: str = "inside",
) -> list[LocatorIssue]:
    issues: list[LocatorIssue] = []
    raw = (expr or "").strip()
    if not raw:
        issues.append(
            LocatorIssue("error", "missing_expr", "xpath expr is required", expr=expr)
        )
        return issues

    suggestion = rewrite_locator(raw, parent_arch) if parent_arch else raw
    if suggestion == raw:
        suggestion = None
    else:
        suggestion = suggestion

    if is_positional(raw):
        issues.append(
            LocatorIssue(
                "warning",
                "positional_fragility",
                "Positional predicate ([n] / last()) breaks when the parent view is upgraded.",
                expr=raw,
                suggestion=suggestion,
            )
        )
    elif STRING_RE.search(raw) and not NAME_OR_ID_RE.search(raw):
        issues.append(
            LocatorIssue(
                "warning",
                "string_attr_fragility",
                "Locator keys off @string, which translations and label edits can change.",
                expr=raw,
                suggestion=suggestion,
            )
        )

    if body_xml is not None and position != "move":
        body = body_xml.strip()
        if not body:
            issues.append(
                LocatorIssue(
                    "error",
                    "empty_body",
                    "xpath body is empty",
                    expr=raw,
                )
            )
        else:
            try:
                fromstring(f"<wrap>{body}</wrap>")
            except ParseError as exc:
                issues.append(
                    LocatorIssue(
                        "error",
                        "invalid_body_xml",
                        f"Invalid XML body: {exc}",
                        expr=raw,
                    )
                )

    if not parent_arch:
        return issues

    count = count_xpath_matches(parent_arch, raw)
    if count is None:
        issues.append(
            LocatorIssue(
                "warning",
                "unsupported_xpath",
                "This expr uses xpath that we cannot evaluate locally (Odoo still might).",
                expr=raw,
                suggestion=suggestion,
            )
        )
        return issues
    if count == 0:
        issues.append(
            LocatorIssue(
                "error",
                "missing_node",
                f"Locator matches no node in the parent view ({raw}).",
                expr=raw,
                suggestion=suggestion,
            )
        )
    elif count > 1:
        issues.append(
            LocatorIssue(
                "error",
                "ambiguous_match",
                f"Locator matches {count} nodes — Odoo inherit requires exactly one.",
                expr=raw,
                suggestion=suggestion,
            )
        )
    return issues


def classify_xpath_arch(arch: str, *, parent_arch: str | None = None) -> list[LocatorIssue]:
    issues: list[LocatorIssue] = []
    try:
        root = fromstring(arch)
    except ParseError as exc:
        return [LocatorIssue("error", "invalid_xml", f"Invalid XML: {exc}")]
    if root.tag not in {"data", "xpath"}:
        issues.append(
            LocatorIssue(
                "warning",
                "unexpected_root",
                f"Root should be <data> or <xpath>, got <{root.tag}>",
            )
        )
    xpaths = (
        root.findall(".//xpath")
        if root.tag == "data"
        else ([root] if root.tag == "xpath" else [])
    )
    if not xpaths:
        issues.append(LocatorIssue("error", "missing_expr", "No <xpath> elements found"))
        return issues
    for xp in xpaths:
        expr = (xp.get("expr") or "").strip()
        pos = xp.get("position") or "inside"
        if pos not in {"inside", "after", "before", "replace", "attributes", "move"}:
            issues.append(
                LocatorIssue(
                    "warning",
                    "unusual_position",
                    f"Unusual xpath position={pos!r}",
                    expr=expr or None,
                )
            )
        inner = "".join(tostring(child, encoding="unicode") for child in list(xp))
        text = (xp.text or "").strip()
        body = (inner + text).strip()
        body_arg = None if pos == "move" else (body or "")
        issues.extend(
            classify_locator(expr, parent_arch=parent_arch, body_xml=body_arg, position=pos)
        )
    return _dedupe_issues(issues)


def looks_like_xpath_inherit(arch: str) -> bool:
    s = (arch or "").lstrip()
    if s.startswith("<?xml"):
        s = "\n".join(s.splitlines()[1:]).lstrip()
    return s.startswith("<data") or s.startswith("<xpath")


def blocking_issues(issues: list[LocatorIssue]) -> list[LocatorIssue]:
    return [i for i in issues if i.severity == "error" and i.code in BLOCKING_CODES]


def suggested_expr_from_issues(issues: list[LocatorIssue], current: str) -> str | None:
    for item in issues:
        if item.suggestion and item.suggestion != current:
            return item.suggestion
    return None


def _parse_root(arch: str) -> Element | None:
    cleaned = (arch or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("<?xml"):
        cleaned = "\n".join(cleaned.splitlines()[1:]).strip()
    try:
        return fromstring(cleaned)
    except ParseError:
        return None


def _esc(value: str) -> str:
    return value or ""


def _unique(root: Element, expr: str) -> bool:
    nodes = _findall(root, expr)
    return nodes is not None and len(nodes) == 1


def _unique_named_xpath(root: Element, el: Element, attrs: tuple[str, ...]) -> str | None:
    tag = el.tag if isinstance(el.tag, str) else "node"
    for attr in attrs:
        val = el.get(attr)
        if not val or "'" in val:
            continue
        expr = f"//{tag}[@{attr}='{_esc(val)}']"
        if _unique(root, expr):
            return expr
    return None


def _ancestors(root: Element, el: Element) -> list[Element]:
    parents = _parent_map(root)
    out: list[Element] = []
    cur = parents.get(el)
    while cur is not None:
        out.append(cur)
        cur = parents.get(cur)
    return out


def _parent_map(root: Element) -> dict[Element, Element]:
    mapping: dict[Element, Element] = {}
    for parent in root.iter():
        for child in list(parent):
            mapping[child] = parent
    return mapping


def _snippet(el: Element) -> str:
    raw = tostring(el, encoding="unicode")
    return raw[:240]


def _dedupe_issues(issues: list[LocatorIssue]) -> list[LocatorIssue]:
    seen: set[tuple[str, str | None, str]] = set()
    out: list[LocatorIssue] = []
    for item in issues:
        key = (item.code, item.expr, item.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
