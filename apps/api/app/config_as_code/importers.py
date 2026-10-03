"""Import checks and CSV load against a fake port. Blank cells are never keys."""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Protocol


LOAD_BATCH_SIZE = 500
LOAD_CONTEXT = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_notrack": True,
}

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_INT_RE = re.compile(r"-?\d+\Z")
_PHONE_FIELD_RE = re.compile(r"(phone|mobile)", re.I)

REFUSED_INTENTS = frozenset(
    {
        "partner_merge",
        "opening_balances",
        "opening_stock",
        "opening_gl",
        "posting",
    }
)
REFUSED_MODELS = {
    "base.partner.merge.automatic.wizard": "partner_merge",
    "base.partner.merge.wizard": "partner_merge",
}
_POSTED_STATES = frozenset({"posted", "post"})
_OPENING_HEADERS = frozenset(
    {"opening_balance", "opening_debit", "opening_credit", "openbal"}
)


class ImportPort(Protocol):
    def load(
        self,
        model: str,
        fields: list[str],
        data: list[list[Any]],
        context: dict[str, Any] | None = None,
    ) -> Any: ...


class ImportRefused(ValueError):
    """Partner merge, opening balances, posting, or write_mode=production."""

    def __init__(self, name: str, *, destructive: bool = True) -> None:
        self.name = name
        self.destructive = destructive
        super().__init__(name)


@dataclass(frozen=True)
class RowError:
    row: int
    message: str


@dataclass
class ImportResult:
    loaded: int
    errors: list[RowError] = field(default_factory=list)
    load_calls: int = 0


class FakeImportPort:
    """Recording port. load() only — no network, no Odoo host."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def load(
        self,
        model: str,
        fields: list[str],
        data: list[list[Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        batch = [list(row) for row in data]
        self.calls.append(
            {
                "model": model,
                "fields": list(fields),
                "data": batch,
                "context": dict(context or {}),
            }
        )
        return {"ids": list(range(1, len(batch) + 1))}


def normalize_ng_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("234"):
        rest = digits[3:]
    elif digits.startswith("0"):
        rest = digits[1:]
    else:
        rest = digits
    if len(rest) < 10:
        raise ValueError("phone too short")
    return "+234" + rest[:10]


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def dedupe_key(row: dict, fields: list[str]) -> str | None:
    parts: list[str] = []
    for field_name in fields:
        value = row.get(field_name)
        if is_blank(value):
            return None
        parts.append(str(value).strip().lower())
    return "|".join(parts)


def fuzzy_name_match(left: str, right: str) -> bool:
    if is_blank(left) or is_blank(right):
        return False
    return SequenceMatcher(None, left.casefold(), right.casefold()).ratio() >= 0.92


def looks_like_ng_phone(raw: object) -> bool:
    if is_blank(raw):
        return False
    text = str(raw).strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+234") or digits.startswith("234"):
        return len(digits) >= 13
    if digits.startswith("0") and len(digits) == 11:
        return True
    return len(digits) == 10 and digits[:1] in "789"


def _trigrams(name: str) -> set[str]:
    folded = name.casefold()
    if len(folded) < 3:
        return {folded} if folded else set()
    return {folded[i : i + 3] for i in range(len(folded) - 2)}


def names_share_block(left: str, right: str) -> bool:
    """3-character blocks before the 0.92 fuzzy compare."""
    if is_blank(left) or is_blank(right):
        return False
    return bool(_trigrams(str(left)) & _trigrams(str(right)))


def template_columns(fields_get: dict[str, Any]) -> list[str]:
    cols = ["id"]
    for name, spec in fields_get.items():
        if name in {"id", "display_name"}:
            continue
        if not isinstance(spec, dict):
            continue
        if spec.get("readonly"):
            continue
        if spec.get("type") == "many2one":
            cols.append(f"{name}/id")
        else:
            cols.append(name)
    return cols


def template_from_fields(fields_get: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(template_columns(fields_get))
    return buf.getvalue()


def parse_csv_text(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    rows: list[dict[str, str]] = []
    for raw in reader:
        rows.append({str(k): "" if v is None else str(v) for k, v in raw.items() if k is not None})
    return headers, rows


def _logical_field(column: str) -> str:
    return column[:-3] if column.endswith("/id") else column


def _field_spec(fields_get: dict[str, Any], column: str) -> dict[str, Any] | None:
    spec = fields_get.get(_logical_field(column))
    return spec if isinstance(spec, dict) else None


def _selection_keys(spec: dict[str, Any]) -> set[str]:
    raw = spec.get("selection") or []
    keys: set[str] = set()
    for item in raw:
        if isinstance(item, (list, tuple)) and item:
            keys.add(str(item[0]))
        elif isinstance(item, str):
            keys.add(item)
    return keys


def _is_phone_column(column: str, spec: dict[str, Any] | None) -> bool:
    if spec and spec.get("type") not in {None, "char", "text"}:
        return False
    return bool(_PHONE_FIELD_RE.search(_logical_field(column)))


def _valid_date(value: str) -> bool:
    if not _DATE_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _valid_datetime(value: str) -> bool:
    text = value.strip()
    if _valid_date(text):
        return True
    try:
        datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return True


def _valid_number(value: str, integer: bool) -> bool:
    text = value.strip()
    if integer:
        return bool(_INT_RE.fullmatch(text))
    try:
        number = float(text)
    except ValueError:
        return False
    return math.isfinite(number)


def _normalize_intent(intent: str) -> str:
    return intent.strip().lower().replace("-", "_").replace(" ", "_")


def _refused_reason(
    model: str,
    intent: str,
    headers: list[str],
    rows: list[dict[str, str]],
) -> str | None:
    kind = _normalize_intent(intent)
    if kind in REFUSED_INTENTS:
        return kind
    if model in REFUSED_MODELS:
        return REFUSED_MODELS[model]
    header_set = {h.strip().lower() for h in headers}
    if "dst_partner_id" in header_set or "partner_ids" in header_set:
        return "partner_merge"
    if header_set & _OPENING_HEADERS:
        return "opening_balances"
    if model in {"account.move", "account.move.line", "account.bank.statement"}:
        for row in rows:
            if str(row.get("state") or "").strip().lower() in _POSTED_STATES:
                return "posting"
    return None


def _load_columns(headers: list[str], fields_get: dict[str, Any]) -> list[str]:
    """Prefer field/id when both the bare column and the external-id column exist."""
    present = set(headers)
    chosen: list[str] = []
    seen_logical: set[str] = set()
    if "id" in present:
        chosen.append("id")
        seen_logical.add("id")
    for column in headers:
        if column == "id":
            continue
        logical = _logical_field(column)
        if logical in seen_logical:
            continue
        external = f"{logical}/id"
        if external in present:
            chosen.append(external)
        else:
            chosen.append(column)
        seen_logical.add(logical)
    return chosen


def _cell(row: dict[str, str], column: str) -> str:
    value = row.get(column)
    return "" if value is None else str(value)


def _transform_cell(column: str, value: str, spec: dict[str, Any] | None) -> str:
    if is_blank(value):
        return ""
    text = value.strip()
    if _is_phone_column(column, spec) and looks_like_ng_phone(text):
        return normalize_ng_phone(text)
    return text


def validate_csv(
    csv_text: str,
    fields_get: dict[str, Any],
    *,
    dedupe_fields: list[str] | None = None,
) -> list[RowError]:
    """Validate every row. Never stop at the first error (EV-DATA-03)."""
    headers, rows = parse_csv_text(csv_text)
    errors: list[RowError] = []
    has_id = "id" in headers
    unknown = [
        column
        for column in headers
        if column != "id" and _field_spec(fields_get, column) is None
    ]

    id_seen: dict[str, int] = {}
    key_seen: dict[str, int] = {}
    name_rows: list[tuple[int, str]] = []
    key_fields = list(dedupe_fields) if dedupe_fields is not None else []

    for index, row in enumerate(rows, start=1):
        if not has_id or is_blank(_cell(row, "id")):
            errors.append(RowError(index, "csv id column is required"))
        elif not is_blank(_cell(row, "id")):
            row_id = _cell(row, "id").strip()
            prior = id_seen.get(row_id)
            if prior is not None:
                errors.append(RowError(index, f"duplicate id {row_id} (also row {prior})"))
                errors.append(RowError(prior, f"duplicate id {row_id} (also row {index})"))
            else:
                id_seen[row_id] = index

        for column in unknown:
            errors.append(RowError(index, f"unknown field {column}"))

        for column in headers:
            if column == "id" or column in unknown:
                continue
            spec = _field_spec(fields_get, column)
            raw = _cell(row, column)
            if is_blank(raw):
                if spec and spec.get("required") and not column.endswith("/id"):
                    errors.append(RowError(index, f"{_logical_field(column)} is required"))
                continue
            text = raw.strip()
            ftype = str((spec or {}).get("type") or "char")
            if ftype == "date" and not _valid_date(text):
                errors.append(RowError(index, f"{column} must be YYYY-MM-DD"))
            elif ftype == "datetime" and not _valid_datetime(text):
                errors.append(RowError(index, f"{column} must be YYYY-MM-DD"))
            elif ftype == "integer" and not _valid_number(text, integer=True):
                errors.append(RowError(index, f"{column} must be an integer"))
            elif ftype in {"float", "monetary"} and not _valid_number(text, integer=False):
                errors.append(RowError(index, f"{column} must be numeric"))
            elif ftype == "selection":
                allowed = _selection_keys(spec or {})
                if allowed and text not in allowed:
                    errors.append(RowError(index, f"{column} is not a valid selection"))
            elif _is_phone_column(column, spec) and looks_like_ng_phone(text):
                try:
                    normalize_ng_phone(text)
                except ValueError as exc:
                    errors.append(RowError(index, f"{column}: {exc}"))

        if key_fields:
            key = dedupe_key(row, key_fields)
            if key is not None:
                prior = key_seen.get(key)
                if prior is not None:
                    errors.append(RowError(index, f"duplicate key {key} (also row {prior})"))
                else:
                    key_seen[key] = index

        name = _cell(row, "name")
        if not is_blank(name):
            name_rows.append((index, name.strip()))

    for i, (row_i, left) in enumerate(name_rows):
        for row_j, right in name_rows[i + 1 :]:
            if names_share_block(left, right) and fuzzy_name_match(left, right):
                errors.append(RowError(row_j, f"duplicate name of row {row_i}"))
                errors.append(RowError(row_i, f"duplicate name of row {row_j}"))

    return errors


def import_csv(
    port: ImportPort,
    *,
    model: str,
    csv_text: str,
    fields_get: dict[str, Any],
    intent: str = "records",
    write_mode: str = "",
    dedupe_fields: list[str] | None = None,
) -> ImportResult:
    """Validate against fields_get, then port.load() in batches of 500.

    write_mode=production is refused. Partner merge, opening balances, and
    posting are refused or marked destructive — never silently loaded.
    """
    if str(write_mode or "").strip().lower() == "production":
        raise ImportRefused("write_mode_production_refused", destructive=True)

    headers, rows = parse_csv_text(csv_text)
    refused = _refused_reason(model, intent, headers, rows)
    if refused:
        raise ImportRefused(f"{refused}_refused", destructive=True)

    errors = validate_csv(csv_text, fields_get, dedupe_fields=dedupe_fields)
    if errors:
        return ImportResult(loaded=0, errors=errors, load_calls=0)

    columns = _load_columns(headers, fields_get)
    payload: list[list[Any]] = []
    for row in rows:
        line: list[Any] = []
        for column in columns:
            spec = _field_spec(fields_get, column)
            line.append(_transform_cell(column, _cell(row, column), spec))
        payload.append(line)

    context = dict(LOAD_CONTEXT)
    load_calls = 0
    for start in range(0, len(payload), LOAD_BATCH_SIZE):
        batch = payload[start : start + LOAD_BATCH_SIZE]
        port.load(model, columns, batch, context=context)
        load_calls += 1
    return ImportResult(loaded=len(payload), errors=[], load_calls=load_calls)
