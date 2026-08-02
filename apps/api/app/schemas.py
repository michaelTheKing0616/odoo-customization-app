"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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


class ConnectionOut(BaseModel):
    id: str
    name: str
    url: str
    db_name: str
    username: str
    server_version: str | None
    created_at: datetime | None
    updated_at: datetime | None
    capabilities: CapabilityMatrixOut | None = None

    model_config = {"from_attributes": True}


class ProbeResult(BaseModel):
    ok: bool
    uid: int | None = None
    server_version: str | None = None
    capabilities: CapabilityMatrixOut | None = None


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


class DeleteFieldOut(BaseModel):
    ok: bool = True
    field_id: int
    snapshot_id: str | None = None


class DeleteModelOut(BaseModel):
    ok: bool = True
    model: str
    snapshot_id: str | None = None


class UpdateAutomationBody(BaseModel):
    active: bool


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


class AiDraftModuleOut(BaseModel):
    ok: bool = True
    draft: dict
    raw_response: str | None = None
    note: str = (
        "Draft only — does not apply. Review, then Generate UI from JSON "
        "(or save as Project → Apply)."
    )
    warnings: list[str] = Field(default_factory=list)
    domain_pack: str | None = None


class ModuleSpecApplyBody(BaseModel):
    spec: dict = Field(..., description="ModuleSpec-like JSON (from AI draft or Projects)")
    apply_views: bool = True
    apply_menus: bool = True
    apply_smart_buttons: bool = True
    apply_automations: bool = True
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


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
    source: str = ""
    note: str = (
        "Imported into ModuleSpec — review in visual editor before Generate UI / Apply."
    )
