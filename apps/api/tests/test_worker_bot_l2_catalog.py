"""L2 must pause (or deny R4) every catalog write op — card 5C-02."""

from __future__ import annotations

import pytest

from app.changeset.executor import get_journal, reset_journal
from app.changeset.ops import OP_CATALOG
from app.changeset.validate import validate
from app.worker_bot import WorkerBot
from tests.engine.test_suite_03_idempotency import _plan

pytestmark = pytest.mark.no_app_db

_CATALOG_OPS: tuple[str, ...] = tuple(OP_CATALOG)
_KNOWN_MODELS = frozenset({"x_ticket", "x_m", "res.partner", "sale.order"})


def _r4_at_validation(op_type: str) -> bool:
    report = validate(_plan(op_type), known_models=_KNOWN_MODELS)
    return report["max_risk"] == "R4"


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


@pytest.mark.parametrize("op_type", _CATALOG_OPS)
def test_l2_every_catalog_write_op_has_zero_applies(op_type: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each catalog op at L2: inbox submit or R4 deny; executor never applies."""
    apply_calls: list[tuple] = []

    def _forbidden_apply(*args: object, **kwargs: object) -> dict:
        apply_calls.append((args, kwargs))
        raise AssertionError("L2 must not call executor.apply")

    monkeypatch.setattr("app.worker_bot.runtime.apply", _forbidden_apply)

    bot = WorkerBot("L2")
    out = bot.handle(
        _plan(op_type),
        environment="production",
        requester_id="user-1",
        connection_id="conn-l2-catalog",
        known_models=set(_KNOWN_MODELS),
        goal="5C-02 catalog pause property",
    )

    assert apply_calls == []
    assert out["applied"] is False
    assert get_journal() == []

    if _r4_at_validation(op_type):
        assert out.get("error") == "R4 is denied"
        assert out.get("ok") is False
    else:
        assert out["action"] == "paused"
        assert "card" in out


def test_l2_pause_property_covers_full_op_catalog() -> None:
    """Parametrize list stays aligned with OP_CATALOG (closed list)."""
    assert set(_CATALOG_OPS) == set(OP_CATALOG)
    assert len(_CATALOG_OPS) == len(OP_CATALOG)
