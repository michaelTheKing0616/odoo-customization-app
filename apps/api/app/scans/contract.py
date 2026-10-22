"""SCAN-01: the scan request/response contract shared by every scan epic.

Field lists follow docs/build-plan/new-features/00_BASELINE.md B5 exactly.
This module defines shapes only: it makes no Odoo call and stores nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# B5 error codes this epic uses, with their HTTP status.
ErrorCode = Literal[
    "ODOO_UNREACHABLE",
    "ODOO_ACCESS_MISSING",
    "ROLE_DENIED",
    "RATE_LIMITED",
    "VALIDATION",
    "NOT_FOUND",
    "CONFLICT",
]
ERROR_HTTP: dict[str, int] = {
    "ODOO_UNREACHABLE": 503,
    "ODOO_ACCESS_MISSING": 403,
    "ROLE_DENIED": 403,
    "RATE_LIMITED": 429,
    "VALIDATION": 422,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
}

RunStatus = Literal["queued", "running", "partial", "done", "failed", "cancelled"]
AreaStatus = Literal["done", "partial", "skipped", "failed"]
Severity = Literal["info", "low", "medium", "high", "critical"]
FixKind = Literal["plan", "link", "manual"]

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
MAX_SAMPLE_IDS = 20


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AreaResult(_Strict):
    area: str
    status: AreaStatus
    rows_read: int = Field(ge=0)
    sampled: bool
    duration_ms: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    error_code: ErrorCode | None = None


class ScanRun(_Strict):
    id: str
    connection_id: str
    scan_id: str
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    areas: list[AreaResult] = Field(default_factory=list)
    budget_ms: int = Field(ge=0)
    odoo_version: str | None = None
    schema_fingerprint: str | None = None


class FixRef(_Strict):
    kind: FixKind
    plan_template: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Finding(_Strict):
    id: str
    scan_id: str
    area: str
    severity: Severity
    title: str
    plain_why: str
    count: int = Field(ge=0)
    sample_ids: list[int] = Field(default_factory=list, max_length=MAX_SAMPLE_IDS)
    model: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    fix: FixRef | None = None
    docs_url: str | None = None


class StartScanRequest(_Strict):
    scan_id: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class FindingsPage(_Strict):
    items: list[Finding]
    next_cursor: str | None = None


class PlanDraftRef(_Strict):
    """A change-plan draft id. Making the draft writes nothing to Odoo."""

    draft_id: str


class ScanErrorBody(BaseModel):
    code: ErrorCode
    message: str
    detail: dict[str, Any] | None = None
    retry_after_s: int | None = None


class ScanErrorEnvelope(BaseModel):
    error: ScanErrorBody


class ScanError(Exception):
    """Raised by engines and the router; rendered as the B5 error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        if code not in ERROR_HTTP:
            raise ValueError(f"unknown scan error code {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.retry_after_s = retry_after_s

    @property
    def status_code(self) -> int:
        return ERROR_HTTP[self.code]

    def body(self) -> dict[str, Any]:
        return ScanErrorEnvelope(
            error=ScanErrorBody(
                code=self.code,  # type: ignore[arg-type]
                message=self.message,
                detail=self.detail,
                retry_after_s=self.retry_after_s,
            )
        ).model_dump()


@dataclass(frozen=True)
class ScanScope:
    """The workspace and connection a request is allowed to act on."""

    workspace_id: str | None
    connection_id: str


@dataclass(frozen=True)
class FindingsQuery:
    severity: str | None
    area: str | None
    offset: int
    limit: int


# One engine function per route. Later cards provide real ones; tests inject fakes.
StartScanFn = Callable[[ScanScope, StartScanRequest], tuple[ScanRun, bool]]  # (run, created)
GetScanFn = Callable[[ScanScope, str], ScanRun]
FindingsFn = Callable[[ScanScope, str, FindingsQuery], tuple[list[Finding], bool]]  # has_more
CancelScanFn = Callable[[ScanScope, str], ScanRun]
PlanFindingFn = Callable[[ScanScope, str], PlanDraftRef]
