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
import fnmatch
import io
import json
import re
import stat
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from app.bots import code_audit_flow as flow
from app.bots import code_audit_policy as policy
from app.bots import code_audit_web as web
from app.bots.versioncaps import caps

VERSIONS = (17, 18, 19, 20)
# Budget sized from measurements of all 630 stock addons (2026-10-27): the largest module is
# `web` (25.2 MB of code in 1841 files + 70 .po), the largest single file 2.7 MB
# (spreadsheet o_spreadsheet.js). A whole-module audit of `web` takes ~9 s and ~400 MB RSS, so
# every stock module is audited in full; anything past these caps is not a normal Odoo module
# and still fails closed ("source too large" / file-unaudited HIGH).
MAX_FILES, MAX_FILE, MAX_TOTAL, MAX_DEPTH, MAX_RATIO = 3000, 4_000_000, 40_000_000, 12, 100
HEAD_BYTES = 262_144  # inert files: only this much is read, for type/content sniffing
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
# inert content: never executed by Odoo, Python or the browser (served with a non-script type)
_INERT_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tif",
    ".tiff",
    ".avif",
    ".cur",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp3",
    ".mp4",
    ".webm",
    ".ogg",
    ".wav",
    ".m4a",
    ".mov",
    ".pdf",
    ".txt",
    ".md",
    ".rst",
    ".json",
    ".map",
    ".bcmap",
    ".ftl",
    ".typed",
    ".xsd",
    ".xls",
    ".xlsx",
    ".ods",
    ".odt",
    ".doc",
    ".docx",
    ".eml",
    ".gitignore",
    ".ds_store",
)
# executable code Python, the OS or the browser would run without it ever being audited
_BINARY_CODE = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".dll",
    ".wasm",
    ".node",
    ".jar",
    ".class",
    ".exe",
    ".bin",
    ".elf",
    ".whl",
    ".egg",
)
_SCRIPT_EXT = (
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".cmd",
    ".ps1",
    ".service",
    ".rules",
    ".conf",
    ".local",
    ".vimrc",
    ".pl",
    ".rb",
    ".php",
    ".lua",
    ".vbs",
)
_KEY_EXT = (".pem", ".p12", ".pfx", ".key", ".p7m", ".crt", ".cer", ".der", ".jks")
MAX_INDEX_FINDINGS = 20
MAX_PO_TOTAL = 120_000_000  # translations are audited too, on their own budget
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


def _is_po(rel: str) -> bool:
    return rel.lower().endswith((".po", ".pot"))


def _is_asset(rel: str) -> bool:
    """Skip only non-code assets: any .py is audited wherever it lives, and so are XML
    templates under static/ (OWL), JavaScript, stylesheets, SVG/HTML documents
    (code_audit_web) and translations (translated template terms render as markup)."""
    low = rel.lower()
    if low.endswith((".py", ".pyw")) or web.web_kind(rel) or _is_po(rel):
        return False
    return low.endswith(_INERT_EXT)


def _check_name(rel: str) -> None:
    if PurePosixPath(rel).name == ".module_dir":
        raise SourceError("reserved file name .module_dir in source")


def _check_local_header(data: bytes, i: zipfile.ZipInfo) -> None:
    """The local file header must carry the central directory's name: extractors that walk
    local headers (or stream the archive) would otherwise see a different file."""
    off = i.header_offset
    head = data[off : off + 30]
    if len(head) != 30 or head[:4] != b"PK\x03\x04":
        raise SourceError(f"zip local header missing: {i.filename[:80]}")
    n = int.from_bytes(head[26:28], "little")
    raw = data[off + 30 : off + 30 + n]
    want = i.orig_filename.encode("utf-8" if i.flag_bits & 0x800 else "cp437", "replace")
    if raw != want:
        raise SourceError(f"zip local header name differs from directory: {i.filename[:80]}")


def _from_zip(
    data: bytes,
    skip_assets: bool = False,
    oversized: list[str] | None = None,
    heads: dict[str, bytes] | None = None,
) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SourceError("not a valid zip archive") from e
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise SourceError("too many files")
    out: dict[str, bytes] = {}
    total = po_total = 0
    for i in infos:
        _check_local_header(data, i)  # every entry, also the ones skipped below
        if i.is_dir():
            continue
        rel = _safe_rel(i.filename)
        _check_name(rel)
        if stat.S_ISLNK(i.external_attr >> 16):
            raise SourceError(f"symlink in archive: {rel}")
        if skip_assets and _is_asset(rel):
            if heads is not None and not (
                i.compress_size and i.file_size / i.compress_size > MAX_RATIO
            ):
                with zf.open(i) as fh:
                    heads[rel] = fh.read(HEAD_BYTES)  # content sniffing of inert files
            continue
        if i.compress_size and i.file_size / i.compress_size > MAX_RATIO:
            raise SourceError(f"file too large or over-compressed: {rel}")
        if i.file_size > MAX_FILE and oversized is not None:
            oversized.append(rel)  # reported HIGH unaudited; the rest is still audited
            continue
        if i.file_size > MAX_FILE:
            raise SourceError(f"file too large or over-compressed: {rel}")
        with zf.open(i) as fh:
            body = fh.read(MAX_FILE + 1)
        if len(body) > MAX_FILE:
            raise SourceError(f"file too large: {rel}")
        if _is_po(rel):
            po_total += len(body)
            if po_total > MAX_PO_TOTAL:
                raise SourceError("archive too large")
        else:
            total += len(body)
        if total > MAX_TOTAL:
            raise SourceError("archive too large")
        if rel in out:
            raise SourceError(f"duplicate path {rel}")
        out[rel] = body
    return out


def _from_dir(
    root: Path,
    skip_assets: bool = False,
    oversized: list[str] | None = None,
    heads: dict[str, bytes] | None = None,
) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise SourceError("source directory missing or a symlink")
    out: dict[str, bytes] = {}
    total = po_total = 0
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise SourceError("directory too deep")
        for p in sorted(d.iterdir()):
            st = p.lstat()
            if stat.S_ISLNK(st.st_mode):
                kind = "dangling symlink" if not p.exists() else "symlink"
                raise SourceError(f"{kind} in source: {p.relative_to(root)}")
            if stat.S_ISDIR(st.st_mode):
                stack.append((p, depth + 1))
                continue
            if not stat.S_ISREG(st.st_mode):
                raise SourceError(f"special file in source: {p.relative_to(root)}")
            rel = _safe_rel(p.relative_to(root).as_posix())
            _check_name(rel)
            if skip_assets and _is_asset(rel):
                if heads is not None:
                    with p.open("rb") as fh:
                        heads[rel] = fh.read(HEAD_BYTES)
                continue
            if st.st_size > MAX_FILE and oversized is not None:
                oversized.append(rel)
                continue
            if st.st_size > MAX_FILE:
                raise SourceError(f"file too large: {p.relative_to(root)}")
            if _is_po(rel):
                po_total += st.st_size
            else:
                total += st.st_size
            if total > MAX_TOTAL or po_total > MAX_PO_TOTAL or len(out) >= MAX_FILES:
                raise SourceError("source too large")
            out[rel] = p.read_bytes()
    return out


def load_tree(
    src: bytes | Path,
    *,
    skip_assets: bool = False,
    oversized: list[str] | None = None,
    heads: dict[str, bytes] | None = None,
) -> tuple[dict[str, bytes], str | None]:
    """Return (module-relative files, top folder or None). The folder name never enters files.
    With `oversized`, files over MAX_FILE are listed there (top folder kept) instead of
    refusing the whole tree."""
    if isinstance(src, (bytes, bytearray)):
        files = _from_zip(bytes(src), skip_assets, oversized, heads)
    elif isinstance(src, Path):
        files = _from_dir(src, skip_assets, oversized, heads)
    else:
        raise SourceError("source must be zip bytes or a directory path")
    top = None
    every = [*files, *(oversized or [])]
    tops = {f.split("/", 1)[0] for f in every}
    if len(tops) == 1 and all("/" in f for f in every):
        top = tops.pop()
        files = {f.split("/", 1)[1]: b for f, b in files.items()}
        if heads:
            moved = {f.split("/", 1)[1]: b for f, b in heads.items() if "/" in f}
            heads.clear()
            heads.update(moved)
        if oversized:
            oversized[:] = [f.split("/", 1)[1] for f in oversized]
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
        root = _reparse_python_codec(body, parser, e)
    if root.getroottree().docinfo.doctype:
        raise ValueError("DTD/entities are not allowed")
    return root


_XML_DECL_ENC = re.compile(
    rb"""^(\xef\xbb\xbf)?<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z0-9._-]+)["']"""
)


def _reparse_python_codec(body: bytes, parser: Any, err: Exception) -> Any:
    """libxml2 builds without iconv reject aliases such as 'latin-1'. When Python knows the
    declared codec, decode with it (strict) and parse the text with the declaration's encoding
    dropped; any other failure is the original parse error (reported HIGH, never skipped)."""
    import codecs

    from lxml import etree

    m = _XML_DECL_ENC.match(body)
    if not m or "encoding" not in str(err).lower():
        raise ValueError(str(err)[:200]) from err
    try:
        codecs.lookup(m.group(2).decode())
        text = body.decode(m.group(2).decode())
    except (LookupError, UnicodeDecodeError) as e:
        raise ValueError(str(err)[:200]) from e
    text = re.sub(
        r"""^(\ufeff)?(<\?xml[^>]*?)\s+encoding\s*=\s*["'][^"']*["']""", r"\2", text, count=1
    )
    try:
        return etree.fromstring(text.encode("utf-8"), parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(str(e)[:200]) from e


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


_JSON_BAD = object()


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
        self.props_domain = False  # CA13 H3: module passes a domain prop it builds itself
        self.text_fields: frozenset[str] = flow.USER_TEXT
        self.db_helpers: dict[str, str] = {}
        self.flow_pt: frozenset[str] = frozenset()  # module-wide passthrough functions
        self.flow_sinks: dict[str, flow.Summary] = {}  # module-wide sink helpers
        # (key, file, first line, kind, text) for code_audit_web: files and inline <script>s
        self.web: list[tuple[str, str, int, str, str]] = []
        self.pycache: list[str] = []
        self.addons_dirs: list[Path] = []  # installed-module inventory: sibling addons on the path
        self.heads: dict[str, bytes] = {}  # inert assets skipped from files: first HEAD_BYTES
        self._const_cache: dict[str, dict[str, Any]] = {}

    def add(self, sev, code, file, line, msg, fix):
        tdir = file.startswith("tests/") or "/tests/" in file
        # test-tamper keeps its rank: test code runs inside the gate and can forge its result.
        # CA12 M1: exec sinks too: tests/ ship in the module and run with --test-enable on the client DB
        if tdir and file not in self.prod_tests and code not in _TEST_KEEP_RANK:
            if file.startswith("static/"):
                # j-tests-dir: JS test bundles load in browser test runs, also with
                # --test-enable on the client's DB: capped at MEDIUM, never silent
                sev = MEDIUM if _SEV_RANK[sev] < _SEV_RANK[MEDIUM] else sev
            else:
                sev = LOW if _SEV_RANK[sev] < _SEV_RANK[LOW] else sev  # test code never loads in prod
        if not self.owned:
            fix = f"{FOREIGN_HINT} Suggested fix: {fix}"
        if code == "test-tamper" and any(  # M5: one test-tamper per line (two scanners hit os.*)
            x.code == code and x.file == file and x.line == int(line or 0) for x in self.f
        ):
            return
        self.f.append(Finding(sev, code, file, int(line or 0), msg, fix))


# codes whose severity test files keep (exec sinks run wherever the test runs; tamper forges the gate)
_TEST_KEEP_RANK = frozenset(
    {"test-tamper", "dangerous-call", "safe-eval", "eval-exec", "compile-code", "outbound-network"}
)  # CA13 M1: eval/exec/compile and network clients run wherever the test runs


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
    "importlib.import_module",
    "importlib.reload",
    "importlib.__import__",
    "importlib.util.spec_from",
    "importlib.util.module_from",
    "importlib.machinery.",
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
# read-only threading helpers: no worker, no runner race (attribute writes are checked apart)
_THREAD_READ = frozenset(
    {
        "current_thread",
        "currentThread",
        "local",
        "Lock",
        "RLock",
        "Event",
        "Condition",
        "Semaphore",
        "BoundedSemaphore",
        "get_ident",
        "get_native_id",
        "main_thread",
        "active_count",
        "enumerate",
    }
)
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


_RUNNER_CLS = re.compile(
    r"(?:^|\.)(?:\w*TestCase|TestResult|\w*TestRunner|TestLoader|TestSuite|OdooSuite|Case)$"
    r"|unittest|odoo\.tests|sys\.modules|builtins"
)
_TEST_SAFE_IMPORTS = re.compile(
    r"^unittest(?:\.mock(?:\.\w+)?|\.(?:skip|skipIf|skipUnless|SkipTest|expectedFailure|mock|TestCase))?$"
)


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

    def layout(n: ast.AST, why: str) -> None:
        # generated (owned) modules must keep the gate's test layout; for foreign code it
        # is a style note, the behavioural tamper rules below stay HIGH everywhere
        if getattr(c, "owned", True):
            hit(n, why)
        else:
            c.add(
                LOW,
                "test-layout",
                path,
                getattr(n, "lineno", 1),
                why[:200],
                "Layout note only (foreign module).",
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
        layout(tree, f"{path}: test files must be flat tests/__init__.py or tests/test_*.py.")
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
                layout(st, "tests/__init__.py may only contain 'from . import test_x' lines.")
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
        if isinstance(n, (ast.Assign, ast.AugAssign)) and any(
            isinstance(t, ast.Attribute) and "current_thread" in ast.unparse(t.value)
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        ):
            hit(n, "Writes an attribute of the current thread (test-mode flags).")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and _PRIV_PATH.match(n.value):
            hit(n, f"Reaches {n.value[:40]!r}: the gate's result and process area.")
        if isinstance(n, ast.JoinedStr):
            head = n.values[0] if n.values else None
            if isinstance(head, ast.Constant) and _PRIV_PATH.match(str(head.value)):
                hit(n, "Builds a path under the gate's result and process area.")
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
            if any(
                m.split(".")[0] in _THREAD_ROOTS and m.split(".")[0] != "threading" for m in names
            ):
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
            tgt0 = _chain(n.args[0]) if n.args else ""
            if (
                re.search(r"assert|fail|unittest|odoo\.tests|sys\.modules|TestCase", txt)
                or (name == "object" and n.args and _RUNNER_CLS.search(tgt0))
                or (
                    name == "dict"
                    and (
                        not tgt0
                        or _RUNNER_CLS.search(tgt0)
                        or tgt0 in ("sys.modules", "builtins.__dict__", "globals")
                    )
                )
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
        if (root in _THREAD_ROOTS and not (root == "threading" and name in _THREAD_READ)) or (
            name in ("Thread", "Timer", "start_new_thread", "Process")
        ):
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


def _danger_refs(c: _Ctx, path: str, tree: ast.AST, res: flow.Resolver) -> None:
    """Dangerous callables used as values (stored in a list/dict/attribute, passed as a
    callback, returned) and introspection escapes (__subclasses__, __globals__, frames)."""
    parent: dict[int, ast.AST] = {}
    for p in ast.walk(tree):
        for ch in ast.iter_child_nodes(p):
            parent[id(ch)] = p
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and (n.attr in _INTRO_HIGH or n.attr in _INTRO_LOW):
            hi = n.attr in _INTRO_HIGH
            c.add(
                HIGH if hi else LOW,
                "dangerous-call" if hi else "introspection",
                path,
                n.lineno,
                f"Reaches {n.attr} (object-graph walk to builtins/frames: sandbox escape)."
                if hi
                else f"Reads {n.attr} (class hierarchy introspection).",
                "Remove interpreter introspection from module code.",
            )
        if not isinstance(n, (ast.Name, ast.Attribute)) or not isinstance(n.ctx, ast.Load):
            continue
        up = parent.get(id(n))
        if isinstance(up, ast.Attribute) or (isinstance(up, ast.Call) and up.func is n):
            continue  # part of a longer chain, or the call itself (checked as a call)
        if any(isinstance(a, ast.ExceptHandler) for a in _ancestors(n, parent)) and not isinstance(
            up, ast.Call
        ):
            continue  # except socket.timeout: a type, not a call target
        d = res.expr(n)
        raw = _chain(n)
        last = d.rsplit(".", 1)[-1]
        if (
            d in _DANGER_EXACT
            or (
                d.startswith(_DANGER_PREFIX)
                and last[:1].islower()
                and last not in ("timeout", "error", "gaierror", "herror", "path")
            )
            or (isinstance(n, ast.Name) and n.id in ("eval", "exec", "compile", "__import__"))
        ):
            c.add(
                HIGH,
                "dangerous-call",
                path,
                n.lineno,
                f"{raw or d} ({d}) is used as a value (stored, passed or returned): it can be"
                " called later under another name.",
                "Remove it; Odoo modules must not shell out, import dynamically or reach builtins.",
            )


def _ancestors(n: ast.AST, parent: dict[int, ast.AST]):
    while id(n) in parent:
        n = parent[id(n)]
        yield n


_SQL_COMPOSED = frozenset({"SQL", "Identifier", "Literal", "Placeholder", "Composed", "identifier"})


def _sql_has_variable(n: ast.AST, safe: frozenset[str] = frozenset()) -> bool:
    """True when a formatted query interpolates anything except literals, safe names, the
    model table, record ids, literal-returning methods or SQL()/psycopg2.sql objects."""
    if isinstance(n, ast.JoinedStr):
        parts = [v.value for v in n.values if isinstance(v, ast.FormattedValue)]
    elif isinstance(n, ast.BinOp):
        parts = [n.left, n.right]
    elif isinstance(n, ast.Call):
        parts = [n.func.value, *n.args, *(k.value for k in n.keywords)]  # type: ignore[attr-defined]
    else:
        return False
    return not all(_sql_safe_part(p, safe) for p in parts)


def _sql_safe_part(p: ast.AST, safe: frozenset[str]) -> bool:
    if isinstance(p, ast.Constant) or (isinstance(p, ast.Name) and p.id in safe) or _literal(p):
        return True
    if isinstance(p, ast.Attribute) and p.attr in ("_table", "id"):
        return True  # the model's own table; a record id (an integer)
    if isinstance(p, (ast.JoinedStr, ast.BinOp)):
        return not _sql_has_variable(p, safe)
    if isinstance(p, ast.IfExp):
        return _sql_safe_part(p.body, safe) and _sql_safe_part(p.orelse, safe)
    if isinstance(p, (ast.Tuple, ast.List, ast.Set)):
        return all(_sql_safe_part(e, safe) for e in p.elts)
    if isinstance(p, ast.Call):
        if not p.args and not p.keywords and "()" + _chain(p.func).rsplit(".", 1)[-1] in safe:
            return True  # self._select(): a method that only ever returns a literal
        if isinstance(p.func, (ast.Name, ast.Attribute)) and (
            _chain(p.func).rsplit(".", 1)[-1] in _SQL_COMPOSED
        ):
            return True  # odoo.tools.SQL / psycopg2.sql objects: quoted by construction
        if (
            isinstance(p.func, ast.Attribute)
            and p.func.attr in ("join", "format")
            and isinstance(p.func.value, ast.Call)
            and _chain(p.func.value.func).rsplit(".", 1)[-1] == "SQL"
        ):
            return True
    return False


def _literal(v: ast.AST) -> bool:
    if isinstance(v, ast.Constant):
        return True
    if isinstance(v, (ast.List, ast.Tuple)):
        return all(_literal(e) for e in v.elts)  # a list of literal SQL fragments
    if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Mult):
        return _literal(v.left) and isinstance(v.left, (ast.List, ast.Tuple))  # [lit] * n
    if (
        isinstance(v, ast.Call)
        and isinstance(v.func, ast.Attribute)
        and v.func.attr == "join"
        and isinstance(v.func.value, ast.Constant)
        and len(v.args) == 1
        and _literal(v.args[0])
    ):
        return True  # ' OR '.join([literal, ...])
    return isinstance(v, ast.IfExp) and _literal(v.body) and _literal(v.orelse)


def _local_sql(tree: ast.AST) -> tuple[dict[int, ast.AST], dict[int, frozenset[str]]]:
    """execute(name) call id -> the expression assigned to ``name`` in the same scope, when that
    name has exactly one plain assignment there. Augmented assignments with a non-literal value
    resolve to the augmentation itself so ``q += name`` is still seen as dynamic."""
    out: dict[int, ast.AST] = {}
    safe_of: dict[int, frozenset[str]] = {}
    lit_funcs = set()
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rets = [r for r in ast.walk(f) if isinstance(r, ast.Return)]
            if rets and all(r.value is not None and _literal(r.value) for r in rets):
                lit_funcs.add("()" + f.name)
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
                if all(_sql_safe_part(v, frozenset(chain | {k}) | lit_funcs) for v in vals):
                    chain.add(k)
                    changed = True
        safe = frozenset(chain) | lit_funcs
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
                # innermost scope wins: a module-level walk also sees other functions' names
                if dyn:
                    out[id(n)] = dyn[0]
                elif len(plain.get(nm, [])) == 1:
                    out[id(n)] = plain[nm][0]
                else:
                    out.pop(id(n), None)
    return out, safe_of


# security core: writes here change who may do what, or run code later
SENSITIVE_MODELS = policy.SENSITIVE_MODELS  # one central deny-by-default list
_SENSITIVE_WRITES = frozenset(
    {
        "write",
        "create",
        "unlink",
        "copy",
        "set_param",
        "_set_password",
        "toggle_active",
        "action_archive",
        "action_unarchive",
        "button_install",
        "button_immediate_install",
        "button_immediate_upgrade",
        "button_uninstall",
        "button_immediate_uninstall",
        "method_direct_trigger",
        "run",
    }
)
_INTRO_HIGH = frozenset(
    {
        "__subclasses__",
        "__globals__",
        "__code__",
        "__closure__",
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_back",
        "gi_frame",
        "cr_frame",
        "ag_frame",
        "tb_frame",
    }
)
_INTRO_LOW = frozenset({"__mro__", "__bases__", "__base__"})
_SERVER_CODE_MODELS = frozenset({"ir.actions.server", "ir.cron", "base.automation"})
_SUPERUSER = re.compile(r"^(?:1|SUPERUSER_ID|.*\.SUPERUSER_ID|.*user_root.*|.*user_admin.*)$")


def _elevating(n: ast.AST, malias: dict[str, str]) -> str:
    """Why call n runs with elevated rights: sudo() (also through an alias),
    with_user(superuser), env(su=True) / Environment(..., su=True)."""
    if not isinstance(n, ast.Call):
        return ""
    name = flow.call_name(n, malias)
    if name == "sudo":
        return "sudo()"
    if name == "with_user" and n.args and _SUPERUSER.match(ast.unparse(n.args[0])):
        return "with_user(superuser)"
    if any(k.arg == "su" and _const(k.value) is True for k in n.keywords):
        return "su=True"
    if name in ("Environment", "env") and len(n.args) >= 2:
        if _SUPERUSER.match(ast.unparse(n.args[1])):
            return "Environment(superuser)"
    return ""


def _sensitive_writes(
    c: _Ctx, path: str, tree: ast.AST, malias: dict[str, str], server_code: bool = False
) -> None:
    """ORM writes on the security core; HIGH when the receiver runs elevated."""
    model_vars: dict[str, str] = {}
    elev_vars: set[str] = set()
    str_consts = _str_consts(tree)
    dict_vars = {
        t.id: n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
        for t in n.targets
        if isinstance(t, ast.Name)
    }

    def env_key(y: ast.AST) -> str | None:
        if isinstance(y, ast.Subscript) and _chain(y.value).endswith("env"):
            k = _fold_str(y.slice)
            if k is None and isinstance(y.slice, ast.Name):
                k = str_consts.get(y.slice.id)
            return k
        return None

    def model_of(x: ast.AST) -> str:
        # H15: the outermost relation hop decides the receiver (search(...).mapped('user_ids'))
        r = _receiver_model(x, model_vars, env_key)
        if r is not None:
            return r
        for y in ast.walk(x):
            if (k := env_key(y)) is not None:
                return k
            if isinstance(y, ast.Name) and y.id in model_vars:
                return model_vars[y.id]
        return ""

    def elevated(x: ast.AST) -> str:
        for y in ast.walk(x):
            if why := _elevating(y, malias):
                return why
            if isinstance(y, ast.Name) and y.id in elev_vars:
                return f"{y.id} (elevated)"
        return ""

    for _ in range(2):
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1:
                t = n.targets[0]
                if isinstance(t, ast.Name):
                    if m := model_of(n.value):
                        model_vars[t.id] = m
                    if elevated(n.value):
                        elev_vars.add(t.id)
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr == "new":
            # H17: an in-memory record with privilege vals (onchange/new) on the security core
            vals = [dict_vars.get(a.id, a) if isinstance(a, ast.Name) else a for a in n.args]
            if not any(_priv_keys_in(v) for v in vals):
                continue
        elif n.func.attr not in _SENSITIVE_WRITES:
            continue
        model = model_of(n.func.value)
        if not policy.python_write_needs_l3(model):
            continue
        why = elevated(n.func.value) or ("stored server code" if server_code else "")
        sev = HIGH  # deny by default: any write on the security core needs L3 approval
        c.add(
            sev,
            "sensitive-model-write",
            path,
            n.lineno,
            f"{model}.{n.func.attr}()" + (f" with {why}" if why else "") + ": changes the"
            " security core (users, groups, rules, access, parameters, scheduled code).",
            "Do not change security records from module code; if required, check the"
            " caller's rights explicitly and never with sudo().",
        )


_SERVER_DML = re.compile(
    r"\b(?:update|delete|insert|drop|alter|truncate|create|grant|revoke|copy|vacuum|reindex)\b",
    re.I,
)


# Domain truth: T = matches every record, F = matches none, C = really constrained.
_ALWAYS_SET = frozenset({"id", "create_date", "write_date", "create_uid", "write_uid"})


def _lit(n: ast.AST):
    if isinstance(n, ast.Constant):
        return True, n.value
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant) and isinstance(n.operand.value, (int, float)):
        return True, -n.operand.value
    if isinstance(n, (ast.List, ast.Tuple)):
        vals = [_lit(e) for e in n.elts]
        return (all(v[0] for v in vals), [v[1] for v in vals])
    s = _fold_str(n)
    return (s is not None, s)


def _leaf_truth(leaf: list) -> str:
    """One (left, op, right) leaf: T/F when it holds for every / no record whatever the data."""
    (lk, left), (ok, op), (rk, right) = (_lit(e) for e in leaf)
    if not ok or not isinstance(op, str):
        return "C"
    op = op.strip().lower()
    if lk and rk and not isinstance(left, str):  # (1,'=',1) / (0,'=',1): literal on both sides
        try:
            return "T" if {"=": left == right, "==": left == right, "!=": left != right, "<>": left != right,
                           ">": left > right, ">=": left >= right, "<": left < right, "<=": left <= right}.get(op, None) else "F"
        except TypeError:
            return "C"
    if not (lk and isinstance(left, str) and rk):
        return "C"
    fld = left.split(".")[0]
    if fld in _ALWAYS_SET:  # never NULL; ids are positive
        if op in ("!=", "<>") and right in (False, None, 0, -1):
            return "T"
        if op in ("!=", "<>") and fld == "id" and isinstance(right, int) and not isinstance(right, bool) and right <= 0:
            return "T"
        if fld == "id" and isinstance(right, (int, float)) and not isinstance(right, bool) and ((op == ">" and right < 1) or (op == ">=" and right <= 1)):
            return "T"
        if op == "not in" and isinstance(right, list) and all(v in (False, None, 0) for v in right):
            return "T"
    if op == "not in" and right == []:
        return "T"
    if op == "in" and right == []:
        return "F"
    if fld == "active" and op == "in" and isinstance(right, list) and True in right and False in right:
        return "T"
    return "C"


def _domain_truth(dom: ast.AST | None, names: dict | None = None, depth: int = 0) -> str:
    """T when a domain provably matches every record (empty, tautologies such as
    ('id','!=',0) / (1,'=',1) / '|' over a tautology, built through local names, module
    constants, helper returns, expression.AND/OR or list concatenation); F when it matches
    nothing; C when it carries a real condition or is a runtime value we cannot see."""
    names = names or {}
    if dom is None:
        return "T"
    if depth > 8:
        return "C"
    if isinstance(dom, ast.Name) and dom.id in names:
        vals = {_domain_truth(v, names, depth + 1) for v in names[dom.id]}
        return vals.pop() if len(vals) == 1 else "C"
    if isinstance(dom, ast.Call):
        fn = _dotted(dom.func) if isinstance(dom.func, (ast.Name, ast.Attribute)) else ""
        last = fn.rsplit(".", 1)[-1]
        if last in ("AND", "OR") and dom.args and isinstance(dom.args[0], (ast.List, ast.Tuple)):
            parts = [_domain_truth(e, names, depth + 1) for e in dom.args[0].elts]
            if last == "AND":
                return "F" if "F" in parts else ("T" if all(p == "T" for p in parts) else "C")
            return "T" if "T" in parts else ("F" if parts and all(p == "F" for p in parts) else "C")
        if last in ("Domain", "list", "tuple") and len(dom.args) == 1:
            return _domain_truth(dom.args[0], names, depth + 1)
        if isinstance(dom.func, ast.Name) and dom.func.id in names:  # same-module helper: its returns
            return _domain_truth(ast.Name(id=dom.func.id), names, depth + 1)
        if isinstance(dom.func, ast.Attribute) and isinstance(dom.func.value, ast.Name) and dom.func.value.id in ("self", "cls") and dom.func.attr in names:
            return _domain_truth(ast.Name(id=dom.func.attr), names, depth + 1)
        return "C"
    if isinstance(dom, ast.Attribute) and dom.attr == "TRUE" and _dotted(dom).endswith("Domain.TRUE"):
        return "T"
    if isinstance(dom, ast.Attribute) and dom.attr == "FALSE" and _dotted(dom).endswith("Domain.FALSE"):
        return "F"
    if isinstance(dom, ast.BinOp) and isinstance(dom.op, ast.Add):  # list concatenation is an implicit AND
        a, b = _domain_truth(dom.left, names, depth + 1), _domain_truth(dom.right, names, depth + 1)
        return "F" if "F" in (a, b) else ("T" if a == b == "T" else "C")
    if not isinstance(dom, (ast.List, ast.Tuple)):
        return "C"
    terms: list = []
    for e in dom.elts:
        if isinstance(e, ast.Constant) and e.value in ("&", "|", "!"):
            terms.append(e.value)
        elif isinstance(e, (ast.List, ast.Tuple)) and len(e.elts) == 3:
            terms.append(_leaf_truth(list(e.elts)))
        elif isinstance(e, ast.Starred):
            terms.append(_domain_truth(e.value, names, depth + 1))
        else:
            return "C"

    pos = 0

    def take() -> str:
        nonlocal pos
        if pos >= len(terms):
            raise ValueError
        t = terms[pos]
        pos += 1
        if t == "!":
            v = take()
            return {"T": "F", "F": "T"}.get(v, "C")
        if t in ("&", "|"):
            a, b = take(), take()
            if t == "&":
                return "F" if "F" in (a, b) else ("T" if a == b == "T" else "C")
            return "T" if "T" in (a, b) else ("F" if a == b == "F" else "C")
        return t

    out = "T"
    try:
        while pos < len(terms):
            v = take()
            out = "F" if "F" in (out, v) else ("T" if out == v == "T" else "C")
    except ValueError:
        return "C"
    return out


def _domain_names(tree: ast.AST) -> dict:
    """name -> assigned values (and function name -> returned values) across a module."""
    names: dict[str, list] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.setdefault(t.id, []).append(n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            names.setdefault(n.target.id, []).append(n.value)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            names.setdefault(n.target.id, []).append(ast.BinOp(left=ast.List(elts=[]), op=ast.Add(), right=n.value))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rets = [r.value for r in ast.walk(n) if isinstance(r, ast.Return) and r.value is not None]
            if rets:
                names.setdefault(n.name, []).extend(rets)
    for n in ast.walk(tree):  # a name that is also a parameter / loop target / mutated is a runtime value
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("append", "extend", "insert", "__iadd__") and isinstance(n.func.value, ast.Name):
            names.pop(n.func.value.id, None)
        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store) and isinstance(n.value, ast.Name):
            names.pop(n.value.id, None)
        elif isinstance(n, ast.arg):
            names.pop(n.arg, None)
        elif isinstance(n, (ast.For, ast.comprehension, ast.With)):
            for t in ast.walk(getattr(n, "target", n)):
                if isinstance(t, ast.Name) and isinstance(n, (ast.For, ast.comprehension)):
                    names.pop(t.id, None)
    return names


# Recordset boundedness (CODE-AUDIT-11 root-cause inversion): a write/unlink/archive sink is
# safe only when its recordset is PROVABLY bounded. Every search is unbounded until its domain
# carries a selective leaf (or a small literal limit outside a batch loop); derived sets
# (filtered / mapped / ids / browse / _search / search_read / comprehensions) inherit.
_FULL_SELECTIONS = {
    "account.move": {"state": {"draft", "posted", "cancel"}},
    "sale.order": {"state": {"draft", "sent", "sale", "cancel", "done"}},
    "purchase.order": {"state": {"draft", "sent", "to approve", "purchase", "done", "cancel"}},
    "stock.picking": {"state": {"draft", "waiting", "confirmed", "assigned", "done", "cancel"}},
}
_SMALL_LIMIT = 1000
# CA13 H1: an exact match selects (bounds) only on a provably unique key: id, a core unique key, or a
# field the audited module declares unique (_sql_constraints / models.Constraint / models.UniqueIndex)
_CORE_UNIQUE = {
    "res.users": {"login"}, "ir.config_parameter": {"key"}, "ir.model": {"model"}, "ir.module.module": {"name"},
    "res.lang": {"code"}, "res.country": {"code"}, "res.currency": {"name"}, "ir.model.data": {"name"},
}
_MODULE_UNIQUE: set[str] = set()  # set per audit by _module_unique()
# many2one fields that never select a few records even when compared to a record id
_LOW_CARD = frozenset({"active", "company_id", "company_ids", "type", "state", "user_id", "user_ids", "create_uid",
                       "write_uid", "currency_id", "lang", "country_id", "categ_id", "uom_id"})
_ENVISH = frozenset({"env", "request", "context", "_context", "ctx", "uid", "user", "company", "companies"})


def _unique_key(model: str, fld: str) -> bool:
    return fld == "id" or fld in _CORE_UNIQUE.get(model, ()) or fld in _MODULE_UNIQUE


def _record_ids(n: ast.AST) -> bool:
    """self.ids / rec.ids: the ids of a recordset already in hand."""
    return isinstance(n, ast.Attribute) and n.attr == "ids" and isinstance(n.value, ast.Name) and n.value.id not in _ENVISH


_PROPS_DOM_RX = (
    re.compile(r"<[A-Z][\w.]*\b[^>]{0,2000}?\s(?:t-att-)?domain\s*="),  # <Comp domain=".."/>
    re.compile(r"\bprops\s*:\s*\{[^}]{0,2000}?\bdomain\s*:"),  # {Component, props: {domain}}
    re.compile(r"\.add\(\s*\w+\s*,\s*\{[^}]{0,2000}?\bdomain\s*:"),  # dialog.add(Comp, {domain})
)


def _props_domain(files: dict) -> bool:
    """CA13 H3: does the module's XML/JS hand a component a domain prop it builds itself?"""
    for f, b in files.items():
        if not f.endswith((".xml", ".js")):
            continue
        t = b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b)
        if any(rx.search(t) for rx in _PROPS_DOM_RX):
            return True
    return False


def _module_unique(files: dict) -> set[str]:
    out: set[str] = set()
    rx = re.compile(r"unique\s*\(([^)]*)\)", re.I)
    for f, b in files.items():
        if not f.endswith(".py"):
            continue
        t = b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b)
        for m in rx.finditer(t):
            cols = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
            if len(cols) == 1 and cols[0].isidentifier():  # a composite key alone does not bound
                out.add(cols[0])
    return out


def _record_id(n: ast.AST) -> bool:
    """self.id / rec.id: one record's id (not env.uid, env.company.id, self.parent_id.id)."""
    return isinstance(n, ast.Attribute) and n.attr == "id" and isinstance(n.value, ast.Name) and n.value.id not in _ENVISH
_RS_PASS = frozenset({"with_context", "sudo", "with_user", "with_company", "with_env", "with_prefetch",
                      "exists", "sorted", "filtered", "filtered_domain", "mapped", "grouped", "concat",
                      "union", "__or__", "__add__", "browse"})
_RS_SEARCH = frozenset({"search", "search_fetch", "_search", "search_read", "web_search_read", "read_group",
                        "_read_group", "search_count"})
MASS_SINKS = frozenset({"unlink", "write", "_write", "action_archive", "action_unarchive", "toggle_active",
                        "update", "sudo_write"})


def _leaf_bound(leaf: list, model: str = "", rs_unbounded: Callable[[ast.AST], str | None] | None = None) -> str:
    """B = selective (narrows to specific records), T = matches all, F = matches none,
    U = matches an unprovable / non-selective set (negations, ranges over literals, '%')."""
    t = _leaf_truth(leaf)
    if t in ("T", "F"):
        return t
    (lk, left), (ok, op), (rk, right) = (_lit(e) for e in leaf)
    if not (ok and isinstance(op, str)):
        return "U"
    op = op.strip().lower()
    if not (lk and isinstance(left, str)):  # runtime field name: only an equality on a runtime value selects
        return "U"  # CA13 H1: an unknown field cannot be proven a unique key
    fld = left.split(".")[0]
    rnode = leaf[2]
    if not rk:  # runtime value: selective unless it is itself an unbounded set / range
        for sub in ast.walk(rnode):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "range":
                return "U"
        if rs_unbounded is not None and rs_unbounded(rnode):
            return "U"
        # CA12 H1: only equality-style leaves select; an open range (<, >, <=, >=), negation or a
        # runtime like-pattern is non-selective whatever the RHS (today(), 10**9, context, count)
        # CA13 H1: and only on a unique key, or a many2one equal to one record's id; child_of/parent_of
        # with a runtime root is a whole subtree
        if op not in ("=", "==", "in"):
            return "U"
        if _unique_key(model, fld):
            return "B"
        if fld in _LOW_CARD:
            return "U"
        return "B" if (op in ("=", "==") and _record_id(rnode)) or (op == "in" and _record_ids(rnode)) else "U"
    if op in ("like", "ilike", "=like", "=ilike"):
        if isinstance(right, str) and not right.replace("%", "").replace("_", ""):
            return "T"
        # CA13 H1: a pattern selects only an exact (wildcard-free =like) unique key
        return "B" if op in ("=like", "=ilike") and isinstance(right, str) and "%" not in right and "_" not in right \
            and _unique_key(model, fld) else "U"
    if fld == "active" and op in ("=", "==", "in"):
        return "U"  # archived-or-not is a filter over (nearly) every record, not a selection
    if op in ("child_of", "parent_of"):
        return "B" if fld == "id" and op == "parent_of" else "U"  # CA13 H1: a subtree is not bounded
    if op in ("=", "==", "in"):
        vals = right if isinstance(right, list) else [right]
        full = _FULL_SELECTIONS.get(model, {}).get(fld)
        if full and {v for v in vals if isinstance(v, str)} >= full:
            return "T"
        if any(v is False or v is None for v in vals) and fld != "id":
            return "U"  # field unset: every record without a value
        return "B" if _unique_key(model, fld) else "U"  # CA13 H1: only unique keys select
    return "U"


def _domain_bound(dom: ast.AST | None, names: dict, model: str = "", depth: int = 0,
                  rs_unbounded: Callable[[ast.AST], str | None] | None = None) -> str:
    """B/F = provably bounded; T/U = matches every / an unprovable set. Unknown is U (deny)."""
    if dom is None:
        return "T"
    if depth > 8:
        return "U"
    if isinstance(dom, ast.Name):
        if dom.id not in names:
            return "U"
        selfref = lambda v: any(isinstance(q, ast.Name) and q.id == dom.id for q in ast.walk(v))  # noqa: E731
        sub = {**names, dom.id: [v for v in names[dom.id] if not selfref(v)]}  # x = f(x): the previous x
        vals = {_domain_bound(v, sub, model, depth + 1, rs_unbounded) for v in names[dom.id]}
        for v in names[dom.id]:  # x &= <selective> / x += [<selective leaf>] narrows whatever x was
            if isinstance(v, ast.BinOp) and isinstance(v.op, (ast.Add, ast.BitAnd)) and isinstance(v.left, ast.Name) \
                    and v.left.id == dom.id and _domain_bound(v.right, sub, model, depth + 1, rs_unbounded) in ("B", "F"):
                return "B"
        return "B" if vals <= {"B"} else ("F" if vals == {"F"} else ("T" if "T" in vals else "U"))
    if isinstance(dom, ast.Call):
        fn = _dotted(dom.func) if isinstance(dom.func, (ast.Name, ast.Attribute)) else ""
        last = fn.rsplit(".", 1)[-1]
        if last in ("AND", "OR") and dom.args and isinstance(dom.args[0], (ast.List, ast.Tuple)):
            parts = [_domain_bound(e, names, model, depth + 1, rs_unbounded) for e in dom.args[0].elts]
            return _and(parts) if last == "AND" else _or(parts)
        if last in ("AND", "OR") and dom.args and isinstance(dom.args[0], ast.Name) and dom.args[0].id in names:
            elts: list[ast.AST] = []  # a list built by literal + .append(): its elements
            for v in names[dom.args[0].id]:
                if isinstance(v, (ast.List, ast.Tuple)):
                    elts += v.elts
                elif isinstance(v, ast.BinOp) and isinstance(v.left, ast.Name) and v.left.id == dom.args[0].id and isinstance(v.right, ast.List):
                    elts += v.right.elts
                else:
                    return "U"
            parts = [_domain_bound(e, names, model, depth + 1, rs_unbounded) for e in elts]
            return _and(parts) if last == "AND" else _or(parts)
        if last in ("Domain", "list", "tuple") and len(dom.args) == 1:
            return _domain_bound(dom.args[0], names, model, depth + 1, rs_unbounded)
        if last == "Domain" and len(dom.args) == 3:  # Domain('field', 'op', value): one leaf
            return _leaf_bound(list(dom.args), model, rs_unbounded)
        if isinstance(dom.func, ast.Name) and dom.func.id in names:
            return _domain_bound(ast.Name(id=dom.func.id), names, model, depth + 1, rs_unbounded)
        if isinstance(dom.func, ast.Attribute) and isinstance(dom.func.value, ast.Name) and dom.func.value.id in ("self", "cls") and dom.func.attr in names:
            return _domain_bound(ast.Name(id=dom.func.attr), names, model, depth + 1, rs_unbounded)
        return "U"
    if isinstance(dom, ast.Attribute) and dom.attr in ("TRUE", "TRUE_DOMAIN", "TRUE_LEAF"):
        return "T"
    if isinstance(dom, ast.Attribute) and dom.attr in ("FALSE", "FALSE_DOMAIN", "FALSE_LEAF"):
        return "F"
    if isinstance(dom, ast.IfExp):
        return _or([_domain_bound(dom.body, names, model, depth + 1, rs_unbounded),
                    _domain_bound(dom.orelse, names, model, depth + 1, rs_unbounded)])
    if isinstance(dom, ast.BinOp) and isinstance(dom.op, ast.BitOr):
        return _or([_domain_bound(dom.left, names, model, depth + 1, rs_unbounded),
                    _domain_bound(dom.right, names, model, depth + 1, rs_unbounded)])
    if isinstance(dom, ast.BinOp) and isinstance(dom.op, (ast.Add, ast.BitAnd)):
        return _and([_domain_bound(dom.left, names, model, depth + 1, rs_unbounded),
                     _domain_bound(dom.right, names, model, depth + 1, rs_unbounded)])
    if not isinstance(dom, (ast.List, ast.Tuple)):
        return "U"
    terms: list = []
    for e in dom.elts:
        if isinstance(e, ast.Constant) and e.value in ("&", "|", "!"):
            terms.append(e.value)
        elif isinstance(e, (ast.List, ast.Tuple)) and len(e.elts) == 3:
            terms.append((_leaf_bound(list(e.elts), model, rs_unbounded), list(e.elts)))
        elif isinstance(e, ast.Starred):
            terms.append(_domain_bound(e.value, names, model, depth + 1, rs_unbounded))
        elif isinstance(e, ast.IfExp) and all(isinstance(b, (ast.List, ast.Tuple)) and len(b.elts) == 3 for b in (e.body, e.orelse)):
            terms.append(_or([_leaf_bound(list(e.body.elts), model, rs_unbounded), _leaf_bound(list(e.orelse.elts), model, rs_unbounded)]))
        elif isinstance(e, (ast.Call, ast.Name)):  # a nested Domain(...) / sub-domain
            terms.append(_domain_bound(e, names, model, depth + 1, rs_unbounded))
        else:
            return "U"
    pos = 0

    def take() -> str:
        nonlocal pos
        if pos >= len(terms):
            raise ValueError
        t = terms[pos]
        pos += 1
        if isinstance(t, tuple):
            return t[0]
        if t == "!":
            v = take()
            return {"T": "F", "F": "T"}.get(v, "U")  # '!' of a selective leaf selects the rest
        if t in ("&", "|"):
            if t == "|" and pos + 1 < len(terms) and _complementary(terms[pos], terms[pos + 1]):
                pos += 2
                return "T"  # ('active','=',True) | ('active','=',False): every record
            a, b = take(), take()
            return _and([a, b]) if t == "&" else _or([a, b])
        return t

    out: list[str] = []
    try:
        while pos < len(terms):
            out.append(take())
    except ValueError:
        return "U"
    return _and(out) if out else "T"


_NEG_OP = {"=": "!=", "!=": "=", "in": "not in", "not in": "in", "like": "not like", "not like": "like",
           "ilike": "not ilike", "not ilike": "ilike", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}


def _complementary(a: Any, b: Any) -> bool:
    """Two leaves whose OR is every record: same field, negated operators / both booleans."""
    if not (isinstance(a, tuple) and isinstance(b, tuple)):
        return False
    (lk1, f1), (ok1, o1), (rk1, v1) = (_lit(e) for e in a[1])
    (lk2, f2), (ok2, o2), (rk2, v2) = (_lit(e) for e in b[1])
    if not (lk1 and lk2 and ok1 and ok2 and isinstance(o1, str) and isinstance(o2, str) and f1 == f2):
        return False
    o1, o2 = o1.strip().lower(), o2.strip().lower()
    if o1 == o2 == "=" and rk1 and rk2 and {v1, v2} == {True, False}:
        return True
    if _NEG_OP.get(o1) == o2:
        return ast.dump(a[1][2]) == ast.dump(b[1][2])
    return False


def _and(parts: list[str]) -> str:
    if "F" in parts:
        return "F"
    if "B" in parts:
        return "B"
    return "T" if all(p == "T" for p in parts) else "U"


def _or(parts: list[str]) -> str:
    if "T" in parts:
        return "T"
    if parts and all(p == "F" for p in parts):
        return "F"
    return "B" if all(p in ("B", "F") for p in parts) else "U"


def _model_of(x: ast.AST) -> str:
    """'res.partner' for env['res.partner'] at the root of a call chain."""
    while True:
        if isinstance(x, ast.Subscript):
            s = _fold_str(x.slice)
            if s is not None:
                return s
            x = x.value
        elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute):
            x = x.func.value
        elif isinstance(x, ast.Attribute):
            x = x.value
        else:
            return ""


def _small_int(n: ast.AST | None, names: dict) -> bool:
    if isinstance(n, ast.Name) and n.id in names and len(names[n.id]) == 1:
        n = names[n.id][0]
    return (isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool)
            and 0 < n.value <= _SMALL_LIMIT)


class _Bounds:
    """Per-function recordset/domain provenance. A name resolves to the assignments that reach
    the use: preceding ones not dominated by a later assignment at the same or outer indent,
    plus the iterable of an enclosing loop. A literal limit inside a while loop batches over
    everything."""

    def __init__(self, tree: ast.AST):
        self.fn_returns: dict[str, list[ast.AST]] = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rets = [r.value for r in ast.walk(n) if isinstance(r, ast.Return) and r.value is not None]
                rets += [y.value for y in ast.walk(n) if isinstance(y, ast.Yield) and y.value is not None]
                if rets:
                    self.fn_returns.setdefault(n.name, []).extend(rets)
            elif isinstance(n, ast.Assign) and isinstance(n.value, ast.Lambda):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        self.fn_returns.setdefault(t.id, []).append(n.value.body)
        self.scopes: list[tuple[int, int, dict]] = []
        self.whiles: list[tuple[int, int]] = []
        self.module: dict[str, list[tuple[int, int, int, ast.AST]]] = {}
        self.attrs: dict[str, list[tuple[int, int, int, ast.AST]]] = {}
        self._collect(tree, self.module)
        self.rs = self.module
        self.line = 10**9

    def _put(self, rs: dict, key: str, stmt: ast.AST, value: ast.AST, end: int = 0) -> None:
        rs.setdefault(key, []).append((stmt.lineno, stmt.col_offset, end, value))

    def _collect(self, node: ast.AST, rs: dict) -> None:
        for n in ast.iter_child_nodes(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                local: dict = {}
                self.scopes.append((n.lineno, n.end_lineno or n.lineno, local))
                self._collect(n, local)
                continue
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    for s in ast.walk(t):
                        if isinstance(s, ast.Name):
                            self._put(rs, s.id, n, n.value)
                        elif isinstance(s, ast.Attribute) and isinstance(s.value, ast.Name) and s.value.id == "self":
                            self._put(self.attrs, s.attr, n, n.value)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                self._put(rs, n.target.id, n, ast.BinOp(left=n.target, op=n.op, right=n.value), end=-1)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                self._put(rs, n.target.id, n, n.value)
            elif isinstance(n, ast.NamedExpr):
                self._put(rs, n.target.id, n, n.value)
            elif isinstance(n, (ast.For, ast.AsyncFor)):
                for s in ast.walk(n.target):
                    if isinstance(s, ast.Name):
                        self._put(rs, s.id, n, n.iter, end=n.end_lineno or n.lineno)
            elif isinstance(n, ast.comprehension):
                for s in ast.walk(n.target):
                    if isinstance(s, ast.Name):
                        self._put(rs, s.id, n.iter, n.iter, end=10**9)
            elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) \
                    and n.value.func.attr in ("extend", "append", "add", "insert") and isinstance(n.value.func.value, ast.Name) and n.value.args:
                tgt = n.value.func.value
                self._put(rs, tgt.id, n, ast.BinOp(left=ast.Name(id=tgt.id), op=ast.Add(),
                                                   right=ast.List(elts=[n.value.args[-1]])), end=-1)
            if isinstance(n, ast.While):
                self.whiles.append((n.lineno, n.end_lineno or n.lineno))
            self._collect(n, rs)

    def at(self, ln: int) -> "_Bounds":
        best = None
        for a, b, d in self.scopes:
            if a <= ln <= b and (best is None or b - a < best[1] - best[0]):
                best = (a, b, d)
        view = object.__new__(_Bounds)
        view.__dict__.update(self.__dict__)
        view.rs = best[2] if best is not None else self.module
        view.line = ln
        return view

    def reaching(self, entries: list[tuple[int, int, int, ast.AST]]) -> list[ast.AST]:
        ln = self.line
        loop = [e for e in entries if e[2] > 0 and e[0] <= ln <= e[2]]
        pre = [e for e in entries if e[0] < ln and not (e[2] > 0 and not e[0] <= ln <= e[2])] or [e for e in entries if e[2] <= 0]
        live = [e for e in pre if e[2] < 0 or not any(o[0] > e[0] and o[1] <= e[1] and o[2] >= 0 for o in pre)]
        return [e[3] for e in loop + live] or [e[3] for e in entries]

    def names(self) -> dict:
        """Domain-name view for _domain_bound: reaching values of locals, then helper returns."""
        out = {k: v for k, v in self.fn_returns.items()}
        for k, v in self.module.items():
            out[k] = [e[3] for e in v]
        for k, v in self.rs.items():
            out[k] = self.reaching(v)
        return out

    def unbounded(self, x: ast.AST | None, depth: int = 0, seen: frozenset = frozenset(), data_ok: bool = False) -> str | None:
        """Why x may be every record (None when provably bounded or not a recordset). With
        data_ok, rows from search_read/read_group are plain data (dict.update, not ORM)."""
        if x is None or depth > 12:
            return None
        rec = lambda y: self.unbounded(y, depth + 1, seen, data_ok)  # noqa: E731
        if isinstance(x, ast.Name):
            if x.id in seen:
                return None
            ent = self.rs.get(x.id) or (self.module.get(x.id) if self.rs is not self.module else None)
            for v in self.reaching(ent) if ent else ():
                r = self.unbounded(v, depth + 1, seen | {x.id}, data_ok)
                if r:
                    return r
            return None
        if isinstance(x, ast.Attribute):
            if isinstance(x.value, ast.Name) and x.value.id == "self" and x.attr in self.attrs and "self." + x.attr not in seen:
                return next((r for e in self.attrs[x.attr] if (r := self.unbounded(e[3], depth + 1, seen | {"self." + x.attr}, data_ok))), None)
            return rec(x.value)  # .ids / relation of an unbounded set
        if isinstance(x, ast.Subscript):
            sl = x.slice
            if isinstance(sl, ast.Slice):
                if sl.upper is not None and _small_int(sl.upper, {}) and sl.lower is None:
                    return None
                return rec(x.value)
            if isinstance(sl, ast.Constant) and isinstance(sl.value, int):
                return None  # one record
            return rec(x.value)
        if isinstance(x, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return next((r for g in x.generators if (r := rec(g.iter))), None)
        if isinstance(x, ast.BoolOp):
            return next((r for v in x.values if (r := rec(v))), None)
        if isinstance(x, ast.IfExp):
            return rec(x.body) or rec(x.orelse)
        if isinstance(x, ast.BinOp):
            return rec(x.left) or rec(x.right)
        if isinstance(x, (ast.Await, ast.Starred)):
            return rec(x.value)
        if isinstance(x, (ast.List, ast.Tuple, ast.Set)):
            return next((r for e in x.elts if (r := rec(e))), None)
        if not isinstance(x, ast.Call):
            return None
        f = x.func
        if isinstance(f, ast.Name):
            if f.id in ("list", "set", "tuple", "sorted", "iter", "frozenset", "next") and x.args:
                return rec(x.args[0])
            if f.id in self.fn_returns and f.id not in seen:  # same-module helper / lambda: its returns
                return next((r for v in self.fn_returns[f.id] if (r := self.at(v.lineno).unbounded(v, depth + 1, seen | {f.id}, data_ok))), None)
            return None
        if not isinstance(f, ast.Attribute):
            return None
        a = f.attr
        if a in _RS_SEARCH:
            if data_ok and a in ("search_read", "web_search_read", "read_group", "search_count"):
                return None
            model = _model_of(f.value)
            dom = x.args[0] if x.args else next((k.value for k in x.keywords if k.arg in ("domain", "args")), None)
            lim = next((k.value for k in x.keywords if k.arg == "limit"), None)
            if lim is None and a in ("search", "search_fetch", "_search", "search_read") and len(x.args) >= (3 if a in ("search", "_search") else 4):
                lim = x.args[2] if a in ("search", "_search") else x.args[3]
            nm = self.names()
            batch = any(p < x.lineno <= q for p, q in self.whiles)
            if lim is not None and _small_int(lim, nm) and not batch:
                return None
            d = _domain_bound(dom, nm, model, rs_unbounded=rec)
            if d in ("B", "F"):
                return None
            why = {"T": "matches every record", "U": "is not provably selective"}[d]
            if lim is not None and not _small_int(lim, nm):
                why += "; its limit is not a small literal"
            elif lim is not None:
                why += "; a literal limit inside a while loop batches over everything"
            return f"{a}() over {model or 'a model'} whose domain {why}"
        if a in _RS_PASS:
            if a == "browse":
                return next((r for v in x.args if (r := self.unbounded(v, depth + 1, seen))), None)
            return rec(f.value) or next((r for v in x.args if not isinstance(v, ast.Lambda) and (r := rec(v))), None)
        if a in self.fn_returns and a not in seen and (
            (isinstance(f.value, ast.Name) and f.value.id in ("self", "cls")) or isinstance(f.value, (ast.Subscript, ast.Name))
        ):  # self.helper() / env['m'].helper() / Cls.helper()
            return next((r for v in self.fn_returns[a] if (r := self.at(v.lineno).unbounded(v, depth + 1, seen | {a}, data_ok))), None)
        return None


_UNBOUNDED_DML = re.compile(
    r"^\s*(?:delete\s+from\s+\"?\w+\"?\s*;?\s*$|truncate\b|drop\s+(?:table|schema|database)\b)",
    re.I,
)


def _hook_lines(path: str, tree: ast.AST) -> Callable[[int], bool]:
    """Install/uninstall hooks and migration scripts run once as the superuser, unattended."""
    if path == "hooks.py" or path.startswith(("migrations/", "upgrades/")):
        return lambda _ln: True
    spans = [
        (d.lineno, d.end_lineno or d.lineno)
        for d in ast.walk(tree)
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (d.name in _HOOK_DEFS or d.name.endswith("_hook") or d.name == "migrate")
    ]
    return lambda ln: any(a <= ln <= b for a, b in spans)


_REVERSIBLE_SINKS = frozenset({"action_archive", "action_unarchive", "toggle_active"})


def _module_models(c: _Ctx) -> frozenset[str]:
    """Models this module creates (_name not inherited) across all its Python files."""
    got = getattr(c, "_own_models", None)
    if got is None:
        names: set[str] = set()
        for f, b in c.files.items():
            if not f.endswith(".py") or f.startswith("tests/") or "/tests/" in f:
                continue
            try:
                t = ast.parse(b)
            except (SyntaxError, ValueError):
                continue
            for cls in ast.walk(t):
                if not isinstance(cls, ast.ClassDef):
                    continue
                at = {st.targets[0].id: st.value for st in cls.body if isinstance(st, ast.Assign)
                      and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)}
                nm, inh = _const(at.get("_name")), at.get("_inherit")
                inh_l = [_const(inh)] if isinstance(inh, ast.Constant) else [_const(e) for e in getattr(inh, "elts", [])]
                if isinstance(nm, str) and nm not in inh_l:
                    names.add(nm)
        got = c._own_models = frozenset(names)
    return got


def _settings_toggle(c: _Ctx, tree: ast.AST, call: ast.Call, recv: ast.AST) -> bool:
    """call sits in res.config.settings.set_values/execute and acts on env['<own model>']."""
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        at = {st.targets[0].id: st.value for st in cls.body if isinstance(st, ast.Assign)
              and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)}
        inh = at.get("_inherit")
        inh_l = [_const(inh)] if isinstance(inh, ast.Constant) else [_const(e) for e in getattr(inh, "elts", [])]
        if "res.config.settings" not in inh_l and _const(at.get("_name")) != "res.config.settings":
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in ("set_values", "execute") \
                    and fn.lineno <= call.lineno <= (fn.end_lineno or fn.lineno):
                models = {_const(x.slice) for x in ast.walk(recv) if isinstance(x, ast.Subscript)
                          and isinstance(_const(x.slice), str)}
                return len(models) == 1 and models <= _module_models(c)
    return False


def _server_code_grades(c: _Ctx, path: str, tree: ast.AST, server: bool = True) -> None:
    """Stored server/cron/automation code, hooks and migrations run unattended (as root):
    mass unlink/write over a whole model (also looping over search([])) and write-DML
    through cr.execute are HIGH. In ordinary code a mass change is MEDIUM and only an
    unbounded DELETE/TRUNCATE/DROP is HIGH."""
    hook = (lambda _ln: True) if server else _hook_lines(path, tree)
    where = "Stored server code" if server else "Hook/migration code"
    _dn = _domain_names(tree)

    bounds = _Bounds(tree)
    # CA12 L1: a destructive sink inside a loop on a fresh search() over an unbounded domain (limit=1 each
    # time) walks the whole model one record at a time: a mass change, not only a performance issue
    for lp in ast.walk(tree):
        if not isinstance(lp, (ast.For, ast.AsyncFor, ast.While)):
            continue
        local: dict[str, ast.Call] = {}
        for st in ast.walk(lp):
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                    and isinstance(st.value, ast.Call):
                local[st.targets[0].id] = st.value
        for sk in ast.walk(lp):
            if not (isinstance(sk, ast.Call) and isinstance(sk.func, ast.Attribute)
                    and sk.func.attr in MASS_SINKS - {"update"}):
                continue
            q = sk.func.value
            q = local.get(q.id, q) if isinstance(q, ast.Name) else q
            if not (isinstance(q, ast.Call) and isinstance(q.func, ast.Attribute) and q.func.attr == "search"):
                continue
            dom = q.args[0] if q.args else next((k.value for k in q.keywords if k.arg == "domain"), None)
            if _domain_bound(dom, _dn, _model_of(q.func.value)) in ("T", "U") and \
                    not any(f.code in ("mass-change", "server-mass-change") and f.file == path and f.line == sk.lineno for f in c.f):
                c.add(HIGH, "server-mass-change" if server else "mass-change", path, sk.lineno,
                      f"{sk.func.attr}() in a loop on a fresh search() whose domain is not selective: every "
                      "iteration takes another record, so the loop walks the whole model.",
                      "Act on records proven to be specific; never re-search an unbounded domain in a loop.")
    sink_alias = {  # m = getattr(rs, 'unl'+'ink') / m = rs.unlink
        t.id: (n.value.args[0], _fold_str(n.value.args[1]))
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "getattr" and len(n.value.args) >= 2 and _fold_str(n.value.args[1]) in MASS_SINKS
        for t in n.targets if isinstance(t, ast.Name)
    }
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name) and n.func.id in sink_alias:
            recv0, attr0 = sink_alias[n.func.id]
            bv = bounds.at(n.lineno)
            why = bv.unbounded(n.args[0]) if n.args else bv.unbounded(recv0)
            if why:
                c.add(HIGH, "server-mass-change" if server else "mass-change", path, n.lineno,
                      f"{attr0}() through getattr on a recordset that is not provably bounded: {why}.",
                      "Act on records proven to be specific (self / ids checked for access / a selective domain).")
            continue
        if not isinstance(n.func, ast.Attribute):
            continue
        recv, attr = n.func.value, n.func.attr
        h = hook(n.lineno)
        why = None
        if attr in MASS_SINKS and not (attr == "update" and not isinstance(recv, ast.Call)):  # dict.update
            why = bounds.at(n.lineno).unbounded(recv, data_ok=True)
        if why and not server and attr in _REVERSIBLE_SINKS and _settings_toggle(c, tree, n, recv):
            # CA12 M3: res.config.settings.set_values archiving the module's own model when the admin turns
            # the feature off (product: pricelists): admin-only, reversible, the model is the module's own
            c.add(LOW, "settings-archive", path, n.lineno,
                  f"Settings {attr}() over every record of this module's own model when the feature is toggled.",
                  "Fine when it mirrors the toggle; archive only the records the feature created if possible.")
            why = None
        if why:
            c.add(
                HIGH,
                "server-mass-change" if server else "mass-change",
                path,
                n.lineno,
                f"{where if h else 'Code'} runs {attr}() on a recordset that is not provably bounded: {why}.",
                "Act on records proven to be specific (self / ids checked for access / a selective domain"
                " with a small literal limit).",
            )
        if attr in ("execute", "execute_values", "execute_batch") and n.args:
            q = _sql_text(n.args[0]) or ast.unparse(n.args[0])
            m = _UNBOUNDED_DML.search(q)
            own = (
                not h
                and m is not None
                and not _CORE_TABLES.search(q)
                and bool(
                    re.search(rf"\b{re.escape(c.module or '#')}_\w+", q)
                    or any(mm.replace(".", "_") in q for mm in c.new_models)
                )
            )  # ordinary code clearing the module's own table (a cache/statistics table)
            if (server and _SERVER_DML.search(q)) or (m and not own):
                c.add(
                    HIGH,
                    "server-raw-dml" if server else "mass-raw-dml",
                    path,
                    n.lineno,
                    f"{where if h else 'Code'} changes the database with raw SQL"
                    + ("" if server else " over a whole table (no WHERE)")
                    + " (no access rights, no ORM, no audit trail).",
                    "Use the ORM on the intended records; never unbounded raw DML.",
                )


_AUTH_METHODS = frozenset(
    {
        "_check_credentials",
        "check_credentials",
        "check_access_rights",
        "check_access_rule",
        "check_access",
        "_check_access",
        "check_field_access_rights",
        "has_group",
        "_has_group",
        "user_has_groups",
        "has_access",
        "_compute_session_token",
        "_get_session_token_fields",
        "authenticate",
        "_login",
        "_is_admin",
        "_is_system",
        "_is_superuser",
        "_is_public",
    }
)
_SENSITIVE_FIELDS = re.compile(
    r"^(?:password|new_password|login|api_key\w*|totp_\w*|signup_token|\w*_secret|"
    r"\w*token\w*|oauth_\w*)$"
)
_PUBLIC_WRITES = frozenset({"write", "unlink", "create", "update", "sudo_write", "copy"})
_PUBLIC_READS = frozenset({"read", "search_read", "read_group", "export_data", "mapped"})


def _route_auth(f: ast.AST) -> str:
    """auth= of an @http.route / @route decorator; '' when not a route."""
    for d in getattr(f, "decorator_list", []):
        if isinstance(d, ast.Call) and _dotted(d.func).split(".")[-1] == "route":
            for k in d.keywords:
                if k.arg == "auth":
                    v = _const(k.value)
                    return v if isinstance(v, str) else "dynamic"
            return "user"
    return ""


def _auth_bypass(c: _Ctx, path: str, tree: ast.AST, malias: dict[str, str]) -> None:
    """Overriding or monkeypatching the access/authentication core, and public routes that
    write, delete or read sensitive data with elevated rights."""
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for f in cls.body:
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_auth_name(f.name) or _route_auth(f):
                continue
            sup = any(isinstance(x, ast.Call) and _dotted(x.func) == "super" for x in ast.walk(f))
            c.add(
                MEDIUM if sup else HIGH,
                "auth-override",
                path,
                f.lineno,
                f"{cls.name}.{f.name}() overrides an access/authentication check"
                + (" (calls super(); review every early return)." if sup else " without super()."),
                "Never replace access or credential checks; extend them by calling super()"
                " first and only ever adding restrictions.",
            )
    for n in ast.walk(tree):
        name = ""
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                if isinstance(t, ast.Attribute) and _is_auth_name(t.attr):
                    name = t.attr
        elif (
            isinstance(n, ast.Call)
            and _dotted(n.func) in ("setattr", "builtins.setattr", "object.__setattr__")
            and len(n.args) >= 2
        ):
            v = _fold_str(n.args[1])
            if v is not None and _is_auth_name(v):
                name = v
        if name:
            c.add(
                HIGH,
                "auth-override",
                path,
                n.lineno,
                f"Monkeypatches {name} at runtime: replaces an access/authentication check.",
                "Never patch security methods; inherit and call super() instead.",
            )
    for f in ast.walk(tree):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        auth = _route_auth(f)
        if auth not in ("public", "none", "dynamic"):
            continue
        tainted = {a.arg for a in [*f.args.args, *f.args.kwonlyargs] if a.arg != "self"}
        tainted |= {a.arg for a in (f.args.kwarg, f.args.vararg) if a is not None}
        for x in ast.walk(f):
            if isinstance(x, ast.Assign) and any(
                isinstance(y, ast.Name)
                and y.id in tainted
                or ("params" in _chain(y) if isinstance(y, ast.Attribute) else False)
                for y in ast.walk(x.value)
            ):
                tainted |= {t.id for t in x.targets if isinstance(t, ast.Name)}
        checked = any(
            isinstance(y, ast.Call)
            and re.search(r"access|consteq|_check_|_get_with_|_document_check", _dotted(y.func))
            for y in ast.walk(f)
        )  # an explicit ownership/token check before the elevated call
        for x in ast.walk(f):
            if not (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)):
                continue
            attr = x.func.attr
            if attr not in _PUBLIC_WRITES | _PUBLIC_READS:
                continue
            why = next((w for y in ast.walk(x.func.value) if (w := _elevating(y, malias))), "")
            if not why:
                continue
            used = {y.id for y in ast.walk(x) if isinstance(y, ast.Name)} & tainted
            consts = {v for y in ast.walk(x) if isinstance(v := _const(y), str)}
            sens = any(_SENSITIVE_FIELDS.match(v) for v in consts)
            model = next(
                (
                    _const(y.slice)
                    for y in ast.walk(x.func.value)
                    if isinstance(y, ast.Subscript) and isinstance(_const(y.slice), str)
                ),
                "",
            ) or _env_record_model(x.func.value)
            direct = any(
                isinstance(y, ast.Call)
                and _dotted(y.func).split(".")[-1] == "browse"
                and {z.id for z in ast.walk(y) if isinstance(z, ast.Name)} & tainted
                for y in ast.walk(x.func.value)
            ) or (
                attr == "write"
                and {z.id for a in x.args for z in ast.walk(a) if isinstance(z, ast.Name)} & tainted
            )
            if attr in _PUBLIC_WRITES and (used or model in SENSITIVE_MODELS):
                what = "with request data" if used else f"on {model}"
                sev = HIGH if (direct or model in SENSITIVE_MODELS) else MEDIUM
            elif attr in _PUBLIC_READS and (sens or model in SENSITIVE_MODELS):
                what = "of credentials/security records"
                sev = HIGH
            else:
                continue
            if sev == HIGH and model not in SENSITIVE_MODELS and checked:
                sev = MEDIUM
            c.add(
                sev,
                "public-sudo-access",
                path,
                x.lineno,
                f"auth='{auth}' route {f.name}() runs {attr}() {what} with {why}:"
                " any visitor can change or read data past access rights.",
                "Use auth='user', drop sudo(), or check the record belongs to the caller"
                " (access token) and whitelist the fields written.",
            )


def _is_auth_name(name: str) -> bool:
    return name in _AUTH_METHODS or name.startswith("_auth_method_") or name in (
        "_authenticate",
        "_authenticate_explicit",
        "_check_credentials",
        "check_credentials",
        "_check_session_validity",
        "check_session",
        "_auth_method",
        "_check_access",
        "check_access_rights",
        "check_access_rule",
        "_check_access_rights",
        "_compute_domain",
        "_compute_domain_keys",
        "domain_get",
        "_get_rules",
        "_get_failing",
    )


def _fold_str(n: ast.AST) -> str | None:
    """Constant-fold a string built from literals ('_check_'+'credentials', f'{"a"}b',
    ''.join([...]), '%s' % 'x'); None when any part is not a literal."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        a, b = _fold_str(n.left), _fold_str(n.right)
        return a + b if a is not None and b is not None else None
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):  # 'a' * 200000 padding (L1)
        for sv, iv in ((n.left, n.right), (n.right, n.left)):
            t = _fold_str(sv)
            if t is not None and isinstance(iv, ast.Constant) and isinstance(iv.value, int) and not isinstance(iv.value, bool):
                k = max(0, iv.value)
                return t * min(k, 64) + ("\u2026" if k > 64 else "")  # bounded: padding never matters to the grade
        return None
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod):
        a, b = _fold_str(n.left), _fold_str(n.right)
        try:
            return a % b if a is not None and b is not None else None
        except (TypeError, ValueError):
            return None
    if isinstance(n, ast.JoinedStr):
        out = []
        for v in n.values:
            x = _fold_str(v.value) if isinstance(v, ast.FormattedValue) else _fold_str(v)
            if x is None:
                return None
            out.append(x)
        return "".join(out)
    if (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "join"
        and len(n.args) == 1
        and isinstance(n.args[0], (ast.List, ast.Tuple))
    ):
        sep = _fold_str(n.func.value)
        parts = [_fold_str(e) for e in n.args[0].elts]
        if sep is None or any(p is None for p in parts):
            return None
        return sep.join(parts)  # type: ignore[arg-type]
    return None


def _env_record_model(n: ast.AST) -> str:
    """request.env.user / self.env.user -> res.users; env.company -> res.company."""
    for y in ast.walk(n):
        if isinstance(y, ast.Attribute) and _chain(y.value).endswith("env"):
            if y.attr in ("user", "uid"):
                return "res.users"
            if y.attr in ("company", "companies"):
                return "res.company"
    return ""


_CORE_PATCH_ROOTS = ("odoo.http", "odoo.service", "odoo.addons.base.models.ir_http", "odoo.modules", "odoo.sql_db", "odoo.api", "odoo.models", "odoo.fields", "odoo.tools", "odoo.addons")
_ASYNC_SPAWN = frozenset({"create_subprocess_shell", "create_subprocess_exec", "subprocess_shell", "subprocess_exec"})
_CORE_DML = re.compile(r"^\s*(?:UPDATE|DELETE\s+FROM|DELETE|TRUNCATE(?:\s+TABLE)?|DROP\s+TABLE|ALTER\s+TABLE|INSERT\s+INTO)\b", re.I)
# Anywhere in normalised SQL (CTE bodies, after comments): a write verb straight onto a core table.
_CORE_DML_ON = re.compile(
    r"\b(?:UPDATE(?:\s+ONLY)?|DELETE\s+FROM(?:\s+ONLY)?|TRUNCATE(?:\s+TABLE)?(?:\s+ONLY)?|DROP\s+TABLE(?:\s+IF\s+EXISTS)?|"
    r"ALTER\s+TABLE(?:\s+IF\s+EXISTS)?(?:\s+ONLY)?|INSERT\s+INTO|MERGE\s+INTO|COPY)\s+(?:\w+\.)?"
    r"(?:res_users\w*|res_groups\w*|res_company\w*|ir_\w+|auth_\w+|res_partner\w*)\b", re.I)


def _sql_norm(q: str) -> str:
    """SQL as the server parses it: comments removed, identifier quotes and schema dropped,
    whitespace collapsed (UPDATE/**/res_users, "res_users", public.res_users)."""
    q = re.sub(r"/\*.*?(?:\*/|$)", " ", q, flags=re.S)
    q = re.sub(r"--[^\n]*", " ", q)
    q = q.replace('"', "")
    q = re.sub(r"\bpublic\.", "", q, flags=re.I)
    return re.sub(r"\s+", " ", q)


def _odoo_imports(tree: ast.AST) -> dict[str, str]:
    """Local name -> dotted origin for odoo imports (from odoo import http; import odoo.http as h)."""
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] == "odoo":
                    out[a.asname or "odoo"] = a.name if a.asname else "odoo"
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            if n.module.split(".")[0] == "odoo":
                for a in n.names:
                    if a.name != "*":
                        out[a.asname or a.name] = f"{n.module}.{a.name}"
    return out


_SESSION_AUTH = frozenset({"uid", "pre_uid", "session_token", "login", "db", "pre_login"})


_CONST_DEPTH = 4


def _key_shape(n: ast.AST | None, consts: dict[str, Any]) -> list[str | None] | None:
    """Literal skeleton of a string expression: str parts are fixed, None is any text.
    None when nothing about the value is known."""
    if n is None:
        return None
    v = _fold_str(n)
    if v is not None:
        return [v]
    if isinstance(n, ast.Name):
        k = consts.get(n.id)
        if isinstance(k, str):
            return [k]
        return None
    if isinstance(n, ast.JoinedStr):
        out: list[str | None] = []
        for p in n.values:
            if isinstance(p, ast.FormattedValue):
                sh = _key_shape(p.value, consts)
                out += sh if sh is not None else [None]
            else:
                out += [_fold_str(p)]
        return out
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        a, b = _key_shape(n.left, consts), _key_shape(n.right, consts)
        return (a or [None]) + (b or [None])
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod):
        f = _key_shape(n.left, consts)
        if f and len(f) == 1 and isinstance(f[0], str):
            return [x if i % 2 == 0 else None for i, x in enumerate(re.split(r"(%[-#0 +]*\d*(?:\.\d+)?[sdirfx])", f[0]))]
        return None
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format":
        f = _key_shape(n.func.value, consts)
        if f and len(f) == 1 and isinstance(f[0], str):
            return [x if i % 2 == 0 else None for i, x in enumerate(re.split(r"(\{[^{}]*\})", f[0]))]
    return None


def _shape_may_be(shape: list[str | None], keys: Iterable[str]) -> list[str]:
    """Keys the skeleton could evaluate to."""
    rx = re.compile("".join(re.escape(x) if isinstance(x, str) else ".*" for x in shape), re.S)
    return [k for k in keys if rx.fullmatch(k)]


def _module_consts(tree: ast.AST) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Module-level names bound once to a foldable string, and names it imports (name -> (module, attr))."""
    consts = {k: v for k, v in _str_consts(ast.Module(body=[n for n in getattr(tree, "body", []) if isinstance(n, ast.Assign)], type_ignores=[])).items()}
    imports: dict[str, tuple[str, str]] = {}
    for n in getattr(tree, "body", []):
        if isinstance(n, ast.ImportFrom):
            mod = "." * n.level + (n.module or "")
            for a in n.names:
                imports[a.asname or a.name] = (mod, a.name)
    return consts, imports


def _abs_module(c: _Ctx, path: str, mod: str) -> str:
    """Dotted absolute module for an import written in module file ``path``."""
    if not mod.startswith("."):
        return mod
    lvl = len(mod) - len(mod.lstrip("."))
    pkg = ["odoo", "addons", c.module, *path.rsplit(".", 1)[0].split("/")]
    pkg = pkg[:-1] if pkg[-1] != "__init__" else pkg[:-1]
    base = pkg[: len(pkg) - (lvl - 1)] if lvl > 1 else pkg
    rest = mod.lstrip(".")
    return ".".join(base + ([rest] if rest else []))


def _module_source(c: _Ctx, dotted: str) -> tuple[str, bytes] | None:
    """Source of an odoo.addons.* module: the audited module's own files, else a sibling
    addon in the installed inventory. Bounded: one file, MAX_FILE."""
    parts = dotted.split(".")
    if parts[:2] != ["odoo", "addons"] or len(parts) < 3:
        return None
    m, rest = parts[2], parts[3:]
    for rel in ("/".join(rest) + ".py" if rest else None, "/".join([*rest, "__init__.py"])):
        if rel is None:
            continue
        if m == c.module:
            if rel in c.files:
                return rel, c.files[rel]
            continue
        for d in c.addons_dirs:
            f = d / m / rel
            try:
                if f.is_file() and not f.is_symlink() and f.stat().st_size <= MAX_FILE:
                    return f"{m}/{rel}", f.read_bytes()
            except OSError:
                return None
    return None


def _resolve_const(c: _Ctx, path: str, tree_or_none: ast.AST | None, name: str, depth: int = 0) -> str | None:
    """Follow ``name`` through module constants and from-imports (own module or installed addons)."""
    if depth > _CONST_DEPTH:
        return None
    key = f"{path}"
    info = c._const_cache.get(key)
    if info is None:
        tree = tree_or_none
        if tree is None:
            body = c.files.get(path)
            try:
                tree = ast.parse(body) if body is not None else None
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                tree = None
        info = dict(zip(("consts", "imports"), _module_consts(tree))) if tree is not None else {"consts": {}, "imports": {}}
        c._const_cache[key] = info
    if name in info["consts"]:
        return info["consts"][name]
    if name not in info["imports"]:
        return None
    mod, attr = info["imports"][name]
    dotted = _abs_module(c, path, mod) if not path.startswith("@") else mod
    got = _module_source(c, dotted)
    if got is None:
        return None
    rel, body = got
    own = rel in c.files and c.files[rel] is body
    p2 = rel if own else "@" + rel
    if p2 not in c._const_cache:
        try:
            t2 = ast.parse(body)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return None
        consts, imports = _module_consts(t2)
        if not own:  # re-express relative imports of a foreign addon absolutely
            m = rel.split("/", 1)[0]
            fake = rel.split("/", 1)[1]
            saved = c.module
            c.module = m
            imports = {k: (_abs_module(c, fake, v[0]), v[1]) for k, v in imports.items()}
            c.module = saved
        c._const_cache[p2] = {"consts": consts, "imports": imports}
    return _resolve_const(c, p2, None, attr, depth + 1)


def _core_patches(c: _Ctx, path: str, tree: ast.AST) -> None:
    """H2/H3/H5/H6 of review 5: non-literal setattr on an imported Odoo class, assignments
    into odoo.http/odoo.service internals, literal DML on core tables anywhere, and asyncio
    subprocess spawns."""
    imp = _odoo_imports(tree)
    spawn_alias = {
        a.asname or a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "asyncio"
        for a in n.names
        if a.name in _ASYNC_SPAWN
    }

    sql_vars = {
        t.id: n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    }

    def origin(x: ast.AST) -> str:
        d = _dotted(x)
        head, _, rest = d.partition(".")
        if head in imp:
            return f"{imp[head]}.{rest}" if rest else imp[head]
        return d

    sess_alias = {
        t.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and origin(n.value) == "odoo.http.request.session"
        for t in n.targets
        if isinstance(t, ast.Name)
    }

    def is_session(x: ast.AST) -> bool:
        return origin(x) == "odoo.http.request.session" or (isinstance(x, ast.Name) and x.id in sess_alias)

    sconsts = _str_consts(tree)
    # loop variables over literal string collections: `for key in ('a', 'b')`
    loop_vals: dict[str, list[str]] = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Name):
            it = n.iter
            if isinstance(it, (ast.Tuple, ast.List, ast.Set)):
                vals = [_fold_str(e) for e in it.elts]
                if all(v is not None for v in vals):
                    loop_vals.setdefault(n.target.id, []).extend(vals)  # type: ignore[arg-type]
                    continue
            loop_vals[n.target.id] = loop_vals.get(n.target.id, []) + [None]  # type: ignore[list-item]

    class _Key:
        __slots__ = ("hits", "why")

        def __init__(self, hits: list[str], why: str):
            self.hits, self.why = hits, why

    def skey(x: ast.AST | None) -> "_Key":
        """Which identity keys x could be. hits=[] and why='' means provably none."""
        if x is None:
            return _Key([], "no key")
        consts = dict(sconsts)
        names = {y.id for y in ast.walk(x) if isinstance(y, ast.Name)}
        unresolved = []
        for nm in names:
            if nm in consts:
                continue
            if nm in loop_vals and None not in loop_vals[nm]:
                continue
            v = _resolve_const(c, path, tree, nm)
            if v is not None:
                consts[nm] = v
            else:
                unresolved.append(nm)
        if isinstance(x, ast.Name) and x.id in loop_vals and None not in loop_vals[x.id]:
            hits = [k for k in loop_vals[x.id] if k in _SESSION_AUTH]
            return _Key(hits, "")
        shape = _key_shape(x, consts)
        if shape is None:
            return _Key(sorted(_SESSION_AUTH), f"key from runtime data ({', '.join(sorted(unresolved)) or ast.unparse(x)[:40]})")
        hits = _shape_may_be(shape, _SESSION_AUTH)
        if hits and any(p is None for p in shape):
            return _Key(hits, f"key pattern {''.join(p if isinstance(p, str) else '*' for p in shape)!r} built from runtime data")
        return _Key(hits, "")

    def sess_auth_write(line: int, key: "_Key | str | None") -> None:
        if isinstance(key, str):
            key = _Key([key] if key in _SESSION_AUTH else [], "")
        elif key is None:
            key = _Key(sorted(_SESSION_AUTH), "key from runtime data")
        if not key.hits:
            return
        # unknowable only when the key really is runtime data (request args, parameters): the
        # constant tables of this module and installed addons were already followed
        if key.why:
            c.add(MEDIUM, "session-auth-write", path, line,
                  f"Writes request.session[<runtime key>]: {key.why}; could be {'/'.join(key.hits[:3])}.",
                  "Use a literal or constant key; identity must only change through request.session.authenticate().")  # fmt: skip
            return
        c.add(HIGH, "session-auth-write", path, line,
              f"Writes request.session[{key.hits[0]!r}]: sets who the request is authenticated as.",
              "Authenticate through request.session.authenticate(); never set identity by hand.")  # fmt: skip

    for n in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(n, ast.Assign):
            targets = list(n.targets)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            targets = [n.target]
        for t in targets:
            # H13: request.session['uid'] = ... (also through an alias of request.session)
            if isinstance(t, ast.Subscript) and is_session(t.value):
                sess_auth_write(n.lineno, skey(t.slice))
                continue
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in sess_alias:
                if t.attr in _SESSION_AUTH:
                    sess_auth_write(n.lineno, t.attr)
                continue
            if isinstance(t, ast.Attribute):
                o = origin(t.value)
                if o == "odoo.http.request" or o.startswith("odoo.http.request."):
                    # per-request state (request.pricelist, session.debug) is not a patch; the
                    # identity of the request is: session uid/token/db/login, request env/uid
                    sess = o == "odoo.http.request.session"
                    if (sess and t.attr in _SESSION_AUTH) or (o == "odoo.http.request" and t.attr in ("session", "env", "uid")):
                        c.add(HIGH, "session-auth-write", path, n.lineno,
                              f"Assigns {o}.{t.attr}: sets who the request is authenticated as.",
                              "Authenticate through request.session.authenticate(); never set identity by hand.")  # fmt: skip
                    continue
                if "thread_local" in o:
                    continue  # per-thread bookkeeping (odoo.service.server.thread_local)
                if o.startswith(("odoo.http", "odoo.service", "odoo.addons.base.models.ir_http")):
                    c.add(HIGH, "core-patch", path, n.lineno,
                          f"Assigns {o}.{t.attr}: patches Odoo's HTTP/auth/service internals at import.",
                          "Never patch odoo.http/odoo.service; inherit ir.http and call super().")  # fmt: skip
        if not isinstance(n, ast.Call):
            continue
        fn = _dotted(n.func)
        if fn in ("setattr", "builtins.setattr", "object.__setattr__", "type.__setattr__") and len(n.args) >= 2:
            o = origin(n.args[0])
            lit = _fold_str(n.args[1])
            if o.startswith("odoo.") and lit is None:
                c.add(HIGH, "core-patch", path, n.lineno,
                      f"setattr on {o} with a computed attribute name: patches an Odoo class"
                      " (cannot prove it is not a security method).",
                      "Never monkeypatch Odoo classes; inherit and call super().")  # fmt: skip
            elif o.startswith(("odoo.http", "odoo.service", "odoo.addons.base.models.ir_http")):
                c.add(HIGH, "core-patch", path, n.lineno, f"setattr on {o}: patches Odoo's HTTP/auth internals.",
                      "Never patch odoo.http/odoo.service; inherit ir.http and call super().")  # fmt: skip
        attr = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        # H13: request.session.update({'uid': ..}) / update(uid=..) / setdefault('uid', ..) / __setitem__
        if isinstance(n.func, ast.Attribute) and is_session(n.func.value) and attr in ("update", "setdefault", "__setitem__"):
            keys: list[str | None] = [k.arg for k in n.keywords]
            if attr == "update" and n.args:
                a0 = n.args[0]
                keys += [skey(k) if k is not None else None for k in a0.keys] if isinstance(a0, ast.Dict) else [None]
            elif n.args:
                keys.append(skey(n.args[0]))
            ks = [k if not isinstance(k, str) else _Key([k] if k in _SESSION_AUTH else [], "") for k in keys]
            ks = [k for k in ks if k is None or k.hits]
            if ks:
                sess_auth_write(n.lineno, next((k for k in ks if k is not None and not k.why), ks[0]))
        if attr in _ASYNC_SPAWN or attr in spawn_alias:
            c.add(HIGH, "dangerous-call", path, n.lineno,
                  f"{fn or attr}() starts an OS process (asyncio subprocess).",
                  "Never run shell commands from a module.")  # fmt: skip
        if attr in ("execute", "executemany", "copy_expert", "copy_from", "copy_to") and n.args:
            q = _sql_folded(n.args[0], sql_vars)
            q = _sql_norm(q) if q else q
            if q and ((_CORE_DML.search(q) and _CORE_TABLES.search(q)) or _CORE_DML_ON.search(q)):
                c.add(HIGH, "core-table-dml", path, n.lineno,
                      f"Literal SQL changes a core table ({q.strip()[:60]!r}) bypassing the ORM and access rules.",
                      "Never write core tables with SQL; use the ORM on your own models.")  # fmt: skip


def _str_consts(tree: ast.AST) -> dict[str, str]:
    """Names bound exactly once to a constant-foldable string (m = 'res' + '.users')."""
    seen: dict[str, int] = {}
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    seen[t.id] = seen.get(t.id, 0) + 1
                    v = _fold_str(n.value)
                    if v is not None:
                        out[t.id] = v
    return {k: v for k, v in out.items() if seen.get(k) == 1}


# relation fields whose records are on the security core, whatever model holds them
_REL_MODEL = {
    "user_ids": "res.users", "user_id": "res.users", "create_uid": "res.users", "write_uid": "res.users",
    "users": "res.users", "groups_id": "res.groups", "group_ids": "res.groups", "implied_ids": "res.groups",
    "company_id": "res.company", "company_ids": "res.company",
}  # fmt: skip
_SAME_RECORDSET = frozenset({
    "filtered", "filtered_domain", "sorted", "sudo", "with_user", "with_context", "with_company",
    "with_env", "exists", "ensure_one", "browse", "search", "union", "concat",
})  # fmt: skip


def _receiver_model(x: ast.AST, model_vars: dict[str, str], env_key) -> str | None:
    """Model of the recordset x, read from the outside in; None when unknown here."""
    for _ in range(40):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute):
            a = x.func.attr
            if a == "mapped" and x.args:
                f = _fold_str(x.args[0])
                if f is None:
                    return None
                return _REL_MODEL.get(f.split(".")[-1], "")
            if a in _SAME_RECORDSET:
                x = x.func.value
                continue
            if a in ("create", "copy", "new"):  # a new record of the receiver's model
                x = x.func.value
                continue
            if a in ("ref", "get", "browse_ref") or _chain(x.func.value).endswith("env"):
                return None
            # another method's result (message_post(), _get_x()) is not provably the receiver's model
            return ""
        if isinstance(x, ast.Attribute):
            if x.attr in _REL_MODEL:
                return _REL_MODEL[x.attr]
            if x.attr in ("user", "uid") and _chain(x.value).endswith("env"):
                return "res.users"
            if x.attr in ("company", "companies") and _chain(x.value).endswith("env"):
                return "res.company"
            if x.attr in ("env", "sudo") or _chain(x).endswith(".env"):
                return None
            # a field hop off a recordset lands on another model: never the base record's model
            return ""
        if isinstance(x, ast.BinOp) and isinstance(x.op, (ast.BitOr, ast.BitAnd, ast.Add, ast.Sub)):
            x = x.left
            continue
        if isinstance(x, ast.Subscript):
            k = env_key(x)
            return k if k is not None else None
        if isinstance(x, ast.Name):
            return model_vars.get(x.id)
        return None
    return None


_PRIV_VAL_KEY = re.compile(r"^(?:groups_id|group_ids|implied_ids|share|company_ids|sel_groups_\w+|in_group_\w+)$")


def _priv_keys_in(x: ast.AST) -> bool:
    """A dict literal / dict(...) call / keyword set naming a privilege field."""
    for y in ast.walk(x):
        if isinstance(y, ast.Dict) and any(isinstance(k := _fold_str(kk) if kk else None, str) and _PRIV_VAL_KEY.match(k) for kk in y.keys):
            return True
        if isinstance(y, ast.Call) and any(k.arg and _PRIV_VAL_KEY.match(k.arg) for k in y.keywords):
            return True
    return False


def _sql_folded(q: ast.AST, names: dict[str, ast.AST], depth: int = 0) -> str | None:
    """Folded SQL text: literals, SQL('.. %s ..', SQL.identifier('t')) and
    psycopg2 sql.SQL('.. {} ..').format(sql.Identifier('t')); identifiers through a local name."""
    if depth > 6:
        return None
    if isinstance(q, ast.Name) and q.id in names:
        return _sql_folded(names[q.id], names, depth + 1)
    s = _fold_str(q)
    if s is not None:
        return s
    if isinstance(q, ast.JoinedStr):  # f'UPDATE {t} ...' with t a local constant
        out = ""
        for v in q.values:
            if isinstance(v, ast.Constant):
                out += str(v.value)
            elif isinstance(v, ast.FormattedValue):
                p = _sql_folded(v.value, names, depth + 1)
                out += p if p is not None else "?"
        return out
    if isinstance(q, ast.BinOp) and isinstance(q.op, ast.Add):
        a, b = _sql_folded(q.left, names, depth + 1), _sql_folded(q.right, names, depth + 1)
        return None if a is None and b is None else (a or "?") + (b or "?")
    if isinstance(q, ast.BinOp) and isinstance(q.op, ast.Mod):  # 'UPDATE %s SET ..' % t
        a = _sql_folded(q.left, names, depth + 1)
        if a is None:
            return None
        args = q.right.elts if isinstance(q.right, ast.Tuple) else [q.right]
        for x in args:
            p = _sql_folded(x, names, depth + 1)
            a = a.replace("%s", p if p is not None else "?", 1)
        return a
    if not isinstance(q, ast.Call):
        return None
    fn = _dotted(q.func).split(".")[-1]
    if fn in ("identifier", "Identifier") and q.args:
        return _sql_folded(q.args[0], names, depth + 1)
    if fn == "format" and isinstance(q.func, ast.Attribute) and isinstance(q.func.value, ast.Call):
        head = _sql_folded(q.func.value, names, depth + 1)
        if head is None:
            return None
        parts = [_sql_folded(a, names, depth + 1) for a in q.args]
        try:
            return head.replace("%s", "{}").format(*[p if p is not None else "?" for p in parts])
        except (IndexError, KeyError, ValueError):
            return head
    if q.args:
        head = _sql_folded(q.args[0], names, depth + 1)
        if head is None:
            return None
        for a in q.args[1:]:
            p = _sql_folded(a, names, depth + 1) if isinstance(a, (ast.Call, ast.Name)) else None
            if "%s" in head:
                head = head.replace("%s", p if p is not None else "?", 1)
        return head
    return None


_SECRET_ATTR = re.compile(
    r"^(?:password|new_password|api_key\w*|totp_secret|signup_token|oauth_access_token|\w+_secret|secret)$"
)
_SECRET_READ_MODELS = frozenset({"res.users.apikeys", "auth.totp.device"})
_RPC_PROXY = re.compile(
    r"^odoo\.(?:service\.(?:dispatch_rpc|model\.(?:execute(?:_kw|_cr)?|dispatch)|common\.dispatch|"
    r"db\.(?:dispatch|exp_\w+)|dispatch)|http\.dispatch_rpc)$"
)


def _rpc_open(x: ast.Call, o: str) -> bool:
    """An RPC dispatch is an open proxy when the caller picks the service/model/method; a call
    with those fixed by literals (dispatch_rpc('db', 'list', ...), db.exp_list()) is a fixed
    service call and is graded by what it does, not as a proxy."""
    if any(isinstance(a, ast.Starred) for a in x.args) or any(k.arg is None for k in x.keywords):
        return True
    tail = o.rsplit(".", 1)[-1]
    if tail.startswith("exp_"):
        return False
    pos = {"dispatch_rpc": (0, 1), "execute" + "_kw": (3, 4), "execute": (2, 3), "execute_cr": (2, 3), "dispatch": (0,)}.get(tail, (0,))
    if tail == "dispatch" and ".model." not in o and ".common." not in o and ".db." not in o:
        pos = (0, 1)
    for i in pos:
        if i >= len(x.args) or _fold_str(x.args[i]) is None:
            return True
    return False


_RULE_CORE = frozenset({"ir.rule", "ir.model.access"})
_RULE_CORE_METHODS = frozenset({"_compute_domain", "_compute_domain_keys", "_get_rules", "domain_get", "_get_failing", "check", "_get_allowed_models", "call_cache_clearing_methods"})


def _class_inherits(cls: ast.ClassDef) -> set[str]:
    out: set[str] = set()
    for st in cls.body:
        if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("_inherit", "_name") for t in st.targets):
            v = st.value
            for e in v.elts if isinstance(v, (ast.List, ast.Tuple)) else [v]:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    out.add(e.value)
    return out



_SECRET_PASS = frozenset({
    "dict", "str", "list", "tuple", "format", "join", "dumps", "url_encode", "urlencode",
    "encode", "decode", "b64encode", "copy", "update", "jsonify",
    "make_response", "make_json_response", "render", "Response",
    "append", "extend", "add", "insert", "setdefault",
})  # fmt: skip
_SECRET_READERS = ("mapped", "read", "search_read", "read_group", "export_data", "get_param", "webRead", "web_read")


def _callee_name(x: ast.Call) -> str:
    """Helper reached by name: f(), self.f(), super().f(), Cls.f() (staticmethod) and
    env['m'].f() (a model method of this module)."""
    if isinstance(x.func, ast.Attribute) and _chain(x.func.value).split(".")[-1] in ("self", "cls", "super()") or (
        isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Call) and getattr(x.func.value.func, "id", "") == "super"
    ):
        return x.func.attr
    if isinstance(x.func, ast.Attribute) and (
        (isinstance(x.func.value, ast.Name) and x.func.value.id[:1].isupper())
        or any(isinstance(z, ast.Subscript) and _chain(z.value).endswith("env") for z in ast.walk(x.func.value))
    ):
        return x.func.attr
    return x.func.id if isinstance(x.func, ast.Name) else ""


def _secret_flow(f: ast.AST, summ: dict[str, tuple[str, frozenset[int]]]):
    """Secret taint inside one function. Returns (returned secret reads, returned param
    indexes, secret_read). A helper whose summary returns a secret taints its result; a
    helper that returns one of its params carries the argument's taint; any other call
    consumes its arguments."""
    args = getattr(f, "args", None)
    params = [a.arg for a in (args.posonlyargs + args.args)] if args else []
    if params and params[0] in ("self", "cls"):
        params = params[1:]
    ptaint: dict[str, set[int]] = {p: {i} for i, p in enumerate(params)}
    tainted: dict[str, str] = {}
    called = {id(y.func) for y in ast.walk(f) if isinstance(y, ast.Call)}
    carry: set[int] = set()  # Name ids passed into a helper that returns that argument
    for y in ast.walk(f):
        if isinstance(y, ast.Call) and (nm := _callee_name(y)) in summ:
            for i, a0 in enumerate(y.args):
                if i in summ[nm][1]:
                    carry |= {id(z) for z in ast.walk(a0) if isinstance(z, ast.Name)}
    sunk = {
        id(z)
        for y in ast.walk(f)
        if isinstance(y, ast.Call) and (y.func.attr if isinstance(y.func, ast.Attribute) else getattr(y.func, "id", "")) not in _SECRET_PASS
        for a0 in [*y.args, *[k.value for k in y.keywords]]
        for z in ast.walk(a0)
        if isinstance(z, ast.Name) and id(z) not in carry
    }

    fconsts = _str_consts(f)
    rec_vars: set[str] = set()

    def fold(x: ast.AST) -> str | None:
        v = _fold_str(x)
        if v is None and isinstance(x, ast.Name):
            v = fconsts.get(x.id)
        return v

    def rec_like(x: ast.AST) -> bool:
        """x evaluates to a recordset / read() rows, not to request input (kw['password'])."""
        for z in ast.walk(x):
            if isinstance(z, ast.Subscript) and _chain(z.value).endswith("env"):
                return True
            if isinstance(z, ast.Call) and isinstance(z.func, ast.Attribute) and z.func.attr in (
                "browse", "search", "sudo", "with_user", "with_context", "exists", "filtered", "read",
                "search_read", "search_fetch", "with_company", "ensure_one", "_read_group", "web_read",
            ):
                return True
            if isinstance(z, ast.Name) and (z.id in rec_vars or z.id in ("self", "user", "users", "record", "records", "rec", "recs")):
                return True
            if isinstance(z, ast.Attribute) and z.attr in ("user", "users"):
                return True
        return False

    for _ in range(2):
        for st in ast.walk(f):
            if isinstance(st, ast.Assign) and rec_like(st.value):
                rec_vars |= {t.id for t in st.targets if isinstance(t, ast.Name)}
            elif isinstance(st, (ast.For, ast.AsyncFor, ast.comprehension)) and rec_like(st.iter):
                rec_vars |= {t.id for t in ast.walk(st.target) if isinstance(t, ast.Name)}
    if params:  # a helper's record parameter (g(rec): return rec[...]) is a record when callers pass one
        rec_vars |= set(params)

    def secret_read(e: ast.AST) -> str:
        for y in ast.walk(e):
            if isinstance(y, ast.Attribute) and _SECRET_ATTR.match(y.attr) and id(y) not in called:
                return y.attr
            # H1: rec['password'] / rec[fld] / browse(..)['x'] / rows[0]['password']
            if isinstance(y, ast.Subscript) and not _chain(y.value).endswith("env") and (k := fold(y.slice)) and _SECRET_ATTR.match(k) and rec_like(y.value):
                return k
            if isinstance(y, ast.Attribute) and y.attr in ("__dict__", "_cache") and rec_like(y.value):
                return y.attr
            if isinstance(y, ast.Call):
                fn = y.func
                # H2: getattr(rec, 'pass' + 'word'), operator.attrgetter('password')(rec), rec.get('password')
                if isinstance(fn, ast.Name) and fn.id == "getattr" and len(y.args) >= 2:
                    k = fold(y.args[1])
                    if k is not None and _SECRET_ATTR.match(k):
                        return k
                    if k is None and rec_like(y.args[0]):  # a field name that cannot be proven non-secret
                        return "getattr(<runtime field name>)"
                if isinstance(fn, ast.Call) and _dotted(fn.func).endswith(("attrgetter", "itemgetter")) and any((k := fold(a)) and _SECRET_ATTR.match(k) for a in fn.args):
                    return "attrgetter"
                if isinstance(fn, ast.Attribute) and fn.attr in ("get", "mapped", "_read_format", "__getitem__", "__getattribute__", "__getattr__") and y.args and (k := fold(y.args[0])) and _SECRET_ATTR.match(k.split(".")[-1]) and rec_like(fn.value):
                    return k
                if isinstance(fn, ast.Attribute) and fn.attr in ("read", "search_read", "web_read", "_read_format", "export_data", "search_fetch") and any(
                    isinstance(z, (ast.List, ast.Tuple)) and any((k := fold(el)) and _SECRET_ATTR.match(k.split(".")[-1]) for el in z.elts) for a in [*y.args, *[kk.value for kk in y.keywords]] for z in ast.walk(a)
                ):
                    return "read(secret field)"
            if isinstance(y, ast.Call):
                nm = _callee_name(y)
                if nm in summ and summ[nm][0]:
                    return f"{nm}() -> {summ[nm][0]}"
                if isinstance(y.func, ast.Attribute):
                    a = y.func.attr
                    if a in _SECRET_READERS:
                        for z in ast.walk(y):
                            v = _fold_str(z) if isinstance(z, (ast.Constant, ast.JoinedStr, ast.BinOp)) else None
                            if v and (_SECRET_ATTR.match(v.split(".")[-1]) or (a == "get_param" and re.search(r"secret|password|token|api_?key", v, re.I))):
                                return v
                    if (k := next((kk for z in ast.walk(y.func.value) if isinstance(z, ast.Subscript) and (kk := _fold_str(z.slice)) in _SECRET_READ_MODELS), None)):
                        return k
            if isinstance(y, ast.Name) and y.id in tainted and id(y) not in sunk:
                return tainted[y.id]
        return ""

    def param_flow(e: ast.AST) -> set[int]:
        return {i for y in ast.walk(e) if isinstance(y, ast.Name) and id(y) not in sunk for i in ptaint.get(y.id, ())}

    for _ in range(4):
        for st in ast.walk(f):
            if isinstance(st, ast.Call) and isinstance(st.func, ast.Attribute) and isinstance(st.func.value, ast.Name) \
                    and st.func.attr in ("append", "extend", "add", "insert", "update", "setdefault"):
                if w := next((w for a0 in st.args if (w := secret_read(a0))), ""):  # out.append(rec['password'])
                    tainted[st.func.value.id] = w
            if isinstance(st, ast.Assign):
                w = secret_read(st.value)
                pf = param_flow(st.value)
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        if w:
                            tainted[t.id] = w
                        if pf:
                            ptaint[t.id] = ptaint.get(t.id, set()) | pf
    reads: list[tuple[int, str]] = []
    rparams: set[int] = set()
    for st in ast.walk(f):
        if isinstance(st, (ast.Return, ast.Yield)) and st.value is not None:
            if w := secret_read(st.value):
                reads.append((st.lineno, w))
            rparams |= param_flow(st.value)
        elif isinstance(st, ast.Call) and re.search(r"make_(json_)?response|render|dumps", _dotted(st.func)) and any(secret_read(a) for a in [*st.args, *[k.value for k in st.keywords]]):
            reads.append((st.lineno, secret_read(st)))
    return reads, frozenset(rparams), secret_read


def _secret_summaries(c: _Ctx) -> dict[str, tuple[str, frozenset[int]]]:
    """Module-wide fixpoint: function name -> (secret it returns, params it returns).
    Names are merged across the module (methods are reached through self/super)."""
    got = getattr(c, "_secret_summ", None)
    if got is not None:
        return got
    funcs: list[ast.AST] = []
    for rel, body in c.files.items():
        if rel.endswith(".py") and not rel.startswith("tests/") and "/tests/" not in rel:
            try:
                t = ast.parse(body)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                continue
            funcs += [n for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for n in ast.walk(t):  # g = lambda r: r.password is a helper too
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Lambda):
                    for tg in n.targets:
                        if isinstance(tg, ast.Name):
                            fd = ast.FunctionDef(name=tg.id, args=n.value.args, body=[ast.Return(value=n.value.body, lineno=n.lineno, col_offset=0)],
                                                 decorator_list=[], returns=None, type_params=[], lineno=n.lineno, col_offset=0)
                            funcs.append(fd)
    summ: dict[str, tuple[str, frozenset[int]]] = {}
    for _ in range(MAX_FLOW_ROUNDS):
        changed = False
        for fn in funcs:
            reads, rp, _ = _secret_flow(fn, summ)
            old = summ.get(fn.name, ("", frozenset()))
            new = (old[0] or (reads[0][1] if reads else ""), old[1] | rp)
            if new != old:
                summ[fn.name] = new
                changed = True
        if not changed:
            break
    c._secret_summ = summ
    return summ


_ATT_CONTENT = frozenset({"raw", "datas", "db_datas", "index_content"})
_ATT_GUARDS = ("access_token", "_document_check_access", "check_access", "_check_access", "consteq", "_can_bypass_rights", "_get_stream")


def _attachment_idor(f: ast.AST) -> int:
    """Line of an ir.attachment content read on a sudo record whose id comes from the request."""
    src_names = {a.arg for a in ast.walk(f.args) if isinstance(a, ast.arg) and a.arg not in ("self", "cls")} if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) else set()
    if any((isinstance(n, ast.Name) and n.id in _ATT_GUARDS) or (isinstance(n, ast.Attribute) and n.attr in _ATT_GUARDS) or (isinstance(n, ast.Constant) and n.value in _ATT_GUARDS) for n in ast.walk(f)):
        return 0

    def user_id(x: ast.AST) -> bool:
        return any((isinstance(z, ast.Name) and z.id in src_names) or (isinstance(z, ast.Attribute) and z.attr in ("params", "jsonrequest", "httprequest", "get_json_data")) for z in ast.walk(x))

    def att_rec(x: ast.AST) -> bool:
        txt = ast.dump(x)
        if "'ir.attachment'" not in txt or "attr='sudo'" not in txt:
            return False
        return any(isinstance(z, ast.Call) and isinstance(z.func, ast.Attribute) and z.func.attr in ("browse", "search", "search_read", "read") and user_id(z) for z in ast.walk(x))

    att_vars = {t.id for st in ast.walk(f) if isinstance(st, ast.Assign) and att_rec(st.value) for t in st.targets if isinstance(t, ast.Name)}
    for n in ast.walk(f):
        if isinstance(n, ast.Attribute) and n.attr in _ATT_CONTENT and (att_rec(n.value) or (isinstance(n.value, ast.Name) and n.value.id in att_vars)):
            return n.lineno
        if isinstance(n, ast.Subscript) and _fold_str(n.slice) in _ATT_CONTENT and (att_rec(n.value) or (isinstance(n.value, ast.Name) and n.value.id in att_vars)):
            return n.lineno
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("read", "search_read") and att_rec(n) and any(_fold_str(e) in _ATT_CONTENT for a in [*n.args, *[k.value for k in n.keywords]] for e in ast.walk(a)):
            return n.lineno
    return 0


_IDOR_MODELS = frozenset({"ir.attachment", "mail.message", "mail.mail", "res.partner", "res.users", "hr.employee", "account.move", "sale.order", "res.users.apikeys"})
_STREAM_FNS = frozenset({"_get_stream_from", "_record_to_stream", "_get_image_stream_from", "_binary_record_content", "binary_content"})
_REC_META = frozenset({"id", "ids", "exists", "sudo", "with_context", "with_user", "ensure_one", "_name", "browse"})


def _record_idor(f: ast.AST) -> int:
    """Line where a public route reads a sudo record of a personal-data model (or streams any
    sudo record through ir.binary) whose id the caller chose, with no access check."""
    if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return 0
    src = {a.arg for a in ast.walk(f.args) if isinstance(a, ast.arg) and a.arg not in ("self", "cls")}
    if any((isinstance(n, ast.Name) and n.id in _ATT_GUARDS) or (isinstance(n, ast.Attribute) and n.attr in _ATT_GUARDS) for n in ast.walk(f)):
        return 0
    # ownership check: the record is compared with the caller's session / user / partner
    if any(isinstance(n, ast.Compare) and any(isinstance(z, ast.Attribute) and z.attr in ("session", "user", "uid", "partner_id", "commercial_partner_id") for z in ast.walk(n)) for n in ast.walk(f)):
        return 0

    def user_id(x: ast.AST) -> bool:
        return any((isinstance(z, ast.Name) and z.id in src) or (isinstance(z, ast.Attribute) and z.attr in ("params", "jsonrequest", "httprequest", "get_json_data")) for z in ast.walk(x))

    def picked(x: ast.AST, models: frozenset | None) -> bool:
        txt = ast.dump(x)
        if "attr='sudo'" not in txt or (models is not None and not any(f"'{m}'" in txt for m in models)):
            return False
        return any(isinstance(z, ast.Call) and isinstance(z.func, ast.Attribute) and z.func.attr in ("browse", "search") and user_id(z) for z in ast.walk(x))

    pd = {t.id for st in ast.walk(f) if isinstance(st, ast.Assign) and picked(st.value, _IDOR_MODELS) for t in st.targets if isinstance(t, ast.Name)}
    anyv = {t.id for st in ast.walk(f) if isinstance(st, ast.Assign) and picked(st.value, None) for t in st.targets if isinstance(t, ast.Name)}
    is_pd = lambda x: (isinstance(x, ast.Name) and x.id in pd) or (not isinstance(x, ast.Name) and picked(x, _IDOR_MODELS))  # noqa: E731
    is_any = lambda x: (isinstance(x, ast.Name) and x.id in anyv) or (not isinstance(x, ast.Name) and picked(x, None))  # noqa: E731
    for n in ast.walk(f):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _STREAM_FNS and any(is_any(a) for a in n.args):
            return n.lineno
        if isinstance(n, ast.Attribute) and n.attr not in _REC_META and is_pd(n.value):
            return n.lineno
        if isinstance(n, ast.Subscript) and is_pd(n.value):
            return n.lineno
    return 0


def _review6_py(c: _Ctx, path: str, tree: ast.AST, malias: dict[str, str]) -> None:
    """REVIEW-CODE-AUDIT-6 root causes: rule/access core overrides (H10), security-core
    create/write overrides that inject privilege vals (H11), secret reads in controllers
    (H12/M3), RPC proxies on public routes (H9), stored/related secret fields (H16), and
    privilege defaults through Python action contexts (H8 Python twin)."""
    imp = _odoo_imports(tree)

    def origin(x: ast.AST) -> str:
        d = _dotted(x)
        head, _, rest = d.partition(".")
        if head in imp:
            return f"{imp[head]}.{rest}" if rest else imp[head]
        return d

    # H10/H11: overrides on the security core
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        inh = _class_inherits(cls)
        if not inh:
            continue
        for f in cls.body:
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) or f.name.startswith("__"):
                continue
            sup = any(isinstance(x, ast.Call) and _dotted(x.func) == "super" for x in ast.walk(f))
            lit_domain = any(isinstance(r, ast.Return) and isinstance(r.value, (ast.List, ast.Tuple)) for r in ast.walk(f))
            if inh & _RULE_CORE and (not _is_auth_name(f.name) or (sup and lit_domain)):
                c.add(HIGH if (not sup or lit_domain or f.name in _RULE_CORE_METHODS and not sup) else MEDIUM,
                      "auth-override", path, f.lineno,
                      f"{cls.name}.{f.name}() overrides {'/'.join(sorted(inh & _RULE_CORE))}: record rules and"
                      " access rights are computed here" + (" (returns a literal domain)." if lit_domain else "."),
                      "Never override record-rule or access-right computation in a module.")  # fmt: skip
            if inh & SENSITIVE_MODELS and f.name in ("create", "write", "copy", "_create", "_write", "new", "default_get", "_signup_create_user"):
                for x in ast.walk(f):
                    k = None
                    if isinstance(x, (ast.Assign, ast.AugAssign)):
                        for t in x.targets if isinstance(x, ast.Assign) else [x.target]:
                            if isinstance(t, ast.Subscript):
                                k = _fold_str(t.slice)
                    elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in ("update", "setdefault", "__setitem__"):
                        if x.func.attr == "update" and x.args and isinstance(x.args[0], ast.Dict):
                            k = next((kk for kk in map(_fold_str, x.args[0].keys) if kk and _PRIV_VAL_KEY.match(kk)), None)
                        elif x.func.attr != "update" and x.args:
                            k = _fold_str(x.args[0])
                        k = k or next((kw.arg for kw in x.keywords if kw.arg and _PRIV_VAL_KEY.match(kw.arg)), None)
                    if k is None and isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) \
                            and isinstance(x.func.value, ast.Call) and _dotted(x.func.value.func) == "super":
                        if any(_priv_keys_in(a) for a in x.args):
                            k = "groups_id"
                    if k and (_PRIV_VAL_KEY.match(k) or ("res.groups" in inh and k in ("users", "user_ids"))):
                        c.add(HIGH, "sensitive-override-write", path, x.lineno,
                              f"{cls.name}.{f.name}() on {'/'.join(sorted(inh & SENSITIVE_MODELS))} sets {k!r} in the"
                              " values: every record created/written through it gets privileges.",
                              "Never inject groups/share/company privileges in a security-core create/write override.")  # fmt: skip
                        break

    # H16: python fields related to a secret column (stored or not, the hash/token becomes readable)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _dotted(n.func).split(".")[0] in ("fields", "odoo") and _dotted(n.func)[:1].isalpha():
            for kw in n.keywords:
                if kw.arg == "related":
                    r = _fold_str(kw.value)
                    if r and _SECRET_ATTR.match(r.split(".")[-1]):
                        store = any(k.arg == "store" and _const(k.value) is True for k in n.keywords)
                        c.add(HIGH, "sensitive-field-exposure", path, n.lineno,
                              f"Field related to {r!r}{' (stored)' if store else ''}: copies a secret onto a readable model.",
                              "Never relate or store password/token/secret columns on another model.")  # fmt: skip

    # H8 Python twin: action dicts / with_context defaulting privilege fields
    for n in ast.walk(tree):
        hit = None
        if isinstance(n, ast.Dict):
            for kk, vv in zip(n.keys, n.values):
                if kk is not None and _fold_str(kk) == "context":
                    src = ast.unparse(vv)
                    if m := policy.CTX_PRIV_DEFAULT.search(src):
                        hit = m.group(1) or m.group(2)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "with_context":
            for kw in n.keywords:
                if kw.arg and re.match(r"^default_(groups_id|group_ids|implied_ids|share|password|company_ids|sel_groups_\w+|in_group_\w+|user_ids|users)$", kw.arg):
                    hit = kw.arg[8:]
            for a in n.args:
                if m := policy.CTX_PRIV_DEFAULT.search(ast.unparse(a)):
                    hit = m.group(1) or m.group(2)
        if hit:
            c.add(HIGH, "context-privilege-default", path, n.lineno,
                  f"Context sets default_{hit}: records created with it get privilege fields.",
                  "Do not default security fields through a context.")  # fmt: skip

    # H9 / H12 / M3: controllers
    funcs = {f.name: f for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
    proxy: set[str] = set()
    for _ in range(4):  # helpers that reach an RPC dispatcher are dispatchers too
        for name, f in funcs.items():
            if name in proxy:
                continue
            for x in ast.walk(f):
                if isinstance(x, ast.Call):
                    o = origin(x.func)
                    callee = x.func.attr if isinstance(x.func, ast.Attribute) and _chain(x.func.value) in ("self", "cls") else (x.func.id if isinstance(x.func, ast.Name) else "")
                    if (_RPC_PROXY.match(o) and _rpc_open(x, o)) or callee in proxy:
                        proxy.add(name)
                        break
    for f in funcs.values():
        auth = _route_auth(f)
        if not auth:
            continue
        public = auth in ("public", "none", "dynamic")
        for x in ast.walk(f):
            if not isinstance(x, ast.Call):
                continue
            o = origin(x.func)
            callee = x.func.attr if isinstance(x.func, ast.Attribute) and _chain(x.func.value) in ("self", "cls") else (x.func.id if isinstance(x.func, ast.Name) else "")
            if (_RPC_PROXY.match(o) and _rpc_open(x, o)) or (callee and callee in proxy and callee != f.name):
                c.add(HIGH if public else MEDIUM, "rpc-proxy", path, x.lineno,
                      f"auth='{auth}' route {f.name}() forwards to the RPC dispatcher ({o or callee}):"
                      " an open proxy to every model and service.",
                      "Never expose the RPC dispatcher (dispatch_rpc, model.execute*) from a route; call the ORM on fixed models.")  # fmt: skip
                break
        # secret reads inside the route (helper returns followed through module summaries)
        summ = _secret_summaries(c)
        reads, _, secret_read = _secret_flow(f, summ)
        # returned to the caller: HIGH under any auth (the response carries the secret)
        for line, w in reads[:1]:
            c.add(HIGH, "route-secret-read", path, line,
                  f"auth='{auth}' route {f.name}() returns secret material ({w}).",
                  "Never return passwords, API keys, TOTP secrets or tokens from a controller.")  # fmt: skip
        if not reads:  # M3: secret-holding models read in a route, not (provably) returned
            for st in ast.walk(f):
                if isinstance(st, ast.Call) and (w := secret_read(st)) in _SECRET_READ_MODELS:
                    c.add(HIGH if public else MEDIUM, "route-secret-read", path, st.lineno,
                          f"auth='{auth}' route {f.name}() reads {w}.",
                          "Do not read API keys/TOTP devices in controllers.")  # fmt: skip
                    break
        if public:  # M4: sudo ir.attachment content for a caller-chosen id (IDOR)
            line = _attachment_idor(f)
            if line:
                c.add(MEDIUM, "route-attachment-idor", path, line,
                      f"auth='{auth}' route {f.name}() returns ir.attachment content for a caller-supplied id under sudo"
                      " with no access-token / ownership check: any visitor can download any attachment.",
                      "Drop sudo(), or verify access_token / res_model+res_id ownership (portal _document_check_access) first.")  # fmt: skip
            elif line2 := _record_idor(f):
                c.add(MEDIUM, "route-record-idor", path, line2,
                      f"auth='{auth}' route {f.name}() reads a sudo record (personal data / binary stream) for a caller-supplied id"
                      " with no access-token / ownership check.",
                      "Drop sudo(), or check access_token / ownership (_document_check_access) before reading.")  # fmt: skip


def _audit_py(c: _Ctx, path: str, body: bytes, server_code: bool = False) -> None:
    try:
        # bytes: the parser honours a PEP 263 coding cookie and a BOM, like Python itself
        tree = ast.parse(body, filename=path)
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
    malias = flow.method_aliases(tree)
    local_sql, sql_safe = _local_sql(tree)
    tar = any(v.split(".")[0] == "tarfile" for v in res.alias.values())
    params = {
        a.arg
        for f in ast.walk(tree)
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
        for a in [*f.args.args, *f.args.kwonlyargs, f.args.kwarg, f.args.vararg]
        if a is not None and a.arg not in ("self", "cls")
    }
    # parameters an outside caller controls: public model methods (RPC-callable) and routes
    rpc_params: set[str] = set()
    for cls in (x for x in ast.walk(tree) if isinstance(x, ast.ClassDef)):
        for f in cls.body:
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                not f.name.startswith("_") or _route_auth(f)
            ):
                rpc_params |= {
                    a.arg
                    for a in [*f.args.args, *f.args.kwonlyargs, f.args.vararg, f.args.kwarg]
                    if a is not None and a.arg not in ("self", "cls")
                }
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and not any(
            isinstance(x, ast.ClassDef) and f in x.body for x in ast.walk(tree)
        ):
            rpc_params |= {a.arg for a in [*f.args.args, *f.args.kwonlyargs]}  # loose functions
    for a in ast.walk(tree):  # names holding record field values (user-editable data)
        if (
            isinstance(a, ast.Assign)
            and isinstance(a.value, ast.Attribute)
            and _chain(a.value.value) == "self"
            and not a.value.attr.startswith("_")
            and a.value.attr != "id"
        ):
            rpc_params |= {t.id for t in a.targets if isinstance(t, ast.Name)}

    rhs: dict[str, set[str]] = {}
    for a in ast.walk(tree):
        if isinstance(a, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and a.value is not None:
            tg = a.targets if isinstance(a, ast.Assign) else [a.target]
            used = {x.id for x in ast.walk(a.value) if isinstance(x, ast.Name)}
            for t in tg:
                if isinstance(t, ast.Name):
                    rhs.setdefault(t.id, set()).update(used)

    def _sqli_sev(q: ast.AST) -> str:
        """HIGH when a caller-controlled parameter is interpolated; MEDIUM when only
        internally computed names are (still blocks owned code; review per site)."""
        names = {x.id for x in ast.walk(q) if isinstance(x, ast.Name)}
        todo = list(names)
        while todo:  # follow local assignments: q = q + n reaches n
            for v in rhs.get(todo.pop(), ()):
                if v not in names:
                    names.add(v)
                    todo.append(v)
        field = any(
            isinstance(x, ast.Attribute)
            and _chain(x.value) == "self"
            and not x.attr.startswith("_")
            and x.attr != "id"
            for x in ast.walk(q)
        )
        return HIGH if field or names & rpc_params or not names else MEDIUM

    _danger_refs(c, path, tree, res)
    _sensitive_writes(c, path, tree, malias, server_code)
    _auth_bypass(c, path, tree, malias)
    _core_patches(c, path, tree)
    _review6_py(c, path, tree, malias)
    _server_code_grades(c, path, tree, server_code)
    if server_code:
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                c.add(
                    HIGH,
                    "server-code-import",
                    path,
                    n.lineno,
                    "Stored server code imports a module (safe_eval forbids it; an attempt to"
                    " reach the interpreter).",
                    "Use only the evaluation context (env, model, records, time, datetime).",
                )
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = flow.call_name(n, malias)
        aliased = isinstance(fn, ast.Name) and fn.id in malias
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
        tgt = res.expr(fn)
        if tgt in flow._GETTERS and not (n.args and isinstance(_const(n.args[0]), str)):
            c.add(
                HIGH,
                "dangerous-call",
                path,
                ln,
                f"{tgt.split('.')[-1]}() with a computed name: any method can be reached.",
                "Call the method directly by name.",
            )
        if res.call_target(n) in ("compile", "builtins.compile"):
            lit = bool(n.args) and isinstance(_const(n.args[0]), (str, bytes))
            c.add(
                MEDIUM if lit else HIGH,
                "compile-code",
                path,
                ln,
                "compile() builds a code object"
                + ("." if lit else " from computed text (reaches exec via types/FunctionType)."),
                "Remove it; modules never need to compile Python at runtime.",
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
            arg = n.args[0] if n.args else None
            caller = arg is not None and any(
                isinstance(x, ast.Name) and x.id in params for x in ast.walk(arg)
            )
            c.add(
                MEDIUM if caller else LOW,
                "safe-eval",
                path,
                ln,
                "safe_eval of a caller-supplied expression (a parameter)."
                if caller
                else "safe_eval of stored text.",
                "Make sure only trusted users can edit the evaluated text.",
            )
        elif why := _elevating(n, malias):
            c.add(
                LOW,
                "sudo",
                path,
                ln,
                f"{why} bypasses access rights and record rules.",
                "Limit to the smallest read needed and check the caller's rights first.",
            )
        elif (
            name in ("extractall", "extract")
            and tar
            and not any(k.arg == "filter" for k in n.keywords)
        ):
            c.add(
                MEDIUM,
                "archive-extract",
                path,
                ln,
                f"tarfile {name}() without filter=: members can write outside the target"
                " (../, absolute paths, links).",
                "Pass filter='data' (Python 3.12+), or validate every member path first.",
            )
        elif (
            name == "SQL"
            and n.args
            and _is_dynamic_str(n.args[0])
            and _sql_has_variable(n.args[0], sql_safe.get(id(n), frozenset()))
        ):
            c.add(
                _sqli_sev(n.args[0]),
                "sql-injection",
                path,
                ln,
                "SQL() built from a formatted string (the template must be a literal).",
                "Use SQL('... %s', value) or SQL.identifier() for names.",
            )
        elif (
            name == "SQL"
            and n.args
            and isinstance(n.args[0], ast.Name)
            and n.args[0].id in rpc_params
        ):
            c.add(
                HIGH,
                "sql-injection",
                path,
                ln,
                f"SQL({n.args[0].id}): the whole query comes from a caller-controlled parameter.",
                "SQL templates must be literals; pass values as SQL('... %s', value).",
            )
        elif (
            name in _SQL_CALLS
            and (
                isinstance(fn, (ast.Attribute, ast.Call))
                or aliased
                or name in ("execute_values", "execute_batch")
            )
            and len(n.args) > _SQL_CALLS[name]
        ):
            q = local_sql.get(id(n), n.args[_SQL_CALLS[name]])
            if _is_dynamic_str(q) and _sql_has_variable(q, sql_safe.get(id(n), frozenset())):
                c.add(
                    _sqli_sev(q),
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
        elif (
            (name == "Markup" or flow._markup_call(res, n))
            and n.args
            and not isinstance(n.args[0], ast.Constant)
        ):
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
        if (
            name == "ref"
            and n.args
            and isinstance(_const(n.args[0]), str)
            and not any(
                k.arg == "raise_if_not_found" and _const(k.value) is False for k in n.keywords
            )
            and not (len(n.args) > 1 and _const(n.args[1]) is False)
        ):  # ref(..., raise_if_not_found=False) tolerates a missing record by design
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
        bad_t = sorted(
            {m for m in full if m.startswith(_TEST_MODULES) and not _TEST_SAFE_IMPORTS.match(m)}
        )
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
        flow.taint_hits(tree, c.text_fields, res, c.flow_pt, c.flow_sinks)
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
_STYLE_RISK = re.compile(
    r"url\(\s*['\"]?\s*((?:https?:)?//)|expression\s*\(|javascript:|behavior\s*:", re.I
)
_EXT_URL = re.compile(r"^\s*(?:https?:)?//", re.I)
_RESOURCE_TAGS = {
    "script": "src",
    "link": "href",
    "iframe": "src",
    "object": "data",
    "embed": "src",
}


_JS_SAFE_OUT = re.compile(r"json\.dumps|json_dumps|\btojson\b|^\s*(?:int|float|bool)\(")


def _js_ctx(text: str) -> str:
    """Lexical context at the end of `text` (all script text so far, every line): "code",
    a quote char when inside a string ("'", '"', "`"), or "comment". Template literals are
    tracked across lines; ${...} inside one is code."""
    st: list[str] = []  # stack: quote chars and "${" frames
    i, n = 0, len(text)
    mode = "code"
    while i < n:
        ch = text[i]
        if mode == "line":
            if ch == "\n":
                mode = "code"
        elif mode == "block":
            if text.startswith("*/", i):
                mode, i = "code", i + 1
        elif st and st[-1] in "'\"`":
            q = st[-1]
            if ch == "\\":
                i += 1
            elif ch == q:
                st.pop()
            elif q == "`" and text.startswith("${", i):
                st.append("{")
                i += 1
            elif ch == "\n" and q != "`":
                st.pop()  # unterminated string ends at the line (a syntax error in JS)
        else:
            if text.startswith("//", i):
                mode = "line"
            elif text.startswith("/*", i):
                mode = "block"
            elif ch in "'\"`":
                st.append(ch)
            elif ch == "{" and st:
                st.append("(")
            elif ch == "}" and st and st[-1] in "({":
                st.pop()
        i += 1
    if mode != "code":
        return "comment"
    return st[-1] if st and st[-1] in "'\"`" else "code"


def _in_js_string(line: str) -> bool:
    return _js_ctx(line) in ("'", '"', "`")


def _handler_holes_quoted(val: str) -> bool:
    """True when every interpolation of a t-attf handler lands inside a JS string literal.
    Still injectable by a value carrying a quote (the attribute is entity-decoded before
    the script runs), so this lowers HIGH to MEDIUM, never to clean."""
    holes = list(re.finditer(r"#\{[^}]*\}|\{\{.*?\}\}", val))
    return bool(holes) and all(_in_js_string(val[: m.start()]) for m in holes)


_REQ_DATA = re.compile(
    r"\brequest\.(?:params|httprequest|get_http_params|get_json_data)|\bkw\b|\bpost\b"
)
_TOKEN_DATA = re.compile(
    r"session(?:_token|\.sid|\.uid|\.login|_id)?\b|csrf|access_token|password|api_key|cookies?\b",
    re.I,
)
_EXT_URL_ANY = re.compile(r"""(?:^\s*|['"])(?:https?:)?//""", re.I)


def _qweb_attr_checks(c: _Ctx, path: str, xl: _XLines, el: Any, a: str, val: str) -> None:
    """Inline event handlers, runtime URLs, srcdoc, external form targets, meta refresh,
    dynamic t-call targets and tokens sent to other hosts."""
    base = a.removeprefix("t-att-").removeprefix("t-attf-")
    dyn = base != a
    if a == "t-call" and re.search(r"\{\{|#\{", val or ""):
        req = bool(_REQ_DATA.search(val))
        # OWL (static/) resolves names only among registered client templates: LOW
        c.add(
            HIGH if req else (LOW if path.startswith("static/") else MEDIUM),
            "qweb-dynamic-call",
            path,
            xl.el(el, a),
            "t-call target computed at render time"
            + (
                " from request input: any template (incl. admin-only ones) can be rendered."
                if req
                else "."
            ),
            "Call fixed template ids; choose between them with t-if.",
        )
    if (
        dyn
        and base in ("href", "src", "action", "formaction", "data", "srcset", "poster")
        and (_EXT_URL_ANY.search(val) and _TOKEN_DATA.search(val))
    ):
        c.add(
            HIGH,
            "qweb-token-leak",
            path,
            xl.el(el, a),
            f"{a} sends a session/CSRF/access token to an external host.",
            "Never put tokens in URLs to other hosts.",
        )
    if re.fullmatch(r"on[a-z]{3,30}", base):
        sev = HIGH if dyn else MEDIUM
        if a.startswith("t-attf-") and _handler_holes_quoted(val):
            sev = MEDIUM  # every #{}/{{}} sits inside a JS string literal (M6)
        c.add(
            sev,
            "qweb-inline-handler",
            path,
            xl.el(el, a),
            f"{a} is an inline event handler"
            + (" built from data" if dyn else "")
            + ": script in markup (CSP-unsafe, injection point).",
            "Use an OWL handler (t-on-click) or a JS event listener.",
        )
    if base == "srcdoc":
        c.add(
            HIGH if dyn else MEDIUM,
            "qweb-srcdoc",
            path,
            xl.el(el, a),
            f"{a} renders an HTML document inside the frame (same origin, unescaped).",
            "Load a fixed route in the iframe instead.",
        )
    elif dyn and base in ("href", "src", "action", "formaction", "xlink:href", "data"):
        fixed = a.startswith("t-attf-") and re.match(r"\s*(?:/|#|https?:|mailto:|tel:)", val)
        if not fixed:
            c.add(
                MEDIUM if _REQ_DATA.search(val) else LOW,
                "qweb-dynamic-url",
                path,
                xl.el(el, a),
                f"{a} is a URL decided at runtime: QWeb does not block javascript: URLs here"
                " (flagged).",
                "Start the URL with a fixed path (/...) or validate the scheme in Python.",
            )
    tag = xl._local(el)
    if tag == "form" and a == "action" and _EXT_URL.search(val):
        c.add(
            MEDIUM,
            "qweb-external-form",
            path,
            xl.el(el, a),
            f"Form posts to an external host ({val[:80]}).",
            "Post to this server's routes only.",
        )
    if tag == "meta" and base == "content" and (el.get("http-equiv") or "").lower() == "refresh":
        if dyn or re.search(r"url\s*=\s*['\"]?\s*(?:https?:)?//", val, re.I):
            c.add(
                MEDIUM,
                "qweb-meta-refresh",
                path,
                xl.el(el, a),
                "meta refresh redirects to an external or runtime URL.",
                "Redirect in the controller to a fixed local route.",
            )


def _rebuild(el: Any) -> tuple[str, list[tuple[Any, str, str]]]:
    """Element text with each child replaced by a neutral identifier (line breaks kept);
    returns the text and the (child, output attribute, text before it) for QWeb outputs."""
    from lxml import etree

    parts = [el.text or ""]
    outs = []
    for ch in el:
        raw = etree.tostring(ch, with_tail=False, encoding="unicode")
        oa = next((k for k in ("t-out", "t-esc", "t-raw") if ch.get(k)), None)
        if oa:
            outs.append((ch, oa, "".join(parts)))
        parts.append("__qweb__" + "\n" * raw.count("\n"))
        parts.append(ch.tail or "")
    return "".join(parts), outs


def _qweb_resources(c: _Ctx, path: str, xl: _XLines, el: Any) -> None:
    """External or computed script/style/frame sources in templates, and inline <script> and
    <style> bodies (handed to the JS / CSS parser like any static file)."""
    tag = xl._local(el)
    if tag == "style" and (el.text or len(el)):
        css, outs = _rebuild(el)
        for ch, oa, _ in outs:
            c.add(
                MEDIUM,
                "qweb-style-injection",
                path,
                xl.el(ch, oa),
                f"{oa} writes into a stylesheet: HTML escaping does not stop CSS injection"
                " (url(), @import, selectors).",
                "Pass values as CSS custom properties set from validated data, or as classes.",
            )
        if css.strip():
            line0 = xl.line(xl._tag_span(el)[1] + 1)
            c.web.append((f"{path}#style@{line0}", path, line0, "css", css))
        return
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
        if _data_script(c, path, xl.el(el), typ, "".join(el.itertext())):
            return
        if "template" in typ:
            return
        # QWeb output inside the script (<t t-esc/>) becomes a neutral identifier that is
        # valid both inside a string literal and as an expression; line breaks are kept.
        # The lexical context is computed over the whole script (multi-line strings,
        # template literals, comments), not per line.
        js, outs = _rebuild(el)
        for ch, out_attr, before in outs:
            if _JS_SAFE_OUT.search(ch.get(out_attr)):
                continue
            ctx = _js_ctx(before)
            where = {
                "code": "script code outside a string",
                "`": "a template literal (${...} is not escaped)",
                "comment": "a comment (a newline or */ ends it)",
            }.get(ctx, "a string literal (a trailing backslash or U+2028 can break out)")
            req = bool(_REQ_DATA.search(ch.get(out_attr) or ""))
            c.add(
                # request data is attacker-chosen: a trailing backslash or U+2028 breaks
                # even a string literal, so it is HIGH in every JavaScript context
                HIGH if req else (LOW if ctx in ("'", '"') else MEDIUM),
                "qweb-script-injection",
                path,
                xl.el(ch, out_attr),
                f"{out_attr} writes into {where}: HTML escaping does not stop JavaScript"
                " injection.",
                "Emit json.dumps(value) (or put the value in a data- attribute).",
            )
        if not js.strip():
            return
        line0 = xl.line(xl._tag_span(el)[1] + 1)
        c.web.append((f"{path}#script@{line0}", path, line0, "js", js))


_JSON_SCRIPT = re.compile(r"^\s*(?:importmap|speculationrules|application/(?:[\w.+-]+\+)?json|text/json)\s*$")


def _data_script(c: _Ctx, path: str, line: int, typ: str, text: str) -> bool:
    """<script type="importmap|speculationrules|*json"> holds JSON the browser never runs as
    code: parse it as JSON (unparsable: fail closed). An import map remaps every module
    specifier and speculation rules prefetch URLs, so a remote target in either is graded."""
    if not _JSON_SCRIPT.match(typ or ""):
        return False
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError as e:
        c.add(HIGH, "web-unaudited", path, line, f"Cannot parse, unaudited ({typ} is not JSON: {str(e)[:80]}).",
              "Ship valid JSON in the script element.")
        return True
    kind = typ.strip()
    if kind not in ("importmap", "speculationrules"):
        return True  # plain JSON data block: inert
    urls: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str) and kind == "importmap":
                    urls.append(k)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            urls.append(x)

    walk(data)
    for u in urls:
        if re.match(r"\s*(?:[a-z][a-z0-9+.-]*:|//|\\\\)", u, re.I) and not re.match(r"\s*(?:/(?!/)|\./|\.\./)", u):
            if re.match(r"\s*(?:https?:)?//", u, re.I) or re.match(r"\s*(?:javascript|data|blob):", u, re.I):
                c.add(HIGH if kind == "importmap" else MEDIUM, "markup-external-resource", path, line,
                      f"<script type={kind}> points at {u[:80]}: "
                      + ("module imports are loaded from it." if kind == "importmap" else "the browser prefetches it."),
                      "Map modules to bundled, same-origin paths only.")
                break
    return True


_READ_ONLY_CALLS = frozenset(
    {"search", "search_read", "read", "browse", "search_count", "name_search", "exists"}
)


_EXPR_FIELDS = frozenset(
    {"domain", "domain_force", "context", "filter_domain", "filter_pre_domain", "domain_filter"}
)
_EXPR_WRITE = frozenset(
    {
        "write",
        "create",
        "unlink",
        "sudo",
        "with_user",
        "with_env",
        "execute",
        "set_param",
        "copy",
        "toggle_active",
        "action_archive",
        "action_unarchive",
        "message_post",
        "send_mail",
        "commit",
        "rollback",
        "update",
        "setdefault",
        "pop",
        "clear",
        "invalidate_all",
        "flush_all",
        "_write",
        "_create",
        "_set_password",
        "unlink_all",
    }
)
_EXPR_ESCAPE = frozenset({"cr", "_cr", "pool", "registry", "env_su", "_env", "func_globals"})
_EXPR_BAD_CALLS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "open",
        "globals",
        "locals",
        "vars",
        "type",
        "super",
        "breakpoint",
        "input",
        "memoryview",
    }
)
_EXPR_SAFE_CALLS = frozenset(
    {
        "ref",
        "context_today",
        "relativedelta",
        "timedelta",
        "datetime",
        "date",
        "time",
        "strftime",
        "strptime",
        "now",
        "today",
        "to_string",
        "to_date",
        "to_datetime",
        "str",
        "int",
        "float",
        "bool",
        "len",
        "list",
        "tuple",
        "set",
        "dict",
        "sorted",
        "min",
        "max",
        "sum",
        "abs",
        "any",
        "all",
        "round",
        "get",
        "mapped",
        "filtered",
        "ids",
        "search",
        "browse",
        "exists",
        "filtered_domain",
        "get_param",
        "has_group",
        "user_has_groups",
        "obj",
        "isoformat",
        "replace",
        "combine",
        "join",
        "split",
        "strip",
        "lower",
        "upper",
        "format",
        "startswith",
        "endswith",
        "range",
        "enumerate",
        "zip",
        "keys",
        "values",
        "items",
        "localize",
        "astimezone",
        "timezone",
        "fromisoformat",
        "utcnow",
        "AND",
        "OR",
        "_",
        "_t",
        "is_html_empty",
        "format_date",
        "format_datetime",
        "format_amount",
        "format_duration",
        "_get_company",
        "company",
        "user",
    }
)
# container mutators (no recordset defines them): harmful only on shared state (session, env, registry)
_EXPR_CONTAINER_MUT = frozenset({"pop", "popitem", "setdefault", "clear"})
_EXPR_SHARED = frozenset({"request", "session", "httprequest", "env", "context", "registry", "pool", "cr", "_cr",
                          "self", "user", "company", "website", "odoo", "http", "ir", "config", "tools"})


def _expr_shared(n: ast.AST, tainted: frozenset[str] = frozenset()) -> bool:
    """Does a receiver reach session/env/registry state (vs. a list/dict value of the render)?
    tainted: QWeb t-set names bound to such state (CA13 M3: <t t-set="s" t-value="request.session"/>)."""
    return any((isinstance(x, ast.Name) and (x.id in _EXPR_SHARED or x.id in tainted)) or (isinstance(x, ast.Attribute) and x.attr in _EXPR_SHARED)
               or isinstance(x, ast.Call) for x in ast.walk(n))


_INLINE_EXPR = re.compile(r"\{\{(.+?)\}\}|\$\{(.+?)\}", re.S)
_TPL_EXPR_ATTRS = (
    "t-out",
    "t-esc",
    "t-raw",
    "t-if",
    "t-elif",
    "t-foreach",
    "t-value",
    "t-att",
    "t-options",
    "t-set",
)
_CFG_SECURITY = re.compile(
    r"secret|token|passw|key|auth|signup|oauth|totp|login|session|database\.|web\.base\.url"
    r"|mail\.(?:catchall|bounce|default)|server|url|domain|uuid|cors|iap|webhook",
    re.I,
)


def _qweb_aliases(c: _Ctx, el: Any) -> frozenset[str]:
    """CA13 M3: t-set names that alias session/env/context (transitively), per document."""
    try:
        root = el.getroottree().getroot()
    except (AttributeError, ValueError):
        return frozenset()
    cache = c.__dict__.setdefault("_qweb_alias_cache", {})
    key = id(root)
    if key in cache and cache[key][0] is root:
        return cache[key][1]
    sets = []
    for e in root.iter():
        if not isinstance(e.tag, str) or not e.get("t-set"):
            continue
        v = e.get("t-value") or e.get("value") or (e.text or "")
        try:
            sets.append((e.get("t-set").strip(), ast.parse(v.strip(), mode="eval")))
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            sets.append((e.get("t-set").strip(), None))  # unparseable value: unprovable, taint
    out: set[str] = set()
    for _ in range(len(sets) + 1):
        new = {n for n, t in sets if t is None or _expr_shared(t, frozenset(out))}
        if new <= out:
            break
        out |= new
    cache[key] = (root, frozenset(out))
    return frozenset(out)


def _audit_expr(
    c: _Ctx, path: str, line: int, text: str, where: str, template: bool = False,
    tainted: frozenset[str] = frozenset(),
) -> None:
    """A stored/load-time Python expression (safe_eval domain, context, eval=, QWeb t-*,
    {{ }} inline template): writes, sudo, cursor/registry access, dunders and dynamic
    builtins are HIGH; other unknown calls in a domain/context are MEDIUM."""
    src = (text or "").strip()
    if not src:
        return
    try:
        tree = ast.parse(src, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        bad = _DANGER_PY.search(src) or re.search(r"__|\.(?:sudo|write|unlink|create)\s*\(", src)
        c.add(
            HIGH if bad else LOW,
            "unsafe-expression" if bad else "expression-unparsed",
            path,
            line,
            f"{where}: expression does not parse as Python"
            + (" and reaches internals or writes." if bad else " (Odoo would fail on it)."),
            "Use field names, literals and the documented evaluation context only.",
        )
        return
    high, unknown = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and (n.attr.startswith("__") or n.attr in _EXPR_ESCAPE):
            high.append(f".{n.attr}")
        elif isinstance(n, ast.Name) and n.id.startswith("__"):
            high.append(n.id)
        elif isinstance(n, ast.Call):
            fn = n.func
            nm = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if isinstance(fn, ast.Attribute) and getattr(fn.value, "id", "") == "Command":
                continue  # x2many command tuples
            if template and nm in ("sudo", "with_user", "with_env"):
                continue  # read under elevation for display: qweb-orm-call (MEDIUM)
            if (
                isinstance(fn, ast.Subscript)
                and isinstance(fn.value, ast.Name)
                and not fn.value.id.startswith("_")
                and fn.value.id not in _EXPR_ESCAPE | {"env", "request", "globals", "locals"}
                and isinstance(_const(fn.slice), str)
                and not _const(fn.slice).startswith("_")
                and not (_EXPR_WRITE | _EXPR_BAD_CALLS) & {_const(fn.slice)}
            ):
                # data['get_color']() (stock mrp): a render-value callable chosen by the
                # controller; it cannot be steered to write/elevate from the template.
                unknown.append(f"{fn.value.id}[{_const(fn.slice)!r}]()")
                continue
            if nm in _EXPR_CONTAINER_MUT and isinstance(fn, ast.Attribute) and not _expr_shared(fn.value, tainted):
                continue  # CA12 M2: list/dict pop() on a render-local value; recordsets have no pop()
            if nm in _EXPR_CONTAINER_MUT and isinstance(fn, ast.Attribute):
                high.append(f"{nm}()")  # CA13 M3: mutates session/env/context (directly or via a t-set alias)
                continue
            if nm in _EXPR_BAD_CALLS or nm in _EXPR_WRITE or not nm:
                high.append(f"{nm or ast.unparse(fn)[:30]}()")
            elif nm not in _EXPR_SAFE_CALLS:
                unknown.append(f"{nm}()")
    if high:
        c.add(
            HIGH,
            "unsafe-expression",
            path,
            line,
            f"{where}: expression {', '.join(sorted(set(high))[:4])} writes data, elevates or"
            " reaches the interpreter/cursor.",
            "Expressions must only read: field names, literals, ref(), dates, user/company.",
        )
    elif unknown and not template:
        c.add(
            MEDIUM,
            "expression-call",
            path,
            line,
            f"{where}: expression calls {', '.join(sorted(set(unknown))[:4])} (runs on every"
            " evaluation with the evaluating user's rights).",
            "Keep domains/contexts to literals, ref(), user/company fields and dates.",
        )


def _audit_template_html(c: _Ctx, path: str, line: int, html: str, where: str) -> None:
    """Escaped body_html (mail/sms templates, report bodies) parsed as QWeb/HTML."""
    try:
        import lxml.html as lh

        root = lh.fragment_fromstring(html, create_parent="div")
    except Exception:  # noqa: BLE001 - unparsable markup: fail closed on script text
        if re.search(r"<\s*script|\bon\w+\s*=|javascript:", html, re.I):
            c.add(HIGH, "template-script", path, line, f"{where}: script in template.", "Remove.")
        return
    _audit_template_tree(c, path, line, root.iter(), where)


def _audit_template_tree(c: _Ctx, path: str, line: int, els: Any, where: str) -> None:
    for e in els:
        if not isinstance(e.tag, str):
            continue
        ln = line + max(0, (e.sourceline or 1) - 1) if hasattr(e, "sourceline") else line
        if e.tag.lower() in ("script", "iframe", "object", "embed", "base", "meta"):
            c.add(
                HIGH,
                "template-script",
                path,
                ln,
                f"{where}: <{e.tag}> in a rendered template (runs in the reader's session or"
                " mail client).",
                "Templates must only hold static markup and escaped values.",
            )
        for a, v in e.attrib.items():
            al = a.lower()
            if al.startswith("on") or (al in _URL_ATTRS and _JS_URL.search(v or "")):
                c.add(
                    HIGH,
                    "template-script",
                    path,
                    ln,
                    f"{where}: {a} runs script in a rendered template.",
                    "Remove event handlers and javascript: URLs.",
                )
            if al == "t-raw" or (
                al in ("t-out", "t-esc") and re.search(r"\bMarkup\s*\(|\bmarkup\s*\(", v or "")
            ):
                c.add(
                    HIGH,
                    "template-script",
                    path,
                    ln,
                    f"{where}: {a} renders unescaped HTML in stored content.",
                    "Use t-out with escaped values only.",
                )
            if al in _TPL_EXPR_ATTRS or al.startswith(("t-att-", "t-attf-")):
                if al.startswith("t-attf-"):
                    for m in _INLINE_EXPR.finditer(v or ""):
                        _audit_expr(c, path, ln, m.group(1) or m.group(2), where, True, _qweb_aliases(c, e))
                elif al == "t-foreach" or al != "t-set":
                    _audit_expr(c, path, ln, v, f"{where} {a}", True, _qweb_aliases(c, e))
        for t in (e.text, e.tail):
            for m in _INLINE_EXPR.finditer(t or ""):
                _audit_expr(c, path, ln, m.group(1) or m.group(2), f"{where} {{{{ }}}}", True, _qweb_aliases(c, e))


_OWL_LITERAL = re.compile(r"""\s*(?:'[^'\\]*'|"[^"\\]*"|`[^`$\\]*`|-?\d+(?:\.\d+)?)\s*""")
_OWL_MARKUP = re.compile(r"\b(?:markup|Markup)\s*\(\s*(.*)\)\s*$", re.S)
_OWL_DATA = re.compile(r"\b(?:props|record|env|state)\b|\.data\b")


def owl_out_grade(v: str) -> tuple[str, str] | None:
    """Severity/why for an OWL t-out (Odoo 17+: Markup values render unescaped)."""
    if not v or _OWL_LITERAL.fullmatch(v):
        return None
    m = _OWL_MARKUP.search(v)
    if m:
        if _OWL_LITERAL.fullmatch(m.group(1)):
            return None  # markup of a constant string: fixed, reviewed HTML
        return HIGH, "t-out of markup(...) of runtime data renders it as raw HTML"
    if _OWL_DATA.search(v):
        return MEDIUM, "t-out of props/record data: unescaped when the value is a Markup"
    return None


def _owl_expressions(c: _Ctx, path: str, xl: _XLines, el: Any) -> None:
    """H8: OWL templates under static/ (t-out of Markup props renders raw HTML)."""
    if c.v < 17:
        return
    for a in ("t-out", "t-esc"):
        g = owl_out_grade(el.get(a) or "")
        if g:
            c.add(
                g[0],
                "owl-t-out",
                path,
                xl.el(el, a),
                f"OWL {a}: {g[1]}.",
                "Pass plain strings (escaped) or build Markup only from escaped, fixed parts.",
            )
    # H12: t-on-*/t-att*/t-props are JavaScript run by OWL: audit each one through the
    # JS helper exactly like an inline xml`` template (eval, cookie, URL attributes)
    for a, v in el.attrib.items():
        if not isinstance(a, str) or not _OWL_JS_ATTR.fullmatch(a) or not (v or "").strip():
            continue
        q = "'" if '"' in v and "'" not in v else '"'
        val = v.replace(q, "&quot;") if q == '"' else v
        src = f"<x {a}={q}{val}{q}/>".replace("\\", "\\\\").replace("`", "\\`")
        src = src.replace("${", "\\${")
        line = xl.el(el, a)
        c.web.append((f"{path}#owl:{line}:{a}", path, line, "js", f"xml`{src}`;\n"))


_OWL_JS_ATTR = re.compile(r"t-on-[\w.-]+|t-att-[\w-]+|t-attf-[\w-]+|t-att|t-props|t-call-context")


def _xml_expressions(c: _Ctx, path: str, xl: _XLines, el: Any) -> None:
    """domain/context/domain_force/filter_domain (safe_eval), eval= (load time),
    {{ }} inline templates, body_html QWeb, config parameter records."""
    tag = el.tag if isinstance(el.tag, str) else ""
    if path.startswith("static/"):
        _owl_expressions(c, path, xl, el)  # OWL: JavaScript expressions, not safe_eval
        return
    if tag != "field":
        for a, v in el.attrib.items():
            if a in _TPL_EXPR_ATTRS[:-1] or a.startswith("t-att-"):
                _audit_expr(c, path, xl.el(el, a), v, f"QWeb {a}", True, _qweb_aliases(c, el))
                if a in ("t-out", "t-esc") and re.search(r"\brequest\.(?:params|httprequest)", v):
                    c.add(
                        LOW,
                        "qweb-request-output",
                        path,
                        xl.el(el, a),
                        f"{a} prints request input (escaped unless it is Markup).",
                        "Validate the parameter; never wrap it in Markup.",
                    )
            elif a.startswith("t-attf-"):
                for m in _INLINE_EXPR.finditer(v or ""):
                    _audit_expr(c, path, xl.el(el, a), m.group(1) or m.group(2), f"QWeb {a}", True, _qweb_aliases(c, el))
        return
    parent = el.getparent()
    model = parent.get("model") if parent is not None else ""
    name = el.get("name") or ""
    if el.get("eval") is not None:
        _audit_expr(c, path, xl.el(el, "eval"), el.get("eval"), f"{model}.{name} eval=")
    if el.get("file"):
        ref = el.get("file").strip()
        rel = ref.split("/", 1)[1] if ref.split("/", 1)[0] == getattr(c, "module", None) else ref
        body = c.files.get(rel) if hasattr(c, "files") else None
        binary_field = name not in _STORED_MARKUP and name not in ("code", "arch_db")
        if body is None and binary_field and _inert_ref_ok(c, rel, ref):
            return  # an image/font sniffed true to its extension, stored in a binary field: inert
        if body is None and not binary_field:
            body = _sibling_file(c, ref)  # markup/code from another installed addon: audit its text
        if body is None:
            c.add(
                MEDIUM,
                "data-file-unaudited",
                path,
                xl.el(el, "file"),
                f"{model}.{name} is loaded from {ref}, which is not in the module: unaudited.",
                "Ship the file inside the module (module/path), or inline the value.",
            )
        elif name in _STORED_MARKUP or name in ("code", "arch_db"):
            ftxt = body.decode("utf-8", "replace")
            if name == "code":
                c.add(
                    HIGH,
                    "server-code",
                    path,
                    xl.el(el, "file"),
                    f"{model}.code loaded from {ref}: server code kept outside Python files.",
                    "Write server logic in Python model methods.",
                )
            else:
                _audit_template_html(c, rel, 1, ftxt, f"{model}.{name} (file={ref})")
    text = el.text or ""
    lead = len(text) - len(text.lstrip())
    if name in _EXPR_FIELDS and text.strip() and len(el) == 0:
        _audit_expr(c, path, xl.body(el, lead), text, f"{model or 'record'}.{name}")
    if len(el):
        return  # type="html"/"xml" children: audited element by element by the caller
    if len(el) == 0 and text.strip():
        if "<" in text and name in _STORED_MARKUP:
            _audit_template_html(c, path, xl.body(el, lead), text, f"{model}.{name}")
        elif _INLINE_EXPR.search(text):
            for m in _INLINE_EXPR.finditer(text):
                _audit_expr(
                    c,
                    path,
                    xl.body(el, m.start()),
                    m.group(1) or m.group(2),
                    f"{model}.{name} inline template",
                    True,
                )
    if model == "ir.config_parameter" and name == "key" and text.strip():
        key = text.strip()
        hi = bool(_CFG_SECURITY.search(key))
        c.add(
            HIGH if hi else MEDIUM,
            "config-parameter-record",
            path,
            xl.body(el, lead),
            f"Data record sets system parameter {key!r}"
            + (" (security / auth / routing setting)." if hi else "."),
            "Do not ship system parameters in module data; document the setting instead.",
        )


_DESTRUCTIVE_FN = re.compile(
    r"^(?:_?unlink\w*|_?write|action_(?:un)?archive|toggle_active|update|_?purge\w*|_gc_\w*|"
    r"button_(?:immediate_)?uninstall|module_uninstall|_?drop\w*|_?truncate\w*|_?reset\w*)$"
)


def _function_ids_bounded(el: Any) -> bool:
    """The first argument provably names specific records: literal ids / ref('xmlid'), a
    search= domain, or an eval recordset expression that the recordset-bounds analysis proves
    bounded (same rule as Python sinks). Anything unprovable is unbounded."""
    vs = list(el.iter("value"))
    v0 = vs[0] if vs else None
    if v0 is not None and v0.get("search"):
        try:
            d = ast.parse(v0.get("search"), mode="eval").body
        except (SyntaxError, ValueError):
            return False
        return _domain_bound(d, {}, v0.get("model") or "") in ("B", "F")
    ev = ((v0.get("eval") or "") if v0 is not None else (el.get("eval") or "")).strip()
    lit = r"[\[\]\(\)\s\d,]*(?:ref\(\s*['\"][\w.]+['\"]\s*\)[\[\]\(\)\s\d,]*)*"
    if re.fullmatch(lit, ev):
        return bool(re.search(r"\d|ref\(", ev))
    try:
        t = ast.parse("_x = " + ev)
    except (SyntaxError, ValueError):
        return False
    e = t.body[0].value
    if v0 is None and isinstance(e, (ast.List, ast.Tuple)) and e.elts:
        e = e.elts[0]  # eval="[ids, vals]": the first positional argument
    while isinstance(e, ast.Attribute) and e.attr in ("ids", "id"):
        e = e.value
    if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _RS_SEARCH for n in ast.walk(e)):
        return False
    return _Bounds(t).unbounded(e) is None


def _dep_defs(c: _Ctx) -> set[str]:
    """Method names defined by the declared dependency closure, when the installed addons are
    on disk (directory audit). Without them a dependency's method stays unknown (fail closed)."""
    dirs = getattr(c, "addons_dirs", []) or []
    if not dirs:
        return set()

    def deps(man: bytes) -> list[str]:
        try:
            m = ast.literal_eval(man.decode("utf-8", "replace"))
        except (SyntaxError, ValueError):
            return []
        return [str(d) for d in (m.get("depends") or [])] if isinstance(m, dict) else []

    todo, seen, out = deps(c.files.get("__manifest__.py", b"")), set(), set()
    while todo and len(seen) < 200:
        d = todo.pop()
        if d in seen:
            continue
        seen.add(d)
        root = next((r / d for r in dirs if (r / d / "__manifest__.py").is_file()), None)
        if root is None:
            continue
        todo += deps((root / "__manifest__.py").read_bytes())
        for f in root.rglob("*.py"):
            if "tests" in f.relative_to(root).parts:
                continue
            try:
                t = ast.parse(f.read_bytes())
            except (SyntaxError, ValueError, OSError):
                continue
            out |= {n.name for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return out


def _module_defs(c: _Ctx) -> frozenset[str]:
    """Method names defined in this module's own (audited) Python."""
    got = getattr(c, "_defs", None)
    if got is None:
        names: set[str] = set()
        for f, b in c.files.items():
            if f.endswith(".py"):
                try:
                    t = ast.parse(b)
                except (SyntaxError, ValueError):
                    continue
                names |= {n.name for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        names |= _dep_defs(c)
        got = c._defs = frozenset(names)
    return got


def _function_on_own_records(c: _Ctx, model: str, fn: str, el: Any) -> bool:
    """M6: a core-model <function> provably limited to this module's own records
    (xmlids it owns / its own ir.module.module row) is MEDIUM, anything else HIGH."""
    mod = getattr(c, "module", None) or ""
    if not mod:
        return False
    vals = " ".join((v.get("eval") or "") + (v.text or "") for v in el.iter("value"))
    if model == "ir.model.data" and fn == "_update_xmlids":
        ids = re.findall(r"""['"]xml_id['"]\s*:\s*['"]([^'"]+)['"]""", vals)
        return (
            bool(ids)
            and all(i.startswith(mod + ".") for i in ids)
            and (vals.count("xml_id") == len(ids))
        )
    if model == "ir.module.module":
        refs = re.findall(r"""ref\(\s*['"]([^'"]+)['"]\s*\)""", vals)
        rest = re.sub(r"""ref\(\s*['"][^'"]+['"]\s*\)|[\[\],\s]""", "", vals)
        return bool(refs) and not rest and all(r == f"base.module_{mod}" for r in refs)
    return False


_STORED_MARKUP = frozenset(
    {"body_html", "body", "description", "arch_db", "arch", "arch_base", "note", "raw"}
)
_ADMIN_GROUPS = re.compile(r"\bbase\.group_(?:system|erp_manager|no_one)\b|\bgroup_system\b")
_GROUP_FIELDS = re.compile(r"^(?:implied_ids|groups_id|group_ids|all_implied_ids|users|user_ids)\b")
_OPEN_DOMAIN = re.compile(r"^\s*\[\s*(?:\(\s*1\s*,\s*['\"]=['\"]\s*,\s*1\s*\)\s*,?\s*)?\]\s*$")
_TRUE = ("1", "True", "true")


def _record_checks(
    c: _Ctx,
    path: str,
    line: int,
    model: str,
    vals: dict[str, str],
    csv_row: bool = False,
    rid: str = "",
    eval_code: bool = False,
) -> None:
    """Data-record rules shared by XML <record>, CSV rows and JSON/YAML data (column names:
    groups_id/id, model_id:id, ...). vals maps field name -> text / eval / ref.
    Deny by default: policy.data_record_policy grades every record on the security core."""
    policy.data_record_policy(
        c.add, HIGH, path, line, model, ({"id": rid} if rid else {}) | vals, c.module
    )
    v = {k.split("/")[0].split(":")[0]: (x or "").strip() for k, x in vals.items()}
    if model == "ir.actions.server" and re.search(r"\.unlink\s*\(", v.get("code", "")):
        c.add(
            MEDIUM,
            "server-action-unlink",
            path,
            line,
            "Server action deletes records"
            + (f" of {v.get('model_id')}" if v.get("model_id") else "")
            + ": wired to an automation it deletes data on every trigger.",
            "Archive instead of deleting, or limit the action to this module's own model.",
        )
    if model == "ir.default" and re.search(
        r"field_(?:res_users|res_groups|ir_|res_company|auth_)", v.get("field_id", "")
    ):
        c.add(
            MEDIUM,
            "sensitive-default",
            path,
            line,
            f"ir.default sets a default on a security-core field ({v.get('field_id')}).",
            "Do not ship defaults for users/groups/company/ir.* fields.",
        )
    if model == "ir.default" and v.get("json_value"):
        # probe x-default-value-expr: the stored JSON is the default every new record gets
        jv = v["json_value"]
        try:
            parsed = json.loads(jv)
        except (ValueError, RecursionError):
            parsed = _JSON_BAD
        fname = re.sub(r".*__", "", v.get("field_id", ""))
        if parsed is _JSON_BAD:
            c.add(
                HIGH,
                "default-value-unaudited",
                path,
                line,
                "ir.default json_value is not JSON: the stored default is undecidable.",
                "Store a plain JSON literal.",
            )
        elif re.fullmatch(
            r"groups_id|group_ids|implied_ids|share|password|login|company_ids|user_ids|"
            r"users|sel_groups_\w+|in_group_\w+",
            fname,
        ) or (fname == "active" and re.search(r"field_(?:res_users|res_groups|ir_)", v.get("field_id", ""))) or re.search(r"group_(?:system|erp_manager|no_one)|__\w+__", jv):
            c.add(
                HIGH,
                "privilege-default",
                path,
                line,
                f"ir.default gives every new record a privilege value ({fname or 'json_value'}={jv[:60]}).",
                "Do not ship defaults for privilege fields.",
            )
    if model == "ir.model.access" and not v.get("group_id"):
        if any(v.get(p) in _TRUE for p in ("perm_write", "perm_create", "perm_unlink")):
            c.add(
                HIGH,
                "access-global-write",
                path,
                line,
                f"{v.get('id') or 'access record'} gives every user (no group)"
                " write/create/delete.",
                "Restrict the rule to a group.",
            )
    for k, x in vals.items():
        if (
            _GROUP_FIELDS.match(k)
            and model in ("res.groups", "res.users")
            and _ADMIN_GROUPS.search(x)
        ):
            c.add(
                HIGH,
                "privilege-grant",
                path,
                line,
                f"{model} data puts users in an administrator group ({k}: settings/technical"
                " rights) at install.",
                "Never grant administrator rights from module data; let an admin assign groups.",
            )
    if model == "res.users" and (v.get("password") or v.get("new_password")):
        c.add(
            HIGH,
            "user-credential-data",
            path,
            line,
            "Module data creates a user with a known password (a shipped login).",
            "Do not ship users with passwords; create them inactive or without password.",
        )
    if (
        model == "ir.rule"
        and _OPEN_DOMAIN.match(v.get("domain_force", "") or "[]")
        and (v.get("global") in _TRUE or not v.get("groups"))
    ):
        target = v.get("model_id", "")
        sens = any(target.endswith("model_" + m.replace(".", "_")) for m in SENSITIVE_MODELS)
        c.add(
            HIGH if sens else MEDIUM,
            "rule-open-domain",
            path,
            line,
            f"Global record rule with an always-true domain on {target or 'a model'}"
            " (lifts restrictions for every user).",
            "Give the rule a real domain and groups.",
        )
    if model in _SERVER_CODE_MODELS | {"ir.server.object.lines"}:
        if (csv_row or eval_code) and v.get("code"):
            # CSV text, or an XML eval="'...'" string literal: same code path as <field>text (H10)
            _audit_py(c, path, ("\n" * max(0, line - 1) + v["code"]).encode(), server_code=True)
        if v.get("evaluation_type") == "equation" and v.get("value"):
            _audit_py(c, path, ("\n" * max(0, line - 1) + v["value"]).encode(), server_code=True)
        if v.get("state") == "webhook" or v.get("webhook_url"):
            sens = re.search(r"password|token|secret|api_?key|totp", v.get("webhook_field_ids", ""))
            c.add(
                HIGH,
                "server-webhook",
                path,
                line,
                f"Server action posts records to {v.get('webhook_url') or 'an external URL'}"
                + (" including credential fields." if sens else " (data leaves the database)."),
                "Do not ship webhooks in module data; let an admin configure them.",
            )
    if model == "ir.model.fields":
        if v.get("compute"):
            _audit_py(c, path, ("\n" * max(0, line - 1) + v["compute"]).encode(), server_code=True)
        for k in ("related", "depends"):
            if any(
                _SENSITIVE_FIELDS.match(p.strip().split(".")[-1])
                for p in v.get(k, "").split(",")
                if p.strip()
            ):
                c.add(
                    HIGH,
                    "sensitive-field-exposure",
                    path,
                    line,
                    f"Manual field {k} {v[k]!r} copies a credential field into a readable field.",
                    "Never relate or compute from password/token fields.",
                )
    if model == "ir.actions.report":
        for k in ("print_report_name", "attachment"):
            if v.get(k):
                _audit_expr(c, path, line, v[k], f"ir.actions.report.{k}")
    if model == "ir.asset" and _EXT_URL.match(v.get("path", "")):
        c.add(
            HIGH,
            "asset-external",
            path,
            line,
            f"ir.asset loads {v['path']} from an external host into a bundle (code that"
            " can change after review).",
            "Ship the file in static/ and list it in the manifest assets.",
        )
    if model == "ir.attachment":
        mime = v.get("mimetype", "")
        blob = v.get("raw", "")
        if v.get("datas"):
            import base64
            import binascii

            try:
                blob = base64.b64decode(v["datas"], validate=False).decode("utf-8", "replace")
            except (binascii.Error, ValueError):
                blob = ""
        name = v.get("name", "")
        scripty = re.search(r"javascript|ecmascript|html|svg|xml", mime, re.I) or name.endswith(
            (".js", ".mjs", ".html", ".htm", ".svg", ".xhtml")
        )
        if scripty or re.search(r"<\s*script|\beval\s*\(", blob, re.I):
            c.add(
                HIGH,
                "attachment-active-content",
                path,
                line,
                f"Data attachment {name or ''} stores active content ({mime or 'script'})"
                + (" served publicly." if v.get("public") in _TRUE else "."),
                "Ship web code in static/ (audited); attachments must hold inert data only.",
            )


def _fields_lines(c: _Ctx, path: str, line: int, ev: str) -> None:
    """fields_lines eval=[(0,0,{'evaluation_type':'equation','value':'<code>'})]: code."""
    if "equation" not in ev:
        return
    try:
        tree = ast.parse(ev, mode="eval")
    except (SyntaxError, ValueError):
        c.add(HIGH, "parse-error", path, line, "fields_lines eval does not parse.", "Fix it.")
        return
    for d in ast.walk(tree):
        if isinstance(d, ast.Dict):
            kv = {_const(k): x for k, x in zip(d.keys, d.values, strict=False) if k is not None}
            if _const(kv.get("evaluation_type")) == "equation":
                code = _const(kv.get("value"))
                if isinstance(code, str):
                    _audit_py(c, path, ("\n" * max(0, line - 1) + code).encode(), server_code=True)
                else:
                    c.add(
                        HIGH,
                        "expression-unaudited",
                        path,
                        line,
                        "fields_lines equation value is computed: the code cannot be audited.",
                        "Use a literal value.",
                    )


def _xml_operations(c: _Ctx, path: str, xl: _XLines, el: Any) -> None:
    """Server action / cron / automation code (audited with the Python rules), <function>
    calls and <delete> at install or update."""
    tag = el.tag if isinstance(el.tag, str) else ""
    parent = el.getparent()
    if (
        tag == "field"
        and el.get("name") == "code"
        and parent is not None
        and parent.get("model") in _SERVER_CODE_MODELS
        and (el.text or "").strip()
    ):
        raw = el.text
        lead = raw[: len(raw) - len(raw.lstrip())]
        line = xl.body(el, len(lead))
        _audit_py(c, path, ("\n" * (line - 1) + raw.strip()).encode(), server_code=True)
    if tag == "function":
        m, fn = el.get("model") or "", el.get("name") or ""
        sens = m in SENSITIVE_MODELS and fn not in _READ_ONLY_CALLS
        own = sens and _function_on_own_records(c, m, fn, el)
        if not sens and _DESTRUCTIVE_FN.match(fn) and not _function_ids_bounded(el):
            c.add(HIGH, "xml-function-destructive", path, xl.el(el, "name"),
                  f"<function> calls {m}.{fn}() as superuser at every install/update on records it cannot prove bounded.",
                  "Use <delete>/<record> on xmlids this module owns, or a reviewed migration.")  # fmt: skip
        elif not sens and fn not in _READ_ONLY_CALLS and not _DESTRUCTIVE_FN.match(fn) and fn not in _module_defs(c):
            c.add(MEDIUM, "xml-function-unknown", path, xl.el(el, "name" if fn else None),
                  f"<function> calls {m}.{fn}(), a method this module does not define: its effect cannot be audited.",
                  "Call a method defined (and audited) in this module, or use data records.")  # fmt: skip
        c.add(
            MEDIUM if own else HIGH if sens else LOW,
            "xml-function-call",
            path,
            xl.el(el, "name" if el.get("name") else None),
            f"<function> calls {m}.{fn}() at every install/update"
            + (" on the security core." if sens else "."),
            "Use data records or a reviewed migration; never change security records this way.",
        )
    if tag == "delete":
        m, rid = el.get("model") or "", el.get("id") or ""
        if m in SENSITIVE_MODELS:
            sev, why = HIGH, f"deletes {m} records (security core)"
        elif el.get("search"):
            own = m in c.new_models or m.startswith(f"x_{c.module}") or m.startswith(c.module + ".")
            empty = bool(_OPEN_DOMAIN.match(el.get("search")))
            sev = MEDIUM if own and not empty else HIGH
            why = f"deletes every {m} record matching a domain" + (
                " (all of them)" if empty else ""
            )
        elif "." in rid and rid.split(".", 1)[0] != c.module:
            sev, why = MEDIUM, f"deletes {rid}, which belongs to another module"
        else:
            return
        c.add(
            sev,
            "xml-delete",
            path,
            xl.el(el),
            f"<delete> {why} at install/update.",
            "Delete only this module's own records, by xmlid.",
        )


def _audit_xml(c: _Ctx, path: str, body: bytes) -> None:
    try:
        root = _parse_xml_lines(body)
        enc = root.getroottree().docinfo.encoding or "utf-8"
        try:
            text = body.decode(enc)
        except (LookupError, UnicodeDecodeError):
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
            if attr == "action" and not re.fullmatch(r"[\w.]+", val or ""):
                continue  # an HTML form/URL action, not an xmlid (checked by _qweb_attr_checks)
            if val and attr != "groups":
                c.refs.append((val, path, xl.el(el, attr)))
        for a, val in el.attrib.items():
            _qweb_attr_checks(c, path, xl, el, a, val)
            if a.startswith("t-") and a != "t-name" and _QWEB_ORM.search(val):
                c.add(
                    MEDIUM,
                    "qweb-orm-call",
                    path,
                    xl.el(el, a),
                    f"Template expression in {a} calls sudo()/ORM methods or reads credentials.",
                    "Compute values in Python with access checks; templates must only display.",
                )
            if (a == "style" or a in ("t-att-style", "t-attf-style")) and (
                m := _STYLE_RISK.search(val)
            ):
                ext = bool(m.group(1))
                c.add(
                    MEDIUM if ext else HIGH,
                    "css-external-url" if ext else "css-expression",
                    path,
                    xl.el(el, a),
                    "Inline style loads from an external host."
                    if ext
                    else "Inline style runs script (expression()/javascript:/behavior).",
                    "Use bundled assets and plain CSS.",
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
                "invisible",
                "readonly",
                "required",
                "column_invisible",
                "options",
                "attrs",
                "states",
            ) and (_DANGER_PY.search(val) or re.search(r"__\w+__", val)):
                c.add(
                    HIGH,
                    "unsafe-expression",
                    path,
                    xl.el(el, a),
                    f"Expression in {a} reaches Python internals or sudo.",
                    "Use only field names and literals in domains, contexts and evals.",
                )
            # M6 (review 6): view modifiers are expressions too; fail closed when they do not
            # parse, and grade env/sudo/ORM writes in them like any other expression
            if a in ("invisible", "readonly", "required", "column_invisible") and not path.startswith("static/") \
                    and val.strip() not in ("", "1", "0", "True", "False", "true", "false"):
                try:
                    mt = ast.parse(val.strip(), mode="eval")
                except (SyntaxError, ValueError, RecursionError, MemoryError):
                    mt = None
                    c.add(MEDIUM, "expression-unparsed", path, xl.el(el, a),
                          f"{a} modifier does not parse as an expression: unaudited (and the view fails to load).",
                          "Write the modifier as a plain expression over field names.")  # fmt: skip
                if mt is not None and any(
                    (isinstance(y, ast.Name) and y.id in ("env", "request", "cr", "pool", "registry"))
                    or (isinstance(y, ast.Attribute) and y.attr in ("sudo", "write", "unlink", "create", "env", "cr"))
                    for y in ast.walk(mt)
                ):
                    c.add(HIGH, "unsafe-expression", path, xl.el(el, a),
                          f"{a} modifier reaches env/sudo/ORM writes: not a field expression.",
                          "Use only field names and literals in modifiers.")  # fmt: skip
            if a == "context" and el.tag != "record":
                pk = re.search(
                    r"""['"]default_(groups_id|group_ids|implied_ids|share|password|company_ids|"""
                    r"""sel_groups_\w+|in_group_\w+|user_ids|users)['"]\s*:""",
                    val,
                )
                if pk:
                    c.add(
                        HIGH,
                        "context-privilege-default",
                        path,
                        xl.el(el, a),
                        f"context sets default_{pk.group(1)}: records created from this view get"
                        " privilege fields (used server-side by create()).",
                        "Do not default security fields from a view context.",
                    )
        if el.tag == "record" and el.get("model"):
            vals = {}
            eval_code = False
            for f in el.findall("field"):
                if f.get("name") == "code" and f.get("eval"):
                    try:
                        lit = ast.literal_eval(f.get("eval"))
                    except (ValueError, SyntaxError, MemoryError, RecursionError):
                        lit = None
                    if isinstance(lit, str):
                        vals["code"] = lit
                        eval_code = True
                        continue
                if f.get("name"):
                    inner = (f.text or "") + "".join(
                        ET.tostring(ch, encoding="unicode") if isinstance(ch.tag, str) else ""
                        for ch in f
                    )
                    vals[f.get("name")] = (
                        f.get("eval") or f.get("ref") or f.get("search") or inner
                    )
            _record_checks(
                c, path, xl.el(el), el.get("model"), vals, rid=el.get("id") or "", eval_code=eval_code
            )
            _fields_lines(
                c, path, xl.el(el), vals.get("fields_lines", "") or vals.get("update_field_ids", "")
            )
        if (
            el.tag == "button"
            and el.get("type") == "object"
            and (el.get("name") or "") in _EXPR_WRITE | {"unlink", "write", "action_archive"}
            and re.search(r"group_(?:public|portal)\b", el.get("groups") or "")
        ):
            c.add(
                HIGH,
                "public-button",
                path,
                xl.el(el, "name"),
                f"Button calls {el.get('name')}() and is shown to public/portal users.",
                "Restrict the button to internal groups; check rights in the method.",
            )
        if el.tag == "field" and el.get("search") and _DANGER_PY.search(el.get("search")):
            c.add(
                HIGH,
                "unsafe-expression",
                path,
                xl.el(el, "search"),
                "Expression in search= reaches Python internals (evaluated at load).",
                "Use only field names and literals in domains.",
            )
        if isinstance(el.tag, str) and el.tag.endswith("}include") and "XInclude" in el.tag:
            c.add(
                HIGH,
                "xml-xinclude",
                path,
                xl.el(el),
                "XInclude element: pulls an external file into the data.",
                "Remove XInclude; Odoo data files are self-contained.",
            )
        _qweb_resources(c, path, xl, el)
        _xml_operations(c, path, xl, el)
        _xml_expressions(c, path, xl, el)
        if (
            el.tag == "field"
            and el.get("name") == "code"
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
    "owl-t-out": "Pass plain strings to t-out; build Markup only from escaped, fixed parts.",
    "js-flow-sink": "Do not route runtime values into a helper that evaluates or renders HTML.",
    "js-flow-incomplete": "Simplify the call graph; this file could not be fully analysed.",
}


def _audit_web(c: _Ctx) -> None:
    """JS and stylesheets through the pinned parser helper; fail closed per file."""
    todo = [
        (k, f, ln, "js" if kind == "tryjs" else kind, t)
        for k, f, ln, kind, t in c.web
        if kind not in ("unparseable", "inert", "foreign")
    ]
    tried = {k for k, _, _, kind, _ in c.web if kind == "tryjs"}
    for _, file, line, _, _ in (w for w in c.web if w[3] == "inert"):
        c.add(
            INFO,
            "web-unaudited",
            file,
            line,
            "Type declarations only (.d.ts): no runtime code to audit.",
            "Nothing to do.",
        )
    for _, file, line, _, _ in (w for w in c.web if w[3] == "foreign"):
        c.add(
            HIGH,
            "web-unaudited",
            file,
            line,
            "Cannot parse, unaudited: a build-step source Odoo's asset bundles never load"
            " (only its compiled output would run).",
            "Ship the compiled JavaScript/CSS in the module, or review this file by hand.",
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
    res = web.run(
        [(key, kind, text) for key, _, _, kind, text in todo],
        props_domain=c.props_domain,
    )
    for key, file, line0, _, _ in todo:
        r = res.get(key) if isinstance(res, dict) else None
        if r is None or not r.get("ok"):
            why = res if isinstance(res, str) else (r or {}).get("error", "no result")
            typed = key in tried and isinstance(res, dict)  # TypeScript/JSX syntax: not loaded
            c.add(
                MEDIUM if typed else HIGH,
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


_PO_RISK = re.compile(
    r"<\s*(?:script|iframe|object|embed|base|meta|form|svg)\b|\bon[a-z]{3,30}\s*=|"
    r"javascript\s*:|\bt-(?:raw|out|esc)\s*=",
    re.I,
)


def _po_entries(text: str):
    """(msgid, msgstr, msgstr line) for each entry of a .po file."""
    msgid, msgstr, cur, line = [], [], None, 0
    for i, ln in enumerate(text.splitlines(), 1):
        t = ln.strip()
        if t.startswith("msgid "):
            if msgstr:
                yield "".join(msgid), "".join(msgstr), line
            msgid, msgstr, cur = [t[6:].strip().strip('"')], [], "id"
        elif t.startswith("msgid_plural "):
            msgid.append(t[13:].strip().strip('"'))
            cur = "id"
        elif t.startswith("msgstr"):
            msgstr.append(t.split(" ", 1)[1].strip().strip('"') if " " in t else "")
            cur, line = "str", line or i
            line = i if len(msgstr) == 1 else line
        elif t.startswith('"') and cur:
            (msgid if cur == "id" else msgstr).append(t.strip('"'))
    if msgstr:
        yield "".join(msgid), "".join(msgstr), line


# attributes Odoo translates inside terms (their text may differ); every other attribute
# and every tag must match the source term exactly
_PO_TEXT_ATTRS = frozenset({"title", "alt", "label", "placeholder", "aria-label", "data-tooltip"})


def _po_structure(s: str) -> tuple[Counter[tuple[str, tuple[tuple[str, str], ...]]], bool]:
    """Multiset of (tag, attributes) a term renders as, the way Odoo's xml/html translate
    parses it (lxml HTML fragment); True when it does not parse."""
    from lxml import etree
    from lxml import html as lhtml

    out: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
    try:
        root = lhtml.fragment_fromstring(s, create_parent="div")
    except (etree.ParserError, ValueError, TypeError):
        return out, True
    for el in root.iterdescendants():
        if not isinstance(el.tag, str):
            out[("#" + type(el).__name__.lower(), ())] += 1  # comments / PIs
            continue
        attrs = tuple(
            sorted(
                (str(k).lower(), "" if str(k).lower() in _PO_TEXT_ATTRS else str(v))
                for k, v in el.attrib.items()
            )
        )
        out[(el.tag.lower(), attrs)] += 1
    return out, False


def _audit_po(c: _Ctx, path: str, body: bytes) -> None:
    """Translated template terms render as markup: a translation must not add script,
    event handlers or javascript: URLs its source text does not have."""
    cs = re.search(rb"charset\s*=\s*([A-Za-z0-9_.:-]+)", body[:4096], re.I)
    charset = cs.group(1).decode("ascii", "replace").lower() if cs else "utf-8"
    try:
        text = body.decode("utf-8", "strict")
    except UnicodeDecodeError:
        text = None
    pf = re.search(r"Plural-Forms:[^\n\"]*?plural\s*=\s*([^;\\\"]*)", text or "")
    if pf and not re.fullmatch(r"[\sn0-9%<>=!&|?:()+\-*/]*", pf.group(1)):
        # L2: Odoo does not evaluate it; non-standard arithmetic stays LOW, but code-shaped text
        # (names, calls, quotes, attribute access) has no place in a translation file: MEDIUM
        code_like = re.search(r"[A-Za-mo-z_'\"\[\].]|\bn\w", pf.group(1))
        c.add(
            MEDIUM if code_like else LOW,
            "po-plural-forms",
            path,
            (text or "")[: pf.start()].count("\n") + 1,
            "Plural-Forms expression holds more than n, numbers and operators.",
            "Use the standard gettext Plural-Forms expression for the language.",
        )
    if text is None or charset.replace("_", "-") not in ("utf-8", "utf8", "charset"):
        c.add(
            HIGH,
            "po-unaudited",
            path,
            1,
            f"Translation file is not plain UTF-8 (charset {charset!r}): its rendered text is"
            " undecidable (e.g. UTF-7 hides markup).",
            "Save translations as UTF-8 with 'charset=UTF-8'.",
        )
        return
    for msgid, msgstr, line in _po_entries(text):
        src = {m.group(0).lower() for m in _PO_RISK.finditer(msgid)}
        new = [m.group(0) for m in _PO_RISK.finditer(msgstr) if m.group(0).lower() not in src]
        if new:
            c.add(
                HIGH,
                "po-markup-injection",
                path,
                line,
                f"Translation adds {new[0]!r} that the source term does not contain: rendered as"
                " markup in templates (stored XSS).",
                "Translate text only; keep the source term's markup unchanged.",
            )
            continue
        if "<" not in msgstr and "&" not in msgstr:
            continue
        got, bad = _po_structure(msgstr)
        want, _ = _po_structure(msgid)
        if bad and "<" in msgstr:
            c.add(
                HIGH,
                "po-markup-injection",
                path,
                line,
                "Translation markup does not parse: its rendered structure is undecidable.",
                "Translate text only; keep the source term's markup unchanged.",
            )
            continue
        extra = got - want
        if extra:
            tag, attrs = next(iter(extra))
            c.add(
                MEDIUM,
                "po-markup-change",
                path,
                line,
                f"Translation adds or changes markup <{tag}{''.join(' ' + a for a, _ in attrs)}>"
                " that the source term does not have (Odoo keeps translated markup).",
                "Keep exactly the source term's tags and attributes; translate text only.",
            )


_SMIL = frozenset({"set", "animate", "animatetransform", "animatemotion", "animatecolor"})


def _markup_doc_checks(c: _Ctx, path: str, el: Any, tag: str, ln: int, kind: str) -> None:
    """Navigation / origin hijacks in static documents and SVG animation that rewrites
    handlers or links (SMIL set/animate)."""
    at = {a.rsplit("}", 1)[-1].lower(): v or "" for a, v in el.attrib.items()}
    if tag == "meta" and at.get("http-equiv", "").lower() == "refresh":
        url = at.get("content", "").split("=", 1)[-1]
        js = bool(_JS_URL.search(url) or "javascript:" in url.lower().replace(" ", ""))
        if js or _EXT_URL.search(url) or "url=" in at.get("content", "").lower():
            c.add(
                HIGH if js or _EXT_URL.search(url) else MEDIUM,
                "markup-redirect",
                path,
                ln,
                "meta refresh navigates the reader (javascript: or another host).",
                "Remove the redirect.",
            )
    if tag == "base" and at.get("href"):
        c.add(
            HIGH if _EXT_URL.search(at["href"]) or _JS_URL.search(at["href"]) else MEDIUM,
            "markup-base",
            path,
            ln,
            "<base href> rewrites every relative URL of the document.",
            "Remove <base>.",
        )
    if tag == "form" or (tag in ("button", "input") and at.get("formaction")):
        act = at.get("action") or at.get("formaction") or ""
        if _EXT_URL.search(act) or _JS_URL.search(act):
            pwd = any(
                (x.get("type") or "").lower() == "password"
                for x in el.iter()
                if isinstance(x.tag, str)
            )
            c.add(
                HIGH if pwd or _JS_URL.search(act) else MEDIUM,
                "markup-form-action",
                path,
                ln,
                "Form posts to another host" + (" with a password field." if pwd else "."),
                "Post only to this server's routes.",
            )
    if tag in _SMIL:
        name = at.get("attributename", "").lower().rsplit(":", 1)[-1]
        vals = " ".join(at.get(k, "") for k in ("to", "values", "from", "by"))
        if (
            name.startswith("on")
            or (
                name in ("href", "src")
                and (
                    _JS_URL.search(vals)
                    or "javascript:" in vals.lower()
                    or _EXT_URL.search(vals)
                    or not vals.strip()
                )
            )
            or name in ("href", "src")
            and "data:" in vals.lower()
        ):
            c.add(
                HIGH,
                "markup-animation",
                path,
                ln,
                f"SVG <{tag}> rewrites {name or 'an attribute'} (script or navigation on"
                " interaction).",
                "Remove animations of handlers and links.",
            )


def _audit_markup_file(c: _Ctx, path: str, body: bytes, kind: str) -> None:
    """SVG / HTML documents served from static/: scripts, handlers and javascript: URLs run
    in the server's origin when the file is opened."""
    try:
        from lxml import etree
    except ImportError:
        c.add(
            HIGH,
            "web-unaudited",
            path,
            0,
            "Cannot parse, unaudited (lxml missing).",
            "Install lxml.",
        )
        return
    try:
        if kind == "svg":
            if b"<!ENTITY" in body.upper():
                raise ValueError("entities are not allowed")
            parser = etree.XMLParser(
                resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
            )
        else:
            parser = etree.HTMLParser(no_network=True, remove_comments=True, remove_pis=True)
        root = etree.fromstring(body, parser)
    except (ValueError, etree.XMLSyntaxError) as e:
        c.add(
            HIGH,
            "web-unaudited",
            path,
            0,
            f"Cannot parse, unaudited ({str(e)[:120]}).",
            "Fix the file, or remove it.",
        )
        return
    if root is None:
        return
    # parser differential: lxml (HTML4/XML) and a browser (HTML5) may disagree on a malformed
    # tag; any script-like opening the parse did not yield is reported (fail closed)
    parsed_scripts = sum(
        1
        for el in root.iter()
        if isinstance(el.tag, str) and el.tag.rsplit("}", 1)[-1].lower() == "script"
    )
    raw_open = len(re.findall(rb"<\s*script\b", body, re.I))
    if raw_open > parsed_scripts:
        c.add(
            HIGH,
            "markup-script",
            path,
            1,
            "Malformed <script> markup the parser did not read as a script (a browser may).",
            "Ship well-formed static documents without scripts.",
        )
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.rsplit("}", 1)[-1].lower()
        ln = el.sourceline or 1
        for a, val in el.attrib.items():
            an = a.rsplit("}", 1)[-1].lower()
            if re.fullmatch(r"on[a-z]{3,30}", an):
                c.add(
                    HIGH,
                    "markup-inline-handler",
                    path,
                    ln,
                    f"{tag} {an}= runs script when the {kind.upper()} file is opened.",
                    "Remove event handlers from static documents.",
                )
            if an in ("href", "src", "action", "formaction", "data") and _JS_URL.search(val):
                c.add(
                    HIGH, "markup-js-url", path, ln, f"{an} holds a javascript: URL.", "Remove it."
                )
            if an == "srcdoc":
                active = re.search(r"<\s*script|\bon[a-z]+\s*=|javascript:", val, re.I)
                c.add(
                    HIGH if active else MEDIUM,
                    "markup-script" if active else "markup-srcdoc",
                    path,
                    ln,
                    f"<{tag} srcdoc> holds an inline document"
                    + (" with script." if active else " (unaudited HTML)."),
                    "Remove srcdoc; ship static documents without embedded pages.",
                )
            if (an in ("data", "src") and tag in ("object", "embed", "applet")) or (
                an == "href" and tag == "feimage" and _EXT_URL.search(val)
            ):
                plugin = tag in ("object", "embed", "applet")
                c.add(
                    HIGH if plugin and _EXT_URL.search(val) else MEDIUM,
                    "markup-plugin" if plugin else "markup-external-resource",
                    path,
                    ln,
                    f"<{tag}> {'embeds plugin content' if plugin else 'loads'} {val[:80]}.",
                    "Ship plain images/documents; no plugins or remote filter inputs.",
                )
            if an in ("href", "src") and tag in ("script", "iframe", "use", "image", "link"):
                if _EXT_URL.search(val):
                    c.add(
                        HIGH if tag in ("script", "iframe") else MEDIUM,
                        "markup-external-resource",
                        path,
                        ln,
                        f"<{tag}> loads from an external host ({val[:80]}).",
                        "Bundle the resource with the module.",
                    )
        _markup_doc_checks(c, path, el, tag, ln, kind)
        if tag == "script":
            c.add(
                HIGH,
                "markup-script",
                path,
                ln,
                f"{kind.upper()} contains a <script>: it runs in the server's origin when opened.",
                "Ship static documents without scripts.",
            )
            code = "".join(el.itertext())
            if code.strip() and not _data_script(c, path, ln, (el.get("type") or "").lower(), code):
                c.web.append((f"{path}#script@{ln}", path, ln, "js", code))
        elif tag == "style":
            css = "".join(el.itertext())
            if css.strip():
                c.web.append((f"{path}#style@{ln}", path, ln, "css", css))
        elif tag == "foreignobject" and kind == "svg":
            c.add(
                MEDIUM,
                "markup-script",
                path,
                ln,
                "SVG embeds HTML (foreignObject).",
                "Ship plain vector images.",
            )


_CORE_TABLES = re.compile(
    r"\b(?:res_users\w*|res_groups\w*|res_company\w*|ir_\w+|auth_\w+|res_partner\w*)\b", re.I
)


def _manifest_files(manifest: dict[str, Any] | None) -> set[str]:
    out: set[str] = set()
    for k in ("data", "demo", "init_xml", "update_xml", "demo_xml"):
        v = (manifest or {}).get(k)
        if isinstance(v, (list, tuple)):
            out |= {str(x) for x in v}
    return out


_MAGIC_OF = {
    (".png",): (b"\x89PNG\r\n\x1a\n",),
    (".jpg", ".jpeg"): (b"\xff\xd8\xff",),
    (".gif",): (b"GIF87a", b"GIF89a"),
    (".ico",): (b"\x00\x00\x01\x00",),
    (".cur",): (b"\x00\x00\x02\x00",),
    (".bmp",): (b"BM",),
    (".tif", ".tiff"): (b"II*\x00", b"MM\x00*"),
    (".woff",): (b"wOFF",),
    (".woff2",): (b"wOF2",),
    (".ttf",): (b"\x00\x01\x00\x00", b"true", b"ttcf"),
    (".otf",): (b"OTTO", b"\x00\x01\x00\x00"),
    (".ogg",): (b"OggS",),
    (".webm",): (b"\x1aE\xdf\xa3",),
    (".pdf",): (b"%PDF",),
    (".docx", ".xlsx", ".odt", ".ods"): (b"PK\x03\x04",),
    (".doc", ".xls"): (b"\xd0\xcf\x11\xe0",),
    (".mp3",): (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
}
_FTYP = (".mp4", ".mov", ".m4a", ".avif")
_ACTIVE = re.compile(
    rb"<\s*(script|html|svg|iframe|object|embed)\b|javascript:|\bon[a-z]+\s*=", re.I
)
_PIP_SRC = re.compile(
    r"^\s*(-i\s|--index-url|--extra-index-url|--trusted-host|-f\s|--find-links|-e\s|--editable)"
    r"|^\s*\S*(git\+|hg\+|svn\+|https?://|file:)",
    re.M,
)


def _magic_ok(path: str, head: bytes) -> bool:
    """True only for an inert extension whose content starts with that format's signature."""
    low = path.lower()
    if not low.endswith(_INERT_EXT) or not head:
        return False
    if low.endswith(".webp"):
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    for exts, magics in _MAGIC_OF.items():
        if low.endswith(exts):
            return head.startswith(magics)
    return False  # inert by name but no signature we can verify: not proven


def _sibling_file(c: _Ctx, ref: str, limit: int | None = None) -> bytes | None:
    """module/path resolved in an installed sibling addon (directory audits only), never
    escaping that addon; None when unavailable, oversize or unsafe."""
    parts = ref.replace("\\", "/").split("/")
    if len(parts) < 2 or any(p in ("", ".", "..") for p in parts) or not re.fullmatch(r"[a-z][a-z0-9_]*", parts[0]):
        return None
    for d in getattr(c, "addons_dirs", []) or []:
        try:
            root = (d / parts[0]).resolve()
            f = (d / ref).resolve()
            if root not in f.parents or not f.is_file() or f.is_symlink() or f.stat().st_size > MAX_FILE:
                continue
            with open(f, "rb") as fh:
                return fh.read(limit) if limit else fh.read()
        except OSError:
            continue
    return None


def _inert_ref_ok(c: _Ctx, rel: str, ref: str) -> bool:
    """file= target is an inert asset of this module (skipped from c.files but sniffed in
    c.heads) or of an installed sibling addon, and its bytes match its extension."""
    heads = getattr(c, "heads", {}) or {}
    if rel in heads:
        return _magic_ok(rel, heads[rel])
    if rel != ref or "/" not in ref:
        return False
    return _magic_ok(ref, _sibling_file(c, ref, HEAD_BYTES) or b"")


def _audit_inert(c: _Ctx, path: str, head: bytes) -> None:
    """Inert files are never executed, but only when they are what their name says: sniff
    the first HEAD_BYTES. A mismatch, an embedded document or active content is reported."""
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    if not head:
        return
    egg = [seg for seg in low.split("/")[:-1] if seg.endswith((".egg-info", ".dist-info"))]
    if egg and name in ("entry_points.txt", "requires.txt", "top_level.txt", "pkg-info", "record"):
        c.add(
            MEDIUM,
            "packaging-metadata",
            path,
            0,
            "Python packaging metadata shipped in the module (entry points install console"
            " scripts or plugins when the folder is pip-installed).",
            "Remove the .egg-info/.dist-info folder; Odoo modules are not pip packages.",
        )
    for exts, magics in _MAGIC_OF.items():
        if low.endswith(exts):
            ok = head.startswith(magics) or (low.endswith(".webp") and head[8:12] == b"WEBP")
            break
    else:
        ok = None
        if low.endswith(".webp"):
            ok = head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        elif low.endswith(".wav"):
            ok = head[:4] == b"RIFF" and head[8:12] == b"WAVE"
        elif low.endswith(_FTYP):
            ok = head[4:8] == b"ftyp"
    if ok is False:
        active = bool(_ACTIVE.search(head[:65536]))
        media = any(head.startswith(m) for ms in _MAGIC_OF.values() for m in ms if len(m) >= 3)
        media = media and not head.startswith((b"PK", b"%PDF", b"\xd0\xcf"))
        c.add(
            HIGH if active else INFO if media else MEDIUM,
            "content-mismatch",
            path,
            0,
            f"Content is not a {name.rsplit('.', 1)[-1]} file"
            + (" and holds markup/script a browser can sniff and run." if active else "."),
            "Ship the real file type, or rename it to what it is (then it is audited).",
        )
        return
    if ok and not low.endswith((".pdf", ".docx", ".xlsx", ".odt", ".ods", ".doc", ".xls")):
        if _ACTIVE.search(head):
            c.add(
                MEDIUM,
                "polyglot-content",
                path,
                0,
                "Media file also contains markup/script (polyglot): served with a sniffable type"
                " or re-used as a document, it runs.",
                "Re-export the file from a clean source.",
            )
        return
    if low.endswith(".pdf"):
        if re.search(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia)\b", head):
            c.add(
                MEDIUM,
                "pdf-active-content",
                path,
                0,
                "PDF with JavaScript, launch actions or embedded files.",
                "Ship a flattened PDF without actions or attachments.",
            )
        return
    if low.endswith((".docx", ".xlsx", ".odt", ".ods", ".doc", ".xls")):
        macro = b"vbaProject" in head or b"_\x00V\x00B\x00A\x00_\x00P" in head
        macro = macro or b"Basic/" in head or b"macros/" in head.lower()
        if head.startswith(b"PK") and len(head) < HEAD_BYTES:
            try:
                with zipfile.ZipFile(io.BytesIO(head)) as z:
                    names = z.namelist()
                macro = macro or any(
                    "vbaproject" in n.lower() or n.startswith("Basic/") for n in names
                )
            except (zipfile.BadZipFile, ValueError, OSError):
                c.add(
                    MEDIUM,
                    "content-mismatch",
                    path,
                    0,
                    "Office document that is not a readable archive: unaudited.",
                    "Ship a valid document or remove it.",
                )
                return
        if macro:
            c.add(
                HIGH,
                "office-macro",
                path,
                0,
                "Office document with macros (VBA/Basic): runs code when opened.",
                "Remove the macros or the document.",
            )
        return
    # text inert files: active content, dependency sources, external import maps
    text = head.decode("utf-8", "replace")
    if low.endswith((".txt", ".json", ".md", ".map")) and re.match(
        r"\s*<\s*(script|html|svg|!doctype)", text, re.I
    ):
        c.add(
            MEDIUM,
            "content-mismatch",
            path,
            0,
            "Text/data file that is really an HTML/SVG document (sniffable as a page).",
            "Rename it to .html/.svg (then it is audited) or remove it.",
        )
    if low.endswith(".txt") and ("requirements" in name or "constraints" in name):
        m = _PIP_SRC.search(text)
        if m:
            c.add(
                MEDIUM,
                "dependency-source",
                path,
                text[: m.start()].count("\n") + 1,
                "Requirements point pip at a custom index, VCS or URL source.",
                "Depend on released PyPI packages by name and pinned version only.",
            )
    if low.endswith(".rst"):
        raw = re.search(r"^\s*\.\.\s+raw::\s*html", text, re.M | re.I)
        if raw and _ACTIVE.search(text.encode()):
            c.add(
                MEDIUM,
                "doc-active-content",
                path,
                text[: raw.start()].count("\n") + 1,
                "reStructuredText raw HTML with script/handlers: module descriptions are"
                " rendered from it.",
                "Remove the raw HTML block.",
            )
        elif re.search(r"javascript:", text, re.I):
            c.add(
                MEDIUM,
                "doc-active-content",
                path,
                0,
                "javascript: link in a rendered document.",
                "Use http(s) links only.",
            )
    if low.endswith(".md") and _ACTIVE.search(text.encode()):
        m = _ACTIVE.search(text.encode())
        c.add(
            MEDIUM,  # m-md: README.md raw HTML is rendered by Apps/GitHub (same rule as .rst)
            "doc-active-content",
            path,
            text.encode()[: m.start()].count(b"\n") + 1,
            "Markdown with raw HTML/script or javascript: links (rendered by Apps/GitHub).",
            "Remove raw HTML and javascript: links.",
        )
    if low.endswith(".json") and low.startswith("static/"):
        # probe j-json-module: a JSON file under static/ is importable by asset JS
        # (import x from "./d.json"): its strings are data the page uses
        um = re.search(r'"\s*((?:https?:)?//[^"\s]+)"', text)
        if um:
            c.add(
                MEDIUM,
                "json-module-url",
                path,
                text[: um.start()].count("\n") + 1,
                f"JSON asset holds an external URL ({um.group(1)[:60]}) the client code may load.",
                "Ship the resource in the module; keep JSON assets free of external URLs.",
            )
        sm = re.search(r"<\s*(?:script|iframe|object|embed)\b|\bon[a-z]+\s*=|javascript\s*:", text, re.I)
        if sm:
            c.add(
                MEDIUM,
                "json-module-script",
                path,
                text[: sm.start()].count("\n") + 1,
                "JSON asset holds markup/script: rendered by client code it runs in the page.",
                "Keep JSON assets to plain data.",
            )
    if low.endswith(".json"):
        _structured_data(
            c, path, head.decode("utf-8", "replace"), truncated=len(head) >= HEAD_BYTES
        )
        for m in re.finditer(
            r'"(imports|scopes|import|src|url|script|scripts)"\s*:\s*[\[{]?\s*"((?:https?:)?//[^"]+)"',
            text,
        ):
            c.add(
                MEDIUM,
                "json-external-url",
                path,
                text[: m.start()].count("\n") + 1,
                f"JSON {m.group(1)} entry points at an external host ({m.group(2)[:60]}).",
                "Ship the resource in the module; never load code from other hosts.",
            )
            break
        else:
            # L1: an import map (imports/scopes objects) maps module names to URLs: any
            # external URL value inside it loads code from another host
            if re.search(r'"(imports|scopes)"\s*:\s*\{', text) or "importmap" in low:
                m = re.search(r':\s*"((?:https?:)?//[^"]+)"', text)
                if m:
                    c.add(
                        MEDIUM,
                        "json-external-url",
                        path,
                        text[: m.start()].count("\n") + 1,
                        f"Import map entry points at an external host ({m.group(1)[:60]}).",
                        "Ship the resource in the module; never load code from other hosts.",
                    )


def _structured_data(c: _Ctx, path: str, text: str, truncated: bool = False) -> None:
    """JSON/YAML data: every dict that names a sensitive model (or carries stored web
    content / alias defaults) goes through the same deny-by-default record policy."""
    low = path.lower()
    try:
        if low.endswith(".json"):
            import json

            obj = json.loads(text)
        else:
            import yaml

            obj = list(yaml.safe_load_all(text))
    except Exception as e:  # noqa: BLE001 - any parse failure is graded below
        hint = re.search(
            r"\b(?:" + "|".join(re.escape(m) for m in sorted(policy.SENSITIVE_MODELS)) + r")\b"
            r"|custom_code_|alias_defaults",
            text,
        )
        if hint or truncated:
            c.add(
                HIGH,
                "data-unaudited",
                path,
                0,
                f"Structured data names a sensitive model or field but cannot be parsed"
                f" ({type(e).__name__}): unaudited.",
                "Ship valid JSON/YAML, or move the records to XML/CSV data.",
            )
        return
    for model, vals in policy.records_from_structured(obj):
        if model == "__too_deep__":
            c.add(HIGH, "data-unaudited", path, 0, "Structured data nests too deep to audit.",
                  "Flatten the data.")  # fmt: skip
            return
        _record_checks(c, path, 0, model, vals, rid=vals.get("id", ""))


def _audit_other_file(c: _Ctx, path: str, body: bytes, manifest: dict[str, Any] | None) -> None:
    """Every file that is neither audited code nor on the inert allow-list: graded, never
    silently skipped (fail closed)."""
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    if low.endswith((".yml", ".yaml")):
        _structured_data(c, path, body.decode("utf-8", "replace"))
    if low.endswith(".svgz"):
        import gzip

        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as g:
                svg = g.read(MAX_FILE + 1)
            if len(svg) > MAX_FILE:
                raise ValueError("expands over the size limit")
        except (OSError, EOFError, ValueError) as e:
            c.add(
                HIGH,
                "web-unaudited",
                path,
                0,
                f"Compressed SVG cannot be expanded, unaudited ({str(e)[:80]}).",
                "Ship a plain .svg.",
            )
            return
        _audit_markup_file(c, path, svg, "svg")
        return
    if low.endswith(_BINARY_CODE):
        if "/__pycache__/" in f"/{low}" and low.endswith((".pyc", ".pyo")):
            c.pycache.append(path)
            return
        c.add(
            HIGH,
            "binary-code",
            path,
            0,
            "Compiled/binary code (bytecode, native library, WebAssembly, package): it runs"
            " without its source ever being audited.",
            "Remove it; ship source only.",
        )
        return
    if low.endswith(".sql"):
        text = body.decode("utf-8", "replace")
        loaded = path in _manifest_files(manifest)
        if _SQL_DANGER.search(text) or (_SERVER_DML.search(text) and _CORE_TABLES.search(text)):
            sev = HIGH
        else:
            sev = MEDIUM if loaded else LOW
        c.add(
            sev,
            "sql-data-file",
            path,
            1,
            "SQL file"
            + (" run at install/update" if loaded else "")
            + (": changes security/core tables or the server." if sev == HIGH else "."),
            "Use XML/CSV data or the ORM; raw SQL bypasses access rights.",
        )
        return
    if low.endswith(_KEY_EXT) or name == "enc_key":
        c.add(
            MEDIUM,
            "key-material",
            path,
            0,
            "Key or certificate file shipped in the module.",
            "Never ship private keys; load secrets from configuration.",
        )
        return
    if low.endswith((".b64", ".base64")):
        # base64-wrapped binaries (stock web ships roboto.b64 for PDF reports): decode strictly
        # and accept only inert font/image payloads; anything else stays unaudited
        import base64 as _b64
        import binascii as _ba

        try:
            raw = _b64.b64decode(re.sub(rb"\s+", b"", body), validate=True)
        except (_ba.Error, ValueError):
            raw = b""
        if raw[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"wOFF", b"wOF2", b"ttcf") or raw.startswith(
            (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")
        ) or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"):
            return
    if "." not in name and not body.startswith(b"#!") and b"\x00" not in body[:4096]:
        return  # extensionless text (LICENSE, COPYRIGHT): never imported or served as script
    kind = name.rsplit(".", 1)[-1] if "." in name else "no extension"
    c.add(
        HIGH,
        "script-file" if low.endswith(_SCRIPT_EXT) or body.startswith(b"#!") else "file-unaudited",
        path,
        0,
        f"Unknown/unaudited file type ({kind}): nothing about it was checked.",
        "Remove it, or use a supported type (py, xml, csv, js, css/scss, svg, html, po, inert"
        " media).",
    )


def _bytecode_summary(c: _Ctx) -> None:
    if c.pycache:
        c.add(
            HIGH,
            "binary-code",
            sorted(c.pycache)[0],
            0,
            f"{len(c.pycache)} Python bytecode cache file(s) in __pycache__: a forged .pyc runs"
            " instead of the audited .py.",
            "Delete every __pycache__ directory before packaging or installing.",
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
    try:
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as e:
        c.add(
            HIGH,
            "parse-error",
            path,
            0,
            f"Data CSV does not parse ({type(e).__name__}).",
            "Fix the CSV.",
        )
        return
    for i, r in enumerate(rows):
        r = {k: v for k, v in r.items() if isinstance(k, str) and isinstance(v, str)}
        if model == "ir.model.access":
            ref = (r.get("model_id:id") or r.get("model_id/id") or "").split(".")[-1]
            if ref:
                c.access.setdefault(path, set()).add(ref)
        _record_checks(c, path, i + 2, model, r, csv_row=True)
        if model == "ir.config_parameter" and (key := (r.get("key") or "").strip()):
            hi = bool(_CFG_SECURITY.search(key))
            c.add(
                HIGH if hi else MEDIUM,
                "config-parameter-record",
                path,
                i + 2,
                f"Data row sets system parameter {key!r}"
                + (" (security / auth / routing setting)." if hi else "."),
                "Do not ship system parameters in module data; document the setting instead.",
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
        tree = ast.parse(body)
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
            for b, v in assets.items():
                if "test" in str(b):
                    continue  # web.assets_tests / assets_unit_tests: loaded only in test mode
                for x in v if isinstance(v, list) else []:
                    vals = x if isinstance(x, (list, tuple)) else [x]
                    listed |= {y.removeprefix(f"{module}/") for y in vals if isinstance(y, str)}
    out = {
        f
        for f in files
        if _is_test(f)
        and any(
            g == f
            or ("*" in g and (fnmatch.fnmatch(f, g) or fnmatch.fnmatch(f, g.replace("**/", ""))))
            for g in listed
        )
    }
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


MAX_FLOW_ROUNDS = 64

# Findings that mean "this was not (or cannot be) checked". A base copy with the same
# finding proves nothing about the new bytes, so approval gates never baseline them.
UNBASELINABLE = frozenset(
    {
        "file-unaudited",
        "xml-unaudited",
        "web-unaudited",
        "parse-error",
        "binary-code",
        "script-file",
        "sql-data-file",
        "key-material",
        "flow-incomplete",
        "expression-unparsed",
        "web-encoding",
    }
)


def unbaselinable(code: str) -> bool:
    """Never baseline a not-checked finding: the fixed set, any *-unaudited, *-incomplete."""
    return code in UNBASELINABLE or code.endswith(("-unaudited", "-incomplete"))


class FlowIncomplete(RuntimeError):
    """Interprocedural summaries did not reach a fixpoint: the audit fails closed."""


def _module_flow(
    files: dict[str, bytes],
) -> tuple[frozenset[str], dict[str, flow.Summary]]:
    """Cross-file taint summaries: functions returning (a transform of) a parameter, and
    functions passing a parameter into a sink, over every Python file of the module."""
    trees = []
    for p, b in sorted(files.items()):
        if p.endswith(".py"):
            try:
                t = ast.parse(b)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                continue
            trees.append((t, flow.Resolver(t, _ALIAS_ROOTS)))
    pt: frozenset[str] = frozenset()
    for _ in range(MAX_FLOW_ROUNDS):
        new = pt
        for t, r in trees:
            new = new | flow.passthrough_functions(t, r, new)
        if new == pt:
            break
        pt = new
    else:  # M4: passthrough summaries must converge too, or the audit fails closed
        raise FlowIncomplete("passthrough summaries did not converge")
    # sink summaries to a fixpoint over the module call graph: a helper calling a helper
    # that reaches a sink is itself a sink for the parameter that flows (any depth, any file)
    defs = [(fn, r) for t, r in trees for fn in flow.function_defs(t)]
    calls = {
        id(fn): {flow.call_name(n, {}) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        for fn, _ in defs
    }
    sinks: dict[str, flow.Summary] = {}
    dirty: set[str] | None = None  # None: first round, every function
    for _ in range(MAX_FLOW_ROUNDS):
        new: dict[str, flow.Summary] = {}
        for fn, r in defs:
            if dirty is not None and not (calls[id(fn)] & dirty):
                if fn.name in sinks:
                    new[fn.name] = flow.merge_summary(new.get(fn.name, {}), sinks[fn.name])
                continue
            sm = flow.function_summary(fn, r, pt, sinks)
            if sm:
                new[fn.name] = flow.merge_summary(new.get(fn.name, {}), sm)
        # monotone: never lose an earlier summary
        for k, v in sinks.items():
            new[k] = flow.merge_summary(new.get(k, {}), v)
        dirty = {k for k in new if new[k] != sinks.get(k)}
        sinks = new
        if not dirty:
            return pt, sinks
    raise FlowIncomplete("taint summaries did not converge")


def _module_index(files: dict[str, bytes]) -> tuple[frozenset[str], dict[str, str]]:
    """Module-wide facts for the flow checks: user-text field names (Char/Text/Html) and
    helpers that reach the database."""
    trees: dict[str, ast.AST] = {}
    for p, b in files.items():
        if p.endswith(".py"):
            try:
                trees[p] = ast.parse(b)
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
    big: list[str] = []
    try:
        heads: dict[str, bytes] = {}
        files, top = load_tree(src, skip_assets=True, oversized=big, heads=heads)
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
    c.heads = heads  # inert assets skipped from c.files, by their first HEAD_BYTES
    if isinstance(src, Path):
        c.addons_dirs = [src.resolve().parent]
        # Odoo source layout: <root>/addons beside the core addons path <root>/odoo/addons (base, web...)
        core = src.resolve().parent.parent / "odoo" / "addons"
        if (core / "base" / "__manifest__.py").is_file() and core.resolve() != c.addons_dirs[0]:
            c.addons_dirs.append(core.resolve())
    for rel in big:
        c.add(
            HIGH,
            "file-unaudited",
            rel,
            0,
            f"Cannot audit, unaudited: file is over {MAX_FILE // 1_000_000} MB (the rest of the"
            " module was audited).",
            "Split or remove the file (generated bundles, data dumps), then audit again.",
        )
    try:
        manifest = _audit_manifest(c)
        c.prod_tests = _prod_tests(files, name, manifest)
        _MODULE_UNIQUE.clear()
        _MODULE_UNIQUE.update(_module_unique(files))
        c.props_domain = _props_domain(files)
        c.text_fields, c.db_helpers = _module_index(files)
        c.flow_pt, c.flow_sinks = _module_flow(files)
        for rel in sorted(heads):
            _audit_inert(c, rel, heads[rel])
        for path in sorted(files):
            body = files[path]
            try:
                if path.endswith((".py", ".pyw")):
                    _audit_py(c, path, body)
                elif path.endswith(".xml"):
                    _audit_xml(c, path, body)
                elif path.endswith(".csv"):
                    _audit_csv(c, path, body)
                elif _is_po(path):
                    _audit_po(c, path, body)
                elif web.web_kind(path) in ("svg", "html"):
                    _audit_markup_file(c, path, body, web.web_kind(path))
                elif web.web_kind(path):
                    kind = web.web_kind(path)
                    text, note = web.decode(body, kind)
                    if note:
                        c.add(
                            MEDIUM,
                            "web-encoding",
                            path,
                            1,
                            f"File is {note}; Odoo's asset bundles decode UTF-8.",
                            "Save the file as UTF-8.",
                        )
                    c.web.append((path, path, 1, kind, text))
                else:
                    _audit_other_file(c, path, body, manifest)
            except (RecursionError, MemoryError) as e:
                c.add(
                    HIGH,
                    "parse-error",
                    path,
                    0,
                    f"File too deeply nested to audit ({type(e).__name__}).",
                    "Simplify the file; it is not a normal module source file.",
                )
        _bytecode_summary(c)
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
