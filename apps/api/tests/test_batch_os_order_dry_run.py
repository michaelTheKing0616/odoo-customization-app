"""Order batch (sale/purchase) dry-run with mock RPC client."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.order_batch import OrderBatchRecipe
from app.batch_os.types import HONESTY_PREVIEW_NE_CONFIRMED


class FakeClient:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []

    def model_exists(self, model: str) -> bool:
        return model in {
            "sale.order",
            "purchase.order",
            "res.partner",
            "product.product",
        }

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        kwargs = kwargs or {}
        if model == "res.partner" and method == "search_read":
            return [{"id": 10, "name": "Acme Co"}]
        if model == "product.product" and method == "search_read":
            return [{"id": 50, "name": "Widget"}]
        if model in {"sale.order", "purchase.order"} and method == "create":
            vals = args[0]
            self.created.append((model, vals))
            return 9000 + len(self.created)
        return []


def _rows():
    return [
        {
            "partner": "Acme Co",
            "date": "2024-06-01",
            "product": "Widget",
            "qty": "2",
            "price": "100",
            "order_type": "sale",
            "order_group": "SO1",
            "ref": "PO-42",
        },
        {
            "partner": "Acme Co",
            "date": "2024-06-01",
            "product": "Widget",
            "qty": "1",
            "price": "50",
            "order_type": "sale",
            "order_group": "SO1",
            "ref": "PO-42",
        },
    ]


def test_order_dry_run_groups_lines():
    recipe = OrderBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="orders.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert len(state.moves) == 1
    assert state.moves[0].balanced is True
    assert abs(state.moves[0].total_debit - 250.0) < 0.01
    assert client.created == []
    assert "DRAFT" in state.message or "not confirmed" in state.message.lower()
    assert HONESTY_PREVIEW_NE_CONFIRMED in (state.honesty or "")


def test_order_apply_creates_sale_order_draft_never_confirms():
    recipe = OrderBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="orders.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.apply(state, client, post_after_create=True)
    assert state.phase == "applied"
    assert len(client.created) == 1
    model, vals = client.created[0]
    assert model == "sale.order"
    assert vals["partner_id"] == 10
    assert len(vals["order_line"]) == 2
    assert state.posted_move_ids == []
    assert "not confirmed" in state.message.lower()
