"""Bridge connection gate, queue idempotency, and connector protocol (no Odoo)."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.bridge.connections import (
    ConnectionProbeError,
    connection_may_leave_tier_i,
    probe_for_connection,
    probe_odoo,
    probe_shopify,
    require_verified_connections,
    shopify_shop_json_url,
    verify_connection,
)
from app.bridge.connector import Connector, ShopifyConnector
from app.bridge.contract import ContractError, validate_contract
from app.bridge.queue import enqueue_pure, mark_dead

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


def _connection(status: str = "unverified") -> SimpleNamespace:
    return SimpleNamespace(status=status, verified_at=None)


def test_unverified_connection_cannot_leave_tier_i() -> None:
    row = _connection("unverified")
    assert connection_may_leave_tier_i(row) is False
    verify_connection(row, probe_ok=False)
    assert connection_may_leave_tier_i(row) is False


def test_verified_connection_may_leave_tier_i() -> None:
    row = _connection("unverified")
    verify_connection(row, probe_ok=True)
    assert row.status == "verified"
    assert row.verified_at is not None
    assert connection_may_leave_tier_i(row) is True



class _FakeOdooOk:
    def version(self) -> dict:
        return {"server_version": "19.0", "server_version_info": [19, 0, 0, "final", 0, ""]}

    def search_count(self, model: str, domain: list) -> int:
        assert model == "res.partner"
        assert domain == []
        return 3


class _FakeOdooFailVersion:
    def version(self) -> dict:
        raise RuntimeError("xmlrpc down")

    def search_count(self, model: str, domain: list) -> int:  # pragma: no cover
        return 0


class _FakeOdooFailCount:
    def server_version(self) -> dict:
        return {"server_version": "18.0"}

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        assert method == "search_count"
        raise RuntimeError("access denied")


def test_odoo_probe_success_sets_verified_at_and_tier_i_may_pass() -> None:
    row = _connection("unverified")
    row.kind = "odoo"
    verify_connection(row, probe=probe_for_connection(row, odoo_client=_FakeOdooOk()))
    assert row.status == "verified"
    assert row.verified_at is not None
    assert connection_may_leave_tier_i(row) is True
    detail = probe_odoo(_FakeOdooOk())
    assert detail["search_count"] == 3
    assert detail["kind"] == "odoo"


def test_odoo_probe_failure_sets_failed_and_tier_i_refuses() -> None:
    row = _connection("unverified")
    row.kind = "odoo"
    verify_connection(row, probe=probe_for_connection(row, odoo_client=_FakeOdooFailVersion()))
    assert row.status == "failed"
    assert row.verified_at is None
    assert connection_may_leave_tier_i(row) is False
    with pytest.raises(ConnectionProbeError, match="odoo probe failed"):
        probe_odoo(_FakeOdooFailCount())


def test_shopify_probe_success_sets_verified_at_and_tier_i_may_pass() -> None:
    row = _connection("unverified")
    row.kind = "shopify"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/shop.json")
        assert request.headers.get("X-Shopify-Access-Token") == "shpat_test"
        return httpx.Response(
            200,
            json={"shop": {"id": 42, "myshopify_domain": "acme.myshopify.com"}},
        )

    transport = httpx.MockTransport(handler)
    verify_connection(
        row,
        probe=probe_for_connection(
            row,
            shopify_shop="acme",
            shopify_token="shpat_test",
            shopify_transport=transport,
        ),
    )
    assert row.status == "verified"
    assert row.verified_at is not None
    assert connection_may_leave_tier_i(row) is True
    assert shopify_shop_json_url("acme").endswith("/admin/api/2024-10/shop.json")


def test_shopify_probe_failure_sets_failed_and_tier_i_refuses() -> None:
    row = _connection("unverified")
    row.kind = "third_party"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": "Unauthorized"})

    verify_connection(
        row,
        probe=probe_for_connection(
            row,
            shopify_shop="acme.myshopify.com",
            shopify_token="bad",
            shopify_transport=httpx.MockTransport(handler),
        ),
    )
    assert row.status == "failed"
    assert row.verified_at is None
    assert connection_may_leave_tier_i(row) is False
    with pytest.raises(ConnectionProbeError, match="HTTP 401"):
        probe_shopify(
            shop="acme",
            access_token="bad",
            transport=httpx.MockTransport(handler),
        )


def test_tier_i_refuses_contract_until_referenced_connections_have_verified_at() -> None:
    contract = validate_contract(
        {
            "odoo_connection_id": "odoo-1",
            "third_party_connection_id": "shop-1",
            "direction": "inbound",
            "webhook_signature_required": True,
            "entities": [{"name": "orders", "money": True, "money_policy": "odoo_wins"}],
        }
    )
    odoo = _connection("unverified")
    shop = _connection("unverified")
    with pytest.raises(ContractError, match="verified_at"):
        require_verified_connections(contract, {"odoo-1": odoo, "shop-1": shop})
    verify_connection(odoo, probe_ok=True)
    with pytest.raises(ContractError, match="third_party:shop-1"):
        require_verified_connections(contract, {"odoo-1": odoo, "shop-1": shop})
    verify_connection(shop, probe=lambda: probe_shopify(
        shop="acme",
        access_token="tok",
        http_get=lambda url, headers: httpx.Response(
            200, json={"shop": {"id": 7, "domain": "acme.myshopify.com"}}
        ),
    ))
    require_verified_connections(contract, {"odoo-1": odoo, "shop-1": shop})
    assert connection_may_leave_tier_i(odoo) and connection_may_leave_tier_i(shop)


def test_failed_probe_clears_prior_verified_at() -> None:
    row = _connection("unverified")
    verify_connection(row, probe_ok=True)
    assert row.verified_at is not None
    verify_connection(row, probe_ok=False)
    assert row.status == "failed"
    assert row.verified_at is None
    assert connection_may_leave_tier_i(row) is False


def test_duplicate_idempotency_key_does_not_create_second_event() -> None:
    events: list[SimpleNamespace] = []
    first = enqueue_pure(
        events,
        connection_id="conn-1",
        idempotency_key="evt-a",
        payload={"order_id": "1"},
    )
    second = enqueue_pure(
        events,
        connection_id="conn-1",
        idempotency_key="evt-a",
        payload={"order_id": "2"},
    )
    assert first is second
    assert len(events) == 1


def test_secret_in_payload_raises() -> None:
    with pytest.raises(ValueError, match="secret key"):
        enqueue_pure([], connection_id="c", idempotency_key="k", payload={"api_key": "x"})
    with pytest.raises(ValueError, match="secret key"):
        enqueue_pure([], connection_id="c", idempotency_key="k", payload={"nested": {"token": "t"}})


def test_empty_webhook_signature_is_false() -> None:
    shop = ShopifyConnector(webhook_secret="shpss_test")
    assert shop.verify_webhook_signature(b"{}", "") is False
    assert shop.verify_webhook_signature(b"{}", "sig") is False
    parsed = shop.parse_webhook_event(b'{"id": 7}')
    assert parsed["idempotency_key"] == "shopify:7"
    assert "orders" in shop.declared_schema()


def test_connector_protocol_has_exactly_six_method_names() -> None:
    assert set(Connector.__protocol_attrs__) == _CONNECTOR_METHODS


def test_mark_dead_increments_attempts() -> None:
    event = SimpleNamespace(status="queued", attempts=0)
    mark_dead(event, "timeout")
    assert event.status == "dead"
    assert event.attempts == 1


_INTEGRATION_URL = "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"


def _postgres_integration_available() -> bool:
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg not installed")
    try:
        with psycopg.connect(
            "host=127.0.0.1 port=5433 dbname=odoo_custom user=odoo_custom password=odoo_custom"
        ) as conn:
            conn.execute("SELECT 1")
    except Exception:
        pytest.skip("Postgres bridge integration DB not reachable")
    return True


def test_enqueue_persists_and_deduplicates_on_postgres() -> None:
    _postgres_integration_available()
    os.environ["DATABASE_URL"] = _INTEGRATION_URL
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.account_models import Workspace
    from app.bridge.queue import enqueue
    from app.db_models import BridgeConnection, IntegrationEvent

    engine = create_engine(_INTEGRATION_URL, pool_pre_ping=True)
    Workspace.__table__.create(bind=engine, checkfirst=True)
    BridgeConnection.__table__.create(bind=engine, checkfirst=True)
    IntegrationEvent.__table__.create(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        conn_id = str(uuid.uuid4())
        ws_id = str(uuid.uuid4())
        db.add(
            Workspace(
                id=ws_id,
                name="bridge-test",
                slug=f"bridge-{ws_id[:12]}",
            )
        )
        db.flush()
        db.add(
            BridgeConnection(
                id=conn_id,
                workspace_id=ws_id,
                kind="third_party",
                display_name=f"shop-{conn_id[:8]}",
                status="verified",
                secret_ref="secret:SHOPIFY_TOKEN",
            )
        )
        db.commit()
        key = f"idem-{uuid.uuid4().hex[:8]}"
        e1 = enqueue(db, conn_id, key, {"topic": "orders/create"})
        e2 = enqueue(db, conn_id, key, {"topic": "orders/updated"})
        db.commit()
        assert e1.id == e2.id
        count = (
            db.query(IntegrationEvent)
            .filter_by(connection_id=conn_id, idempotency_key=key)
            .count()
        )
        assert count == 1
    finally:
        db.close()
