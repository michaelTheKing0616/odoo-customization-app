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

from app.bots import code_audit_flow as flow
from app.bots import code_audit_web as web
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
_BAD_MODULES = frozenset(
    {"subprocess", "ctypes", "pickle", "marshal", "pty", "shelve", "socket", "dill", "runpy"}
)
_NET_MODULES = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "http.client",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc.client",
)
_QWEB_ORM = re.compile(
    r"\.sudo\s*\(|\.(?:write|create|unlink|search|search_read|search_count|browse|read_group"
    r"|with_user|execute)\s*\(|\b(?:password|password_crypt|api_key|totp_secret|signup_token)\b"
)
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
    """Skip only non-code assets: any .py is audited wherever it lives, and so are XML
    templates under static/ (OWL), JavaScript and stylesheets (code_audit_web)."""
    low = rel.lower()
    if low.endswith(".py") or web.web_kind(rel):
        return False
    parts = rel.split("/")
    if "static" in parts[:-1] and low.endswith(".xml"):
        return False
    return bool({"static", "i18n", "__pycache__"} & set(parts[:-1])) or low.endswith(_ASSET_EXT)


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


class _XmlUnavailable(ValueError):
    pass


def _parse_xml_lines(body: bytes) -> Any:
    """lxml tree whose elements carry exact source lines. Same refusal as _parse_xml (no
    DTD, no entities); lxml additionally never loads a DTD, resolves an entity or touches the
    network. Comments and processing instructions are dropped so iter() yields elements."""
    head = body[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in body.upper():
        raise ValueError("DTD/entities are not allowed")
    try:
        from lxml import etree
    except ImportError as e:  # fail closed: reported as unaudited, never skipped
        raise _XmlUnavailable("lxml is not installed; XML not audited") from e
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        remove_comments=True,
        remove_pis=True,
    )
    try:
        root = etree.fromstring(body, parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(str(e)[:200]) from e
    if root.getroottree().docinfo.doctype:
        raise ValueError("DTD/entities are not allowed")
    return root


class _XLines:
    """Exact lines for an lxml element, one of its attributes, or its text."""

    def __init__(self, text: str):
        self.text = text
        self.starts = [0]
        for m in re.finditer("\n", text):
            self.starts.append(m.end())
        self.nth: dict[int, int] | None = None  # element -> rank among same-line same-tag

    @staticmethod
    def _local(el: Any) -> str:
        return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""

    def _rank(self, el: Any) -> int:
        if self.nth is None:
            self.nth, seen = {}, {}
            for e in el.getroottree().getroot().iter():
                key = (e.sourceline, self._local(e))
                self.nth[id(e)] = seen.get(key, 0)
                seen[key] = seen.get(key, 0) + 1
        return self.nth.get(id(el), 0)

    def _tag_span(self, el: Any) -> tuple[int, int]:
        ln = getattr(el, "sourceline", None) or 1
        i = self.starts[min(ln, len(self.starts)) - 1]
        pat = re.compile("<(?:[\\w.-]+:)?" + re.escape(self._local(el)) + "(?=[\\s/>])")
        j = i
        for r in range(self._rank(el) + 1):  # siblings on one line: the n-th start tag
            m = pat.search(self.text, j + (1 if r else 0))
            if not m:
                break
            j = m.start()
        k, q = j, ""
        while k < len(self.text):
            ch = self.text[k]
            if q:
                q = "" if ch == q else q
            elif ch in "\"'":
                q = ch
            elif ch == ">":
                break
            k += 1
        return j, k

    def line(self, off: int) -> int:
        lo, hi = 0, len(self.starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.starts[mid] <= off:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def el(self, el: Any, attr: str | None = None) -> int:
        j, k = self._tag_span(el)
        if attr:
            m = re.compile("\\s" + re.escape(attr) + "\\s*=").search(self.text, j, k)
            if m:
                return self.line(m.start() + 1)
        return self.line(j)

    def body(self, el: Any, at: int = 0) -> int:
        """Line of offset `at` inside the element's text (default: its first character)."""
        t = el.text or ""
        lead = len(t) - len(t.lstrip())
        if at > lead:
            return self.body(el) + t.count("\n", lead, at)
        _, k = self._tag_span(el)
        m = re.compile("\\s*(?:<!\\[CDATA\\[\\s*)?").match(self.text, k + 1)
        return self.line(m.end() if m else k + 1)


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
        self.prod_tests: set[str] = set()  # test-dir files production code imports or loads
        self.text_fields: frozenset[str] = flow.USER_TEXT
        self.db_helpers: dict[str, str] = {}
        # (key, file, first line, kind, text) for code_audit_web: files and inline <script>s
        self.web: list[tuple[str, str, int, str, str]] = []

    def add(self, sev, code, file, line, msg, fix):
        tdir = file.startswith("tests/") or "/tests/" in file
        # test-tamper keeps its rank: test code runs inside the gate and can forge its result
        if tdir and file not in self.prod_tests and code != "test-tamper":
            sev = LOW if _SEV_RANK[sev] < _SEV_RANK[LOW] else sev  # test code never loads in prod
        if not self.owned:
            fix = f"{FOREIGN_HINT} Suggested fix: {fix}"
        self.f.append(Finding(sev, code, file, int(line or 0), msg, fix))


# ---------------------------------------------------------------- python


def _is_dynamic_str(n: ast.AST) -> bool:
    return isinstance(n, (ast.JoinedStr, ast.BinOp)) or (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("format", "join")
    )


# Constant SQL that escapes the database sandbox or reshapes name resolution: always HIGH.
_SQL_DANGER = re.compile(
    r"\bCOPY\b[\s\S]*\bPROGRAM\b|\bALTER\s+(?:DATABASE|ROLE|USER|SYSTEM)\b"
    r"|\bCREATE\s+SCHEMA\b|\bSET\s+(?:SESSION\s+|LOCAL\s+)?search_path\b"
    r"|\bset_config\s*\(\s*'search_path'|\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\b"
    r"[\s\S]*\bLANGUAGE\s+(?:plpython\w*|plperlu|c)\b|\bpg_(?:read|write)_(?:binary_)?file\b"
    r"|\blo_(?:import|export)\b|\bdblink\w*\s*\(|\bCREATE\s+EXTENSION\b"
    r"|\bSECURITY\s+DEFINER\b|\bSET\s+(?:SESSION\s+|LOCAL\s+)?ROLE\b|\bSET\s+SESSION\s+AUTHORIZATION\b"
    r"|\bCREATE\s+EVENT\s+TRIGGER\b|\bGRANT\b|\bCREATE\s+(?:ROLE|USER)\b",
    re.IGNORECASE,
)
# SQL entry points and the position of their query argument.
_SQL_CALLS = {
    "execute": 0,
    "executemany": 0,
    "copy_expert": 0,
    "mogrify": 0,
    "execute_values": 1,
    "execute_batch": 1,
}
# Test-runner internals a module could patch to turn failures into passes.
_TEST_INTERNALS = frozenset(
    {
        "OdooTestResult",
        "TestResult",
        "TextTestResult",
        "TestCase.run",
        "addFailure",
        "addError",
        "addSubTest",
        "addExpectedFailure",
        "addUnexpectedSuccess",
        "wasSuccessful",
        "_feedErrorsToResult",
        "_outcome",
        "testsRun",
        "stopTestRun",
    }
)
_TEST_MODULES = ("unittest", "odoo.tests.result", "odoo.tests.runner", "odoo.tests.loader")
_HOOK_DEFS = frozenset({"post_init_hook", "pre_init_hook", "uninstall_hook", "post_load"})


def _sql_text(n: ast.AST | None) -> str:
    """Every literal piece of a (possibly formatted) query, joined: for the danger patterns."""
    if n is None:
        return ""
    return " ".join(
        x.value for x in ast.walk(n) if isinstance(x, ast.Constant) and isinstance(x.value, str)
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


_DANGER_EXACT = frozenset(
    {
        "__import__",
        "os.system",
        "os.popen",
        "os.startfile",
        "os.fork",
        "os.forkpty",
        "os.kill",
        "os.killpg",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.removedirs",
        "os.chmod",
        "os.chown",
        "os.putenv",
        "pickle.load",
        "pickle.loads",
        "pickle.Unpickler",
        "marshal.load",
        "marshal.loads",
        "shelve.open",
        "yaml.load",
        "yaml.load_all",
        "yaml.unsafe_load",
        "yaml.unsafe_load_all",
        "yaml.full_load",
        "dill.load",
        "dill.loads",
        "code.interact",
        "builtins.eval",
        "builtins.exec",
        "builtins.compile",
        "builtins.__import__",
        "builtins.getattr",
        "builtins.open",
    }
)
_DANGER_PREFIX = (
    "os.exec",
    "os.spawn",
    "os.posix_spawn",
    "subprocess.",
    "importlib.",
    "pty.",
    "ctypes.",
    "shutil.",
    "socket.",
    "multiprocessing.",
    "runpy.",
)
_ALIAS_ROOTS = frozenset(
    {
        "os",
        "subprocess",
        "importlib",
        "builtins",
        "shutil",
        "socket",
        "ctypes",
        "pickle",
        "marshal",
        "yaml",
        "pty",
        "shelve",
        "dill",
        "code",
        "multiprocessing",
        "runpy",
    }
)


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> dotted origin for imports of risky modules (import x as y, from x import y)."""
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                root = a.name.split(".")[0]
                if root in _ALIAS_ROOTS:
                    out[a.asname or root] = a.name if a.asname else root
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            if n.module.split(".")[0] in _ALIAS_ROOTS:
                for a in n.names:
                    if a.name != "*":
                        out[a.asname or a.name] = f"{n.module}.{a.name}"
    return out


def _resolve(d: str, aliases: dict[str, str]) -> str:
    head, _, rest = d.partition(".")
    if head in aliases:
        return f"{aliases[head]}.{rest}" if rest else aliases[head]
    return d


# ---- result forging: what a module can do in-process to make failing tests look green
_ASSERT_ATTR = re.compile(
    r"^(?:assert\w*|fail|failIf\w*|failUnless\w*|failureException|_?callTestMethod|_outcome"
    r"|longMessage|skipTest|subTest|_addSkip|doCleanups|setUpClass|tearDownClass)$"
)
_CASE_ATTR = frozenset({"run", "debug", "__call__", "setUp", "tearDown", "__init__"})
_FS_WRITE = frozenset(
    {
        "write_text",
        "write_bytes",
        "touch",
        "replace",
        "rename",
        "symlink_to",
        "hardlink_to",
        "link_to",
        "unlink",
        "rmtree",
        "copyfile",
        "copy",
        "copy2",
        "move",
        "truncate",
        "chmod",
        "utime",
    }
)
_OS_WRITE = frozenset(
    {
        "write",
        "open",
        "fdopen",
        "pwrite",
        "writev",
        "rename",
        "replace",
        "remove",
        "unlink",
        "symlink",
        "link",
        "makedirs",
        "mkdir",
        "truncate",
        "ftruncate",
        "chmod",
        "utime",
        "listdir",
        "scandir",
        "walk",
    }
)
# Methods that, defined on any TestCase subclass, take over how the runner drives or reports it.
_CASE_DEF = frozenset(
    {
        "run",
        "debug",
        "__call__",
        "__init_subclass__",
        "__getattribute__",
        "_callSetUp",
        "defaultTestResult",
    }
)
# Introspection / process hooks that reach the runner's frames, objects or lifecycle.
_INTROSPECT = frozenset(
    {
        "sys._getframe",
        "sys.settrace",
        "sys.setprofile",
        "inspect.stack",
        "inspect.currentframe",
        "inspect.getouterframes",
        "gc.get_objects",
        "gc.get_referrers",
        "atexit.register",
        "os.register_at_fork",
        "threading.settrace",
        "threading.setprofile",
    }
)
_TEST_FILE = re.compile(r"^tests/(?:__init__|test_[a-z0-9_]{1,60})\.py$")
_LIST_CALLS = frozenset({"listdir", "scandir", "walk", "iterdir", "glob", "rglob", "iglob"})
_THREAD_ROOTS = ("threading", "_thread", "multiprocessing", "concurrent", "signal", "sched")
_PRIV_PATH = re.compile(r"^/(?:var/tmp|proc|tmp|dev/shm|run)(?:/|$)")


def _chain(n: ast.AST) -> str:
    parts = []
    while isinstance(n, (ast.Attribute, ast.Call, ast.Subscript)):
        if isinstance(n, ast.Attribute):
            parts.append(n.attr)
            n = n.value
        else:
            n = n.func if isinstance(n, ast.Call) else n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
    return ".".join(reversed(parts))


def _tamper_scan(c: Any, path: str, tree: ast.AST) -> None:
    """Every way found so far to neuter assertions, reach the result file or race the
    runner. Fails closed: anything matching is HIGH test-tamper, also in tests/."""

    def hit(n: ast.AST, why: str) -> None:
        c.add(
            HIGH,
            "test-tamper",
            path,
            getattr(n, "lineno", 1),
            why[:200],
            "Remove it: module code never patches tests, reaches the result path or "
            "runs background workers.",
        )

    test_names = {"unittest"}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith(
            ("odoo.tests", "unittest")
        ):
            test_names |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.Import):
            test_names |= {
                (a.asname or a.name).split(".")[0]
                for a in n.names
                if a.name.startswith(("odoo.tests", "unittest"))
            }
    if (path.startswith("tests/") or "/tests/" in path) and not _TEST_FILE.match(path):
        hit(tree, f"{path}: test files must be flat tests/__init__.py or tests/test_*.py.")
    if path == "tests/__init__.py":
        for st in getattr(tree, "body", []):
            if not (
                isinstance(st, ast.ImportFrom)
                and st.module is None
                and st.level == 1
                and all(
                    re.fullmatch(r"test_[a-z0-9_]{1,60}", a.name) and not a.asname for a in st.names
                )
            ):
                hit(st, "tests/__init__.py may only contain 'from . import test_x' lines.")
    aliases: dict[str, str] = {}  # import inspect as i / from sys import _getframe as g
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            aliases |= {a.asname: a.name for a in n.names if a.asname}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            aliases |= {(a.asname or a.name): f"{n.module}.{a.name}" for a in n.names}
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            bases = " ".join(_chain(b) for b in n.bases)
            if re.search(r"Case|Test", bases) or any(
                b.split(".")[0] in test_names for b in bases.split()
            ):
                for st in n.body:
                    if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        st.name in _CASE_DEF
                    ):
                        hit(st, f"Defines {n.name}.{st.name}: takes over the test runner.")
                    if isinstance(st, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id in _CASE_DEF for t in st.targets
                    ):
                        hit(st, f"Assigns {n.name} runner hook: takes over the test runner.")
        if isinstance(n, ast.ImportFrom) and any(
            f"{n.module}.{a.name}" in _INTROSPECT for a in n.names
        ):
            hit(n, f"Imports a frame/object/lifecycle hook from {n.module}.")
        if isinstance(n, (ast.Call, ast.Attribute)) and not isinstance(
            getattr(n, "ctx", None), ast.Store
        ):
            d0 = _resolve(_chain(n.func if isinstance(n, ast.Call) else n), aliases)
            if d0 in _INTROSPECT:
                hit(n, f"{d0}: reaches the runner's frames, objects or lifecycle.")
        targets: list[ast.AST] = []
        if isinstance(n, (ast.Assign, ast.Delete)):
            targets = list(n.targets)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            targets = [n.target]
        for t in targets:
            for e in t.elts if isinstance(t, ast.Tuple) else [t]:
                if isinstance(e, ast.Attribute):
                    d = _chain(e)
                    r0 = d.split(".")[0]
                    if (
                        _ASSERT_ATTR.match(e.attr)
                        or r0 in ("unittest", "sys")
                        or (r0 in test_names and (e.attr in _CASE_ATTR or "." in d))
                    ):
                        hit(e, f"Overrides {d or e.attr}: can turn failing tests into passes.")
                if isinstance(e, ast.Subscript) and _chain(e.value).endswith("modules"):
                    hit(e, "Writes sys.modules: can swap the test framework under the runner.")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and _PRIV_PATH.match(n.value):
            hit(n, f"Reaches {n.value[:40]!r}: the gate's result and process area.")
        if isinstance(n, ast.JoinedStr):
            head = n.values[0] if n.values else None
            if isinstance(head, ast.Constant) and _PRIV_PATH.match(str(head.value)):
                hit(n, "Builds a path under the gate's result and process area.")
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
            if any(m.split(".")[0] in _THREAD_ROOTS for m in names):
                hit(n, "Imports a thread/process/signal module: can race the test runner.")
            if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in (
                "glob",
                "shutil",
            ):
                hit(n, "Imports file listing/copy helpers.")
            if isinstance(n, ast.ImportFrom) and n.module == "os":
                bad = [a.name for a in n.names if a.name in _OS_WRITE or a.name == "*"]
                if bad:
                    hit(n, f"Imports os.{bad[0]}: raw file access.")
        if not isinstance(n, ast.Call):
            continue
        f, d = n.func, _chain(n.func)
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        args = [_const(a) for a in n.args]
        if name in ("setattr", "delattr") and len(n.args) >= 2:
            a1, tgt = args[1], _chain(n.args[0])
            on_test = tgt.split(".")[0] in test_names | {"sys"} or bool(
                re.search(r"Case|Test", tgt)
            )
            if (isinstance(a1, str) and _ASSERT_ATTR.match(a1)) or (on_test and tgt):
                hit(n, f"{name}() on {tgt or 'an object'}: can neuter assertions.")
        if name in ("patch", "object", "dict", "multiple") and ("patch" in d or "mock" in d):
            txt = " ".join(str(a) for a in args if isinstance(a, str))
            if (
                re.search(r"assert|fail|unittest|odoo\.tests|sys\.modules|TestCase", txt)
                or (name == "object" and n.args and re.search(r"Case|Test", _chain(n.args[0])))
                or name == "dict"
            ):
                hit(n, "Patches the test framework or sys.modules.")
        if d.startswith("sys.modules.") or d in ("sys.modules.update", "sys.modules.setdefault"):
            hit(n, "Changes sys.modules.")
        root = d.split(".")[0]
        if root == "os" and name in _OS_WRITE:
            hit(n, f"os.{name}(): raw file access outside the ORM.")
        if (
            isinstance(f, ast.Attribute)
            and name in _FS_WRITE
            and root not in ("self", "cls", "env", "record", "records")
        ):
            if root in ("Path", "pathlib", "shutil", "os") or "path" in d.lower():
                hit(n, f"{d}(): file system write.")
        if name in _LIST_CALLS and (
            root in ("os", "glob", "Path", "pathlib") or "path" in d.lower()
        ):
            hit(n, f"{d}(): lists files (result path discovery).")
        if root in _THREAD_ROOTS or name in ("Thread", "Timer", "start_new_thread", "Process"):
            hit(n, f"{d}(): starts a background worker.")
        if name == "open" and root in ("", "open", "io", "builtins", "codecs"):
            mode = (
                args[1]
                if len(args) > 1
                else next((_const(k.value) for k in n.keywords if k.arg == "mode"), "r")
            )
            if not isinstance(mode, str) or set(mode) & set("wax+"):
                hit(n, "open() for writing: file system write outside the ORM.")


def _py_danger(call: ast.Call, aliases: dict[str, str] | None = None) -> str:
    raw = _chain(call.func)
    d = _resolve(raw, aliases or {})
    shown = d if d == raw else f"{raw} ({d})"
    if d in _DANGER_EXACT or d.startswith(_DANGER_PREFIX):
        return f"{shown}()"
    if d == "getattr" and call.args:
        first = _resolve(_chain(call.args[0]), aliases or {})
        if first in ("__builtins__", "builtins") or (
            len(call.args) > 1
            and not isinstance(call.args[1], ast.Constant)
            and first.split(".")[0] in _ALIAS_ROOTS
        ):
            return f"getattr({first}, ...)"
    return ""


def _resolved_danger(call: ast.Call, res: flow.Resolver) -> str:
    """Dangerous targets reached through re-binding, getattr("literal"), literal dynamic
    imports, sys.modules / __builtins__ subscripts or star imports."""
    raw = _chain(call.func) or ast.unparse(call.func)[:60]
    d = res.call_target(call)
    if d and d != raw and (d in _DANGER_EXACT or d.startswith(_DANGER_PREFIX)):
        return f"{raw} ({d})()"
    return ""


def _sql_has_variable(n: ast.AST, safe: frozenset[str] = frozenset()) -> bool:
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
        if isinstance(p, ast.Constant) or (isinstance(p, ast.Name) and p.id in safe):
            continue
        if isinstance(p, (ast.JoinedStr, ast.BinOp)):
            if _sql_has_variable(p, safe):
                return True
            continue
        if isinstance(p, (ast.Tuple, ast.List, ast.Set)) and all(
            isinstance(e, ast.Constant)
            or (isinstance(e, ast.Name) and e.id in safe)
            or (isinstance(e, ast.Attribute) and e.attr == "_table")
            for e in p.elts
        ):
            continue
        if isinstance(p, ast.Attribute) and p.attr == "_table":
            continue
        return True
    return False


def _literal(v: ast.AST) -> bool:
    if isinstance(v, ast.Constant):
        return True
    return isinstance(v, ast.IfExp) and _literal(v.body) and _literal(v.orelse)


def _local_sql(tree: ast.AST) -> tuple[dict[int, ast.AST], dict[int, frozenset[str]]]:
    """execute(name) call id -> the expression assigned to ``name`` in the same scope, when that
    name has exactly one plain assignment there. Augmented assignments with a non-literal value
    resolve to the augmentation itself so ``q += name`` is still seen as dynamic."""
    out: dict[int, ast.AST] = {}
    safe_of: dict[int, frozenset[str]] = {}
    scopes = [
        tree,
        *(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)),
    ]
    for scope in scopes:
        plain: dict[str, list[ast.AST]] = {}
        aug: dict[str, list[ast.AST]] = {}
        for n in ast.walk(scope):
            if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
            ):
                plain.setdefault(n.targets[0].id, []).append(n.value)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value:
                plain.setdefault(n.target.id, []).append(n.value)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                aug.setdefault(n.target.id, []).append(
                    ast.BinOp(left=ast.Constant(""), op=n.op, right=n.value)
                )
        # names bound exactly once, to a literal (or a choice between literals)
        safe = frozenset(
            k for k, v in plain.items() if len(v) == 1 and _literal(v[0]) and k not in aug
        )
        # names whose every (re)assignment is built only from literals, safe names or itself
        # (q = 'a'; q = q + 'b'), found as a fixpoint; anything else stays dynamic
        chain = set(safe)
        changed = True
        while changed:
            changed = False
            for k in set(plain) | set(aug):
                if k in chain:
                    continue
                vals = plain.get(k, []) + aug.get(k, [])
                if all(
                    _literal(v)
                    or (_is_dynamic_str(v) and not _sql_has_variable(v, frozenset(chain | {k})))
                    for v in vals
                ):
                    chain.add(k)
                    changed = True
        safe = frozenset(chain)
        for n in ast.walk(scope):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execute"
            ) or (isinstance(n, ast.Call) and _chain(n.func).split(".")[-1] == "SQL"):
                safe_of[id(n)] = safe
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execute"
                and n.args
                and isinstance(n.args[0], ast.Name)
            ):
                nm = n.args[0].id
                dyn = [
                    a
                    for a in aug.get(nm, []) + plain.get(nm, [])
                    if _is_dynamic_str(a) and _sql_has_variable(a, safe)
                ]
                if dyn:
                    out[id(n)] = dyn[0]
                elif len(plain.get(nm, [])) == 1:
                    out[id(n)] = plain[nm][0]
    return out, safe_of


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
    # per-iteration code only: a for-loop's iterable and a comprehension's first iterable
    # run once; comprehension elements and ORM lambdas (mapped/filtered/sorted) run per item
    in_loop: set[int] = {
        id(node)
        for _, parts in flow._loop_bodies(tree)
        for node in flow._walk_parts(parts)
        if isinstance(node, ast.Call)
    }
    searched: list[tuple[str, int]] = []
    has_hook = any(
        isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (d.name in _HOOK_DEFS or d.name.endswith("_hook"))
        for d in ast.walk(tree)
    )
    aliases = _aliases(tree)
    res = flow.Resolver(tree, _ALIAS_ROOTS)
    local_sql, sql_safe = _local_sql(tree)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        ln = getattr(n, "lineno", 0)
        danger = _py_danger(n, aliases) or _resolved_danger(n, res)
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
        elif (
            name == "SQL"
            and n.args
            and _is_dynamic_str(n.args[0])
            and _sql_has_variable(n.args[0], sql_safe.get(id(n), frozenset()))
        ):
            c.add(
                HIGH,
                "sql-injection",
                path,
                ln,
                "SQL() built from a formatted string (the template must be a literal).",
                "Use SQL('... %s', value) or SQL.identifier() for names.",
            )
        elif (
            name in _SQL_CALLS
            and (isinstance(fn, ast.Attribute) or name in ("execute_values", "execute_batch"))
            and len(n.args) > _SQL_CALLS[name]
        ):
            q = local_sql.get(id(n), n.args[_SQL_CALLS[name]])
            if _is_dynamic_str(q) and _sql_has_variable(q, sql_safe.get(id(n), frozenset())):
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
        if (name in _SQL_CALLS or name == "SQL") and n.args:
            qi = _SQL_CALLS.get(name, 0)
            q = local_sql.get(id(n), n.args[qi] if len(n.args) > qi else None)
            if _SQL_DANGER.search(_sql_text(q)):
                c.add(
                    HIGH,
                    "sql-dangerous",
                    path,
                    ln,
                    "SQL runs server programs, changes database/role settings, schemas or the"
                    " search path.",
                    "Remove it: modules must never run COPY PROGRAM, ALTER DATABASE/ROLE or"
                    " change search_path.",
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
        if isinstance(n, ast.ImportFrom) and n.module and any(a.name == "*" for a in n.names):
            root = n.module.split(".")[0]
            if root in _ALIAS_ROOTS or root in _BAD_MODULES:
                c.add(
                    HIGH,
                    "dangerous-import",
                    path,
                    n.lineno,
                    f"Star import from {n.module} hides dangerous calls from review.",
                    "Import the exact names needed (never * from os/subprocess/builtins etc.).",
                )
        full = []
        if isinstance(n, ast.Import):
            full = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            full = [n.module, *(f"{n.module}.{a.name}" for a in n.names)]
        bad_t = sorted({m for m in full if m.startswith(_TEST_MODULES)})
        if bad_t:
            c.add(
                HIGH,
                "test-tamper",
                path,
                n.lineno,
                f"Imports test-runner internals ({bad_t[0]}).",
                "Tests use odoo.tests.common only; never touch the runner or result classes.",
            )
        net = sorted({m for m in full if m.startswith(_NET_MODULES)})
        if net:
            hook = path.rsplit("/", 1)[-1] in ("__init__.py", "hooks.py") or has_hook
            c.add(
                MEDIUM if hook else LOW,
                "outbound-network",
                path,
                n.lineno,
                f"Outbound network client imported ({net[0]})"
                + (" in module load/hook code." if hook else "."),
                "Network calls need a reviewed integration; never at install/load time.",
            )
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
        tn = n.attr if isinstance(n, ast.Attribute) else n.id if isinstance(n, ast.Name) else ""
        if tn in _TEST_INTERNALS:
            c.add(
                HIGH,
                "test-tamper",
                path,
                n.lineno,
                f"Touches test-result internals ({tn}): can turn failures into passes.",
                "Remove it; tests must only assert, never change how results are counted.",
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
    _tamper_scan(c, path, tree)
    sqli = {f.line for f in c.f if f.file == path and f.code == "sql-injection"}
    for h in (
        flow.taint_hits(tree, c.text_fields, res)
        + flow.loop_hits(tree, c.db_helpers)
        + flow.dynamic_hits(tree, res)
    ):
        if h.code == "tainted-sql" and h.line in sqli:
            continue  # already reported as sql-injection on that line
        c.add(h.sev, h.code, path, h.line, h.msg, h.fix)
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


def _top_fields(arch: Any):
    """Arch elements, not descending into a <field>'s sub-views (they belong to the comodel)
    or into <xpath> (it targets another view's context)."""
    stack = list(arch)[::-1]
    while stack:
        el = stack.pop()
        yield el
        if el.tag not in ("field", "xpath"):
            stack.extend(list(el)[::-1])


# Records another module owns that a module must never rewrite through an xml id.
FOREIGN_GUARDED = frozenset(
    {"ir.rule", "ir.model.access", "res.groups", "res.users", "ir.config_parameter", "ir.cron"}
)


_URL_ATTRS = frozenset({"href", "src", "action", "formaction", "data", "xlink:href", "srcdoc"})
_JS_URL = re.compile(r"^\W*j\W*a\W*v\W*a\W*s\W*c\W*r\W*i\W*p\W*t\s*:|['\"]\s*javascript:", re.I)
_EXT_URL = re.compile(r"^\s*(?:https?:)?//", re.I)
_RESOURCE_TAGS = {
    "script": "src",
    "link": "href",
    "iframe": "src",
    "object": "data",
    "embed": "src",
}


def _qweb_resources(c: _Ctx, path: str, xl: _XLines, el: Any) -> None:
    """External or computed script/style/frame sources in templates, and inline <script>
    bodies (handed to the JS parser like any static file)."""
    tag = xl._local(el)
    attr = _RESOURCE_TAGS.get(tag)
    if not attr:
        return
    lit = el.get(attr)
    dyn = next((k for k in (f"t-att-{attr}", f"t-attf-{attr}") if el.get(k) is not None), None)
    if tag == "link" and "stylesheet" not in (el.get("rel") or "stylesheet"):
        return
    if lit and _EXT_URL.search(lit):
        c.add(
            HIGH if tag in ("script", "iframe", "object", "embed") else MEDIUM,
            "qweb-external-resource",
            path,
            xl.el(el, attr),
            f"<{tag}> loads from an external host ({lit[:80]}).",
            "Bundle the asset with the module (manifest assets).",
        )
    elif dyn:
        c.add(
            MEDIUM if tag == "script" else LOW,
            "qweb-dynamic-resource",
            path,
            xl.el(el, dyn),
            f"<{tag}> source is computed ({dyn}): the host cannot be decided statically.",
            "Use a fixed, bundled asset path.",
        )
    if tag == "script" and not lit and not dyn:
        typ = (el.get("type") or "text/javascript").lower()
        if "json" in typ or "template" in typ:
            return
        # QWeb output inside the script (<t t-esc/>) becomes a neutral identifier that is
        # valid both inside a string literal and as an expression; line breaks are kept
        from lxml import etree

        parts = [el.text or ""]
        for ch in el:
            raw = etree.tostring(ch, with_tail=False, encoding="unicode")
            parts.append("__qweb__" + "\n" * raw.count("\n"))
            parts.append(ch.tail or "")
        js = "".join(parts)
        if not js.strip():
            return
        line0 = xl.line(xl._tag_span(el)[1] + 1)
        c.web.append((f"{path}#script@{line0}", path, line0, "js", js))


def _audit_xml(c: _Ctx, path: str, body: bytes) -> None:
    try:
        root = _parse_xml_lines(body)
        text = body.decode("utf-8", "replace")
        xl = _XLines(text)
    except _XmlUnavailable as e:
        c.add(HIGH, "xml-unaudited", path, 0, f"Cannot parse, unaudited ({e}).", "Install lxml.")
        return
    except ValueError as e:
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
        if (
            rid
            and el.tag == "record"
            and "." in rid
            and rid.split(".", 1)[0] != c.module
            and el.get("model") in FOREIGN_GUARDED
        ):
            c.add(
                HIGH,
                "foreign-record-edit",
                path,
                xl.el(el, "id"),
                f"Record {rid} ({el.get('model')}) belongs to another module and is rewritten "
                "here (access, rules, groups, users, parameters or crons).",
                "Create your own record instead of editing another module's.",
            )
        for attr in ("ref", "parent", "action", "inherit_id", "groups"):
            val = el.get(attr)
            if val and attr != "groups":
                c.refs.append((val, path, xl.el(el, attr)))
        for a, val in el.attrib.items():
            if a.startswith("t-") and a != "t-name" and _QWEB_ORM.search(val):
                c.add(
                    MEDIUM,
                    "qweb-orm-call",
                    path,
                    xl.el(el, a),
                    f"Template expression in {a} calls sudo()/ORM methods or reads credentials.",
                    "Compute values in Python with access checks; templates must only display.",
                )
            if a.startswith("t-") and re.search(r"\b[Mm]arkup\s*\(", val):
                c.add(
                    MEDIUM,
                    "unsafe-markup",
                    path,
                    xl.el(el, a),
                    f"Template wraps a value in markup()/Markup() in {a} (no HTML escaping).",
                    "Only mark trusted, already-escaped HTML; prefer plain t-out.",
                )
            if (a in _URL_ATTRS or (a.startswith("t-att") and a.split("-")[-1] in _URL_ATTRS)) and (
                _JS_URL.search(val)
            ):
                c.add(
                    HIGH,
                    "qweb-js-url",
                    path,
                    xl.el(el, a),
                    f"{a} holds a javascript: URL (script execution on click/load).",
                    "Use an OWL event handler (t-on-click) instead.",
                )
            if a == "t-raw":
                c.add(
                    HIGH,
                    "qweb-t-raw",
                    path,
                    xl.el(el, a),
                    "t-raw renders unescaped HTML (and was removed from Odoo 15+).",
                    "Use t-out with a Markup value built from escaped parts.",
                )
            if (
                a in ("attrs", "states")
                and el.tag not in ("record",)
                and c.v >= 17
                and not path.startswith("static/")
            ):
                c.add(
                    HIGH,
                    "version-attrs",
                    path,
                    xl.el(el, a),
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
                    xl.el(el, a),
                    f"Expression in {a} reaches Python internals or sudo.",
                    "Use only field names and literals in domains, contexts and evals.",
                )
        _qweb_resources(c, path, xl, el)
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
                xl.body(el, _DANGER_PY.search(el.text).start()),
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
            model = model.strip() if model else model
            arch = next((f for f in el.findall("field") if f.get("name") == "arch"), None)
            parent = next(
                (f.get("ref") for f in el.findall("field") if f.get("name") == "inherit_id"), None
            )
            if arch is not None and parent:
                # Inheriting view: locator fields and everything placed by xpath/positioned
                # fields belong to the parent view's model.
                for sub in _top_fields(arch):
                    if not (sub.tag == "xpath" or (sub.tag == "field" and sub.get("position"))):
                        continue
                    placed = [sub] if sub.tag == "field" else []
                    placed += [
                        x for x in _top_fields(sub) if x.tag == "field" and not x.get("position")
                    ]
                    for x in placed:
                        if x.get("name"):
                            c.view_fields.append(
                                (
                                    model or f"?{parent}",
                                    x.get("name"),
                                    path,
                                    xl.el(x, "name"),
                                )
                            )
            if model and arch is not None:
                for sub in _top_fields(arch):
                    if sub.tag == "tree" and c.v >= 18:
                        c.add(
                            MEDIUM,
                            "version-tree",
                            path,
                            xl.el(sub),
                            "<tree> views are renamed <list> from Odoo 18.",
                            "Rename the root tag to <list>.",
                        )
                    if sub.tag == "list" and c.v <= 17:
                        c.add(
                            HIGH,
                            "version-list",
                            path,
                            xl.el(sub),
                            "<list> views do not exist before Odoo 18.",
                            "Use <tree> on Odoo 17.",
                        )
                    if sub.tag == "field" and sub.get("name") and sub.get("position") is None:
                        c.view_fields.append(
                            (
                                model,
                                sub.get("name"),
                                path,
                                xl.el(sub, "name"),
                            )
                        )
    if root.tag not in ("odoo", "openerp", "templates", "data") and not path.startswith("static/"):
        c.add(
            LOW,
            "xml-root",
            path,
            1,
            f"Unexpected XML root <{root.tag}>.",
            "Use <odoo> as the root element.",
        )


# ---------------------------------------------------------------- javascript / stylesheets

_WEB_FIX = {
    "js-eval": "Never build code from strings; call functions directly.",
    "js-html-sink": "Render through OWL templates (t-out) or set textContent.",
    "js-dynamic-sink": "Render through OWL templates (t-out) or set textContent.",
    "js-markup": "Only wrap trusted, already-escaped HTML in markup().",
    "js-external-request": "Call only this Odoo server; route integrations through Python.",
    "js-dynamic-request": "Build request URLs from fixed routes on this server.",
    "js-dynamic-import": "Import modules statically through the asset bundle.",
    "js-service-worker": "Do not register service workers from a module.",
    "js-token-storage": "Keep secrets out of browser storage and cookies.",
    "js-cookie-write": "Let the server set cookies (HttpOnly).",
    "js-sensitive-model": "Do security-sensitive writes in Python with access checks.",
    "js-dynamic-model": "Call fixed model and method names.",
    "js-dynamic-call": "Call fixed model and method names.",
    "css-external-import": "Bundle the stylesheet with the module.",
    "css-external-url": "Bundle fonts and images with the module.",
    "css-dynamic-url": "Use fixed, bundled asset paths.",
    "css-exfiltration": "Remove attribute-selector or variable-driven remote loads.",
    "css-expression": "Remove script execution from stylesheets.",
}


def _audit_web(c: _Ctx) -> None:
    """JS and stylesheets through the pinned parser helper; fail closed per file."""
    todo = [w for w in c.web if w[3] not in ("unparseable", "inert")]
    for _, file, line, _, _ in (w for w in c.web if w[3] == "inert"):
        c.add(
            INFO,
            "web-unaudited",
            file,
            line,
            "Cannot parse, unaudited: Odoo's asset bundles never load this file type.",
            "Ship only the built JavaScript, or review this file by hand.",
        )
    for _, file, line, _, _ in (w for w in c.web if w[3] == "unparseable"):
        c.add(
            HIGH,
            "web-unaudited",
            file,
            line,
            "Cannot parse, unaudited: no parser for this file type.",
            "Ship plain JavaScript/CSS/SCSS/LESS, or review this file by hand.",
        )
    res = web.run([(key, kind, text) for key, _, _, kind, text in todo])
    for key, file, line0, _, _ in todo:
        r = res.get(key) if isinstance(res, dict) else None
        if r is None or not r.get("ok"):
            why = res if isinstance(res, str) else (r or {}).get("error", "no result")
            c.add(
                HIGH,
                "web-unaudited",
                file,
                line0 + max(int((r or {}).get("line") or 1), 1) - 1,
                f"Cannot parse, unaudited ({why}).",
                "Fix the syntax, or install the pinned parser (npm ci --ignore-scripts in "
                "app/bots/code_audit_js), then audit again.",
            )
            continue
        for f in r.get("findings", []):
            sev = f.get("sev") if f.get("sev") in _SEV_RANK else HIGH
            code = str(f.get("code", "web-finding"))
            c.add(
                sev,
                code,
                file,
                line0 + max(int(f.get("line") or 1), 1) - 1,
                str(f.get("msg", ""))[:300],
                _WEB_FIX.get(code, "Review this code by hand."),
            )


def _audit_csv(c: _Ctx, path: str, body: bytes) -> None:
    model = path.rsplit("/", 1)[-1][: -len(".csv")]  # Odoo loads a csv into the model it names
    if model in FOREIGN_GUARDED:
        try:
            ids = [(r.get("id") or "").strip() for r in csv.DictReader(
                io.StringIO(body.decode("utf-8-sig")))]  # fmt: skip
        except (UnicodeDecodeError, csv.Error):
            ids = []
        for rid in ids:
            if "." in rid and rid.split(".", 1)[0] != c.module:
                c.add(
                    HIGH,
                    "foreign-record-edit",
                    path,
                    0,
                    f"Row {rid} ({model}) belongs to another module and is rewritten here.",
                    "Create your own record instead of editing another module's.",
                )
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

    deps = [d for d in (manifest or {}).get("depends", []) or [] if isinstance(d, str)]
    cat = caps.load(c.v)
    foreign_dep = cat is None or any(
        (caps.module_info(c.v, d) or {}).get("edition") != "community" for d in deps
    )
    closure: set[str] = {"base", c.module}
    if cat is not None:
        for d in deps:
            closure |= caps._closure(cat, d)
        grew = True
        while grew:  # auto_install modules whose depends are all present get installed too
            grew = False
            for mname, info in cat.modules.items():
                if (
                    mname not in closure
                    and info.get("auto_install")
                    and set(info.get("depends", ())) <= closure
                ):
                    closure.add(mname)
                    grew = True
    unresolved_views: set[tuple[str, str]] = set()

    def _in_subview(model: str, fname: str) -> bool:
        """Inheriting views can place fields inside an x2many sub-view (locators such as a div
        or a field of the comodel). Accept a field that exists on any x2many comodel."""
        rows = ((cat.models.get(model) or {}).get("fields") or {}) if cat else {}
        for row in rows.values():
            if row[0] in ("one2many", "many2many") and row[1]:
                if fname in known.get(row[1], ()) or caps.field_info(c.v, row[1], fname):
                    return True
        return False

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
                    MEDIUM if model in unresolved else HIGH,
                    "field-undefined",
                    path,
                    line,
                    f"View uses {model}.{fname}, which the module does not define.",
                    "Define the field or remove it from the view.",
                )
        elif fname in _MAGIC or fname in known.get(model, set()):
            continue
        elif model.startswith("?") or caps.model_info(c.v, model) is None:
            # Never silently pass a field we cannot resolve: the model is unknown here.
            if (model, path) not in unresolved_views:
                unresolved_views.add((model, path))
                c.add(
                    MEDIUM,
                    "field-unresolved",
                    path,
                    line,
                    f"View fields on {model.lstrip('?')} cannot be checked: the model is not "
                    f"defined here or in stock Odoo {c.v} (or the view does not name its model).",
                    "Name the model on the view and depend on the module that defines it.",
                )
        else:
            fi = caps.field_info(c.v, model, fname)
            if fi is None and _in_subview(model, fname):
                continue  # placed inside a one2many/many2many sub-view of the parent view
            if fi is None:
                elsewhere = caps._versions_with(model, fname, c.v)
                code = "version-field" if elsewhere else "field-undefined"
                c.add(
                    MEDIUM if foreign_dep else HIGH,
                    code,
                    path,
                    line,
                    f"View uses {model}.{fname}, which is not defined by this module or any stock "
                    f"Odoo {c.v} module"
                    + (f" (exists in {list(elsewhere)})." if elsewhere else "."),
                    "Fix the field name for this version, or define the field.",
                )
            elif fi["modules"] and not set(fi["modules"]) & closure:
                c.add(
                    MEDIUM,
                    "field-missing-depend",
                    path,
                    line,
                    f"View uses {model}.{fname}, defined by {fi['module']}, which is not in this "
                    "module's dependencies.",
                    f"Add {fi['module']} to depends.",
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


def _is_test(rel: str) -> bool:
    return rel.startswith("tests/") or "/tests/" in rel


def _py_imports(rel: str, body: bytes, module: str, files: dict[str, bytes]) -> set[str]:
    """Module-local .py files imported by ``rel`` (relative or odoo.addons.<module> imports)."""
    try:
        tree = ast.parse(body.decode("utf-8-sig"))
    except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError, MemoryError):
        return set()
    here = rel.split("/")[:-1]
    out: set[str] = set()

    def add(parts: list[str]) -> None:
        for cand in ("/".join(parts) + ".py", "/".join([*parts, "__init__.py"])):
            if cand in files:
                out.add(cand)

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            if n.level:
                base = here[: len(here) - (n.level - 1)] if n.level > 1 else list(here)
                if n.level - 1 > len(here):
                    continue
            elif n.module and n.module.startswith(f"odoo.addons.{module}"):
                base, n_mod = [], n.module.split(".")[3:]
                add(n_mod)
                for a in n.names:
                    add([*n_mod, a.name])
                continue
            else:
                continue
            mod = n.module.split(".") if n.module else []
            add([*base, *mod])
            for a in n.names:
                add([*base, *mod, a.name])
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith(f"odoo.addons.{module}."):
                    add(a.name.split(".")[3:])
    return out


def _prod_tests(files: dict[str, bytes], module: str, manifest: dict[str, Any] | None) -> set[str]:
    """Test-directory files that production loads: imported (transitively) from non-test code,
    or listed in the manifest data/assets. These are not capped at LOW."""
    listed: set[str] = set()
    if isinstance(manifest, dict):
        for key in ("data", "demo", "qweb", "init_xml", "update_xml"):
            v = manifest.get(key)
            if isinstance(v, list):
                listed |= {x for x in v if isinstance(x, str)}
        assets = manifest.get("assets")
        if isinstance(assets, dict):
            for v in assets.values():
                for x in v if isinstance(v, list) else []:
                    vals = x if isinstance(x, (list, tuple)) else [x]
                    listed |= {y.removeprefix(f"{module}/") for y in vals if isinstance(y, str)}
    out = {f for f in listed if _is_test(f) and f in files}
    stack = [f for f in files if f.endswith(".py") and not _is_test(f)] + sorted(out)
    seen: set[str] = set()
    while stack:
        f = stack.pop()
        if f in seen or not f.endswith(".py"):
            continue
        seen.add(f)
        for g in _py_imports(f, files[f], module, files):
            if _is_test(g):
                out.add(g)
            stack.append(g)
    return out


def _module_index(files: dict[str, bytes]) -> tuple[frozenset[str], dict[str, str]]:
    """Module-wide facts for the flow checks: user-text field names (Char/Text/Html) and
    helpers that reach the database."""
    trees: dict[str, ast.AST] = {}
    for p, b in files.items():
        if p.endswith(".py"):
            try:
                trees[p] = ast.parse(b.decode("utf-8-sig"))
            except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError, MemoryError):
                continue  # reported as parse-error by _audit_py
    text = set(flow.USER_TEXT)
    for t in trees.values():
        for n in ast.walk(t):
            if (
                isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Call)
                and _chain(n.value.func) in ("fields.Char", "fields.Text", "fields.Html")
            ):
                text |= {x.id for x in n.targets if isinstance(x, ast.Name)}
    return frozenset(text), flow.module_db_helpers(trees)


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
        c.prod_tests = _prod_tests(files, name, manifest)
        c.text_fields, c.db_helpers = _module_index(files)
        for path in sorted(files):
            body = files[path]
            try:
                if path.endswith(".py"):
                    _audit_py(c, path, body)
                elif path.endswith(".xml"):
                    _audit_xml(c, path, body)
                elif path.endswith(".csv"):
                    _audit_csv(c, path, body)
                elif web.web_kind(path):
                    c.web.append(
                        (path, path, 1, web.web_kind(path), body.decode("utf-8", "replace"))
                    )
            except (RecursionError, MemoryError) as e:
                c.add(
                    HIGH,
                    "parse-error",
                    path,
                    0,
                    f"File too deeply nested to audit ({type(e).__name__}).",
                    "Simplify the file; it is not a normal module source file.",
                )
        _audit_web(c)
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
