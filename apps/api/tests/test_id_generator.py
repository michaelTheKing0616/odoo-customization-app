"""Unit tests for Inventory ID Generator (BLK-9)."""

from __future__ import annotations

import csv
import io
import random
import string

import pytest

from app.id_generator import (
    CodeAssignment,
    IdGeneratorConfig,
    InputRow,
    apply_csv_assignments,
    assign_initials_for_rows,
    disambiguate_initials,
    extract_initials,
    generate_codes,
    next_number,
    rows_from_csv_dicts,
    trim_text,
)


def _cfg(**kwargs) -> IdGeneratorConfig:
    return IdGeneratorConfig(prefix="INV", **kwargs)


def test_audit_fix_1_only_changed_rows_emitted_in_csv() -> None:
    rows = [
        {"name": "Alpha Widget", "code": "INV-ALP-0001"},
        {"name": "Beta Widget", "code": ""},
    ]
    input_rows = rows_from_csv_dicts(rows, name_column="name", code_column="code")
    assignments = generate_codes(input_rows, _cfg())
    changed_csv = apply_csv_assignments(
        ["name", "code"],
        rows,
        assignments,
        code_column="code",
        changed_only=True,
    )
    parsed = list(csv.DictReader(io.StringIO(changed_csv)))
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Beta Widget"
    assert parsed[0]["code"].startswith("INV-")


def test_audit_fix_2_trim_non_ascii_whitespace() -> None:
    assert trim_text("  hello\u00a0 \t world \n") == "hello world"
    assert trim_text("\u00a0foo") == "foo"


def test_audit_fix_3_int_coercion_on_row_ids() -> None:
    rows = rows_from_csv_dicts(
        [{"id": "42", "name": "Acme Corp"}],
        name_column="name",
        id_column="id",
    )
    assert rows[0].row_id == 42
    assignments = generate_codes(rows, _cfg())
    assert assignments[0].row_id == 42


def test_audit_fix_4_no_shared_mutable_aliases() -> None:
    left = [InputRow(row_id=1, name="Alpha One")]
    right = [InputRow(row_id=2, name="Alpha Two")]
    cfg = _cfg()
    a = generate_codes(left, cfg)
    b = generate_codes(right, cfg)
    assert a[0].new_code != b[0].new_code
    assert a is not b


def test_audit_fix_5_utf8_io_roundtrip() -> None:
    rows = [{"name": "Café Société", "code": ""}]
    input_rows = rows_from_csv_dicts(rows, name_column="name", code_column="code")
    assignments = generate_codes(input_rows, _cfg())
    csv_text = apply_csv_assignments(
        ["name", "code"],
        rows,
        assignments,
        code_column="code",
    )
    encoded = csv_text.encode("utf-8")
    assert "Café Société".encode("utf-8") in encoded


def test_audit_fix_6_semantic_initials_and_collision_disambiguation() -> None:
    assert extract_initials("The Alpha Company", length=3) == "ACL"
    assert extract_initials("École des Arts", length=3) == "EAC"
    rows = [
        InputRow(row_id=1, name="Alpha One"),
        InputRow(row_id=2, name="Alpha Other"),
        InputRow(row_id=3, name="Alpha Odd"),
    ]
    initials = assign_initials_for_rows(rows, length=3)
    assert initials[1] == "AOL"
    assert initials[2] == "AO2"
    assert initials[3] == "AO3"


def test_next_number_increments_from_existing_codes() -> None:
    existing = {"INV-ABC-0004", "INV-ABC-0002", "INV-XYZ-0001"}
    assert next_number(existing, "INV", "ABC", 4) == "INV-ABC-0005"


def test_generate_codes_skip_if_present_default() -> None:
    rows = [InputRow(row_id=1, name="Widget", existing_code="INV-CUS-0099")]
    out = generate_codes(rows, _cfg())
    assert out[0].changed is False
    assert out[0].new_code == "INV-CUS-0099"


def test_property_500_random_names_unique_and_idempotent() -> None:
    rng = random.Random(90210)
    names = []
    for _ in range(500):
        parts = [
            "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(2, 7)))
            for _ in range(rng.randint(1, 4))
        ]
        names.append(" ".join(parts))
    rows = [InputRow(row_id=i + 1, name=n) for i, n in enumerate(names)]
    cfg = _cfg()
    first = generate_codes(rows, cfg)
    codes = [a.new_code for a in first if a.new_code]
    assert len(codes) == len(set(codes))
    assert all(code.startswith("INV-") for code in codes)

    second_rows = [
        InputRow(row_id=a.row_id, name=a.name, existing_code=a.new_code) for a in first
    ]
    second = generate_codes(second_rows, cfg)
    assert sum(1 for a in second if a.changed) == 0


def test_disambiguate_initials_examples() -> None:
    assert disambiguate_initials("ABC", 0, 3) == "ABC"
    assert disambiguate_initials("ABC", 1, 3) == "AB2"
    assert disambiguate_initials("ABC", 2, 3) == "AB3"
