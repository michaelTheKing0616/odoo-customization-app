"""Config Packet — intended-state for stock Odoo configuration (not ModuleSpec)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.job_autopilot.packet import SCORECARD_IS_NOT_GOLIVE

CONFIG_PACKET_VERSION = 1
COA_THRESHOLD = 8

ChecklistStatus = Literal["done", "todo", "blocked", "secret"]
DiffOpKind = Literal[
    "install_module",
    "create_journal",
    "write_warehouse",
    "create_user",
    "write_settings",
    "write_company",
    "write_layout",
    "create_fiscal_position",
    "write_cash_basis",
    "create_reconcile_model",
    "skip",
    "secret_handoff",
    "verify_tax",
]


class ConfigCompany(BaseModel):
    name: str | None = None
    currency: str | None = None
    country_code: str | None = None
    vat: str | None = None


class ConfigJournal(BaseModel):
    name: str
    type: str
    code: str


class ConfigTax(BaseModel):
    """l10n xmlid only — apply never creates taxes."""

    xmlid: str
    name: str | None = None
    amount: float | None = None
    type_tax_use: str | None = None
    tax_exigibility: str | None = None
    cash_basis_account_xmlid: str | None = None


class ConfigFiscalTaxMap(BaseModel):
    src_xmlid: str
    dest_xmlid: str | None = None


class ConfigFiscalPosition(BaseModel):
    name: str
    auto_apply: bool = False
    tax_map: list[ConfigFiscalTaxMap] = Field(default_factory=list)


class ConfigReconcileModel(BaseModel):
    name: str
    rule_type: str = "writeoff_button"


class ConfigAccounting(BaseModel):
    journals: list[ConfigJournal] = Field(default_factory=list)
    tax_xmlids: list[str] = Field(default_factory=list)
    taxes: list[ConfigTax] = Field(default_factory=list)
    fiscal_position_names: list[str] = Field(default_factory=list)
    fiscal_positions: list[ConfigFiscalPosition] = Field(default_factory=list)
    reconcile_models: list[ConfigReconcileModel] = Field(default_factory=list)
    account_code_count: int = 0
    taxes_invented: bool = False


class ConfigStock(BaseModel):
    warehouse_code: str | None = None
    warehouse_name: str | None = None
    delivery_steps: str | None = None
    reception_steps: str | None = None
    lot_tracking: bool = False
    mto: bool = False
    dropship: bool = False


class ConfigSales(BaseModel):
    pricelist_name: str | None = None
    pricelist_currency: str | None = None


class ConfigDocuments(BaseModel):
    paperformat_name: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    layout_xmlid: str | None = None
    font: str | None = None
    layout_background: str | None = None
    external_report_layout_xmlid: str | None = None
    report_header: str | None = None
    report_footer: str | None = None
    option_a_qweb_needed: bool = False
    logo_upload_needed: bool = True


class ConfigUser(BaseModel):
    login: str
    name: str | None = None
    email: str | None = None
    group_xmlids: list[str] = Field(default_factory=list)


class ConfigConnector(BaseModel):
    id: str
    title: str
    needs_secret: bool = True
    odoo_model: str = "payment.provider"
    brands: list[str] = Field(default_factory=list)
    open_hint: str = ""
    action_id: int | None = None
    action_xmlid: str | None = None


class ConfigSettings(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ConfigMailHealth(BaseModel):
    smtp_servers: int = 0
    alias_domains: int = 0
    ok: bool = False
    warnings: list[str] = Field(default_factory=list)
    action_id: int | None = None
    odoo_model: str = "ir.mail_server"


class ConfigSmoke(BaseModel):
    processes: list[str] = Field(default_factory=list)
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


class ConfigOpening(BaseModel):
    tb_present: bool = False
    tb_allowed: bool = False
    coa_threshold: int = COA_THRESHOLD
    account_code_count: int = 0
    message: str = ""
    lock_date_blocked: bool = False
    period_lock_date: str | None = None
    fiscalyear_lock_date: str | None = None
    tax_lock_date: str | None = None


class ChecklistItem(BaseModel):
    id: str
    label: str
    status: ChecklistStatus = "todo"
    surface: str = "job_autopilot"
    href_hint: str = ""
    action_id: int | None = None
    odoo_model: str = ""


class InstanceFingerprint(BaseModel):
    major: int | None = None
    modules_installed: list[str] = Field(default_factory=list)
    journal_types: list[str] = Field(default_factory=list)
    journal_names: list[str] = Field(default_factory=list)
    warehouse_codes: list[str] = Field(default_factory=list)
    warehouse_delivery_steps: str | None = None
    tax_xmlids: list[str] = Field(default_factory=list)
    user_logins: list[str] = Field(default_factory=list)
    account_code_count: int = 0
    company_name: str | None = None
    currency: str | None = None
    country_code: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    mail: ConfigMailHealth = Field(default_factory=ConfigMailHealth)
    paperformat_name: str | None = None
    fiscal_position_names: list[str] = Field(default_factory=list)
    reconcile_model_names: list[str] = Field(default_factory=list)
    period_lock_date: str | None = None
    fiscalyear_lock_date: str | None = None
    tax_lock_date: str | None = None
    sha256: str = ""
    warnings: list[str] = Field(default_factory=list)


class ConfigDiffOp(BaseModel):
    op: DiffOpKind
    target: str
    detail: str
    risky: bool = False


class ConfigDiff(BaseModel):
    ops: list[ConfigDiffOp] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    message: str = ""


class ConfigApplyReport(BaseModel):
    ok: bool = False
    refused: bool = False
    refuse_reason: str | None = None
    snapshot_id: str | None = None
    applied: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    message: str = ""
    target_kind: str = "unknown"


class ConfigPacket(BaseModel):
    """Replayable stock-configuration document emitted by sandbox Autopilot."""

    packet_version: int = CONFIG_PACKET_VERSION
    recipe_version: int = 0
    source_kind: str = "sandbox"
    modules: list[str] = Field(default_factory=list)
    company: ConfigCompany = Field(default_factory=ConfigCompany)
    accounting: ConfigAccounting = Field(default_factory=ConfigAccounting)
    stock: ConfigStock = Field(default_factory=ConfigStock)
    sales: ConfigSales = Field(default_factory=ConfigSales)
    documents: ConfigDocuments = Field(default_factory=ConfigDocuments)
    users: list[ConfigUser] = Field(default_factory=list)
    connectors: list[ConfigConnector] = Field(default_factory=list)
    settings: ConfigSettings = Field(default_factory=ConfigSettings)
    mail: ConfigMailHealth = Field(default_factory=ConfigMailHealth)
    ingest_plan: list[str] = Field(default_factory=list)
    smoke: ConfigSmoke = Field(default_factory=ConfigSmoke)
    opening: ConfigOpening = Field(default_factory=ConfigOpening)
    fingerprint: InstanceFingerprint | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)
    sha256: str = ""
    scorecard_note: str = SCORECARD_IS_NOT_GOLIVE
    secrets_excluded: bool = True
    custom_zip_present: bool = False
    residual_models: list[str] = Field(default_factory=list)


__all__ = [
    "COA_THRESHOLD",
    "CONFIG_PACKET_VERSION",
    "ChecklistItem",
    "ConfigAccounting",
    "ConfigApplyReport",
    "ConfigCompany",
    "ConfigConnector",
    "ConfigFiscalPosition",
    "ConfigFiscalTaxMap",
    "ConfigReconcileModel",
    "ConfigTax",
    "ConfigDiff",
    "ConfigDiffOp",
    "ConfigDocuments",
    "ConfigJournal",
    "ConfigMailHealth",
    "ConfigOpening",
    "ConfigPacket",
    "ConfigSales",
    "ConfigSettings",
    "ConfigSmoke",
    "ConfigStock",
    "ConfigUser",
    "InstanceFingerprint",
]
