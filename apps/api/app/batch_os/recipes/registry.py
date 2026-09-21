"""Recipe registry — journal/document/payment + master data + settings/access/automation/UI/housekeeping."""

from __future__ import annotations

from typing import Any

from app.batch_os.document_batch import DocumentBatchRecipe
from app.batch_os.journal_batch import JournalBatchRecipe
from app.batch_os.master_data_batch import PartnersBatchRecipe, ProductsBatchRecipe
from app.batch_os.payment_batch import PaymentBatchRecipe
from app.batch_os.recipes.access_company_recipes import MultiCompanyLinkRecipe, UsersGroupsRecipe
from app.batch_os.recipes.accounting_fiscal_year import FiscalYearRecipe
from app.batch_os.recipes.accounting_lock_dates import LockDatesRecipe
from app.batch_os.recipes.accounting_opening_balances import OpeningBalancesRecipe
from app.batch_os.recipes.accounting_tax_pack import TaxPackRecipe
from app.batch_os.recipes.automation_housekeeping_recipes import (
    AttachmentsCleanupRecipe,
    AutomationBasePointerRecipe,
    CronPackRecipe,
    PartnerDedupeRecipe,
)
from app.batch_os.recipes.schema import RecipeCard
from app.batch_os.recipes.settings_recipes import (
    CurrencyBasicsRecipe,
    PaymentTermsRecipe,
    PricelistRecipe,
    SequenceDefaultsRecipe,
    SettingsBoardRecipe,
)
from app.batch_os.recipes.stubs import build_stubs
from app.batch_os.recipes.ui_studio_recipes import MenuPackPointerRecipe, ViewPackPointerRecipe
from app.batch_os.types import RiskTier

_COMPLETE = {
    "accounting.journal_batch",
    "accounting.opening_balances",
    "accounting.lock_dates",
    "accounting.tax_pack",
    "accounting.fiscal_year",
    "document_batch.invoices",
    "document_batch.payments",
    "master_data.partners_batch",
    "master_data.products_batch",
    "settings.board_apply",
    "settings.payment_terms",
    "settings.pricelists",
    "settings.currency",
    "settings.sequences",
    "access_company.users",
    "access_company.multi_company",
    "automation.cron_pack",
    "automation.base",
    "ui_studio.view_pack",
    "ui_studio.menus",
    "housekeeping.attachments",
    "housekeeping.partner_dedupe",
}


def _registry() -> dict[str, Any]:
    recipes: dict[str, Any] = {
        "accounting.journal_batch": JournalBatchRecipe(),
        "accounting.opening_balances": OpeningBalancesRecipe(),
        "accounting.lock_dates": LockDatesRecipe(),
        "accounting.tax_pack": TaxPackRecipe(),
        "accounting.fiscal_year": FiscalYearRecipe(),
        "document_batch.invoices": DocumentBatchRecipe(),
        "document_batch.payments": PaymentBatchRecipe(),
        "master_data.partners_batch": PartnersBatchRecipe(),
        "master_data.products_batch": ProductsBatchRecipe(),
        "settings.board_apply": SettingsBoardRecipe(),
        "settings.payment_terms": PaymentTermsRecipe(),
        "settings.pricelists": PricelistRecipe(),
        "settings.currency": CurrencyBasicsRecipe(),
        "settings.sequences": SequenceDefaultsRecipe(),
        "access_company.users": UsersGroupsRecipe(),
        "access_company.multi_company": MultiCompanyLinkRecipe(),
        "automation.cron_pack": CronPackRecipe(),
        "automation.base": AutomationBasePointerRecipe(),
        "ui_studio.view_pack": ViewPackPointerRecipe(),
        "ui_studio.menus": MenuPackPointerRecipe(),
        "housekeeping.attachments": AttachmentsCleanupRecipe(),
        "housekeeping.partner_dedupe": PartnerDedupeRecipe(),
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
    models_map = {
        "accounting.journal_batch": ["account.move", "account.move.line", "account.journal", "account.account"],
        "accounting.opening_balances": ["account.move", "account.journal"],
        "accounting.lock_dates": ["res.company"],
        "accounting.tax_pack": ["account.tax"],
        "accounting.fiscal_year": ["account.fiscal.year", "res.company"],
        "document_batch.invoices": [
            "account.move", "account.move.line", "res.partner", "product.product", "account.tax", "account.journal"
        ],
        "document_batch.payments": [
            "account.payment", "account.payment.register", "account.move", "account.journal", "res.partner"
        ],
        "master_data.partners_batch": ["res.partner"],
        "master_data.products_batch": ["product.template", "product.product"],
        "settings.board_apply": ["account.payment.term", "res.currency", "ir.sequence", "product.pricelist"],
        "settings.payment_terms": ["account.payment.term"],
        "settings.pricelists": ["product.pricelist"],
        "settings.currency": ["res.currency", "res.company"],
        "settings.sequences": ["ir.sequence"],
        "access_company.users": ["res.users", "res.groups"],
        "access_company.multi_company": ["res.company", "res.users"],
        "automation.cron_pack": ["ir.cron"],
        "automation.base": ["base.automation"],
        "ui_studio.view_pack": ["ir.ui.view"],
        "ui_studio.menus": ["ir.ui.menu"],
        "housekeeping.attachments": ["ir.attachment"],
        "housekeeping.partner_dedupe": ["res.partner"],
    }
    cards: list[RecipeCard] = []
    for rid, recipe in _registry().items():
        status = "complete" if rid in _COMPLETE else "stub"
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
