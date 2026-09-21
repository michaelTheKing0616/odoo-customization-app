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


# Canonical document-batch (invoice/bill) column targets
DOCUMENT_COLUMN_TARGETS: tuple[str, ...] = (
    "move_type",
    "partner",
    "date",
    "due",
    "product",
    "account",
    "label",
    "qty",
    "price",
    "tax",
    "journal",
    "ref",
    "invoice_group",
    "tax_inclusive",
    "currency",
    "amount_currency",
)

DOCUMENT_HEADER_ALIASES: dict[str, str] = {
    "move_type": "move_type",
    "type": "move_type",
    "invoice_type": "move_type",
    "doc_type": "move_type",
    "partner": "partner",
    "partner_name": "partner",
    "customer": "partner",
    "vendor": "partner",
    "supplier": "partner",
    "date": "date",
    "invoice_date": "date",
    "bill_date": "date",
    "due": "due",
    "due_date": "due",
    "invoice_date_due": "due",
    "product": "product",
    "product_code": "product",
    "product_name": "product",
    "account": "account",
    "account_code": "account",
    "label": "label",
    "description": "label",
    "name": "label",
    "qty": "qty",
    "quantity": "qty",
    "price": "price",
    "price_unit": "price",
    "unit_price": "price",
    "tax": "tax",
    "taxes": "tax",
    "tax_name": "tax",
    "journal": "journal",
    "journal_code": "journal",
    "ref": "ref",
    "reference": "ref",
    "invoice_group": "invoice_group",
    "group": "invoice_group",
    "invoice": "invoice_group",
    "invoice_number": "invoice_group",
    "tax_inclusive": "tax_inclusive",
    "price_includes_tax": "tax_inclusive",
    "tax_included": "tax_inclusive",
    "currency": "currency",
    "currency_code": "currency",
    "amount_currency": "amount_currency",
    "amount_in_currency": "amount_currency",
}

# Payment / matching helpers
PAYMENT_COLUMN_TARGETS: tuple[str, ...] = (
    "move_ref",
    "partner",
    "amount",
    "date",
    "journal",
    "memo",
    "payment_type",
)

PAYMENT_HEADER_ALIASES: dict[str, str] = {
    "move_ref": "move_ref",
    "invoice": "move_ref",
    "invoice_ref": "move_ref",
    "move": "move_ref",
    "move_id": "move_ref",
    "partner": "partner",
    "partner_name": "partner",
    "amount": "amount",
    "payment_amount": "amount",
    "date": "date",
    "payment_date": "date",
    "journal": "journal",
    "journal_code": "journal",
    "bank_journal": "journal",
    "memo": "memo",
    "communication": "memo",
    "payment_type": "payment_type",
    "type": "payment_type",
}

