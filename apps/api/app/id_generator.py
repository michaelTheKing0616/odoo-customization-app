"""Inventory reference ID generator — PREFIX/INITIALS/NUMBER (BLK-9)."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

DEFAULT_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "de",
        "la",
        "le",
        "les",
        "du",
        "des",
        "el",
        "los",
        "las",
        "y",
        "e",
        "et",
    }
)

_NBSP = "\u00a0"
_TRIM_RE = re.compile(r"[\s" + _NBSP + r"]+")


class IdGeneratorError(Exception):
    pass


@dataclass(frozen=True)
class IdGeneratorConfig:
    prefix: str
    separator: str = "-"
    padding: int = 4
    initials_length: int = 3
    skip_if_present: bool = True
    stopwords: frozenset[str] = DEFAULT_STOPWORDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "prefix", trim_text(self.prefix).upper())
        object.__setattr__(self, "separator", trim_text(self.separator) or "-")
        object.__setattr__(self, "padding", int(self.padding))
        object.__setattr__(self, "initials_length", int(self.initials_length))
        if self.padding < 1 or self.padding > 12:
            raise IdGeneratorError("padding must be between 1 and 12")
        if self.initials_length < 1 or self.initials_length > 8:
            raise IdGeneratorError("initials_length must be between 1 and 8")
        if not self.prefix:
            raise IdGeneratorError("prefix is required")


@dataclass(frozen=True)
class InputRow:
    row_id: str | int
    name: str
    existing_code: str | None = None


@dataclass
class CodeAssignment:
    row_id: str | int
    name: str
    existing_code: str | None
    new_code: str | None
    changed: bool
    initials: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IdGeneratorRunResult:
    run_id: str
    operation: str
    model: str
    total: int
    succeeded: int
    failed: int
    changed: int
    skipped: int
    assignments: list[CodeAssignment] = field(default_factory=list)
    dry_run: bool = True
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "operation": self.operation,
            "model": self.model,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "changed": self.changed,
            "skipped": self.skipped,
            "assignments": [a.to_dict() for a in self.assignments],
            "dry_run": self.dry_run,
            "message": self.message,
        }


def trim_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).replace(_NBSP, " ")
    return _TRIM_RE.sub(" ", text).strip()


def _optional_str(value: Any) -> str | None:
    if value is False or value is None:
        return None
    text = trim_text(str(value))
    return text or None


def _optional_str(value: Any) -> str | None:
    if value is False or value is None:
        return None
    text = trim_text(str(value))
    return text or None


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def extract_initials(
    name: str,
    length: int = 3,
    stopwords: frozenset[str] | None = None,
) -> str:
    length = int(length)
    if length < 1:
        raise IdGeneratorError("initials length must be >= 1")
    stop = stopwords or DEFAULT_STOPWORDS
    normalized = _normalize_name(trim_text(name))
    words = [w for w in normalized.split() if w and w.lower() not in stop]
    if not words:
        words = [w for w in normalized.split() if w]
    if not words:
        return ("X" * length)[:length]

    chars: list[str] = []
    for word in words:
        if len(chars) >= length:
            break
        chars.append(word[0].upper())

    word_idx = 0
    char_idx = 1
    guard = 0
    while len(chars) < length and guard < length * 10:
        word = words[word_idx % len(words)]
        if char_idx < len(word):
            chars.append(word[char_idx].upper())
            char_idx += 1
        else:
            word_idx += 1
            char_idx = 1
        guard += 1
    return "".join(chars)[:length]


def disambiguate_initials(base: str, rank: int, length: int) -> str:
    length = int(length)
    rank = int(rank)
    base = trim_text(base).upper()[:length]
    if rank <= 0:
        return base.ljust(length, "X")[:length]
    suffix = str(rank + 1)
    if length <= 1:
        return (base[:1] + suffix)[:length]
    return (base[: max(length - len(suffix), 1)] + suffix)[:length]


def _code_pattern(prefix: str, separator: str, initials: str) -> re.Pattern[str]:
    esc = re.escape
    return re.compile(
        rf"^{esc(prefix)}{esc(separator)}{esc(initials)}{esc(separator)}(\d+)$",
        re.IGNORECASE,
    )


def next_number(
    existing_codes: set[str],
    prefix: str,
    initials: str,
    padding: int,
    *,
    separator: str = "-",
) -> str:
    padding = int(padding)
    prefix = trim_text(prefix).upper()
    initials = trim_text(initials).upper()
    pattern = _code_pattern(prefix, separator, initials)
    max_num = 0
    for code in existing_codes:
        m = pattern.match(trim_text(code).upper())
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}{separator}{initials}{separator}{max_num + 1:0{padding}d}"


def assign_initials_for_rows(
    rows: list[InputRow],
    *,
    length: int,
    stopwords: frozenset[str] | None = None,
) -> dict[str | int, str]:
    bases: list[tuple[str | int, str]] = []
    for row in rows:
        rid = row.row_id
        if isinstance(rid, str) and rid.isdigit():
            rid = int(rid)
        bases.append((rid, extract_initials(row.name, length=length, stopwords=stopwords)))
    groups: dict[str, list[str | int]] = {}
    for rid, base in bases:
        groups.setdefault(base, []).append(rid)
    out: dict[str | int, str] = {}
    for base, ids in groups.items():
        stable_ids = sorted(ids, key=lambda x: (isinstance(x, str), x))
        for rank, rid in enumerate(stable_ids):
            out[rid] = disambiguate_initials(base, rank, length)
    return out


def generate_codes(
    rows: list[InputRow],
    config: IdGeneratorConfig,
    *,
    external_codes: set[str] | None = None,
) -> list[CodeAssignment]:
    if not rows:
        return []
    cfg = config
    normalized_rows = [
        InputRow(
            row_id=int(row.row_id) if str(row.row_id).isdigit() else row.row_id,
            name=trim_text(row.name),
            existing_code=trim_text(row.existing_code) or None,
        )
        for row in rows
    ]
    initials_map = assign_initials_for_rows(
        normalized_rows,
        length=cfg.initials_length,
        stopwords=cfg.stopwords,
    )
    known: set[str] = {c.upper() for c in (external_codes or set()) if trim_text(c)}
    for row in normalized_rows:
        if row.existing_code:
            known.add(row.existing_code.upper())

    assignments: list[CodeAssignment] = []
    for row in normalized_rows:
        existing = row.existing_code
        if cfg.skip_if_present and existing:
            assignments.append(
                CodeAssignment(
                    row_id=row.row_id,
                    name=row.name,
                    existing_code=existing,
                    new_code=existing,
                    changed=False,
                    initials=initials_map.get(row.row_id),
                )
            )
            continue
        initials = initials_map[row.row_id]
        new_code = next_number(
            known,
            cfg.prefix,
            initials,
            cfg.padding,
            separator=cfg.separator,
        )
        known.add(new_code.upper())
        assignments.append(
            CodeAssignment(
                row_id=row.row_id,
                name=row.name,
                existing_code=existing,
                new_code=new_code,
                changed=True,
                initials=initials,
            )
        )
    return assignments


def rows_from_csv_dicts(
    rows: list[dict[str, str]],
    *,
    name_column: str,
    code_column: str | None = None,
    id_column: str | None = None,
) -> list[InputRow]:
    name_column = trim_text(name_column)
    if not name_column:
        raise IdGeneratorError("name_column is required")
    out: list[InputRow] = []
    for idx, raw in enumerate(rows, start=1):
        row = {trim_text(k): trim_text(v) for k, v in raw.items()}
        name = trim_text(row.get(name_column))
        if not name:
            continue
        row_id: str | int = idx
        if id_column and trim_text(row.get(id_column or "")):
            rid_raw = trim_text(row[id_column])
            row_id = int(rid_raw) if rid_raw.isdigit() else rid_raw
        code = _optional_str(row.get(code_column or "")) if code_column else None
        out.append(InputRow(row_id=row_id, name=name, existing_code=code))
    return out


def apply_csv_assignments(
    headers: list[str],
    rows: list[dict[str, str]],
    assignments: list[CodeAssignment],
    *,
    code_column: str,
    changed_only: bool = False,
) -> str:
    code_column = trim_text(code_column)
    by_id = {a.row_id: a for a in assignments}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for idx, raw in enumerate(rows, start=1):
        row = dict(raw)
        rid: str | int = idx
        assignment = by_id.get(rid) or by_id.get(str(rid))
        if assignment and assignment.changed and assignment.new_code:
            row[code_column] = assignment.new_code
        if changed_only and not (assignment and assignment.changed):
            continue
        writer.writerow({h: row.get(h, "") for h in headers})
    return buf.getvalue()


def create_reference_sequence(
    client: OdooClient,
    *,
    model: str,
    config: IdGeneratorConfig,
    sequence_name: str | None = None,
) -> dict[str, Any]:
    model = trim_text(model)
    if not model:
        raise IdGeneratorError("model is required")
    code = f"{model.replace('.', '_')}_ref"
    prefix = f"{config.prefix}{config.separator}"
    vals = {
        "name": sequence_name or f"{model} reference",
        "code": code,
        "prefix": prefix,
        "padding": int(config.padding),
        "number_next": 1,
        "number_increment": 1,
    }
    existing = client.execute_kw(
        "ir.sequence",
        "search",
        [[("code", "=", code)]],
        {"limit": 1},
    )
    if existing:
        seq_id = int(existing[0])
        client.execute_kw("ir.sequence", "write", [[seq_id], vals])
    else:
        seq_id = int(client.execute_kw("ir.sequence", "create", [vals]))
    rows = client.execute_kw(
        "ir.sequence",
        "read",
        [[seq_id]],
        {"fields": ["name", "code", "prefix", "padding", "number_next"]},
    )
    return rows[0] if rows else {"id": seq_id, **vals}


def run_live_id_generator(
    client: OdooClient,
    *,
    model: str,
    name_field: str,
    code_field: str,
    config: IdGeneratorConfig,
    record_ids: list[int],
    dry_run: bool = True,
    run_id: str | None = None,
) -> IdGeneratorRunResult:
    run_id = run_id or str(uuid.uuid4())
    model = trim_text(model)
    name_field = trim_text(name_field)
    code_field = trim_text(code_field)
    if not client.model_exists(model):
        raise IdGeneratorError(f"Model {model!r} not found")
    fg = client.execute_kw(model, "fields_get", [[name_field, code_field]], {})
    if name_field not in fg:
        raise IdGeneratorError(f"Field {name_field!r} not found on {model!r}")
    if code_field not in fg:
        raise IdGeneratorError(f"Field {code_field!r} not found on {model!r}")

    ids = [int(i) for i in record_ids if int(i) > 0]
    if not ids:
        raise IdGeneratorError("No target records")

    rows_raw = client.execute_kw(
        model,
        "read",
        [ids],
        {"fields": [name_field, code_field, "display_name"]},
    )
    input_rows = [
        InputRow(
            row_id=int(r["id"]),
            name=str(r.get(name_field) or r.get("display_name") or ""),
            existing_code=_optional_str(r.get(code_field)),
        )
        for r in rows_raw
    ]
    external = set()
    try:
        all_codes = client.execute_kw(
            model,
            "search_read",
            [[(code_field, "!=", False)]],
            {"fields": [code_field], "limit": 5000},
        )
        external = {_optional_str(r.get(code_field)) for r in all_codes}
        external = {c for c in external if c}
    except OdooClientError:
        external = set()

    assignments = generate_codes(input_rows, config, external_codes=external)
    changed = [a for a in assignments if a.changed]
    succeeded = 0
    failed = 0

    if not dry_run:
        for item in changed:
            try:
                client.execute_kw(
                    model,
                    "write",
                    [[int(item.row_id)], {code_field: item.new_code}],
                )
                succeeded += 1
            except OdooClientError:
                failed += 1
    else:
        succeeded = len(changed)

    skipped = sum(1 for a in assignments if not a.changed)
    return IdGeneratorRunResult(
        run_id=run_id,
        operation="id_generator_live",
        model=model,
        total=len(assignments),
        succeeded=succeeded if not dry_run else len(changed),
        failed=failed,
        changed=len(changed),
        skipped=skipped,
        assignments=assignments,
        dry_run=dry_run,
        message=(
            f"ID generator {'dry-run' if dry_run else 'live'}: "
            f"{len(changed)} changed, {skipped} skipped of {len(assignments)} row(s)"
            + (f", {failed} failed" if failed else "")
        ),
    )
