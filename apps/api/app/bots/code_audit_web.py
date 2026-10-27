"""BOT-CODE-AUDIT web layer: JavaScript (OWL components, legacy widgets) and stylesheets
(CSS, SCSS, LESS) parsed for real by a pinned Node helper (acorn, postcss; see code_audit_js/).

Fail closed: when Node, the helper or its locked dependencies are missing or do not match
their pins, or a file does not parse, every affected file gets a HIGH "cannot parse,
unaudited" finding; nothing passes silently. The helper reads one JSON document on stdin and
writes one on stdout; it runs under Node's permission model (read access to its own folder
only, no child processes, no workers, no code generation from strings) when Node supports it.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).with_name("code_audit_js")
HELPER = HELPER_DIR / "audit.mjs"
HELPER_ID = "ingenium-code-audit-js/1"
# sha256 pins: the helper source, its lockfile (exact versions + sha512 integrity of each
# tarball) and the installed dependency tree (npm ci --ignore-scripts from that lockfile)
HELPER_SHA256 = "b61bf4da58e9d3ec11e3ffb7fb8976d7dacbfec93a543e23b099faa75f6f746e"
LOCK_SHA256 = "8ab8dad809a88374e66decbf38124363a682a38ea5ab68c48b3e4d2b4212e839"
MODULES_SHA256 = "4dc4b9addaa413cf20481526c85a3cf1c503e1bbae2d547ab0ab0fc3e2fe170a"
# Node 22+: the stable permission model (fs read limited to the private helper copy, no child
# processes, workers or addons). Older Node has no such sandbox -> fail closed.
NODE_MIN_MAJOR = 22
# the Node binary itself is pinned per host: `python -m app.bots.code_audit_web --pin-node`
# records its real path and sha256 (and of the libnode it loads); unpinned -> fail closed
NODE_PIN = HELPER_DIR / "node.pin.json"
TIMEOUT_S = 60  # per batch; a batch that times out is retried file by file
BATCH_BYTES = 1_500_000
WORKERS = 4
WEB_KINDS = {".js": "js", ".mjs": "js", ".cjs": "js", ".css": "css", ".scss": "scss"}
WEB_KINDS[".less"] = "less"
# no parser here: unaudited. .sass is loaded by Odoo's asset bundles (HIGH); the others are
# never served by Odoo's bundler (type declarations, sources for a build step) -> INFO
UNPARSEABLE = (".sass", ".ts", ".tsx", ".jsx", ".coffee", ".styl")
# served from static/ as documents: scripts and handlers inside run in the module's origin
MARKUP_KINDS = {".svg": "svg", ".html": "html", ".htm": "html", ".xhtml": "html"}


def web_kind(path: str) -> str | None:
    low = path.lower()
    for ext, kind in MARKUP_KINDS.items():
        if low.endswith(ext):
            return kind
    for ext, kind in WEB_KINDS.items():
        if low.endswith(ext):
            return kind
    if low.endswith(".sass"):
        return "unparseable"
    if low.endswith(".d.ts"):
        return "inert"  # type declarations only: no runtime code exists in the file
    if low.endswith((".ts", ".tsx", ".jsx")):
        return "tryjs"  # audited when the source is plain JS; otherwise reported unaudited
    return "foreign" if low.endswith(UNPARSEABLE) else None


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


def _find_node() -> str | None:
    """Candidate binary for pinning only; auditing runs the pinned path, never PATH."""
    cand = os.environ.get("INGENIUM_NODE") or shutil.which("node")
    if not cand:
        for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
            if Path(p).is_file():
                return p
    return cand


def _node_libs(node: Path) -> list[Path]:
    """Shared libnode next to the binary (Homebrew/distro builds load it via rpath)."""
    lib = node.parent.parent / "lib"
    return sorted(p for p in lib.glob("libnode*") if p.is_file()) if lib.is_dir() else []


def _node_fingerprint(node: Path) -> str:
    h = hashlib.sha256(_sha(node).encode())
    for lib in _node_libs(node):
        h.update(lib.name.encode() + b"\0" + _sha(lib).encode())
    return h.hexdigest()


def pin_node(cand: str | None = None) -> dict[str, str]:
    """Operator step (like npm ci): pin this host's Node binary by real path and hash."""
    c = cand or _find_node()
    if not c:
        raise RuntimeError("Node.js not found")
    real = Path(c).resolve(strict=True)
    doc = {"path": str(real), "sha256": _node_fingerprint(real)}
    NODE_PIN.write_text(json.dumps(doc) + "\n")
    return doc


def _node() -> str | None:
    """The pinned Node binary, re-hashed now; None when unpinned or changed."""
    try:
        pin = json.loads(NODE_PIN.read_text())
        real = Path(pin["path"])
        if real.is_symlink() or not real.is_file():
            return None
        return str(real) if _node_fingerprint(real) == pin["sha256"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _node_major(node: str) -> int:
    r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20)
    v = r.stdout.strip().lstrip("v").split(".")[0]
    return int(v) if r.returncode == 0 and v.isdigit() else 0


def helper_problem() -> str | None:
    """Why the helper cannot be trusted to run now, or None."""
    node = _node()
    if not node:
        return "Node.js binary not pinned or changed since pinning (code_audit_web --pin-node)"
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


_SB_PROFILE = "(version 1)(allow default)(deny network*)(deny file-write*)"
_SB_PROFILE += '(allow file-write* (literal "/dev/null"))'
_UNSHARE_OK: bool | None = None


def _os_sandbox() -> list[str] | None:
    """No-network, no-file-write wrapper for the helper process, or None if unavailable."""
    global _UNSHARE_OK
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file():
        return ["/usr/bin/sandbox-exec", "-p", _SB_PROFILE]
    un = shutil.which("unshare")
    if sys.platform.startswith("linux") and un:
        if _UNSHARE_OK is None:
            try:
                _UNSHARE_OK = (
                    subprocess.run([un, "-rn", "true"], capture_output=True, timeout=10).returncode
                    == 0
                )
            except (OSError, subprocess.SubprocessError):
                _UNSHARE_OK = False
        if _UNSHARE_OK:
            return [un, "-rn"]
    return None


def _limits() -> None:  # runs in the child before exec
    import resource

    for lim, val in (
        (resource.RLIMIT_CPU, TIMEOUT_S + 5),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 256),
    ):
        try:
            resource.setrlimit(lim, (val, val))
        except (ValueError, OSError):
            pass


def _cmd(node: str, helper_dir: Path) -> list[str] | None:
    sb = _os_sandbox()
    if sb is None:
        return None
    return [
        *sb,
        node,
        "--disallow-code-generation-from-strings",
        "--permission",
        f"--allow-fs-read={helper_dir}",
        str(helper_dir / "audit.mjs"),
    ]


def _private_copy() -> tuple[Path, str | None]:
    """Copy the helper and its dependencies into a fresh 0700 directory and verify the copy:
    the files Node executes are exactly the hashed ones (no swap between check and run)."""
    d = Path(tempfile.mkdtemp(prefix="ingenium-audit-js-")).resolve()
    shutil.copy2(HELPER, d / "audit.mjs")
    shutil.copy2(HELPER_DIR / "package.json", d / "package.json")
    shutil.copy2(HELPER_DIR / "package-lock.json", d / "package-lock.json")
    shutil.copytree(HELPER_DIR / "node_modules", d / "node_modules", symlinks=False)
    if _sha(d / "audit.mjs") != HELPER_SHA256:
        return d, "parser helper does not match its pin"
    if _sha(d / "package-lock.json") != LOCK_SHA256 or modules_tree_sha(d) != MODULES_SHA256:
        return d, "installed parser dependencies do not match the lockfile pin"
    return d, None


def decode(body: bytes, kind: str) -> tuple[str, str | None]:
    """Text of a web file and a note when it is not plain UTF-8. BOMs (UTF-8/16/32) and a CSS
    @charset are honoured; anything else undecodable is read byte-for-byte as latin-1 so the
    audited structure matches the bytes, and the note is reported."""
    for bom, enc in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ):
        if body.startswith(bom):
            try:
                return body.decode(enc), f"{enc.upper()} with BOM (Odoo bundles read UTF-8)" if (
                    "16" in enc or "32" in enc
                ) else None
            except UnicodeDecodeError:
                break
    try:
        return body.decode("utf-8"), None
    except UnicodeDecodeError:
        pass
    m = re.match(rb'@charset\s+"([A-Za-z0-9_-]{1,40})"', body) if kind != "js" else None
    if m:
        try:
            return body.decode(m.group(1).decode()), None
        except (LookupError, UnicodeDecodeError):
            pass
    return body.decode("latin-1"), "not UTF-8 (audited byte-for-byte as latin-1)"


def _run_batch(
    node: str, helper_dir: Path, files: list[tuple[str, str, str]]
) -> dict[str, dict[str, Any]] | str:
    cmd = _cmd(node, helper_dir)
    if cmd is None:
        return "no OS sandbox (sandbox-exec / unshare -rn) to run the parser without network"
    payload = json.dumps({"files": [{"path": p, "kind": k, "text": t} for p, k, t in files]})
    try:
        r = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            cwd=helper_dir,
            env={"PATH": "/usr/bin:/bin", "NODE_OPTIONS": ""},
            preexec_fn=_limits,  # noqa: PLW1509 - no threads touch fork state here
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


def _batches(files: list[tuple[str, str, str]]) -> list[list[tuple[str, str, str]]]:
    out: list[list[tuple[str, str, str]]] = [[]]
    size = 0
    for f in files:
        if out[-1] and size + len(f[2]) > BATCH_BYTES:
            out.append([])
            size = 0
        out[-1].append(f)
        size += len(f[2])
    return out


def run(files: list[tuple[str, str, str]]) -> dict[str, dict[str, Any]] | str:
    """{path: {"ok", "findings" | "error", "line"}} for (path, kind, text) files, or the
    reason the whole batch could not be audited."""
    if not files:
        return {}
    why = helper_problem()
    if why:
        return why
    node = _node()
    if not node:
        return "Node.js binary changed since pinning"
    try:
        helper_dir, why = _private_copy()
    except OSError as e:
        return f"parser helper copy failed ({type(e).__name__})"
    try:
        if why:
            return why
        out: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(WORKERS) as ex:
            batches = _batches(files)
            done = list(ex.map(lambda b: _run_batch(node, helper_dir, b), batches))
            for b, res in zip(batches, done, strict=True):
                if isinstance(res, dict):
                    out.update(res)
                    continue
                # one bad or slow file never leaves the rest unaudited: retry one by one
                single = list(ex.map(lambda f: _run_batch(node, helper_dir, [f]), b))
                for f, r1 in zip(b, single, strict=True):
                    out[f[0]] = r1[f[0]] if isinstance(r1, dict) else {"ok": False, "error": r1}
        return out
    finally:
        shutil.rmtree(helper_dir, ignore_errors=True)


if __name__ == "__main__":  # operator: pin this host's node binary
    if sys.argv[1:] == ["--pin-node"]:
        print(json.dumps(pin_node()))
