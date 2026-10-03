"""Shopify verification scenarios against a fake connector. No network."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeShop:
    orders: dict[str, dict] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    fail: str | None = None


def run_scenario(shop: FakeShop, event: dict) -> str:
    if shop.fail == "auth":
        return "auth_failure"
    if shop.fail == "rate":
        return "rate_limit"
    if "id" not in event or "idempotency_key" not in event:
        return "malformed"
    key = str(event["idempotency_key"])
    if key in shop.seen:
        return "duplicate"
    if shop.fail == "partial":
        shop.seen.add(key)
        return "partial_failure"
    shop.seen.add(key)
    shop.orders[str(event["id"])] = event
    return "ok"


def reconcile(local_ids: set[str], remote_ids: set[str]) -> set[str]:
    return remote_ids - local_ids


def test_tier_ii_six_scenarios() -> None:
    shop = FakeShop()
    assert run_scenario(shop, {"id": "1", "idempotency_key": "a"}) == "ok"
    assert run_scenario(shop, {"id": "1", "idempotency_key": "a"}) == "duplicate"
    assert run_scenario(FakeShop(fail="partial"), {"id": "2", "idempotency_key": "b"}) == "partial_failure"
    assert run_scenario(FakeShop(fail="auth"), {"id": "3", "idempotency_key": "c"}) == "auth_failure"
    assert run_scenario(FakeShop(fail="rate"), {"id": "4", "idempotency_key": "d"}) == "rate_limit"
    assert run_scenario(shop, {"id": "5"}) == "malformed"


def test_tier_iii_seeded_discrepancy_is_detected() -> None:
    missing = reconcile({"1"}, {"1", "9"})
    assert missing == {"9"}
