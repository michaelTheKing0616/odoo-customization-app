"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=500, examples=["http://127.0.0.1:8069"])
    db_name: str = Field(..., min_length=1, max_length=200)
    username: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, description="Password or API key")
    verify: bool = Field(True, description="Probe Odoo 19 before saving")


class ConnectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=1, max_length=500)
    db_name: str | None = Field(None, min_length=1, max_length=200)
    username: str | None = Field(None, min_length=1, max_length=200)
    password: str | None = Field(None, min_length=1)
    verify: bool = True


class UnsupportedCapabilityOut(BaseModel):
    id: str
    label: str
    reason: str


class CapabilityMatrixOut(BaseModel):
    """Version capability probe (registry-backed + hosting honesty)."""

    major: int | None = None
    edition: str = "community"
    server_version: str | None = None
    supported: list[str] = Field(default_factory=list)
    unsupported: list[UnsupportedCapabilityOut] = Field(default_factory=list)
    ga: bool = False
    message: str = ""
    hosting_hint: str = "unknown"  # online | odoo_sh | self_hosted | unknown
    python_module_install: bool = True
    installed_modules_sample: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TierCapabilityRowOut(BaseModel):
    key: str
    label: str
    available: Literal["yes", "no", "verify", "plan_gated"]
    reason: str
    options: list[str] = Field(default_factory=list)


class TierMatrixOut(BaseModel):
    """Four-tier capability matrix (hosting × edition × modules)."""

    connection_id: str
    hosting: Literal["online", "sh", "onprem", "unknown"]
    hosting_hint: str = "unknown"
    edition: Literal["community", "enterprise", "unknown"]
    major: int | None = None
    server_version: str | None = None
    web_base_url: str | None = None
    installed_modules_sample: list[str] = Field(default_factory=list)
    capabilities: list[TierCapabilityRowOut] = Field(default_factory=list)
    legacy_supported: list[str] = Field(default_factory=list)
    legacy_unsupported: list[UnsupportedCapabilityOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class GatingOptionOut(BaseModel):
    id: str
    label: str


class GatingCalloutOut(BaseModel):
    feature: str
    title: str
    why: str
    options: list[str] = Field(default_factory=list)
    available: bool = False
    capability_key: str
    gating_choices: list[GatingOptionOut] = Field(default_factory=list)


class AutomationsGateOut(BaseModel):
    automations: GatingCalloutOut
    approvals: GatingCalloutOut


class AutomationTriggerProbeRow(BaseModel):
    major: int
    source: str
    on_webhook: bool
    on_change: bool
    on_change_field_ids: bool = False
    trigger_count: int | None = None


class AutomationTriggersOut(BaseModel):
    major: int
    source: str
    supported_triggers: list[str] = Field(default_factory=list)
    probe_table: list[AutomationTriggerProbeRow] = Field(default_factory=list)


class PropertyFieldsProbeRow(BaseModel):
    major: int
    source: str
    ttype_properties: bool = False
    ttype_properties_definition: bool = False
    definition_record_column: bool = False
    definition_record_field_column: bool = False
    definition_write: bool = False
    rpc_create: bool = False
    supported: bool = False


class PropertyFieldsProbeOut(BaseModel):
    major: int
    source: str
    supported: bool
    probe_table: list[PropertyFieldsProbeRow] = Field(default_factory=list)


class PreviewThemeOut(BaseModel):
    ok: bool
    theme: dict[str, str] = Field(default_factory=dict)
    preview_vars: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class DeploymentPanelOut(BaseModel):
    tier: Literal["onprem", "sh", "online", "unknown"] = "unknown"
    title: str = ""
    body: str = ""
    options: list[str] = Field(default_factory=list)
    include_deploy_doc: bool = False


class ValidateLiveItemOut(BaseModel):
    item_id: str
    category: str
    status: Literal["pass", "warn", "fail"]
    message: str


class ValidateLiveOut(BaseModel):
    ok: bool
    items: list[ValidateLiveItemOut] = Field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    message: str = ""


class ModuleSpecValidateLiveBody(BaseModel):
    spec: dict = Field(..., description="ModuleSpec-like JSON to validate read-only")


class TierCapabilityRowOut(BaseModel):
    key: str
    label: str
    available: Literal["yes", "no", "verify", "plan_gated"]
    reason: str
    options: list[str] = Field(default_factory=list)


class TierMatrixOut(BaseModel):
    """Four-tier capability matrix (hosting × edition × modules)."""

    connection_id: str
    hosting: Literal["online", "sh", "onprem", "unknown"]
    hosting_hint: str = "unknown"
    edition: Literal["community", "enterprise", "unknown"]
    major: int | None = None
    server_version: str | None = None
    web_base_url: str | None = None
    installed_modules_sample: list[str] = Field(default_factory=list)
    capabilities: list[TierCapabilityRowOut] = Field(default_factory=list)
    legacy_supported: list[str] = Field(default_factory=list)
    legacy_unsupported: list[UnsupportedCapabilityOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class GatingOptionOut(BaseModel):
    id: str
    label: str


class GatingCalloutOut(BaseModel):
    feature: str
    title: str
    why: str
    options: list[str] = Field(default_factory=list)
    available: bool = False
    capability_key: str
    gating_choices: list[GatingOptionOut] = Field(default_factory=list)


class AutomationsGateOut(BaseModel):
    automations: GatingCalloutOut
    approvals: GatingCalloutOut


class AutomationTriggerProbeRow(BaseModel):
    major: int
    source: str
    on_webhook: bool
    on_change: bool
    on_change_field_ids: bool = False
    trigger_count: int | None = None


class AutomationTriggersOut(BaseModel):
    major: int
    source: str
    supported_triggers: list[str] = Field(default_factory=list)
    probe_table: list[AutomationTriggerProbeRow] = Field(default_factory=list)


class PropertyFieldsProbeRow(BaseModel):
    major: int
    source: str
    ttype_properties: bool = False
    ttype_properties_definition: bool = False
    definition_record_column: bool = False
    definition_record_field_column: bool = False
    definition_write: bool = False
    rpc_create: bool = False
    supported: bool = False


class PropertyFieldsProbeOut(BaseModel):
    major: int
    source: str
    supported: bool
    probe_table: list[PropertyFieldsProbeRow] = Field(default_factory=list)


class PreviewThemeOut(BaseModel):
    ok: bool
    theme: dict[str, str] = Field(default_factory=dict)
    preview_vars: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class DeploymentPanelOut(BaseModel):
    tier: Literal["onprem", "sh", "online", "unknown"] = "unknown"
    title: str = ""
    body: str = ""
    options: list[str] = Field(default_factory=list)
    include_deploy_doc: bool = False


class ValidateLiveItemOut(BaseModel):
    item_id: str
    category: str
    status: Literal["pass", "warn", "fail"]
    message: str


class ValidateLiveOut(BaseModel):
    ok: bool
    items: list[ValidateLiveItemOut] = Field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    message: str = ""


class ModuleSpecValidateLiveBody(BaseModel):
    spec: dict = Field(..., description="ModuleSpec-like JSON to validate read-only")


class ConnectionOut(BaseModel):
    id: str
    name: str
    url: str
    db_name: str
    username: str
    server_version: str | None
    last_seen_version: str | None = None
    upgrade_detected: bool = False
    upgrade_detected_at: datetime | None = None
    write_mode: Literal["observer", "standard", "production"] = "observer"
    writes_paused: bool = False
    created_at: datetime | None
    updated_at: datetime | None
    capabilities: CapabilityMatrixOut | None = None

    model_config = {"from_attributes": True}


class WriteModeUpdate(BaseModel):
    write_mode: Literal["observer", "standard", "production"]


class WritesPausedUpdate(BaseModel):
    writes_paused: bool


class ProductionReadinessItemOut(BaseModel):
    key: str
    label: str
    status: Literal["pass", "fail", "warn"]
    detail: str


class ProductionReadinessOut(BaseModel):
    passed: bool
    items: list[ProductionReadinessItemOut]
    drill_snapshot_id: str | None = None
    updated_at: datetime | None = None
    first_write_acknowledged: bool = False


class LeastPrivilegeConfirmBody(BaseModel):
    acknowledge_admin: bool = False


class HealthCheckItemOut(BaseModel):
    artifact_id: str
    artifact_type: str
    label: str
    status: str
    reason: str
    deep_link: str
    resource_type: str | None = None
    resource_key: str | None = None


class HealthCheckRunOut(BaseModel):
    id: str
    connection_id: str
    job_id: str | None = None
    trigger: str
    status: str
    previous_version: str | None = None
    current_version: str | None = None
    ok_count: int = 0
    broken_count: int = 0
    message: str = ""
    items: list[HealthCheckItemOut] = Field(default_factory=list)
    created_at: datetime | None = None
    finished_at: datetime | None = None


class HealthCheckTriggerOut(BaseModel):
    job_id: str | None = None
    run_id: str | None = None
    async_job: bool = True
    message: str = ""
    report: HealthCheckRunOut | None = None


class ProbeResult(BaseModel):
    ok: bool
    uid: int | None = None
    server_version: str | None = None
    capabilities: CapabilityMatrixOut | None = None
    upgrade_detected: bool = False
    health_job_id: str | None = None
    upgrade_detected: bool = False
    health_job_id: str | None = None


class ProtectedModulesOut(BaseModel):
    connection_id: str
    server_version: str | None = None
    manifest_version: str | None = None
    manifest: dict[str, Any]
    tier_summary: dict[str, int] = Field(default_factory=dict)


class ModuleOut(BaseModel):
    id: int
    name: str
    shortdesc: str | None
    state: str
    application: bool


class ModelOut(BaseModel):
    id: int
    model: str
    name: str
    state: str | None
    transient: bool


class FieldOut(BaseModel):
    id: int
    name: str
    field_description: str
    ttype: str
    required: bool
    readonly: bool
    relation: str | None
    state: str | None
    help: str | None = None
    selection: str | None = None
    related: str | None = None
    currency_field: str | None = None
    relation_field: str | None = None
    tracking: bool = False


class ViewOut(BaseModel):
    id: int
    name: str
    model: str
    type: str
    arch: str | None = None
    snapshot_id: str | None = None


class CreateModelBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Human label")
    model: str = Field(..., min_length=3, max_length=200, description="Technical x_* name")
    transient: bool = False
    with_defaults: bool = Field(
        True, description="Create x_name + default list/form/search views (Studio-like)"
    )
    enable_mail_thread: bool = Field(
        False,
        description=(
            "Ensure mail is installed and try to set is_mail_thread on ir.model when "
            "the field exists (Odoo 19 probe). Full chatter/activities require a "
            "Python module export with mixins=['mail.thread','mail.activity.mixin'] — "
            "live ir.model mixins are limited."
        ),
    )


class CreateModelOut(ModelOut):
    warnings: list[str] = Field(default_factory=list)
    mail_thread_enabled: bool = False
    snapshot_id: str | None = None


class SelectionOption(BaseModel):
    value: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)


class CreateFieldBody(BaseModel):
    model: str = Field(..., min_length=1)
    name: str = Field(..., min_length=3, description="Must start with x_")
    field_description: str = Field(..., min_length=1)
    ttype: str = Field(
        ...,
        description=(
            "Concrete Odoo ttype: char|text|integer|float|boolean|date|datetime|"
            "html|binary|selection|many2one|many2many|one2many|monetary. "
            "Deprecated alias 'related' maps to char/many2one + related= path."
        ),
    )
    required: bool = False
    readonly: bool = False
    relation: str | None = None
    relation_field: str | None = None
    selection: list[SelectionOption] | None = None
    help: str | None = None
    related: str | None = Field(
        None,
        description=(
            "Related path e.g. partner_id.country_id — when set, field is readonly "
            "related; still send a concrete ttype (not ttype=related)"
        ),
    )
    currency_field: str | None = Field(
        None, description="Currency field for monetary, e.g. currency_id or x_currency_id"
    )
    on_delete: Literal["set null", "restrict", "cascade"] | None = Field(
        None,
        description=(
            "Many2one on_delete. Odoo 19: required many2one cannot use set null "
            "(API defaults to restrict when required and on_delete omitted)."
        ),
    )
    inject_into_views: bool = Field(
        True,
        description="After create, inject field into form/list/search views when present",
    )
    view_widget: str | None = Field(
        None,
        description="Optional widget when injecting into views (e.g. barcode, monetary)",
    )
    inject_strategy: Literal["inherit", "mutate"] = Field(
        "inherit",
        description=(
            "inherit (default): xpath extension view. "
            "mutate: write parent arch — requires advanced confirm"
        ),
    )
    confirm_advanced: bool = False
    confirm_phrase: str | None = None

    def selection_odoo_string(self) -> str | None:
        if not self.selection:
            return None
        parts = [f"({o.value!r},{o.label!r})" for o in self.selection]
        return "[" + ",".join(parts) + "]"


class FieldCreateOut(FieldOut):
    injected_view_ids: list[int] = Field(default_factory=list)
    snapshot_id: str | None = None
    currency_field_created: str | None = None
    currency_field_created: str | None = None


class ExportModuleBody(BaseModel):
    technical_name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(..., min_length=1, max_length=200)
    include_custom_models: bool = True
    include_extensions: bool = Field(
        True,
        description="Also package x_* fields on stock models (res.partner, etc.) as _inherit",
    )
    include_views: bool = True
    install_mode: str = Field("python", description="python | data")
    model_filter: list[str] | None = Field(
        None, description="If set, only export these model technical names"
    )
    extend_models: list[str] | None = Field(
        None,
        description="Stock models to export as inherit extensions (default: auto-detect)",
    )
    depends: list[str] | None = Field(
        None,
        description="Explicit module depends to merge with inferred depends (None = infer only)",
    )
    include_reports: bool = Field(
        True,
        description="Package custom QWeb PDF reports for exported models into report/reports.xml",
    )
    store_ready: bool = Field(
        False,
        description="Inject Apps Store assets (icon, index.html, manifest fields) + readiness report",
    )


class StoreReadinessItemOut(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str


class StoreReadinessReportOut(BaseModel):
    ok: bool
    items: list[StoreReadinessItemOut] = Field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    disclaimer: str = ""
    message: str = ""


class MigrationUnlockOut(BaseModel):
    key: str
    label: str
    online_status: str
    sh_status: str
    unlocks: bool
    reason: str


class MigrationAssistOut(BaseModel):
    eligible: bool
    hosting: str
    title: str
    body: str
    unlocks: list[MigrationUnlockOut] = Field(default_factory=list)
    docs_links: list[dict[str, str]] = Field(default_factory=list)
    disclaimer: str = ""
    message: str = ""
    store_ready: bool = Field(
        False,
        description="Inject Apps Store assets (icon, index.html, manifest fields) + readiness report",
    )


class StoreReadinessItemOut(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warn", "fail"]
    message: str


class StoreReadinessReportOut(BaseModel):
    ok: bool
    items: list[StoreReadinessItemOut] = Field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    disclaimer: str = ""
    message: str = ""


class MigrationUnlockOut(BaseModel):
    key: str
    label: str
    online_status: str
    sh_status: str
    unlocks: bool
    reason: str


class MigrationAssistOut(BaseModel):
    eligible: bool
    hosting: str
    title: str
    body: str
    unlocks: list[MigrationUnlockOut] = Field(default_factory=list)
    docs_links: list[dict[str, str]] = Field(default_factory=list)
    disclaimer: str = ""
    message: str = ""


class ModuleExportOut(BaseModel):
    technical_name: str
    filename: str
    content_base64: str
    note: str
    model_count: int = 0
    view_count: int = 0
    report_count: int = 0
    target_major: int | None = None
    manifest_version: str | None = None
    warnings: list[str] = Field(default_factory=list)
    deployment_panel: DeploymentPanelOut | None = None
    store_readiness: StoreReadinessReportOut | None = None
    deployment_panel: DeploymentPanelOut | None = None
    store_readiness: StoreReadinessReportOut | None = None


class SandboxRunBody(BaseModel):
    technical_name: str | None = None
    display_name: str | None = None
    include_custom_models: bool = True
    include_extensions: bool = True
    include_views: bool = True
    model_filter: list[str] | None = None
    extend_models: list[str] | None = None
    depends: list[str] | None = None
    extra_modules: list[str] | None = Field(
        None,
        description=(
            "Install these modules in the sandbox after DB init and before the "
            "candidate zip. None = use settings SANDBOX_EXTRA_MODULES (default empty)."
        ),
    )
    # Or pass a previously generated zip (base64) instead of exporting live
    zip_base64: str | None = None
    keep_alive: bool = Field(
        False, description="If true, leave sandbox containers running after success"
    )
    async_job: bool = Field(
        True,
        description="If true, return job_id immediately and run sandbox in background",
    )
    odoo_major: int | None = Field(
        None,
        description=(
            "Ephemeral sandbox Docker major (16–19). None = connection server_version major."
        ),
    )


class SandboxRunOut(BaseModel):
    ok: bool
    module: str
    message: str
    log_tail: str = ""
    sandbox_url: str | None = None
    odoo_major: int | None = None
    validation_id: str | None = None
    zip_sha256: str | None = None
    zip_base64: str | None = Field(
        None, description="Echo of validated zip so promote can reuse without re-export"
    )
    job_id: str | None = Field(
        None, description="Set when async_job=true — poll GET /api/jobs/{id}"
    )
    approximation: bool = False
    approximation_label: str | None = None
    sh_staging_suggestion: str | None = None
    approximation: bool = False
    approximation_label: str | None = None
    sh_staging_suggestion: str | None = None


class PromoteModuleBody(BaseModel):
    technical_name: str | None = None
    display_name: str | None = None
    include_custom_models: bool = True
    include_views: bool = True
    model_filter: list[str] | None = None
    install_mode: str = Field(
        "python",
        description="python (filesystem) or data (base_import_module / remote)",
    )
    zip_base64: str | None = None
    validation_id: str | None = Field(
        None, description="From sandbox/run — required unless run_sandbox=true"
    )
    run_sandbox: bool = Field(
        False, description="If true, run sandbox first then promote on success"
    )
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class PromoteModuleOut(BaseModel):
    ok: bool
    module: str
    method: str
    message: str
    module_state: str | None = None
    validation_id: str | None = None
    promotion_id: str | None = None


class UninstallModuleBody(BaseModel):
    module_name: str = Field(..., min_length=1, max_length=120)
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class UninstallModuleOut(BaseModel):
    ok: bool
    module: str
    module_state: str | None = None
    message: str
    residual_models: list[str] = Field(default_factory=list)
    residual_note: str | None = None


class PromotedModuleOut(BaseModel):
    id: str
    module_name: str
    method: str
    status: str
    zip_sha256: str | None = None
    models: list[str] = []
    created_at: datetime | None = None
    uninstalled_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConfirmAdvancedBody(BaseModel):
    """Shared confirm gate for destructive / advanced actions."""

    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class PropertyDefinitionEntry(BaseModel):
    name: str
    string: str | None = None
    type: str = "char"
    default: str | int | float | bool | None = None
    selection: list[list[str]] | None = None
    comodel: str | None = None


class PropertyFieldsSetupBody(ConfirmAdvancedBody):
    child_model: str
    parent_m2o_field: str
    properties_field: str = "x_properties"
    definition_field: str = "x_properties_definition"
    properties_label: str = "Properties"


class PropertyFieldsSetupOut(BaseModel):
    ok: bool
    properties_field: str
    definition_field: str
    parent_model: str
    created: bool
    definition_field_created: bool | None = None


class PropertyDefinitionWriteBody(ConfirmAdvancedBody):
    parent_model: str
    parent_record_id: int
    definition_field: str = "x_properties_definition"
    entries: list[PropertyDefinitionEntry]


class PropertyDefinitionWriteOut(BaseModel):
    ok: bool
    parent_model: str
    record_id: int
    definition_field: str
    property_count: int


class InvoicingPreflightOut(BaseModel):
    ok: bool
    account_installed: bool
    l10n_installed: bool
    company_country: str | None = None
    l10n_modules: list[str] = Field(default_factory=list)
    message: str = ""


class InvoicingConnectBody(ConfirmAdvancedBody):
    model: str
    invoice_field: str = "x_invoice_ids"
    smart_button_name: str = "Invoices"


class InvoicingConnectOut(BaseModel):
    ok: bool
    path: str
    invoice_field: str
    field_created: bool
    count_field: str | None = None
    count_field_created: bool | None = None
    window_action_id: int
    button_spec: dict = Field(default_factory=dict)
    form_view_id: int | None = None
    form_view_name: str | None = None


class InvoicingMergeSpecBody(BaseModel):
    base_spec: dict = Field(default_factory=dict)
    model: str
    invoice_field: str = "x_invoice_ids"
    origin_field_on_move: str = "x_origin_id"
    partner_field: str = "x_partner_id"


class InvoicingMergeSpecOut(BaseModel):
    ok: bool
    merged: dict = Field(default_factory=dict)


class InvoicingDraftInvoiceBody(ConfirmAdvancedBody):
    source_model: str
    record_id: int
    invoice_field: str = "x_invoice_ids"
    partner_field: str = "x_partner_id"
    amount_field: str = "x_amount"
    description_field: str = "x_name"


class InvoicingDraftInvoiceOut(BaseModel):
    ok: bool
    move_id: int
    move_name: str | None = None
    state: str | None = None
    source_model: str
    record_id: int


class InvoicingModuleSpecBody(BaseModel):
    model: str
    invoice_field: str = "x_invoice_ids"
    origin_field_on_move: str = "x_origin_id"
    partner_field: str = "x_partner_id"


class InvoicingModuleSpecOut(BaseModel):
    ok: bool
    fragment: dict = Field(default_factory=dict)


class UpdateFieldBody(BaseModel):
    """Safe field metadata updates (no rename / ttype change)."""

    string: str | None = Field(None, description="Label → field_description")
    field_description: str | None = None
    help: str | None = None
    required: bool | None = None
    readonly: bool | None = None
    tracking: bool | None = None
    selection: str | None = Field(
        None, description="Odoo selection string, only when ttype=selection"
    )


class DeleteFieldBody(ConfirmAdvancedBody):
    mode: Literal["deprecate", "hard_delete"] = "deprecate"


class DeleteFieldOut(BaseModel):
    ok: bool = True
    field_id: int
    mode: Literal["deprecate", "hard_delete"] = "deprecate"
    snapshot_id: str | None = None
    artifact_id: str | None = None
    artifact_url: str | None = None
    row_count: int | None = None
    truncated: bool | None = None
    new_field_name: str | None = None


class DeleteModelOut(BaseModel):
    ok: bool = True
    model: str
    snapshot_id: str | None = None
    data_artifact_id: str | None = None
    artifact_url: str | None = None
    record_count: int | None = None
    truncated: bool | None = None
    overflow_warning: str | None = None


class UpdateAutomationBody(BaseModel):
    active: bool | None = None
    model: str | None = None
    action_kind: str | None = None
    field_name: str | None = None
    value: str | None = None
    target_model: str | None = None


class DeleteAutomationOut(BaseModel):
    ok: bool = True
    automation_id: int
    snapshot_id: str | None = None


class UpdateAccessBody(BaseModel):
    name: str | None = None
    group_id: int | None = None
    clear_group: bool = False
    perm_read: bool | None = None
    perm_write: bool | None = None
    perm_create: bool | None = None
    perm_unlink: bool | None = None
    active: bool | None = None


class UpdateRuleBody(BaseModel):
    name: str | None = None
    domain_force: str | None = None
    group_ids: list[int] | None = None
    perm_read: bool | None = None
    perm_write: bool | None = None
    perm_create: bool | None = None
    perm_unlink: bool | None = None
    active: bool | None = None


class DeleteAccessOut(BaseModel):
    ok: bool = True
    access_id: int
    snapshot_id: str | None = None


class DeleteRuleOut(BaseModel):
    ok: bool = True
    rule_id: int
    snapshot_id: str | None = None


class AppTemplateOut(BaseModel):
    id: str
    name: str
    description: str


class AppScaffoldBody(BaseModel):
    template_id: str = Field(
        ...,
        description="Template id: library | crm_lite | inventory_lite",
    )
    display_name: str | None = Field(
        None, min_length=1, max_length=200, description="Human label for the app"
    )
    technical_prefix: str | None = Field(
        None,
        min_length=1,
        max_length=40,
        description=(
            "Optional model name prefix (e.g. lib_demo → x_lib_demo_book). "
            "Omit for fixed library names x_lib_category / x_lib_book / x_lib_loan."
        ),
    )
    multi_company: bool = Field(
        False,
        description=(
            "Library only: add x_company_id + company record rules on live scaffold. "
            "Portable zip uses company_id when building via library_module_spec."
        ),
    )
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class AppScaffoldOut(BaseModel):
    ok: bool = True
    template_id: str
    models: list[str] = Field(default_factory=list)
    models_created: list[str] = Field(default_factory=list)
    models_skipped: list[str] = Field(default_factory=list)
    fields_created: int = 0
    view_injects: int = 0
    menus_created: int = 0
    message: str = ""
    warnings: list[str] = Field(default_factory=list)


class RelationalPairBody(BaseModel):
    parent_model: str = Field(..., min_length=1)
    child_model: str = Field(..., min_length=1)
    parent_o2m_name: str = Field(..., min_length=3, description="O2M on parent, e.g. x_loan_ids")
    child_m2o_name: str = Field(..., min_length=3, description="M2O on child, e.g. x_book_id")
    parent_o2m_string: str = Field(..., min_length=1)
    child_m2o_string: str = Field(..., min_length=1)
    inject_into_views: bool = True


class RelationalPairOut(BaseModel):
    ok: bool = True
    parent_model: str
    child_model: str
    parent_o2m_name: str
    child_m2o_name: str
    m2o_created: bool = False
    o2m_created: bool = False
    injected_view_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    template_id: str | None = Field(None, max_length=64)
    spec_json: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    template_id: str | None = None
    spec_json: dict | None = None
    status: Literal["draft", "applied"] | None = None


class ProjectOut(BaseModel):
    id: str
    connection_id: str
    name: str
    template_id: str | None
    spec_json: dict
    status: str
    lifecycle_status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectApplyBody(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class ProjectApplyOut(BaseModel):
    ok: bool = True
    project_id: str
    models_created: list[str] = Field(default_factory=list)
    fields_created: int = 0
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class ProjectDiffOut(BaseModel):
    ok: bool = True
    message: str = ""
    to_create_models: list[str] = Field(default_factory=list)
    existing_models: list[str] = Field(default_factory=list)
    to_create_fields: list[str] = Field(default_factory=list)
    existing_fields: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class ReminderCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    model: str = Field(..., min_length=1, description="Technical model, e.g. x_lib_loan")
    date_field: str = Field(
        ...,
        min_length=1,
        description="Date/datetime field used in domain, e.g. x_due_date",
    )
    mode: str = Field(
        "overdue",
        description="overdue | due_soon",
    )
    due_soon_days: int = Field(2, ge=1, le=30)
    interval_number: int = Field(1, ge=1, le=365)
    interval_type: str = Field("days", description="minutes|hours|days|weeks|months")
    email_to: str = Field(
        "{{ object.x_member_id.email }}",
        description="mail.template email_to expression",
    )
    subject: str | None = None
    body_html: str | None = None
    create_cron: bool = True
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class ReminderCreateOut(BaseModel):
    ok: bool = True
    mail_template_id: int | None = None
    cron_id: int | None = None
    message: str = ""
    warnings: list[str] = Field(default_factory=list)


class SuggestDependsOut(BaseModel):
    suggested: list[str] = Field(default_factory=list)
    from_relations: list[str] = Field(default_factory=list)
    message: str = ""


class LibraryStatsOut(BaseModel):
    available: bool = False
    book_model: str | None = None
    loan_model: str | None = None
    books: int | None = None
    loans: int | None = None
    active_loans: int | None = None
    overdue_loans: int | None = None
    message: str = ""


class LibraryExportBody(BaseModel):
    technical_name: str = Field("library_mgmt", min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field("Library Management", min_length=1, max_length=200)
    fines: bool = Field(True, description="Include Option A fine automation + model methods")
    reminders: bool = Field(True, description="Include mail template + overdue ir.cron")
    multi_company: bool = Field(
        False,
        description="Add company_id + multi-company record rules on Book/Loan/Category",
    )
    store_ready: bool = Field(False, description="Apps Store packaging assist")


class ProtectedModuleRefusal(BaseModel):
    protected_module_conflict: bool = True
    requested_capability: str
    protected_module: str
    safe_alternative: str
    kind: str = "refusal"
    model: str | None = None
    reason: str = ""


class AiDraftModuleBody(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    connection_id: str | None = Field(
        None,
        description="Optional connection — loads sample models for reuse context",
    )
    reuse_models: list[str] = Field(
        default_factory=list,
        description="Existing Odoo models to prefer linking (e.g. res.partner)",
    )
    rejected_reuse_models: list[str] = Field(
        default_factory=list,
        description="Stock models the operator rejected — skip inference and allow custom x_* parallels",
    )
    reuse_view_ids: list[int] = Field(
        default_factory=list,
        description="Existing ir.ui.view ids the operator wants to reuse",
    )
    reuse_action_ids: list[int] = Field(
        default_factory=list,
        description="Existing ir.actions.act_window / server action ids to reuse",
    )
    expand: bool = Field(
        True,
        description="Post-process: domain packs + default views/menus/actions",
    )
    pipeline: str | None = Field(
        None,
        description="single | staged — staged = multi-step LLM pipeline (overrides AI_PIPELINE_MODE)",
    )
    grain: str | None = Field(
        None,
        description="Override grain: field_pack | feature_slice | full_app",
    )
    gallery_id: str | None = Field(
        None,
        description="Apply a built-in component gallery seed",
    )
    host_model: str | None = Field(
        None,
        description="Override detected host model for component grain",
    )
    connect_points: dict | None = Field(
        None,
        description="Operator-edited connect points from wizard review step",
    )
    overlap_choice: str | None = Field(
        None,
        description="AI-9 audit: use | extend | build_anyway",
    )
    overlap_finding_id: str | None = Field(
        None,
        description="AI-9 finding id when user chose use/extend/build_anyway",
    )


class AiProposeConnectPointsBody(BaseModel):
    prompt: str = Field(..., min_length=3)
    connection_id: str | None = None
    grain: str | None = None
    gallery_id: str | None = None
    host_model: str | None = None
    connect_points: dict | None = None


class AiProposeConnectPointsOut(BaseModel):
    ok: bool = True
    grain: str
    grain_label: str
    connect_points: dict | None = None
    host_candidates: list[dict] = Field(default_factory=list)
    requires_review: bool = False
    warnings: list[str] = Field(default_factory=list)
    gallery_id: str | None = None


class AiCheckOverlapBody(BaseModel):
    prompt: str = Field(..., min_length=3)
    connection_id: str | None = None
    grain: str | None = None
    host_model: str | None = None


class AiCheckOverlapOut(BaseModel):
    ok: bool = True
    grain: str
    grain_label: str
    findings: list[dict] = Field(default_factory=list)
    semantic_pass_ran: bool = False
    requires_review: bool = False


class GeneralizeComponentBody(BaseModel):
    spec_json: dict
    consent_share_template: bool = False
    host_slot: str | None = None
    pack_slug: str | None = None


class AiDraftModuleOut(BaseModel):
    ok: bool = True
    draft: dict
    raw_response: str | None = None
    note: str = (
        "Draft only — does not apply. Review, then Generate UI from JSON "
        "(or save as Project → Apply)."
    )
    warnings: list[str] = Field(default_factory=list)
    refusals: list[ProtectedModuleRefusal] = Field(default_factory=list)
    domain_pack: str | None = None
    grain: str | None = None
    grain_label: str | None = None
    connect_points: dict | None = None
    host_candidates: list[dict] = Field(default_factory=list)


class AiReapplyReuseBody(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    draft: dict = Field(..., description="Existing ModuleSpec draft JSON")
    connection_id: str | None = None
    reuse_models: list[str] = Field(default_factory=list)
    rejected_reuse_models: list[str] = Field(default_factory=list)


class AiReapplyReuseOut(BaseModel):
    ok: bool = True
    draft: dict
    warnings: list[str] = Field(default_factory=list)


class ModuleSpecApplyBody(BaseModel):
    spec: dict = Field(..., description="ModuleSpec-like JSON (from AI draft or Projects)")
    apply_views: bool = True
    apply_menus: bool = True
    apply_smart_buttons: bool = True
    apply_automations: bool = True
    confirm_advanced: bool = False
    confirm_phrase: str | None = None
    skip_validate_live: bool = Field(
        False,
        description="Skip pre-apply validate-live (requires confirm_advanced when failures exist)",
    )


class ModuleSpecApplyOut(BaseModel):
    ok: bool = True
    models_created: list[str] = Field(default_factory=list)
    fields_created: int = 0
    views_created: int = 0
    views_updated: int = 0
    menus_created: int = 0
    smart_buttons: int = 0
    automations_created: int = 0
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class ModuleSpecImportOut(BaseModel):
    ok: bool = True
    spec: dict
    warnings: list[str] = Field(default_factory=list)
    unmapped: list[dict] = Field(default_factory=list)
    custom_code_blocks: list[dict] = Field(default_factory=list)
    source: str = ""
    note: str = (
        "Imported into ModuleSpec — review in visual editor before Generate UI / Apply."
    )


class ExpertConversationTurn(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=4000)


class ExpertAskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    connection_id: str | None = None
    ui_context: dict | None = None
    conversation: list[ExpertConversationTurn] = Field(default_factory=list)


class ExpertCitationOut(BaseModel):
    source: str
    version: str
    breadcrumb: str
    chunk_id: str
    source_index: int = 0


class ExpertAskOut(BaseModel):
    answer_markdown: str
    citations: list[ExpertCitationOut] = Field(default_factory=list)
    grounded: bool = False
    declined: bool = False
    suggested_tools: list[dict] = Field(default_factory=list)
    caution_flags: list[str] = Field(default_factory=list)
    retrieval_version: str | None = None
    model_used: str | None = None
    reasoning: bool = False
    uncited_warning: bool = False
