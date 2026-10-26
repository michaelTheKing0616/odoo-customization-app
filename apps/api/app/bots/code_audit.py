"""BOT-CODE-AUDIT: read-only audit of Odoo module source (owned or third-party).

Takes module source as zip bytes or a directory, never imports or executes it, and parses
only with ``ast``, ``csv`` and a DTD-free XML parser. Returns structured findings (severity,
code, file, line, message, fix hint) for: access rights and record rules, unsafe code (sudo,
raw SQL, eval/exec, unsafe XML/QWeb, unsafe default/domain/context), upgrade hazards
(references to xmlids or fields the module does not define), compatibility with the target
Odoo version (versioncaps), and performance smells. Ownership is decided by the caller's
registry of Ingenium-owned module names, never by the module's own manifest; foreign modules
are audit-only (``editable`` False). Hostile input is bounded (size, count, depth, ratio),
zip-slip and symlink safe; malformed files become findings, never crashes.
"""

from __future__ import annotations

import ast
import csv
import io
import re
import stat
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from app.bots.versioncaps import caps

VERSIONS = (17, 18, 19, 20)
MAX_FILES, MAX_FILE, MAX_TOTAL, MAX_DEPTH, MAX_RATIO = 2000, 2_000_000, 20_000_000, 12, 100
MAX_AST_NODES = 200_000
HIGH, MEDIUM, LOW, INFO = "high", "medium", "low", "info"
_SEV_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}
_MAGIC = frozenset(
    {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "__last_update"}
)
_DANGER = re.compile(
    r"__import__|\beval\s*\(|\bexec\s*\(|\bos\.|\bsubprocess\b|\bopen\s*\(|\bsudo\s*\("
)
_DANGER_PY = re.compile(r"__import__|\beval\s*\(|\bexec\s*\(|\bos\.|\bsubprocess\b|\bopen\s*\(")
_BAD_MODULES = frozenset({"subprocess", "ctypes", "pickle", "marshal", "pty", "shelve"})
_ASSET_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".bmp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp3",
    ".mp4",
    ".webm",
    ".pdf",
    ".zip",
    ".gz",
    ".map",
    ".pyc",
    ".po",
    ".pot",
)
MAX_INDEX_FINDINGS = 20
_DB_CALLS = frozenset({"search", "search_count", "browse", "read", "search_read", "read_group"})
FOREIGN_HINT = "Audit only: report to the module's maintainer; Ingenium never edits foreign code."


class SourceError(ValueError):
    """The source cannot be audited at all (refused before parsing)."""


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    file: str
    line: int
    message: str
    fix: str


@dataclass
class Report:
    ok: bool
    module: str | None
    owned: bool
    editable: bool
    version: int | None
    findings: list[Finding] = field(default_factory=list)
    error: str = ""

    @property
    def counts(self) -> dict[str, int]:
        c = {s: 0 for s in _SEV_RANK}
        for f in self.findings:
            c[f.severity] += 1
        return c


# ---------------------------------------------------------------- source loading (hostile-safe)


def _safe_rel(name: str) -> str:
    if "\x00" in name or "\\" in name:
        raise SourceError(f"unsafe path {name!r}")
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or len(p.parts) > MAX_DEPTH:
        raise SourceError(f"unsafe path {name!r}")
    return str(p)


def _is_asset(rel: str) -> bool:
    parts = rel.split("/")
    return bool({"static", "i18n", "__pycache__"} & set(parts[:-1])) or rel.lower().endswith(
        _ASSET_EXT
    )


def _check_name(rel: str) -> None:
    if PurePosixPath(rel).name == ".module_dir":
        raise SourceError("reserved file name .module_dir in source")


def _from_zip(data: bytes, skip_assets: bool = False) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SourceError("not a valid zip archive") from e
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise SourceError("too many files")
    out: dict[str, bytes] = {}
    total = 0
    for i in infos:
        if i.is_dir():
            continue
        rel = _safe_rel(i.filename)
        _check_name(rel)
        if stat.S_ISLNK(i.external_attr >> 16):
            raise SourceError(f"symlink in archive: {rel}")
        if skip_assets and _is_asset(rel):
            continue
        if i.file_size > MAX_FILE or (
            i.compress_size and i.file_size / i.compress_size > MAX_RATIO
        ):
            raise SourceError(f"file too large or over-compressed: {rel}")
        with zf.open(i) as fh:
            body = fh.read(MAX_FILE + 1)
        if len(body) > MAX_FILE:
            raise SourceError(f"file too large: {rel}")
        total += len(body)
        if total > MAX_TOTAL:
            raise SourceError("archive too large")
        if rel in out:
            raise SourceError(f"duplicate path {rel}")
        out[rel] = body
    return out


def _from_dir(root: Path, skip_assets: bool = False) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise SourceError("source directory missing or a symlink")
    out: dict[str, bytes] = {}
    total = 0
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise SourceError("directory too deep")
        for p in sorted(d.iterdir()):
            st = p.lstat()
            if stat.S_ISLNK(st.st_mode):
                raise SourceError(f"symlink in source: {p.relative_to(root)}")
            if stat.S_ISDIR(st.st_mode):
                stack.append((p, depth + 1))
                continue
            if not stat.S_ISREG(st.st_mode):
                raise SourceError(f"special file in source: {p.relative_to(root)}")
            rel = _safe_rel(p.relative_to(root).as_posix())
            _check_name(rel)
            if skip_assets and _is_asset(rel):
                continue
            if st.st_size > MAX_FILE:
                raise SourceError(f"file too large: {p.relative_to(root)}")
            total += st.st_size
            if total > MAX_TOTAL or len(out) >= MAX_FILES:
                raise SourceError("source too large")
            out[rel] = p.read_bytes()
    return out


def load_tree(
    src: bytes | Path, *, skip_assets: bool = False
) -> tuple[dict[str, bytes], str | None]:
    """Return (module-relative files, top folder or None). The folder name never enters files."""
    if isinstance(src, (bytes, bytearray)):
        files = _from_zip(bytes(src), skip_assets)
    elif isinstance(src, Path):
        files = _from_dir(src, skip_assets)
    else:
        raise SourceError("source must be zip bytes or a directory path")
    top = None
    tops = {f.split("/", 1)[0] for f in files}
    if len(tops) == 1 and all("/" in f for f in files):
        top = tops.pop()
        files = {f.split("/", 1)[1]: b for f, b in files.items()}
    return files, top


def load_source(src: bytes | Path) -> dict[str, bytes]:
    return load_tree(src)[0]


# ---------------------------------------------------------------- parsing helpers


def _parse_xml(body: bytes) -> ET.Element:
    head = body[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in body.upper():
        raise ValueError("DTD/entities are not allowed")
    return ET.fromstring(body)  # noqa: S314 - DTD rejected above; expat never fetches


def _line_of(text: str, needle: str) -> int:
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else 0


class _Ctx:
    def __init__(self, files: dict[str, bytes], version: int, owned: bool):
        self.files, self.v, self.owned = files, version, owned
        self.f: list[Finding] = []
        self.new_models: dict[str, tuple[str, int, bool]] = {}  # model -> file, line, transient
        self.inherit: dict[str, tuple[str, int]] = {}
        self.model_fields: dict[str, dict[str, dict[str, Any]]] = {}
        self.xmlids: set[str] = set()
        self.refs: list[tuple[str, str, int]] = []
        self.access: dict[str, set[str]] = {}  # file -> model xmlids with access rows
        self.abstract: set[str] = set()
        self.seen_idx: set[tuple[str, str]] = set()
        self.parents: dict[str, list[str]] = {}  # new model -> _inherit/_inherits parents
        self.rules: set[str] = set()
        self.view_fields: list[tuple[str, str, str, int]] = []  # model, field, file, line
        self.module = ""

    def add(self, sev, code, file, line, msg, fix):
        if file.startswith("tests/") or "/tests/" in file:
            sev = LOW if _SEV_RANK[sev] < _SEV_RANK[LOW] else sev  # test code never loads in prod
        if not self.owned:
            fix = f"{FOREIGN_HINT} Suggested fix: {fix}"
        self.f.append(Finding(sev, code, file, int(line or 0), msg, fix))


# ---------------------------------------------------------------- python


def _is_dynamic_str(n: ast.AST) -> bool:
    return isinstance(n, (ast.JoinedStr, ast.BinOp)) or (
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format"
    )


def _const(n: ast.AST) -> Any:
    return n.value if isinstance(n, ast.Constant) else None


def _dotted(n: ast.AST) -> str:
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
    return ".".join(reversed(parts))


def _py_danger(call: ast.Call) -> str:
    d = _dotted(call.func)
    if d in ("__import__", "os.system", "os.popen", "os.spawnl", "os.spawnv", "os.startfile"):
        return f"{d}()"
    if d.startswith(("os.exec", "subprocess.", "importlib.", "pty.", "ctypes.")):
        return f"{d}()"
    if d == "getattr" and call.args:
        first = _dotted(call.args[0])
        if first in ("__builtins__", "builtins") or (
            len(call.args) > 1
            and not isinstance(call.args[1], ast.Constant)
            and first in ("os", "subprocess", "importlib")
        ):
            return f"getattr({first}, ...)"
    return ""


def _sql_has_variable(n: ast.AST) -> bool:
    """True when a formatted query interpolates anything except literals or the model table."""
    if isinstance(n, ast.JoinedStr):
        parts = [v.value for v in n.values if isinstance(v, ast.FormattedValue)]
    elif isinstance(n, ast.BinOp):
        parts = [n.left, n.right]
    elif isinstance(n, ast.Call):
        parts = [n.func.value, *n.args, *(k.value for k in n.keywords)]  # type: ignore[attr-defined]
    else:
        return False
    for p in parts:
        if isinstance(p, ast.Constant):
            continue
        if isinstance(p, (ast.JoinedStr, ast.BinOp)):
            if _sql_has_variable(p):
                return True
            continue
        if isinstance(p, ast.Tuple) and all(
            isinstance(e, ast.Constant) or (isinstance(e, ast.Attribute) and e.attr == "_table")
            for e in p.elts
        ):
            continue
        if isinstance(p, ast.Attribute) and p.attr == "_table":
            continue
        return True
    return False


def _audit_py(c: _Ctx, path: str, body: bytes) -> None:
    try:
        text = body.decode("utf-8-sig")
        tree = ast.parse(text, filename=path)
    except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError, MemoryError) as e:
        c.add(
            HIGH,
            "parse-error",
            path,
            getattr(e, "lineno", 0),
            f"Python file does not parse ({type(e).__name__}).",
            "Fix the syntax; Odoo will fail to load this module.",
        )
        return
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        c.add(MEDIUM, "too-complex", path, 1, "File too large to audit fully.", "Split the file.")
        return
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        attrs = {}
        for st in cls.body:
            if (
                isinstance(st, ast.Assign)
                and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
            ):
                attrs[st.targets[0].id] = st.value
        name = _const(attrs.get("_name"))
        inh = attrs.get("_inherit")
        inh_list = (
            [_const(inh)]
            if isinstance(inh, ast.Constant)
            else [_const(e) for e in getattr(inh, "elts", [])]
        )
        transient = any(
            getattr(b, "attr", getattr(b, "id", "")) == "TransientModel" for b in cls.bases
        )
        abstract = any(
            getattr(b, "attr", getattr(b, "id", "")) == "AbstractModel" for b in cls.bases
        )
        inherits = attrs.get("_inherits")
        deleg = [_const(k) for k in getattr(inherits, "keys", [])]
        if isinstance(name, str) and name not in inh_list:
            c.new_models[name] = (path, cls.lineno, transient)
            c.parents[name] = [m for m in inh_list + deleg if isinstance(m, str)]
            if abstract:
                c.abstract.add(name)
            target = name
        elif inh_list and isinstance(inh_list[0], str):
            target = name if isinstance(name, str) else inh_list[0]
            for m in inh_list:
                if isinstance(m, str):
                    c.inherit.setdefault(m, (path, cls.lineno))
        else:
            continue
        flds = c.model_fields.setdefault(target, {})
        for st in cls.body:
            if not (isinstance(st, ast.Assign) and isinstance(st.value, ast.Call)):
                continue
            fn = st.value.func
            if isinstance(fn, ast.Attribute) and getattr(fn.value, "id", "") == "fields":
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        kws = {k.arg: k.value for k in st.value.keywords if k.arg}
                        flds[t.id] = {
                            "type": fn.attr,
                            "line": st.lineno,
                            "index": _const(kws.get("index")) not in (None, False),
                        }
                        d = kws.get("default")
                        if d is not None and any(
                            isinstance(x, ast.Attribute) and x.attr in ("sudo", "search")
                            for x in ast.walk(d)
                        ):
                            c.add(
                                MEDIUM,
                                "unsafe-default",
                                path,
                                st.lineno,
                                f"Default of {t.id} runs a search or sudo() on every new record.",
                                "Use a plain value or a cheap context-based default.",
                            )
    # calls
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]
    in_loop: set[int] = set()
    for lp in loops:
        for node in ast.walk(lp):
            if node is not lp and isinstance(node, ast.Call):
                in_loop.add(id(node))
    searched: list[tuple[str, int]] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        ln = getattr(n, "lineno", 0)
        danger = _py_danger(n)
        if danger:
            c.add(
                HIGH,
                "dangerous-call",
                path,
                ln,
                f"{danger} can run commands or arbitrary code.",
                "Remove it; Odoo modules must not shell out, import dynamically or reach builtins.",
            )
        elif isinstance(fn, ast.Name) and name == "open":
            c.add(
                MEDIUM,
                "file-access",
                path,
                ln,
                "open() reads or writes server files.",
                "Use attachments (ir.attachment) or odoo.tools.file_open for module files.",
            )
        if isinstance(fn, ast.Name) and name in ("eval", "exec"):
            c.add(
                HIGH,
                "eval-exec",
                path,
                ln,
                f"{name}() runs arbitrary code.",
                "Use odoo.tools.safe_eval with a minimal context, or remove.",
            )
        elif name == "safe_eval":
            c.add(
                LOW,
                "safe-eval",
                path,
                ln,
                "safe_eval of stored text.",
                "Make sure only trusted users can edit the evaluated text.",
            )
        elif name == "sudo":
            c.add(
                LOW,
                "sudo",
                path,
                ln,
                "sudo() bypasses access rights and record rules.",
                "Limit to the smallest read needed and check the caller's rights first.",
            )
        elif name == "execute" and isinstance(fn, ast.Attribute) and n.args:
            if _is_dynamic_str(n.args[0]) and _sql_has_variable(n.args[0]):
                c.add(
                    HIGH,
                    "sql-injection",
                    path,
                    ln,
                    "Raw SQL built from a formatted string.",
                    "Pass parameters separately (cr.execute(query, params)) or use odoo.tools.SQL.",
                )
            else:
                c.add(
                    LOW,
                    "raw-sql",
                    path,
                    ln,
                    "Raw SQL bypasses the ORM, access rights and caches.",
                    "Use the ORM, or flush and invalidate around the query.",
                )
        elif name == "Markup" and n.args and not isinstance(n.args[0], ast.Constant):
            c.add(
                MEDIUM,
                "unsafe-markup",
                path,
                ln,
                "Markup() of non-constant text disables HTML escaping.",
                "Escape the values (markupsafe.escape / Markup(...) % values).",
            )
        if name in _DB_CALLS and id(n) in in_loop:
            c.add(
                MEDIUM,
                "query-in-loop",
                path,
                ln,
                f"{name}() inside a loop (N+1 queries).",
                "Query once before the loop and map results, or use read_group / mapped().",
            )
        if name in ("search", "search_count") and n.args and isinstance(n.args[0], ast.List):
            for e in n.args[0].elts:
                if isinstance(e, ast.Tuple) and e.elts and isinstance(_const(e.elts[0]), str):
                    searched.append((_const(e.elts[0]).split(".")[0], ln))
        if name == "ref" and n.args and isinstance(_const(n.args[0]), str):
            c.refs.append((_const(n.args[0]), path, ln))
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.Import):
            mods = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods = [n.module.split(".")[0]]
        for mname in mods:
            if mname in _BAD_MODULES:
                c.add(
                    MEDIUM,
                    "dangerous-import",
                    path,
                    n.lineno,
                    f"Imports {mname}.",
                    "Remove the import unless a reviewed integration needs it.",
                )
        if isinstance(n, ast.Name) and n.id in ("__builtins__", "builtins"):
            c.add(
                HIGH,
                "dangerous-call",
                path,
                n.lineno,
                f"Reaches {n.id} (sandbox escape).",
                "Remove builtins access.",
            )
    seen_idx = c.seen_idx
    for fname, ln in searched:
        for m, flds in c.model_fields.items():
            meta = flds.get(fname)
            if (
                m in c.new_models
                and meta
                and not meta["index"]
                and meta["type"] in ("Char", "Many2one", "Date", "Datetime", "Integer", "Selection")
                and (m, fname) not in seen_idx
                and len(seen_idx) < MAX_INDEX_FINDINGS
            ):
                seen_idx.add((m, fname))
                c.add(
                    LOW,
                    "missing-index",
                    path,
                    ln,
                    f"{m}.{fname} is searched but not indexed.",
                    f"Add index=True to {fname} if the table grows large.",
                )


# ---------------------------------------------------------------- xml / csv


def _top_fields(arch: ET.Element):
    """Arch elements, not descending into a <field>'s sub-views (they belong to the comodel)
    or into <xpath> (it targets another view's context)."""
    stack = list(arch)[::-1]
    while stack:
        el = stack.pop()
        yield el
        if el.tag not in ("field", "xpath"):
            stack.extend(list(el)[::-1])


def _audit_xml(c: _Ctx, path: str, body: bytes) -> None:
    try:
        root = _parse_xml(body)
        text = body.decode("utf-8", "replace")
    except (ET.ParseError, ValueError) as e:
        c.add(
            HIGH,
            "parse-error",
            path,
            0,
            f"XML file does not parse ({e}).",
            "Fix the XML; Odoo will fail to load this module.",
        )
        return
    for el in root.iter():
        rid = el.get("id")
        if rid and el.tag in ("record", "template", "menuitem", "report"):
            c.xmlids.add(rid if "." in rid else f"{c.module}.{rid}")
        for attr in ("ref", "parent", "action", "inherit_id", "groups"):
            val = el.get(attr)
            if val and attr != "groups":
                c.refs.append((val, path, _line_of(text, f'"{val}"')))
        for a, val in el.attrib.items():
            if a == "t-raw":
                c.add(
                    HIGH,
                    "qweb-t-raw",
                    path,
                    _line_of(text, "t-raw"),
                    "t-raw renders unescaped HTML (and was removed from Odoo 15+).",
                    "Use t-out with a Markup value built from escaped parts.",
                )
            if a in ("attrs", "states") and el.tag not in ("record",) and c.v >= 17:
                c.add(
                    HIGH,
                    "version-attrs",
                    path,
                    _line_of(text, f"{a}="),
                    f"'{a}' in views was removed in Odoo 17.",
                    "Use invisible/readonly/required expressions directly.",
                )
            if a in (
                "eval",
                "domain",
                "context",
                "filter_domain",
                "t-att",
                "t-esc",
                "t-out",
            ) and _DANGER_PY.search(val):
                c.add(
                    HIGH,
                    "unsafe-expression",
                    path,
                    _line_of(text, val[:40]),
                    f"Expression in {a} reaches Python internals or sudo.",
                    "Use only field names and literals in domains, contexts and evals.",
                )
        if (
            el.tag == "field"
            and el.get("name") in ("domain", "context", "code")
            and el.text
            and _DANGER_PY.search(el.text)
        ):
            c.add(
                HIGH,
                "unsafe-expression",
                path,
                _line_of(text, el.text.strip()[:40]),
                "Stored domain/context/code reaches Python internals or sudo.",
                "Use only field names and literals.",
            )
        if el.tag == "record" and el.get("model") in ("ir.model.access", "ir.access"):
            for f in el.findall("field"):
                if f.get("name") == "model_id" and f.get("ref"):
                    c.access.setdefault(path, set()).add(f.get("ref").split(".")[-1])
        if el.tag == "record" and el.get("model") == "ir.rule":
            for f in el.findall("field"):
                if f.get("name") == "model_id" and f.get("ref"):
                    c.rules.add(f.get("ref").split(".")[-1])
        if el.tag == "record" and el.get("model") == "ir.ui.view":
            model = next((f.text for f in el.findall("field") if f.get("name") == "model"), None)
            arch = next((f for f in el.findall("field") if f.get("name") == "arch"), None)
            if model and arch is not None:
                for sub in _top_fields(arch):
                    if sub.tag == "tree" and c.v >= 18:
                        c.add(
                            MEDIUM,
                            "version-tree",
                            path,
                            _line_of(text, "<tree"),
                            "<tree> views are renamed <list> from Odoo 18.",
                            "Rename the root tag to <list>.",
                        )
                    if sub.tag == "list" and c.v <= 17:
                        c.add(
                            HIGH,
                            "version-list",
                            path,
                            _line_of(text, "<list"),
                            "<list> views do not exist before Odoo 18.",
                            "Use <tree> on Odoo 17.",
                        )
                    if sub.tag == "field" and sub.get("name") and sub.get("position") is None:
                        c.view_fields.append(
                            (
                                model,
                                sub.get("name"),
                                path,
                                _line_of(text, f'name="{sub.get("name")}"'),
                            )
                        )
    if root.tag not in ("odoo", "openerp", "templates", "data"):
        c.add(
            LOW,
            "xml-root",
            path,
            1,
            f"Unexpected XML root <{root.tag}>.",
            "Use <odoo> as the root element.",
        )


def _audit_csv(c: _Ctx, path: str, body: bytes) -> None:
    if not path.endswith("ir.model.access.csv"):
        return
    try:
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as e:
        c.add(
            HIGH,
            "parse-error",
            path,
            0,
            f"Access file does not parse ({type(e).__name__}).",
            "Fix the CSV.",
        )
        return
    for r in rows:
        ref = (r.get("model_id:id") or "").split(".")[-1]
        if ref:
            c.access.setdefault(path, set()).add(ref)
        if not (r.get("group_id:id") or "").strip() and any(
            r.get(p) == "1" for p in ("perm_write", "perm_create", "perm_unlink")
        ):
            c.add(
                HIGH,
                "access-global-write",
                path,
                0,
                f"{r.get('id')} gives every user (no group) write/create/delete.",
                "Restrict the rule to a group.",
            )


# ---------------------------------------------------------------- module-level checks


def _audit_manifest(c: _Ctx) -> dict[str, Any] | None:
    for name in ("__manifest__.py", "__openerp__.py"):
        if name in c.files:
            try:
                m = ast.literal_eval(c.files[name].decode("utf-8-sig"))
                if not isinstance(m, dict):
                    raise ValueError
            except (ValueError, SyntaxError, UnicodeDecodeError, RecursionError):
                c.add(
                    HIGH,
                    "manifest-invalid",
                    name,
                    1,
                    "Manifest is not a plain dictionary literal.",
                    "Make __manifest__.py a single dict literal.",
                )
                return None
            return m
    c.add(
        HIGH,
        "manifest-missing",
        "",
        0,
        "No __manifest__.py: this is not an Odoo module.",
        "Add a manifest.",
    )
    return None


def _auto_xmlid(c: _Ctx, local: str) -> bool:
    """model_<x> / field_<x>__<f> ids Odoo creates for models this module defines or extends."""
    models = {m.replace(".", "_") for m in (*c.new_models, *c.inherit)}
    if local.startswith("model_"):
        return local[6:] in models
    if local.startswith("field_") and "__" in local:
        return local[6:].split("__", 1)[0] in models
    return False


def _module_checks(c: _Ctx, manifest: dict[str, Any] | None) -> None:
    if manifest:
        ver = str(manifest.get("version", ""))
        if re.match(r"^\d+\.0\.", ver) and not ver.startswith(f"{c.v}.0."):
            c.add(
                HIGH,
                "version-manifest",
                "__manifest__.py",
                1,
                f"Manifest version {ver} targets another Odoo series than {c.v}.",
                f"Port the module and set version {c.v}.0.x.y.z.",
            )
        for d in manifest.get("depends", []) or []:
            if isinstance(d, str) and caps.module_info(c.v, d) is None:
                c.add(
                    MEDIUM,
                    "depend-unknown",
                    "__manifest__.py",
                    1,
                    f"Dependency {d} is not a stock Odoo {c.v} module.",
                    "Check it exists for this version before installing.",
                )
        if manifest.get("license") in (None, ""):
            c.add(
                INFO,
                "license-missing",
                "__manifest__.py",
                1,
                "No license declared.",
                "Declare a license (e.g. LGPL-3).",
            )
    data = manifest.get("data", []) if isinstance(manifest, dict) else []
    listed = {d for d in data if isinstance(d, str)} if isinstance(data, list) else set()
    access = set().union(*(v for f, v in c.access.items() if f in listed)) if listed else set()
    for m, (path, line, _transient) in c.new_models.items():
        xid = "model_" + m.replace(".", "_")
        if m in c.abstract:
            continue
        if xid not in access:
            c.add(
                HIGH,
                "access-missing",
                path,
                line,
                f"Model {m} has no access rights: users cannot open it (or tests fail).",
                f"Add {xid} rows to security/ir.model.access.csv and list it in the manifest data.",
            )
        if "company_id" in c.model_fields.get(m, {}) and xid not in c.rules and c.v <= 19:
            c.add(
                MEDIUM,
                "rule-missing-company",
                path,
                line,
                f"Model {m} has company_id but no record rule (cross-company leak).",
                "Add a multi-company ir.rule on company_id.",
            )
    for m, (path, line) in c.inherit.items():
        if m in c.new_models:
            continue
        if caps.model_info(c.v, m) is None:
            c.add(
                HIGH,
                "version-model",
                path,
                line,
                f"Inherited model {m} does not exist in Odoo {c.v} (or is not stock).",
                "Check the model name for this version, or depend on the module defining it.",
            )
    known = {m: set(f) | _MAGIC for m, f in c.model_fields.items()}
    unresolved: set[str] = set()
    for m, parents in c.parents.items():
        for par in parents:
            if par in c.model_fields:
                known[m] |= set(c.model_fields[par])
            elif caps.model_info(c.v, par) is None:
                unresolved.add(m)

    def _via_parent(model: str, fname: str) -> bool:
        return any(caps.field_info(c.v, p, fname) for p in c.parents.get(model, ()))

    for model, fname, path, line in c.view_fields:
        if model in c.new_models:
            if (
                fname not in known.get(model, set())
                and not _via_parent(model, fname)
                and fname
                not in (
                    "message_ids",
                    "message_follower_ids",
                    "activity_ids",
                    "name",
                    "active",
                    "company_id",
                    "currency_id",
                )
            ):
                c.add(
                    LOW if model in unresolved else HIGH,
                    "field-undefined",
                    path,
                    line,
                    f"View uses {model}.{fname}, which the module does not define.",
                    "Define the field or remove it from the view.",
                )
        elif fname not in known.get(model, set()):
            info = caps.model_info(c.v, model)
            if (
                info is not None
                and fname not in info.get("fields", {})
                and caps.field_info(c.v, model, fname) is None
            ):
                c.add(
                    MEDIUM,
                    "version-field",
                    path,
                    line,
                    f"View uses {model}.{fname}, which is not a stock field in Odoo {c.v}.",
                    "Check the field name for this version.",
                )
    for ref, path, line in c.refs:
        if "." in ref:
            mod, _, _local = ref.partition(".")
            if mod == c.module and ref not in c.xmlids and not _auto_xmlid(c, _local):
                c.add(
                    HIGH,
                    "xmlid-undefined",
                    path,
                    line,
                    f"Reference to {ref}, which this module does not define (removed or renamed?).",
                    "Restore the record or update every reference before upgrading.",
                )
        elif (
            f"{c.module}.{ref}" not in c.xmlids
            and ref not in ("True", "False")
            and not _auto_xmlid(c, ref)
        ):
            c.add(
                MEDIUM,
                "xmlid-undefined",
                path,
                line,
                f"Reference to {ref}, which this module does not define in its data files.",
                "Prefix with the defining module or define the record.",
            )


# ---------------------------------------------------------------- entry point


def audit(
    src: bytes | Path,
    *,
    version: Any,
    owned_names: Iterable[str] = (),
    module_name: str | None = None,
) -> Report:
    """Audit module source for Odoo ``version``. Never raises; never executes the module."""
    if type(version) is not int or version not in VERSIONS:
        return Report(
            False, None, False, False, None, error=f"Odoo version must be one of {VERSIONS}"
        )
    try:
        files, top = load_tree(src, skip_assets=True)
    except SourceError as e:
        return Report(False, None, False, False, version, error=str(e))
    except Exception as e:  # noqa: BLE001 - fail closed
        return Report(
            False, None, False, False, version, error=f"source unreadable ({type(e).__name__})"
        )
    name = module_name or top or (src.name if isinstance(src, Path) else None)
    if not name or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return Report(False, None, False, False, version, error="module name unknown or invalid")
    owned = isinstance(owned_names, (list, tuple, set, frozenset)) and name in set(owned_names)
    c = _Ctx(files, version, owned)
    c.module = name
    try:
        manifest = _audit_manifest(c)
        for path in sorted(files):
            body = files[path]
            try:
                if path.endswith(".py"):
                    _audit_py(c, path, body)
                elif path.endswith(".xml"):
                    _audit_xml(c, path, body)
                elif path.endswith(".csv"):
                    _audit_csv(c, path, body)
            except (RecursionError, MemoryError) as e:
                c.add(
                    HIGH,
                    "parse-error",
                    path,
                    0,
                    f"File too deeply nested to audit ({type(e).__name__}).",
                    "Simplify the file; it is not a normal module source file.",
                )
        _module_checks(c, manifest)
        if (
            manifest
            and str(manifest.get("author", "")).lower().startswith("ingenium")
            and not owned
        ):
            c.add(
                INFO,
                "ownership-claimed",
                "__manifest__.py",
                1,
                "Manifest claims Ingenium authorship but the module is not in the owned registry.",
                "Treat as foreign until registered as owned.",
            )
    except Exception as e:  # noqa: BLE001 - fail closed: partial audit is not an audit
        return Report(
            False, name, owned, False, version, error=f"audit failed ({type(e).__name__})"
        )
    c.f.sort(key=lambda f: (_SEV_RANK[f.severity], f.file, f.line, f.code))
    return Report(True, name, owned, owned, version, c.f)
