"""NG-01: the Nigeria pack request/response contract.

Field lists follow docs/build-plan/new-features/LOCALIZATION.md §NG §6 exactly
(NgDetect/NgTax/NgPlanResponse pinned 2026-10-22). Shapes only: no Odoo call,
nothing stored, no rates (rates come from YAML in NG-04).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scans.contract import Finding, ScanScope

# B5 error codes this epic uses (subset of app.scans.contract.ERROR_HTTP).
NgErrorCode = Literal["ROLE_DENIED", "VALIDATION", "NOT_FOUND"]
NG_ERROR_CODES: tuple[str, ...] = ("ROLE_DENIED", "VALIDATION", "NOT_FOUND")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NgTax(_Strict):
    id: int
    name: str
    amount: Decimal
    type_tax_use: str


class NgDetect(_Strict):
    country: str | None = None  # company country code
    l10n_ng_installed: bool
    l10n_ng_available: bool
    taxes: list[NgTax] = Field(default_factory=list)


class NgPlanResponse(_Strict):
    plan_id: str


class EinvoiceReadiness(_Strict):
    items: list[Finding] = Field(default_factory=list)
    sample_payload: dict[str, Any] | None = None


class PayrollComputeRequest(_Strict):
    """Exactly one source: an uploaded sheet (upload_id) or hr.employee (from_hr=true)."""

    upload_id: str | None = None
    from_hr: bool = False
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @model_validator(mode="after")
    def _one_source(self) -> PayrollComputeRequest:
        if bool(self.upload_id) == bool(self.from_hr):
            raise ValueError("upload_id: give exactly one of upload_id or from_hr=true")
        return self


class PayrollRow(_Strict):
    employee_ref: str
    gross: Decimal
    paye: Decimal
    pension_employee: Decimal
    pension_employer: Decimal


class PayrollCompute(_Strict):
    rows: list[PayrollRow] = Field(default_factory=list)
    rules_version: str


class BankConvertRequest(_Strict):
    upload_id: str = Field(min_length=1)
    bank: str | None = None


class TryLoading(_Strict):
    ok: bool
    messages: list[str] = Field(default_factory=list)


class BankConvert(_Strict):
    bank: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)  # row shape pinned by NG-08
    csv_id: str | None = None
    try_loading: TryLoading


# One injected engine per route; engine cards replace the defaults.
DetectFn = Callable[[ScanScope], NgDetect]
PlanFn = Callable[[ScanScope], NgPlanResponse]
ReadinessFn = Callable[[ScanScope], EinvoiceReadiness]
PayrollFn = Callable[[ScanScope, PayrollComputeRequest], PayrollCompute]
BankConvertFn = Callable[[ScanScope, BankConvertRequest], BankConvert]
