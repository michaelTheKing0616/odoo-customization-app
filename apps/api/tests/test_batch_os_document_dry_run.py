"""Document batch (invoices/bills) dry-run with mock RPC client."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.document_batch import DocumentBatchRecipe


class FakeClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.posted: list[int] = []

    def model_exists(self, model: str) -> bool:
        return model in {
            "account.move",
            "account.journal",
            "account.account",
            "res.partner",
            "product.product",
            "account.tax",
        }

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        kwargs = kwargs or {}
        if model == "res.partner" and method == "search_read":
            return [{"id": 10, "name": "Acme Co"}]
        if model == "account.journal" and method == "search_read":
            return [{"id": 3, "name": "Customer Invoices", "code": "INV", "type": "sale"}]
        if model == "product.product" and method == "search_read":
            return [{"id": 50, "name": "Widget"}]
        if model == "account.account" and method == "search_read":
            return [{"id": 400, "code": "400000"}]
        if model == "account.tax" and method == "search_read":
            return [{"id": 1, "name": "VAT 7.5%"}]
        if model == "account.move" and method == "create":
            vals = args[0]
            self.created.append(vals)
            return 8000 + len(self.created)
        if model == "account.move" and method == "action_post":
            self.posted.extend(args[0])
            return True
        return []


def _rows():
    return [
        {
            "partner": "Acme Co",
            "date": "2024-06-01",
            "due": "2024-06-30",
            "product": "Widget",
            "qty": "2",
            "price": "100",
            "move_type": "out_invoice",
            "invoice_group": "INV1",
            "journal": "INV",
            "tax": "VAT 7.5%",
        },
        {
            "partner": "Acme Co",
            "date": "2024-06-01",
            "due": "2024-06-30",
            "product": "Widget",
            "qty": "1",
            "price": "50",
            "move_type": "out_invoice",
            "invoice_group": "INV1",
            "journal": "INV",
        },
    ]


def test_document_dry_run_groups_lines():
    recipe = DocumentBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="inv.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert len(state.moves) == 1
    assert state.moves[0].balanced is True
    assert abs(state.moves[0].total_debit - 250.0) < 0.01  # 2*100 + 1*50
    assert client.created == []
    assert "DRAFT" in state.message or "not posted" in state.message.lower()


def test_document_apply_creates_out_invoice_draft():
    recipe = DocumentBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="inv.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.apply(state, client, post_after_create=False)
    assert state.phase == "applied"
    assert len(client.created) == 1
    assert client.posted == []
    assert state.created_move_ids
    move_vals = client.created[0]
    assert move_vals["move_type"] == "out_invoice"
    assert move_vals["partner_id"] == 10
    assert len(move_vals["invoice_line_ids"]) == 2


def test_document_missing_partner_blocks():
    recipe = DocumentBatchRecipe()
    client = FakeClient()
    rows = _rows()
    rows[0]["partner"] = ""
    rows[1]["partner"] = ""
    state = recipe.intake(
        connection_id="c1",
        filename="bad.csv",
        headers=list(rows[0].keys()),
        rows=rows,
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "failed"
    assert any(e.code == "blocking" for e in state.errors)
