"""BOT-CODE-AUDIT Python analysis beyond single calls: name resolution through every import
and re-binding shape, taint from requests and record text into HTML/SQL/eval/redirect sinks,
and database work inside loops, comprehensions, ORM lambdas and same-module helpers.

Everything here is static and conservative: when a fact is undecidable (a dynamic attribute
name on an imported module, a dynamic import target) the code is FLAGGED, never assumed safe.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

HIGH, MEDIUM, LOW, INFO = "high", "medium", "low", "info"

# builtins that are only dangerous by name; a re-binding (e = eval) makes them aliases
_BUILTIN_DANGER = frozenset({"eval", "exec", "compile", "__import__", "getattr", "open"})
DB_CALLS = frozenset({"search", "search_count", "browse", "read", "search_read", "read_group"})
DB_CALLS |= {"search_fetch", "_read_group", "fetch", "create", "write", "unlink", "execute"}
DB_CALLS |= {"name_search", "_search", "exists", "copy"}
_ORM_LAMBDA = frozenset({"mapped", "filtered", "sorted", "map", "filter", "sorted_by"})
_PREFETCH_BREAK = frozenset({"sudo", "with_context", "with_user", "with_company", "with_env"})
_SANITIZERS = frozenset(
    {
        "escape",
        "html_escape",
        "html_sanitize",
        "plaintext2html",
        "int",
        "float",
        "bool",
        "len",
        "quote",
        "identifier",
        "is_html_empty",
    }
)
# stock text fields users type into (record taint); module-defined Char/Text/Html add to it
USER_TEXT = frozenset(
    {
        "name",
        "display_name",
        "description",
        "note",
        "notes",
        "comment",
        "body",
        "body_html",
        "subject",
        "email",
        "email_from",
        "street",
        "ref",
        "login",
        "website",
        "partner_name",
        "contact_name",
    }
)
_REQUEST_ATTRS = frozenset(
    {"params", "httprequest", "jsonrequest", "get_json_data", "get_http_params", "args", "form"}
)
# methods whose result carries their receiver's (or arguments') text through unchanged
_STR_PASS = frozenset(
    {
        "format",
        "format_map",
        "join",
        "replace",
        "strip",
        "lstrip",
        "rstrip",
        "lower",
        "upper",
        "title",
        "capitalize",
        "encode",
        "decode",
        "split",
        "rsplit",
        "splitlines",
        "get",
        "getlist",
        "pop",
        "values",
        "items",
        "copy",
        "to_dict",
        "get_json_data",
        "get_data",
        "str",
        "repr",
        "loads",
        "urljoin",
        "unquote",
        "unquote_plus",
    }
)
# calls that always query (browse() does not: it only builds a recordset)
_DB_READ = frozenset(
    {"search", "search_count", "read", "search_read", "read_group", "_read_group"}
) | {"search_fetch", "fetch", "execute", "_search", "name_search"}
# BaseModel API names a module may override; a call by that name is the ORM's, not a helper
_ORM_API = frozenset(
    {
        "new",
        "invalidate_recordset",
        "invalidate_model",
        "flush_recordset",
        "flush_model",
        "modified",
        "ensure_one",
        "default_get",
        "fields_get",
        "name_get",
        "name_create",
        "onchange",
        "check_access",
        "check_access_rights",
        "check_access_rule",
        "has_access",
        "_check_company",
        "_field_will_change",
        "_compute_display_name",
        "get_metadata",
        "update",
        "filtered_domain",
    }
)
MAX_HELPER_HOPS = 2
_SQL_EXEC = frozenset({"execute", "executemany", "mogrify", "execute_values", "execute_batch"})


@dataclass(frozen=True)
class Hit:
    sev: str
    code: str
    line: int
    msg: str
    fix: str


def chain(n: ast.AST) -> str:
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return ".".join(reversed(parts))
    return ""


# ---------------------------------------------------------------- (d) name resolution


class Resolver:
    """Local name -> dotted origin, through: import x / import x.y / import x as y, from x
    import y [as z], relative imports (ignored: same module), star imports, imports under
    if/try/def (all branches count), re-binding (s = os; f = s.system; e = eval),
    getattr(x, "literal"), __import__("lit") / importlib.import_module("lit"),
    sys.modules["lit"], __builtins__["lit"] / builtins.__dict__["lit"]. Flow-insensitive: a
    name bound anywhere to a risky origin is that origin everywhere (over-approximation)."""

    def __init__(self, tree: ast.AST, roots: frozenset[str]):
        self.roots = roots
        self.alias: dict[str, str] = {}
        self.star: list[str] = []
        self.defined: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.alias[a.asname or a.name.split(".")[0]] = (
                        a.name if a.asname else a.name.split(".")[0]
                    )
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                for a in n.names:
                    if a.name == "*":
                        self.star.append(n.module)
                    else:
                        self.alias[a.asname or a.name] = f"{n.module}.{a.name}"
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defined.add(n.name)
        binds = [
            (t.id, n.value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name)
        ]
        binds += [
            (n.target.id, n.value)
            for n in ast.walk(tree)
            if isinstance(n, (ast.AnnAssign, ast.NamedExpr))
            and isinstance(n.target, ast.Name)
            and n.value is not None
        ]
        for _ in range(4):  # fixpoint over chains of re-bindings
            changed = False
            for name, val in binds:
                d = self.expr(val)
                if d and self._risky(d) and self.alias.get(name) != d:
                    self.alias[name] = d
                    changed = True
            if not changed:
                break

    def _risky(self, d: str) -> bool:
        return d.split(".")[0] in self.roots or d.startswith(("builtins.", "sys.modules"))

    def expr(self, n: ast.AST) -> str:
        """Dotted origin of an expression, '' when unknown."""
        if isinstance(n, ast.Name):
            if n.id in self.alias:
                return self.alias[n.id]
            if n.id in ("__builtins__", "builtins"):
                return "builtins"
            return n.id
        if isinstance(n, ast.Attribute):
            base = self.expr(n.value)
            if base == "builtins" and n.attr == "__dict__":
                return "builtins"
            return f"{base}.{n.attr}" if base else ""
        if isinstance(n, ast.Call):
            f = self.expr(n.func)
            a0 = n.args[0] if n.args else None
            lit = a0.value if isinstance(a0, ast.Constant) and isinstance(a0.value, str) else None
            if f in ("getattr", "builtins.getattr") and len(n.args) >= 2:
                base = self.expr(n.args[0])
                name = n.args[1]
                if isinstance(name, ast.Constant) and isinstance(name.value, str) and base:
                    return f"{base}.{name.value}"
                return ""
            if f in ("__import__", "builtins.__import__", "importlib.import_module") and lit:
                return lit if f == "importlib.import_module" else lit.split(".")[0]
            return ""
        if isinstance(n, ast.Subscript):
            base = self.expr(n.value)
            key = n.slice
            lit = key.value if isinstance(key, ast.Constant) else None
            if isinstance(lit, str):
                if base == "sys.modules":
                    return lit
                if base in ("builtins", "globals", "vars"):
                    return f"builtins.{lit}"
            return ""
        return ""

    def call_target(self, call: ast.Call) -> str:
        d = self.expr(call.func)
        if (
            isinstance(call.func, ast.Name)
            and call.func.id not in self.alias
            and call.func.id not in self.defined
        ):
            for mod in self.star:
                if mod.split(".")[0] in self.roots:
                    return f"{mod}.{call.func.id}"
            if call.func.id in _BUILTIN_DANGER:
                return call.func.id  # plain builtin: existing checks own it
        if d in _BUILTIN_DANGER and isinstance(call.func, ast.Name) and call.func.id != d:
            return f"builtins.{d}"
        return d

    def dynamic_module_attr(self, call: ast.Call) -> str:
        """getattr(<imported module>, <non-literal>): undecidable target -> flagged."""
        if self.expr(call.func) in ("getattr", "builtins.getattr") and len(call.args) >= 2:
            if not isinstance(call.args[1], ast.Constant):
                base = call.args[0]
                if isinstance(base, ast.Name) and base.id in self.alias:
                    return self.alias[base.id]
        return ""


# ---------------------------------------------------------------- (c) taint


def _is_route(fn: ast.AST) -> bool:
    return any(
        chain(d.func if isinstance(d, ast.Call) else d).endswith("route") for d in fn.decorator_list
    )


def _func_scopes(tree: ast.AST) -> Iterator[ast.AST]:
    yield tree
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            yield n


def _own_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """Nodes of a scope, not descending into nested functions/classes."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        n = stack.pop()
        yield n
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(n))


class Taint:
    def __init__(
        self,
        scope: ast.AST,
        text_fields: frozenset[str],
        res: Resolver,
        passthrough: frozenset[str] = frozenset(),
        seed_params: bool = False,
    ):
        self.fields = text_fields
        self.res = res
        self.passthrough = passthrough  # same-file functions whose result carries an argument
        self.src: dict[str, tuple[str, int]] = {}  # var -> (source description, line)
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            seed_params or _is_route(scope)
        ):
            a = scope.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                if arg is not None and arg.arg not in ("self", "cls"):
                    self.src[arg.arg] = (f"route parameter {arg.arg}", scope.lineno)
        assigns = []
        for n in _own_nodes(scope):
            if isinstance(n, ast.Assign):
                assigns += [(t, n.value) for t in n.targets]
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)) and n.value is not None:
                assigns.append((n.target, n.value))
            elif isinstance(n, ast.NamedExpr):
                assigns.append((n.target, n.value))
            elif isinstance(n, (ast.For, ast.comprehension)):
                assigns.append((n.target, n.iter))
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                assigns.append((n.optional_vars, n.context_expr))
        for _ in range(6):
            changed = False
            for tgt, val in assigns:
                s = self.source(val)
                if not s:
                    continue
                for t in ast.walk(tgt):
                    if isinstance(t, ast.Name) and t.id not in self.src:
                        self.src[t.id] = s
                        changed = True
            if not changed:
                break

    def source(self, n: ast.AST | None) -> tuple[str, int] | None:
        """Where tainted data in expression n comes from, or None."""
        if n is None:
            return None
        if isinstance(n, ast.Call):
            # only text-preserving calls pass taint on; any other call (a lookup, an ORM
            # method, a renderer) returns new data (see BOT-CODE-AUDIT-2.md, limitations)
            fn = n.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name not in _STR_PASS and name not in self.passthrough:
                return None
            if isinstance(fn, ast.Attribute):
                r = self.source(fn.value)
                if r:
                    return r
            for a in [*n.args, *(k.value for k in n.keywords)]:
                r = self.source(a)
                if r:
                    return r
            return None
        if isinstance(n, ast.Attribute):
            d = chain(n)
            parts = d.split(".")
            if len(parts) >= 2 and parts[0] == "request" and parts[1] in _REQUEST_ATTRS:
                return (f"request.{parts[1]}", n.lineno)
            if (
                n.attr in self.fields
                and isinstance(n.value, (ast.Name, ast.Attribute))
                and not (isinstance(n.value, ast.Name) and n.value.id in self.res.alias)
            ):
                return (f"record field {n.attr}", n.lineno)
        if isinstance(n, ast.Name) and n.id in self.src:
            return self.src[n.id]
        if isinstance(n, (ast.Lambda, ast.Constant)):
            return None
        if isinstance(n, (ast.Subscript, ast.Starred)):
            return self.source(n.value)
        if isinstance(n, ast.Attribute):
            return None  # attribute of an untainted object
        for ch in ast.iter_child_nodes(n):
            r = self.source(ch)
            if r:
                return r
        return None


def _markup_call(res: Resolver, call: ast.Call) -> bool:
    d = res.expr(call.func)
    return d.rsplit(".", 1)[-1] == "Markup"


def passthrough_functions(tree: ast.AST, res: Resolver) -> frozenset[str]:
    """Functions in this file that return (a transform of) one of their parameters, so a
    call with tainted arguments yields tainted data: def wrap(x): return '<b>' + x."""
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found: frozenset[str] = frozenset()
    for _ in range(4):
        new = set(found)
        for fn in fns:
            if fn.name in new:
                continue
            t = Taint(fn, frozenset(), res, found, seed_params=True)
            if any(
                isinstance(r, ast.Return) and r.value is not None and t.source(r.value)
                for r in _own_nodes(fn)
            ):
                new.add(fn.name)
        if new == found:
            break
        found = frozenset(new)
    return found


def taint_hits(tree: ast.AST, text_fields: frozenset[str], res: Resolver) -> list[Hit]:
    out: list[Hit] = []
    passthrough = passthrough_functions(tree, res)
    for scope in _func_scopes(tree):
        if isinstance(scope, ast.Lambda):
            continue
        t = Taint(scope, text_fields, res, passthrough)
        sudo_recv = {
            id(c.func.value)
            for c in _own_nodes(scope)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr in ("sudo", "with_user")
        }
        for n in _own_nodes(scope):
            if isinstance(n, ast.Subscript) and chain(n.value).endswith("env"):
                s = t.source(n.slice)
                if s and not s[0].startswith("record field"):
                    # the ORM still checks the caller's rights on env[model]; sudo() drops them
                    su = id(n) in sudo_recv or "sudo" in chain(n.value)
                    out.append(
                        Hit(
                            HIGH if su else LOW,
                            "tainted-model",
                            n.lineno,
                            f"Model name comes from {s[0]} (line {s[1]})"
                            + (" and is used with sudo()." if su else "."),
                            "Accept only model names from a fixed allow-list.",
                        )
                    )
            if not isinstance(n, ast.Call):
                continue
            name = chain(n.func).rsplit(".", 1)[-1] if chain(n.func) else ""
            a0 = n.args[0] if n.args else None
            fc = n.func
            if (
                isinstance(fc, ast.Call)
                and res.expr(fc.func) in ("getattr", "builtins.getattr")
                and len(fc.args) >= 2
            ):
                s = t.source(fc.args[1])
                if s:
                    out.append(
                        Hit(
                            HIGH,
                            "tainted-dispatch",
                            n.lineno,
                            f"Calls a method named by {s[0]} (line {s[1]}): any public or"
                            " private method can be reached.",
                            "Map allowed names to methods explicitly (a dict of allowed actions).",
                        )
                    )
            if _markup_call(res, n) and a0 is not None and not isinstance(a0, ast.Constant):
                s = t.source(a0)
                if s:
                    out.append(
                        Hit(
                            HIGH,
                            "tainted-markup",
                            n.lineno,
                            f"Markup() wraps {s[0]} (line {s[1]}): stored/reflected XSS.",
                            "Escape it: Markup('<b>%s</b>') % value, or plain t-out.",
                        )
                    )
            elif name in _SQL_EXEC and isinstance(n.func, ast.Attribute) and a0 is not None:
                s = t.source(a0)
                if s:
                    out.append(
                        Hit(
                            HIGH,
                            "tainted-sql",
                            n.lineno,
                            f"SQL text built from {s[0]} (line {s[1]}).",
                            "Pass values as query parameters; use SQL.identifier() for names.",
                        )
                    )
            elif name == "SQL" and a0 is not None and not isinstance(a0, ast.Constant):
                s = t.source(a0)
                if s:
                    out.append(
                        Hit(
                            HIGH,
                            "tainted-sql",
                            n.lineno,
                            f"SQL() template built from {s[0]} (line {s[1]}).",
                            "Keep the SQL() template literal; pass values as arguments.",
                        )
                    )
            elif name in ("safe_eval", "eval", "exec", "const_eval", "expr_eval") and a0:
                s = t.source(a0)
                if s:
                    out.append(
                        Hit(
                            HIGH,
                            "tainted-eval",
                            n.lineno,
                            f"{name}() evaluates {s[0]} (line {s[1]}).",
                            "Never evaluate user-supplied text.",
                        )
                    )
            elif name in ("make_response", "Response") and a0 is not None:
                s = t.source(a0)
                if s:
                    out.append(
                        Hit(
                            MEDIUM,
                            "tainted-response",
                            n.lineno,
                            f"Response body is {s[0]} (line {s[1]}) without escaping.",
                            "Render through a QWeb template, or escape and set a text/plain type.",
                        )
                    )
            elif name == "redirect" and a0 is not None:
                # Odoo's request.redirect() keeps only the path unless local=False
                d = chain(n.func)
                local = not any(
                    k.arg == "local" and isinstance(k.value, ast.Constant) and not k.value.value
                    for k in n.keywords
                )
                s = None if d.startswith("request.") and local else t.source(a0)
                if s:
                    out.append(
                        Hit(
                            MEDIUM,
                            "open-redirect",
                            n.lineno,
                            f"Redirect target comes from {s[0]} (line {s[1]}).",
                            "Use request.redirect(url, local=True) or a fixed route.",
                        )
                    )
    return out


# ---------------------------------------------------------------- (c) loops, helpers, N+1


def _loop_bodies(tree: ast.AST) -> Iterator[tuple[ast.AST, list[ast.AST]]]:
    """(loop node, parts evaluated once per iteration). A for-loop's iterable and a
    comprehension's first iterable run once and are excluded."""
    for n in ast.walk(tree):
        if isinstance(n, (ast.For, ast.AsyncFor)):
            yield n, [*n.body, n.target]
        elif isinstance(n, ast.While):
            yield n, [n.test, *n.body]
        elif isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            elts = [n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]
            gens = n.generators
            yield n, [*elts, *gens[0].ifs, *(p for g in gens[1:] for p in (g.iter, *g.ifs))]
        elif (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in _ORM_LAMBDA
        ):
            lams = [a for a in n.args if isinstance(a, ast.Lambda)]
            if lams:
                yield n, [lam.body for lam in lams]


def _walk_parts(parts: Iterable[ast.AST]) -> Iterator[ast.AST]:
    for p in parts:
        yield from ast.walk(p)


def module_db_helpers(trees: dict[str, ast.AST]) -> dict[str, str]:
    """Function/method name defined anywhere in the module -> the DB call it reaches
    (directly or through other same-module helpers). Names that equal ORM methods are left
    to the direct check."""
    defs: dict[str, list[ast.AST]] = {}
    for tree in trees.values():
        for n in ast.walk(tree):
            if (
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name not in DB_CALLS
                and n.name not in _ORM_API
            ):
                defs.setdefault(n.name, []).append(n)
    reach: dict[str, str] = {}
    for name, fns in defs.items():
        for fn in fns:
            for c in ast.walk(fn):
                if isinstance(c, ast.Call):
                    cn = c.func.attr if isinstance(c.func, ast.Attribute) else ""
                    if cn in _DB_READ:
                        reach[name] = f"{cn}()"
    for _ in range(16):  # full transitive closure, one hop per pass (snapshot)
        snap = dict(reach)
        for name, fns in defs.items():
            if name in snap:
                continue
            hit = next(
                (
                    cn
                    for fn in fns
                    for c in ast.walk(fn)
                    if isinstance(c, ast.Call)
                    for cn in [chain(c.func).rsplit(".", 1)[-1] if chain(c.func) else ""]
                    if cn in snap and cn != name
                ),
                None,
            )
            if hit:
                reach[name] = f"{hit}() -> {snap[hit]}"
        if len(reach) == len(snap):
            break
    return reach


def loop_hits(tree: ast.AST, helpers: dict[str, str]) -> list[Hit]:
    out: list[Hit] = []
    seen: set[int] = set()
    # rec.sudo().partner_id.name: a related (two-level) field read on a fresh, non-prefetched
    # recordset; rec.with_company(c).write(...) or a single-level read is not N+1
    related_reads = {
        id(a.value.value)
        for a in ast.walk(tree)
        if isinstance(a, ast.Attribute)
        and isinstance(a.value, ast.Attribute)
        and isinstance(a.value.value, ast.Call)
        and not isinstance(a, ast.Call)
    }
    for loop, parts in _loop_bodies(tree):
        kind = (
            "comprehension"
            if isinstance(loop, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp))
            else "ORM lambda"
            if isinstance(loop, ast.Call)
            else "loop"
        )
        for n in _walk_parts(parts):
            if not isinstance(n, ast.Call) or id(n) in seen:
                continue
            fn = n.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in DB_CALLS and isinstance(fn, ast.Attribute):
                if name in (
                    "search",
                    "search_count",
                    "browse",
                    "read",
                    "search_read",
                    "read_group",
                ):
                    continue  # the existing direct check reports these (query-in-loop)
                seen.add(id(n))
                out.append(
                    Hit(
                        LOW if name == "create" else INFO,
                        "orm-in-loop",
                        n.lineno,
                        f"{name}() inside a {kind} (one query per item).",
                        "Batch it: create(vals_list), or write/unlink on the whole recordset"
                        " when the values are the same.",
                    )
                )
            elif name in helpers:
                seen.add(id(n))
                hops = helpers[name].count("->") + 1
                out.append(
                    Hit(
                        LOW if hops <= MAX_HELPER_HOPS else INFO,
                        "query-in-loop-helper",
                        n.lineno,
                        f"{name}() inside a {kind} runs a query each time ({helpers[name]}).",
                        "Make the helper work on a whole recordset and call it once.",
                    )
                )
            elif name in _PREFETCH_BREAK and isinstance(fn, ast.Attribute):
                tgt = fn.value
                loopvars = {
                    t.id
                    for t in ast.walk(getattr(loop, "target", None) or ast.Pass())
                    if isinstance(t, ast.Name)
                }
                if isinstance(tgt, ast.Name) and tgt.id in loopvars and id(n) in related_reads:
                    seen.add(id(n))
                    out.append(
                        Hit(
                            LOW,
                            "n-plus-one",
                            n.lineno,
                            f"{tgt.id}.{name}() per iteration breaks prefetching: each related"
                            " field read becomes its own query.",
                            f"Call {name}() once on the recordset before the loop.",
                        )
                    )
    return out


def dynamic_hits(tree: ast.AST, res: Resolver) -> list[Hit]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            mod = res.dynamic_module_attr(n)
            if mod:
                out.append(
                    Hit(
                        LOW,
                        "dynamic-dispatch",
                        n.lineno,
                        f"getattr({mod}, <computed name>): call target cannot be decided.",
                        "Use explicit attribute names.",
                    )
                )
    return out
