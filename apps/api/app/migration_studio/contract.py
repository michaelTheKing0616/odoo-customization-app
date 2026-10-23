"""MIG-01: the data migration studio request/response contract.

Field lists follow docs/build-plan/new-features/INTEGRATE.md §MIG §6 exactly
(pinned 2026-10-22). Shapes only: no Odoo call, no tables, no file storage.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scans.contract import ScanScope

# B5 error codes this epic uses (subset of app.scans.contract.ERROR_HTTP).
MigErrorCode = Literal["ROLE_DENIED", "VALIDATION", "NOT_FOUND", "CONFLICT"]
MIG_ERROR_CODES: tuple[str, ...] = ("ROLE_DENIED", "VALIDATION", "NOT_FOUND", "CONFLICT")

MigrationSource = Literal[
    "QuickBooks Online export",
    "Sage 50 CSV",
    "Zoho Books export",
    "Excel workbook",
    "Other ERP CSV",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MigrationCreate(_Strict):
    source: MigrationSource


class MigrationJob(_Strict):
    id: str
    connection_id: str
    source: MigrationSource
    created_at: datetime


class MigrationFile(_Strict):
    filename: str


class EntityMapping(_Strict):
    source: MigrationSource
    entity: str
    column_map: dict[str, str]
    transforms: dict[str, str]


class MappingSet(_Strict):
    mappings: list[EntityMapping]


class RowError(_Strict):
    row: int = Field(ge=1, description="1-based data row")
    column: str
    message: str


class DryRunEntity(_Strict):
    entity: str
    rows: int = Field(ge=0)
    errors: list[RowError]


class DryRunResult(_Strict):
    entities: list[DryRunEntity]


class ImportRequest(_Strict):
    target_connection_id: str
    confirm: bool


class ImportResult(_Strict):
    target_connection_id: str
    failed: list[RowError]


class ReconcileLine(_Strict):
    entity: str
    file_count: int
    odoo_count: int
    file_sum: str
    odoo_sum: str
    equal: bool

    @field_validator("file_sum", "odoo_sum")
    @classmethod
    def _decimal_string(cls, v: str) -> str:
        try:
            Decimal(v)
        except InvalidOperation as exc:
            raise ValueError("must be a decimal string") from exc
        return v


class ReconcileReport(_Strict):
    lines: list[ReconcileLine]


@dataclass(frozen=True)
class ImportTarget:
    """The import target, resolved in the caller's workspace. live: real business data."""

    connection_id: str
    live: bool


CreateFn = Callable[[ScanScope, MigrationCreate], MigrationJob]
FilesFn = Callable[[ScanScope, str, Any], MigrationFile]
GetMappingFn = Callable[[ScanScope, str], MappingSet]
PutMappingFn = Callable[[ScanScope, str, MappingSet], MappingSet]
DryRunFn = Callable[[ScanScope, str], DryRunResult]
ImportFn = Callable[[ScanScope, str, ImportTarget, ImportRequest], ImportResult]
ReconcileFn = Callable[[ScanScope, str], ReconcileReport]
TargetResolver = Callable[[str], ImportTarget]
