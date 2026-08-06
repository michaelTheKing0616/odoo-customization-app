"""Universal ingestion pipeline — canonical schema (Wave 17 ING-1)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DocType = Literal[
    "coa",
    "bom",
    "product_catalog",
    "customer_list",
    "vendor_list",
    "price_list",
    "employee_roster",
    "opening_trial_balance",
    "inventory_count",
    "other",
]

DOC_TYPE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "coa",
        "bom",
        "product_catalog",
        "customer_list",
        "vendor_list",
        "price_list",
        "employee_roster",
        "opening_trial_balance",
        "inventory_count",
        "other",
    }
)


class IngestJobStatus(str, Enum):
    pending = "pending"
    classified = "classified"
    extracted = "extracted"
    mapped = "mapped"
    planned = "planned"
    dry_run = "dry_run"
    committed = "committed"
    failed = "failed"


class IngestRow(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, str] = Field(default_factory=dict)
    confidence: float = 1.0
    flags: list[str] = Field(default_factory=list)
    source_ref: str | None = None


class IngestTable(BaseModel):
    id: str
    model: str
    doc_type: DocType
    rows: list[IngestRow] = Field(default_factory=list)
    mapping: dict[str, str] = Field(default_factory=dict)
    natural_key_fields: list[str] = Field(default_factory=list)
    mode: Literal["create", "upsert"] = "upsert"
    warnings: list[str] = Field(default_factory=list)


class IngestRef(BaseModel):
    from_table_id: str
    field: str
    to_model: str
    to_value: str
    resolved: bool = False
    resolved_id: int | None = None
    note: str | None = None


class IngestGap(BaseModel):
    model: str
    field: str
    value: str
    message: str


class IngestPlanStep(BaseModel):
    step_index: int
    table_ids: list[str]
    models: list[str]
    parallel_ok: bool = False


class IngestPlan(BaseModel):
    steps: list[IngestPlanStep] = Field(default_factory=list)
    gaps: list[IngestGap] = Field(default_factory=list)


class IngestFile(BaseModel):
    id: str
    filename: str
    mime: str | None = None
    doc_type: DocType = "other"
    confidence: float = 0.0
    needs_user_confirm: bool = False
    warnings: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)


class IngestCommitLog(BaseModel):
    dry_run: bool = True
    created: int = 0
    updated: int = 0
    failed: int = 0
    skipped: int = 0
    messages: list[str] = Field(default_factory=list)
    step_results: list[dict[str, Any]] = Field(default_factory=list)


class IngestBatch(BaseModel):
    connection_id: str | None = None
    source: Literal["upload", "interview"] = "upload"
    files: list[IngestFile] = Field(default_factory=list)
    tables: list[IngestTable] = Field(default_factory=list)
    refs: list[IngestRef] = Field(default_factory=list)
    gaps: list[IngestGap] = Field(default_factory=list)
    plan: IngestPlan | None = None
    commit_log: IngestCommitLog | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("files", "tables", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> Any:
        return v or []


class ClassificationResult(BaseModel):
    doc_type: DocType
    confidence: float
    needs_user_confirm: bool = False
    method: str = "structured"
    signals: list[str] = Field(default_factory=list)


def validate_doc_type(value: str) -> DocType:
    if value not in DOC_TYPE_ALLOWLIST:
        raise ValueError(f"Unknown doc_type {value!r}")
    return value  # type: ignore[return-value]
