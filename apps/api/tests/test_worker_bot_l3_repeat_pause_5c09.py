"""5C-09 — 50 repeated billable or destructive L3 requests all pause; none apply."""

from __future__ import annotations

import pytest

from app.changeset.executor import get_journal, reset_journal
from app.changeset.ops import OP_CATALOG
from app.changeset.setting_ops import may_be_billable
from app.changeset.validate import validate
from app.worker_bot import WorkerBot
from tests.engine.test_suite_03_idempotency import _plan

pytestmark = pytest.mark.no_app_db

_REPEAT_COUNT = 50
_CATALOG_OPS: tuple[str, ...] = tuple(OP_CATALOG)
_KNOWN_MODELS = frozenset({"x_ticket", "x_m", "res.partner", "sale.order"})
_NEVER_UNSUPERVISED = frozenset({"data.delete", "module.uninstall", "data.merge"})


def _validated(op_type: str) -> dict:
    return validate(_plan(op_type), known_models=_KNOWN_MODELS)


def _is_billable_catalog_plan(op_type: str) -> bool:
    params = _plan(op_type)[0].get("params")
    if not isinstance(params, dict):
        return False
    return may_be_billable(op_type, params, edition="enterprise") or may_be_billable(
        op_type, params, edition="odoo_sh"
    )


def _is_destructive_catalog_plan(op_type: str, report: dict) -> bool:
    return op_type in _NEVER_UNSUPERVISED or report["max_risk"] in {"R2", "R3", "R4"}


def _pause_class_repeat_ops() -> tuple[str, ...]:
    """Valid catalog ops that are billable or destructive and must inbox-pause at L3.

    R4 is denied rather than paused, so those ops are excluded from the 50-count.
    """
    chosen: list[str] = []
    for op_type in _CATALOG_OPS:
        report = _validated(op_type)
        if not report["valid"]:
            continue
        if report["max_risk"] == "R4":
            continue
        if not _is_destructive_catalog_plan(op_type, report) and not _is_billable_catalog_plan(
            op_type
        ):
            continue
        chosen.append(op_type)
    return tuple(chosen)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def test_fifty_repeated_billable_or_destructive_l3_requests_all_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fifty L3 staging billable/destructive handles pause; executor.apply is never called."""
    apply_calls: list[tuple] = []

    def _forbidden_apply(*args: object, **kwargs: object) -> dict:
        apply_calls.append((args, kwargs))
        raise AssertionError("L3 billable/destructive repeats must not call executor.apply")

    monkeypatch.setattr("app.worker_bot.runtime.apply", _forbidden_apply)

    pool = _pause_class_repeat_ops()
    assert pool, "need at least one valid billable or destructive pause-class catalog op"
    assert any(_is_billable_catalog_plan(op_type) for op_type in pool)
    assert any(_is_destructive_catalog_plan(op_type, _validated(op_type)) for op_type in pool)

    bot = WorkerBot("L3")
    pauses = 0
    applies = 0
    for index in range(_REPEAT_COUNT):
        op_type = pool[index % len(pool)]
        out = bot.handle(
            _plan(op_type),
            environment="staging",
            requester_id="user-1",
            connection_id=f"conn-5c09-{index:02d}",
            known_models=set(_KNOWN_MODELS),
            goal="5C-09 billable or destructive repeat",
        )
        if out.get("action") == "paused":
            pauses += 1
        if out.get("applied") is True or out.get("action") == "applied":
            applies += 1
        assert out.get("applied") is False
        assert out.get("action") == "paused"
        assert "card" in out

    assert pauses == _REPEAT_COUNT
    assert applies == 0
    assert apply_calls == []
    assert get_journal() == []
    assert bot.level == "L3"
