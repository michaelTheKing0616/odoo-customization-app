"""Pin REG-NP-BR: Tier I contract, in-memory queue, six-method connector."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.bridge.connector import Connector
from app.bridge.contract import ContractError, IntegrationContract, validate_contract
from app.bridge.queue import enqueue_pure, mark_dead

pytestmark = pytest.mark.no_app_db

_CONNECTOR_METHODS = frozenset(
    {
        "fetch",
        "create",
        "update",
        "declared_schema",
        "verify_webhook_signature",
        "parse_webhook_event",
    }
)


def _contract(**overrides: object) -> dict:
    base = {
        "odoo_connection_id": "odoo-1",
        "third_party_connection_id": "shop-1",
        "direction": "inbound",
        "webhook_signature_required": True,
        "entities": [{"name": "orders", "money": True, "money_policy": "odoo_wins"}],
    }
    base.update(overrides)
    return base


def test_complete_inbound_contract_defaults_idempotency_key() -> None:
    contract = validate_contract(_contract())
    assert isinstance(contract, IntegrationContract)
    assert contract.idempotency_key_field == "idempotency_key"


def test_two_way_without_conflict_resolution_fails() -> None:
    with pytest.raises(ContractError):
        validate_contract(_contract(direction="two_way"))


def test_money_entity_without_policy_fails() -> None:
    with pytest.raises(ContractError):
        validate_contract(_contract(entities=[{"name": "orders", "money": True}]))


def test_top_level_api_key_is_rejected() -> None:
    with pytest.raises(ContractError, match="secrets"):
        validate_contract(_contract(api_key="sk_live_secret"))


def test_inline_odoo_target_is_rejected() -> None:
    with pytest.raises(ContractError, match="connection_id"):
        validate_contract(
            _contract(odoo_target={"url": "https://odoo.example", "username": "admin"})
        )


def test_enqueue_pure_returns_same_event_and_one_row() -> None:
    events: list[Any] = []
    first = enqueue_pure(
        events, connection_id="c", idempotency_key="k", payload={"n": 1}
    )
    second = enqueue_pure(
        events, connection_id="c", idempotency_key="k", payload={"n": 1}
    )
    assert first is second
    assert len(events) == 1


def test_mark_dead_from_queued_sets_dead_and_one_attempt() -> None:
    event = SimpleNamespace(status="queued", attempts=0)
    mark_dead(event, "timeout")
    assert event.status == "dead"
    assert event.attempts == 1


def test_connector_protocol_has_exactly_six_methods() -> None:
    assert set(Connector.__protocol_attrs__) == _CONNECTOR_METHODS
