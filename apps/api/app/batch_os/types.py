"""Shared types for the Batch OS spine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RiskTier = Literal["L0", "L1", "L2", "L3"]
RISK_TIERS: tuple[RiskTier, ...] = ("L0", "L1", "L2", "L3")

BatchPhase = Literal[
    "intake",
    "mapped",
    "validated",
    "dry_run",
    "applied",
    "failed",
]

# Honesty: dry-run / preview never equals posted accounting.
HONESTY_PREVIEW_NE_POSTED = (
    "Preview is not posted. Dry-run only validates shape and balance — "
    "Apply creates drafts; posting (if requested) is a separate L2 step."
)

RISK_LABELS: dict[RiskTier, str] = {
    "L0": "Read / preview only",
    "L1": "Draft creates (reversible via draft unlink)",
    "L2": "Post / irreversible accounting effects",
    "L3": "Fiscal locks / period close — confirm required",
}


@dataclass
class RowError:
    row_index: int  # 1-based data row
    field: str | None = None
    code: str = "invalid"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MappedLine:
    """One journal line after column map + resolve."""

    row_index: int
    journal_key: str = ""
    journal_id: int | None = None
    date: str = ""
    ref: str = ""
    label: str = ""
    account_key: str = ""
    account_id: int | None = None
    debit: float = 0.0
    credit: float = 0.0
    partner_key: str = ""
    partner_id: int | None = None
    analytic_key: str = ""
    analytic_id: int | None = None
    move_group: str = ""  # groups lines into one account.move

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MovePreview:
    """One balanced (or attempted) account.move in preview."""

    group_key: str
    journal_id: int | None
    journal_name: str | None
    date: str
    ref: str
    line_count: int
    total_debit: float
    total_credit: float
    balanced: bool
    line_indexes: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    move_id: int | None = None  # set after apply
    posted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchJobState:
    job_id: str
    connection_id: str
    recipe_id: str
    risk: RiskTier
    phase: BatchPhase
    filename: str = ""
    headers: list[str] = field(default_factory=list)
    raw_rows: list[dict[str, str]] = field(default_factory=list)
    column_map: dict[str, str] = field(default_factory=dict)
    mapped_lines: list[MappedLine] = field(default_factory=list)
    moves: list[MovePreview] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    honesty: str = HONESTY_PREVIEW_NE_POSTED
    dry_run: bool = True
    post_after_create: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    created_move_ids: list[int] = field(default_factory=list)
    posted_move_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "connection_id": self.connection_id,
            "recipe_id": self.recipe_id,
            "risk": self.risk,
            "phase": self.phase,
            "filename": self.filename,
            "headers": list(self.headers),
            "raw_row_count": len(self.raw_rows),
            "sample_rows": list(self.raw_rows[:5]),
            "column_map": dict(self.column_map),
            "mapped_lines": [m.to_dict() for m in self.mapped_lines],
            "moves": [m.to_dict() for m in self.moves],
            "errors": [e.to_dict() for e in self.errors],
            "warnings": list(self.warnings),
            "message": self.message,
            "honesty": self.honesty,
            "dry_run": self.dry_run,
            "post_after_create": self.post_after_create,
            "extras": dict(self.extras),
            "created_move_ids": list(self.created_move_ids),
            "posted_move_ids": list(self.posted_move_ids),
            "ok": self.phase in {"dry_run", "applied"} and not any(
                e.code == "blocking" for e in self.errors
            ),
        }


# Canonical journal-batch column targets
JOURNAL_COLUMN_TARGETS: tuple[str, ...] = (
    "journal",
    "date",
    "ref",
    "label",
    "account",
    "debit",
    "credit",
    "partner",
    "analytic",
    "move_group",
)

JOURNAL_HEADER_ALIASES: dict[str, str] = {
    "journal": "journal",
    "journal_code": "journal",
    "journal_name": "journal",
    "date": "date",
    "entry_date": "date",
    "accounting_date": "date",
    "ref": "ref",
    "reference": "ref",
    "label": "label",
    "name": "label",
    "description": "label",
    "memo": "label",
    "account": "account",
    "account_code": "account",
    "account_name": "account",
    "debit": "debit",
    "dr": "debit",
    "credit": "credit",
    "cr": "credit",
    "partner": "partner",
    "partner_name": "partner",
    "partner_id": "partner",
    "analytic": "analytic",
    "analytic_account": "analytic",
    "analytic_code": "analytic",
    "move_group": "move_group",
    "group": "move_group",
    "entry": "move_group",
    "entry_ref": "move_group",
}
