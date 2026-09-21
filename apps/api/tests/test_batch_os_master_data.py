"""Master data partners/products batch — parse/validate/dry-run/apply (mocked RPC)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.master_data_batch import (
    PartnersBatchRecipe,
    ProductsBatchRecipe,
    suggest_partner_column_map,
    suggest_product_column_map,
)


class FakeClient:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.written: list[tuple[str, list[int], dict[str, Any]]] = []
        self.partners = [
            {"id": 10, "name": "Acme Co", "vat": "NG123", "email": "a@acme.test", "ref": "ACM"}
        ]
        self.products = [
            {"id": 50, "name": "Widget", "default_code": "W1", "barcode": False, "product_tmpl_id": 5}
        ]

    def model_exists(self, model: str) -> bool:
        return model in {
            "res.partner",
            "res.country",
            "product.template",
            "product.product",
            "uom.uom",
            "product.category",
        }

    def _match(self, row: dict[str, Any], domain: list[Any]) -> bool:
        if not domain:
            return True
        # support simple leaf and |/& prefixes lightly
        leaves = [d for d in domain if isinstance(d, (list, tuple)) and len(d) == 3]
        if not leaves:
            return True
        ok = True
        for field, op, val in leaves:
            cur = row.get(field)
            if cur is False or cur is None:
                cur = ""
            cur_s = str(cur)
            val_s = str(val)
            if op == "=":
                if cur_s != val_s:
                    ok = False
            elif op == "ilike":
                if val_s.lower() not in cur_s.lower():
                    ok = False
            else:
                pass
        return ok

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        kwargs = kwargs or {}
        if method == "search_read":
            domain = args[0] if args else []
            if model == "res.partner":
                return [r for r in self.partners if self._match(r, domain)]
            if model == "product.product":
                # map template fields onto product rows
                return [r for r in self.products if self._match(r, domain)]
            if model == "product.template":
                return []
            if model == "res.country":
                return [{"id": 1, "code": "NG"}] if self._match({"code": "NG"}, domain) or not domain else []
            return []
        if method == "create":
            vals = args[0]
            self.created.append((model, vals))
            return 9000 + len(self.created)
        if method == "write":
            ids, vals = args[0], args[1]
            self.written.append((model, ids, vals))
            return True
        return []


def test_partner_column_map_aliases():
    m = suggest_partner_column_map(["Name", "Email", "VAT", "Phone"])
    assert m["Name"] == "name"
    assert m["Email"] == "email"
    assert m["VAT"] == "vat"


def test_product_column_map_aliases():
    m = suggest_product_column_map(["Product", "SKU", "Price"])
    assert m["Product"] == "name"
    assert m["SKU"] == "default_code"
    assert m["Price"] == "list_price"


def test_partners_dry_run_dedup_and_create():
    recipe = PartnersBatchRecipe()
    client = FakeClient()
    rows = [
        {"name": "Acme Co", "email": "a@acme.test", "vat": "NG123"},  # update
        {"name": "New Co", "email": "n@new.test"},  # create
    ]
    state = recipe.intake(
        connection_id="c1",
        filename="partners.csv",
        headers=list(rows[0].keys()),
        rows=rows,
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert state.dry_run is True
    assert client.created == []
    assert "Preview" in state.honesty or "written" in state.honesty.lower() or "≠" in state.honesty


def test_partners_apply_creates():
    recipe = PartnersBatchRecipe()
    client = FakeClient()
    rows = [{"name": "Brand New", "email": "b@new.test"}]
    state = recipe.intake(connection_id="c1", filename="p.csv", headers=list(rows[0].keys()), rows=rows)
    state = recipe.map(state)
    state = recipe.apply(state, client)
    assert state.phase == "applied"
    assert state.dry_run is False
    assert any(m == "res.partner" for m, _ in client.created)


def test_products_dry_run_and_apply():
    recipe = ProductsBatchRecipe()
    client = FakeClient()
    rows = [{"name": "Gadget", "default_code": "G9", "list_price": "12.5"}]
    state = recipe.intake(connection_id="c1", filename="pr.csv", headers=list(rows[0].keys()), rows=rows)
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert client.created == []
    state = recipe.apply(state, client)
    assert state.phase == "applied"
    assert any(m == "product.template" for m, _ in client.created)
