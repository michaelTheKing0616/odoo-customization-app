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
_GETTERS = {"operator.methodcaller": "@mc:", "operator.attrgetter": "@ag:"}
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
        self.container: dict[str, str] = {}  # list/dict/tuple holding a risky callable
        self.attr_alias: dict[str, str] = {}  # self.f = os.system -> "self.f"
        binds = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign):
                continue
            for t in n.targets:
                if isinstance(t, ast.Name):
                    binds.append((t.id, n.value))
                elif isinstance(t, (ast.Tuple, ast.List)) and isinstance(
                    n.value, (ast.Tuple, ast.List)
                ):
                    binds += [
                        (a.id, b)
                        for a, b in zip(t.elts, n.value.elts, strict=False)
                        if isinstance(a, ast.Name)
                    ]
                elif isinstance(t, ast.Attribute) and chain(t):
                    binds.append(("." + chain(t), n.value))
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    binds.append(("[]" + t.value.id, n.value))
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
                box = name.startswith("[]")
                if not d and isinstance(val, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
                    elts = val.values if isinstance(val, ast.Dict) else val.elts
                    d = next((e for e in map(self.expr, elts) if e and self._risky(e)), "")
                    box = True
                if not (d and self._risky(d)):
                    continue
                if box:
                    key = name.removeprefix("[]")
                    if self.container.get(key) != d:
                        self.container[key] = d
                        changed = True
                elif name.startswith("."):
                    if self.attr_alias.get(name[1:]) != d:
                        self.attr_alias[name[1:]] = d
                        changed = True
                elif self.alias.get(name) != d:
                    self.alias[name] = d
                    changed = True
            if not changed:
                break

    def _risky(self, d: str) -> bool:
        return (
            d.split(".")[0] in self.roots
            or d.startswith(("builtins.", "sys.modules"))
            or d in _BUILTIN_DANGER
            or d.rsplit(".", 1)[-1] == "Markup"
            or d.startswith(("@mc:", "@ag:"))
            or d in _GETTERS
            or d in ("getattr", "builtins.getattr", "functools.reduce")
        )

    def _reroot(self, d: str) -> str:
        """os.path.os.system -> os.system: re-root a dotted path at its last module root."""
        segs = d.split(".")
        for i in range(len(segs) - 2, 0, -1):
            if segs[i] in self.roots:
                return ".".join(segs[i:])
        return d

    def expr(self, n: ast.AST) -> str:
        """Dotted origin of an expression, '' when unknown."""
        if isinstance(n, ast.Name):
            if n.id in self.alias:
                return self.alias[n.id]
            if n.id in ("__builtins__", "builtins"):
                return "builtins"
            return n.id
        if isinstance(n, ast.Attribute):
            c = chain(n)
            if c and c in self.attr_alias:
                return self.attr_alias[c]
            base = self.expr(n.value)
            if n.attr == "__dict__" and base and self._risky(base + ".x"):
                return base  # module namespace dict
            if not base:
                return ""
            if n.attr == "__call__":
                return base
            return self._reroot(f"{base}.{n.attr}")
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
            if f in _GETTERS and lit:
                return _GETTERS[f] + lit  # methodcaller / attrgetter with a literal name
            if f.startswith("@ag:") and n.args:
                base = self.expr(n.args[0])
                return self._reroot(f"{base}.{f[4:]}") if base else ""
            if f == "functools.reduce" and len(n.args) >= 3:
                if self.expr(n.args[0]) in ("getattr", "builtins.getattr") and isinstance(
                    n.args[1], (ast.List, ast.Tuple)
                ):
                    names = [_c.value for _c in n.args[1].elts if isinstance(_c, ast.Constant)]
                    base = self.expr(n.args[2])
                    if base and len(names) == len(n.args[1].elts):
                        return self._reroot(".".join([base, *map(str, names)]))
                return ""
            if f in ("__import__", "builtins.__import__", "importlib.import_module") and lit:
                return lit if f == "importlib.import_module" else lit.split(".")[0]
            if f in ("globals", "locals") and not n.args:
                return "globals"
            if f == "vars":
                return self.expr(n.args[0]) if n.args else "globals"
            return ""
        if isinstance(n, ast.Subscript):
            base = self.expr(n.value)
            key = n.slice
            lit = key.value if isinstance(key, ast.Constant) else None
            if isinstance(n.value, ast.Name) and n.value.id in self.container:
                return self.container[n.value.id]
            if isinstance(lit, str):
                if base == "sys.modules":
                    return lit
                if base == "globals":
                    if lit in ("__builtins__", "builtins"):
                        return "builtins"
                    return self.alias.get(lit, f"builtins.{lit}")
                if base in ("builtins", "vars"):
                    return f"builtins.{lit}"
                if base and self._risky(base + ".x"):
                    return f"{base}.{lit}"  # vars(os)["system"], os.__dict__["system"]
            return ""
        return ""

    def call_target(self, call: ast.Call) -> str:
        d = self.expr(call.func)
        if d.startswith("@mc:"):
            base = self.expr(call.args[0]) if call.args else ""
            return f"{base}.{d[4:]}" if base else ""
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

    def dynamic_namespace(self, n: ast.Subscript) -> str:
        """globals()[x] / vars(os)[x] / os.__dict__[x] / sys.modules[x] / builtins[x] with a
        computed key: any function can be reached -> flagged."""
        if isinstance(n.slice, ast.Constant):
            return ""
        base = self.expr(n.value)
        if base in ("globals", "sys.modules", "builtins") or (
            base and base.split(".")[0] in self.roots and not isinstance(n.value, ast.Name)
        ):
            return base
        return ""

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
        seed_only: str | None = None,
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
                    if seed_only is None or arg.arg == seed_only:
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


def passthrough_functions(
    tree: ast.AST, res: Resolver, known: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Functions in this file that return (a transform of) one of their parameters, so a
    call with tainted arguments yields tainted data: def wrap(x): return '<b>' + x.
    `known` carries passthrough names from the module's other files (cross-file taint)."""
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found: frozenset[str] = frozenset(known)
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


_NET_ROOTS = ("requests.", "urllib.", "urllib3.", "httpx.", "http.client.", "aiohttp.")
_NET_CALLS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "request", "urlopen", "Request", "options"}
)
_SQL_ALIAS = _SQL_EXEC | {"sudo", "with_user"}


def method_aliases(tree: ast.AST) -> dict[str, str]:
    """ex = cr.execute; s = self.sudo; e = getattr(cr, "execute"); p = partial(cr.execute):
    local name -> the bound method it stands for."""
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Assign, ast.NamedExpr)):
            continue
        v = n.value
        if isinstance(v, ast.Call) and chain(v.func).rsplit(".", 1)[-1] == "partial" and v.args:
            v = v.args[0]
        m = ""
        if isinstance(v, ast.Attribute) and v.attr in _SQL_ALIAS:
            m = v.attr
        elif (
            isinstance(v, ast.Call)
            and getattr(v.func, "id", "") == "getattr"
            and len(v.args) >= 2
            and isinstance(v.args[1], ast.Constant)
            and v.args[1].value in _SQL_ALIAS
        ):
            m = v.args[1].value
        if m:
            tg = n.targets if isinstance(n, ast.Assign) else [n.target]
            out.update({t.id: m for t in tg if isinstance(t, ast.Name)})
    return out


def call_name(n: ast.Call, maliases: dict[str, str]) -> str:
    """Method name a call invokes, through method aliases and getattr(x, "literal")."""
    fn = n.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return maliases.get(fn.id, fn.id)
    if (
        isinstance(fn, ast.Call)
        and getattr(fn.func, "id", "") == "getattr"
        and len(fn.args) >= 2
        and isinstance(fn.args[1], ast.Constant)
        and isinstance(fn.args[1].value, str)
    ):
        return fn.args[1].value
    return ""


_NOT_HELPER = DB_CALLS | _STR_PASS | _ORM_API | _SQL_EXEC | {"sudo", "with_user", "with_context"}


# Summary of a helper: parameter key (position after self/cls, name, "*", "**") ->
# (severity, code, guard). guard names a parameter defaulting to a falsy literal that must be
# truthy for the sink to be reached (if body_is_html: Markup(body)); "" = unconditional.
Summary = dict[str | int, tuple[str, str, str]]
_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3, "": 9}
_CLEAN = ("", "", "")  # a declared parameter that reaches no sink


def _params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str | int, str]]:
    a = fn.args
    pos = [x for x in [*a.posonlyargs, *a.args] if x.arg not in ("self", "cls")]
    out: list[tuple[str | int, str]] = [(i, x.arg) for i, x in enumerate(pos)]
    out += [(x.arg, x.arg) for x in a.kwonlyargs]
    if a.vararg:
        out.append(("*", a.vararg.arg))
    if a.kwarg:
        out.append(("**", a.kwarg.arg))
    return out


def _falsy_defaults(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = fn.args
    pos = [*a.posonlyargs, *a.args]
    pairs = list(zip(pos[len(pos) - len(a.defaults) :], a.defaults, strict=False))
    pairs += [(x, d) for x, d in zip(a.kwonlyargs, a.kw_defaults, strict=False) if d is not None]
    return {
        x.arg for x, d in pairs if isinstance(d, ast.Constant) and d.value in (False, None, 0, "")
    }


def _guard(fn: ast.AST, line: int, flags: set[str], seeded: str) -> str:
    """A falsy-default flag parameter whose truth the sink at `line` depends on."""
    for n in ast.walk(fn):
        if not isinstance(n, ast.If) or not n.body:
            continue
        if not (n.body[0].lineno <= line <= (n.body[-1].end_lineno or n.body[-1].lineno)):
            continue
        t = n.test
        terms = t.values if isinstance(t, ast.BoolOp) and isinstance(t.op, ast.And) else [t]
        for x in terms:
            if isinstance(x, ast.Name) and x.id in flags and x.id != seeded:
                pos = [
                    p.arg
                    for p in [*fn.args.posonlyargs, *fn.args.args]
                    if p.arg not in ("self", "cls")
                ]
                return f"{x.id}:{pos.index(x.id) if x.id in pos else -1}"
    return ""


def function_defs(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        fn
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and fn.name not in _NOT_HELPER
        and not fn.name.startswith("__")
        and not _is_route(fn)
    ]


def function_summary(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    res: Resolver,
    passthrough: frozenset[str],
    sinks: dict[str, Summary],
) -> Summary:
    """Which parameters of fn reach a sink, directly or through helpers already summarised
    (sinks): computed per parameter so a call is reported only for the argument that flows."""
    malias = method_aliases(fn)
    t = Taint(fn, frozenset(), res, passthrough, seed_params=True)
    if not _scope_hits(fn, t, res, sinks, malias):
        return {}
    flags = _falsy_defaults(fn)
    out: Summary = {}
    for key, name in _params(fn):
        t = Taint(fn, frozenset(), res, passthrough, seed_params=True, seed_only=name)
        hits = _scope_hits(fn, t, res, sinks, malias)
        if not hits:
            out.setdefault(key, _CLEAN)
            if isinstance(key, int):
                out.setdefault(name, _CLEAN)
            continue
        h = min(hits, key=lambda h: _RANK[h.sev])
        guards = {_guard(fn, x.line, flags, name) for x in hits if x.sev == h.sev}
        g = "" if "" in guards else sorted(guards)[0]
        out[key] = (h.sev, h.code, g)
        if isinstance(key, int):
            out[name] = (h.sev, h.code, g)
    return out if any(v[0] for v in out.values()) else {}


def merge_summary(a: Summary, b: Summary) -> Summary:
    out = dict(a)
    for k, v in b.items():
        old = out.get(k)
        if old is None or _RANK[v[0]] < _RANK[old[0]] or (v[0] == old[0] and not v[2]):
            out[k] = v
    return out


def _sink_arg(n: ast.Call, summ: Summary, t: Taint) -> tuple[tuple[str, int], tuple] | None:
    """The tainted argument of call n that lands on a summarised sink parameter."""

    def guard_on(g: str) -> bool:
        if not g:
            return True
        name, _, idx = g.partition(":")
        for k in n.keywords:
            if k.arg == name:
                return not (isinstance(k.value, ast.Constant) and not k.value.value)
            if k.arg is None:
                return True  # **kwargs may carry the flag
        if any(isinstance(a, ast.Starred) for a in n.args):
            return True
        i = int(idx or -1)
        if 0 <= i < len(n.args):
            a = n.args[i]
            return not (isinstance(a, ast.Constant) and not a.value)
        return False  # flag left at its falsy default: the sink is not reached

    for i, a in enumerate(n.args):
        s = t.source(a)
        if not s:
            continue
        if isinstance(a, ast.Starred):
            cand = [v for k, v in summ.items() if isinstance(k, int) or k == "*"]
        else:
            cand = [summ[i]] if i in summ else ([summ["*"]] if "*" in summ else [])
        for v in cand:
            if v[0] and guard_on(v[2]):
                return s, v
    for k in n.keywords:
        s = t.source(k.value)
        if not s:
            continue
        if k.arg is None:
            cand = [v for kk, v in summ.items() if isinstance(kk, str)]
        else:
            cand = [summ[k.arg]] if k.arg in summ else ([summ["**"]] if "**" in summ else [])
        for v in cand:
            if v[0] and guard_on(v[2]):
                return s, v
    return None


def taint_hits(
    tree: ast.AST,
    text_fields: frozenset[str],
    res: Resolver,
    module_passthrough: frozenset[str] = frozenset(),
    module_sinks: dict[str, Summary] | None = None,
) -> list[Hit]:
    out: list[Hit] = []
    passthrough = passthrough_functions(tree, res, module_passthrough) | module_passthrough
    malias = method_aliases(tree)
    for scope in _func_scopes(tree):
        if isinstance(scope, ast.Lambda):
            continue
        t = Taint(scope, text_fields, res, passthrough)
        out += _scope_hits(scope, t, res, module_sinks or {}, malias)
    return out


_SANITIZED_SINKS = frozenset(
    {
        "message_post",
        "_message_update_content",
        "message_update_content",
        "_prepare_message_data",
        "_message_log",
        "message_notify",
        "_replace_local_links",
        "_render_template",
    }
)


def _const_str(n: ast.AST) -> str:
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else ""


def _scope_hits(
    scope: ast.AST,
    t: Taint,
    res: Resolver,
    sinks: dict[str, Summary],
    malias: dict[str, str],
) -> list[Hit]:
    out: list[Hit] = []
    sudo_recv = {
        id(c.func.value)
        for c in _own_nodes(scope)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in ("sudo", "with_user")
    }
    mail_body: set[int] = set()
    for a in _own_nodes(scope):
        if isinstance(a, ast.Assign) and any(
            (isinstance(tg, ast.Name) and tg.id == "body")
            or (isinstance(tg, ast.Subscript) and _const_str(tg.slice) == "body")
            for tg in a.targets
        ):
            v = a.value
            mail_body |= {id(v), id(getattr(v, "body", v)), id(getattr(v, "orelse", v))}
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
        name = call_name(n, malias)
        a0 = n.args[0] if n.args else None
        fdot = res.expr(n.func)
        if name in _NET_CALLS and fdot.startswith(_NET_ROOTS):
            url = a0 if name not in ("request", "Request") or len(n.args) < 2 else n.args[1]
            url = next((k.value for k in n.keywords if k.arg == "url"), url)
            s = t.source(url)
            if s:
                out.append(
                    Hit(
                        HIGH,
                        "tainted-request",
                        n.lineno,
                        f"Server-side request to a URL from {s[0]} (line {s[1]}): SSRF.",
                        "Call only fixed hosts; never fetch a URL the client supplies.",
                    )
                )
        if name in sinks and isinstance(n.func, (ast.Name, ast.Attribute)):
            got = _sink_arg(n, sinks[name], t)
            if got:
                s, (sev, code, _g) = got
                if code == "tainted-markup" and (
                    name in _SANITIZED_SINKS or s[0].startswith("record field")
                ):
                    sev = MEDIUM  # mail bodies are sanitized Html fields; stored data: review
                out.append(
                    Hit(
                        sev,
                        code,
                        n.lineno,
                        f"{s[0]} (line {s[1]}) is passed to {name}(), which uses its"
                        f" argument in a {code.removeprefix('tainted-')} sink.",
                        "Validate or escape the value before the call, or inside the helper.",
                    )
                )
        fc = n.func
        if (
            isinstance(fc, ast.Call)
            and res.expr(fc.func) in ("getattr", "builtins.getattr")
            and len(fc.args) >= 2
        ):
            s = t.source(fc.args[1])
            if s and not s[0].startswith("record field"):  # names stored by admins: INFO
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
                body = id(n) in mail_body and any(
                    isinstance(y, ast.Call) and call_name(y, malias) in _SANITIZED_SINKS
                    for y in _own_nodes(scope)
                )  # Markup(body) handed to message_post/_message_update_content: sanitized
                out.append(
                    Hit(
                        MEDIUM if body else HIGH,
                        "tainted-markup",
                        n.lineno,
                        f"Markup() wraps {s[0]} (line {s[1]}): stored/reflected XSS.",
                        "Escape it: Markup('<b>%s</b>') % value, or plain t-out.",
                    )
                )
        elif name in _SQL_EXEC and not isinstance(n.func, ast.Lambda) and a0 is not None:
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
        if isinstance(n, ast.Subscript) and (ns := res.dynamic_namespace(n)):
            out.append(
                Hit(
                    HIGH,
                    "dynamic-dispatch",
                    n.lineno,
                    f"{ns} namespace indexed by a computed name: any function (os.system,"
                    " eval) can be reached.",
                    "Use explicit names.",
                )
            )
        if (
            isinstance(n, ast.Call)
            and res.expr(n.func) in ("getattr", "builtins.getattr")
            and len(n.args) >= 2
            and not isinstance(n.args[1], ast.Constant)
            and not res.dynamic_module_attr(n)
        ):
            out.append(
                Hit(
                    INFO,
                    "dynamic-dispatch",
                    n.lineno,
                    f"getattr({ast.unparse(n.args[0])[:40]}, <computed name>): the method"
                    " reached cannot be decided statically (flagged; HIGH when the name comes"
                    " from a request).",
                    "Map allowed names to methods explicitly.",
                )
            )
        if isinstance(n, ast.Call):
            mod = res.dynamic_module_attr(n)
            if mod:
                out.append(
                    Hit(
                        HIGH if res._risky(mod + ".x") else LOW,
                        "dynamic-dispatch",
                        n.lineno,
                        f"getattr({mod}, <computed name>): any function of the module (os.system,"
                        " eval) can be reached; the target cannot be decided.",
                        "Use explicit attribute names.",
                    )
                )
    return out
