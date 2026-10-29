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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.bots import code_audit as ca
from app.bots import debug_notes as dn
from app.bots.versioncaps import caps

SCHEMA = "module-test-gate/2"
VERSIONS = (17, 18, 19, 20)
SANDBOX = "docker-local"  # the only sandbox endpoint the gate accepts
IMAGES = {v: f"odoo:{v}" for v in VERSIONS}
PG_IMAGE = "postgres:16"
KEY_ENV = "INGENIUM_GATE_KEY"
CHECKS = ("audit", "install", "smoke", "upgrade", "access", "uninstall", "tests")
# Only externally controlled checks decide: state read by the trusted reader, leftover and
# access diffs, and gate-written smoke tests run from a separate harness container. The
# module's own test results (and the canaries next to them) run inside the module's process,
# so they are recorded as an advisory signal and never make or break gate_passed.
ADVISORY = ("tests",)
DECIDING = tuple(c for c in CHECKS if c not in ADVISORY)
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
    "module-test-gate: the sandbox is detectable by the module under test (empty database, no "
    "outbound network, container limits, the harness re-run); a module can behave differently "
    "in the gate than on a client database. Names are neutral, but this is not a guarantee: "
    "code_audit findings and human diff review stay required, and the first install targets a "
    "staging clone.",
    "module-test-gate: the module's own test results (stock log line, harness report, "
    "canaries) come from the module's own process and can in principle be forged, so they are "
    "advisory and never decide gate_passed. Deciding checks are install/upgrade/uninstall state "
    "read by the trusted reader, the leftover and access diffs, and gate-written smoke tests.",
    "module-test-gate: smoke tests run from a separate harness container (no mounts, no "
    "database credentials) over JSON-RPC, but the server answering them runs the module's "
    "code, so a module could fake its own RPC answers (e.g. a create that reports success). "
    "Smoke covers CRUD on owned models, owned views, actions, menus, cron/automation model "
    "references and the spec'd role permissions only where values can be built; anything it "
    "cannot exercise is UNVERIFIED, not PASS. Smoke role checks confirm granted permissions "
    "only; extra grants are caught by the trusted access-row diff, not by smoke.",
    "module-test-gate: live hostile fixtures re-run on odoo:17 and odoo:19 only; 18 and 20 "
    "must be run live before the switch.",
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
_ENV_KEYS = frozenset({"HOST", "USER", "PASSWORD", "POSTGRES_USER", "POSTGRES_PASSWORD"})
# Database roles: the image superuser only sets the sandbox up; Odoo (and so the module) runs as
# a role with no superuser, createdb, createrole, replication or bypassrls; every read the gate
# trusts uses a separate read-only role with a pinned search_path and schema-qualified names.
PG_ADMIN, APP_ROLE, READ_ROLE = "postgres", "odoo", "reader"
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
# Smoke harness container: gate code only (no module files, no database credentials), same
# containment except a writable root so its report can be read back with docker cp after it
# exits (docker cp cannot read tmpfs).
HARNESS_HARDEN = tuple(f for f in ODOO_HARDEN if f != "--read-only")
_RUN_FLAGS = frozenset(ODOO_HARDEN + PG_HARDEN)
_ODOO_FLAGS = frozenset(
    {
        "--stop-after-init",
        "--without-demo=all",
        "--test-enable",
        "--no-http",
        "--max-cron-threads=0",
        "--no-database-list",
    }
)
DB_RE = re.compile(r"db[us]?_[0-9a-f]{16}")
_HFILE_RE = re.compile(r"/var/tmp/[0-9a-f]{16}\.(?:json|ready)")
_NET_RE = re.compile(r"ws-[0-9a-f]{12}-net")
_RES_RE = re.compile(r"r[0-9a-f]{16}")  # harness result dir: random, unknown to the module
_PSQL_TAIL = ["-q", "-At", "-v", "ON_ERROR_STOP=1"]


def _sandbox_name(v: str) -> bool:
    return bool(re.fullmatch(r"ws-[0-9a-f]{12}(-pg|-net|-o\d{1,3}|-s1|-h1)?", v))


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
    if argv[1] == "cp":
        src, _, path = (argv[2] if len(argv) == 4 else "").partition(":")
        dst = argv[3] if len(argv) == 4 else ""
        if (
            not re.fullmatch(r"ws-[0-9a-f]{12}-h1", src)
            or not _HFILE_RE.fullmatch(path)
            or not path.endswith(".json")
            or ".." in dst.split("/")
            or os.path.realpath(os.path.dirname(dst)) != os.path.dirname(dst)
            or not dst.startswith(tmp_root.rstrip("/") + "/ws-")
        ):
            raise GateError("cp only the harness report into the sandbox work dir")
        return
    if argv[1] == "exec":
        if (
            len(argv) == 6
            and re.fullmatch(r"ws-[0-9a-f]{12}-h1", argv[2])
            and argv[3:5] == ["test", "-e"]
            and _HFILE_RE.fullmatch(argv[5])
        ):
            return
        pg = re.compile(r"ws-[0-9a-f]{12}-pg")
        if (
            len(argv) == 8
            and pg.fullmatch(argv[2])
            and argv[3:] == ["pg_isready", "-h", "127.0.0.1", "-U", PG_ADMIN]
        ):
            return
        if (
            len(argv) == 9 + len(_PSQL_TAIL)
            and argv[2] == "-i"
            and pg.fullmatch(argv[3])
            and argv[9:] == _PSQL_TAIL
            and (
                (argv[4:8] == ["psql", "-U", READ_ROLE, "-d"] and DB_RE.fullmatch(argv[8]))
                or argv[4:9] == ["psql", "-U", PG_ADMIN, "-d", "postgres"]
                or (argv[4:8] == ["psql", "-U", PG_ADMIN, "-d"] and DB_RE.fullmatch(argv[8]))
            )
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
    i, net, name, host, mounts, res, seen, envs = 2, None, None, None, 0, 0, set(), 0
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
            envs += 1
            if k not in _ENV_KEYS:
                raise GateError("environment variable not allowed")
            if k == "HOST":
                host = v
            if (k == "USER" and v != APP_ROLE) or (k == "POSTGRES_USER" and v != PG_ADMIN):
                raise GateError("database role not allowed")
        else:
            src, _, rest = val.partition(":")
            base = src.rsplit("/", 1)[-1]
            if _RES_RE.fullmatch(base) and rest == f"/var/tmp/{base}:rw":
                rest, res = "/mnt/extra-addons:ro", res + 1  # harness result dir, same checks
                mounts -= 1
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
    tag = net[3:15]
    if image == PG_IMAGE:
        if name != f"ws-{tag}-pg" or mounts or res or argv[img_at + 1 :]:
            raise GateError("sandbox database container malformed")
        if not all(f in seen for f in PG_HARDEN):
            raise GateError("sandbox database missing resource limits")
        return
    if name == f"ws-{tag}-h1":
        if (
            argv[img_at + 1 :] != ["python3", "-"]
            or envs
            or mounts
            or res
            or "-i" not in seen
            or "--rm" in seen
            or "--read-only" in seen
            or not all(f in seen for f in HARNESS_HARDEN)
        ):
            raise GateError("smoke harness container malformed")
        return
    if name == f"ws-{tag}-s1":
        if "-d" not in seen or "--rm" not in seen or "--stop-after-init" in argv[img_at:]:
            raise GateError("smoke server container malformed")
    elif not re.fullmatch(rf"ws-{tag}-o\d{{1,3}}", name):
        raise GateError("odoo container name must match the sandbox")
    if host != f"ws-{tag}-pg":
        raise GateError("HOST must be this sandbox's database")
    if mounts != 1 or res > 1:
        raise GateError("exactly one addons mount and at most one result mount")
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
    """True only for an untampered, signed report where every deciding check passed for exactly
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
        for name in DECIDING:  # the module's own tests are advisory (see ADVISORY)
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


# Uninstall runs inside the module's own process, so nothing it prints is trusted: the result
# is read afterwards from the sandbox database by psql in the postgres container, which never
# has the module on any path.
def uninstall_script(module: str) -> str:
    assert MODULE_RE.fullmatch(module)
    return (
        f"env['ir.module.module'].search([('name', '=', {module!r})])"
        ".button_immediate_uninstall()\n"
        "env.cr.commit()\n"
    )


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
# rows compared by id (not count) before install and after uninstall; optional ones may be absent
ID_TABLES = COUNT_TABLES + (
    "ir_config_parameter",
    "ir_sequence",
    "ir_attachment",
    "mail_template",
    "res_users",
    "res_partner",
)
# Superuser-owned event trigger in each sandbox database: any function the module creates with
# SECURITY DEFINER or its own settings, and any ALTER DEFAULT PRIVILEGES, is logged to a table
# the app role cannot write or drop, so creating one and dropping it before the uninstall
# snapshot still shows. The app role cannot disable event triggers (not owner, not superuser).
DDL_WATCH = """
CREATE SCHEMA gate_audit AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA gate_audit FROM PUBLIC;
CREATE TABLE gate_audit.ddl (tag text NOT NULL, ident text NOT NULL);
CREATE FUNCTION gate_audit.ddl_log() RETURNS event_trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog AS $w$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM pg_catalog.pg_event_trigger_ddl_commands() LOOP
    IF r.command_tag = 'ALTER DEFAULT PRIVILEGES' OR (
       r.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass AND EXISTS (
         SELECT 1 FROM pg_catalog.pg_proc p
         WHERE p.oid = r.objid AND (p.prosecdef OR p.proconfig IS NOT NULL))) THEN
      INSERT INTO gate_audit.ddl VALUES (r.command_tag, COALESCE(r.object_identity, '?'));
    END IF;
  END LOOP;
END $w$;
CREATE EVENT TRIGGER gate_ddl ON ddl_command_end EXECUTE FUNCTION gate_audit.ddl_log();
"""

# every read the gate trusts: pinned search_path, then a settings probe (must be 0 rows)
# Trusted reads use NUL field and RS (0x1e) record separators so values containing "|" or
# newlines cannot shift columns; psql ends each result set with "\n". Exactly one statement
# follows the prefix, so the output is "k0\0<n>\n" + records joined by RS + "\n".
_PSET = "\\pset fieldsep_zero\n\\pset recordsep '\\036'\n"
_READ_PREFIX = _PSET + (
    "SET search_path = pg_catalog, public;\n"
    "SELECT 'k0', count(*) FROM pg_catalog.pg_db_role_setting;\n"
)
_NS = (
    "{n}.nspname NOT IN ('pg_catalog', 'information_schema') "
    "AND {n}.nspname NOT LIKE 'pg\\_toast%' AND {n}.nspname NOT LIKE 'pg\\_temp%'"
)
SQL_TABLES = (
    "-- gate:tables\nSELECT c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
    "ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname IN ("
    + ", ".join(f"'{t}'" for t in ID_TABLES)
    + ");\n"
)


# Other database objects a module could leave behind or use to keep a foothold, compared as sets
# of (kind:name, detail). ACLs carry their text, so a changed grant is a new row.
_SQL_EXTRA = (
    "UNION ALL SELECT 'x', 'trigger:' || cn.nspname || '.' || c.relname || '.' || t.tgname, '' "
    "FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid "
    "JOIN pg_catalog.pg_namespace cn ON cn.oid = c.relnamespace "
    "WHERE NOT t.tgisinternal AND {ns_c}\n"
    "UNION ALL SELECT 'x', 'rule:' || cn.nspname || '.' || c.relname || '.' || r.rulename, '' "
    "FROM pg_catalog.pg_rewrite r JOIN pg_catalog.pg_class c ON c.oid = r.ev_class "
    "JOIN pg_catalog.pg_namespace cn ON cn.oid = c.relnamespace "
    "WHERE r.rulename <> '_RETURN' AND {ns_c}\n"
    "UNION ALL SELECT 'x', 'policy:' || cn.nspname || '.' || c.relname || '.' || p.polname, '' "
    "FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid = p.polrelid "
    "JOIN pg_catalog.pg_namespace cn ON cn.oid = c.relnamespace WHERE {ns_c}\n"
    "UNION ALL SELECT 'x', 'type:' || n.nspname || '.' || t.typname, t.typtype::text "
    "FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace "
    "WHERE t.typrelid = 0 AND t.typcategory <> 'A' AND {ns}\n"
    "UNION ALL SELECT 'x', 'cast:' || k.castsource::pg_catalog.regtype::text || '->' "
    "|| k.casttarget::pg_catalog.regtype::text, '' FROM pg_catalog.pg_cast k "
    "WHERE k.oid >= 16384\n"
    "UNION ALL SELECT 'x', 'operator:' || n.nspname || '.' || o.oprname, "
    "o.oprleft::pg_catalog.regtype::text || ',' || o.oprright::pg_catalog.regtype::text "
    "FROM pg_catalog.pg_operator o JOIN pg_catalog.pg_namespace n ON n.oid = o.oprnamespace "
    "WHERE {ns}\n"
    "UNION ALL SELECT 'x', 'extension:' || e.extname, e.extversion FROM pg_catalog.pg_extension e\n"
    "UNION ALL SELECT 'x', 'grant:' || n.nspname || '.' || c.relname, c.relacl::text "
    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relacl IS NOT NULL AND {ns}\n"
    "UNION ALL SELECT 'x', 'grant:schema ' || n.nspname, n.nspacl::text "
    "FROM pg_catalog.pg_namespace n WHERE n.nspacl IS NOT NULL AND {ns}\n"
    "UNION ALL SELECT 'x', 'grant:function ' || n.nspname || '.' || p.proname, p.proacl::text "
    "FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
    "WHERE p.proacl IS NOT NULL AND {ns}\n"
    "UNION ALL SELECT 'x', 'grant:default ' || d.defaclrole::pg_catalog.regrole::text || ' ' "
    "|| d.defaclobjtype::text, d.defaclacl::text FROM pg_catalog.pg_default_acl d\n"
)


def sql_schema(tables: Sequence[str]) -> str:
    """Every schema, relation (all relkinds incl. sequences), column and function outside the
    catalogs, plus the row ids of the given public tables."""
    assert all(t in ID_TABLES for t in tables)
    ns = _NS.format(n="n")
    rel = "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace"
    return (
        "-- gate:schema\n"
        f"SELECT 's', n.nspname, '' FROM pg_catalog.pg_namespace n WHERE {ns}\n"
        f"UNION ALL SELECT 'k', n.nspname || '.' || c.relname, c.relkind::text {rel} WHERE {ns}\n"
        "UNION ALL SELECT 'c', n.nspname || '.' || c.relname, a.attname "
        f"FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid = a.attrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        f"WHERE a.attnum > 0 AND NOT a.attisdropped AND {ns}\n"
        "UNION ALL SELECT 'f', n.nspname || '.' || p.proname, "
        "pg_catalog.pg_get_function_identity_arguments(p.oid) FROM pg_catalog.pg_proc p "
        f"JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace WHERE {ns}\n"
        "UNION ALL SELECT 'o', l.oid::text, '' FROM pg_catalog.pg_largeobject_metadata l\n"
        "UNION ALL SELECT 'd', w.tag, w.ident FROM gate_audit.ddl w\n"
        + _SQL_EXTRA.format(ns=ns, ns_c=_NS.format(n="cn"))
        + "".join(
            f"UNION ALL SELECT 'i', '{t}', COALESCE(pg_catalog.string_agg(id::text, ',' "
            f"ORDER BY id), '') FROM public.{t}\n"
            for t in tables
        )
        + ";\n"
    )


FORBIDDEN_GROUPS = frozenset({"base.group_public", "base.group_portal"})


def sql_state(module: str) -> str:
    assert MODULE_RE.fullmatch(module)
    return f"-- gate:state\nSELECT state FROM public.ir_module_module WHERE name = '{module}';\n"


SECVALS_GUARDED = (
    "ir.model.access",
    "ir.rule",
    "res.groups",
    "res.users",
    "ir.config_parameter",
    "ir.cron",
)


def sql_secvals(module: str, max_uid: int | None = None) -> str:
    """-- gate:secvals: a VALUE fingerprint of every access row, record rule and group (with its
    implied groups and its members up to max_uid), each flagged when the module owns it by xml
    id; 'U' carries the highest user id; 'F' lists module xml ids pointing at a record another
    module also names. Audit columns (create/write uid/date) are left out so a no-op rewrite is
    not a change. 4 fields: kind, id, md5, own."""
    assert MODULE_RE.fullmatch(module)
    mu = "" if max_uid is None else f" AND x.uid <= {int(max_uid)}"
    strip = "- 'write_date' - 'write_uid' - 'create_date' - 'create_uid'"

    def own(model: str, ref: str) -> str:
        return (
            f"(EXISTS (SELECT 1 FROM public.ir_model_data d WHERE d.module = '{module}' "
            f"AND d.model = '{model}' AND d.res_id = {ref}))::int::text"
        )

    guarded = ", ".join(f"'{m}'" for m in SECVALS_GUARDED)
    return (
        "-- gate:secvals\n"
        f"SELECT 'A', a.id::text, md5((to_jsonb(a) {strip})::text), "
        f"{own('ir.model.access', 'a.id')} FROM public.ir_model_access a\n"
        "UNION ALL\n"
        f"SELECT 'R', r.id::text, md5((to_jsonb(r) {strip})::text || '|' || COALESCE(("
        "SELECT string_agg(x.group_id::text, ',' ORDER BY x.group_id) FROM public.rule_group_rel x "
        f"WHERE x.rule_group_id = r.id), '')), {own('ir.rule', 'r.id')} FROM public.ir_rule r\n"
        "UNION ALL\n"
        f"SELECT 'G', g.id::text, md5((to_jsonb(g) {strip})::text || '|' || COALESCE(("
        "SELECT string_agg(x.hid::text, ',' ORDER BY x.hid) FROM public.res_groups_implied_rel x "
        "WHERE x.gid = g.id), '') || '|' || COALESCE((SELECT string_agg(x.uid::text, ',' "
        f"ORDER BY x.uid) FROM public.res_groups_users_rel x WHERE x.gid = g.id{mu}), '')), "
        f"{own('res.groups', 'g.id')} FROM public.res_groups g\n"
        "UNION ALL\n"
        # users: every column (the password hash too: compared, never printed: only md5 leaves
        # the database) and group membership; login bookkeeping left out
        f"SELECT 'S', u.id::text, md5((to_jsonb(u) {strip})::text || '|' || COALESCE(("
        "SELECT string_agg(x.gid::text, ',' ORDER BY x.gid) FROM public.res_groups_users_rel x "
        f"WHERE x.uid = u.id), '')), {own('res.users', 'u.id')} FROM public.res_users u"
        f"{'' if max_uid is None else f' WHERE u.id <= {int(max_uid)}'}\n"
        "UNION ALL\n"
        f"SELECT 'P', p.id::text, md5((to_jsonb(p) {strip})::text), "
        f"{own('ir.config_parameter', 'p.id')} FROM public.ir_config_parameter p\n"
        "UNION ALL\n"
        # scheduled actions: run bookkeeping (next/last call, failure counters) left out
        f"SELECT 'C', c.id::text, md5((to_jsonb(c) {strip} - 'nextcall' - 'lastcall' "
        "- 'failure_count' - 'first_failure_date')::text), "
        f"{own('ir.cron', 'c.id')} FROM public.ir_cron c\n"
        "UNION ALL\n"
        "SELECT 'U', COALESCE(max(id), 0)::text, '', '0' FROM public.res_users\n"
        "UNION ALL\n"
        "SELECT 'F', d.model || ':' || d.res_id::text, d.module || '.' || d.name, '1' "
        f"FROM public.ir_model_data d WHERE d.module = '{module}' AND d.model IN ({guarded}) "
        "AND EXISTS (SELECT 1 FROM public.ir_model_data o WHERE o.model = d.model "
        f"AND o.res_id = d.res_id AND o.module <> '{module}')\n"
        "ORDER BY 1, 2;\n"
    )


def _secvals(rows) -> dict | None:
    if rows is None:
        return None
    out: dict = {"v": {}, "own": set(), "f": [], "u": None}
    for k, i, h, o in rows:
        if k in _SECVAL_NAMES:
            out["v"][(k, i)] = h
            if o == "1":
                out["own"].add((k, i))
        elif k == "U":
            out["u"] = int(i) if i.isdigit() else None
        elif k == "F":
            out["f"].append(f"{h} -> {i}")
        else:
            return None
    return out if out["u"] is not None else None


_SECVAL_NAMES = {
    "A": "access row",
    "R": "record rule",
    "G": "group",
    "S": "user",
    "P": "system parameter",
    "C": "scheduled action",
}


def secvals_diff(v0, v1) -> list[str]:
    """Pre-existing access rows, rules and groups the module does not own must keep their
    values (and exist); the module's own xml ids must not name another module's records."""
    bad = [f"module xml id names another module's record: {f}" for f in v1["f"]]
    for key, h in sorted(v0["v"].items()):
        if key in v0["own"] or key in v1["own"]:
            continue
        name = f"{_SECVAL_NAMES[key[0]]} id {key[1]}"
        if key not in v1["v"]:
            bad.append(f"{name} removed")
        elif v1["v"][key] != h:
            bad.append(f"{name} changed")
    return bad


def _secvals_check(sb, db: str, mod: str, v0) -> tuple[str, str]:
    """(status, detail) for stock security values after module code ran in db."""
    if v0 is None:
        return UNVERIFIED, "security values unreadable before install"
    v1 = _secvals(sb.psql(db, sql_secvals(mod, v0["u"]), fields=4))
    if v1 is None:
        return UNVERIFIED, "security values unreadable after install"
    bad = secvals_diff(v0, v1)
    if bad:
        return FAIL, "stock security edited: " + "; ".join(bad[:10])
    return (
        PASS,
        f"{len(v0['v'])} pre-existing security value(s) unchanged",
    )


def sql_access(module: str, after: Mapping[str, int] | None = None) -> str:
    """Live access rows and record rules on the module's models, created by its xml ids, or
    created after the baseline (any id above the baseline maximum, whoever made it)."""
    assert MODULE_RE.fullmatch(module)
    after = after or {}
    ma, mr = int(after.get("ir_model_access", 0)), int(after.get("ir_rule", 0))
    grp = (
        "COALESCE((SELECT d.module || '.' || d.name FROM public.ir_model_data d WHERE "
        "d.model = 'res.groups' AND d.res_id = {g} ORDER BY d.id LIMIT 1), '')"
    )
    mx = (
        "COALESCE((SELECT d.module || '.' || d.name FROM public.ir_model_data d WHERE "
        "d.model = 'ir.model' AND d.res_id = m.id ORDER BY d.id LIMIT 1), m.model)"
    )
    dom = "replace(replace(COALESCE(r.domain_force, ''), E'\\n', ' '), E'\\r', ' ')"
    return (
        "-- gate:access\n"
        # models this module introduces; an inherited stock model also gets a module xmlid,
        # but its stock rows are not the module's (its own rows still match by id/xmlid)
        f"WITH own AS (SELECT d.res_id FROM public.ir_model_data d WHERE d.module = '{module}' "
        "AND d.model = 'ir.model' AND NOT EXISTS (SELECT 1 FROM public.ir_model_data o "
        f"WHERE o.model = 'ir.model' AND o.res_id = d.res_id AND o.module <> '{module}'))\n"
        f"SELECT 'a', {mx}, {grp.format(g='a.group_id')}, a.perm_read::int, "
        "a.perm_write::int, a.perm_create::int, a.perm_unlink::int, ''\n"
        "FROM public.ir_model_access a JOIN public.ir_model m ON m.id = a.model_id\n"
        f"WHERE a.active AND (a.model_id IN (SELECT res_id FROM own) OR a.id > {ma} OR a.id IN "
        f"(SELECT res_id FROM public.ir_model_data WHERE module = '{module}' "
        "AND model = 'ir.model.access'))\n"
        f"UNION ALL SELECT 'r', {mx}, {grp.format(g='rg.group_id')}, r.perm_read::int, "
        f"r.perm_write::int, r.perm_create::int, r.perm_unlink::int, {dom}\n"
        "FROM public.ir_rule r JOIN public.ir_model m ON m.id = r.model_id\n"
        "LEFT JOIN public.rule_group_rel rg ON rg.rule_group_id = r.id\n"
        f"WHERE r.active AND (r.model_id IN (SELECT res_id FROM own) OR r.id > {mr} OR r.id IN "
        f"(SELECT res_id FROM public.ir_model_data WHERE module = '{module}' "
        "AND model = 'ir.rule'));\n"
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


def _dom(d: str) -> str:
    return re.sub(r"\s+", "", d or "").replace('"', "'")


_TRUE_DOMAINS = frozenset({"", "[]", "()", "None", "False", "True", "[(1,'=',1)]", "[(1,'=',1),]"})


def _always_true(d: str) -> bool:
    n = _dom(d)
    return n in _TRUE_DOMAINS or "(1,'=',1)" in n or "(0,'=',0)" in n


def role_spec_from(spec: Any, module: str) -> dict[str, dict] | None:
    """The req2mod role spec (not the module's own files): access (model, group) -> rights and
    record rules (model, group) -> normalised domain. None when unreadable."""
    try:
        acc = {
            (_norm_ref(a.model, module), _norm_ref(a.group, module)): (
                int(a.perm_read),
                int(a.perm_write),
                int(a.perm_create),
                int(a.perm_unlink),
            )
            for a in spec.access_rules
        }
        rules = {}
        for r in spec.record_rules:
            for gx in list(r.group_xml_ids) or [""]:
                rules[(_norm_ref(r.model_xml_id, module), _norm_ref(gx, module))] = _dom(
                    r.domain_force
                )
        return {"access": acc, "rules": rules}
    except Exception:  # noqa: BLE001 - fail closed
        return None


def access_diff(role_spec: Mapping, rows: Sequence[Sequence[str]]) -> list[str]:
    """Compare live ir.model.access / ir.rule rows with the req2mod role spec. Anything not in
    the spec fails, as does any global rule or always-true domain."""
    bad: list[str] = []
    spec, rspec = role_spec.get("access") or {}, role_spec.get("rules") or {}
    groups = {g for _, g in spec if g} | {g for _, g in rspec if g}
    seen, rseen = set(), set()
    for r in rows:
        if len(r) != 8:
            bad.append("unreadable access row")
            continue
        kind, model, grp, dom = r[0], r[1], r[2], r[7]
        try:
            p = tuple(int(x) for x in r[3:7])
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
        elif kind == "r":
            if not grp:
                bad.append(f"global record rule on {model}")
            elif _always_true(dom):
                bad.append(f"always-true record rule on {model} for {grp}")
            elif (model, grp) not in rspec:
                bad.append(f"record rule on {model} for {grp} not in the role spec")
            elif rspec[(model, grp)] != _dom(dom):
                bad.append(f"record rule on {model} for {grp} differs from the role spec")
            rseen.add((model, grp))
        else:
            bad.append("unreadable access row")
    for k in spec:
        if k not in seen:
            bad.append(f"declared access {k[0]}/{k[1] or '-'} not present")
    for k in rspec:
        if k not in rseen:
            bad.append(f"declared record rule {k[0]}/{k[1] or '-'} not present")
    return bad


def _snapshot(rows: Sequence[Sequence[str]] | None):
    if rows is None:
        return None
    snap: dict[str, Any] = {
        "s": set(),
        "k": set(),
        "c": set(),
        "f": set(),
        "o": set(),
        "d": set(),
        "x": set(),
        "i": {},
    }
    for r in rows:
        if len(r) != 3 or r[0] not in snap:
            return None
        if r[0] == "i":
            try:
                snap["i"][r[1]] = {int(x) for x in r[2].split(",") if x}
            except ValueError:
                return None
        else:
            snap[r[0]].add((r[1], r[2]))
    if not snap["k"] or not set(COUNT_TABLES) <= set(snap["i"]):
        return None
    return snap


_KIND = {"r": "table", "S": "sequence", "v": "view", "m": "matview", "i": "index", "f": "foreign"}


def snapshot_diff(s0, s1) -> list[str]:
    """Anything present after uninstall that was not there before install (compared by name and
    by row id, never by count)."""
    bad = []
    new_s = sorted(n for n, _ in s1["s"] - s0["s"])
    if new_s:
        bad.append(f"schemas left: {', '.join(new_s[:10])}")
    rel0 = {n for n, _ in s0["k"]}
    new_k = sorted(s1["k"] - s0["k"])
    by_kind: dict[str, list[str]] = {}
    for n, k in new_k:
        by_kind.setdefault(_KIND.get(k, f"relkind {k}"), []).append(n)
    for kind, names in sorted(by_kind.items()):
        bad.append(f"{kind}s left: {', '.join(names[:10])}")
    new_c = sorted(f"{t}.{c}" for t, c in s1["c"] - s0["c"] if t in rel0)
    if new_c:
        bad.append(f"columns left: {', '.join(new_c[:10])}")
    new_f = sorted(f"{n}({a})" for n, a in s1["f"] - s0["f"])
    if new_f:
        bad.append(f"functions left: {', '.join(new_f[:10])}")
    new_o = sorted(o for o, _ in s1.get("o", set()) - s0.get("o", set()))
    if new_o:
        bad.append(f"large objects left: {', '.join(new_o[:10])}")
    new_d = sorted(f"{t} {i}" for t, i in s1.get("d", set()) - s0.get("d", set()))
    if new_d:
        bad.append(f"privileged database objects created: {'; '.join(new_d[:5])}")
    x0, x1 = s0.get("x", set()), s1.get("x", set())
    by: dict[str, list[str]] = {}
    for name, det in sorted(x1 - x0):
        k, _, n = name.partition(":")
        by.setdefault(k, []).append(n if k != "grant" else f"{n} {det}")
    for name, det in sorted(x0 - x1):  # a grant revoked or an object altered also counts
        k, _, n = name.partition(":")
        if k == "grant" or (name, det) not in x1 and any(m == name for m, _ in x1):
            by.setdefault(k, []).append(f"{n} (changed)")
    for k, names in sorted(by.items()):
        bad.append(f"{k}s left or changed: {', '.join(names[:10])}")
    for t in sorted(set(s0["i"]) | set(s1["i"])):
        left = s1["i"].get(t, set()) - s0["i"].get(t, set())
        if left:
            ids = ", ".join(map(str, sorted(left)[:10]))
            bad.append(f"{len(left)} {t} row(s) left (ids {ids})")
    return bad


# Module tests are re-run by a harness script the gate supplies: the result class is defined
# after the module is imported, and it writes a JUnit-style report to a random directory mounted
# only for that run. The verdict counts that report against the test methods found in the
# module's source, and the stock run's log line must agree.
_HARNESS = r"""
import threading, unittest, xml.sax.saxutils
import odoo
from odoo.tests import loader
from odoo.tests.common import TransactionCase as GateCase
M, P = {module!r}, {path!r}
CF, CP, CC = {fail!r}, {pas!r}, {cls!r}
class Res(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = []
    def _row(self, t, k):
        i = t.id() if hasattr(t, 'id') else str(t)
        self.rows.append((str(i), k))
    def addSuccess(self, t): self._row(t, 'ok')
    def addFailure(self, t, e): self._row(t, 'failure')
    def addError(self, t, e): self._row(t, 'error')
    def addSkip(self, t, r): self._row(t, 'skipped')
    def addExpectedFailure(self, t, e): self._row(t, 'failure')
    def addUnexpectedSuccess(self, t): self._row(t, 'failure')
    def addSubTest(self, t, s, e):
        if e is not None:
            self._row(t, 'failure')
def c0(self): self.assertEqual(1, 2)
def c1(self): self.assertTrue(False)
def c2(self): self.fail('x')
def c3(self):
    with self.assertRaises(ValueError):
        pass
def c4(self): assert False
def c5(self): self.assertIn(1, ())
def c6(self): self.assertEqual(1, 1)
def canary(base, k):
    # gate-owned base: the module's class (and anything it overrides) is not inherited
    ns = dict(zip(CF, (c0, c1, c2, c3, c4, c5)))
    ns[CP], ns['__module__'] = c6, base.__module__
    c = type(CC + str(k), (GateCase,), ns)
    c.__qualname__ = c.__name__
    return c
def flat(s):
    for t in s:
        if isinstance(t, unittest.TestSuite):
            yield from flat(t)
        else:
            yield t
res = Res()
threading.current_thread().testing = True
odoo.modules.module.current_test = M
k = 0
for pos in ('at_install', 'post_install'):
    suite = loader.make_suite([M], pos)
    S, groups = type(suite), {{}}
    for t in flat(suite):
        groups.setdefault(type(t), []).append(t)
    for cls, tests in groups.items():
        S(tests).run(res)
        k += 1
        c = canary(cls, k)
        S([c(n) for n in (*CF, CP)]).run(res)
odoo.modules.module.current_test = None
with open(P, 'w') as f:
    f.write('<testsuite>')
    for i, r in res.rows:
        f.write('<testcase name=%s result=%s/>' % (
            xml.sax.saxutils.quoteattr(i), xml.sax.saxutils.quoteattr(r)))
    f.write('</testsuite>')
"""
_CANARY_FAILS = 6


@dataclass(frozen=True)
class Canary:
    """Known-answer tests the harness adds per module test class, as subclasses of that class:
    each `fail` test must fail and `pas` must pass. If assertions were neutered in-process the
    must-fail tests pass and the run is refused. Names are random per run."""

    cls: str
    fail: tuple[str, ...]
    pas: str

    @staticmethod
    def new() -> Canary:
        import secrets

        r = lambda: secrets.token_hex(6)  # noqa: E731
        return Canary(
            f"Test{r().capitalize()}",
            tuple(f"test_{r()}" for _ in range(_CANARY_FAILS)),
            f"test_{r()}",
        )


def harness_script(module: str, path: str, canary: Canary | None = None) -> str:
    assert MODULE_RE.fullmatch(module) and re.fullmatch(
        r"/var/tmp/r[0-9a-f]{16}/[0-9a-f]{16}\.xml", path
    )
    cn = canary or Canary.new()
    assert re.fullmatch(r"Test[0-9a-zA-Z]{12}", cn.cls) and len(cn.fail) == _CANARY_FAILS
    assert all(re.fullmatch(r"test_[0-9a-f]{12}", x) for x in (*cn.fail, cn.pas))
    return _HARNESS.format(module=module, path=path, fail=cn.fail, pas=cn.pas, cls=cn.cls)


def read_harness(
    raw: bytes | None, every: set[str], module: str = "", canary: Canary | None = None
) -> tuple[bool, str]:
    """Count the harness report independently: every test method in the source ran and passed,
    nothing failed, errored or was skipped; and every known-answer canary gave its known answer."""
    if raw is None:
        return False, "no harness report"
    if len(raw) > 2_000_000:
        return False, "harness report too large"
    try:
        root = ca._parse_xml(raw)
    except Exception:  # noqa: BLE001 - fail closed
        return False, "harness report unreadable"
    if root.tag != "testsuite":
        return False, "harness report malformed"
    ok, bad = set(), []
    seen: dict[str, dict[str, str]] = {}
    n = 0
    for tc in root.iter("testcase"):
        name, kind = tc.get("name") or "", tc.get("result") or ""
        parts = name.rsplit(".", 2)
        meth, cls = parts[-1], (parts[-2] if len(parts) > 2 else "")
        if module and f".addons.{module}." not in name:
            bad.append(f"{name[:60]}: not this module's test")
        elif canary is not None and cls.startswith(canary.cls):
            seen.setdefault(cls, {})[meth] = kind
        elif kind == "ok":
            n += 1
            ok.add(meth)
        else:
            n += 1
            bad.append(f"{meth}: {kind or '?'}")
    if canary is not None:
        want = {**dict.fromkeys(canary.fail, "failure"), canary.pas: "ok"}
        if not seen:
            return False, "harness: known-answer canaries did not run"
        wrong = [c for c, got in seen.items() if got != want]
        if wrong:
            return False, (
                f"harness: known-answer canary gave the wrong answer in {len(wrong)} test "
                "class(es): assertions or result reporting were tampered with"
            )
    if bad:
        return False, f"harness: {len(bad)} not passed ({'; '.join(bad[:5])})"
    missing = sorted(every - ok)
    if missing:
        return False, f"harness: {len(missing)} test(s) did not run ({', '.join(missing[:5])})"
    return True, f"harness: {n} passed" + (f", {len(seen)} canary class(es) ok" if seen else "")


# ---------------------------------------------------------------- smoke harness
# Gate-written smoke tests. They run in their own container (odoo image, `python3 -`, no
# mounts, no database credentials) against a server container that has the module installed
# in a third database, over JSON-RPC only. The module's code never runs in the harness
# process; the harness writes its report (0600) only after the server is gone, and the gate
# reads it host-side with docker cp.
SMOKE_HARNESS = Path(__file__).resolve().parents[1] / "sandbox_harness" / "smoke.py"
# Reviewed content of the harness. It lives outside app/bots (so the kill_audit raw-RPC ban on
# app/bots stays unconditional); this pin is checked at gate start and again when it is sent.
SMOKE_HARNESS_SHA256 = "8d9ceef39edac5d43db48b2cf51c73098bc8f12484a16dbb2abed61fe6b8a9a8"


def smoke_source() -> str:
    """The harness text, refused unless it is byte-identical to the reviewed pin."""
    raw = SMOKE_HARNESS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SMOKE_HARNESS_SHA256:
        raise GateError("smoke harness changed since review (sha256 mismatch)")
    return raw.decode()


def smoke_script(cfg: Mapping[str, Any]) -> str:
    assert set(cfg) == {"host", "db", "module", "pw", "ready", "out", "roles"}
    assert _HFILE_RE.fullmatch(cfg["ready"]) and _HFILE_RE.fullmatch(cfg["out"])
    assert re.fullmatch(r"ws-[0-9a-f]{12}-s1", cfg["host"]) and DB_RE.fullmatch(cfg["db"])
    src = smoke_source()
    assert src.count("__CFG__") == 1
    return src.replace("__CFG__", repr(json.dumps(dict(cfg))))


_SMOKE_BUCKETS = ("models", "views", "actions", "menus", "crons")


def read_smoke(raw: bytes | None) -> tuple[str, str, dict[str, str]]:
    """Count the smoke report host-side. Returns (status, detail, role results). Fail closed:
    unreadable, errors, any non-ok item -> FAIL; a model that could not be filled -> UNVERIFIED;
    nothing smoked at all -> FAIL."""
    if raw is None:
        return UNVERIFIED, "no smoke report", {}
    try:
        d = json.loads(raw.decode()) if len(raw) < 2_000_000 else None
        assert isinstance(d, dict) and isinstance(d.get("errors"), list)
        buckets = {b: d[b] for b in (*_SMOKE_BUCKETS, "roles")}
        assert all(
            isinstance(v, dict) and all(isinstance(x, str) for x in v.values())
            for v in buckets.values()
        )
    except Exception:  # noqa: BLE001 - fail closed
        return FAIL, "smoke report unreadable", {}
    roles = buckets.pop("roles")
    if d["errors"]:
        return FAIL, "smoke: " + "; ".join(map(str, d["errors"][:5])), roles
    bad = [f"{b} {k}: {v}" for b, items in buckets.items() for k, v in items.items() if v != "ok"]
    n = sum(len(v) for v in buckets.values())
    if not n:
        return FAIL, "smoke: nothing owned to exercise", roles
    if any(not v.startswith("skip:") for v in (x.split(": ", 1)[1] for x in bad)):
        return FAIL, "smoke: " + "; ".join(bad[:8]), roles
    if bad:
        return UNVERIFIED, "smoke: " + "; ".join(bad[:8]), roles
    counts = ", ".join(f"{len(v)} {b}" for b, v in buckets.items() if v)
    return PASS, f"smoke ok: {counts}", roles


_MODEL_RE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*")  # x_asset (no dot) too
_COL_RE = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_LOGIN_RE = re.compile(r"smoke_[0-9]{1,10}")
_SEQ_OK = "true"


def _pos_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and 0 < x < 2**31


def smoke_facts(raw: bytes | None) -> tuple[dict, dict] | None:
    """The harness's own trail (ids it created/kept/unlinked) and role users, strictly typed.
    None = unreadable (fail closed)."""
    try:
        d = json.loads(raw.decode())  # type: ignore[union-attr]
        trail, users = d["trail"], d["role_users"]
        assert isinstance(trail, dict) and isinstance(users, dict)
        for m, t in trail.items():
            assert _MODEL_RE.fullmatch(m) and set(t) == {"kept", "field", "gone"}
            assert _pos_int(t["kept"]) and _pos_int(t["gone"]) and t["kept"] != t["gone"]
            assert t["field"] is None or _COL_RE.fullmatch(t["field"])
        for u in users.values():
            assert set(u) == {"uid", "login", "gid", "model"}
            assert _pos_int(u["uid"]) and _pos_int(u["gid"]) and _LOGIN_RE.fullmatch(u["login"])
            assert _MODEL_RE.fullmatch(u["model"]) and u["login"] == f"smoke_{u['gid']}"
    except Exception:  # noqa: BLE001
        return None
    return trail, users


def sql_smoke_record(model: str, kept: int, field: str | None, gone: int) -> str:
    """-- gate:smokedb: the kept record is there (with the written value), the unlinked one is
    gone, and the id sequence really passed it (it was created). Table must be a plain table."""
    t = model.replace(".", "_")
    assert _COL_RE.fullmatch(t) and _pos_int(kept) and _pos_int(gone)
    written = (
        f'(SELECT count(*) FROM public."{t}" WHERE id = {kept} '
        f"AND position('smoke2' in \"{field}\"::text) > 0)::text"
        if field and _COL_RE.fullmatch(field)
        else "'1'"
    )
    return (
        "-- gate:smokedb\n"
        "SELECT 'm', (SELECT c.relkind::text FROM pg_catalog.pg_class c JOIN "
        "pg_catalog.pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
        f"AND c.relname = '{t}'), "
        f'(SELECT count(*) FROM public."{t}" WHERE id = {kept})::text, {written}, '
        f'(SELECT count(*) FROM public."{t}" WHERE id = {gone})::text, '
        "(pg_catalog.pg_sequence_last_value(pg_catalog.pg_get_serial_sequence("
        f"'public.\"{t}\"', 'id')::regclass) >= {gone})::text;\n"
    )


def sql_smoke_role(uid: int, login: str, gid: int, model: str) -> str:
    """-- gate:smokerole: the role user exists, is active, holds the group (incl. implied
    groups), and the access rows in the database grant it each permission."""
    assert _pos_int(uid) and _pos_int(gid) and _LOGIN_RE.fullmatch(login)
    assert _MODEL_RE.fullmatch(model)
    perms = ", ".join(
        f"coalesce(bool_or(a.perm_{p}), false)::text" for p in ("read", "write", "create", "unlink")
    )
    return (
        "-- gate:smokerole\n"
        "WITH RECURSIVE g(id) AS (SELECT r.gid FROM public.res_groups_users_rel r "
        f"WHERE r.uid = {uid} UNION SELECT i.hid FROM public.res_groups_implied_rel i "
        "JOIN g ON i.gid = g.id) "
        f"SELECT 'u', (SELECT count(*) FROM public.res_users WHERE id = {uid} "
        f"AND login = '{login}' AND active)::text, "
        f"(SELECT count(*) FROM g WHERE id = {gid})::text, {perms} "
        "FROM public.ir_model_access a JOIN public.ir_model m ON m.id = a.model_id "
        f"WHERE m.model = '{model}' AND a.active "
        "AND (a.group_id IS NULL OR a.group_id IN (SELECT id FROM g));\n"
    )


def sql_smoke_scope(module: str) -> str:
    """-- gate:smokescope: every model with a table that the module defines or adds stored
    fields to (inherited stock models included), from the database, not the module's server."""
    assert re.fullmatch(r"[a-z][a-z0-9_]{0,63}", module)
    return (
        "-- gate:smokescope\n"
        "SELECT DISTINCT 's', x.model FROM (SELECT m.model FROM public.ir_model m "
        "JOIN public.ir_model_data d ON d.model = 'ir.model' AND d.res_id = m.id "
        f"WHERE d.module = '{module}' UNION SELECT f.model FROM public.ir_model_fields f "
        "JOIN public.ir_model_data d ON d.model = 'ir.model.fields' AND d.res_id = f.id "
        f"WHERE d.module = '{module}' AND f.store) x "
        "JOIN pg_catalog.pg_class c ON c.relname = replace(x.model, '.', '_') "
        "AND c.relkind = 'r' JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "AND n.nspname = 'public' ORDER BY 2;\n"
    )


def verify_smoke_db(
    psql: Callable[[str, int], list[list[str]] | None],
    raw: bytes | None,
    smoked: Iterable[str],
    roles: list,
    module: str | None = None,
) -> tuple[str, str, dict[str, str]]:
    """Re-read every smoke fact from the smoke database (trusted read-only role). Returns
    (status, detail, per-role 'ok' or reason). Fail closed: missing trail or unreadable -> not
    PASS; a fact the database contradicts -> FAIL."""
    facts = smoke_facts(raw)
    if facts is None:
        return FAIL, "smoke trail unreadable", {}
    trail, users = facts
    bad: list[str] = []
    unread: list[str] = []
    smoked = set(smoked)
    if module is not None:  # scope from the database: defined AND inherited models
        rows = psql(sql_smoke_scope(module), 2)
        if rows is None:
            unread.append("scope")
        else:
            bad += [f"{r[1]}: not smoked" for r in rows if r[1] not in smoked]
    for m in sorted(smoked):
        t = trail.get(m)
        if t is None:
            bad.append(f"{m}: no smoke trail")
            continue
        rows = psql(sql_smoke_record(m, t["kept"], t["field"], t["gone"]), 6)
        if rows is None or len(rows) != 1:
            unread.append(m)
            continue
        _, kind, kept, wrote, gone, seq = rows[0]
        if kind != "r":
            bad.append(f"{m}: not a plain table ({kind or 'missing'})")
        elif kept != "1":
            bad.append(f"{m}: created record not in the database")
        elif wrote != "1":
            bad.append(f"{m}: written value not in the database")
        elif gone != "0":
            bad.append(f"{m}: unlinked record still in the database")
        elif seq != _SEQ_OK:
            bad.append(f"{m}: second record was never created")
    role_db: dict[str, str] = {}
    for m, gr, perms in roles:
        key = f"{m}|{gr}"
        u = users.get(key)
        if u is None:
            role_db[key] = "no role user recorded"
            continue
        rows = psql(sql_smoke_role(u["uid"], u["login"], u["gid"], u["model"]), 7)
        if rows is None or len(rows) != 1:
            role_db[key] = "role rows unreadable"
            continue
        _, exists, member, *got = rows[0]
        if exists != "1" or member != "1":
            role_db[key] = "role user or group membership not in the database"
            continue
        miss = [
            op
            for op, want, g_ in zip(("read", "write", "create", "unlink"), perms, got, strict=False)
            if want and g_ != "true"
        ]
        role_db[key] = "ok" if not miss else "database grants no " + ", ".join(miss)
    if bad:
        return FAIL, "smoke db read-back: " + "; ".join(bad[:8]), role_db
    if unread:
        return UNVERIFIED, "smoke db read-back unreadable: " + ", ".join(unread[:8]), role_db
    return PASS, f"db read-back {len(trail)} model(s)", role_db


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
        self.net, self.pg = f"ws-{tag}-net", f"ws-{tag}-pg"
        nonce = secrets.token_hex(8)  # per-run database names, unknown before the run
        self.db_main, self.db_upg = f"db_{nonce}", f"dbu_{nonce}"
        self.db_smoke = f"dbs_{nonce}"  # smoke tests run here, against a server container
        self.pw = secrets.token_hex(16)  # app role password, never printed
        self.res_dir, self.res_file = f"r{secrets.token_hex(8)}", f"{secrets.token_hex(8)}.xml"
        self.work = tempfile.mkdtemp(prefix="ws-", dir=tmp_root)
        self.up = False
        self.tainted = ""  # set when a read finds database/role settings (search_path, ...)
        self.n = 0
        self.started: list[str] = []

    def addons(self, label: str, files: Mapping[str, bytes]) -> str:
        root = Path(self.work) / label
        for p, b in files.items():
            dst = root / self.mod / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b)
        return str(root)

    def result_mount(self) -> tuple[str, str]:
        d = Path(self.work) / self.res_dir
        d.mkdir(mode=0o777, exist_ok=True)
        d.chmod(0o777)  # the container user writes here; the dir exists for one run only
        return str(d), f"/var/tmp/{self.res_dir}/{self.res_file}"

    def start(self) -> None:
        import secrets

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
                f"POSTGRES_USER={PG_ADMIN}",
                "-e",
                f"POSTGRES_PASSWORD={secrets.token_hex(16)}",
                PG_IMAGE,
            ],
            timeout=120,
        )
        if r.rc != 0:
            raise GateError("sandbox database failed")
        import time

        for _ in range(60):
            # over TCP: the image's init-time server listens on the socket only and then
            # restarts, so a socket probe can pass before the real server is up (r7 flake)
            ready = ["docker", "exec", self.pg, "pg_isready", "-h", "127.0.0.1", "-U", PG_ADMIN]
            if self.r.run(ready, timeout=10).rc == 0:
                break
            time.sleep(1)
        else:
            raise GateError("sandbox database not ready")
        lim = "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        setup = (
            f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{self.pw}' {lim};\n"
            f"CREATE ROLE {READ_ROLE} LOGIN {lim};\n"
            f"GRANT pg_read_all_data TO {READ_ROLE};\n"
            + "".join(
                f"CREATE DATABASE {d} OWNER {APP_ROLE} TEMPLATE template0 ENCODING 'UTF8';\n"
                for d in (self.db_main, self.db_upg, self.db_smoke)
            )
        )
        r = self.admin_sql("postgres", setup)
        if r.rc != 0:
            raise GateError("sandbox roles failed")
        for d in (self.db_main, self.db_upg, self.db_smoke):
            w = self.admin_sql(d, DDL_WATCH)
            if w.rc != 0:
                raise GateError("sandbox ddl watch failed")
        rows = self.psql(
            self.db_main,
            "SELECT rolsuper::int + rolcreatedb::int + rolcreaterole::int + rolreplication::int"
            f" + rolbypassrls::int FROM pg_catalog.pg_roles WHERE rolname = '{APP_ROLE}';\n",
        )
        if rows != [["0"]]:
            raise GateError("odoo role is privileged")

    def odoo(
        self,
        addons: str,
        db: str,
        sub: str,
        *args: str,
        stdin: str | None = None,
        result_dir: str | None = None,
    ) -> RunResult:
        self.n += 1
        name = f"ws-{self.tag}-o{self.n}"
        self.started.append(name)
        res = ["-v", f"{result_dir}:/var/tmp/{self.res_dir}:rw"] if result_dir else []
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
            f"USER={APP_ROLE}",
            "-e",
            f"PASSWORD={self.pw}",
            "-v",
            f"{addons}:/mnt/extra-addons:ro",
            *res,
            IMAGES[self.v],
            "odoo",
            *([sub] if sub else []),
            "-d",
            db,
            *args,
        ]
        res_ = self.r.run(argv, stdin=stdin, timeout=self.timeout)
        if res_.rc == -1:  # runner timeout/error: the docker CLI died, the container may not
            self.r.run(["docker", "rm", "-f", name], timeout=60)
        return res_

    def admin_sql(self, db: str, sql: str) -> RunResult:
        """Superuser SQL is setup-only. Once any odoo container has run (module code may have
        planted triggers, functions or settings), superuser SQL could execute module-controlled
        objects with superuser rights, so it is refused from then on (fail closed)."""
        if self.n > 0:
            raise GateError("superuser SQL after module code")
        argv = ["docker", "exec", "-i", self.pg, "psql", "-U", PG_ADMIN, "-d", db, *_PSQL_TAIL]
        return self.r.run(argv, stdin=sql, timeout=120)

    def psql(self, db: str, sql: str, fields: int = 0) -> list[list[str]] | None:
        """Independent read as the read-only role: psql in the postgres container (no module
        code on any path), search_path pinned, and refused when any database or role setting
        exists (a module could otherwise redirect unqualified names)."""
        r = self.r.run(
            ["docker", "exec", "-i", self.pg, "psql", "-U", READ_ROLE, "-d", db, *_PSQL_TAIL],
            stdin=_READ_PREFIX + sql,
            timeout=120,
        )
        if r.rc != 0:
            return None
        return self._parse(r.output, fields)

    def _parse(self, out: str, fields: int) -> list[list[str]] | None:
        """Fail closed: anything but the exact framing or field count is refused."""
        if out.startswith("k0\x00") and not out.startswith("k0\x000\n"):
            self.tainted = "database or role settings present (e.g. search_path)"
            return None
        if not out.startswith("k0\x000\n"):
            return None
        body = out[len("k0\x000\n") :]
        if not body:
            return []
        if not body.endswith("\n"):
            return None
        rows = [rec.split("\x00") for rec in body[:-1].split("\x1e")]
        if fields and any(len(row) != fields for row in rows):
            return None
        return rows

    def state(self, db: str) -> str | None:
        rows = self.psql(db, sql_state(self.mod))
        return rows[0][0] if rows and len(rows) == 1 and len(rows[0]) == 1 else None

    def snapshot(self, db: str):
        tabs = self.psql(db, SQL_TABLES)
        if tabs is None or any(len(t) != 1 for t in tabs):
            return None
        return _snapshot(self.psql(db, sql_schema([t[0] for t in tabs]), fields=3))

    def smoke(self, addons: str, roles: list) -> bytes | None:
        """Gate-written smoke tests: server container (module code) + harness container (gate
        code only, no mounts, no credentials). Returns the raw report read via docker cp."""
        import secrets
        import threading
        import time

        srv, hn = f"ws-{self.tag}-s1", f"ws-{self.tag}-h1"
        ready, out = (f"/var/tmp/{secrets.token_hex(8)}.{x}" for x in ("ready", "json"))
        self.n += 1  # the server runs module code: no superuser SQL from here on
        self.started += [srv, hn]
        r = self.r.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                srv,
                "--network",
                self.net,
                *ODOO_HARDEN,
                "-e",
                f"HOST={self.pg}",
                "-e",
                f"USER={APP_ROLE}",
                "-e",
                f"PASSWORD={self.pw}",
                "-v",
                f"{addons}:/mnt/extra-addons:ro",
                IMAGES[self.v],
                "odoo",
                "-d",
                self.db_smoke,
                "--max-cron-threads=0",
                "--no-database-list",
            ],
            timeout=120,
        )
        if r.rc != 0:
            return None
        script = smoke_script(
            {
                "host": srv,
                "db": self.db_smoke,
                "module": self.mod,
                "pw": secrets.token_hex(16),
                "ready": ready,
                "out": out,
                "roles": roles,
            }
        )
        argv = ["docker", "run", "-i", "--name", hn, "--network", self.net, *HARNESS_HARDEN]
        done: list[RunResult] = []
        th = threading.Thread(
            target=lambda: done.append(
                self.r.run(
                    [*argv, IMAGES[self.v], "python3", "-"], stdin=script, timeout=self.timeout
                )
            ),
            daemon=True,
        )
        th.start()
        t0 = time.monotonic()
        while th.is_alive() and time.monotonic() - t0 < self.timeout:
            if self.r.run(["docker", "exec", hn, "test", "-e", ready], timeout=30).rc == 0:
                break
            time.sleep(2)
        self.r.run(["docker", "rm", "-f", srv], timeout=120)  # module process gone first
        th.join(self.timeout)
        dst = Path(self.work) / f"smoke-{secrets.token_hex(8)}.json"
        raw = None
        if self.r.run(["docker", "cp", f"{hn}:{out}", str(dst)], timeout=60).rc == 0:
            if dst.is_file() and not dst.is_symlink():
                raw = dst.read_bytes()
        self.r.run(["docker", "rm", "-f", hn], timeout=60)
        return raw

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
    role_spec: Mapping[str, Any] | None = None,
) -> GateReport:
    """Run all checks. Refuses (GateError) on invalid input or a non-sandbox endpoint; every
    other failure is recorded in the report, which then cannot pass. ``role_spec`` is the
    req2mod role spec (see role_spec_from); without it the access check cannot pass."""
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
    smoke_source()  # pinned harness, checked before anything runs
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
            _sandbox_checks(sb, files, old, version, checks, role_spec)
        except Exception as e:  # noqa: BLE001 - fail closed
            msg = str(e) if isinstance(e, GateError) else type(e).__name__
            for c in CHECKS[1:]:
                checks.setdefault(c, Check(UNVERIFIED, f"sandbox error: {msg}"))
        finally:
            if sb is not None:
                if sb.tainted:
                    for c in CHECKS[1:]:
                        prev = checks.get(c)
                        checks[c] = Check(FAIL, sb.tainted, prev.log if prev else "")
                sb.close()
    for c in CHECKS:
        checks.setdefault(c, Check(UNVERIFIED, "not run"))
    ok = all(
        checks[c].status == PASS or (c == "upgrade" and checks[c].status == NA and old is None)
        for c in DECIDING
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
            if f.severity in _BLOCK and not ca.unbaselinable(f.code):
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


def _harness(sb: _Sandbox, new_dir: str, db: str, files, every: set[str]) -> tuple[bool, str, set]:
    """Second, independent test run: harness-owned result class, report at a random path."""
    marks = (sb.res_dir.encode(), sb.res_file.encode())
    if any(m in b for b in files.values() for m in marks):
        return False, "module references the harness result path", set()
    host_dir, path = sb.result_mount()
    cn = Canary.new()
    sb.odoo(
        new_dir,
        db,
        "shell",
        "--no-http",
        "--test-enable",
        "--test-tags",
        f"/{sb.mod}",  # registry load must not run (and commit) other modules' tests
        stdin=harness_script(sb.mod, path, cn),
        result_dir=host_dir,
    )
    f = Path(host_dir) / sb.res_file
    raw = f.read_bytes() if f.is_file() and not f.is_symlink() else None
    shutil.rmtree(host_dir, ignore_errors=True)
    ok, why = read_harness(raw, every, sb.mod, cn)
    passed = set()
    if ok and raw is not None:
        passed = {
            (tc.get("name") or "").rsplit(".", 1)[-1]
            for tc in ca._parse_xml(raw).iter("testcase")
            if tc.get("result") == "ok" and f".{cn.cls}" not in (tc.get("name") or "")
        }
    return ok, why, passed


def _sandbox_checks(
    sb: _Sandbox, files, old, version, checks: dict[str, Check], role_spec=None
) -> None:
    mod, db = sb.mod, sb.db_main
    new_dir = sb.addons("new", files)
    deps = _depends(files)
    # (1) baseline database with only base + declared depends, then a full snapshot
    res = sb.odoo(
        new_dir,
        db,
        "",
        "-i",
        ",".join(dict.fromkeys(["base", *deps])),
        "--stop-after-init",
        "--without-demo=all",
    )
    s0 = sb.snapshot(db) if res.rc == 0 else None
    v0 = _secvals(sb.psql(db, sql_secvals(mod), fields=4)) if s0 is not None else None
    if s0 is None:
        for c in ("install", "smoke", "tests", "access", "uninstall"):
            checks[c] = Check(UNVERIFIED, "baseline database failed", _tail(res.output))
    else:
        # (2) install, confirmed from the database, not from logs
        res = sb.odoo(new_dir, db, "", "-i", mod, "--stop-after-init", "--without-demo=all")
        ok, why = _odoo_ok(res, sb, db)
        warns = len(_WARN.findall(res.output))
        sv_st, sv_why = _secvals_check(sb, db, mod, v0) if ok else (PASS, "")
        if ok and sv_st != PASS:
            checks["install"] = Check(sv_st, sv_why, _tail(res.output))
        else:
            checks["install"] = Check(
                PASS if ok else FAIL,
                why or f"installed; {warns} warning line(s); {sv_why}",
                _tail(res.output),
                [] if ok else _classify(res.output, version),
            )
    if checks.get("install") and checks["install"].status == FAIL:
        for c in ("smoke", "tests", "access", "uninstall"):
            checks[c] = Check(SKIPPED, "install failed")
    elif s0 is not None:
        # (3a) gate-written smoke tests in a third database, from a separate harness container
        spec_acc = (role_spec or {}).get("access") or {}
        roles = [[m, gr, [int(x) for x in p]] for (m, gr), p in sorted(spec_acc.items())]
        r = sb.odoo(
            new_dir,
            sb.db_smoke,
            "",
            "-i",
            ",".join(dict.fromkeys(["base", *deps, mod])),
            "--stop-after-init",
            "--without-demo=all",
        )
        ok_s, why_s = _odoo_ok(r, sb, sb.db_smoke)
        role_res: dict[str, str] = {}
        if not ok_s:
            checks["smoke"] = Check(FAIL, f"smoke database install: {why_s}", _tail(r.output))
        else:
            raw_s = sb.smoke(new_dir, roles)
            st_s, det_s, role_res = read_smoke(raw_s)
            if st_s == PASS:
                smoked = json.loads(raw_s.decode())["models"]  # type: ignore[union-attr]
                st_v, det_v, role_db = verify_smoke_db(
                    lambda q, n: sb.psql(sb.db_smoke, q, fields=n),
                    raw_s,
                    [m for m, v in smoked.items() if v == "ok"],
                    roles,
                    mod,
                )
                st_s, det_s = (st_s, f"{det_s}; {det_v}") if st_v == PASS else (st_v, det_v)
                role_res = {
                    k: (v if role_db.get(k) == "ok" else f"db: {role_db.get(k, 'not checked')}")
                    for k, v in role_res.items()
                }
            checks["smoke"] = Check(st_s, det_s)
        # (3b) the module's own tests: ADVISORY only (they run inside the module's process);
        # stock run (log line) AND harness run (own report, gate-owned canaries)
        every, _access = _test_methods(files)
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
        h_ok, h_why, h_passed = (False, "not run", set())
        if every and stats and not (failed or errors or not ok3 or ran < len(every)):
            h_ok, h_why, h_passed = _harness(sb, new_dir, db, files, every)
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
        elif not h_ok:
            checks["tests"] = Check(FAIL, h_why, _tail(res.output))
        else:
            checks["tests"] = Check(
                PASS, f"0 failed, 0 error(s) of {ran} tests; {h_why}", _tail(res.output)
            )
        # (5) role access: live rows (trusted reader) match the req2mod spec AND the gate's
        # smoke role users get every permission the spec grants (checked over RPC)
        if role_spec is None:
            checks["access"] = Check(UNVERIFIED, "no req2mod role spec supplied")
        elif not spec_acc:
            checks["access"] = Check(FAIL, "role spec has no access rows to verify")
        elif checks["smoke"].status != PASS:
            checks["access"] = Check(
                checks["smoke"].status if checks["smoke"].status != SKIPPED else UNVERIFIED,
                "smoke tests did not pass",
            )
        else:
            after = {t: max(s0["i"].get(t) or {0}) for t in ("ir_model_access", "ir_rule")}
            rows = sb.psql(db, sql_access(mod, after), fields=8)
            bad = access_diff(role_spec, rows) if rows is not None else None
            want = {f"{m}|{gr}" for m, gr, _p in roles}
            role_bad = sorted(
                f"{k}: {role_res.get(k, 'not checked')}" for k in want if role_res.get(k) != "ok"
            )
            if bad is None:
                checks["access"] = Check(UNVERIFIED, "live access rows unreadable")
            elif bad:
                checks["access"] = Check(FAIL, "; ".join(bad[:10]))
            elif role_bad:
                checks["access"] = Check(FAIL, "smoke roles: " + "; ".join(role_bad[:10]))
            else:
                checks["access"] = Check(
                    PASS,
                    f"{len(rows)} live row(s) match the role spec ({len(spec_acc)} access, "
                    f"{len(role_spec.get('rules') or {})} rule(s)); {len(want)} smoke role "
                    "check(s) granted",
                )
        # (5b) stock security values still untouched after the module's own tests ran in db
        sv_st, sv_why = _secvals_check(sb, db, mod, v0)
        if sv_st != PASS and checks["install"].status == PASS:
            checks["install"] = Check(sv_st, f"after module tests: {sv_why}")
        # (6) uninstall leaves nothing behind: state and full snapshot read from the database
        res = sb.odoo(new_dir, db, "shell", "--no-http", stdin=uninstall_script(mod))
        st = sb.state(db)
        s1 = sb.snapshot(db)
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
                "; ".join(bad)
                or "clean: nothing left (schemas, relations, columns, functions, row ids)",
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
            u0 = _secvals(sb.psql(sb.db_upg, sql_secvals(mod), fields=4))
            r2 = sb.odoo(new_dir, sb.db_upg, "", "-u", mod, "--stop-after-init")
            ok2, why2 = _odoo_ok(r2, sb, sb.db_upg)
            sv_st, sv_why = _secvals_check(sb, sb.db_upg, mod, u0) if ok2 else (PASS, "")
            if ok2 and sv_st != PASS:
                checks["upgrade"] = Check(sv_st, f"upgrade: {sv_why}", _tail(r2.output))
            else:
                checks["upgrade"] = Check(
                    PASS if ok2 else FAIL,
                    why2 or f"prior -> new upgraded cleanly; {sv_why}",
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
    "role_spec_from",
    "run_gate",
    "validate_argv",
]
