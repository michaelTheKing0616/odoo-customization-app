"""BV-03: every OP_CATALOG op kind has a read-back and a walkthrough step."""

from __future__ import annotations

import importlib
import socket
import sys

import pytest

from app.bot_verify import readback
from app.changeset.ops import OP_CATALOG

PINNED_STEP_IDS = frozenset(
    {
        "walk.model.open_list",
        "walk.field.open_form",
        "walk.constraint.check_state",
        "walk.view.render",
        "walk.action.open",
        "walk.menu.open",
        "walk.filter.apply",
        "walk.report.render",
        "walk.automation.trigger",
        "walk.cron.check_state",
        "walk.config.open",
        "walk.access.as_persona",
        "walk.user.check_state",
        "walk.setting.open",
        "walk.module.check_state",
        "walk.data.list",
        "walk.translation.render",
    }
)


def _cov():
    from app.bot_verify import coverage

    return coverage


def test_every_op_kind_mapped():
    cov = _cov()
    missing = sorted(set(OP_CATALOG) - set(cov.COVERAGE))
    unknown = sorted(set(cov.COVERAGE) - set(OP_CATALOG))
    assert not missing, f"op kinds without coverage: {missing}"
    assert not unknown, f"coverage lists unknown op kinds: {unknown}"


def test_each_entry_has_readback_and_step():
    cov = _cov()
    for op, entry in cov.COVERAGE.items():
        assert isinstance(entry, tuple) and len(entry) == 2, op
        rb, step = entry
        assert isinstance(rb, str) and rb, f"{op}: empty readback name"
        assert isinstance(step, str) and step, f"{op}: empty step id"
        assert callable(readback.READBACKS.get(rb)), f"{op}: readback {rb!r} missing"


def test_real_catalog_clean():
    cov = _cov()
    assert cov.check_coverage(OP_CATALOG, cov.COVERAGE, cov.STEP_LIBRARY_STUB) == []


def test_unknown_key_in_map_fails():
    cov = _cov()
    bad = dict(cov.COVERAGE)
    bad["bogus.op"] = ("bogus.op", "walk.data.list")
    errs = cov.check_coverage(OP_CATALOG, bad, cov.STEP_LIBRARY_STUB)
    assert errs and all("bogus.op" in e for e in errs)


def test_step_ids_in_stub_library():
    cov = _cov()
    assert cov.STEP_LIBRARY_STUB == PINNED_STEP_IDS
    for op, (_, step) in cov.COVERAGE.items():
        assert step in cov.STEP_LIBRARY_STUB, f"{op}: step {step!r} not in library"
    bad = dict(cov.COVERAGE)
    bad["field.create"] = ("field.create", "walk.nope")
    errs = cov.check_coverage(OP_CATALOG, bad, cov.STEP_LIBRARY_STUB)
    assert errs and "field.create" in errs[0] and "walk.nope" in errs[0]


def test_mutation_fake_op_kind(monkeypatch):
    cov = _cov()
    import app.changeset.ops as ops

    fake = dict(OP_CATALOG)
    fake["fake.op"] = next(iter(OP_CATALOG.values()))
    monkeypatch.setattr(ops, "OP_CATALOG", fake)
    errs = cov.check_coverage(ops.OP_CATALOG, cov.COVERAGE, cov.STEP_LIBRARY_STUB)
    assert errs and all("fake.op" in e for e in errs)
    monkeypatch.undo()
    assert cov.check_coverage(ops.OP_CATALOG, cov.COVERAGE, cov.STEP_LIBRARY_STUB) == []


@pytest.mark.parametrize(
    "entry,half", [((None, "walk.data.list"), "readback"), (("field.create", None), "step")]
)
def test_missing_readback_or_step_named(entry, half):
    cov = _cov()
    bad = dict(cov.COVERAGE)
    bad["field.create"] = entry
    errs = cov.check_coverage(OP_CATALOG, bad, cov.STEP_LIBRARY_STUB)
    assert errs and "field.create" in errs[0] and half in errs[0]


def test_pure_no_io(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("coverage import opened a socket")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    sys.modules.pop("app.bot_verify.coverage", None)
    mod = importlib.import_module("app.bot_verify.coverage")
    assert mod.COVERAGE
