"""FITGAP-01: the fit-gap request/response contract.

Field lists follow docs/build-plan/new-features/DELIVERY.md §FITGAP §6 exactly.
Shapes only: no Odoo call, nothing stored.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scans.contract import ScanScope

# B5 error codes this epic uses (subset of app.scans.contract.ERROR_HTTP).
FitGapErrorCode = Literal["ROLE_DENIED", "VALIDATION", "NOT_FOUND", "CONFLICT", "RATE_LIMITED"]
FITGAP_ERROR_CODES: tuple[str, ...] = (
    "ROLE_DENIED",
    "VALIDATION",
    "NOT_FOUND",
    "CONFLICT",
    "RATE_LIMITED",
)

LineClass = Literal["standard", "config", "custom", "impossible"]
MAX_TEXT_CHARS = 1_000_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    module: str | None = None
    model: str | None = None
    field: str | None = None
    setting: str | None = None
    not_in_community: str | None = None


class LineOverride(_Strict):
    """The PATCH body. `reason` is stored as fitgap_lines.override_reason."""

    cls: LineClass
    reason: str = Field(min_length=1, max_length=2000)


class FitGapLine(_Strict):
    id: str
    quote: str
    cls: LineClass | None = None  # null = not classified yet (or chunk failed, retryable)
    evidence: list[Evidence] = Field(default_factory=list)
    effort_h: tuple[float, float]
    confidence: float = Field(ge=0, le=1)
    override: LineOverride | None = None

    @model_validator(mode="after")
    def _effort_range(self) -> FitGapLine:
        lo, hi = self.effort_h
        if lo < 0 or hi < lo:
            raise ValueError("effort_h must be [low, high] with 0 <= low <= high")
        return self


class FitGapDoc(_Strict):
    id: str
    doc_sha256: str
    catalog_version: str
    lines: list[FitGapLine] = Field(default_factory=list)


class FitGapRequest(_Strict):
    """POST body: exactly one of upload_id or text."""

    upload_id: str | None = Field(None, min_length=1, max_length=128)
    text: str | None = Field(None, min_length=1, max_length=MAX_TEXT_CHARS)

    @model_validator(mode="after")
    def _exactly_one(self) -> FitGapRequest:
        if (self.upload_id is None) == (self.text is None):
            raise ValueError("send exactly one of upload_id or text")
        return self


# One engine function per route. Later cards provide real ones; tests inject fakes.
CreateFitGapFn = Callable[[ScanScope, FitGapRequest], tuple[FitGapDoc, bool]]  # (doc, created)
GetFitGapFn = Callable[[ScanScope, str], FitGapDoc]
OverrideLineFn = Callable[[ScanScope, str, str, LineOverride], FitGapLine]
