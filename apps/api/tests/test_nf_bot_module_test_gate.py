"""BOT-MODULE-TEST-GATE: fail-closed promotion gate (fake runner; live needs ODOO_LIVE=1)."""

from __future__ import annotations

import ast
import copy
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
from module_generator import build_module_zip

from app.bots import module_test_gate as g
from app.bots import req2mod as rm
from app.bots import tiers

sys.path.insert(0, str(Path(__file__).parent))
from test_nf_bot_req2mod import ASSETS, BASE  # noqa: E402

MOD = "x_gate_fixture"
KEY = "k" * 40
LOADED = "2026-01-01 00:00:00,000 1 INFO gate odoo.modules.loading: 9 modules loaded in 1.0s\n"


def files(q=ASSETS, v=17):
    r = rm.build(copy.deepcopy(q), version=v, installed_modules=BASE, technical_name=MOD)
    assert r.ok, r.errors
    z = zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec)))
    return {n.split("/", 1)[1]: z.read(n) for n in z.namelist() if not n.endswith("/")}


NEW = copy.deepcopy(ASSETS)
NEW["entities"][0]["fields"].append({"key": "note", "type": "text"})


def role_spec(q=NEW, v=17):
    r = rm.build(copy.deepcopy(q), version=v, installed_modules=BASE, technical_name=MOD)
    return g.role_spec_from(r.spec, MOD)


def trail(models=("x.asset",)):
    return {m: {"kept": 41, "field": "name", "gone": 42} for m in models}


def role_users(cfg):
    return {
        f"{m}|{gr}": {"uid": 50 + i, "login": f"smoke_{60 + i}", "gid": 60 + i, "model": "x.asset"}
        for i, (m, gr, _p) in enumerate(cfg["roles"])
    }


def ids(n=10, extra=()):
    return ",".join(map(str, [*range(1, n + 1), *extra]))


class Fake:
    """Emulates docker + odoo + an independent psql read. State lives per database."""

    def __init__(self, tmp, spec=None, **over):
        self.tmp, self.over, self.calls = str(Path(tmp).resolve()), over, []
        self.spec = spec  # None: rows mirror the module's own access files
        self.state, self.phase, self.addons, self.mod = {}, {}, None, None

    def _files(self):
        root = Path(self.addons) / self.mod
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def _spec_rows(self):
        if self.spec is None:
            acc = g.declared_access(self._files(), self.mod) or {}
            return [["a", m, gr, *map(str, p), ""] for (m, gr), p in acc.items()]
        rows = [["a", m, gr, *map(str, p), ""] for (m, gr), p in self.spec["access"].items()]
        rows += [["r", m, gr, "1", "1", "1", "1", d] for (m, gr), d in self.spec["rules"].items()]
        return rows

    def _out(self, rows):
        pre = "k0\x001\n" if self.over.get("settings") else "k0\x000\n"
        body = "\x1e".join("\x00".join(r) for r in rows)
        return g.RunResult(0, pre + (body + "\n" if rows else ""))

    def _psql(self, db, sql):
        o = self.over
        if o.get("on_sql"):
            o["on_sql"](sql)
        if "gate:state" in sql:
            return self._out([[self.state.get(db, "uninstalled")]])
        if "pg_roles" in sql:
            return self._out([[o.get("role_priv", "0")]])
        if "gate:access" in sql:
            if o.get("access_rc"):
                return g.RunResult(1, "ERROR")
            rows = o.get("access_rows") or self._spec_rows()
            return self._out(rows + o.get("access_extra", []))
        if "gate:smokedb" in sql:
            if o.get("smokedb") is None and "smokedb" in o:
                return g.RunResult(1, "ERROR")
            return self._out([o.get("smokedb", ["m", "r", "1", "1", "0", "true"])])
        if "gate:smokescope" in sql:
            return self._out([["s", m] for m in o.get("scope", ["x.asset"])])
        if "gate:smokerole" in sql:
            return self._out([o.get("smokerole", ["u", "1", "1", "true", "true", "true", "true"])])
        if "gate:tables" in sql:
            return self._out([[t] for t in g.COUNT_TABLES])
        if "gate:schema" in sql:
            snap = {
                ("s", "public", ""): None,
                ("k", "public.res_partner", "r"): None,
                ("c", "public.res_partner", "id"): None,
                ("c", "public.res_partner", "name"): None,
            }
            idrows = {t: ids() for t in g.COUNT_TABLES}
            if self.phase.get(db) == "uninstalled":
                for r in o.get("leftover", []):
                    if r[0] == "i":
                        idrows[r[1]] = r[2]
                    else:
                        snap[tuple(r)] = None
            rows = [list(k) for k in snap] + [["i", t, v] for t, v in idrows.items()]
            return self._out(rows)
        return g.RunResult(1, "unknown query")

    def _harness(self, argv, stdin):
        host = next(a.split(":")[0] for a in argv if a.endswith(":rw"))
        path = stdin.split("M, P = ", 1)[1].split("\n", 1)[0].split(", ")[1].strip("'")
        xml = self.over.get("harness_xml", "auto")
        line = stdin.split("CF, CP, CC = ", 1)[1].split("\n", 1)[0]
        cf, cp, cc = ast.literal_eval(line)
        forged = self.over.get("canary") == "forged"
        can = "".join(
            f'<testcase name="odoo.addons.{self.mod}.tests.{cc}1.{m}" '
            f'result="{"ok" if forged or m == cp else "failure"}"/>'
            for m in (*cf, cp)
        )
        if self.over.get("canary") == "missing":
            can = ""
        if xml == "auto":
            every, _ = g._test_methods(self._files())
            xml = (
                "<testsuite>"
                + "".join(
                    f'<testcase name="odoo.addons.{self.mod}.tests.T.{m}" result="ok"/>'
                    for m in sorted(every)
                )
                + can
                + "</testsuite>"
            )
        if xml is not None:
            (Path(host) / path.rsplit("/", 1)[1]).write_text(xml)
        return g.RunResult(0, "")

    def smoke_report(self, cfg):
        sm = self.over.get("smoke", "auto")
        if callable(sm):
            return sm(cfg)
        if sm != "auto":
            return sm
        return {
            "models": {"x.asset": "ok"},
            "views": {"x.asset": "ok"},
            "actions": {"1": "ok"},
            "menus": {"1": "ok"},
            "crons": {},
            "roles": {f"{m}|{gr}": "ok" for m, gr, _p in cfg["roles"]},
            "errors": [],
            "trail": trail(),
            "role_users": role_users(cfg),
        }

    def run(self, argv, *, stdin=None, timeout=900):
        g.validate_argv(argv, self.tmp)
        self.calls.append(list(argv))
        o = self.over
        if "boom" in o:
            raise RuntimeError("x")
        if argv[1] == "exec" and argv[3] == "test":
            return g.RunResult(0, "")
        if argv[1] == "cp":
            rep = self.smoke_report(self.smoke_cfg)
            if rep is None:
                return g.RunResult(1, "no such file")
            Path(argv[3]).write_text(rep if isinstance(rep, str) else json.dumps(rep))
            return g.RunResult(0, "")
        if argv[1] == "run" and any(a.endswith("-s1") for a in argv):
            return g.RunResult(o.get("server_rc", 0), "")
        if argv[1] == "run" and argv[-2:] == ["python3", "-"]:
            line = stdin.split("C = json.loads(", 1)[1].split("\n", 1)[0][:-1]
            self.smoke_cfg = json.loads(ast.literal_eval(line))
            return g.RunResult(0, "")
        if argv[1] == "exec" and "psql" in argv:
            if argv[6] == g.PG_ADMIN:
                return g.RunResult(o.get("setup_rc", 0), "")
            return self._psql(argv[8], stdin)
        if argv[1] != "run" or "postgres:16" in argv:
            return g.RunResult(o.get("infra_rc", 0), "")
        db = argv[argv.index("-d") + 1]
        self.addons = next(a.split(":")[0] for a in argv if a.endswith(":/mnt/extra-addons:ro"))
        self.mod = next(p.name for p in Path(self.addons).iterdir())
        if "shell" in argv and "--test-enable" in argv:
            return self._harness(argv, stdin)
        if "shell" in argv:
            self.phase[db] = "uninstalled"
            self.state[db] = o.get("after", "uninstalled")
            return g.RunResult(o.get("uninstall_rc", 0), o.get("uninstall_out", ""))
        if "--test-enable" in argv:
            out = o.get(
                "tests_out",
                LOADED + "test_access_x_asset_keeper ok\n"
                "2026-01-01 00:00:00,000 1 INFO {db} odoo.tests.result: "
                "0 failed, 0 error(s) of 2 tests\n",
            )
            return g.RunResult(0, out.replace("{db}", db))
        args = argv[argv.index("-d") + 2 :]
        target = args[args.index("-i") + 1] if "-i" in args else ""
        if target.startswith("base") and self.mod in target.split(","):  # smoke database
            self.state[db] = o.get("smoke_state", "installed")
            return g.RunResult(o.get("smoke_install_rc", 0), LOADED)
        if target.startswith("base"):
            return g.RunResult(o.get("baseline_rc", 0), LOADED)
        key = "upgrade_out" if "-u" in args else "install_out"
        if "timeout" in o and key == "install_out":
            return g.RunResult(-1, "runner error: TimeoutExpired")
        out = o.get(key, LOADED)
        if "modules loaded in" in out:
            self.state[db] = o.get("install_state", "installed")
        else:
            self.state[db] = "to install"
        return g.RunResult(0, out)


def passed(rep, mh, version=17, module=MOD, prior_hash=None):
    return g.gate_passed(rep, mh, version=version, module=module, prior_hash=prior_hash)


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(g.KEY_ENV, KEY)


def gate(tmp_path, prior=None, **over):
    fs = files(NEW)
    rep = g.run_gate(
        fs,
        module=MOD,
        version=17,
        prior=prior,
        runner=Fake(tmp_path, **over),
        tmp_root=str(tmp_path),
        role_spec=role_spec(),
    )
    return rep, g.module_hash(fs)


def test_all_checks_pass_and_report_signed(tmp_path):
    rep, mh = gate(tmp_path, prior=files())
    assert {k: c.status for k, c in rep.checks.items()} == dict.fromkeys(g.CHECKS, g.PASS)
    ph = g.module_hash(files())
    assert rep.verdict == g.PASS and rep.signature and passed(rep, mh, prior_hash=ph)
    assert passed(json.loads(json.dumps(rep.to_dict())), mh, prior_hash=ph)  # stored as JSON
    assert not passed(rep, mh)  # prior must match too
    assert list(tmp_path.iterdir()) == []  # work dir removed


def test_upgrade_na_only_without_prior(tmp_path):
    rep, mh = gate(tmp_path)
    assert rep.checks["upgrade"].status == g.NA and passed(rep, mh)
    d = rep.to_dict()
    d["prior_hash"] = "0" * 64
    assert not passed(d, mh)


def test_no_sandbox_is_unverified_never_pass(tmp_path):
    fs = files(NEW)
    rep = g.run_gate(fs, module=MOD, version=17, runner=None)
    assert all(rep.checks[c].status == g.UNVERIFIED for c in g.CHECKS[1:])
    assert rep.verdict == g.FAIL and not passed(rep, g.module_hash(fs))


def test_sandbox_failures_fail_closed(tmp_path):
    for over in ({"boom": 1}, {"infra_rc": 1}):
        rep, mh = gate(tmp_path, **over)
        assert rep.verdict == g.FAIL and not passed(rep, mh)
        assert rep.checks["install"].status == g.UNVERIFIED


OKT = "2026-01-01 00:00:00,000 1 INFO {db} odoo.tests.result: "
ACC = "test_access_x_asset_keeper ok\n"


@pytest.mark.parametrize(
    "over,check,status",
    [
        (
            {
                "install_out": LOADED
                + "2026-01-01 00:00:00,000 1 ERROR gate odoo.sql_db: bad query\n"
            },
            "install",
            g.FAIL,
        ),
        ({"install_out": "nothing loaded\n"}, "install", g.FAIL),
        ({"install_state": "to install"}, "install", g.FAIL),  # log says loaded, DB says no
        ({"tests_out": LOADED}, "tests", g.UNVERIFIED),
        # module-printed result without this run's DB prefix is ignored
        ({"tests_out": LOADED + ACC + "0 failed, 0 error(s) of 2 tests\n"}, "tests", g.UNVERIFIED),
        (
            {
                "tests_out": LOADED + ACC + "1 2 INFO gate_0000000000000000 odoo.tests.result: "
                "0 failed, 0 error(s) of 2 tests\n"
            },
            "tests",
            g.UNVERIFIED,
        ),
        ({"tests_out": LOADED + OKT + "1 failed, 0 error(s) of 2 tests\n"}, "tests", g.FAIL),
        ({"tests_out": LOADED + OKT + "0 failed, 0 error(s) of 1 tests\n"}, "tests", g.FAIL),
        ({"harness_xml": None}, "tests", g.FAIL),  # no harness report: never pass
        ({"harness_xml": "<testsuite/>"}, "tests", g.FAIL),  # nothing ran
        ({"harness_xml": "<x>"}, "tests", g.FAIL),
        (
            {"harness_xml": '<testsuite><testcase name="a.test_x" result="failure"/></testsuite>'},
            "tests",
            g.FAIL,
        ),
        ({"settings": 1}, "install", g.FAIL),  # db/role setting (search_path) taints the run
        ({"role_priv": "1"}, "install", g.UNVERIFIED),  # odoo role privileged: refused
        ({"setup_rc": 1}, "install", g.UNVERIFIED),
        ({"access_rc": 1}, "access", g.UNVERIFIED),
        (
            {"access_extra": [["a", "x.model_x", "base.group_public", "1", "0", "0", "0", ""]]},
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    ["a", MOD + ".model_x_asset", "base.group_user", "1", "1", "1", "1", ""]
                ]
            },
            "access",
            g.FAIL,
        ),
        (
            {"access_extra": [["a", MOD + ".model_x_asset", "", "1", "1", "1", "1", ""]]},
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    ["r", MOD + ".model_x_asset", "base.group_portal", "1", "1", "1", "1", "[]"]
                ]
            },
            "access",
            g.FAIL,
        ),
        ({"access_rows": [["a", "m", "g", "1", "1", "1", "1", ""]]}, "access", g.FAIL),
        # global rule / always-true domain / rule or row on a non-owned model not in the spec
        (
            {"access_extra": [["r", "base.model_res_partner", "", "1", "1", "1", "1", "[]"]]},
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    [
                        "r",
                        "base.model_res_partner",
                        "base.group_user",
                        "1",
                        "1",
                        "1",
                        "1",
                        "[(1, '=', 1)]",
                    ]
                ]
            },
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    [
                        "r",
                        "base.model_res_partner",
                        "base.group_user",
                        "1",
                        "1",
                        "1",
                        "1",
                        "[('id', '>', 0)]",
                    ]
                ]
            },
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    ["a", "base.model_res_partner", MOD + ".group_keeper", "1", "1", "1", "1", ""]
                ]
            },
            "access",
            g.FAIL,
        ),
        ({"leftover": [["k", "public.x_orphan_tbl", "r"]]}, "uninstall", g.FAIL),
        ({"leftover": [["k", "public.x_orphan_seq", "S"]]}, "uninstall", g.FAIL),
        ({"leftover": [["k", "public.x_orphan_view", "v"]]}, "uninstall", g.FAIL),
        ({"leftover": [["s", "x_orphan_schema", ""]]}, "uninstall", g.FAIL),
        ({"leftover": [["f", "public.x_orphan_fn", ""]]}, "uninstall", g.FAIL),
        ({"leftover": [["c", "public.res_partner", "x_left"]]}, "uninstall", g.FAIL),
        ({"leftover": [["i", "ir_model_data", ids(10, [13])]]}, "uninstall", g.FAIL),
        # same count, different id: compared by id, not count
        ({"leftover": [["i", "ir_cron", ids(9, [11])]]}, "uninstall", g.FAIL),
        ({"after": "to remove"}, "uninstall", g.FAIL),
        # hostile hook prints an old-style clean marker, then raises: DB still says installed
        (
            {
                "after": "installed",
                "uninstall_rc": 1,
                "uninstall_out": 'GATE_RESULT {"before": "installed", "after": "uninstalled",'
                ' "xmlids": 0, "models": 0, "tables": []}\nTraceback',
            },
            "uninstall",
            g.FAIL,
        ),
        ({"uninstall_rc": 1}, "uninstall", g.FAIL),
    ],
)
def test_each_check_fails_closed(tmp_path, over, check, status):
    rep, mh = gate(tmp_path, **over)
    assert rep.checks[check].status == status, rep.checks[check]
    # r7: the module's own tests are advisory; every deciding check fails closed
    assert passed(rep, mh) is (check in g.ADVISORY)


def test_install_failure_skips_dependents_and_classifies(tmp_path):
    out = LOADED + (
        "2026-01-01 00:00:00,000 1 ERROR gate odoo.modules.registry: Failed to load registry\n"
    )
    rep, _ = gate(tmp_path, install_out=out)
    assert rep.checks["install"].status == g.FAIL
    assert all(rep.checks[c].status == g.SKIPPED for c in ("tests", "access", "uninstall"))


def test_upgrade_failure(tmp_path):
    bad = LOADED + "2026-01-01 00:00:00,000 1 CRITICAL gate odoo.service.server: Failed\n"
    rep, mh = gate(tmp_path, prior=files(), upgrade_out=bad)
    assert rep.checks["upgrade"].status == g.FAIL and not passed(rep, mh)


def test_audit_failure_skips_sandbox(tmp_path):
    fs = files(NEW)
    fs["__init__.py"] += b"import os\nos.system('id')\n"
    fake = Fake(tmp_path)
    rep = g.run_gate(fs, module=MOD, version=17, runner=fake, tmp_root=str(tmp_path))
    assert rep.checks["audit"].status == g.FAIL and fake.calls == []
    assert all(rep.checks[c].status == g.SKIPPED for c in g.CHECKS[1:])


def test_module_without_tests_is_advisory_only(tmp_path):
    fs = {p: b for p, b in files(NEW).items() if not p.startswith("tests/")}
    rep = g.run_gate(
        fs,
        module=MOD,
        version=17,
        runner=Fake(tmp_path),
        tmp_root=str(tmp_path),
        role_spec=role_spec(),
    )
    assert rep.checks["tests"].status == g.FAIL  # advisory: recorded, does not decide
    assert rep.checks["smoke"].status == g.PASS and rep.checks["access"].status == g.PASS
    assert passed(rep, g.module_hash(fs))


@pytest.mark.parametrize(
    "mut",
    [
        lambda d: d["checks"]["tests"].update(status="fail"),
        lambda d: d["checks"]["access"].update(status="unverified"),
        lambda d: d.update(verdict="fail"),
        lambda d: d.update(module_hash="0" * 64),
        lambda d: d.update(version=18),
        lambda d: d.update(version=17.0),
        lambda d: d["checks"].pop("uninstall"),
        lambda d: d.update(signature=""),
        lambda d: d.update(signature=d["signature"][::-1]),
        lambda d: d.update(schema="module-test-gate/0"),
        lambda d: d["checks"]["install"].update(log="edited"),
    ],
)
def test_tampered_report_rejected(tmp_path, mut):
    rep, mh = gate(tmp_path)
    d = json.loads(json.dumps(rep.to_dict()))
    mut(d)
    assert not passed(d, mh)


def test_gate_passed_never_raises_and_needs_key(tmp_path, monkeypatch):
    rep, mh = gate(tmp_path)
    for junk in (None, 1, "x", [], {"signature": 5}):
        assert passed(junk, mh) is False
    assert not passed(rep, None) and not passed(rep, "0" * 64)
    monkeypatch.setenv(g.KEY_ENV, "other" * 10)
    assert not passed(rep, mh)  # signed with another key
    monkeypatch.delenv(g.KEY_ENV)
    assert not passed(rep, mh)
    rep2, mh2 = gate(tmp_path)
    assert rep2.verdict == g.FAIL and not rep2.signature and not passed(rep2, mh2)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "X",
        "a",
        "x;rm -rf /",
        "x y",
        "../x",
        "x\n",
        "x$(id)",
        "Ünï",
        "-x",
        "x" * 64,
        None,
        3,
        "sale",
        "base",
        "x_a/b",
    ],
)
def test_hostile_module_names_refused(name):
    with pytest.raises(g.GateError):
        g.run_gate(files(NEW), module=name, version=17, runner=None)


@pytest.mark.parametrize("sb", ["https://client.odoo.com", "prod", "docker-remote", None, ""])
def test_only_local_sandbox_endpoint(sb):
    with pytest.raises(g.GateError):
        g.run_gate(files(NEW), module=MOD, version=17, sandbox=sb)


@pytest.mark.parametrize("v", [16, 21, "17", 17.0, True, None])
def test_version_exact(v):
    with pytest.raises(g.GateError):
        g.run_gate(files(NEW), module=MOD, version=v)


def test_hostile_sources_refused():
    for src in (
        {"../x.py": b""},
        {".module_dir": b"base", "__manifest__.py": b"{}"},
        {"__init__.py": b""},
        {"a.py": "str"},
    ):
        with pytest.raises(g.GateError):
            g.run_gate(src, module=MOD, version=17)


T = str(Path("/tmp").resolve()) + "/w"
NET = "ws-0123456789ab-net"
PG = "ws-0123456789ab-pg"
DB = "db_0123456789abcdef"
OK_RUN = [
    "docker",
    "run",
    "--rm",
    "--name",
    "ws-0123456789ab-o1",
    "--network",
    NET,
    *g.ODOO_HARDEN,
    "-e",
    f"HOST={PG}",
    "-e",
    "USER=odoo",
    "-v",
    f"{T}/ws-x/new:/mnt/extra-addons:ro",
    "odoo:17",
    "odoo",
    "-d",
    DB,
    "-i",
    MOD,
    "--stop-after-init",
]
PSQL = ["docker", "exec", "-i", PG, "psql", "-U", "reader", "-d", DB, *g._PSQL_TAIL]
RES = f"{T}/ws-x/r0123456789abcdef"
OK_SHELL = [*OK_RUN[: OK_RUN.index("odoo:17")], "-v", f"{RES}:/var/tmp/r0123456789abcdef:rw"]
OK_SHELL += [
    "odoo:17",
    "odoo",
    "shell",
    "-d",
    DB,
    "--no-http",
    "--test-enable",
    "--test-tags",
    "/" + MOD,
]


def _drop(flag):
    return [x for x in OK_RUN if x != flag]


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "docker ps"],
        "docker run odoo:17",
        ["docker", "ps"],
        ["docker", "exec", "ws-0123456789ab-pg", "psql"],
        ["docker", "rm", "-f", "client_db"],
        ["docker", "network", "rm", "bridge"],
        OK_RUN[:2] + ["--privileged"] + OK_RUN[2:],
        OK_RUN[:2] + ["-p", "8069:8069"] + OK_RUN[2:],
        OK_RUN[:2] + ["--network=host"] + OK_RUN[4:],
        [x.replace("odoo:17", "evil/odoo:17") for x in OK_RUN],
        [x.replace("odoo:17", "odoo:latest") for x in OK_RUN],
        [x.replace(f"{T}/ws-x/new", "/var/run/docker.sock") for x in OK_RUN],
        [x.replace(f"{T}/ws-x/new", "/etc") for x in OK_RUN],
        [x.replace(":ro", ":rw") for x in OK_RUN],
        [x.replace(f"HOST={PG}", "LD_PRELOAD=x") for x in OK_RUN],
        [x.replace("ws-0123456789ab-net", "client-net") for x in OK_RUN],
        OK_RUN + ["x; rm -rf /"],
        OK_RUN + ["$(id)"],
        [x for x in OK_RUN if x not in ("--network", NET)],
        ["docker", "network", "create", NET],  # not --internal
        *[_drop(f) for f in g.ODOO_HARDEN],  # every containment flag is required
        [x.replace(f"HOST={PG}", "HOST=prod-db") for x in OK_RUN],
        [x.replace(f"HOST={PG}", "HOST=ws-ffffffffffff-pg") for x in OK_RUN],
        OK_RUN + ["--db_host=prod"],
        OK_RUN + ["--addons-path=/etc"],
        OK_RUN + ["-d", "client_db"],
        [x.replace(DB, "client_db") for x in OK_RUN],
        [x.replace(f"{T}/ws-x/new", f"{T}/ws-x/../../etc") for x in OK_RUN],
        [x.replace("ws-0123456789ab-o1", "ws-ffffffffffff-o1") for x in OK_RUN],
        [x.replace("ws-0123456789ab-o1", PG) for x in OK_RUN],
        OK_RUN[:2] + ["--memory=64g"] + OK_RUN[2:],
        OK_RUN[:2] + ["--security-opt=seccomp=unconfined"] + OK_RUN[2:],
        OK_RUN[:2] + ["--read-only"] + OK_RUN[2:],  # duplicate
        PSQL[:-1],
        PSQL + ["-c", "DROP"],
        [x.replace(DB, "postgres") for x in PSQL],
        ["docker", "exec", PG, "sh"],
        [x.replace("reader", "odoo") for x in PSQL],  # reads never as the app role
        [
            {"reader": "postgres", DB: "template1"}.get(x, x) for x in PSQL
        ],  # superuser: postgres or sandbox db only
        [x.replace("USER=odoo", "USER=postgres") for x in OK_RUN],  # odoo never as superuser
        [x.replace(":rw", ":ro").replace("/var/tmp/r0123456789abcdef", "/x") for x in OK_SHELL],
        [x.replace("/var/tmp/r0123456789abcdef", "/var/tmp/rffffffffffffffff") for x in OK_SHELL],
        [x.replace(RES, "/etc/r0123456789abcdef") for x in OK_SHELL],
        OK_SHELL[: OK_SHELL.index("odoo:17")]
        + ["-v", f"{T}/ws-x/rffffffffffffffff:/var/tmp/rffffffffffffffff:rw"]
        + OK_SHELL[OK_SHELL.index("odoo:17") :],  # two result mounts
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            PG,
            "--network",
            NET,
            *g.PG_HARDEN,
            "-e",
            "POSTGRES_USER=odoo",
            "postgres:16",
        ],
    ],
)
def test_sandbox_allow_list(argv):
    with pytest.raises(g.GateError):
        g.validate_argv(argv, T)


def test_allow_list_accepts_gate_commands(tmp_path):
    fake = Fake(tmp_path)
    g.run_gate(
        files(NEW), module=MOD, version=17, prior=files(), runner=fake, tmp_root=str(tmp_path)
    )
    assert len(fake.calls) >= 8 and all(isinstance(a, list) for a in fake.calls)
    g.validate_argv(OK_RUN, T)
    g.validate_argv(PSQL, T)
    g.validate_argv(OK_SHELL, T)
    assert ["docker", "network", "create", "--internal"] == fake.calls[0][:4]
    runs = [c for c in fake.calls if c[1] == "run" and "odoo:17" in c]
    mod_runs = [c for c in runs if c[-2:] != ["python3", "-"]]
    h_runs = [c for c in runs if c[-2:] == ["python3", "-"]]
    assert mod_runs and all(set(g.ODOO_HARDEN) <= set(c) for c in mod_runs)
    assert len(h_runs) == 1 and set(g.HARNESS_HARDEN) <= set(h_runs[0])
    assert "--read-only" not in h_runs[0] and not any(a in h_runs[0] for a in ("-e", "-v"))
    assert any(c[1] == "cp" for c in fake.calls)


def test_real_runner_needs_live(monkeypatch):
    monkeypatch.delenv("ODOO_LIVE", raising=False)
    with pytest.raises(g.GateError):
        g.DockerRunner()
    monkeypatch.setenv("ODOO_LIVE", "1")
    monkeypatch.setenv("DOCKER_HOST", "tcp://prod:2375")
    with pytest.raises(g.GateError):
        g.DockerRunner()


def test_logs_redacted(tmp_path):
    out = (
        LOADED
        + "1 ERROR gate x: password=hunter2secret\n"
        + OKT
        + "0 failed, 0 error(s) of 2 tests\n"
    )
    rep, _ = gate(tmp_path, tests_out=out)
    assert "hunter2secret" not in json.dumps(rep.to_dict())


def test_t3_switch_not_flipped():
    assert tiers.tier_ready(tiers.T3) is False
    assert tiers.REQUIRED[tiers.T3] == ("module-authoring", "module-test-gate")
    assert len(g.T3_SWITCH_PRECONDITIONS) >= 4


def test_version_module_prior_replay_refused(tmp_path):
    rep, mh = gate(tmp_path)
    assert passed(rep, mh)
    assert not passed(rep, mh, version=19)  # a v17 report never passes for v19
    assert not passed(rep, mh, module="x_other_mod")
    assert not passed(rep, mh, prior_hash="0" * 64)
    assert not g.gate_passed(rep, mh)  # version/module are required
    assert not g.gate_passed(rep, mh, version=17)
    assert not g.gate_passed(rep, mh, version="17", module=MOD)


def test_timeout_removes_container_and_close_removes_all_before_network(tmp_path):
    fake = Fake(tmp_path, timeout=1)
    rep = g.run_gate(files(NEW), module=MOD, version=17, runner=fake, tmp_root=str(tmp_path))
    assert rep.checks["install"].status == g.FAIL and not passed(rep, g.module_hash(files(NEW)))
    names = [c[c.index("--name") + 1] for c in fake.calls if c[1] == "run" and "--name" in c]
    timed = names[2]  # pg, baseline o1, then the module install o2 timed out
    i_rm = fake.calls.index(["docker", "rm", "-f", timed])
    last_rm = max(i for i, c in enumerate(fake.calls) if c[1] == "rm")
    net_rm = next(i for i, c in enumerate(fake.calls) if c[1:3] == ["network", "rm"])
    assert i_rm < last_rm < net_rm
    assert set(names) <= set(fake.calls[last_rm][3:])
    assert list(tmp_path.iterdir()) == []


def test_per_run_database_names_are_random(tmp_path):
    a, b = Fake(tmp_path), Fake(tmp_path)
    for f in (a, b):
        g.run_gate(files(NEW), module=MOD, version=17, runner=f, tmp_root=str(tmp_path))

    def db_of(c):
        rest = c[c.index("odoo:17") + 1 :]
        return rest[rest.index("-d") + 1]

    dbs = [{db_of(c) for c in f.calls if "odoo:17" in c and c[-1] != "-"} for f in (a, b)]
    assert dbs[0] and not dbs[0] & dbs[1]
    assert all(g.DB_RE.fullmatch(d) for d in dbs[0] | dbs[1])


def test_access_diff_and_snapshot_diff_units():
    spec = {
        "access": {("m.model_a", "m.group_a"): (1, 1, 0, 0)},
        "rules": {("m.model_a", "m.group_a"): "[('create_uid','=',user.id)]"},
    }
    ok = [
        ["a", "m.model_a", "m.group_a", "1", "1", "0", "0", ""],
        ["r", "m.model_a", "m.group_a", "1", "1", "1", "1", "[('create_uid', '=', user.id)]"],
    ]
    assert g.access_diff(spec, ok) == []
    assert g.access_diff(spec, ok[:1])  # declared rule missing
    assert g.access_diff(spec, [])  # declared row missing
    assert g.access_diff(spec, [["a", "m.model_a", "m.group_a", "1", "1", "1", "0", ""], ok[1]])
    assert g.access_diff(spec, [["x"]])
    assert g.access_diff(spec, [*ok, ["r", "m.model_a", "", "1", "1", "1", "1", "[]"]])
    assert g.access_diff(spec, [*ok, ["r", "m.model_b", "m.group_a", "1", "1", "1", "1", "[]"]])
    s0 = g._snapshot(
        [["s", "public", ""], ["k", "public.t", "r"], ["c", "public.t", "id"]]
        + [["i", t, "1,2"] for t in g.COUNT_TABLES]
    )
    assert s0 and g.snapshot_diff(s0, s0) == []
    for extra in (
        ["k", "public.u", "S"],
        ["s", "evil", ""],
        ["f", "public.f", ""],
        ["c", "public.t", "x"],
    ):
        s1 = copy.deepcopy(s0)
        s1[extra[0]].add((extra[1], extra[2]))
        assert g.snapshot_diff(s0, s1), extra
    s1 = copy.deepcopy(s0)
    s1["i"]["ir_rule"] = {1, 3}
    assert g.snapshot_diff(s0, s1)
    assert g._snapshot([["n", "x", "1"]]) is None  # unknown kind
    x0 = copy.deepcopy(s0)
    x0["x"] = {("extension:plpgsql", "1.0"), ("grant:public.t", "{postgres=arwdDxt/postgres}")}
    assert g.snapshot_diff(x0, x0) == []
    for kind in ("trigger:public.t.tr", "rule:public.t.r", "policy:public.t.p", "type:public.e"):
        x1 = copy.deepcopy(x0)
        x1["x"].add((kind, ""))
        assert g.snapshot_diff(x0, x1), kind
    x1 = copy.deepcopy(x0)
    x1["x"] = {
        ("extension:plpgsql", "1.0"),
        ("grant:public.t", "{postgres=r/postgres,=r/postgres}"),
    }
    assert any("grant" in d for d in g.snapshot_diff(x0, x1))  # changed grant
    x1["x"] = {("extension:plpgsql", "1.0")}
    assert g.snapshot_diff(x0, x1)  # removed grant


class _Rec:
    def __init__(self, out, rc=0):
        self.out, self.rc, self.calls = out, rc, []

    def run(self, argv, stdin=None, timeout=None):
        self.calls.append((argv, stdin))
        return g.RunResult(self.rc, self.out)


def test_psql_framing_fails_closed(tmp_path):
    def rd(out, fields=3):
        sb = g._Sandbox(_Rec(out), 17, MOD, str(tmp_path))
        return sb.psql("db_0123456789abcdef", "SELECT 1;\n", fields=fields), sb

    rows, sb = rd("k0\x000\na|b\x00x\ny\x00z\x1ec\x00d\x00e\n")
    assert rows == [["a|b", "x\ny", "z"], ["c", "d", "e"]]  # "|" and newline stay in-field
    assert sb.r.calls[0][1].startswith(g._PSET)
    assert rd("k0\x000\n")[0] == []
    assert rd("k0\x000\na\x00b\n")[0] is None  # wrong field count
    assert rd("k0\x000\na\x00b\x00c")[0] is None  # truncated framing
    assert rd("k0|0\na|b|c\n")[0] is None  # old "|" framing refused
    rows, sb = rd("k0\x001\na\x00b\x00c\n")
    assert rows is None and sb.tainted


def test_no_superuser_sql_after_module_code(tmp_path):
    sb = g._Sandbox(_Rec(""), 17, MOD, str(tmp_path))
    assert sb.admin_sql("postgres", "SELECT 1;\n").rc == 0
    sb.n = 1  # an odoo container (module code) has run
    with pytest.raises(g.GateError):
        sb.admin_sql("postgres", "SELECT 1;\n")
    src = Path(g.__file__).read_text()
    assert src.count('"-U", PG_ADMIN, "-d", db') == 1  # admin psql only via admin_sql


def test_role_spec_from_req2mod_not_module_files():
    rs = role_spec()
    assert rs and rs["access"] and all(m.startswith(MOD + ".") for m, _ in rs["access"])
    assert g.role_spec_from(object(), MOD) is None


def test_access_without_role_spec_never_passes(tmp_path):
    fs = files(NEW)
    rep = g.run_gate(fs, module=MOD, version=17, runner=Fake(tmp_path), tmp_root=str(tmp_path))
    assert rep.checks["access"].status == g.UNVERIFIED and not passed(rep, g.module_hash(fs))


def test_module_referencing_harness_path_fails(tmp_path, monkeypatch):
    import secrets

    monkeypatch.setattr(secrets, "token_hex", lambda n=16: "ab" * n)
    fs = files(NEW)
    fs["tests/__init__.py"] += b"\n# rabababababababab\n"
    rep = g.run_gate(
        fs,
        module=MOD,
        version=17,
        runner=Fake(tmp_path),
        tmp_root=str(tmp_path),
        role_spec=role_spec(),
    )
    assert rep.checks["tests"].status == g.FAIL
    assert "harness result path" in rep.checks["tests"].detail


def test_read_harness_counts_independently():
    every = {"test_a", "test_b"}
    ok = (
        '<testsuite><testcase name="x.T.test_a" result="ok"/>'
        '<testcase name="x.T.test_b" result="ok"/></testsuite>'
    )
    assert g.read_harness(ok.encode(), every)[0]
    assert not g.read_harness(ok.replace("test_b", "test_c").encode(), every)[0]
    assert not g.read_harness(
        ok.replace('"ok"/></testsuite>', '"skipped"/></testsuite>').encode(), every
    )[0]
    assert not g.read_harness(None, every)[0]
    other = ok.replace("x.T.test_a", "odoo.addons.base.tests.T.test_a")
    assert not g.read_harness(other.encode(), every, module="x")[0]  # foreign test in report
    assert not g.read_harness(b"x" * 2_000_001, every)[0]


@pytest.mark.parametrize("mode", ["forged", "missing"])
def test_canary_wrong_answer_refuses(mode, tmp_path):
    rep, _ = gate(tmp_path, canary=mode)
    assert rep.checks["tests"].status == g.FAIL
    assert "canar" in rep.checks["tests"].detail


def test_read_harness_canary_answers():
    cn = g.Canary.new()
    base = '<testcase name="odoo.addons.x_mod.tests.T.test_a" result="ok"/>'

    def rows(fail_kind):
        return "".join(
            f'<testcase name="odoo.addons.x_mod.tests.{cn.cls}1.{m}" '
            f'result="{fail_kind if m != cn.pas else "ok"}"/>'
            for m in (*cn.fail, cn.pas)
        )

    good = f"<testsuite>{base}{rows('failure')}</testsuite>".encode()
    assert g.read_harness(good, {"test_a"}, "x_mod", cn)[0]
    bad = f"<testsuite>{base}{rows('ok')}</testsuite>".encode()
    assert not g.read_harness(bad, {"test_a"}, "x_mod", cn)[0]
    assert not g.read_harness(f"<testsuite>{base}</testsuite>".encode(), {"test_a"}, "x_mod", cn)[0]
    sc = g.harness_script("x_mod", "/var/tmp/r0123456789abcdef/0123456789abcdef.xml", cn)
    assert cn.cls in sc and all(m in sc for m in cn.fail)


def test_harness_script_paths_are_strict():
    with pytest.raises(AssertionError):
        g.harness_script(MOD, "/tmp/x.xml")
    sc = g.harness_script(MOD, "/var/tmp/r0123456789abcdef/0123456789abcdef.xml")
    assert "make_suite" in sc and MOD in sc


def test_t3_preconditions_document_sandbox_detection():
    assert any("detectable" in x for x in g.T3_SWITCH_PRECONDITIONS)


# ---- round 7 A: gate-written smoke tests decide; the module's own tests are advisory


def _sm(**kw):
    def f(cfg):
        rep = {
            "models": {"x.asset": "ok"},
            "views": {},
            "actions": {},
            "menus": {},
            "crons": {},
            "roles": {f"{m}|{gr}": "ok" for m, gr, _p in cfg["roles"]},
            "errors": [],
            "trail": trail(),
            "role_users": role_users(cfg),
        }
        for k, v in kw.items():
            rep[k] = v(cfg) if callable(v) else v
        return rep

    return f


@pytest.mark.parametrize(
    "over, smoke, access",
    [
        ({"smoke": None}, g.UNVERIFIED, g.UNVERIFIED),  # no report
        ({"smoke": "{not json"}, g.FAIL, g.FAIL),
        ({"smoke": _sm(errors=["admin login failed"])}, g.FAIL, g.FAIL),
        ({"smoke": _sm(models={"x.asset": "error: boom"})}, g.FAIL, g.FAIL),
        ({"smoke": _sm(views={"x.asset": "error: bad arch"})}, g.FAIL, g.FAIL),
        ({"smoke": _sm(menus={"3": "action ir.actions.act_window,9 missing"})}, g.FAIL, g.FAIL),
        ({"smoke": _sm(models={"x.asset": "skip: cannot fill"})}, g.UNVERIFIED, g.UNVERIFIED),
        ({"smoke": _sm(models={})}, g.FAIL, g.FAIL),  # nothing exercised
        ({"smoke": _sm(roles={})}, g.PASS, g.FAIL),  # role checks missing
        (
            {
                "smoke": _sm(
                    roles=lambda c: {f"{m}|{gr}": "write denied" for m, gr, _ in c["roles"]}
                )
            },
            g.PASS,
            g.FAIL,
        ),
        ({"server_rc": 1}, g.UNVERIFIED, g.UNVERIFIED),
        ({"smoke_install_rc": 1}, g.FAIL, g.FAIL),
        ({"smoke_state": "to install"}, g.FAIL, g.FAIL),
    ],
)
def test_smoke_decides_and_fails_closed(tmp_path, over, smoke, access):
    rep, mh = gate(tmp_path, **over)
    assert rep.checks["smoke"].status == smoke, rep.checks["smoke"]
    assert rep.checks["access"].status == access, rep.checks["access"]
    assert not passed(rep, mh)


def test_forged_module_tests_cannot_pass_without_smoke(tmp_path):
    rep, mh = gate(tmp_path, smoke=_sm(models={"x.asset": "error: create failed"}))
    assert rep.checks["tests"].status == g.PASS and not passed(rep, mh)
    d = rep.to_dict()
    d["checks"]["smoke"]["status"] = g.PASS  # tampering breaks the signature
    assert not passed(d, mh)


def test_schema2_and_deciding_checks():
    assert g.SCHEMA == "module-test-gate/2" and "tests" not in g.DECIDING
    assert set(g.DECIDING) | set(g.ADVISORY) == set(g.CHECKS) and "smoke" in g.DECIDING


def test_canaries_use_gate_owned_base():
    src = g.harness_script(MOD, "/var/tmp/r0123456789abcdef/0123456789abcdef.xml")
    assert "(GateCase,)" in src and "(base,)" not in src


def test_smoke_script_compiles_and_is_parameterised():
    cfg = {
        "host": "ws-0123456789ab-s1",
        "db": "dbs_0123456789abcdef",
        "module": MOD,
        "pw": "p" * 32,
        "ready": "/var/tmp/0123456789abcdef.ready",
        "out": "/var/tmp/0123456789abcdef.json",
        "roles": [["m.model_a", "m.group_a", [1, 1, 0, 0]]],
    }
    compile(g.smoke_script(cfg), "smoke", "exec")
    with pytest.raises(AssertionError):
        g.smoke_script({**cfg, "out": "/tmp/x.json"})


T7 = "/tmp/gt"
H = [
    "docker", "run", "-i", "--name", "ws-0123456789ab-h1", "--network",
    "ws-0123456789ab-net", *g.HARNESS_HARDEN, "odoo:17", "python3", "-",
]  # fmt: skip


def test_harness_and_cp_allow_list(tmp_path):
    g.validate_argv(H, T7)
    g.validate_argv(["docker", "exec", "ws-0123456789ab-h1", "test", "-e",
                     "/var/tmp/0123456789abcdef.ready"], T7)  # fmt: skip
    root = os.path.realpath(tmp_path)
    (Path(root) / "ws-abc").mkdir()
    g.validate_argv(["docker", "cp", "ws-0123456789ab-h1:/var/tmp/0123456789abcdef.json",
                     f"{root}/ws-abc/smoke.json"], root)  # fmt: skip
    bad = [
        [*H[:7], "--read-only", *H[7:]],  # (duplicate-free but read-only is not allowed)
        [*H[:3], "--rm", *H[3:]],
        [*H[:7], "-e", "HOST=ws-0123456789ab-pg", *H[7:]],
        [*H[:7], "-v", f"{T7}/ws-a/x:/mnt/extra-addons:ro", *H[7:]],
        [*H[:-2], "python3", "-c", "x"],
        [*H[:-2], "odoo", "-d", "db_0123456789abcdef"],
        [x for x in H if x != "--cap-drop=ALL"],
        ["docker", "cp", "ws-0123456789ab-o1:/var/tmp/0123456789abcdef.json", f"{T7}/ws-a/s"],
        ["docker", "cp", "ws-0123456789ab-h1:/etc/passwd", f"{T7}/ws-a/s"],
        ["docker", "cp", "ws-0123456789ab-h1:/var/tmp/0123456789abcdef.json", "/etc/x"],
        ["docker", "cp", "ws-0123456789ab-h1:/var/tmp/0123456789abcdef.json", f"{T7}/../x"],
        ["docker", "exec", "ws-0123456789ab-h1", "cat", "/var/tmp/0123456789abcdef.json"],
        ["docker", "exec", "ws-0123456789ab-s1", "test", "-e", "/var/tmp/0123456789abcdef.ready"],
    ]
    for argv in bad:
        with pytest.raises(g.GateError):
            g.validate_argv(argv, T7)


def test_smoke_harness_is_never_imported_and_pinned_to_sandbox():
    app = Path(g.__file__).resolve().parents[1]
    for p in app.rglob("*.py"):
        assert "sandbox_harness" not in "".join(
            ln for ln in p.read_text().splitlines() if ln.lstrip().startswith(("import", "from"))
        ), p
    cfg = {
        "host": "ws-0123456789ab-s1",
        "db": "dbs_0123456789abcdef",
        "module": MOD,
        "pw": "p" * 32,
        "ready": "/var/tmp/0123456789abcdef.ready",
        "out": "/var/tmp/0123456789abcdef.json",
        "roles": [],
    }
    for bad in ({"host": "client.example.com"}, {"db": "production"}):
        with pytest.raises(AssertionError):
            g.smoke_script({**cfg, **bad})


# ---- round 8 GATE 1: smoke facts are re-read from the smoke database (trusted read role)


@pytest.mark.parametrize(
    "over, smoke, access, why",
    [
        ({"smokedb": ["m", "r", "0", "0", "0", "true"]}, g.FAIL, g.FAIL, "created record not"),
        ({"smokedb": ["m", "r", "1", "0", "0", "true"]}, g.FAIL, g.FAIL, "written value not"),
        ({"smokedb": ["m", "r", "1", "1", "1", "true"]}, g.FAIL, g.FAIL, "still in the database"),
        ({"smokedb": ["m", "r", "1", "1", "0", "false"]}, g.FAIL, g.FAIL, "never created"),
        ({"smokedb": ["m", "v", "1", "1", "0", "true"]}, g.FAIL, g.FAIL, "not a plain table"),
        ({"smokedb": ["m", "", "1", "1", "0", "true"]}, g.FAIL, g.FAIL, "missing"),
        ({"smokedb": None}, g.UNVERIFIED, g.UNVERIFIED, "unreadable"),
        ({"smokedb": ["m", "r", "1"]}, g.UNVERIFIED, g.UNVERIFIED, "unreadable"),  # framing
        ({"smoke": _sm(trail={})}, g.FAIL, g.FAIL, "no smoke trail"),
        ({"smoke": _sm(trail={"x.asset": {"kept": 1, "field": "a;b", "gone": 2}})}, g.FAIL,
         g.FAIL, "trail unreadable"),
        ({"smoke": _sm(trail={"x.asset": {"kept": 1, "field": None, "gone": 1}})}, g.FAIL,
         g.FAIL, "trail unreadable"),
        ({"smoke": _sm(role_users={})}, g.PASS, g.FAIL, "smoke ok"),
        ({"smokerole": ["u", "0", "1", "true", "true", "true", "true"]}, g.PASS, g.FAIL, ""),
        ({"smokerole": ["u", "1", "0", "true", "true", "true", "true"]}, g.PASS, g.FAIL, ""),
        ({"smokerole": ["u", "1", "1", "false", "false", "false", "false"]}, g.PASS, g.FAIL, ""),
    ],
)  # fmt: skip
def test_smoke_db_readback_fails_closed(tmp_path, over, smoke, access, why):
    rep, mh = gate(tmp_path, **over)
    assert rep.checks["smoke"].status == smoke, rep.checks["smoke"]
    assert why in rep.checks["smoke"].detail
    assert rep.checks["access"].status == access, rep.checks["access"]
    if access == g.FAIL and smoke == g.PASS:
        assert "db:" in rep.checks["access"].detail
    assert not passed(rep, mh)


def test_smoke_db_readback_pass_names_it(tmp_path):
    rep, mh = gate(tmp_path)
    assert "db read-back 1 model(s)" in rep.checks["smoke"].detail
    assert rep.checks["access"].status == g.PASS and passed(rep, mh)


def test_smoke_sql_is_pinned_and_quoted():
    q = g.sql_smoke_record("x.asset", 4, "name", 5)
    assert 'public."x_asset"' in q and "relkind" in q and "pg_sequence_last_value" in q
    assert "'1'" in g.sql_smoke_record("x.asset", 4, None, 5)
    for bad in (("x.asset; drop", 1, None, 2), ("x.asset", 0, None, 2), ("x.asset", True, None, 2)):
        with pytest.raises(AssertionError):
            g.sql_smoke_record(*bad)
    r = g.sql_smoke_role(7, "smoke_9", 9, "x.asset")
    assert "res_groups_implied_rel" in r and "perm_unlink" in r
    with pytest.raises(AssertionError):
        g.sql_smoke_role(7, "admin' or '1", 9, "x.asset")


# ---- round 8 GATE 2: stock models the module inherits get the CRUD regression + DB read-back


def _inh(**kw):
    t = trail(("res.partner", "x.asset"))
    t["res.partner"] = {"kept": 7, "field": "x_note", "gone": 8}
    return _sm(models={"x.asset": "ok", "res.partner": "ok"}, trail=t, **kw)


def test_inherited_stock_model_smoked_and_read_back(tmp_path):
    seen = []
    rep, mh = gate(tmp_path, smoke=_inh(), scope=["res.partner", "x.asset"], on_sql=seen.append)
    assert rep.checks["smoke"].status == g.PASS and passed(rep, mh), rep.checks["smoke"]
    assert any('public."res_partner" WHERE id = 7' in q and '"x_note"' in q for q in seen)


@pytest.mark.parametrize(
    "inh, smokedb, why",
    [
        (False, None, "res.partner: not smoked"),  # harness skipped the inherited model
        (True, ["m", "r", "1", "0", "0", "true"], "written value not"),
        (True, ["m", "r", "1", "1", "1", "true"], "unlinked record still"),
    ],
)
def test_inherited_stock_model_regression_fails_closed(tmp_path, inh, smokedb, why):
    over = {"smoke": _inh() if inh else _sm(), "scope": ["res.partner", "x.asset"]}
    if smokedb:
        over["smokedb"] = smokedb
    rep, mh = gate(tmp_path, **over)
    assert rep.checks["smoke"].status == g.FAIL and why in rep.checks["smoke"].detail
    assert not passed(rep, mh)


def test_smoke_scope_sql_reads_defined_and_inherited():
    q = g.sql_smoke_scope("x_mod")
    assert "ir_model_fields" in q and "f.store" in q and "relkind = 'r'" in q
    with pytest.raises(AssertionError):
        g.sql_smoke_scope("x'; drop")


def test_smoke_harness_smokes_inherited_models():
    src = (g.Path(g.__file__).parent.parent / "sandbox_harness" / "smoke.py").read_text()
    assert "own | set(added)" in src and "prefer" in src


# ---- round 8 GATE 5: the smoke harness file is pinned by sha256


def test_smoke_harness_pin_matches_file():
    raw = g.SMOKE_HARNESS.read_bytes()
    assert g.hashlib.sha256(raw).hexdigest() == g.SMOKE_HARNESS_SHA256
    assert g.smoke_source() == raw.decode()


def test_smoke_harness_tampered_refused_at_gate_start(tmp_path, monkeypatch):
    bad = tmp_path / "smoke.py"
    bad.write_bytes(g.SMOKE_HARNESS.read_bytes() + b"\nout['models'] = {'x.asset': 'ok'}\n")
    monkeypatch.setattr(g, "SMOKE_HARNESS", bad)
    with pytest.raises(g.GateError, match="sha256"):
        gate(tmp_path)
    with pytest.raises(g.GateError, match="sha256"):
        g.smoke_source()


def test_smoke_facts_accepts_dotless_custom_model():
    raw = json.dumps({"trail": {"x_asset": {"kept": 1, "field": "x_name", "gone": 2}},
                      "role_users": {}}).encode()  # fmt: skip
    assert g.smoke_facts(raw) == ({"x_asset": {"kept": 1, "field": "x_name", "gone": 2}}, {})


# ---- round 8 GATE 3: sandbox readiness is probed over TCP (the init-time server is socket-only)


def test_sandbox_ready_probe_uses_tcp(tmp_path):
    fk = Fake(tmp_path)
    g.run_gate(files(NEW), module=MOD, version=17, runner=fk, role_spec=role_spec())
    probes = [c for c in fk.calls if "pg_isready" in c]
    assert probes and all(c[c.index("-h") + 1] == "127.0.0.1" for c in probes)
