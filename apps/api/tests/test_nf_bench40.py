"""BENCH-40 harness tests. Never parses the sealed holdout (INV-16): only its file hash."""

from __future__ import annotations

import json
import os
from types import MappingProxyType

import pytest

from app.bots import tiers as tt
from evals.bots import bench40 as b
from evals.bots import make_bench40 as mk


@pytest.fixture
def tmp_bench(tmp_path, monkeypatch):
    for name in ("DEV", "HOLDOUT", "MANIFEST", "CANDIDATES"):
        monkeypatch.setattr(b, name, tmp_path / getattr(b, name).name)
    b.DEV.write_text("[]")
    b.HOLDOUT.write_text("[]")
    b.CANDIDATES.write_text("")
    b.seal()
    return tmp_path


def test_split_deterministic_and_dev_matches_hash():
    assert b.split_of("x") == b.split_of("x")
    dev = b.load("dev")
    assert dev and all(b.split_of(t["id"]) == "dev" for t in dev)


def test_holdout_sealed(monkeypatch):
    monkeypatch.delenv("EVAL_UNSEAL", raising=False)
    with pytest.raises(b.Sealed):
        b.load("holdout")


def test_manifest_pins_holdout_bytes():
    m = json.loads(b.MANIFEST.read_text())
    assert b.file_sha(b.HOLDOUT) == m["sha256"]
    assert m["count"] + len(b.load("dev")) == 40


def test_tampered_holdout_refused(tmp_bench, monkeypatch):
    b.HOLDOUT.write_text("[1]")
    monkeypatch.setenv("EVAL_UNSEAL", "yes")
    with pytest.raises(b.Sealed):
        b.load("holdout")


def test_generator_shape_quarter_boundary_and_neutral():
    ids = [t["id"] for t in mk.TASKS]
    assert len(ids) == 40 == len(set(ids))
    boundary = [t for t in mk.TASKS if t["expect"] != "ok" or "until_capability" in t]
    assert 9 <= len(boundary) <= 12
    grades = {
        g
        for t in boundary
        for g in ([t["expect"]] if isinstance(t["expect"], str) else t["expect"].values())
    }
    assert {
        "not-built-yet",
        "approval-required",
        "needs-step",
        "needs-edition",
        "not-in-version",
        "unknown",
    } <= grades
    assert any(19 in t.get("versions", ()) for t in mk.TASKS)


@pytest.mark.parametrize("ver", [17, 20])
def test_dev_bench_passes(ver):
    tasks = [dict(t, versions=[ver]) for t in b.load("dev") if ver in t.get("versions", (17, 20))]
    r = b.run(tasks)
    assert r["n"] and r["passed"] == r["n"], r["fails"]


def test_t3_expectation_flips_when_capability_lands(monkeypatch):
    t3 = [t for t in mk.TASKS if t.get("until_capability") == 3]
    assert t3 and all(b.expected(t, 17) == "not-built-yet" for t in t3)
    on = dict(tt._CAPABILITIES, **{"module-authoring": True, "module-test-gate": True})
    monkeypatch.setattr(tt, "_CAPABILITIES", MappingProxyType(on))
    r = b.run([dict(t, versions=[17]) for t in t3])
    assert r["flipped"] == len(t3) and r["passed"] == r["n"]


def test_candidates_are_one_way(tmp_bench):
    task = {"id": "real-1", "task": "m:res.partner:create", "installed": ["base"]}
    b.append_candidate(task, source="refused-run", note="n")
    assert b.load("dev") == [] and b.HOLDOUT.read_text() == "[]"
    with pytest.raises(ValueError):
        b.append_candidate({"id": "x"}, source="s", note="n")


def test_promote_needs_reviewer_and_unseal_for_holdout(tmp_bench, monkeypatch):
    monkeypatch.delenv("EVAL_UNSEAL", raising=False)
    ids: dict[str, str] = {}
    for i in range(64):
        ids.setdefault(b.split_of(f"c{i}"), f"c{i}")
    for tid in ids.values():
        b.append_candidate({"id": tid, "task": "m:res.partner:create"}, source="s", note="n")
    with pytest.raises(PermissionError):
        b.promote(ids["dev"], reviewer=" ", expect="ok")
    assert b.promote(ids["dev"], reviewer="tope", expect="ok") == "dev"
    assert [t["id"] for t in b.load("dev")] == [ids["dev"]]
    with pytest.raises(b.Sealed):
        b.promote(ids["holdout"], reviewer="tope", expect="ok")
    monkeypatch.setenv("EVAL_UNSEAL", "yes")
    assert b.promote(ids["holdout"], reviewer="tope", expect="ok") == "holdout"
    assert b.load("holdout")[0]["reviewed_by"] == "tope"


@pytest.mark.skipif(os.environ.get("ODOO_LIVE") != "1", reason="live runner needs ODOO_LIVE=1")
def test_live_runner_stub():
    pytest.skip("live bench runner not built yet (needs BOT-SPINE-WIRE read path)")
