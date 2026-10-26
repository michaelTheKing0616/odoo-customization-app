"""BOT-MODULE-TEST-GATE: fail-closed promotion gate (fake runner; live needs ODOO_LIVE=1)."""

from __future__ import annotations

import copy
import io
import json
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


class Fake:
    """Emulates docker + odoo + an independent psql read. State lives per database."""

    def __init__(self, tmp, **over):
        self.tmp, self.over, self.calls = str(Path(tmp).resolve()), over, []
        self.state, self.phase, self.addons, self.mod = {}, {}, None, None

    def _spec_rows(self):
        root = Path(self.addons) / self.mod
        fs = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        spec = g.declared_access(fs, self.mod)
        return [["a", m, gr, *map(str, p)] for (m, gr), p in spec.items()]

    def _psql(self, db, sql):
        o = self.over
        if "gate:state" in sql:
            st = self.state.get(db, "uninstalled")
            return g.RunResult(0, st + "\n")
        if "gate:access" in sql:
            if o.get("access_rc"):
                return g.RunResult(1, "ERROR")
            rows = o.get("access_rows") or self._spec_rows()
            rows = rows + o.get("access_extra", [])
            return g.RunResult(0, "".join("|".join(r) + "\n" for r in rows))
        if "gate:schema" in sql:
            cols = [["c", "res_partner", "id"], ["c", "res_partner", "name"]]
            counts = dict.fromkeys(g.COUNT_TABLES, "10")
            if self.phase.get(db) == "uninstalled":
                for r in o.get("leftover", []):
                    if r[0] == "n":
                        counts[r[1]] = r[2]
                    else:
                        cols.append(r)
            rows = cols + [["n", t, n] for t, n in counts.items()]
            return g.RunResult(0, "".join("|".join(r) + "\n" for r in rows))
        return g.RunResult(1, "unknown query")

    def run(self, argv, *, stdin=None, timeout=900):
        g.validate_argv(argv, self.tmp)
        self.calls.append(list(argv))
        o = self.over
        if "boom" in o:
            raise RuntimeError("x")
        if argv[1] == "exec" and "psql" in argv:
            return self._psql(argv[8], stdin)
        if argv[1] != "run" or "postgres:16" in argv:
            return g.RunResult(o.get("infra_rc", 0), "")
        db = argv[argv.index("-d") + 1]
        self.addons = next(a.split(":")[0] for a in argv if a.endswith(":/mnt/extra-addons:ro"))
        self.mod = next(a.split("=", 1)[1] for a in argv if a.startswith("GATE_MODULE="))
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
        ({"tests_out": LOADED + OKT + "0 failed, 0 error(s) of 2 tests\n"}, "access", g.UNVERIFIED),
        ({"access_rc": 1}, "access", g.UNVERIFIED),
        (
            {"access_extra": [["a", "x.model_x", "base.group_public", "1", "0", "0", "0"]]},
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    ["a", MOD + ".model_x_asset", "base.group_user", "1", "1", "1", "1"]
                ]
            },
            "access",
            g.FAIL,
        ),
        (
            {"access_extra": [["a", MOD + ".model_x_asset", "", "1", "1", "1", "1"]]},
            "access",
            g.FAIL,
        ),
        (
            {
                "access_extra": [
                    ["r", MOD + ".model_x_asset", "base.group_portal", "1", "1", "1", "1"]
                ]
            },
            "access",
            g.FAIL,
        ),
        ({"access_rows": [["a", "m", "g", "1", "1", "1", "1"]]}, "access", g.FAIL),
        ({"leftover": [["c", "x_orphan_tbl", "id"]]}, "uninstall", g.FAIL),
        ({"leftover": [["c", "res_partner", "x_left"]]}, "uninstall", g.FAIL),
        ({"leftover": [["n", "ir_model_data", "13"]]}, "uninstall", g.FAIL),
        ({"leftover": [["n", "ir_cron", "11"]]}, "uninstall", g.FAIL),
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
    assert not passed(rep, mh)


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


def test_module_without_tests_or_roles_fails(tmp_path):
    fs = {p: b for p, b in files(NEW).items() if not p.startswith("tests/")}
    rep = g.run_gate(fs, module=MOD, version=17, runner=Fake(tmp_path), tmp_root=str(tmp_path))
    assert rep.checks["tests"].status == g.FAIL and rep.checks["access"].status == g.FAIL


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
NET = "ingate-0123456789ab-net"
PG = "ingate-0123456789ab-pg"
DB = "gate_0123456789abcdef"
OK_RUN = [
    "docker",
    "run",
    "--rm",
    "--name",
    "ingate-0123456789ab-o1",
    "--network",
    NET,
    *g.ODOO_HARDEN,
    "-e",
    f"HOST={PG}",
    "-v",
    f"{T}/ingate-x/new:/mnt/extra-addons:ro",
    "odoo:17",
    "odoo",
    "-d",
    DB,
    "-i",
    MOD,
    "--stop-after-init",
]
PSQL = ["docker", "exec", "-i", PG, "psql", "-U", "odoo", "-d", DB, "-At", "-v", "ON_ERROR_STOP=1"]


def _drop(flag):
    return [x for x in OK_RUN if x != flag]


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "docker ps"],
        "docker run odoo:17",
        ["docker", "ps"],
        ["docker", "exec", "ingate-0123456789ab-pg", "psql"],
        ["docker", "rm", "-f", "client_db"],
        ["docker", "network", "rm", "bridge"],
        OK_RUN[:2] + ["--privileged"] + OK_RUN[2:],
        OK_RUN[:2] + ["-p", "8069:8069"] + OK_RUN[2:],
        OK_RUN[:2] + ["--network=host"] + OK_RUN[4:],
        [x.replace("odoo:17", "evil/odoo:17") for x in OK_RUN],
        [x.replace("odoo:17", "odoo:latest") for x in OK_RUN],
        [x.replace(f"{T}/ingate-x/new", "/var/run/docker.sock") for x in OK_RUN],
        [x.replace(f"{T}/ingate-x/new", "/etc") for x in OK_RUN],
        [x.replace(":ro", ":rw") for x in OK_RUN],
        [x.replace(f"HOST={PG}", "LD_PRELOAD=x") for x in OK_RUN],
        [x.replace("ingate-0123456789ab-net", "client-net") for x in OK_RUN],
        OK_RUN + ["x; rm -rf /"],
        OK_RUN + ["$(id)"],
        [x for x in OK_RUN if x not in ("--network", NET)],
        ["docker", "network", "create", NET],  # not --internal
        *[_drop(f) for f in g.ODOO_HARDEN],  # every containment flag is required
        [x.replace(f"HOST={PG}", "HOST=prod-db") for x in OK_RUN],
        [x.replace(f"HOST={PG}", "HOST=ingate-ffffffffffff-pg") for x in OK_RUN],
        OK_RUN + ["--db_host=prod"],
        OK_RUN + ["--addons-path=/etc"],
        OK_RUN + ["-d", "client_db"],
        [x.replace(DB, "client_db") for x in OK_RUN],
        [x.replace(f"{T}/ingate-x/new", f"{T}/ingate-x/../../etc") for x in OK_RUN],
        [x.replace("ingate-0123456789ab-o1", "ingate-ffffffffffff-o1") for x in OK_RUN],
        [x.replace("ingate-0123456789ab-o1", PG) for x in OK_RUN],
        OK_RUN[:2] + ["--memory=64g"] + OK_RUN[2:],
        OK_RUN[:2] + ["--security-opt=seccomp=unconfined"] + OK_RUN[2:],
        OK_RUN[:2] + ["--read-only"] + OK_RUN[2:],  # duplicate
        PSQL[:-1],
        PSQL + ["-c", "DROP"],
        [x.replace(DB, "postgres") for x in PSQL],
        ["docker", "exec", PG, "sh"],
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
    assert ["docker", "network", "create", "--internal"] == fake.calls[0][:4]
    runs = [c for c in fake.calls if c[1] == "run" and "odoo:17" in c]
    assert runs and all(set(g.ODOO_HARDEN) <= set(c) for c in runs)


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
    dbs = [{c[c.index("-d") + 1] for c in f.calls if "odoo:17" in c} for f in (a, b)]
    assert dbs[0] and not dbs[0] & dbs[1]
    assert all(g.DB_RE.fullmatch(d) for d in dbs[0] | dbs[1])


def test_access_diff_and_snapshot_diff_units():
    spec = {("m.model_a", "m.group_a"): (1, 1, 0, 0)}
    assert g.access_diff(spec, [["a", "m.model_a", "m.group_a", "1", "1", "0", "0"]]) == []
    assert g.access_diff(spec, [])  # declared row missing
    assert g.access_diff(spec, [["a", "m.model_a", "m.group_a", "1", "1", "1", "0"]])
    assert g.access_diff(spec, [["x"]])
    assert (
        g.access_diff(
            spec,
            [
                ["a", "m.model_a", "m.group_a", "1", "1", "0", "0"],
                ["r", "m.model_a", "", "1", "1", "1", "1"],
            ],
        )
        == []
    )
    s0 = ({("t", "id")}, dict.fromkeys(g.COUNT_TABLES, 1))
    assert g.snapshot_diff(s0, s0) == []
    assert g.snapshot_diff(s0, ({("t", "id"), ("u", "id")}, s0[1]))
    assert g.snapshot_diff(s0, ({("t", "id"), ("t", "x")}, s0[1]))
