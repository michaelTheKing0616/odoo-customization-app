"""Payment matching + tax pack + fiscal year + atlas document intents."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.atlas.loader import list_atlas, reload_atlas, search_atlas
from app.batch_os.payment_batch import PaymentBatchRecipe
from app.batch_os.recipes.accounting_fiscal_year import FiscalYearRecipe
from app.batch_os.recipes.accounting_tax_pack import TaxPackRecipe
from app.batch_os.recipes.registry import get_recipe, list_recipes


class FakePayClient:
    def __init__(self) -> None:
        self.payments: list[dict[str, Any]] = []

    def model_exists(self, model: str) -> bool:
        return True

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        kwargs = kwargs or {}
        if model == "res.partner":
            return [{"id": 10, "name": "Acme"}]
        if model == "account.journal":
            return [{"id": 5, "name": "Bank", "code": "BNK", "type": "bank"}]
        if model == "account.move" and method == "search_read":
            return [
                {
                    "id": 99,
                    "name": "INV/2024/001",
                    "ref": "INV1",
                    "partner_id": [10, "Acme"],
                    "amount_residual": 200.0,
                    "move_type": "out_invoice",
                    "payment_state": "not_paid",
                }
            ]
        if model == "account.payment.register" and method == "create":
            return 55
        if model == "account.payment.register" and method == "action_create_payments":
            return True
        if model == "account.payment" and method == "create":
            self.payments.append(args[0])
            return 88
        if model == "account.payment" and method == "action_post":
            return True
        return []


class FakeTaxClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.existing: list[dict[str, Any]] = []

    def model_exists(self, model: str) -> bool:
        return model in {"account.tax", "res.company", "account.fiscal.year"}

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        if model == "account.tax" and method == "search_read":
            return list(self.existing)
        if model == "account.tax" and method == "create":
            self.created.append(args[0])
            return 100 + len(self.created)
        if model == "res.company" and method == "search_read":
            return [{"id": 1, "name": "Demo Co"}]
        if model == "account.fiscal.year" and method == "search_read":
            return []
        if model == "account.fiscal.year" and method == "create":
            return 501
        return []


def test_payment_dry_run_mock():
    recipe = PaymentBatchRecipe()
    client = FakePayClient()
    rows = [
        {
            "move_ref": "INV/2024/001",
            "partner": "Acme",
            "amount": "200",
            "date": "2024-06-15",
            "journal": "BNK",
            "memo": "Pay INV1",
        }
    ]
    state = recipe.intake(
        connection_id="c1", filename="pay.csv", headers=list(rows[0].keys()), rows=rows
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert state.risk == "L2"
    assert len(state.moves) == 1
    assert state.moves[0].balanced is True
    assert "preview" in state.message.lower() or "posted" in state.message.lower()


def test_tax_pack_dry_run_and_apply():
    recipe = TaxPackRecipe()
    client = FakeTaxClient()
    state = recipe.intake(connection_id="c1", extras={"country_code": "NG"})
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert state.extras.get("would_create")
    state = recipe.apply(state, client)
    assert state.phase == "applied"
    assert len(client.created) >= 1
    assert client.created[0]["amount_type"] == "percent"


def test_fiscal_year_report_only_dry_run():
    recipe = FiscalYearRecipe()
    client = FakeTaxClient()
    state = recipe.intake(connection_id="c1")
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert state.extras.get("mode") == "report_only"


def test_atlas_document_batch_complete_and_recipes():
    reload_atlas()
    classes = {c["id"]: c for c in list_atlas()}
    assert classes["document_batch"]["status"] == "complete"
    intent_ids = {i["id"] for i in classes["document_batch"]["intents"]}
    assert "docs.invoices" in intent_ids
    assert "docs.payments" in intent_ids
    inv = next(i for i in classes["document_batch"]["intents"] if i["id"] == "docs.invoices")
    assert inv["recipe"] == "document_batch.invoices"
    assert inv["status"] == "complete"
    tax = next(
        i for i in classes["accounting"]["intents"] if i["id"] == "accounting.taxes"
    )
    assert tax["recipe"] == "accounting.tax_pack"
    fy = next(i for i in classes["accounting"]["intents"] if i["id"] == "accounting.fy")
    assert fy["recipe"] == "accounting.fiscal_year"

    cards = {c.id: c for c in list_recipes()}
    assert cards["document_batch.invoices"].status == "complete"
    assert cards["document_batch.payments"].status == "complete"
    assert cards["document_batch.payments"].risk == "L2"
    assert cards["accounting.tax_pack"].status == "complete"
    assert cards["accounting.fiscal_year"].status == "complete"
    assert get_recipe("document_batch.invoices") is not None

    hits = search_atlas("invoice")
    assert any(h["intent_id"] == "docs.invoices" for h in hits)


def test_master_data_stub_has_recipe_pointers():
    reload_atlas()
    classes = {c["id"]: c for c in list_atlas()}
    partners = next(i for i in classes["master_data"]["intents"] if i["id"] == "master.partners")
    assert partners["recipe"] == "master_data.partners_batch"
    assert partners["status"] == "stub"
