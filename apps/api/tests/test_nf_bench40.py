"""BENCH-40 harness tests. Never parses the sealed holdout (INV-16): only its file hash."""

from __future__ import annotations

import json
import os
from pathlib import Path
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
    monkeypatch.setenv("EVAL_UNSEAL", "yes")
    b.seal("tester")
    monkeypatch.delenv("EVAL_UNSEAL")
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


GRADES = (
    "needs-step",
    "needs-edition",
    "not-in-version",
    "approval-required",
    "not-built-yet",
    "unknown",
)


def _grades(t):
    return {t["expect"]} if isinstance(t["expect"], str) else set(t["expect"].values())


def test_generator_shape_boundary_per_grade_per_split_and_neutral():
    ids = [t["id"] for t in mk.TASKS]
    assert len(ids) == 40 == len(set(ids))
    boundary = [t for t in mk.TASKS if _grades(t) != {"ok"}]
    assert 10 <= len(boundary) <= 12
    for g in GRADES:
        split = [b.split_of(t["id"]) for t in mk.TASKS if g in _grades(t)]
        assert len(split) >= 2 and {"dev", "holdout"} <= set(split), g


def test_installed_lists_closed_over_real_depends():
    dev, _ = mk.build()
    for t in dev:
        for v, mods in t["installed"].items():
            assert "portal" in mods and mods == b.closure(mods, int(v))


def test_closure_rejects_non_stock_module():
    with pytest.raises(KeyError):
        b.closure(["not_a_module"], 17)


def test_dev_bench_passes_all_default_versions():
    assert b.DEFAULT_VERSIONS == (17, 18, 19, 20)
    r = b.run(b.load("dev"))
    assert r["versions"] == [17, 18, 19, 20]
    assert r["n"] and r["passed"] == r["n"], r["fails"]


def test_part_tasks_carry_fields_per_part_or_are_rejected():
    base = {"id": "b40-zz", "expect": "ok", "installed": ["base"]}
    with pytest.raises(ValueError):
        b.grade(dict(base, parts=["m:res.partner:create"], fields=["name"]), 17)
    with pytest.raises(ValueError):
        b.grade(dict(base, parts=[{"task": "m:res.partner:create", "bogus": 1}]), 17)
    inst = b.closure(["contacts"], 19)
    part = {"task": "m:res.partner:mass-write", "fields": ["additional_info"]}
    p = b.grade(dict(base, parts=[part], installed=inst), 19)
    assert p.grade == "not-in-version"


def test_t3_expectation_flips_when_capability_lands(monkeypatch):
    t3 = [t for t in sum(mk.build(), []) if t.get("until_capability") == 3]
    assert t3 and all(b.expected(t, 17) == "not-built-yet" for t in t3)
    on = dict(tt._CAPABILITIES, **{"module-authoring": True, "module-test-gate": True})
    monkeypatch.setattr(tt, "_CAPABILITIES", MappingProxyType(on))
    r = b.run([dict(t, versions=[17]) for t in t3])
    assert r["flipped"] == len(t3) and r["passed"] == r["n"]


def test_candidates_are_one_way(tmp_bench):
    task = {"id": "b40-real-1", "task": "m:res.partner:create", "installed": ["base"]}
    b.append_candidate(task, source="refused-run", note="n")
    assert b.load("dev") == [] and b.HOLDOUT.read_text() == "[]"
    with pytest.raises(ValueError):
        b.append_candidate({"id": "b40-x"}, source="s", note="n")


@pytest.mark.parametrize("bad", ["real-1", "b40-A", "b40-1/..", "b40-x\n", "", None])
def test_candidate_id_pattern(tmp_bench, bad):
    with pytest.raises(ValueError):
        b.append_candidate({"id": bad, "task": "m:res.partner:create"}, source="s", note="n")


def test_duplicate_candidate_rejected(tmp_bench):
    task = {"id": "b40-dup", "task": "m:res.partner:create"}
    b.append_candidate(task, source="s", note="n")
    with pytest.raises(ValueError):
        b.append_candidate(task, source="s", note="n")
    b.CANDIDATES.write_text(b.CANDIDATES.read_text() * 2)  # tampered queue: two matches
    with pytest.raises(KeyError):
        b.promote("b40-dup", reviewer="r", expect="ok")


def _ids_by_split():
    ids: dict[str, str] = {}
    for i in range(64):
        ids.setdefault(b.split_of(f"b40-c{i}"), f"b40-c{i}")
    return ids


def test_promote_whitelist_and_capability_from_reviewer_only(tmp_bench):
    tid = _ids_by_split()["dev"]
    cand = {
        "id": tid,
        "task": "code:040:migrate",
        "until_capability": 1,
        "expect": "ok",
        "reviewed_by": "forged",
        "evil": "x",
    }
    b.append_candidate(cand, source="s", note="n")
    b.promote(tid, reviewer="tope", expect="not-built-yet")
    (got,) = b.load("dev")
    assert set(got) <= b.PROMOTE_KEYS | {"expect", "reviewed_by"}
    assert "until_capability" not in got and got["reviewed_by"] == "tope"
    assert got["expect"] == "not-built-yet"
    b.DEV.write_text("[]")
    b.promote(tid, reviewer="tope", expect="not-built-yet", until_capability=3)
    assert b.load("dev")[0]["until_capability"] == 3


def test_seal_needs_unseal_and_reviewer_and_records_history(tmp_bench, monkeypatch):
    monkeypatch.delenv("EVAL_UNSEAL", raising=False)
    with pytest.raises(b.Sealed):
        b.seal("tope")
    monkeypatch.setenv("EVAL_UNSEAL", "yes")
    for who in ("", " "):
        with pytest.raises(PermissionError):
            b.seal(who)
    with pytest.raises(TypeError):
        b.seal()  # type: ignore[call-arg]
    old = json.loads(b.MANIFEST.read_text())["sha256"]
    b.HOLDOUT.write_text("[]\n")
    b.seal("tope", note="fix")
    m = json.loads(b.MANIFEST.read_text())
    h = m["history"][-1]
    assert (h["old"], h["new"], h["reviewer"]) == (old, m["sha256"], "tope") and h["at"]


def test_real_manifest_has_correction_record():
    m = json.loads(b.MANIFEST.read_text())
    assert m["history"] and m["history"][-1]["reviewer"].strip()


def test_promote_needs_reviewer_and_unseal_for_holdout(tmp_bench, monkeypatch):
    monkeypatch.delenv("EVAL_UNSEAL", raising=False)
    ids = _ids_by_split()
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
    assert json.loads(b.MANIFEST.read_text())["history"][-1]["reviewer"] == "tope"


@pytest.mark.skipif(os.environ.get("ODOO_LIVE") != "1", reason="live runner needs ODOO_LIVE=1")
def test_live_runner_stub():
    pytest.skip("live bench runner not built yet (needs BOT-SPINE-WIRE read path)")


def test_seal_history_must_chain(tmp_bench, monkeypatch):
    import shutil

    shutil.copy(Path(b.__file__).parent / "seal_manifest.json", b.MANIFEST)
    m = json.loads(b.MANIFEST.read_text())
    b.check_chain(m)
    monkeypatch.setenv("EVAL_UNSEAL", "yes")
    for mutate in (
        lambda x: x["history"][-1].update(new="0" * 64),
        lambda x: x["history"].append(dict(x["history"][-1], old="1" * 64)),
    ):
        bad = json.loads(json.dumps(m))
        mutate(bad)
        b.MANIFEST.write_text(json.dumps(bad))
        with pytest.raises(b.Sealed):
            b.check_chain(bad)
        with pytest.raises(b.Sealed):
            b.load("holdout")
        with pytest.raises(b.Sealed):
            b.seal("tope")
