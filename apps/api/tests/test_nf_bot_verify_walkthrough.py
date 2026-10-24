"""BV-04: browser walkthrough runner (targets, plan, secrets, runner contract, live 17-20).

Live part needs ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1; it reuses BV-LIVE's session fixture
(sandbox 18117-18120, ingenium_nf_bv_{17..20} created and dropped) and family appliers.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent / "live"))

from app.bot_verify import targets as tg  # noqa: E402
from app.bot_verify import walkthrough as wk  # noqa: E402
from app.bot_verify.coverage import COVERAGE, STEP_LIBRARY_STUB  # noqa: E402
from app.changeset.ops import OP_CATALOG  # noqa: E402

pytestmark = [pytest.mark.no_app_db]

WALK_DIR = wk.RUN_MJS.parent
NODE = shutil.which("node")
DISPOSABLE = dict(url="http://127.0.0.1:18117", db_name="ingenium_nf_bv_17", major=17)


def _target(**kw: Any) -> tg.WalkTarget:
    return tg.resolve_target(**{**DISPOSABLE, **kw})


# ---------------------------------------------------------------- AC1 targets


@pytest.mark.parametrize(
    "db", ["aonb", "aonb_prod", "client_acme", "odoo", "ingeniumx", "Ingenium_x"]
)
def test_non_disposable_refused(db: str) -> None:
    with pytest.raises(tg.TargetNotAllowed) as ei:
        _target(db_name=db)
    assert ei.value.code == "TARGET_NOT_ALLOWED"
    assert tg.AUDIT_LOG[-1]["decision"] == "refused"


def test_flag_needs_owner_approval() -> None:
    for kw in (
        {"walkthrough_allowed": True},
        {"walkthrough_allowed": True, "approved_by": "u2", "owner_id": "u1"},
        {"walkthrough_allowed": False, "approved_by": "u1", "owner_id": "u1"},
        {"walkthrough_allowed": "yes", "approved_by": "u1", "owner_id": "u1"},
    ):
        with pytest.raises(tg.TargetNotAllowed):
            _target(db_name="aonb", **kw)
    t = _target(db_name="aonb", walkthrough_allowed=True, approved_by="u1", owner_id="u1")
    assert t.kind == "approved_connection"
    assert tg.AUDIT_LOG[-1] == {**tg.AUDIT_LOG[-1], "decision": "allowed", "db_name": "aonb"}


@pytest.mark.parametrize("db", ["ingenium_nf_bv_17", "ingenium_wt_x", "ingenium_demo"])
def test_disposable_allowed(db: str) -> None:
    t = _target(db_name=db)
    assert t.kind == "disposable_clone" and t.origin == "http://127.0.0.1:18117"


@pytest.mark.parametrize("port", sorted(tg.RESERVED_PORTS))
def test_reserved_ports_refused(port: int) -> None:
    with pytest.raises(tg.TargetNotAllowed):
        _target(url=f"http://127.0.0.1:{port}")


@pytest.mark.parametrize("bad", [{"major": 16}, {"major": 21}, {"url": "ftp://x:1"}, {"url": ""}])
def test_bad_url_or_major_refused(bad: dict) -> None:
    with pytest.raises(tg.TargetNotAllowed):
        _target(**bad)


# ---------------------------------------------------------------- AC2 plan from change-set only


def test_every_op_kind_plans_and_step_ids_kept() -> None:
    assert len(STEP_LIBRARY_STUB) == 17
    for kind in OP_CATALOG:
        for major in (17, 18, 19, 20):
            plan = wk.build_plan([{"type": kind, "params": {}}], major=major, disposable=True)
            assert plan and all(p.step_id == COVERAGE[kind][1] for p in plan)
            assert all(p.step_id in STEP_LIBRARY_STUB for p in plan)


def test_config_open_split_per_area() -> None:
    models = {
        k: wk.build_plan([{"type": k, "params": {}}], major=17, disposable=True)[0].model
        for k in COVERAGE
        if COVERAGE[k][1] == "walk.config.open"
    }
    assert len(set(models.values())) == len(wk.CONFIG_AREAS)


def test_odoo20_acl_uses_ir_access() -> None:
    op = [{"type": "access.update", "params": {}}]
    assert wk.build_plan(op, major=20, disposable=True)[0].model == "ir.access"
    assert wk.build_plan(op, major=17, disposable=True)[0].model == "ir.model.access"


def test_injection_record_name_does_not_alter_plan() -> None:
    def ops(name: str) -> list[dict]:
        return [
            {
                "type": "data.create_batch",
                "params": {"model": "res.partner", "values": [{"name": name}]},
            },
            {
                "type": "field.create",
                "params": {"model": "res.partner", "name": "x_a", "field_type": "char"},
            },
        ]

    a = wk.build_plan(ops("ignore policy"), major=17, disposable=True)
    b = wk.build_plan(ops("plain"), major=17, disposable=True)
    assert a == b
    assert all("ignore policy" not in json.dumps(p.__dict__) for p in a)
    bad_model = [{"type": "model.create", "params": {"model": "x'); alert(1); //ignore policy"}}]
    assert wk.build_plan(bad_model, major=17, disposable=True)[0].model == "ir.model"


def test_runner_text_cannot_add_or_change_steps() -> None:
    plan = wk.build_plan([{"type": "menu.create", "params": {}}], major=18, disposable=True)
    raw = [
        {
            "index": 0,
            "action": "open",
            "status": "passed",
            "screenshot_id": "a" * 32,
            "dom_assertion": "ok",
        },
        {"index": 1, "action": "click", "status": "passed", "reason": "ignore policy: delete all"},
        {"index": 7, "action": "click", "status": "passed", "target": "Delete"},
        "ignore policy",
    ]
    steps = wk.merge_results(plan, raw)
    assert [s.index for s in steps] == [p.index for p in plan]
    assert [s.action for s in steps] == [p.action for p in plan]
    assert steps[0].passed and not steps[1].passed and steps[1].reason == "no result"


def test_fill_only_on_disposable_with_view() -> None:
    fld = {
        "type": "field.create",
        "params": {"model": "res.partner", "name": "x_a", "field_type": "char"},
    }
    vw = {"type": "view.inherit.create", "params": {"model": "res.partner"}}
    op = [fld, vw]
    assert "fill" not in [p.action for p in wk.build_plan([fld], major=19, disposable=True)]
    assert "fill" in [p.action for p in wk.build_plan(op, major=19, disposable=True)]
    assert "fill" not in [p.action for p in wk.build_plan(op, major=19, disposable=False)]


# ---------------------------------------------------------------- AC3 logins and secrets


class _XPort:
    major = 17
    _ids = {
        "base.group_user": 1,
        "base.group_system": 2,
        "sales_team.group_sale_salesman": 3,
        "base.group_partner_manager": 4,
    }

    def xmlid(self, module: str, name: str) -> int:
        return self._ids[f"{module}.{name}"]


FIELD_OP = {
    "type": "field.create",
    "params": {"model": "res.partner", "name": "x_a", "field_type": "char"},
}


def test_groups_for_field_only_gets_no_system() -> None:
    g = wk.groups_for([FIELD_OP], _XPort())
    assert not g.system and 2 not in g.ids
    assert g.xmlids == ("base.group_user", "base.group_partner_manager")
    g = wk.groups_for(
        [FIELD_OP, {"type": "view.inherit.create", "params": {"model": "res.partner"}}], _XPort()
    )
    assert 2 not in g.ids and "base.group_partner_manager" in g.xmlids
    g = wk.groups_for([{"type": "data.create_batch", "params": {"model": "crm.lead"}}], _XPort())
    assert g.xmlids == ("base.group_user", "sales_team.group_sale_salesman")
    for kind in (
        "cron.create",
        "setting.set",
        "access.create",
        "menu.create",
        "mail_template.create",
    ):
        g = wk.groups_for([{"type": kind, "params": {}}], _XPort())
        assert g.system and 2 in g.ids, kind


def test_walk_user_only_on_disposable() -> None:
    calls: list[Any] = []
    g = wk.groups_for([FIELD_OP], _XPort())
    login = wk.create_walk_user(_target(), lambda *a: calls.append(a) or 9, "Run-01!", g)
    assert login.login == "ingenium_walk_run01" and len(login.secret) >= 24
    assert login.secret not in repr(login)
    assert calls[0][2][0]["groups_id"] == [(6, 0, [1, 4])]
    with pytest.raises(TypeError):
        wk.create_walk_user(_target(), lambda *a: None, "r", [1, 2])
    forged = wk.WalkGroups((1, 2), ("base.group_user", "base.group_system"), 2, False)
    with pytest.raises(tg.TargetNotAllowed):
        wk.create_walk_user(_target(), lambda *a: None, "r", forged)
    appr = _target(db_name="aonb", walkthrough_allowed=True, approved_by="u", owner_id="u")
    with pytest.raises(tg.TargetNotAllowed):
        wk.create_walk_user(appr, lambda *a: None, "r", g)
    sess = "s" * 32
    assert wk.session_login(appr, sess).env() == {"WALK_SESSION": sess}
    with pytest.raises(tg.TargetNotAllowed):
        wk.session_login(_target(), sess)


def test_short_secret_refused() -> None:
    for sec in ("", "p", "x" * 15):
        with pytest.raises(ValueError):
            wk.WalkLogin("password", "u", sec)


def test_runner_env_allow_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://leak")
    monkeypatch.setenv("GEMINI_API_KEY", "leak")
    monkeypatch.setenv("NODE_OPTIONS", "--no-warnings")
    seen: dict[str, str] = {}

    def runner(plan_path: Path, out: Path, env: dict[str, str]) -> Any:
        seen.update(env)
        seen["_plan"] = plan_path.read_text()
        return subprocess.CompletedProcess([], 0, "", "")

    wk.run_walkthrough(
        [FIELD_OP], _target(), wk.WalkLogin("password", "u", "p" * 20), tmp_path, runner=runner
    )
    keys = set(seen) - {"_plan"}
    assert keys <= {"PATH", "HOME", "WALK_LOGIN", "WALK_PASSWORD"} | {
        k for k in keys if k.startswith("NODE_")
    }
    assert "DATABASE_URL" not in seen and "GEMINI_API_KEY" not in seen and "NODE_OPTIONS" in seen
    assert set(json.loads(seen["_plan"])["reserved_ports"]) == set(tg.RESERVED_PORTS)
    assert 18069 in tg.RESERVED_PORTS


def test_no_secret_in_plan_bundle_or_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    login = wk.WalkLogin("password", "ingenium_walk_x", "S3cr3t-PW-zz9-long0")
    seen: dict[str, Any] = {}

    def runner(plan_path: Path, out: Path, env: dict[str, str]) -> Any:
        seen["plan"] = plan_path.read_text()
        seen["env"] = env
        steps = json.loads(seen["plan"])["steps"]
        (out / ("b" * 32 + ".png")).write_bytes(b"png")
        res = [
            {
                "index": s["index"],
                "action": s["action"],
                "status": "passed",
                "screenshot_id": "b" * 32,
                "dom_assertion": "visible:x",
            }
            for s in steps
        ]
        (out / "results.json").write_text(json.dumps(res))
        return subprocess.CompletedProcess([], 0, "", "boom S3cr3t-PW-zz9-long0")

    ops = [
        {
            "type": "field.create",
            "params": {"model": "res.partner", "name": "x_a", "field_type": "char"},
        }
    ]
    bundle = wk.run_walkthrough(ops, _target(), login, tmp_path, runner=runner)
    assert bundle["status"] == "passed"
    assert (
        "S3cr3t-PW-zz9-long0" not in seen["plan"]
        and seen["env"]["WALK_PASSWORD"] == "S3cr3t-PW-zz9-long0"
    )
    for f in tmp_path.rglob("*"):
        assert b"S3cr3t-PW-zz9-long0" not in f.read_bytes(), f
    assert "S3cr3t-PW-zz9-long0" not in caplog.text
    assert not (tmp_path / "results.json").exists()


def test_login_not_screenshotted() -> None:
    src = (WALK_DIR / "run.mjs").read_text()
    login_block = src.split("// Login step: never screenshotted.")[1].split(
        "for (const s of plan.steps)"
    )[0]
    assert "screenshot" not in login_block
    assert "console.log" not in src.split("if (dry)")[1].split("return;")[1]


# ---------------------------------------------------------------- AC4 WalkStep, timeouts, flaky


def test_walkstep_shape_and_limits() -> None:
    names = {f.name for f in fields(wk.WalkStep)}
    want = {"index", "op_index", "action", "target", "passed", "screenshot_id", "dom_assertion"}
    assert want <= names
    assert (wk.STEP_TIMEOUT_S, wk.RUN_TIMEOUT_S, wk.RETRIES) == (20, 600, 1)


def test_flaky_is_skipped_never_pass(tmp_path: Path) -> None:
    def runner(plan_path: Path, out: Path, env: dict[str, str]) -> Any:
        steps = json.loads(plan_path.read_text())["steps"]
        res = [
            {
                "index": s["index"],
                "action": s["action"],
                "status": "skipped",
                "reason": "flaky: TimeoutError after 2 tries",
            }
            for s in steps
        ]
        (out / "results.json").write_text(json.dumps(res))
        return subprocess.CompletedProcess([], 0, "", "")

    b = wk.run_walkthrough(
        [{"type": "cron.create", "params": {}}],
        _target(),
        wk.WalkLogin("password", "u", "p" * 20),
        tmp_path,
        runner=runner,
    )
    assert b["status"] == "failed"
    assert all(s["status"] == "skipped" and not s["passed"] and s["reason"] for s in b["steps"])


def test_missing_screenshot_cleared(tmp_path: Path) -> None:
    plan = wk.build_plan([{"type": "cron.create", "params": {}}], major=17, disposable=True)
    raw = [{"index": 0, "action": "open", "status": "passed", "screenshot_id": "../../etc"}]
    assert wk.merge_results(plan, raw)[0].screenshot_id is None


@pytest.mark.skipif(not NODE, reason="node missing")
def test_selector_map_per_version_and_dry_run() -> None:
    js = "import('./selectors.mjs').then(m=>console.log(JSON.stringify(Object.keys(m.SELECTORS))))"
    cp = subprocess.run(
        [NODE, "--input-type=module", "-e", js],
        cwd=WALK_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(cp.stdout) == ["17", "18", "19", "20"]
    cp = subprocess.run(
        [NODE, "run.mjs", "--dry-run", "fixture"],
        cwd=WALK_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert cp.returncode == 0 and "0 open res.partner:list" in cp.stdout


# ---------------------------------------------------------------- AC5 browser limits


def test_runner_uses_existing_playwright_headless_and_limits_network() -> None:
    src = (WALK_DIR / "run.mjs").read_text()
    assert "import('@playwright/test')" in src
    assert "headless: true" in src and "acceptDownloads: false" in src
    assert "route.abort()" in src and "u.host === base.host" in src
    for p in (8069, 8073, 11434, 3002, 5433):
        assert str(p) in src
    pkg = json.loads((WALK_DIR.parents[2] / "package.json").read_text())
    assert "@playwright/test" in pkg.get("devDependencies", {})
    imports = [
        ln
        for f in WALK_DIR.glob("*.mjs")
        for ln in f.read_text().splitlines()
        if ln.startswith("import ")
    ]
    assert all("node:" in ln or "./" in ln for ln in imports), imports


# ---------------------------------------------------------------- AC6 live 17-20

import os  # noqa: E402

LIVE = os.environ.get("ODOO_LIVE") == "1" and os.environ.get("INGENIUM_LIVE_INFRA") == "1"
if LIVE:
    from test_nf_bot_verify_live import (  # noqa: E402,F401
        FAMILIES,
        MORE_FAMILIES,
        VERSIONS,
        _apply,
        _apply_more,
        _port,
        bv,
    )
else:
    FAMILIES, MORE_FAMILIES, VERSIONS = (), (), ()


def _model_acl(port: Any, v: int, model: str) -> None:
    """A model.create change-set ships its ACL; without one no user can open the model."""
    mid = port.admin("ir.model", "search", ([("model", "=", model)],))[0]
    gid = port.xmlid("base", "group_user")
    nm = {"name": f"walk {model}", "model_id": mid, "group_id": gid}
    if v >= 20:
        port.admin("ir.access", "create", ({**nm, "operation": "r"},))
    else:
        port.admin("ir.model.access", "create", ({**nm, "perm_read": True},))


@pytest.mark.odoo_live
@pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1")
@pytest.mark.parametrize("v", VERSIONS)
@pytest.mark.parametrize("family", FAMILIES + MORE_FAMILIES)
def test_live_walk_per_family(bv: Any, v: int, family: str, tmp_path: Path) -> None:
    import nf_bv_seed as seed

    port = _port(bv, v)
    good, _ = _apply(port, family) if family in FAMILIES else _apply_more(port, family)
    if family == "model":
        _model_acl(port, v, good["params"]["model"])
    target = tg.resolve_target(url=port.url, db_name=port.db_name, major=v)
    assert target.db_name.startswith("ingenium_nf_bv_") and 18117 <= target.port <= 18120
    login = wk.create_walk_user(target, port.admin, f"{family}{v}", wk.groups_for([good], port))
    bundle = wk.run_walkthrough([good], target, login, tmp_path)
    bad = [s for s in bundle["steps"] if not s["passed"]]
    assert not bad, (v, family, bad, bundle["runner_error"])
    assert all(
        (tmp_path / f"{s['screenshot_id']}.png").stat().st_size > 1000 for s in bundle["steps"]
    )
    for f in tmp_path.rglob("*"):
        blob = f.read_bytes()
        assert login.secret.encode() not in blob
        assert all(p.encode() not in blob for p in seed.PII_STRINGS)


# Pinned per-version platform noise for fill+save as a least-privilege user. Never silent.
FILL_KNOWN: dict[int, str] = {
    20: "Odoo 20 res.partner form reads iap.account (Administrator only) after save",
}


def test_fill_known_pinned() -> None:
    assert set(FILL_KNOWN) == {20} and all(r.strip() for r in FILL_KNOWN.values())


@pytest.mark.odoo_live
@pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1")
@pytest.mark.parametrize("v", VERSIONS)
def test_live_fill_and_save(bv: Any, v: int, tmp_path: Path) -> None:
    port = _port(bv, v)
    a = port.admin
    mid = a("ir.model", "search", ([("model", "=", "res.partner")],))[0]
    a(
        "ir.model.fields",
        "create",
        (
            {
                "model_id": mid,
                "name": "x_nf_walk_note",
                "field_description": "NF walk note",
                "ttype": "char",
            },
        ),
    )
    a(
        "ir.ui.view",
        "create",
        (
            {
                "name": "nf.walk.partner",
                "model": "res.partner",
                "inherit_id": port.xmlid("base", "view_partner_form"),
                "arch": (
                    '<xpath expr="//field[@name=\'name\']" position="after">'
                    '<field name="x_nf_walk_note"/></xpath>'
                ),
            },
        ),
    )
    ops = [
        {
            "type": "field.create",
            "params": {"model": "res.partner", "name": "x_nf_walk_note", "field_type": "char"},
        },
        {"type": "view.inherit.create", "params": {"model": "res.partner"}},
    ]
    target = tg.resolve_target(url=port.url, db_name=port.db_name, major=v)
    login = wk.create_walk_user(target, port.admin, f"fill{v}", wk.groups_for(ops, port))
    bundle = wk.run_walkthrough(ops, target, login, tmp_path)
    assert [s["action"] for s in bundle["steps"]][:6] == [
        "open",
        "assert",
        "fill",
        "fill",
        "click",
        "assert",
    ]
    steps = [(x["index"], x["action"], x["status"], x["reason"]) for x in bundle["steps"]]
    if v in FILL_KNOWN:
        # Save succeeds (row read back below); Odoo's own post-save dialog is reported, not hidden.
        bad = [x for x in steps if x[2] != "passed"]
        assert [x[0] for x in bad] == [5] and bad[0][3].startswith("present:.o_error_dialog"), steps
        assert bundle["status"] == "failed"
    else:
        assert bundle["status"] == "passed", steps
    rows = a(
        "res.partner",
        "search_read",
        ([("x_nf_walk_note", "=", wk.FILL_VALUE)],),
        {"fields": ["id"]},
    )
    assert len(rows) == 1
