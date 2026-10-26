"""BOT-MODULE-AUTHORING: orchestration to a reviewable, never-applied result (fake runner)."""

from __future__ import annotations

import ast
import copy
import importlib
import inspect
from pathlib import Path

import pytest
from test_nf_bot_module_test_gate import KEY, Fake
from test_nf_bot_req2mod import ASSETS

from app.bots import code_audit as ca
from app.bots import module_authoring as ma
from app.bots import module_test_gate as g
from app.bots import owned_change as oc
from app.bots import tiers as tt

CTX = {"owner": "owner-1", "purpose": "asset register"}
MOD = "x_assets"


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(g.KEY_ENV, KEY)


def run(tmp_path, req=ASSETS, **kw):
    kw.setdefault("runner", Fake(tmp_path))
    kw.setdefault("tmp_root", str(tmp_path))
    return ma.author(
        copy.deepcopy(req),
        version=kw.pop("version", 17),
        owner_context=kw.pop("ctx", CTX),
        technical_name=kw.pop("name", MOD),
        **kw,
    )


def drop_access(files):
    files["security/ir.model.access.csv"] = (
        files["security/ir.model.access.csv"].split(b"\n")[0] + b"\n"
    )
    return files


# AC1 happy path: requirement -> promotable result with all parts
def test_happy_path_promotable(tmp_path):
    r = run(tmp_path)
    assert r.ok and r.stage == "done" and r.promotable and r.stop_reason == "passed", r.to_dict()
    assert r.module_hash == g.module_hash(r.files)
    assert g.gate_passed(r.gate_report, r.module_hash, version=17, module=MOD)
    assert r.audit_counts["high"] == r.audit_counts["medium"] == 0
    assert r.trace and all(isinstance(v, list) for v in r.trace.values())
    assert r.change_sets == [] and r.attempts == [] and r.applied is False
    plan = r.approval_plan()
    assert plan["tier"] == "L3" and plan["module_hash"] == r.module_hash and plan["promotable"]


@pytest.mark.parametrize("v", [17, 18, 19, 20])
def test_every_version(tmp_path, v):
    r = run(tmp_path, version=v)
    assert r.ok and r.version == v


# AC promotable is exactly gate_passed
def test_promotable_is_gate_passed_only(tmp_path, monkeypatch):
    assert not run(tmp_path, runner=None).promotable  # sandbox unavailable -> unverified
    monkeypatch.delenv(g.KEY_ENV)
    r = run(tmp_path)
    assert not r.promotable and not g.gate_passed(
        r.gate_report, r.module_hash, version=17, module=MOD
    )


def test_tampered_result_not_promotable(tmp_path):
    r = run(tmp_path)
    rep = copy.deepcopy(r.gate_report)
    rep["checks"]["tests"]["status"] = "fail"
    assert not g.gate_passed(rep, r.module_hash, version=17, module=MOD)
    assert not g.gate_passed(r.gate_report, "0" * 64, version=17, module=MOD)
    assert not g.gate_passed(r.gate_report, r.module_hash, version=19, module=MOD)
    assert not g.gate_passed(r.gate_report, r.module_hash)


# AC repair loop
def test_repair_restores_seeded_defect(tmp_path):
    r = run(tmp_path, seed=drop_access)
    assert r.promotable and r.stop_reason == "passed", r.to_dict()
    assert len(r.change_sets) == 1 and r.attempts[0].outcome == "adopted"
    cs = r.change_sets[0]
    assert cs["files"] == ["security/ir.model.access.csv"] and cs["tier"] == "L3"
    assert "+access_" in cs["diff"]


def test_repair_no_repair_stops(tmp_path):
    r = run(tmp_path, runner=Fake(tmp_path, install_out="ERROR boom\n"))
    assert r.ok and not r.promotable and r.stop_reason == "no-repair"
    assert len(r.attempts) == 1 and not r.change_sets


def test_repair_non_improving_stops(tmp_path):
    def useless(ctx):
        return [
            oc.Edit(
                "doc/n.md",
                "add_file" if "doc/n.md" not in ctx["files"] else "replace_file",
                f"{len(ctx['files'])}\n",
            )
        ]

    r = run(tmp_path, runner=Fake(tmp_path, install_out="ERROR boom\n"), repairer=useless)
    assert not r.promotable and r.attempts[-1].outcome in ("non-improving", "repeated-failure")
    assert len(r.attempts) == 1 and r.change_sets == []  # rejected attempt not adopted


def test_repair_repeated_failure_stops(tmp_path, monkeypatch):
    # improves the score once (audit) but leaves the same gate failure -> second is repeated
    calls = []

    def flip(ctx):
        calls.append(1)
        return [
            oc.Edit(
                "doc/n.md",
                "add_file" if "doc/n.md" not in ctx["files"] else "replace_file",
                f"{len(calls)}\n",
            )
        ]

    scores = iter([(2, 0), (1, 0), (1, 0)])
    keys = iter([("a",), ("b",), ("b",), ("b",)])
    monkeypatch.setattr(ma, "_score", lambda rep, aud: next(scores))
    monkeypatch.setattr(ma, "_key", lambda rep, aud: next(keys))
    r = run(
        tmp_path, runner=Fake(tmp_path, install_out="ERROR boom\n"), repairer=flip, max_attempts=5
    )
    assert [a.outcome for a in r.attempts] == ["adopted", "repeated-failure"]
    assert len(r.change_sets) == 1 and not r.promotable


def test_max_attempts_bound(tmp_path, monkeypatch):
    n = iter(range(100))
    monkeypatch.setattr(ma, "_score", lambda rep, aud: (100 - next(n), 0))
    monkeypatch.setattr(ma, "_key", lambda rep, aud: (object(),))

    def edit(ctx):
        return [
            oc.Edit(
                "doc/n.md",
                "add_file" if "doc/n.md" not in ctx["files"] else "replace_file",
                f"{len(ctx['files'])}{id(ctx)}\n",
            )
        ]

    r = run(
        tmp_path, runner=Fake(tmp_path, install_out="ERROR boom\n"), repairer=edit, max_attempts=2
    )
    assert len(r.attempts) == 2 and r.stop_reason == "max-attempts" and not r.promotable
    assert (
        run(tmp_path, runner=Fake(tmp_path, install_out="ERROR boom\n"), max_attempts=0).stop_reason
        == "no-attempts-allowed"
    )


@pytest.mark.parametrize("bad", [-1, 6, 2.0, "3", True])
def test_max_attempts_validated(tmp_path, bad):
    r = run(tmp_path, max_attempts=bad)
    assert not r.ok and r.stage == "input"


@pytest.mark.parametrize("path", ["../evil.py", "/etc/passwd", ".git/config"])
def test_repair_outside_module_refused(tmp_path, path):
    r = run(tmp_path, seed=drop_access, repairer=lambda ctx: [oc.Edit(path, "add_file", "x\n")])
    assert r.attempts[0].outcome.startswith("refused:") and not r.promotable
    assert not r.change_sets


def test_repair_that_adds_danger_refused(tmp_path):
    r = run(
        tmp_path,
        seed=drop_access,
        repairer=lambda ctx: [
            oc.Edit("__init__.py", "replace_file", "import os as o\no.system('id')\n")
        ],
    )
    assert r.attempts[0].outcome == "refused:audit-regression" and not r.promotable


def test_every_repair_regated(tmp_path):
    fake = Fake(tmp_path)
    run(tmp_path, runner=fake, seed=drop_access)
    pg_starts = [c for c in fake.calls if c[1] == "run" and "postgres:16" in c]
    assert len(pg_starts) >= 1  # gate ran on the repaired module (seeded one skips sandbox)


def test_repair_change_set_reverifiable(tmp_path):
    r = run(tmp_path, seed=drop_access)
    gen = ma._files_of(
        ma.build_module_zip(
            ma.rm.build(
                copy.deepcopy(ASSETS), version=17, installed_modules=["base"], technical_name=MOD
            ).spec,
            odoo_major=17,
        )
    )
    assert r.files == gen  # restored exactly to the generator output


# AC input validation / fail closed
@pytest.mark.parametrize(
    "ctx",
    [
        None,
        {},
        {"purpose": "x"},
        {"owner": ""},
        {"owner": "a\nb"},
        {"owner": "a", "evil": "x"},
        {"owner": 1},
    ],
)
def test_owner_context_validated(tmp_path, ctx):
    r = run(tmp_path, ctx=ctx)
    assert not r.ok and r.stage == "input"


def test_owner_context_redacted(tmp_path):
    r = run(tmp_path, ctx={"owner": "o", "decision": "ok password=Zz9SecretQ"})
    assert "Zz9SecretQ" not in str(r.to_dict())


@pytest.mark.parametrize("v", [16, 21, "17", 17.0, None])
def test_bad_version(tmp_path, v):
    r = run(tmp_path, version=v)
    assert not r.ok and r.stage == "input"


def test_bad_requirement_stops_at_spec(tmp_path):
    r = run(tmp_path, req={"name": "x"})
    assert not r.ok and r.stage == "spec" and r.error and not r.promotable


@pytest.mark.parametrize("name", ["sale", "Bad", "x_" + "a" * 60, "../x", None])
def test_bad_name_refused(tmp_path, name):
    r = run(tmp_path, name=name)
    assert not r.ok and not r.promotable


def test_never_raises_on_crashing_seed(tmp_path):
    def boom(files):
        raise RuntimeError("x")

    r = run(tmp_path, seed=boom)
    assert not r.ok and r.stage == "build"


def test_no_scratch_left(tmp_path):
    run(tmp_path, seed=drop_access)
    assert not list(Path(tmp_path).glob("inauthor-*"))


def test_never_applies_or_installs():
    src = inspect.getsource(ma)
    for bad in (
        "xmlrpc",
        "jsonrpc",
        "execute_kw",
        "requests.",
        "subprocess",
        "button_immediate_install",
    ):
        assert bad not in src
    assert "applied: bool = False" in src


# AC readiness + capability derivation without flipping anything
def test_authoring_ready_offline():
    r = ma.authoring_ready(17)
    assert r["prerequisites"] == dict.fromkeys(
        ("req2mod", "code_audit", "owned_change", "module_test_gate", "debug_notes"), True
    )
    assert r["all_met"] is True and r["reviewed_flag"] is False and r["capability"] is False
    assert len(r["human"]) >= len(g.T3_SWITCH_PRECONDITIONS) + 4


def test_authoring_ready_reports_broken_prerequisite(monkeypatch):
    monkeypatch.setattr(ma.dn, "match", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    r = ma.authoring_ready(17)
    assert r["prerequisites"]["debug_notes"] is False and not r["all_met"]


def test_review_flag_false_and_tiers_unchanged():
    assert tt.MODULE_AUTHORING_REVIEWED is False
    assert tt._CAPABILITIES["module-authoring"] is False
    assert tt._CAPABILITIES["module-test-gate"] is False
    assert tt.REQUIRED[tt.T3] == ("module-authoring", "module-test-gate")
    assert not tt.tier_ready(tt.T3)


@pytest.mark.parametrize("met", [True, 1, "true", "yes", object()])
def test_derived_capability_needs_human_flag(met):
    assert ma.derived_capability(met) is False


def test_flag_cannot_be_flipped_by_env_or_input(monkeypatch):
    for k in ("MODULE_AUTHORING_REVIEWED", "INGENIUM_MODULE_AUTHORING_REVIEWED", "T3", "ODOO_LIVE"):
        monkeypatch.setenv(k, "1")
    importlib.reload(tt)
    try:
        assert tt.MODULE_AUTHORING_REVIEWED is False
        assert ma.authoring_ready(17)["capability"] is False
    finally:
        importlib.reload(tt)
    tree = ast.parse(Path(tt.__file__).read_text())
    assigns = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "MODULE_AUTHORING_REVIEWED" for t in n.targets)
    ]
    assert (
        len(assigns) == 1
        and isinstance(assigns[0].value, ast.Constant)
        and assigns[0].value.value is False
    )
    src = Path(tt.__file__).read_text()
    assert "os.environ" not in src and "getenv(" not in src and "import os" not in src


def test_audit_counts_match_final_files(tmp_path):
    r = run(tmp_path, seed=drop_access)
    assert ca.audit(oc._zip(MOD, r.files), version=17, owned_names={MOD}).counts == r.audit_counts
