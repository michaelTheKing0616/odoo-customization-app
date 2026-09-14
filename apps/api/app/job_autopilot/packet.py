"""Typed Job Packet — stock stack vs custom residual (not a ModuleSpec)."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


SCORECARD_IS_NOT_GOLIVE = (
    "ModuleSpec completeness 10.0 and Certification (Quality/Evidence/Risk) are "
    "draft artifacts — not Apps Store / go-live. Autopilot done-bar is RPC process "
    "smoke on a sandbox (quote→confirm→invoice + custom Confirm), then a human Promote. "
    "Never treat Certification Production as Autopilot smoke pass."
)


class CustomResidual(BaseModel):
    key: str
    model: str
    reason: str


class DataFileClass(BaseModel):
    filename: str
    doc_type: str
    confidence: float = 0.0
    excerpt: str = ""


class JobPacket(BaseModel):
    prompt: str
    domain_label: str = "operations"
    actors: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    stock_apps: list[str] = Field(default_factory=list)
    custom_residuals: list[CustomResidual] = Field(default_factory=list)
    data_files: list[DataFileClass] = Field(default_factory=list)
    country_code: str | None = None
    l10n_module: str | None = None
    company_name: str | None = None
    currency: str | None = None
    warehouse_needed: bool = False
    roles: list[str] = Field(default_factory=list)
    org_emails: list[str] = Field(default_factory=list)
    grounding: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    decision_record: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    planner: str = "deterministic"
    scorecard_note: str = SCORECARD_IS_NOT_GOLIVE
    connectors: list[str] = Field(default_factory=list)
    structured_brief: str = ""
    operator_brief: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_custom_residual(self) -> bool:
        return bool(self.custom_residuals)


class ProbeResult(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class BootstrapReport(BaseModel):
    installed: list[str] = Field(default_factory=list)
    already_installed: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    probes: list[ProbeResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recipe_version: int = 1
    currency_id: int | None = None
    country_id: int | None = None
    message: str = ""


class ConnectorReport(BaseModel):
    ok: bool = False
    skipped: bool = False
    ran: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    skipped_ids: list[str] = Field(default_factory=list)
    steps: list[ProbeResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class CustomApplyReport(BaseModel):
    skipped: bool = False
    reason: str | None = None
    apply_message: str | None = None
    models_created: list[str] = Field(default_factory=list)
    fields_created: int = 0
    fields_relaxed: int = 0
    root_menu_id: int | None = None
    open_action_id: int | None = None
    elite: dict | None = None
    zip_base64: str | None = None
    expert_score_before: float | None = None
    expert_score_after: float | None = None
    warnings: list[str] = Field(default_factory=list)
    spec: dict | None = None


class IngestReport(BaseModel):
    skipped: bool = False
    reason: str | None = None
    ingest_job_id: str | None = None
    status: str | None = None
    committed: bool = False
    dry_run_only: bool = False
    source_rows: int = 0
    loaded_rows: int = 0
    unmatched_m2o: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class SmokeReport(BaseModel):
    ok: bool = False
    steps: list[ProbeResult] = Field(default_factory=list)
    named_process: str | None = None
    ingest_source_rows: int = 0
    ingest_loaded_rows: int = 0
    unmatched_m2o: list[str] = Field(default_factory=list)
    partner_id: int | None = None
    sale_order_id: int | None = None
    invoice_id: int | None = None
    open_model: str | None = None
    open_id: int | None = None
    open_action_id: int | None = None
    message: str = ""


class JobScorecard(BaseModel):
    """Implementation-job scorecard — not ModuleSpec completeness."""

    stack_fit: float = 0.0
    stock_coverage: float = 0.0
    data_load: float = 0.0
    process_smoke: float = 0.0
    overall: float = 0.0
    findings: list[str] = Field(default_factory=list)
    modulespec_completeness_note: str = SCORECARD_IS_NOT_GOLIVE


class AutopilotResult(BaseModel):
    ok: bool = False
    refused: bool = False
    refuse_reason: str | None = None
    connection_kind: str = "unknown"
    sandbox: bool = False
    packet: JobPacket
    bootstrap: BootstrapReport | None = None
    connectors: ConnectorReport | None = None
    custom: CustomApplyReport | None = None
    ingest: IngestReport | None = None
    smoke: SmokeReport | None = None
    job_scorecard: JobScorecard | None = None
    promote_ready: bool = False
    stages: list[str] = Field(default_factory=list)
    retry_count: int = 0
    walkthrough_seeded: bool = False
    report_markdown: str | None = None
    message: str = ""
    scorecard_note: str = SCORECARD_IS_NOT_GOLIVE
    clone_required: bool = False
    config_packet: dict[str, Any] | None = None
