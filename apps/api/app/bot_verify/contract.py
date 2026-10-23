"""BV-01: the verify-run request/response contract.

Field lists follow docs/build-plan/new-features/BOT_VERIFY.md §6. Shapes only:
no Odoo call, no tables (BV-02), no evidence masking (BV-02/04).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.changeset.verify import CHECKS
from app.scans.contract import ERROR_HTTP, ScanError, ScanScope

Layer = Literal["live", "walkthrough", "flows"]
VerifyTarget = Literal["disposable_clone", "approved_connection"]
RunStatus = Literal["queued", "running", "passed", "failed", "needs_human", "rolled_back"]
LayerStatus = Literal["passed", "failed", "skipped"]
StepAction = Literal["open", "click", "fill", "assert"]

# B5 codes this epic uses; the two 409s are the only new ones.
BVErrorCode = Literal[
    "ROLE_DENIED", "VALIDATION", "NOT_FOUND", "TARGET_NOT_ALLOWED", "CHANGESET_NOT_APPLIED"
]
BV_ERROR_CODES: tuple[str, ...] = (
    "ROLE_DENIED",
    "VALIDATION",
    "NOT_FOUND",
    "TARGET_NOT_ALLOWED",
    "CHANGESET_NOT_APPLIED",
)
BV_NEW_HTTP: dict[str, int] = {"TARGET_NOT_ALLOWED": 409, "CHANGESET_NOT_APPLIED": 409}


class BVErrorBody(BaseModel):
    code: BVErrorCode
    message: str
    detail: dict[str, Any] | None = None
    retry_after_s: int | None = None


class BVErrorEnvelope(BaseModel):
    error: BVErrorBody


class BVError(ScanError):
    """A B5 envelope error that also allows the two BV 409 codes."""

    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None) -> None:
        if code not in BV_ERROR_CODES:
            raise ValueError(f"unknown verify-run error code {code!r}")
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.detail = detail
        self.retry_after_s = None

    @property
    def status_code(self) -> int:
        return BV_NEW_HTTP.get(self.code) or ERROR_HTTP[self.code]

    def body(self) -> dict[str, Any]:
        return BVErrorEnvelope(
            error=BVErrorBody(code=self.code, message=self.message, detail=self.detail)  # type: ignore[arg-type]
        ).model_dump()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerifyRunRequest(_Strict):
    changeset_id: str
    layers: list[Layer] = Field(min_length=1)
    target: VerifyTarget

    @field_validator("layers")
    @classmethod
    def _no_duplicates(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("each layer may appear once")
        return v


class CheckResult(_Strict):
    check: str
    op_index: int
    passed: bool
    evidence: dict[str, str]

    @field_validator("check")
    @classmethod
    def _known_check(cls, v: str) -> str:
        if v not in CHECKS:
            raise ValueError(f"unknown check {v!r}")
        return v


class WalkStep(_Strict):
    index: int
    op_index: int | None
    action: StepAction
    target: str
    passed: bool
    screenshot_id: str | None
    dom_assertion: str | None


class LayerResult(_Strict):
    layer: Layer
    status: LayerStatus
    reason: str | None
    checks: list[CheckResult]
    steps: list[WalkStep]


class VerifyRun(_Strict):
    run_id: str
    changeset_id: str
    status: RunStatus
    layers: list[LayerResult]
    started_at: datetime
    finished_at: datetime | None


# One engine per route. Engines raise BVError (NOT_FOUND for a foreign or unknown
# run, artifact or change set; TARGET_NOT_ALLOWED; CHANGESET_NOT_APPLIED).
StartFn = Callable[[ScanScope, VerifyRunRequest], VerifyRun]
GetFn = Callable[[ScanScope, str], VerifyRun]
ArtifactFn = Callable[[ScanScope, str, str], bytes]
