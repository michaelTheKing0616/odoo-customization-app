"""Live lint for runner scripts: unknown models/fields/methods, per-version deprecations, suggestions.

Static only (``ast``): the script is never executed here.
"""

from __future__ import annotations

import ast
import difflib
from typing import Any, Callable

from app.code_runner.schema import DEPRECATED, methods_for

FieldsFn = Callable[[str], "dict[str, Any] | None"]
_VALS_ARG = {"create": 0, "write": 1}  # position in args of the vals dict (create: vals or list of vals)


def _issue(node: ast.AST, severity: str, message: str, fix: str = "") -> dict[str, Any]:
    return {"line": getattr(node, "lineno", 1), "col": getattr(node, "col_offset", 0) + 1,
            "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            "end_col": getattr(node, "end_col_offset", 0) + 1, "severity": severity, "message": message, "fix": fix}


def _suggest(word: str, pool: list[str]) -> str:
    hit = difflib.get_close_matches(word, pool, n=1, cutoff=0.6)
    return hit[0] if hit else ""


def _str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _domain_fields(node: ast.AST) -> list[tuple[ast.AST, str]]:
    out = []
    if isinstance(node, (ast.List, ast.Tuple)):
        for el in node.elts:
            if isinstance(el, (ast.List, ast.Tuple)) and len(el.elts) == 3 and _str(el.elts[0]):
                out.append((el.elts[0], _str(el.elts[0])))
            elif isinstance(el, (ast.List, ast.Tuple)):
                out += _domain_fields(el)
    return out


def _dict_keys(node: ast.AST) -> list[tuple[ast.AST, str]]:
    if isinstance(node, ast.Dict):
        return [(k, _str(k)) for k in node.keys if _str(k)]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [kv for el in node.elts for kv in _dict_keys(el)]
    return []


def lint(code: str, *, major: int, model_names: set[str], fields_of: FieldsFn) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError as exc:
        return [{"line": exc.lineno or 1, "col": exc.offset or 1, "end_line": exc.lineno or 1,
                 "end_col": (exc.offset or 1) + 1, "severity": "error",
                 "message": f"Python can't read this line: {exc.msg}", "fix": ""}]
    methods = methods_for(major)
    issues: list[dict[str, Any]] = []
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        f = call.func
        if not (isinstance(f, ast.Attribute) and f.attr == "execute_kw" and len(call.args) >= 2):
            continue
        model, method = _str(call.args[0]), _str(call.args[1])
        if model is None:
            continue
        if model_names and model not in model_names:
            s = _suggest(model, sorted(model_names))
            issues.append(_issue(call.args[0], "error", f"There is no model '{model}' on this database.", s))
            continue
        if method:
            if method in DEPRECATED and major >= DEPRECATED[method][0]:
                _, msg, repl = DEPRECATED[method]
                issues.append(_issue(call.args[1], "warning", f"{msg}; use {repl}.", repl.split("(")[0]))
            elif method not in methods and not method.startswith(("action_", "button_")):
                if method.startswith("_"):
                    issues.append(_issue(call.args[1], "error", "Private methods (starting with _) can't be called over RPC."))
                else:
                    issues.append(_issue(call.args[1], "info", f"'{method}' isn't a standard ORM method; it must be a public method of {model}.",
                                         _suggest(method, list(methods))))
        flds = fields_of(model) or {}
        if not flds:
            continue
        names = sorted(flds)
        found: list[tuple[ast.AST, str]] = []
        args = call.args[2] if len(call.args) > 2 else None
        kw = call.args[3] if len(call.args) > 3 else None
        if isinstance(args, (ast.List, ast.Tuple)) and args.elts:
            if method in {"search", "search_read", "search_count", "read_group", "formatted_read_group", "web_search_read"}:
                found += _domain_fields(args.elts[0])
            if method in _VALS_ARG and len(args.elts) > _VALS_ARG[method]:
                found += _dict_keys(args.elts[_VALS_ARG[method]])
            if method == "read" and len(args.elts) > 1 and isinstance(args.elts[1], ast.List):
                found += [(e, _str(e)) for e in args.elts[1].elts if _str(e)]
        if isinstance(kw, ast.Dict):
            for k, v in zip(kw.keys, kw.values):
                if _str(k) == "fields" and isinstance(v, ast.List):
                    found += [(e, _str(e)) for e in v.elts if _str(e)]
                if _str(k) == "domain":
                    found += _domain_fields(v)
        for node, name in found:
            base = name.split(".")[0]
            if base not in flds and base not in {"id"}:
                issues.append(_issue(node, "error", f"{model} has no field '{base}'.", _suggest(base, names)))
    return sorted(issues, key=lambda i: (i["line"], i["col"]))
