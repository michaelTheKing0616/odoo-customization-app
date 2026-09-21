"""Batch OS — parse + balance + column map (no live Odoo)."""

import pytest

pytestmark = pytest.mark.no_app_db


from app.batch_os.journal_batch import (
    build_mapped_lines,
    group_moves,
    suggest_journal_column_map,
)
from app.batch_os.parse import parse_upload
from app.batch_os.types import MappedLine


def test_parse_csv_upload():
    raw = b"journal,date,ref,label,account,debit,credit\nMISC,2024-01-15,JE1,Cash,101000,100,0\nMISC,2024-01-15,JE1,Revenue,400000,0,100\n"
    headers, rows = parse_upload(raw, "entries.csv")
    assert "account" in headers
    assert len(rows) == 2


def test_suggest_column_map():
    headers = ["Journal Code", "Date", "Account Code", "Debit", "Credit", "Label"]
    mapping = suggest_journal_column_map(headers)
    assert mapping["Journal Code"] == "journal"
    assert mapping["Account Code"] == "account"
    assert mapping["Debit"] == "debit"
    assert mapping["Credit"] == "credit"


def test_balance_groups_ok():
    rows = [
        {
            "journal": "MISC",
            "date": "2024-01-15",
            "ref": "JE1",
            "label": "Cash",
            "account": "101000",
            "debit": "100",
            "credit": "0",
        },
        {
            "journal": "MISC",
            "date": "2024-01-15",
            "ref": "JE1",
            "label": "Revenue",
            "account": "400000",
            "debit": "0",
            "credit": "100",
        },
    ]
    cmap = suggest_journal_column_map(list(rows[0].keys()))
    lines, errors = build_mapped_lines(rows, cmap)
    assert not [e for e in errors if e.code == "blocking"]
    assert len(lines) == 2
    # assign fake journal ids for grouping
    for line in lines:
        line.journal_id = 1
        line.account_id = 10
    moves = group_moves(lines)
    assert len(moves) == 1
    assert moves[0].balanced is True
    assert moves[0].total_debit == 100.0
    assert moves[0].total_credit == 100.0


def test_unbalanced_move_detected():
    lines = [
        MappedLine(
            row_index=1,
            journal_id=1,
            date="2024-01-01",
            account_id=1,
            debit=50,
            credit=0,
            move_group="A",
        ),
        MappedLine(
            row_index=2,
            journal_id=1,
            date="2024-01-01",
            account_id=2,
            debit=0,
            credit=40,
            move_group="A",
        ),
    ]
    moves = group_moves(lines)
    assert len(moves) == 1
    assert moves[0].balanced is False
