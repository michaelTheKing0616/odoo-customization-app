"""BV-05: business flows on a disposable clone (offline oracle + live 17-20).

Live tests need ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1. They use only the
sandbox stacks (18117-18120): the source ingenium_nf_bv_{v} DB is created,
seeded and dropped by the fixture; every ingenium_nf_bv_clone_* clone is
created and dropped by run_flows (drop asserted).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent / "live"))

from app.bot_verify import flows as fl  # noqa: E402
from app.bot_verify.flow_library import (  # noqa: E402
    FLOWS,
    REQUIRED_APPS,
    Flow,
    FlowStep,
    flows_for,
    touched_apps,
)
from app.bot_verify.targets import TargetNotAllowed  # noqa: E402
from app.changeset import verify as verify_mod  # noqa: E402

pytestmark = [pytest.mark.no_app_db]

LIVE = os.environ.get("ODOO_LIVE") == "1" and os.environ.get("INGENIUM_LIVE_INFRA") == "1"
VERSIONS = tuple(
    int(x) for x in os.environ.get("NF_BV_VERSIONS", "17,18,19,20").split(",") if x.strip()
)
ALL_APPS = set(REQUIRED_APPS)
R2_OP = {
    "type": "field.create",
    "params": {"model": "sale.order", "name": "x_a", "field_type": "char"},
}
R1_OP = {"type": "view.inherit.update", "params": {"model": "sale.order"}}


@pytest.fixture(autouse=True)
def _iso() -> Any:
    verify_mod.reset_verification_log()
    yield
    verify_mod.reset_verification_log()


# ---------------------------------------------------------------- AC1 ---
def test_required_apps_have_flows() -> None:
    assert REQUIRED_APPS <= set(FLOWS)
    for app in REQUIRED_APPS:
        assert FLOWS[app] and all(f.steps for f in FLOWS[app])


@pytest.mark.parametrize(
    ("model", "app"),
    [
        ("sale.order", "sale"),
        ("purchase.order", "purchase"),
        ("account.move", "account"),
        ("stock.picking", "stock"),
        ("hr.leave", "hr_holidays"),
        ("crm.lead", "crm"),
        ("project.task", "project"),
    ],
)
def test_touched_app_maps_to_flow(model: str, app: str) -> None:
    ops = [
        {"type": "field.create", "params": {"model": model, "name": "x_y", "field_type": "char"}}
    ]
    got = flows_for(ops, ALL_APPS)
    assert got and {f.app for f in got} == {app}


def test_module_install_and_not_installed() -> None:
    ops = [{"type": "module.install", "params": {"name": "stock"}}, R2_OP]
    assert touched_apps(ops) == {"stock", "sale"}
    assert {f.app for f in flows_for(ops, {"stock"})} == {"stock"}
    assert flows_for([{"type": "field.create", "params": {"model": "res.partner"}}], ALL_APPS) == []


# ---------------------------------------------------------------- fakes ---
@dataclass
class FakePort:
    db_name: str
    major: int = 17
    rows: dict[tuple[str, int], dict] = field(default_factory=dict)

    def admin(self, model: str, method: str, args: Any = (), kwargs: Any = None) -> Any:
        assert method == "read"
        ids, names = args
        return [{n: self.rows[(model, i)].get(n) for n in names} for i in ids]

    def xmlid(self, module: str, name: str) -> int:
        return {"group_system": 1, "group_user": 2}.get(name, 10 + len(name))


def _flow(app: str, *vals: Any, boom: bool = False) -> Flow:
    def mk(i: int, v: Any) -> FlowStep:
        def run(port: FakePort, c: dict) -> tuple[str, int]:
            if boom and i == 1:
                raise RuntimeError("ValidationError\nMissing required field x_nf_req")
            port.rows[("m.x", i)] = {"state": v}
            return "m.x", i

        return FlowStep(f"s{i}", run, "state", ("ok",))

    return Flow(app, "f", tuple(mk(i, v) for i, v in enumerate(vals)))


class Clones:
    def __init__(self, port_db: str | None = None) -> None:
        self.made: list[str] = []
        self.dropped: list[str] = []
        self.port_db = port_db

    def make(self, src: str, name: str) -> FakePort:
        self.made.append(name)
        return FakePort(self.port_db or name)

    def drop(self, name: str) -> None:
        self.dropped.append(name)

    def exists(self, name: str) -> bool:
        return name in self.made and name not in self.dropped


def _run(changeset: list, flows: list[Flow], clones: Clones, walk: Any = None) -> dict:
    orig = fl.flows_for
    fl.flows_for = lambda cs, inst: flows  # type: ignore[assignment]
    try:
        return fl.run_flows(
            changeset,
            source_db="ingenium_nf_bv_17",
            installed=ALL_APPS,
            make_clone=clones.make,
            drop_clone=clones.drop,
            clone_exists=clones.exists,
            walk=walk,
        )
    finally:
        fl.flows_for = orig  # type: ignore[assignment]


# ---------------------------------------------------------------- AC2 ---
def test_source_db_refused() -> None:
    with pytest.raises(TargetNotAllowed):
        fl.require_clone(FakePort("ingenium_nf_bv_17"), "ingenium_nf_bv_17")
    with pytest.raises(TargetNotAllowed):
        fl.run_flow_steps(FakePort("ingenium_nf_bv_17"), [_flow("sale", "ok")])
    with pytest.raises(TargetNotAllowed):
        fl.require_clone(FakePort("client_prod"))
    fl.require_clone(FakePort("ingenium_nf_bv_clone_ab12"), "ingenium_nf_bv_17")


def test_clone_returning_source_is_refused_and_dropped() -> None:
    c = Clones(port_db="ingenium_nf_bv_17")
    with pytest.raises(TargetNotAllowed):
        _run([R2_OP], [_flow("sale", "ok")], c)
    assert c.made and c.dropped == c.made


def test_clone_dropped_on_pass_and_on_error() -> None:
    c = Clones()
    rep = _run([R1_OP], [_flow("sale", "ok", "ok")], c)
    assert rep["clone"].startswith("ingenium_nf_bv_clone_") and rep["clone_dropped"]
    assert c.dropped == c.made == [rep["clone"]]

    def bad_walk(port: Any, res: Any) -> list:
        raise RuntimeError("walk crashed")

    c2 = Clones()
    with pytest.raises(RuntimeError):
        _run([R1_OP], [_flow("sale", "ok")], c2, walk=bad_walk)
    assert c2.dropped == c2.made


def test_undropped_clone_raises() -> None:
    c = Clones()
    c.drop = lambda name: None  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="not dropped"):
        _run([R1_OP], [_flow("sale", "ok")], c)


# ---------------------------------------------------------------- AC3 ---
def test_all_pass_status_passed() -> None:
    rep = _run([R1_OP], [_flow("sale", "ok", "ok")], Clones())
    assert rep["status"] == "passed" and rep["layer"]["status"] == "passed"
    assert [s["status"] for s in rep["steps"]] == ["passed", "passed"]


def test_failure_at_r2_rolls_back() -> None:
    rep = _run([R2_OP], [_flow("sale", "ok", "ok", "ok", boom=True)], Clones())
    assert rep["status"] == "rolled_back" and rep["layer"]["status"] == "failed"
    assert [s["status"] for s in rep["steps"]] == ["passed", "failed", "skipped"]
    assert "x_nf_req" in rep["steps"][1]["reason"]
    assert verify_mod.recorded_rollbacks() and rep["compensations"]


def test_failure_below_r2_needs_human() -> None:
    rep = _run([R1_OP], [_flow("sale", "ok", "bad")], Clones())
    assert rep["status"] == "needs_human" and rep["runbook"] == verify_mod.RUNBOOK_VERIFY_FAILED
    assert rep["steps"][1]["status"] == "failed" and "expected" in rep["steps"][1]["reason"]
    assert not verify_mod.recorded_rollbacks()


def _bundle(*steps: tuple[int, str, str | None]) -> dict:
    return {
        "steps": [
            {
                "op_index": i,
                "action": "open",
                "status": st,
                "reason": why,
                "screenshot_id": "a" * 32,
            }
            for i, st, why in steps
        ]
    }


def test_screenshots_attached() -> None:
    res = [fl.FlowStepResult("sale", "f", "s0", "m.x", 1, "passed")]
    assert fl.attach_screenshots(res, _bundle((0, "passed", None))) == []
    assert res[0].screenshot_id == "a" * 32 and res[0].status == "passed"


def test_access_dialog_is_notice_not_rollback_even_at_r2() -> None:
    def walk(port: Any, res: list) -> list:
        return fl.attach_screenshots(
            res, _bundle((0, "failed", "present:.o_error_dialog"), (1, "passed", None))
        )

    rep = _run([R2_OP], [_flow("sale", "ok", "ok")], Clones(), walk=walk)
    assert rep["status"] == "needs_human" and not rep["compensations"]
    assert fl.NOTICE_ACCESS_DIALOG in rep["findings"] and "Saved correctly" in rep["findings"][0]
    assert not verify_mod.recorded_rollbacks()


def test_other_walk_failure_is_skipped_never_pass() -> None:
    def walk(port: Any, res: list) -> list:
        return fl.attach_screenshots(res, _bundle((0, "failed", "timeout")))

    rep = _run([R1_OP], [_flow("sale", "ok")], Clones(), walk=walk)
    assert rep["steps"][0]["status"] == "skipped" and rep["status"] == "needs_human"


def test_model_without_acl_flagged() -> None:
    cs = [{"type": "model.create", "params": {"model": "x_thing"}}]
    rep = _run(cs, [], Clones())
    assert rep["status"] == "needs_human" and "x_thing" in rep["findings"][0]
    cs.append({"type": "access.create", "params": {"model": "x_thing", "group": "base.group_user"}})
    assert fl.acl_gaps(cs) == []


def test_flow_groups_never_system() -> None:
    g = fl.flow_groups(FakePort("ingenium_nf_bv_clone_a"), ["sale", "stock"])
    assert g.system is False and g.system_gid not in g.ids and g.xmlids[0] == "base.group_user"


# ---------------------------------------------------------------- live ---
_skip = pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1")
APPS_MODULES = ("sale_management", "purchase", "account", "stock", "hr_holidays", "project")


def live(fn: Any) -> Any:
    return pytest.mark.odoo_live(_skip(fn))


def _docker(*args: str) -> str:
    cp = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=600)
    if cp.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed rc={cp.returncode}")
    return cp.stdout


class LiveClones:
    """Clone = CREATE DATABASE ... TEMPLATE source + filestore copy, on the sandbox stack only."""

    def __init__(self, seed: Any, port: Any) -> None:
        self.seed, self.src = seed, port
        self.stack = seed._stack(port.major)
        self.made: list[str] = []

    def _sql(self, sql: str) -> str:
        return _docker(
            "exec", self.stack.db_container, "psql", "-U", "odoo", "-d", "postgres", "-tAc", sql
        )

    def make(self, src: str, name: str) -> Any:
        assert fl.CLONE_RX.match(name) and src == self.src.db_name
        self.made.append(name)
        self._sql(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            f" WHERE datname = '{src}' AND pid <> pg_backend_pid()"
        )
        self._sql(f'CREATE DATABASE "{name}" TEMPLATE "{src}"')
        for _ in range(20):  # Odoo 20 needs a moment to rebuild the source registry
            try:
                self.src.admin("res.users", "search_count", ([],))
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        fs = "/var/lib/odoo/filestore"
        _docker(
            "exec",
            self.stack.odoo_container,
            "sh",
            "-c",
            f"[ -d {fs}/{src} ] && cp -r {fs}/{src} {fs}/{name} || true",
        )
        clone = self.seed.LivePort(major=self.src.major, url=self.src.url, db_name=name)
        clone.admin_uid = self.src.admin_uid
        clone._pw = dict(self.src._pw)
        clone.personas = dict(self.src.personas)
        return clone

    def drop(self, name: str) -> None:
        assert fl.CLONE_RX.match(name)
        self._sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        _docker("exec", self.stack.odoo_container, "rm", "-rf", f"/var/lib/odoo/filestore/{name}")

    def exists(self, name: str) -> bool:
        return self._sql(f"SELECT 1 FROM pg_database WHERE datname = '{name}'").strip() == "1"

    def leftovers(self) -> list[str]:
        out = self._sql(
            "SELECT datname FROM pg_database WHERE datname LIKE 'ingenium_nf_bv_clone_%'"
        )
        return [x for x in out.split() if x]


@pytest.fixture(scope="session")
def flv() -> Any:
    import nf_bv_seed as seed

    started: list[int] = []
    ports: dict[int, Any] = {}
    errors: dict[int, str] = {}

    def bring(v: int) -> None:
        if seed.stack_up(v):
            started.append(v)
        seed.wait_http(v)
        seed.create_db(v)
        port = seed.seed(v)
        ids = port.admin("ir.module.module", "search", ([("name", "in", list(APPS_MODULES))],))
        port.admin("ir.module.module", "button_immediate_install", (ids,))
        ports[v] = port

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {v: pool.submit(bring, v) for v in VERSIONS}
        for v, fut in futs.items():
            if fut.exception() is not None:
                errors[v] = type(fut.exception()).__name__ + ": " + str(fut.exception())[:300]
        yield seed, ports, errors
    finally:
        left = []
        for v in VERSIONS:
            try:
                if seed.stack_running(v):
                    if v in ports:
                        lc = LiveClones(seed, ports[v])
                        for name in lc.leftovers():
                            lc.drop(name)
                        left += lc.leftovers()
                    seed.drop_db(v)
                    if seed.db_exists(v):
                        left.append(v)
            except Exception:  # noqa: BLE001
                left.append(v)
        for v in started:
            seed.stack_down(v)
        assert not left, f"DBs not dropped: {left}"


def _get(flv: Any, v: int) -> tuple[Any, Any]:
    seed, ports, errors = flv
    if v not in ports:
        pytest.fail(f"v{v} setup failed: {errors.get(v)}")
    return seed, ports[v]


def _installed(port: Any) -> set[str]:
    rows = port.admin(
        "ir.module.module", "search_read", ([("state", "=", "installed")],), {"fields": ["name"]}
    )
    return {r["name"] for r in rows}


def _steps(rep: dict) -> list:
    return [
        (s["app"], s["step"], s["status"], s["observed"], s["reason"])
        for s in rep["steps"]
        if s["status"] != "passed"
    ]


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_live_all_flows_pass_on_clone(flv: Any, v: int, tmp_path: Path) -> None:
    seed, port = _get(flv, v)
    inst = _installed(port)
    assert REQUIRED_APPS <= inst | {"hr_holidays"} and "hr_holidays" in inst
    cs = [
        {"type": "view.inherit.update", "params": {"model": m}}
        for m in (
            "sale.order",
            "purchase.order",
            "account.move",
            "stock.picking",
            "hr.leave",
            "crm.lead",
            "project.task",
        )
    ]
    lc = LiveClones(seed, port)

    def walk(p: Any, res: list) -> list:
        return fl.walk_flow_steps(p, res, url=port.url, bundle_dir=tmp_path)

    rep = fl.run_flows(
        cs,
        source_db=port.db_name,
        installed=inst,
        make_clone=lc.make,
        drop_clone=lc.drop,
        clone_exists=lc.exists,
        walk=walk,
    )
    assert {s["app"] for s in rep["steps"]} == REQUIRED_APPS
    assert rep["status"] == "passed", (_steps(rep), rep["findings"], rep["risk"])
    assert all(s["screenshot_id"] for s in rep["steps"])
    assert all((tmp_path / f"{s['screenshot_id']}.png").exists() for s in rep["steps"])
    assert not lc.exists(rep["clone"]) and lc.leftovers() == []
    assert port.admin("sale.order", "search_count", ([],)) == 0  # source untouched


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_live_seeded_defect_fails_sale_flow(flv: Any, v: int) -> None:
    seed, port = _get(flv, v)
    lc = LiveClones(seed, port)
    defect = {
        "type": "field.create",
        "params": {
            "model": "sale.order",
            "name": "x_nf_req",
            "field_type": "char",
            "required": True,
        },
    }

    def make(src: str, name: str) -> Any:
        clone = lc.make(src, name)
        mid = clone.admin("ir.model", "search", ([("model", "=", "sale.order")],))[0]
        clone.admin(
            "ir.model.fields",
            "create",
            (
                {
                    "model_id": mid,
                    "name": "x_nf_req",
                    "ttype": "char",
                    "required": True,
                    "field_description": "NF req",
                },
            ),
        )
        return clone

    rep = fl.run_flows(
        [defect],
        source_db=port.db_name,
        installed=_installed(port),
        make_clone=make,
        drop_clone=lc.drop,
        clone_exists=lc.exists,
    )
    sale = [s for s in rep["steps"] if s["app"] == "sale"]
    assert sale[0]["status"] == "failed", _steps(rep)
    assert rep["status"] == "rolled_back" and rep["layer"]["status"] == "failed"
    assert not lc.exists(rep["clone"]) and lc.leftovers() == []


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_live_source_refused(flv: Any, v: int) -> None:
    _, port = _get(flv, v)
    with pytest.raises(TargetNotAllowed):
        fl.run_flow_steps(port, FLOWS["crm"], source_db=port.db_name)
    assert port.admin("crm.lead", "search_count", ([],)) == 0
