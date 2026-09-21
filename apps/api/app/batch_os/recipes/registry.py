"""Recipe registry — journal/document/payment batches + tax/FY + stubs."""

from __future__ import annotations

from typing import Any

from app.batch_os.document_batch import DocumentBatchRecipe
from app.batch_os.journal_batch import JournalBatchRecipe
from app.batch_os.payment_batch import PaymentBatchRecipe
from app.batch_os.recipes.accounting_fiscal_year import FiscalYearRecipe
from app.batch_os.recipes.accounting_lock_dates import LockDatesRecipe
from app.batch_os.recipes.accounting_opening_balances import OpeningBalancesRecipe
from app.batch_os.recipes.accounting_tax_pack import TaxPackRecipe
from app.batch_os.recipes.schema import RecipeCard
from app.batch_os.recipes.stubs import build_stubs
from app.batch_os.types import RiskTier

_COMPLETE_PREFIXES = (
    "accounting.",
    "document_batch.invoices",
    "document_batch.payments",
)


def _registry() -> dict[str, Any]:
    recipes: dict[str, Any] = {
        "accounting.journal_batch": JournalBatchRecipe(),
        "accounting.opening_balances": OpeningBalancesRecipe(),
        "accounting.lock_dates": LockDatesRecipe(),
        "accounting.tax_pack": TaxPackRecipe(),
        "accounting.fiscal_year": FiscalYearRecipe(),
        "document_batch.invoices": DocumentBatchRecipe(),
        "document_batch.payments": PaymentBatchRecipe(),
    }
    recipes.update(build_stubs())
    return recipes


def get_recipe(recipe_id: str) -> Any | None:
    return _registry().get(recipe_id)


def require_recipe(recipe_id: str) -> Any:
    recipe = get_recipe(recipe_id)
    if recipe is None:
        raise LookupError(f"Unknown recipe {recipe_id!r}")
    return recipe


def list_recipes() -> list[RecipeCard]:
    cards: list[RecipeCard] = []
    models_map = {
        "accounting.journal_batch": [
            "account.move",
            "account.move.line",
            "account.journal",
            "account.account",
        ],
        "accounting.opening_balances": ["account.move", "account.journal"],
        "accounting.lock_dates": ["res.company"],
        "accounting.tax_pack": ["account.tax"],
        "accounting.fiscal_year": ["account.fiscal.year", "res.company"],
        "document_batch.invoices": [
            "account.move",
            "account.move.line",
            "res.partner",
            "product.product",
            "account.tax",
            "account.journal",
        ],
        "document_batch.payments": [
            "account.payment",
            "account.payment.register",
            "account.move",
            "account.journal",
            "res.partner",
        ],
        "master_data.partners_batch": ["res.partner"],
        "master_data.products_batch": ["product.template", "product.product"],
        "settings.board_apply": ["res.config.settings"],
        "access_company.users": ["res.users", "res.groups"],
        "automation.cron_pack": ["ir.cron"],
        "ui_studio.view_pack": ["ir.ui.view"],
        "housekeeping.attachments": ["ir.attachment"],
    }
    for rid, recipe in _registry().items():
        status = (
            "complete"
            if rid.startswith(_COMPLETE_PREFIXES) or rid in models_map and rid.startswith("accounting.")
            else ("complete" if rid in {"document_batch.invoices", "document_batch.payments"} else "stub")
        )
        if rid.startswith("accounting.") or rid in {
            "document_batch.invoices",
            "document_batch.payments",
        }:
            status = "complete"
        else:
            status = "stub"
        atlas_class = getattr(recipe, "atlas_class", None) or rid.split(".", 1)[0]
        risk: RiskTier = getattr(recipe, "risk", "L1")
        cards.append(
            RecipeCard(
                id=rid,
                title=getattr(recipe, "title", rid),
                blurb=getattr(recipe, "blurb", ""),
                risk=risk,
                status=status,
                atlas_class=atlas_class,
                models=models_map.get(rid, []),
            )
        )
    return cards
