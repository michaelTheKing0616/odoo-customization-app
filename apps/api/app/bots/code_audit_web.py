"""BOT-CODE-AUDIT web layer: JavaScript (OWL components, legacy widgets) and stylesheets
(CSS, SCSS, LESS) parsed for real by a pinned Node helper (acorn, postcss; see code_audit_js/).

Fail closed: when Node, the helper or its locked dependencies are missing or do not match
their pins, or a file does not parse, every affected file gets a HIGH "cannot parse,
unaudited" finding; nothing passes silently. The helper reads one JSON document on stdin and
writes one on stdout; it runs under Node's permission model (read access to its own folder
only, no child processes, no workers, no code generation from strings) when Node supports it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).with_name("code_audit_js")
HELPER = HELPER_DIR / "audit.mjs"
HELPER_ID = "ingenium-code-audit-js/1"
# sha256 pins: the helper source, its lockfile (exact versions + sha512 integrity of each
# tarball) and the installed dependency tree (npm ci --ignore-scripts from that lockfile)
HELPER_SHA256 = "c5727ccca7c996bfd0661f5b1efd084c07194914d76d13fc60a44fbdcb888a8d"
LOCK_SHA256 = "8ab8dad809a88374e66decbf38124363a682a38ea5ab68c48b3e4d2b4212e839"
MODULES_SHA256 = "4dc4b9addaa413cf20481526c85a3cf1c503e1bbae2d547ab0ab0fc3e2fe170a"
NODE_MIN_MAJOR = 20
TIMEOUT_S = 120
WEB_KINDS = {".js": "js", ".mjs": "js", ".cjs": "js", ".css": "css", ".scss": "scss"}
WEB_KINDS[".less"] = "less"
UNPARSEABLE = (".sass", ".ts", ".tsx", ".jsx", ".coffee", ".styl")  # no parser: unaudited


def web_kind(path: str) -> str | None:
    low = path.lower()
    for ext, kind in WEB_KINDS.items():
        if low.endswith(ext):
            return kind
    return "unparseable" if low.endswith(UNPARSEABLE) else None


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def modules_tree_sha(root: Path) -> str:
    """One hash over every installed dependency file (path and content), npm's own
    bookkeeping file excluded."""
    h = hashlib.sha256()
    nm = root / "node_modules"
    for p in sorted(x for x in nm.rglob("*") if x.is_file()):
        rel = p.relative_to(nm).as_posix()
        if rel == ".package-lock.json":
            continue
        h.update(rel.encode() + b"\0" + _sha(p).encode() + b"\n")
    return h.hexdigest()


def _node() -> str | None:
    cand = os.environ.get("INGENIUM_NODE") or shutil.which("node")
    if not cand:
        for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
            if Path(p).is_file():
                return p
    return cand


def _node_major(node: str) -> int:
    r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20)
    v = r.stdout.strip().lstrip("v").split(".")[0]
    return int(v) if r.returncode == 0 and v.isdigit() else 0


def helper_problem() -> str | None:
    """Why the helper cannot be trusted to run now, or None."""
    node = _node()
    if not node:
        return "Node.js not found"
    try:
        major = _node_major(node)
    except (OSError, subprocess.SubprocessError):
        return "Node.js not runnable"
    if major < NODE_MIN_MAJOR:
        return f"Node.js {major} is older than {NODE_MIN_MAJOR}"
    try:
        if _sha(HELPER) != HELPER_SHA256:
            return "parser helper does not match its pin"
        if _sha(HELPER_DIR / "package-lock.json") != LOCK_SHA256:
            return "parser lockfile does not match its pin"
        if not (HELPER_DIR / "node_modules").is_dir():
            return "parser dependencies not installed (npm ci --ignore-scripts)"
        if modules_tree_sha(HELPER_DIR) != MODULES_SHA256:
            return "installed parser dependencies do not match the lockfile pin"
    except OSError as e:
        return f"parser helper unreadable ({type(e).__name__})"
    return None


def _cmd(node: str) -> list[str]:
    base = [node, "--disallow-code-generation-from-strings"]
    if _node_major(node) >= 22:  # stable permission model
        base += ["--permission", f"--allow-fs-read={HELPER_DIR}"]
    return [*base, str(HELPER)]


def run(files: list[tuple[str, str, str]]) -> dict[str, dict[str, Any]] | str:
    """{path: {"ok", "findings" | "error", "line"}} for (path, kind, text) files, or the
    reason the whole batch could not be audited."""
    if not files:
        return {}
    why = helper_problem()
    if why:
        return why
    node = _node()
    assert node
    payload = json.dumps({"files": [{"path": p, "kind": k, "text": t} for p, k, t in files]})
    try:
        r = subprocess.run(
            _cmd(node),
            input=payload,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            cwd=HELPER_DIR,
            env={"PATH": os.environ.get("PATH", ""), "NODE_OPTIONS": ""},
        )
    except subprocess.TimeoutExpired:
        return "parser helper timed out"
    except OSError as e:
        return f"parser helper did not start ({type(e).__name__})"
    if r.returncode != 0:
        return "parser helper failed"
    try:
        doc = json.loads(r.stdout)
        res = {x["path"]: x for x in doc["results"]}
    except (ValueError, KeyError, TypeError):
        return "parser helper output unreadable"
    if doc.get("helper") != HELPER_ID or set(res) != {p for p, _, _ in files}:
        return "parser helper output incomplete"
    return res
