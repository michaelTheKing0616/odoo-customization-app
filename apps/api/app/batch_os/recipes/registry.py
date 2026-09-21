"""Recipe registry — journal batch, opening balances, lock dates + stubs."""

from __future__ import annotations

from typing import Any

from app.batch_os.journal_batch import JournalBatchRecipe
from app.batch_os.recipes.accounting_lock_dates import LockDatesRecipe
from app.batch_os.recipes.accounting_opening_balances import OpeningBalancesRecipe
from app.batch_os.recipes.schema import RecipeCard
from app.batch_os.recipes.stubs import build_stubs
from app.batch_os.types import RiskTier


def _registry() -> dict[str, Any]:
    recipes: dict[str, Any] = {
        "accounting.journal_batch": JournalBatchRecipe(),
        "accounting.opening_balances": OpeningBalancesRecipe(),
        "accounting.lock_dates": LockDatesRecipe(),
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
    for rid, recipe in _registry().items():
        status = "stub" if rid.startswith(
            ("master_data.", "document_batch.", "settings.", "access_company.", "automation.", "ui_studio.", "housekeeping.")
        ) else "complete"
        atlas_class = getattr(recipe, "atlas_class", None) or rid.split(".", 1)[0]
        risk: RiskTier = getattr(recipe, "risk", "L1")
        models = {
            "accounting.journal_batch": [
                "account.move",
                "account.move.line",
                "account.journal",
                "account.account",
            ],
            "accounting.opening_balances": ["account.move", "account.journal"],
            "accounting.lock_dates": ["res.company"],
        }.get(rid, [])
        cards.append(
            RecipeCard(
                id=rid,
                title=getattr(recipe, "title", rid),
                blurb=getattr(recipe, "blurb", ""),
                risk=risk,
                status=status,
                atlas_class=atlas_class,
                models=models,
            )
        )
    return cards
