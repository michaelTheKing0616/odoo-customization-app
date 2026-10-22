"""L3 staging auto-apply for R0/R1 only; production and heavy risk pause — card 5C-03."""

from __future__ import annotations

import pytest

from app.changeset.executor import get_journal, reset_journal
from app.changeset.ops import OP_CATALOG
from app.changeset.setting_ops import may_be_billable
from app.changeset.validate import validate
from app.worker_bot import WorkerBot
from app.worker_bot.l3_policy import l3_staging_may_auto_apply
from tests.engine.test_suite_03_idempotency import _plan

pytestmark = pytest.mark.no_app_db

_CATALOG_OPS: tuple[str, ...] = tuple(OP_CATALOG)
_KNOWN_MODELS = frozenset({"x_ticket", "x_m", "res.partner", "sale.order"})
_NEVER_UNSUPERVISED = frozenset({"data.delete", "module.uninstall", "data.merge"})


def _validated(op_type: str) -> dict:
    return validate(_plan(op_type), known_models=_KNOWN_MODELS)


def _handle_staging(bot: WorkerBot, op_type: str) -> dict:
    return bot.handle(
        _plan(op_type),
        environment="staging",
        requester_id="user-1",
        connection_id="conn-l3-catalog",
        known_models=set(_KNOWN_MODELS),
        goal="5C-03 catalog L3 property",
    )


def _handle_production(bot: WorkerBot, op_type: str) -> dict:
    return bot.handle(
        _plan(op_type),
        environment="production",
        requester_id="user-1",
        connection_id="conn-l3-catalog-prod",
        known_models=set(_KNOWN_MODELS),
        goal="5C-03 catalog L3 production pause",
    )


def _is_billable_catalog_plan(op_type: str) -> bool:
    params = _plan(op_type)[0].get("params")
    if not isinstance(params, dict):
        return False
    return may_be_billable(op_type, params, edition="enterprise") or may_be_billable(
        op_type, params, edition="odoo_sh"
    )


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


@pytest.mark.parametrize("op_type", _CATALOG_OPS)
def test_l3_staging_catalog_op_auto_apply_or_pause(op_type: str) -> None:
    """Each catalog op on L3 staging: R0/R1 applies; R4 denied; else paused."""
    report = _validated(op_type)
    bot = WorkerBot("L3")
    out = _handle_staging(bot, op_type)

    should_apply = report["valid"] and l3_staging_may_auto_apply(
        level="L3",
        environment="staging",
        max_risk=report["max_risk"],
        changeset=_plan(op_type),
    )

    if report["max_risk"] == "R4":
        assert out.get("error") == "R4 is denied"
        assert out["applied"] is False
        assert get_journal() == []
        return

    if should_apply:
        assert out["action"] == "applied"
        assert out["applied"] is True
        assert len(get_journal()) > 0
    else:
        assert out["action"] == "paused"
        assert out["applied"] is False
        assert "card" in out
        assert get_journal() == []


@pytest.mark.parametrize("op_type", _CATALOG_OPS)
def test_l3_production_catalog_op_never_applies(
    op_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production at L3 always pauses or denies; executor.apply is not called."""
    apply_calls: list[tuple] = []

    def _forbidden_apply(*args: object, **kwargs: object) -> dict:
        apply_calls.append((args, kwargs))
        raise AssertionError("L3 production must not call executor.apply")

    monkeypatch.setattr("app.worker_bot.runtime.apply", _forbidden_apply)

    report = _validated(op_type)
    bot = WorkerBot("L3")
    out = _handle_production(bot, op_type)

    assert apply_calls == []
    assert out["applied"] is False
    assert get_journal() == []

    if report["max_risk"] == "R4" and report["valid"]:
        assert out.get("error") == "R4 is denied"
    else:
        assert out["action"] == "paused"
        assert "card" in out


def test_l3_destructive_and_billable_catalog_ops_never_auto_apply_on_staging() -> None:
    """DESTRUCTIVE (R2+) and BILLABLE plans never get unsupervised staging apply."""
    for op_type in _CATALOG_OPS:
        report = _validated(op_type)
        params = _plan(op_type)[0].get("params")
        params_dict = params if isinstance(params, dict) else {}
        destructive = (
            op_type in _NEVER_UNSUPERVISED
            or report["max_risk"] in {"R2", "R3", "R4"}
        )
        billable = _is_billable_catalog_plan(op_type)
        if not destructive and not billable:
            continue
        assert l3_staging_may_auto_apply(
            level="L3",
            environment="staging",
            max_risk=report["max_risk"],
            changeset=_plan(op_type),
        ) is False


def test_l3_catalog_property_covers_full_op_catalog() -> None:
    """Parametrize list stays aligned with OP_CATALOG (closed list)."""
    assert set(_CATALOG_OPS) == set(OP_CATALOG)
    assert len(_CATALOG_OPS) == len(OP_CATALOG)


def test_l3_staging_catalog_apply_vs_pause_partition() -> None:
    """Summarize catalog posture for L3 staging (property test bookkeeping)."""
    staging_apply: list[str] = []
    staging_pause: list[str] = []
    staging_deny: list[str] = []

    for op_type in _CATALOG_OPS:
        report = _validated(op_type)
        if report["max_risk"] == "R4":
            staging_deny.append(op_type)
            continue
        if report["valid"] and l3_staging_may_auto_apply(
            level="L3",
            environment="staging",
            max_risk=report["max_risk"],
            changeset=_plan(op_type),
        ):
            staging_apply.append(op_type)
        else:
            staging_pause.append(op_type)

    assert len(staging_apply) + len(staging_pause) + len(staging_deny) == len(OP_CATALOG)
    # Exposed for card evidence; counts are stable for the current 63-op catalog.
    assert len(staging_apply) == 22
    assert len(staging_pause) == 39
    assert len(staging_deny) == 2
