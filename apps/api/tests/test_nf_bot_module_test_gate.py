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
    def __init__(self, tmp, **over):
        self.tmp, self.over, self.calls = str(Path(tmp).resolve()), over, []

    def run(self, argv, *, stdin=None, timeout=900):
        g.validate_argv(argv, self.tmp)
        self.calls.append(list(argv))
        o = self.over
        if "boom" in o:
            raise RuntimeError("x")
        if argv[1] != "run" or "postgres:16" in argv:
            return g.RunResult(o.get("infra_rc", 0), "")
        if "shell" in argv:
            d = {
                "before": "installed",
                "after": "uninstalled",
                "xmlids": 0,
                "models": 0,
                "tables": [],
                "n_models": 1,
            }
            d.update(o.get("uninstall", {}))
            return g.RunResult(0, o.get("uninstall_out", "GATE_RESULT " + json.dumps(d)))
        if "--test-enable" in argv:
            return g.RunResult(
                0,
                o.get(
                    "tests_out",
                    LOADED + "test_access_x_asset_keeper ok\n"
                    "INFO odoo.tests.stats: 0 failed, 0 error(s) of 2 tests\n",
                ),
            )
        if "gate_upg" in argv and "-u" in argv:
            return g.RunResult(0, o.get("upgrade_out", LOADED))
        return g.RunResult(0, o.get("install_out", LOADED))


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
    assert rep.verdict == g.PASS and rep.signature and g.gate_passed(rep, mh)
    assert g.gate_passed(json.loads(json.dumps(rep.to_dict())), mh)  # stored as JSON
    assert list(tmp_path.iterdir()) == []  # work dir removed


def test_upgrade_na_only_without_prior(tmp_path):
    rep, mh = gate(tmp_path)
    assert rep.checks["upgrade"].status == g.NA and g.gate_passed(rep, mh)
    d = rep.to_dict()
    d["prior_hash"] = "0" * 64
    assert not g.gate_passed(d, mh)


def test_no_sandbox_is_unverified_never_pass(tmp_path):
    fs = files(NEW)
    rep = g.run_gate(fs, module=MOD, version=17, runner=None)
    assert all(rep.checks[c].status == g.UNVERIFIED for c in g.CHECKS[1:])
    assert rep.verdict == g.FAIL and not g.gate_passed(rep, g.module_hash(fs))


def test_sandbox_failures_fail_closed(tmp_path):
    for over in ({"boom": 1}, {"infra_rc": 1}):
        rep, mh = gate(tmp_path, **over)
        assert rep.verdict == g.FAIL and not g.gate_passed(rep, mh)
        assert rep.checks["install"].status == g.UNVERIFIED


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
        ({"tests_out": LOADED}, "tests", g.UNVERIFIED),
        ({"tests_out": LOADED + "1 failed, 0 error(s) of 2 tests\n"}, "tests", g.FAIL),
        ({"tests_out": LOADED + "0 failed, 0 error(s) of 1 tests\n"}, "tests", g.FAIL),
        ({"tests_out": LOADED + "0 failed, 0 error(s) of 2 tests\n"}, "access", g.UNVERIFIED),
        ({"uninstall": {"tables": ["x_asset"]}}, "uninstall", g.FAIL),
        ({"uninstall": {"xmlids": 3}}, "uninstall", g.FAIL),
        ({"uninstall": {"after": "to remove"}}, "uninstall", g.FAIL),
        ({"uninstall_out": "Traceback"}, "uninstall", g.UNVERIFIED),
    ],
)
def test_each_check_fails_closed(tmp_path, over, check, status):
    rep, mh = gate(tmp_path, **over)
    assert rep.checks[check].status == status and not g.gate_passed(rep, mh)


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
    assert rep.checks["upgrade"].status == g.FAIL and not g.gate_passed(rep, mh)


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
    assert not g.gate_passed(d, mh)


def test_gate_passed_never_raises_and_needs_key(tmp_path, monkeypatch):
    rep, mh = gate(tmp_path)
    for junk in (None, 1, "x", [], {"signature": 5}):
        assert g.gate_passed(junk, mh) is False
    assert not g.gate_passed(rep, None) and not g.gate_passed(rep, "0" * 64)
    monkeypatch.setenv(g.KEY_ENV, "other" * 10)
    assert not g.gate_passed(rep, mh)  # signed with another key
    monkeypatch.delenv(g.KEY_ENV)
    assert not g.gate_passed(rep, mh)
    rep2, mh2 = gate(tmp_path)
    assert rep2.verdict == g.FAIL and not rep2.signature and not g.gate_passed(rep2, mh2)


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


T = "/tmp/w"
OK_RUN = [
    "docker",
    "run",
    "--rm",
    "--network",
    "ingate-0123456789ab-net",
    "-e",
    "HOST=x",
    "-v",
    f"{T}/ingate-x/new:/mnt/extra-addons:ro",
    "odoo:17",
    "odoo",
    "-d",
    "gate_main",
]


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
        [x.replace("HOST=x", "LD_PRELOAD=x") for x in OK_RUN],
        [x.replace("ingate-0123456789ab-net", "client-net") for x in OK_RUN],
        OK_RUN + ["x; rm -rf /"],
        OK_RUN + ["$(id)"],
        [x for x in OK_RUN if x not in ("--network", "ingate-0123456789ab-net")],
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


def test_real_runner_needs_live(monkeypatch):
    monkeypatch.delenv("ODOO_LIVE", raising=False)
    with pytest.raises(g.GateError):
        g.DockerRunner()
    monkeypatch.setenv("ODOO_LIVE", "1")
    monkeypatch.setenv("DOCKER_HOST", "tcp://prod:2375")
    with pytest.raises(g.GateError):
        g.DockerRunner()


def test_logs_redacted(tmp_path):
    out = LOADED + "1 ERROR gate x: password=hunter2secret\n0 failed, 0 error(s) of 2 tests\n"
    rep, _ = gate(tmp_path, tests_out=out)
    assert "hunter2secret" not in json.dumps(rep.to_dict())


def test_t3_switch_not_flipped():
    assert tiers.tier_ready(tiers.T3) is False
    assert tiers.REQUIRED[tiers.T3] == ("module-authoring", "module-test-gate")
    assert len(g.T3_SWITCH_PRECONDITIONS) >= 4
