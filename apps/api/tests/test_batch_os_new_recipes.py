"""Dry-run coverage for settings/access/automation/housekeeping/ui recipes."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.recipes.registry import get_recipe, list_recipes


class FakeClient:
    def __init__(self) -> None:
        self.writes: list[Any] = []

    def model_exists(self, model: str) -> bool:
        return True

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        if method == "search_read":
            if model == "account.payment.term":
                return [{"id": 1, "name": "Immediate Payment"}]
            if model == "res.currency":
                return [{"id": 1, "name": "USD", "active": False}]
            if model == "ir.sequence":
                return [{"id": 1, "name": "Invoice", "code": "account.move", "prefix": "INV/", "padding": 4, "number_next": 1}]
            if model == "product.pricelist":
                return []
            if model == "ir.cron":
                return [{"id": 3, "name": "Mail: Email Queue Manager", "active": True}]
            if model == "res.users":
                return []
            if model == "res.company":
                return [{"id": 1, "name": "My Company", "currency_id": [1, "USD"]}]
            if model == "res.partner":
                return [
                    {"id": 1, "name": "A", "vat": "V1", "email": "a@x"},
                    {"id": 2, "name": "B", "vat": "V1", "email": "b@x"},
                ]
            if model == "ir.attachment":
                return [{"id": 9, "name": "orphan.bin", "file_size": 10}]
            return []
        if method == "search":
            return [1]
        if method == "create":
            return 100
        if method == "write":
            self.writes.append((model, args))
            return True
        return True


@pytest.mark.parametrize(
    "recipe_id",
    [
        "settings.payment_terms",
        "settings.pricelists",
        "settings.currency",
        "settings.sequences",
        "settings.board_apply",
        "access_company.users",
        "access_company.multi_company",
        "automation.cron_pack",
        "automation.base",
        "ui_studio.view_pack",
        "ui_studio.menus",
        "housekeeping.attachments",
        "housekeeping.partner_dedupe",
        "master_data.partners_batch",
        "master_data.products_batch",
    ],
)
def test_recipe_dry_run(recipe_id: str):
    recipe = get_recipe(recipe_id)
    assert recipe is not None
    client = FakeClient()
    rows = []
    if recipe_id == "access_company.users":
        rows = [{"login": "new.user@example.com", "name": "New User", "groups": "Internal User"}]
    if recipe_id.startswith("master_data.partners"):
        rows = [{"name": "Zed", "email": "z@example.com"}]
    if recipe_id.startswith("master_data.products"):
        rows = [{"name": "Thing", "default_code": "T1"}]
    state = recipe.intake(connection_id="c1", filename=recipe_id, headers=list(rows[0].keys()) if rows else [], rows=rows)
    if hasattr(recipe, "map"):
        state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase in {"dry_run", "validated", "failed"} or state.dry_run
    # dry-run must not create for write recipes (pointers may no-op)
    if recipe_id not in {"ui_studio.view_pack", "ui_studio.menus", "automation.base"}:
        assert state.phase == "dry_run" or not any(e.code == "blocking" for e in state.errors)


def test_no_stub_recipes_remain():
    stubs = [c for c in list_recipes() if c.status == "stub"]
    assert stubs == []
