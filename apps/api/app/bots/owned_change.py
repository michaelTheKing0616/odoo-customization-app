"""BOT-OWNED-CODE-CHANGE: reviewable change sets for modules Ingenium owns.

Pure and read-only: input is a source tree plus structured edits; output is a ``ChangeSet``
(unified diff, inverse diff, base/after hashes, pre/post ``code_audit`` counts). Nothing is
written here: the approval/guard spine applies the set (wiring is BOT-SPINE-WIRE). Fails
closed on foreign modules, paths outside the module, escapes, drifted bases, new high/medium
findings, or oversize input. Edit content is used verbatim; request text never enters code.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.bots import code_audit as ca

KINDS = ("replace_file", "add_file", "delete_file", "replace_symbol", "replace_xmlid")
MAX_EDITS = 50
MAX_CONTENT = 512 * 1024
MAX_CHANGED = 2 * 1024 * 1024
TEXT_EXT = (".py", ".xml", ".csv", ".js", ".scss", ".css", ".txt", ".rst", ".md", ".po", ".pot")
_BLOCK = (ca.HIGH, ca.MEDIUM)
_NO_EOL = "\\ No newline at end of file"
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
_SYM = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}(\.[A-Za-z_][A-Za-z0-9_]{0,127})?")


class ChangeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Edit:
    path: str
    kind: str
    content: str = ""
    target: str = ""


@dataclass(frozen=True)
class ChangeRequest:
    module: str
    edits: tuple[Edit, ...]
    reason: str = ""  # metadata only; never written into any file


@dataclass
class ChangeSet:
    module: str
    version: int
    reason: str
    base: dict[str, str | None]
    after: dict[str, str | None]
    patches: dict[str, str]
    inverse: dict[str, str]
    pre_counts: dict[str, int]
    post_counts: dict[str, int]
    new_findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def diff(self) -> str:
        return "".join(self.patches[p] for p in sorted(self.patches))

    @property
    def inverse_diff(self) -> str:
        return "".join(self.inverse[p] for p in sorted(self.inverse))

    @property
    def id(self) -> str:
        body = {
            "module": self.module,
            "version": self.version,
            "base": self.base,
            "after": self.after,
            "patches": self.patches,
            "inverse": self.inverse,
            "reason": self.reason,
            "pre_counts": self.pre_counts,
            "post_counts": self.post_counts,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def approval_plan(self) -> dict[str, Any]:
        """Facts for the approval spine. Code changes are always top tier; never auto-run."""
        return {
            "kind": "owned_code_change",
            "change_set_id": self.id,
            "module": self.module,
            "version": self.version,
            "files": sorted(self.after),
            "tier": "L3",
            "reason": self.reason,
            "pre_counts": self.pre_counts,
            "post_counts": self.post_counts,
        }


def sha(b: bytes | None) -> str | None:
    return None if b is None else hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- unified diff (byte exact)


def _text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ChangeError("encoding", "file is not UTF-8") from e


def _split(s: str) -> list[str]:
    """Split after '\n' only; '\r', form feed and U+2028 stay inside their line."""
    return [x for x in re.split(r"(?<=\n)", s) if x]


def _lines(b: bytes) -> list[str]:
    return _split(_text(b))


def _emit(prefix: str, line: str) -> str:
    return prefix + line if line.endswith("\n") else f"{prefix}{line}\n{_NO_EOL}\n"


def make_patch(path: str, old: bytes | None, new: bytes | None) -> str:
    """One whole-file hunk: simple, exact, and self-verifying."""
    a, b = _lines(old or b""), _lines(new or b"")
    src = "/dev/null" if old is None else f"a/{path}"
    dst = "/dev/null" if new is None else f"b/{path}"
    out = [
        f"--- {src}\n",
        f"+++ {dst}\n",
        f"@@ -{1 if a else 0},{len(a)} +{1 if b else 0},{len(b)} @@\n",
    ]
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out += [_emit(" ", x) for x in a[i1:i2]]
        else:
            out += [_emit("-", x) for x in a[i1:i2]]
            out += [_emit("+", x) for x in b[j1:j2]]
    return "".join(out)


def apply_patch(old: bytes | None, patch: str) -> bytes | None:
    rows = _split(patch)
    if len(rows) < 3 or not rows[0].startswith("--- ") or not rows[2].startswith("@@ "):
        raise ChangeError("patch-invalid", "malformed patch")
    a, b = [], []
    body = rows[3:]
    for i, r in enumerate(body):
        if r.rstrip("\n") == _NO_EOL:
            continue
        tag, text = r[0], r[1:]
        if i + 1 < len(body) and body[i + 1].rstrip("\n") == _NO_EOL:
            text = text[:-1]
        if tag in " -":
            a.append(text)
        if tag in " +":
            b.append(text)
        if tag not in " -+":
            raise ChangeError("patch-invalid", "bad hunk line")
    if "".join(a).encode() != (old or b""):
        raise ChangeError("stale-base", "patch does not match current content")
    if rows[1].startswith("+++ /dev/null"):
        return None
    return "".join(b).encode()


# ---------------------------------------------------------------- edits


def _py_span(src: str, target: str) -> tuple[int, int]:
    tree = ast.parse(src)
    parts = target.split(".")
    nodes: list[ast.AST] = list(tree.body)
    hit: list[ast.AST] = []
    for depth, name in enumerate(parts):
        hit = [
            n
            for n in nodes
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.name == name
        ]
        if len(hit) != 1:
            raise ChangeError("target-ambiguous" if hit else "target-missing", target)
        if depth < len(parts) - 1:
            nodes = list(getattr(hit[0], "body", []))
    n = hit[0]
    start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
    return start, int(n.end_lineno or n.lineno)


def _xml_span(src: str, target: str) -> tuple[int, int]:
    pat = re.compile(
        r"<(record|template|menuitem|act_window|report)\b[^>]*?\bid=(['\"])"
        + re.escape(target)
        + r"\2"
    )
    m = list(pat.finditer(src))
    if len(m) != 1:
        raise ChangeError("target-ambiguous" if m else "target-missing", target)
    tag, s = m[0].group(1), m[0].start()
    gt = src.index(">", m[0].end())
    if src[gt - 1] == "/":
        return s, gt + 1
    depth, pos = 1, gt + 1
    tok = re.compile(rf"<(/?){tag}\b[^>]*?(/?)>")
    while depth:
        t = tok.search(src, pos)
        if not t:
            raise ChangeError("target-missing", f"unclosed <{tag}>")
        if t.group(1):
            depth -= 1
        elif not t.group(2):
            depth += 1
        pos = t.end()
    return s, pos


def _check_syntax(path: str, body: bytes) -> None:
    try:
        if path.endswith(".py"):
            ast.parse(body)
        elif path.endswith(".xml"):
            ca._parse_xml(body)
    except Exception as e:  # noqa: BLE001 - fail closed
        raise ChangeError("syntax-invalid", f"{path} does not parse ({type(e).__name__})") from e


def _apply_edit(cur: bytes | None, e: Edit) -> bytes | None:
    new = e.content.encode("utf-8")
    if e.kind == "add_file":
        if cur is not None:
            raise ChangeError("exists", e.path)
        return new
    if cur is None:
        raise ChangeError("missing", e.path)
    if e.kind == "replace_file":
        return new
    if e.kind == "delete_file":
        if e.path == "__manifest__.py":
            raise ChangeError("protected", "manifest cannot be deleted")
        return None
    src = _text(cur)
    if e.kind == "replace_symbol":
        if not e.path.endswith(".py") or not _SYM.fullmatch(e.target):
            raise ChangeError("target-invalid", e.target)
        if re.search(r"\r(?!\n)", src):
            raise ChangeError("encoding", "bare carriage return; line numbers would be ambiguous")
        s, end = _py_span(src, e.target)
        lines = _split(src)
        repl = e.content if e.content.endswith("\n") else e.content + "\n"
        return "".join(lines[: s - 1] + [repl] + lines[end:]).encode()
    if not e.path.endswith(".xml") or not _ID.fullmatch(e.target):
        raise ChangeError("target-invalid", e.target)
    root = ca._parse_xml(new)
    if root.get("id") != e.target:
        raise ChangeError("target-invalid", "replacement must keep the same id")
    s, end = _xml_span(src, e.target)
    return (src[:s] + e.content.strip() + src[end:]).encode()


# ---------------------------------------------------------------- build / apply


def _zip(module: str, files: Mapping[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in sorted(files):
            z.writestr(f"{module}/{p}", files[p])
    return buf.getvalue()


def _key(f: ca.Finding) -> tuple[str, str, str]:
    return (f.code, f.file, f.message)


def _validate(req: ChangeRequest, files: Mapping[str, bytes]) -> None:
    if not isinstance(req.edits, tuple) or not 0 < len(req.edits) <= MAX_EDITS:
        raise ChangeError("bounds", f"1..{MAX_EDITS} edits required")
    nested = {p.rsplit("/", 1)[0] + "/" for p in files if p.endswith("/__manifest__.py")}
    seen: set[tuple[str, str]] = set()
    for e in req.edits:
        if not isinstance(e, Edit) or e.kind not in KINDS:
            raise ChangeError("kind-invalid", str(getattr(e, "kind", e)))
        if not isinstance(e.content, str) or len(e.content.encode("utf-8")) > MAX_CONTENT:
            raise ChangeError("bounds", "content too large or not text")
        if "\x00" in e.content:
            raise ChangeError("content-invalid", "NUL byte")
        try:
            rel = ca._safe_rel(e.path)
        except ca.SourceError as x:
            raise ChangeError("path-escape", str(x)) from x
        if rel != e.path or e.path.startswith(".") or "/." in e.path:
            raise ChangeError("path-escape", e.path)
        if any(e.path.startswith(n) for n in nested):
            raise ChangeError("outside-module", f"{e.path} belongs to a nested module")
        if not e.path.endswith(TEXT_EXT) and e.path != "__manifest__.py":
            raise ChangeError("path-invalid", "only text source files can change")
        k = (e.path, e.target or e.kind)
        if k in seen:
            raise ChangeError("duplicate", e.path)
        seen.add(k)


def build_change_set(
    src: bytes | Path,
    req: ChangeRequest,
    *,
    version: int,
    owned_names: Iterable[str],
) -> ChangeSet:
    """Return a verified ChangeSet or raise ChangeError. Never writes; never executes."""
    owned = set(owned_names) if isinstance(owned_names, (list, tuple, set, frozenset)) else set()
    if not isinstance(req, ChangeRequest) or req.module not in owned:
        raise ChangeError("foreign", "module is not in the owned registry; audit only")
    try:
        files, top = ca.load_tree(src)
    except ca.SourceError as e:
        raise ChangeError("source-unsafe", str(e)) from e
    top = top or (src.name if isinstance(src, Path) else "")
    if top != req.module:
        raise ChangeError("outside-module", "source tree is not the named module")
    _validate(req, files)
    pre = ca.audit(_zip(req.module, files), version=version, owned_names=owned)
    if not pre.ok:
        raise ChangeError("audit-failed", pre.error or "pre audit failed")
    work: dict[str, bytes | None] = dict(files)
    for e in req.edits:
        try:
            work[e.path] = _apply_edit(work.get(e.path), e)
        except UnicodeDecodeError as x:
            raise ChangeError("encoding", f"{e.path} is not UTF-8") from x
        except SyntaxError as x:
            raise ChangeError("syntax-invalid", f"{e.path} unreadable") from x
    touched = sorted({e.path for e in req.edits})
    changed = [p for p in touched if work.get(p) != files.get(p)]
    if not changed:
        raise ChangeError("no-op", "edits change nothing")
    if sum(len(work[p] or b"") for p in changed) > MAX_CHANGED:
        raise ChangeError("bounds", "change set too large")
    for p in changed:
        if work[p] is not None:
            _check_syntax(p, work[p] or b"")
    after_files = {p: b for p, b in work.items() if b is not None}
    post = ca.audit(_zip(req.module, after_files), version=version, owned_names=owned)
    if not post.ok:
        raise ChangeError("audit-failed", post.error or "post audit failed")
    before = Counter(
        _key(f) for f in pre.findings if f.severity in _BLOCK and f.code not in ca.UNBASELINABLE
    )
    new = []
    for f in post.findings:
        if f.severity in _BLOCK:
            if before[_key(f)]:
                before[_key(f)] -= 1
            else:
                new.append(f.__dict__.copy())
    if new:
        raise ChangeError("audit-regression", f"{len(new)} new high/medium finding(s)")
    patches, inverse = {}, {}
    for p in changed:
        old, nb = files.get(p), work[p]
        patches[p], inverse[p] = make_patch(p, old, nb), make_patch(p, nb, old)
        if apply_patch(old, patches[p]) != nb or apply_patch(nb, inverse[p]) != old:
            raise ChangeError("roundtrip-failed", p)
    return ChangeSet(
        req.module,
        version,
        req.reason[:500],
        {p: sha(files.get(p)) for p in changed},
        {p: sha(work[p]) for p in changed},
        patches,
        inverse,
        pre.counts,
        post.counts,
    )


def apply_change_set(
    files: Mapping[str, bytes], cs: ChangeSet, *, approved_id: str, reverse: bool = False
) -> dict[str, bytes]:
    """Pure apply for the spine: base -> after; already-after is a no-op; anything else refused.

    The id is recomputed from content here, so a set edited after approval never applies."""
    if not isinstance(cs, ChangeSet) or not isinstance(approved_id, str) or not approved_id:
        raise ChangeError("not-approved", "an approved change set id is required")
    if cs.id != approved_id:
        raise ChangeError("not-approved", "change set differs from the approved one")
    keys = set(cs.base)
    if not (keys == set(cs.after) == set(cs.patches) == set(cs.inverse)) or not keys:
        raise ChangeError("patch-invalid", "patch files differ from base/after files")
    want_from, want_to = (cs.after, cs.base) if reverse else (cs.base, cs.after)
    patches = cs.inverse if reverse else cs.patches
    cur = {p: sha(files.get(p)) for p in want_from}
    if cur == want_to:
        return dict(files)
    if cur != want_from:
        raise ChangeError("stale-base", "source drifted since the change set was built")
    out = dict(files)
    for p in sorted(patches):
        nb = apply_patch(files.get(p), patches[p])
        if sha(nb) != want_to[p]:
            raise ChangeError("roundtrip-failed", p)
        if nb is None:
            out.pop(p, None)
        else:
            out[p] = nb
    return out
