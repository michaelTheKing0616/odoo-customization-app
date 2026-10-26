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
_NOT_LOADED = re.compile(
    r"Some modules (are not loaded|have inconsistent states)|invalid module names"
)

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
# Containment for the Odoo container that runs the (untrusted) module code, and limits for the
# sandbox database. The network is created --internal: no route out (images must be pulled
# beforehand). validate_argv requires every one of these flags, exactly as written.
ODOO_HARDEN = (
    "--memory=2g",
    "--memory-swap=2g",
    "--pids-limit=256",
    "--cpus=2",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--read-only",
    "--tmpfs=/tmp:rw,nosuid,nodev,mode=1777,size=256m",
    "--tmpfs=/var/lib/odoo:rw,nosuid,nodev,mode=1777,size=512m",
    "--user=odoo",
)
PG_HARDEN = (
    "--memory=1g",
    "--memory-swap=1g",
    "--pids-limit=256",
    "--cpus=1",
    "--security-opt=no-new-privileges",
)
_RUN_FLAGS = frozenset(ODOO_HARDEN + PG_HARDEN)
_ODOO_FLAGS = frozenset({"--stop-after-init", "--without-demo=all", "--test-enable", "--no-http"})
DB_RE = re.compile(r"gateu?_[0-9a-f]{16}")
_NET_RE = re.compile(r"ingate-[0-9a-f]{12}-net")
_PSQL_TAIL = ["-At", "-v", "ON_ERROR_STOP=1"]


def _sandbox_name(v: str) -> bool:
    return bool(re.fullmatch(r"ingate-[0-9a-f]{12}(-pg|-net|-o\d{1,3})?", v))


def _validate_odoo_args(rest: Sequence[str]) -> None:
    """Allow-list for everything after the image: `odoo [shell] -d <sandbox db> ...`."""
    if not rest or rest[0] != "odoo":
        raise GateError("odoo container must run the odoo command")
    j, db = 1, False
    if j < len(rest) and rest[j] == "shell":
        j += 1
    while j < len(rest):
        a, nxt = rest[j], (rest[j + 1] if j + 1 < len(rest) else "")
        if a in _ODOO_FLAGS:
            j += 1
        elif a == "-d" and not db and DB_RE.fullmatch(nxt):
            db, j = True, j + 2
        elif a in ("-i", "-u") and nxt and all(MODULE_RE.fullmatch(x) for x in nxt.split(",")):
            j += 2
        elif a == "--test-tags" and re.fullmatch(r"/[a-z][a-z0-9_]{1,62}", nxt):
            j += 2
        else:
            raise GateError(f"odoo argument not allowed: {a[:40]}")
    if not db:
        raise GateError("odoo run must name a sandbox database")


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
    argv = list(argv)
    sub = tuple(argv[1:3])
    if sub == ("context", "inspect"):
        if argv != ["docker", "context", "inspect"]:
            raise GateError("context inspect takes no arguments")
        return
    if sub == ("network", "create"):
        if len(argv) != 5 or argv[3] != "--internal" or not _NET_RE.fullmatch(argv[4]):
            raise GateError("sandbox network must be --internal and sandbox-named")
        return
    if sub == ("network", "rm"):
        if len(argv) != 4 or not _NET_RE.fullmatch(argv[3]):
            raise GateError("network name outside the sandbox")
        return
    if argv[1] == "rm":
        if argv[2:3] != ["-f"] or not argv[3:] or not all(_sandbox_name(x) for x in argv[3:]):
            raise GateError("rm only for sandbox containers")
        return
    if argv[1] == "exec":
        pg = re.compile(r"ingate-[0-9a-f]{12}-pg")
        if len(argv) == 6 and pg.fullmatch(argv[2]) and argv[3:] == ["pg_isready", "-U", "odoo"]:
            return
        if (
            len(argv) == 12
            and argv[2] == "-i"
            and pg.fullmatch(argv[3])
            and argv[4:8] == ["psql", "-U", "odoo", "-d"]
            and DB_RE.fullmatch(argv[8])
            and argv[9:] == _PSQL_TAIL
        ):
            return
        raise GateError("exec only pg_isready or psql (stdin) in the sandbox db")
    if argv[1] != "run":
        raise GateError("docker subcommand not allowed")
    images = [a for a in argv if a in IMAGES.values() or a == PG_IMAGE]
    if len(images) != 1:
        raise GateError("image outside the allow-list")
    image = images[0]
    img_at = argv.index(image)
    i, net, name, host, mounts, seen = 2, None, None, None, 0, set()
    while i < img_at:
        a = argv[i]
        if a in ("--rm", "-i", "-d") or a in _RUN_FLAGS:
            if a in seen:
                raise GateError("duplicate docker run flag")
            seen.add(a)
            i += 1
            continue
        if a not in ("--name", "--network", "-e", "-v") or i + 1 >= img_at:
            raise GateError(f"docker run flag not allowed: {a[:40]}")
        val = argv[i + 1]
        if a == "--name":
            if name is not None or not _sandbox_name(val) or val.endswith("-net"):
                raise GateError("container name outside the sandbox")
            name = val
        elif a == "--network":
            if net is not None or not _NET_RE.fullmatch(val):
                raise GateError("container/network name outside the sandbox")
            net = val
        elif a == "-e":
            k, _, v = val.partition("=")
            if k not in _ENV_KEYS:
                raise GateError("environment variable not allowed")
            if k == "HOST":
                host = v
            if k == "GATE_MODULE" and not MODULE_RE.fullmatch(v):
                raise GateError("module name invalid")
        else:
            src, _, rest = val.partition(":")
            if (
                rest != "/mnt/extra-addons:ro"
                or ".." in src.split("/")
                or os.path.realpath(src) != src
                or not src.startswith(tmp_root.rstrip("/") + "/")
            ):
                raise GateError("mount outside the sandbox work dir")
            mounts += 1
        i += 2
    if net is None or name is None:
        raise GateError("sandbox containers must be named and join the sandbox network")
    tag = net[7:19]
    if image == PG_IMAGE:
        if name != f"ingate-{tag}-pg" or mounts or argv[img_at + 1 :]:
            raise GateError("sandbox database container malformed")
        if not all(f in seen for f in PG_HARDEN):
            raise GateError("sandbox database missing resource limits")
        return
    if not re.fullmatch(rf"ingate-{tag}-o\d{{1,3}}", name):
        raise GateError("odoo container name must match the sandbox")
    if host != f"ingate-{tag}-pg":
        raise GateError("HOST must be this sandbox's database")
    if mounts != 1:
        raise GateError("exactly one addons mount")
    if not all(f in seen for f in ODOO_HARDEN):
        raise GateError("odoo container missing containment flags")
    _validate_odoo_args(argv[img_at + 1 :])


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


def gate_passed(
    report: Any,
    module_hash: Any,
    *,
    version: Any = None,
    module: Any = None,
    prior_hash: Any = None,
) -> bool:
    """True only for an untampered, signed report where every check ran and passed for exactly
    this module hash, Odoo version, module name and prior version (None = fresh install).
    version and module are required; missing means False. Never raises."""
    try:
        if type(version) is not int or not isinstance(module, str):
            return False
        if prior_hash is not None and not isinstance(prior_hash, str):
            return False
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
        if d["version"] != version or d.get("module") != module:
            return False
        if d.get("prior_hash") != prior_hash:
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


# Uninstall runs inside the module's own process, so nothing it prints is trusted: the result
# is read afterwards from the sandbox database by psql in the postgres container, which never
# has the module on any path.
_UNINSTALL_SCRIPT = r"""
m = __import__('os').environ['GATE_MODULE']
env['ir.module.module'].search([('name', '=', m)]).button_immediate_uninstall()
env.cr.commit()
"""

COUNT_TABLES = (
    "ir_model_data",
    "ir_model",
    "ir_model_fields",
    "ir_ui_view",
    "ir_ui_menu",
    "ir_cron",
    "ir_act_window",
    "ir_act_server",
    "ir_act_report_xml",
    "ir_act_client",
    "ir_model_access",
    "ir_rule",
    "res_groups",
)
SQL_SCHEMA = (
    "-- gate:schema\n"
    "SELECT 'c', table_name, column_name FROM information_schema.columns "
    "WHERE table_schema = 'public'\n"
    + "".join(f"UNION ALL SELECT 'n', '{t}', count(*)::text FROM {t}\n" for t in COUNT_TABLES)
    + ";\n"
)
FORBIDDEN_GROUPS = frozenset({"base.group_public", "base.group_portal"})


def sql_state(module: str) -> str:
    assert MODULE_RE.fullmatch(module)
    return f"-- gate:state\nSELECT state FROM ir_module_module WHERE name = '{module}';\n"


def sql_access(module: str) -> str:
    assert MODULE_RE.fullmatch(module)
    grp = (
        "COALESCE((SELECT d.module || '.' || d.name FROM ir_model_data d WHERE "
        "d.model = 'res.groups' AND d.res_id = {g} ORDER BY d.id LIMIT 1), '')"
    )
    mx = (
        "COALESCE((SELECT d.module || '.' || d.name FROM ir_model_data d WHERE "
        "d.model = 'ir.model' AND d.res_id = m.id ORDER BY d.id LIMIT 1), m.model)"
    )
    return (
        "-- gate:access\n"
        f"WITH own AS (SELECT res_id FROM ir_model_data WHERE module = '{module}' "
        "AND model = 'ir.model')\n"
        f"SELECT 'a', {mx}, {grp.format(g='a.group_id')}, a.perm_read::int, "
        "a.perm_write::int, a.perm_create::int, a.perm_unlink::int\n"
        "FROM ir_model_access a JOIN ir_model m ON m.id = a.model_id\n"
        "WHERE a.active AND (a.model_id IN (SELECT res_id FROM own) OR a.id IN "
        f"(SELECT res_id FROM ir_model_data WHERE module = '{module}' "
        "AND model = 'ir.model.access'))\n"
        f"UNION ALL SELECT 'r', {mx}, {grp.format(g='rg.group_id')}, r.perm_read::int, "
        "r.perm_write::int, r.perm_create::int, r.perm_unlink::int\n"
        "FROM ir_rule r JOIN ir_model m ON m.id = r.model_id\n"
        "LEFT JOIN rule_group_rel rg ON rg.rule_group_id = r.id\n"
        "WHERE r.active AND (r.model_id IN (SELECT res_id FROM own) OR r.id IN "
        f"(SELECT res_id FROM ir_model_data WHERE module = '{module}' AND model = 'ir.rule'));\n"
    )


def _norm_ref(ref: str, module: str) -> str:
    ref = (ref or "").strip()
    return ref if not ref or "." in ref else f"{module}.{ref}"


def _depends(files: Mapping[str, bytes]) -> list[str]:
    import ast

    try:
        man = ast.literal_eval(files["__manifest__.py"].decode("utf-8"))
        deps = list(man.get("depends") or [])
    except Exception as e:  # noqa: BLE001 - fail closed
        raise GateError("manifest unreadable") from e
    if not all(isinstance(d, str) and MODULE_RE.fullmatch(d) for d in deps):
        raise GateError("manifest depends invalid")
    return deps


def declared_access(
    files: Mapping[str, bytes], module: str
) -> dict[tuple[str, str], tuple[int, int, int, int]] | None:
    """The role spec: (model xmlid, group xmlid) -> (read, write, create, unlink) from the
    module's CSV / XML ir.model.access rows. None when unreadable."""
    import csv
    import io

    out: dict[tuple[str, str], tuple[int, int, int, int]] = {}
    perms = ("perm_read", "perm_write", "perm_create", "perm_unlink")
    try:
        for p, b in files.items():
            if p.endswith("ir.model.access.csv"):
                for row in csv.DictReader(io.StringIO(b.decode("utf-8-sig"))):
                    k = (
                        _norm_ref(row.get("model_id:id") or "", module),
                        _norm_ref(row.get("group_id:id") or "", module),
                    )
                    out[k] = tuple(int(str(row.get(x) or "0").strip() or 0) for x in perms)
            elif p.startswith("security/") and p.endswith(".xml"):
                for rec in ca._parse_xml(b).iter("record"):
                    if rec.get("model") != "ir.model.access":
                        continue
                    f = {x.get("name"): x for x in rec.findall("field")}
                    k = (
                        _norm_ref(f["model_id"].get("ref", ""), module) if "model_id" in f else "",
                        _norm_ref(f["group_id"].get("ref", ""), module) if "group_id" in f else "",
                    )
                    vals = []
                    for x in perms:
                        e = f.get(x)
                        v = (e.get("eval") or e.text or "") if e is not None else "0"
                        vals.append(1 if v.strip() in ("1", "True", "true") else 0)
                    out[k] = tuple(vals)
    except Exception:  # noqa: BLE001 - fail closed
        return None
    return out


def access_diff(spec: Mapping, rows: Sequence[Sequence[str]]) -> list[str]:
    """Compare live ir.model.access / ir.rule rows with the declared role spec."""
    bad: list[str] = []
    groups = {g for _, g in spec if g}
    seen = set()
    for r in rows:
        if len(r) != 7:
            bad.append("unreadable access row")
            continue
        kind, model, grp = r[0], r[1], r[2]
        try:
            p = tuple(int(x) for x in r[3:])
        except ValueError:
            bad.append("unreadable access row")
            continue
        if grp in FORBIDDEN_GROUPS:
            bad.append(f"{kind}:{model} grants {grp}")
        elif kind == "a":
            if not grp:
                bad.append(f"access row on {model} with no group")
            elif grp not in groups:
                bad.append(f"access row on {model} for undeclared group {grp}")
            elif spec.get((model, grp)) != p:
                bad.append(f"access {model}/{grp} rights {p} != spec {spec.get((model, grp))}")
            seen.add((model, grp))
        elif kind == "r" and grp and grp not in groups:
            bad.append(f"record rule on {model} for undeclared group {grp}")
    for k in spec:
        if k not in seen:
            bad.append(f"declared access {k[0]}/{k[1] or '-'} not present")
    return bad


def _snapshot(rows: Sequence[Sequence[str]] | None):
    if rows is None:
        return None
    cols, counts = set(), {}
    for r in rows:
        if len(r) != 3:
            return None
        if r[0] == "c":
            cols.add((r[1], r[2]))
        elif r[0] == "n":
            counts[r[1]] = int(r[2])
        else:
            return None
    if set(counts) != set(COUNT_TABLES) or not cols:
        return None
    return cols, counts


def snapshot_diff(s0, s1) -> list[str]:
    """Anything present after uninstall that was not there before install."""
    (c0, n0), (c1, n1) = s0, s1
    t0 = {t for t, _ in c0}
    new_tables = sorted({t for t, _ in c1} - t0)
    new_cols = sorted(f"{t}.{c}" for t, c in c1 - c0 if t in t0)
    bad = []
    if new_tables:
        bad.append(f"tables left: {', '.join(new_tables[:10])}")
    if new_cols:
        bad.append(f"columns left: {', '.join(new_cols[:10])}")
    for t in COUNT_TABLES:
        if n1.get(t, 0) > n0.get(t, 0):
            bad.append(f"{n1[t] - n0[t]} {t} row(s) left")
    return bad


# ---------------------------------------------------------------- gate


class _Sandbox:
    def __init__(
        self,
        runner: Runner,
        version: int,
        module: str,
        tmp_root: str,
        step_timeout: int = STEP_TIMEOUT,
    ) -> None:
        import secrets

        self.r, self.v, self.mod, self.timeout = runner, version, module, step_timeout
        self.tag = tag = uuid.uuid4().hex[:12]
        self.net, self.pg = f"ingate-{tag}-net", f"ingate-{tag}-pg"
        nonce = secrets.token_hex(8)  # per-run database names, unknown before the run
        self.db_main, self.db_upg = f"gate_{nonce}", f"gateu_{nonce}"
        self.work = tempfile.mkdtemp(prefix="ingate-", dir=tmp_root)
        self.up = False
        self.n = 0
        self.started: list[str] = []

    def addons(self, label: str, files: Mapping[str, bytes]) -> str:
        root = Path(self.work) / label
        for p, b in files.items():
            dst = root / self.mod / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b)
        return str(root)

    def start(self) -> None:
        r = self.r.run(["docker", "network", "create", "--internal", self.net], timeout=60)
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
                *PG_HARDEN,
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
        import time

        for _ in range(60):
            if (
                self.r.run(["docker", "exec", self.pg, "pg_isready", "-U", "odoo"], timeout=10).rc
                == 0
            ):
                return
            time.sleep(1)
        raise GateError("sandbox database not ready")

    def odoo(
        self, addons: str, db: str, sub: str, *args: str, stdin: str | None = None
    ) -> RunResult:
        self.n += 1
        name = f"ingate-{self.tag}-o{self.n}"
        self.started.append(name)
        argv = [
            "docker",
            "run",
            "--rm",
            *(["-i"] if stdin is not None else []),
            "--name",
            name,
            "--network",
            self.net,
            *ODOO_HARDEN,
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
        res = self.r.run(argv, stdin=stdin, timeout=self.timeout)
        if res.rc == -1:  # runner timeout/error: the docker CLI died, the container may not
            self.r.run(["docker", "rm", "-f", name], timeout=60)
        return res

    def psql(self, db: str, sql: str) -> list[list[str]] | None:
        """Independent read: psql in the postgres container (no module code on any path)."""
        r = self.r.run(
            ["docker", "exec", "-i", self.pg, "psql", "-U", "odoo", "-d", db, *_PSQL_TAIL],
            stdin=sql,
            timeout=120,
        )
        if r.rc != 0:
            return None
        return [ln.split("|") for ln in r.output.splitlines() if ln.strip()]

    def state(self, db: str) -> str | None:
        rows = self.psql(db, sql_state(self.mod))
        return rows[0][0] if rows and len(rows) == 1 and len(rows[0]) == 1 else None

    def close(self) -> None:
        if self.up:
            self.r.run(["docker", "rm", "-f", *self.started, self.pg], timeout=120)
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
    step_timeout: int = STEP_TIMEOUT,
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
    _depends(files)
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
            sb = _Sandbox(runner, version, module, tmp_root, step_timeout)
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


def _stats_re(db: str) -> re.Pattern[str]:
    # Only a real log line for this run's (random) database counts; module-printed text with
    # another prefix is ignored. In-process output is still module-influenced (see gaps).
    return re.compile(
        rf"^\S+ \S+ \d+ (?:INFO|ERROR|WARNING) {re.escape(db)} odoo\.tests\.(?:result|stats): "
        r"(\d+) failed, (\d+) error\(s\) of (\d+) tests",
        re.M,
    )


def _odoo_ok(res: RunResult, sb: _Sandbox | None = None, db: str = "") -> tuple[bool, str]:
    if res.rc != 0:
        return False, f"odoo exited {res.rc}"
    if _ERR.search(res.output):
        return False, f"{len(_ERR.findall(res.output))} ERROR/CRITICAL log line(s)"
    if _NOT_LOADED.search(res.output):
        return False, "module did not load"
    if sb is not None:
        st = sb.state(db)
        if st != "installed":
            return False, f"module state {st or 'unreadable'} (read from the database)"
    return True, ""


def _sandbox_checks(sb: _Sandbox, files, old, version, checks: dict[str, Check]) -> None:
    mod, db = sb.mod, sb.db_main
    new_dir = sb.addons("new", files)
    deps = _depends(files)
    # (1) baseline database with only base + declared depends, then a schema snapshot
    res = sb.odoo(
        new_dir,
        db,
        "",
        "-i",
        ",".join(dict.fromkeys(["base", *deps])),
        "--stop-after-init",
        "--without-demo=all",
    )
    s0 = _snapshot(sb.psql(db, SQL_SCHEMA)) if res.rc == 0 else None
    if s0 is None:
        for c in ("install", "tests", "access", "uninstall"):
            checks[c] = Check(UNVERIFIED, "baseline database failed", _tail(res.output))
    else:
        # (2) install, confirmed from the database, not from logs
        res = sb.odoo(new_dir, db, "", "-i", mod, "--stop-after-init", "--without-demo=all")
        ok, why = _odoo_ok(res, sb, db)
        warns = len(_WARN.findall(res.output))
        checks["install"] = Check(
            PASS if ok else FAIL,
            why or f"installed; {warns} warning line(s)",
            _tail(res.output),
            [] if ok else _classify(res.output, version),
        )
    if checks.get("install") and checks["install"].status == FAIL:
        for c in ("tests", "access", "uninstall"):
            checks[c] = Check(SKIPPED, "install failed")
    elif s0 is not None:
        # (3) the module's own tests
        every, access = _test_methods(files)
        res = sb.odoo(
            new_dir,
            db,
            "",
            "-u",
            mod,
            "--test-enable",
            "--test-tags",
            f"/{mod}",
            "--stop-after-init",
        )
        stats = [tuple(map(int, m)) for m in _stats_re(db).findall(res.output)]
        failed = sum(s[0] for s in stats)
        errors = sum(s[1] for s in stats)
        ran = sum(s[2] for s in stats)
        ok3, why3 = _odoo_ok(res, sb, db)
        if not every:
            checks["tests"] = Check(FAIL, "module has no tests")
        elif not stats:
            checks["tests"] = Check(
                UNVERIFIED if ok3 else FAIL,
                f"no test result line for this run {why3}".strip(),
                _tail(res.output),
            )
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
        # (5) role access: module's access tests AND live rows compared with the role spec
        roles = _declared_roles(files, mod)
        spec = declared_access(files, mod)
        if roles < 0 or spec is None:
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
            rows = sb.psql(db, sql_access(mod))
            bad = access_diff(spec, rows) if rows is not None else None
            if bad is None:
                checks["access"] = Check(UNVERIFIED, "live access rows unreadable")
            elif bad:
                checks["access"] = Check(FAIL, "; ".join(bad[:10]))
            elif missing:
                checks["access"] = Check(UNVERIFIED, f"not seen in log: {', '.join(missing[:10])}")
            else:
                checks["access"] = Check(
                    PASS,
                    f"{len(access)} access test(s) passed; {len(rows)} live row(s) match the "
                    f"spec ({len(spec)} declared)",
                )
        # (6) uninstall leaves nothing behind: state and schema read from the database
        res = sb.odoo(new_dir, db, "shell", "--no-http", stdin=_UNINSTALL_SCRIPT)
        st = sb.state(db)
        s1 = _snapshot(sb.psql(db, SQL_SCHEMA))
        bad = []
        if res.rc != 0:
            bad.append(f"uninstall run exited {res.rc}")
        if st != "uninstalled":
            bad.append(f"state after {st or 'unreadable'}")
        if s1 is None and not bad:
            checks["uninstall"] = Check(UNVERIFIED, "post-uninstall state unreadable")
        else:
            if s1 is not None:
                bad += snapshot_diff(s0, s1)
            checks["uninstall"] = Check(
                FAIL if bad else PASS,
                "; ".join(bad) or "clean: no tables, columns or records left (database diff)",
                _tail(res.output) if bad else "",
                _classify(res.output, version) if bad else [],
            )
    # (4) upgrade path
    if old is None:
        checks["upgrade"] = Check(NA, "no prior version")
    else:
        old_dir = sb.addons("old", old)
        r1 = sb.odoo(old_dir, sb.db_upg, "", "-i", mod, "--stop-after-init", "--without-demo=all")
        ok1, why1 = _odoo_ok(r1, sb, sb.db_upg)
        if not ok1:
            checks["upgrade"] = Check(
                FAIL,
                f"prior version did not install: {why1}",
                _tail(r1.output),
                _classify(r1.output, version),
            )
        else:
            r2 = sb.odoo(new_dir, sb.db_upg, "", "-u", mod, "--stop-after-init")
            ok2, why2 = _odoo_ok(r2, sb, sb.db_upg)
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
