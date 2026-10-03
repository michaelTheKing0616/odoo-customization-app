"""Ingenium CSV import: fields_get validation, load() batches, fake port only."""

from __future__ import annotations

import csv
import io

import pytest

from app.config_as_code.importers import (
    LOAD_BATCH_SIZE,
    LOAD_CONTEXT,
    FakeImportPort,
    ImportRefused,
    dedupe_key,
    fuzzy_name_match,
    import_csv,
    is_blank,
    normalize_ng_phone,
    template_from_fields,
    validate_csv,
)

_FIELDS_GET = {
    "name": {"type": "char", "string": "Name", "required": True},
    "phone": {"type": "char", "string": "Phone"},
    "email": {"type": "char", "string": "Email"},
    "country_id": {"type": "many2one", "string": "Country", "relation": "res.country"},
    "date": {"type": "date", "string": "Date"},
    "state": {"type": "selection", "selection": [("draft", "Draft"), ("done", "Done")]},
    "qty": {"type": "float", "string": "Qty"},
    "count": {"type": "integer", "string": "Count"},
    "create_date": {"type": "datetime", "readonly": True},
}


def _csv(headers: list[str], rows: list[list[object]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def test_nigerian_phone_becomes_e164() -> None:
    assert normalize_ng_phone("08031234567") == "+2348031234567"
    assert normalize_ng_phone("+234 803 123 4567") == "+2348031234567"


def test_blank_cells_are_not_a_dedupe_key() -> None:
    assert is_blank(None) is True
    assert is_blank("  ") is True
    assert is_blank(float("nan")) is True
    assert dedupe_key({"email": "  ", "name": "Ada"}, ["email"]) is None
    assert dedupe_key({"email": "a@b.co"}, ["email"]) == "a@b.co"


def test_fuzzy_name_threshold() -> None:
    assert fuzzy_name_match("Example Foods", "Example Foods") is True
    assert fuzzy_name_match("Example Foods", "Example Food") is True
    assert fuzzy_name_match("Example Foods", "Other Shop") is False
    assert fuzzy_name_match("", "Example") is False


def test_short_phone_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_ng_phone("123")


def test_phone_normalisation() -> None:
    port = FakeImportPort()
    text = _csv(
        ["id", "name", "phone"],
        [
            ["p1", "Ada Okonkwo", "08031234567"],
            ["p2", "Bisi Ade", "+234 802 123 4567"],
        ],
    )
    result = import_csv(
        port, model="res.partner", csv_text=text, fields_get=_FIELDS_GET
    )
    assert result.errors == []
    assert result.loaded == 2
    phones = [row[2] for row in port.calls[0]["data"]]
    assert phones == ["+2348031234567", "+2348021234567"]


def test_duplicates_in_sample() -> None:
    port = FakeImportPort()
    text = _csv(
        ["id", "name", "phone"],
        [
            ["a", "Example Foods", "08031234567"],
            ["b", "Example Food", "08031234568"],
        ],
    )
    result = import_csv(
        port, model="res.partner", csv_text=text, fields_get=_FIELDS_GET
    )
    assert {err.row for err in result.errors} == {1, 2}
    assert result.loaded == 0
    assert port.calls == []


def test_template_from_fields() -> None:
    header = next(csv.reader(io.StringIO(template_from_fields(_FIELDS_GET))))
    assert header[0] == "id"
    assert "name" in header
    assert "country_id/id" in header
    assert "country_id" not in header
    assert "create_date" not in header
    assert "qty" in header


def test_validate_bad_file() -> None:
    """EV-DATA-03: 30 bad rows report all 30 and load none."""
    port = FakeImportPort()
    rows = [[f"r{i}", f"Partner {i:02d}", "not-a-date"] for i in range(1, 31)]
    text = _csv(["id", "name", "date"], rows)
    errors = validate_csv(text, _FIELDS_GET)
    assert {err.row for err in errors} == set(range(1, 31))
    assert len(errors) >= 30
    result = import_csv(
        port, model="res.partner", csv_text=text, fields_get=_FIELDS_GET
    )
    assert {err.row for err in result.errors} == set(range(1, 31))
    assert result.loaded == 0
    assert result.load_calls == 0
    assert port.calls == []


def test_validate_good_file_and_load() -> None:
    port = FakeImportPort()
    text = _csv(
        ["id", "name", "phone", "country_id", "country_id/id", "date"],
        [
            ["p1", "Ada Okonkwo", "08031234567", "ignored", "base.ng", "2026-01-15"],
            ["p2", "Bisi Ade", "08021234567", "also-ignored", "base.ng", "2026-02-01"],
        ],
    )
    result = import_csv(
        port, model="res.partner", csv_text=text, fields_get=_FIELDS_GET
    )
    assert result.errors == []
    assert result.loaded == 2
    assert result.load_calls == 1
    call = port.calls[0]
    assert call["model"] == "res.partner"
    assert "country_id/id" in call["fields"]
    assert "country_id" not in call["fields"]
    assert call["data"][0][call["fields"].index("country_id/id")] == "base.ng"
    assert call["context"]["tracking_disable"] is True
    assert call["context"]["mail_create_nolog"] is True
    assert call["context"]["mail_notrack"] is True

    big = FakeImportPort()
    many = [
        [f"id{i}", f"{i:04d}-{i * 104729}", "2026-03-01"]
        for i in range(LOAD_BATCH_SIZE + 1)
    ]
    big_text = _csv(["id", "name", "date"], many)
    big_result = import_csv(
        big, model="res.partner", csv_text=big_text, fields_get=_FIELDS_GET
    )
    assert big_result.errors == []
    assert big_result.loaded == LOAD_BATCH_SIZE + 1
    assert big_result.load_calls == 2
    assert [len(call["data"]) for call in big.calls] == [LOAD_BATCH_SIZE, 1]
    for call in big.calls:
        assert len(call["data"]) <= LOAD_BATCH_SIZE
        assert call["context"] == LOAD_CONTEXT


def test_selection_and_numeric_validation() -> None:
    port = FakeImportPort()
    text = _csv(
        ["id", "name", "state", "qty", "count"],
        [
            ["s1", "Bad Select", "posted", "1.5", "2"],
            ["s2", "Bad Float", "draft", "n/a", "2"],
            ["s3", "Bad Int", "done", "1.5", "2.7"],
        ],
    )
    result = import_csv(
        port, model="res.partner", csv_text=text, fields_get=_FIELDS_GET
    )
    messages = {err.row: err.message for err in result.errors}
    assert 1 in messages and "selection" in messages[1]
    assert 2 in messages and "numeric" in messages[2]
    assert 3 in messages and "integer" in messages[3]
    assert result.loaded == 0
    assert port.calls == []

    good = _csv(
        ["id", "name", "state", "qty", "count"],
        [["ok", "Good Row", "draft", "1.5", "2"]],
    )
    ok = import_csv(
        FakeImportPort(), model="res.partner", csv_text=good, fields_get=_FIELDS_GET
    )
    assert ok.errors == []
    assert ok.loaded == 1


def test_blank_values_are_not_duplicates() -> None:
    port = FakeImportPort()
    text = _csv(
        ["id", "name", "email", "phone"],
        [
            ["a", "Ada Okonkwo", "", ""],
            ["b", "Bisi Ade", "  ", ""],
        ],
    )
    assert dedupe_key({"email": "", "name": "Ada Okonkwo"}, ["email"]) is None
    assert dedupe_key({"email": "  ", "name": "Bisi Ade"}, ["email"]) is None
    result = import_csv(
        port,
        model="res.partner",
        csv_text=text,
        fields_get=_FIELDS_GET,
        dedupe_fields=["email", "phone"],
    )
    assert result.errors == []
    assert result.loaded == 2
    assert port.calls


def test_partner_merge_opening_and_posting_are_refused() -> None:
    port = FakeImportPort()
    partners = _csv(["id", "name"], [["p1", "Ada Okonkwo"]])
    with pytest.raises(ImportRefused, match="partner_merge") as merge:
        import_csv(
            port,
            model="base.partner.merge.automatic.wizard",
            csv_text=partners,
            fields_get=_FIELDS_GET,
        )
    assert merge.value.destructive is True
    with pytest.raises(ImportRefused, match="opening_balances") as opening:
        import_csv(
            port,
            model="account.move",
            csv_text=partners,
            fields_get=_FIELDS_GET,
            intent="opening_balances",
        )
    assert opening.value.destructive is True
    posted = _csv(["id", "name", "state"], [["m1", "Opening", "posted"]])
    move_fields = {
        **_FIELDS_GET,
        "state": {"type": "selection", "selection": [("draft", "Draft"), ("posted", "Posted")]},
    }
    with pytest.raises(ImportRefused, match="posting") as posting:
        import_csv(
            port, model="account.move", csv_text=posted, fields_get=move_fields
        )
    assert posting.value.destructive is True
    assert port.calls == []


def test_write_mode_production_is_refused() -> None:
    port = FakeImportPort()
    text = _csv(["id", "name"], [["p1", "Ada Okonkwo"]])
    with pytest.raises(ImportRefused, match="write_mode_production_refused"):
        import_csv(
            port,
            model="res.partner",
            csv_text=text,
            fields_get=_FIELDS_GET,
            write_mode="production",
        )
    assert port.calls == []
