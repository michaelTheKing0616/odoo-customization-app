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
HELPER_SHA256 = "7fc85c63ec344095b1a95dfccda8535d8b1849bdf056921aa45c8328939cf917"
LOCK_SHA256 = "0979e699da625fe55eed29479d64824c3a02acd99793ca3f7c02ecea8e6549d5"
MODULES_SHA256 = "c5adf899c2ee30faa46f5269d41d15bf3dd590b0a1665d87b2459caf7c9dcb96"
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
# no parser here: never loaded by Odoo's asset bundles (sources for a build step) -> LOW
UNPARSEABLE = (".coffee", ".styl")
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
        return "sass"  # indented syntax: postcss-sass
    if low.endswith(".d.ts"):
        return "ts"  # declarations hold no code: audit like .ts so hidden code is seen
    for ext in (".tsx", ".ts", ".jsx"):
        if low.endswith(ext):
            return ext[1:]  # types stripped / JSX compiled by sucrase, then audited as JS
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


# OS-sealed locations: the signed system volume / dyld shared cache (macOS). Every other
# dynamic library the binary loads, directly or transitively, is hashed into the pin.
_SEALED = ("/usr/lib/", "/System/")


def _raw_deps(obj: Path) -> list[str]:
    """Install names exactly as recorded in a Mach-O object (otool -L), unresolved."""
    r = subprocess.run(
        ["/usr/bin/otool", "-L", str(obj)], capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        raise RuntimeError(f"otool failed on {obj.name}")
    out = []
    for line in r.stdout.splitlines()[1:]:
        p = line.strip().split(" (compatibility", 1)[0].strip()
        if p:
            out.append(p)
    return out


def _rpaths(obj: Path) -> list[str]:
    r = subprocess.run(
        ["/usr/bin/otool", "-l", str(obj)], capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        raise RuntimeError(f"otool failed on {obj.name}")
    out, inrp = [], False
    for line in r.stdout.splitlines():
        t = line.strip()
        if t.startswith("cmd "):
            inrp = t == "cmd LC_RPATH"
        elif inrp and t.startswith("path "):
            out.append(t[5:].rsplit(" (offset", 1)[0].strip())
    return out


def _deps(obj: Path, loader: Path) -> list[tuple[str, str]]:
    """Direct dynamic-library dependencies of one object as (load name, path):
    otool -L install names on macOS, ldd sonames (and the ELF interpreter) on Linux."""
    if sys.platform == "darwin":
        out = []
        for raw in _raw_deps(obj):
            p = raw
            for pre, base in (
                ("@rpath/", loader.parent.parent / "lib"),
                ("@loader_path/", obj.parent),
                ("@executable_path/", loader.parent),
            ):
                if p.startswith(pre):
                    cand = base / p[len(pre) :]
                    if pre == "@rpath/" and not cand.exists():
                        cand = obj.parent / p[len(pre) :]
                    p = str(cand)
            out.append((Path(raw).name, p))
        return out
    ldd = shutil.which("ldd")
    if not ldd:
        raise RuntimeError("ldd not found")
    r = subprocess.run([ldd, str(obj)], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"ldd failed on {obj.name}")
    out = []
    for line in r.stdout.splitlines():
        if "=>" in line:
            name, rest = line.split("=>", 1)
            p = rest.strip().split(" (", 1)[0].strip()
            if p == "not found":
                raise RuntimeError(f"unresolved library: {line.strip()[:80]}")
            if p:
                out.append((name.strip(), p))
        elif line.strip().startswith("/"):
            p = line.strip().split(" (", 1)[0]
            out.append((INTERP + Path(p).name, p))
    return out


INTERP = "interp:"  # name prefix marking the ELF program interpreter (ld.so)


def _node_closure(node: Path) -> dict[str, Path]:
    """{load name: real path} for every non-sealed dynamic library Node loads, transitively
    (pin-time; fail closed on a missing library or two different files under one name)."""
    seen: dict[str, Path] = {}
    todo = [node]
    done: set[Path] = set()
    while todo:
        obj = todo.pop()
        if obj in done:
            continue
        done.add(obj)
        for name, d in _deps(obj, node):
            if sys.platform == "darwin" and d.startswith(_SEALED):
                continue
            p = Path(d).resolve(strict=True)  # a listed library that is missing: refuse
            if p == node:
                continue
            if name in seen and seen[name] != p:
                raise RuntimeError(f"two libraries load as {name}")
            seen[name] = p
            todo.append(p)
    return dict(sorted(seen.items()))


def _libs_digest(libs: list[Path]) -> str:
    h = hashlib.sha256()
    for lib in libs:
        h.update(str(lib).encode() + b"\0" + _sha(lib).encode() + b"\n")
    return h.hexdigest()


PIN_FORMAT = 2


def pin_node(cand: str | None = None) -> dict[str, Any]:
    """Operator step (like npm ci): pin this host's Node binary by real path and hash, with
    the full dynamic-library closure it loads (otool -L / ldd, transitively), each library
    by load name, real path and its own hash."""
    c = cand or _find_node()
    if not c:
        raise RuntimeError(
            "Node.js not found: install Node >= "
            f"{NODE_MIN_MAJOR}, then run: python -m app.bots.code_audit_web --pin-node "
            "(or set INGENIUM_NODE=/path/to/node)"
        )
    real = Path(c).resolve(strict=True)
    names = _node_closure(real)
    libs = sorted(set(names.values()))
    doc = {
        "format": PIN_FORMAT,
        "path": str(real),
        "sha256": _sha(real),
        "libs": [str(p) for p in libs],
        "libs_sha256": _libs_digest(libs),
        "lib_sha256": {str(p): _sha(p) for p in libs},
        "names": {n: str(p) for n, p in names.items()},
    }
    d, why = _private_node(doc)
    if why or d is None:
        raise RuntimeError(why or "private Node.js build failed")
    doc["private_sha256"] = _tree_shas(d)
    NODE_PIN.write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def _pin() -> dict[str, Any] | None:
    """The pin, re-verified now (binary and every pinned library); None when unpinned,
    old-format (no per-library hashes) or changed."""
    try:
        pin = json.loads(NODE_PIN.read_text())
        if pin.get("format") != PIN_FORMAT or not isinstance(pin.get("private_sha256"), dict):
            return None
        real = Path(pin["path"])
        libs = [Path(p) for p in pin["libs"]]
        if real.is_symlink() or not real.is_file() or any(p.is_symlink() for p in libs):
            return None
        if set(pin["lib_sha256"]) != set(pin["libs"]) or set(pin["names"].values()) != set(
            pin["libs"]
        ):
            return None
        if _sha(real) != pin["sha256"] or _libs_digest(libs) != pin["libs_sha256"]:
            return None
        if any(_sha(p) != pin["lib_sha256"][str(p)] for p in libs):
            return None
        return pin
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _node() -> str | None:
    """The pinned Node binary, re-hashed now; None when unpinned or changed."""
    pin = _pin()
    return pin["path"] if pin else None


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
    pre = [node]
    interp = Path(node).parent.parent / "lib.interp"
    if sys.platform.startswith("linux"):
        if not interp.is_file():
            return None
        pre = [
            str(interp.parent / "lib" / interp.read_text()),
            "--library-path",
            str(interp.parent / "lib"),
            node,
        ]
    return [
        *sb,
        *pre,
        "--disallow-code-generation-from-strings",
        "--permission",
        f"--allow-fs-read={helper_dir}",
        str(helper_dir / "audit.mjs"),
    ]


NODE_CACHE_ROOT = Path.home() / ".cache" / "ingenium-node"


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


def _build_private(pin: dict[str, Any], d: Path) -> str | None:
    """Node and its whole non-sealed library closure as private copies in d, each hashed
    against its own pin after copying (no swap window on the originals), then relinked so
    the loader can only resolve them inside d."""
    (d / "bin").mkdir()
    (d / "lib").mkdir()
    shutil.copy2(pin["path"], d / "bin" / "node")
    if _sha(d / "bin" / "node") != pin["sha256"]:
        return "Node.js binary copy does not match its pin"
    (d / "bin" / "node").chmod(0o700)
    for name, src in pin["names"].items():
        dst = d / "lib" / name.removeprefix(INTERP)
        shutil.copy2(src, dst)
        if _sha(dst) != pin["lib_sha256"][src]:
            return "Node.js library copy does not match its pin"
        dst.chmod(0o700)
        if name.startswith(INTERP):
            (d / "lib.interp").write_text(dst.name)
    if sys.platform == "darwin":
        return _relink(d, pin)
    if not (d / "lib.interp").is_file():
        return "Node.js program interpreter not pinned"
    return None


def _tree_shas(d: Path) -> dict[str, str]:
    out = {}
    for f in sorted(d.rglob("*")):
        if f.is_symlink():
            out[str(f.relative_to(d))] = "symlink"
        elif f.is_file():
            out[str(f.relative_to(d))] = _sha(f)
    return out


def _private_dir_ok(p: Path) -> bool:
    try:
        st = p.lstat()
    except OSError:
        return False
    import stat

    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077


def _private_node(pin: dict[str, Any]) -> tuple[Path | None, str | None]:
    """The relinked private Node closure for this pin: built once (the first launch of a
    freshly signed binary costs seconds of OS verification), re-verified file by file
    against the pinned post-relink hashes before every use, rebuilt when it differs."""
    root = NODE_CACHE_ROOT
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _private_dir_ok(root):
        return None, "private Node.js directory is not owner-only"
    want = pin.get("private_sha256")
    d = root / (pin["sha256"][:16] + pin["libs_sha256"][:16])
    if d.exists() or d.is_symlink():
        if want and _private_dir_ok(d) and _tree_shas(d) == want:
            return d, None
        if d.is_symlink() or not d.is_dir():
            d.unlink()
        else:
            shutil.rmtree(d)
    tmp = Path(tempfile.mkdtemp(dir=root))
    try:
        why = _build_private(pin, tmp)
        if why:
            return None, why
        if want is not None and _tree_shas(tmp) != want:
            return None, "Node.js private closure does not match its pin"
        os.rename(tmp, d)
    except OSError as e:
        return None, f"private Node.js build failed ({type(e).__name__})"
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return d, None


def _tool(args: list[str]) -> bool:
    try:
        return subprocess.run(args, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _relink(d: Path, pin: dict[str, Any]) -> str | None:
    """macOS: point every non-sealed load command of the private node and libraries at the
    private lib/ copies, drop absolute rpaths, ad-hoc re-sign, then verify nothing outside
    the private directory or the sealed system can be loaded."""
    names = set(pin["names"])
    objs = [d / "bin" / "node", *(d / "lib" / n for n in sorted(names))]
    try:
        for o in objs:
            is_node = o.parent.name == "bin"
            args = []
            for raw in _raw_deps(o)[0 if is_node else 1 :]:
                if raw.startswith(_SEALED):
                    continue
                n = Path(raw).name
                if n not in names:
                    return "Node.js loads a library outside its pin"
                new = f"@rpath/{n}" if is_node else f"@loader_path/{n}"
                if raw != new:
                    args += ["-change", raw, new]
            for rp in _rpaths(o):
                if not rp.startswith("@loader_path") and not rp.startswith("@executable_path"):
                    args += ["-delete_rpath", rp]
            if not is_node:
                args += ["-id", f"@loader_path/{o.name}"]
            if args and not _tool(["/usr/bin/install_name_tool", *args, str(o)]):
                return "Node.js library relink failed"
            if not _tool(["/usr/bin/codesign", "-f", "-s", "-", str(o)]):
                return "Node.js library re-sign failed"
        for o in objs:
            is_node = o.parent.name == "bin"
            for raw in _raw_deps(o)[0 if is_node else 1 :]:
                if raw.startswith(_SEALED):
                    continue
                pre = "@rpath/" if is_node else "@loader_path/"
                if not raw.startswith(pre) or raw[len(pre) :] not in names:
                    return "Node.js library closure not private after relink"
            if any(not rp.startswith(("@loader_path", "@executable_path")) for rp in _rpaths(o)):
                return "Node.js library closure not private after relink"
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return "Node.js library relink failed"
    return None


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
        pin = _pin()
        if pin is None:
            return "Node.js binary changed since pinning"
        try:
            priv, why = _private_node(pin)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            return f"private Node.js build failed ({type(e).__name__})"
        if why or priv is None:
            return why or "private Node.js build failed"
        node = str(priv / "bin" / "node")  # the verified private, relinked copy
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


def main(argv: list[str]) -> int:
    """Operator command: `python -m app.bots.code_audit_web --pin-node [/path/to/node]`."""
    if not argv or argv[0] != "--pin-node" or len(argv) > 2:
        print(
            "usage: python -m app.bots.code_audit_web --pin-node [/path/to/node]", file=sys.stderr
        )
        return 2
    try:
        doc = pin_node(argv[1] if len(argv) == 2 else None)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        print(f"pin failed: {e}", file=sys.stderr)
        return 1
    major = _node_major(doc["path"])
    if major < NODE_MIN_MAJOR:
        NODE_PIN.unlink(missing_ok=True)
        print(f"pin refused: Node.js {major} is older than {NODE_MIN_MAJOR}", file=sys.stderr)
        return 1
    print(f"pinned Node.js {major} with {len(doc['libs'])} libraries -> {NODE_PIN.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
