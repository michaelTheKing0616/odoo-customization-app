"""BOT-MODULE-TEST-GATE: decide whether a generated or owned module may be installed/promoted.

Runs only in a disposable local docker sandbox (odoo:<ver> + throwaway postgres), never a client
DB or a production host. Every check must actually run and pass; anything not run is
"unverified" and unverified is never pass. The report is HMAC-signed over its content.
This module does not flip T3 on (see T3_SWITCH_PRECONDITIONS).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.bots import code_audit as ca
from app.bots import debug_notes as dn
from app.bots.versioncaps import caps

SCHEMA = "module-test-gate/1"
VERSIONS = (17, 18, 19, 20)
SANDBOX = "docker-local"  # the only sandbox endpoint the gate accepts
IMAGES = {v: f"odoo:{v}" for v in VERSIONS}
PG_IMAGE = "postgres:16"
KEY_ENV = "INGENIUM_GATE_KEY"
CHECKS = ("audit", "install", "tests", "upgrade", "access", "uninstall")
PASS, FAIL, UNVERIFIED, SKIPPED, NA = "pass", "fail", "unverified", "skipped", "n/a"
STATUSES = frozenset({PASS, FAIL, UNVERIFIED, SKIPPED, NA})
MODULE_RE = re.compile(r"[a-z][a-z0-9_]{1,62}")
STEP_TIMEOUT = 900
LOG_TAIL = 4000
_BLOCK = ("high", "medium")
_ERR = re.compile(r"^\S+ \S+ \d+ (ERROR|CRITICAL) ", re.M)
_WARN = re.compile(r"^\S+ \S+ \d+ WARNING ", re.M)
_STATS = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
_LOADED = re.compile(r"modules loaded in")
_NOT_LOADED = re.compile(
    r"Some modules (are not loaded|have inconsistent states)|invalid module names"
)
_RESULT = re.compile(r"^GATE_RESULT (\{.*\})$", re.M)

# What must be true before tiers._CAPABILITIES may set module-authoring/module-test-gate True.
T3_SWITCH_PRECONDITIONS = (
    "module-test-gate: gate_passed() verified live on every supported version (17-20) with the "
    "req2mod fixture and with an owned_change set, including the upgrade check against a prior "
    "version and uninstall leaving no orphans; results recorded in the run summary.",
    "module-test-gate: INGENIUM_GATE_KEY provisioned as a server secret (not in the repo), and the "
    "spine stores the report and re-verifies it with gate_passed(report, module_hash) right "
    "before install, recomputing module_hash from the exact bytes it installs.",
    "module-authoring: BOT-SPINE-WIRE routes every T3 install/upgrade through approval (L3) and "
    "refuses unless gate_passed() is True for the same module hash and Odoo version.",
    "module-authoring: install targets only the client's staging/clone first "
    "(BOT-CLONE-REHEARSAL), with a backup and an uninstall path; kill switch and audit chain "
    "cover the install.",
    "Both capabilities are flipped in tiers._CAPABILITIES in the same reviewed commit that ships "
    "the wiring above, with tests proving tier_ready(T3) is False if either is missing.",
)


class GateError(Exception):
    pass


# ---------------------------------------------------------------- runner


@dataclass
class RunResult:
    rc: int
    output: str


class Runner(Protocol):
    def run(
        self, argv: Sequence[str], *, stdin: str | None = None, timeout: int = STEP_TIMEOUT
    ) -> RunResult: ...


_SAFE_ARG = re.compile(r"[A-Za-z0-9_./:=,@+-]{1,512}")
_ENV_KEYS = frozenset(
    {"HOST", "USER", "PASSWORD", "POSTGRES_USER", "POSTGRES_PASSWORD", "GATE_MODULE"}
)
_BAD_FLAGS = frozenset(
    {
        "--privileged",
        "--net=host",
        "--network=host",
        "-p",
        "--publish",
        "--pid",
        "--cap-add",
        "--device",
        "--security-opt",
        "--volumes-from",
        "--userns",
    }
)


def _sandbox_name(v: str) -> bool:
    return bool(re.fullmatch(r"ingate-[0-9a-f]{12}(-pg|-net)?", v))


def validate_argv(argv: Sequence[str], tmp_root: str) -> None:
    """Hard allow-list for docker invocations. Raises GateError on anything outside it."""
    if not isinstance(argv, (list, tuple)) or len(argv) < 2 or argv[0] != "docker":
        raise GateError("only docker argv lists are allowed")
    for a in argv:
        if (
            not isinstance(a, str)
            or not _SAFE_ARG.fullmatch(a)
            or a in _BAD_FLAGS
            or "docker.sock" in a
        ):
            raise GateError("argument outside the sandbox allow-list")
    sub = tuple(argv[1:3])
    if sub == ("context", "inspect"):
        if list(argv) != ["docker", "context", "inspect"]:
            raise GateError("context inspect takes no arguments")
        return
    if sub in (("network", "create"), ("network", "rm")):
        if len(argv) != 4 or not _sandbox_name(argv[3]):
            raise GateError("network name outside the sandbox")
        return
    if argv[1] == "rm":
        if argv[2:3] != ["-f"] or not argv[3:] or not all(_sandbox_name(x) for x in argv[3:]):
            raise GateError("rm only for sandbox containers")
        return
    if argv[1] == "exec":
        if len(argv) < 4 or not _sandbox_name(argv[2]) or argv[3] != "pg_isready":
            raise GateError("exec only pg_isready in the sandbox db")
        return
    if argv[1] != "run":
        raise GateError("docker subcommand not allowed")
    images = [a for a in argv if a in IMAGES.values() or a == PG_IMAGE]
    if len(images) != 1:
        raise GateError("image outside the allow-list")
    i, net = 2, None
    img_at = argv.index(images[0])
    while i < img_at:
        a = argv[i]
        if a in ("--rm", "-i", "-d"):
            i += 1
            continue
        if a not in ("--name", "--network", "-e", "-v"):
            raise GateError(f"docker run flag not allowed: {a}")
        val = argv[i + 1]
        if a in ("--name", "--network") and not _sandbox_name(val):
            raise GateError("container/network name outside the sandbox")
        if a == "--network":
            net = val
        if a == "-e" and val.split("=", 1)[0] not in _ENV_KEYS:
            raise GateError("environment variable not allowed")
        if a == "-v":
            src, _, rest = val.partition(":")
            if rest not in ("/mnt/extra-addons:ro",) or not src.startswith(tmp_root + "/"):
                raise GateError("mount outside the sandbox work dir")
        i += 2
    if net is None:
        raise GateError("sandbox containers must join the sandbox network")


class DockerRunner:
    """Real runner. Refuses unless ODOO_LIVE=1 and the docker endpoint is local."""

    def __init__(self, tmp_root: str = "/tmp") -> None:
        if os.environ.get("ODOO_LIVE") != "1":
            raise GateError("real sandbox runner needs ODOO_LIVE=1")
        dh = os.environ.get("DOCKER_HOST", "")
        if dh and not dh.startswith("unix://"):
            raise GateError("DOCKER_HOST is not a local socket")
        self.tmp_root = os.path.realpath(tmp_root)
        if shutil.which("docker") is None:
            raise GateError("docker not available")
        ctx = self.run(["docker", "context", "inspect"], timeout=30)
        try:
            host = json.loads(ctx.output)[0]["Endpoints"]["docker"]["Host"]
        except (ValueError, LookupError, TypeError) as e:
            raise GateError("cannot confirm the docker endpoint") from e
        if ctx.rc != 0 or not str(host).startswith("unix://"):
            raise GateError("docker endpoint is not local")

    def run(
        self, argv: Sequence[str], *, stdin: str | None = None, timeout: int = STEP_TIMEOUT
    ) -> RunResult:
        validate_argv(argv, self.tmp_root)
        try:
            p = subprocess.run(  # noqa: S603 - argv list, allow-listed above, never a shell
                list(argv),
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if k != "DOCKER_HOST" or v.startswith("unix://")
                },
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return RunResult(-1, f"runner error: {type(e).__name__}")
        return RunResult(p.returncode, (p.stdout or "") + (p.stderr or ""))


# ---------------------------------------------------------------- report


@dataclass
class Check:
    status: str
    detail: str = ""
    log: str = ""
    notes: list[str] = field(default_factory=list)  # debug_notes signature ids


@dataclass
class GateReport:
    schema: str
    module: str
    module_hash: str
    version: int
    prior_hash: str | None
    checks: dict[str, Check]
    verdict: str
    signature: str = ""

    def body(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature")
        return d

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _key() -> bytes | None:
    k = os.environ.get(KEY_ENV, "")
    return k.encode() if len(k) >= 32 else None


def _sign(body: Mapping[str, Any]) -> str:
    key = _key()
    if key is None:
        return ""
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()


def module_hash(files: Mapping[str, bytes]) -> str:
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.encode() + b"\0" + hashlib.sha256(files[p]).hexdigest().encode() + b"\n")
    return h.hexdigest()


def gate_passed(report: Any, module_hash: Any) -> bool:
    """True only for an untampered, signed report where every check ran and passed for exactly
    this module hash. Never raises."""
    try:
        d = report.to_dict() if isinstance(report, GateReport) else dict(report)
        sig = d.pop("signature", "")
        if not isinstance(sig, str) or not sig or not isinstance(module_hash, str):
            return False
        if not hmac.compare_digest(sig, _sign(d) or "x"):
            return False
        if d.get("schema") != SCHEMA or d.get("module_hash") != module_hash:
            return False
        if type(d.get("version")) is not int or d["version"] not in VERSIONS:
            return False
        checks = d.get("checks")
        if not isinstance(checks, dict) or set(checks) != set(CHECKS):
            return False
        for name in CHECKS:
            st = checks[name].get("status") if isinstance(checks[name], dict) else None
            ok = st == PASS or (name == "upgrade" and st == NA and d.get("prior_hash") is None)
            if not ok:
                return False
        return d.get("verdict") == PASS
    except Exception:  # noqa: BLE001 - fail closed
        return False


# ---------------------------------------------------------------- helpers


def _tail(text: str) -> str:
    return dn.redact(text[-LOG_TAIL:])


def _classify(text: str, version: int) -> list[str]:
    errs = "\n".join(m.group(0) + text[m.end() :].split("\n", 1)[0] for m in _ERR.finditer(text))
    r = dn.match(errs or text[-LOG_TAIL:], version=version)
    return [m.id for m in r.matches] if r.status == "matched" else []


def _odoo_ok(res: RunResult) -> tuple[bool, str]:
    if res.rc != 0:
        return False, f"odoo exited {res.rc}"
    if _ERR.search(res.output):
        return False, f"{len(_ERR.findall(res.output))} ERROR/CRITICAL log line(s)"
    if _NOT_LOADED.search(res.output) or not _LOADED.search(res.output):
        return False, "module did not load"
    return True, ""


def _test_methods(files: Mapping[str, bytes]) -> tuple[set[str], set[str]]:
    """(all test_* methods, access tests) in the module's own tests/*.py."""
    import ast

    every, access = set(), set()
    for p, b in files.items():
        if not (p.startswith("tests/") and p.endswith(".py")):
            continue
        try:
            tree = ast.parse(b)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
                every.add(n.name)
                src = ast.unparse(n)
                if "with_user(" in src and ("has_access" in src or "check_access_rights" in src):
                    access.add(n.name)
    return every, access


def _declared_roles(files: Mapping[str, bytes], module: str) -> int:
    """Access rows granting this module's own groups (the spec's roles): CSV ir.model.access
    rows and XML ir.model.access / ir.access (Odoo 20) records. -1 when unreadable."""
    import csv
    import io

    def own(g: str) -> bool:
        g = g.strip()
        return bool(g) and (g.startswith(module + ".") or "." not in g)

    n = 0
    for p, b in files.items():
        try:
            if p.endswith("ir.model.access.csv"):
                for row in csv.DictReader(io.StringIO(b.decode("utf-8-sig"))):
                    n += own(row.get("group_id:id") or "")
            elif p.startswith("security/") and p.endswith(".xml"):
                root = ca._parse_xml(b)
                for rec in root.iter("record"):
                    if rec.get("model") in ("ir.model.access", "ir.access"):
                        n += any(
                            f.get("name") == "group_id" and own(f.get("ref") or "")
                            for f in rec.findall("field")
                        )
        except Exception:  # noqa: BLE001 - fail closed
            return -1
    return n


_UNINSTALL_SCRIPT = r"""
import json, os
m = os.environ['GATE_MODULE']
mod = env['ir.module.module'].search([('name', '=', m)])
before = mod.state
ids = env['ir.model.data'].search([('module', '=', m), ('model', '=', 'ir.model')]).mapped('res_id')
names = env['ir.model'].browse(ids).mapped('model')
tables = set()
for n in names:
    if n in env and env[n]._auto and not env[n]._abstract:
        tables.add(env[n]._table)
        for f in env[n]._fields.values():
            if f.type == 'many2many' and f.store and getattr(f, 'relation', None):
                tables.add(f.relation)
mod.button_immediate_uninstall()
env.cr.commit()
cr = env.cr
cr.execute("SELECT state FROM ir_module_module WHERE name=%s", (m,))
after = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM ir_model_data WHERE module=%s", (m,))
xmlids = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM ir_model WHERE model = ANY(%s)", (list(names),))
models = cr.fetchone()[0]
cr.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_name = ANY(%s)",
    (sorted(tables),),
)
left = sorted(r[0] for r in cr.fetchall())
print('GATE_RESULT ' + json.dumps({'before': before, 'after': after, 'xmlids': xmlids,
      'models': models, 'tables': left, 'n_models': len(names)}))
"""


# ---------------------------------------------------------------- gate


class _Sandbox:
    def __init__(self, runner: Runner, version: int, module: str, tmp_root: str) -> None:
        self.r, self.v, self.mod = runner, version, module
        tag = uuid.uuid4().hex[:12]
        self.net, self.pg, self.name = f"ingate-{tag}-net", f"ingate-{tag}-pg", f"ingate-{tag}"
        self.work = tempfile.mkdtemp(prefix="ingate-", dir=tmp_root)
        self.up = False

    def addons(self, label: str, files: Mapping[str, bytes]) -> str:
        root = Path(self.work) / label
        for p, b in files.items():
            dst = root / self.mod / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b)
        return str(root)

    def start(self) -> None:
        r = self.r.run(["docker", "network", "create", self.net], timeout=60)
        if r.rc != 0:
            raise GateError("sandbox network failed")
        self.up = True
        r = self.r.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                self.pg,
                "--network",
                self.net,
                "-e",
                "POSTGRES_USER=odoo",
                "-e",
                "POSTGRES_PASSWORD=odoo",
                PG_IMAGE,
            ],
            timeout=120,
        )
        if r.rc != 0:
            raise GateError("sandbox database failed")
        for _ in range(60):
            if (
                self.r.run(["docker", "exec", self.pg, "pg_isready", "-U", "odoo"], timeout=10).rc
                == 0
            ):
                return
            import time

            time.sleep(1)
        raise GateError("sandbox database not ready")

    def odoo(
        self, addons: str, db: str, sub: str, *args: str, stdin: str | None = None
    ) -> RunResult:
        argv = (
            ["docker", "run", "--rm"]
            + (["-i"] if stdin is not None else [])
            + [
                "--network",
                self.net,
                "-e",
                f"HOST={self.pg}",
                "-e",
                "USER=odoo",
                "-e",
                "PASSWORD=odoo",
                "-e",
                f"GATE_MODULE={self.mod}",
                "-v",
                f"{addons}:/mnt/extra-addons:ro",
                IMAGES[self.v],
                "odoo",
                *([sub] if sub else []),
                "-d",
                db,
                *args,
            ]
        )
        return self.r.run(argv, stdin=stdin)

    def close(self) -> None:
        if self.up:
            self.r.run(["docker", "rm", "-f", self.pg], timeout=60)
            self.r.run(["docker", "network", "rm", self.net], timeout=60)
        shutil.rmtree(self.work, ignore_errors=True)


def _load(src: Any) -> dict[str, bytes]:
    if isinstance(src, Mapping):
        out = {}
        for p, b in src.items():
            if not isinstance(p, str) or not isinstance(b, (bytes, bytearray)):
                raise GateError("files must map str paths to bytes")
            out[ca._safe_rel(p)] = bytes(b)
        if any(p.rsplit("/", 1)[-1] == ".module_dir" for p in out):
            raise GateError("reserved file name")
        return out
    files, _top = ca.load_tree(src)
    return files


def run_gate(
    src: Any,
    *,
    module: Any,
    version: Any,
    prior: Any = None,
    runner: Runner | None = None,
    sandbox: Any = SANDBOX,
    tmp_root: str = "/tmp",
) -> GateReport:
    """Run all checks. Refuses (GateError) on invalid input or a non-sandbox endpoint; every
    other failure is recorded in the report, which then cannot pass."""
    if sandbox != SANDBOX:
        raise GateError(
            f"sandbox endpoint must be {SANDBOX!r}; client and production hosts are refused"
        )
    if type(version) is not int or version not in VERSIONS:
        raise GateError(f"version must be one of {VERSIONS}")
    if not isinstance(module, str) or not MODULE_RE.fullmatch(module):
        raise GateError("module name invalid")
    if caps.module_info(version, module) is not None:
        raise GateError("module name is a stock Odoo module")
    try:
        files = _load(src)
        old = _load(prior) if prior is not None else None
    except (ca.SourceError, GateError) as e:
        raise GateError(f"source refused: {e}") from e
    if "__manifest__.py" not in files:
        raise GateError("not a module (no __manifest__.py)")
    mh = module_hash(files)
    checks: dict[str, Check] = {}
    checks["audit"] = _audit(files, old, module, version)
    tmp_root = os.path.realpath(tmp_root)
    sb: _Sandbox | None = None
    if runner is None:
        for c in CHECKS[1:]:
            checks[c] = Check(UNVERIFIED, "sandbox unavailable")
    elif checks["audit"].status != PASS:
        for c in CHECKS[1:]:
            checks[c] = Check(SKIPPED, "audit failed")
    else:
        try:
            sb = _Sandbox(runner, version, module, tmp_root)
            sb.start()
            _sandbox_checks(sb, files, old, version, checks)
        except Exception as e:  # noqa: BLE001 - fail closed
            msg = str(e) if isinstance(e, GateError) else type(e).__name__
            for c in CHECKS[1:]:
                checks.setdefault(c, Check(UNVERIFIED, f"sandbox error: {msg}"))
        finally:
            if sb is not None:
                sb.close()
    for c in CHECKS:
        checks.setdefault(c, Check(UNVERIFIED, "not run"))
    ok = all(
        checks[c].status == PASS or (c == "upgrade" and checks[c].status == NA and old is None)
        for c in CHECKS
    )
    rep = GateReport(
        SCHEMA, module, mh, version, module_hash(old) if old else None, checks, PASS if ok else FAIL
    )
    rep.signature = _sign(rep.body())
    if not rep.signature:
        rep.verdict = FAIL
        rep.checks["audit"].notes.append("unsigned: gate key missing")
        rep.signature = ""
    return rep


def _audit(files, old, module, version) -> Check:
    def zipit(fs):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for p, b in fs.items():
                z.writestr(f"{module}/{p}", b)
        return buf.getvalue()

    new = ca.audit(zipit(files), version=version, owned_names={module})
    if not new.ok:
        return Check(FAIL, f"audit could not run: {new.error}")
    base: dict[tuple[str, str], int] = {}
    if old is not None:
        prev = ca.audit(zipit(old), version=version, owned_names={module})
        if not prev.ok:
            return Check(FAIL, f"prior audit could not run: {prev.error}")
        for f in prev.findings:
            if f.severity in _BLOCK:
                base[(f.code, f.file)] = base.get((f.code, f.file), 0) + 1
    added = []
    for f in new.findings:
        if f.severity in _BLOCK:
            k = (f.code, f.file)
            if base.get(k):
                base[k] -= 1
            else:
                added.append(f"{f.severity} {f.code} {f.file}:{f.line}")
    if added:
        return Check(FAIL, f"{len(added)} new high/medium finding(s)", "\n".join(added[:50]))
    return Check(PASS, f"0 new high/medium; counts {new.counts}")


def _sandbox_checks(sb: _Sandbox, files, old, version, checks: dict[str, Check]) -> None:
    mod = sb.mod
    new_dir = sb.addons("new", files)
    # (2) install on a fresh DB
    res = sb.odoo(new_dir, "gate_main", "", "-i", mod, "--stop-after-init", "--without-demo=all")
    ok, why = _odoo_ok(res)
    warns = len(_WARN.findall(res.output))
    checks["install"] = Check(
        PASS if ok else FAIL,
        why or f"installed; {warns} warning line(s)",
        _tail(res.output),
        [] if ok else _classify(res.output, version),
    )
    if not ok:
        for c in ("tests", "access", "uninstall"):
            checks[c] = Check(SKIPPED, "install failed")
    else:
        # (3) the module's own tests, (5) role access via its generated tests
        every, access = _test_methods(files)
        res = sb.odoo(
            new_dir,
            "gate_main",
            "",
            "-u",
            mod,
            "--test-enable",
            "--test-tags",
            f"/{mod}",
            "--stop-after-init",
        )
        stats = [tuple(map(int, m)) for m in _STATS.findall(res.output)]
        failed = sum(s[0] for s in stats)
        errors = sum(s[1] for s in stats)
        ran = sum(s[2] for s in stats)
        ok3, why3 = _odoo_ok(res)
        if not every:
            checks["tests"] = Check(FAIL, "module has no tests")
        elif not stats:
            checks["tests"] = Check(UNVERIFIED, "no test result line in output", _tail(res.output))
        elif failed or errors or not ok3 or ran < len(every):
            checks["tests"] = Check(
                FAIL,
                f"{failed} failed, {errors} error(s) of {ran} "
                f"(expected {len(every)}) {why3}".strip(),
                _tail(res.output),
                _classify(res.output, version),
            )
        else:
            checks["tests"] = Check(PASS, f"0 failed, 0 error(s) of {ran} tests", _tail(res.output))
        roles = _declared_roles(files, mod)
        if roles < 0:
            checks["access"] = Check(FAIL, "access file unreadable")
        elif roles == 0:
            checks["access"] = Check(FAIL, "no declared role access rows to verify")
        elif not access:
            checks["access"] = Check(FAIL, f"{roles} role access row(s) but no access tests")
        elif checks["tests"].status != PASS:
            checks["access"] = Check(
                checks["tests"].status if checks["tests"].status != FAIL else FAIL,
                "access tests did not pass",
            )
        else:
            missing = sorted(a for a in access if a not in res.output)
            checks["access"] = (
                Check(PASS, f"{len(access)} access test(s) passed for {roles} row(s)")
                if not missing
                else Check(UNVERIFIED, f"not seen in log: {', '.join(missing[:10])}")
            )
        # (6) uninstall leaves no orphans
        res = sb.odoo(new_dir, "gate_main", "shell", "--no-http", stdin=_UNINSTALL_SCRIPT)
        m = _RESULT.findall(res.output)
        if not m:
            checks["uninstall"] = Check(
                UNVERIFIED if res.rc == 0 else FAIL,
                "no uninstall result",
                _tail(res.output),
                _classify(res.output, version),
            )
        else:
            d = json.loads(m[-1])
            bad = []
            if d.get("before") != "installed":
                bad.append(f"state before {d.get('before')}")
            if d.get("after") != "uninstalled":
                bad.append(f"state after {d.get('after')}")
            if d.get("xmlids"):
                bad.append(f"{d['xmlids']} xmlid(s) left")
            if d.get("models"):
                bad.append(f"{d['models']} model(s) left")
            if d.get("tables"):
                bad.append(f"tables left: {', '.join(d['tables'][:10])}")
            checks["uninstall"] = Check(
                FAIL if bad else PASS,
                "; ".join(bad)
                or f"clean: {d.get('n_models', 0)} model(s) removed, no xmlids/tables left",
            )
    # (4) upgrade path
    if old is None:
        checks["upgrade"] = Check(NA, "no prior version")
    else:
        old_dir = sb.addons("old", old)
        r1 = sb.odoo(old_dir, "gate_upg", "", "-i", mod, "--stop-after-init", "--without-demo=all")
        ok1, why1 = _odoo_ok(r1)
        if not ok1:
            checks["upgrade"] = Check(
                FAIL,
                f"prior version did not install: {why1}",
                _tail(r1.output),
                _classify(r1.output, version),
            )
        else:
            r2 = sb.odoo(new_dir, "gate_upg", "", "-u", mod, "--stop-after-init")
            ok2, why2 = _odoo_ok(r2)
            checks["upgrade"] = Check(
                PASS if ok2 else FAIL,
                why2 or "prior -> new upgraded cleanly",
                _tail(r2.output),
                [] if ok2 else _classify(r2.output, version),
            )


__all__ = [
    "CHECKS",
    "SANDBOX",
    "T3_SWITCH_PRECONDITIONS",
    "Check",
    "DockerRunner",
    "GateError",
    "GateReport",
    "RunResult",
    "Runner",
    "gate_passed",
    "module_hash",
    "run_gate",
    "validate_argv",
]
