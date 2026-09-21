"""Journal batch dry-run with mock RPC client."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.journal_batch import JournalBatchRecipe


class FakeClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.posted: list[int] = []

    def model_exists(self, model: str) -> bool:
        return model in {
            "account.move",
            "account.journal",
            "account.account",
            "res.partner",
        }

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
        kwargs = kwargs or {}
        if model == "account.journal" and method == "search_read":
            return [{"id": 7, "name": "Miscellaneous", "code": "MISC", "type": "general"}]
        if model == "account.account" and method == "search_read":
            domain = args[0] if args else []
            code = None
            for leaf in domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) >= 3 and leaf[0] == "code":
                    code = leaf[2]
            mapping = {"101000": 101, "400000": 400}
            if code in mapping:
                return [{"id": mapping[code], "code": code}]
            return []
        if model == "account.move" and method == "create":
            vals = args[0]
            self.created.append(vals)
            return 9000 + len(self.created)
        if model == "account.move" and method == "action_post":
            self.posted.extend(args[0])
            return True
        return []


def _rows():
    return [
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


def test_journal_dry_run_balanced_mock():
    recipe = JournalBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="je.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "dry_run"
    assert len(state.moves) == 1
    assert state.moves[0].balanced is True
    assert client.created == []
    assert "DRAFT" in state.message or "not posted" in state.message.lower()


def test_journal_apply_creates_draft_mock():
    recipe = JournalBatchRecipe()
    client = FakeClient()
    state = recipe.intake(
        connection_id="c1",
        filename="je.csv",
        headers=list(_rows()[0].keys()),
        rows=_rows(),
    )
    state = recipe.map(state)
    state = recipe.apply(state, client, post_after_create=False)
    assert state.phase == "applied"
    assert len(client.created) == 1
    assert client.posted == []
    assert state.created_move_ids
    move_vals = client.created[0]
    assert move_vals["move_type"] == "entry"
    assert len(move_vals["line_ids"]) == 2


def test_journal_unbalanced_blocks_dry_run():
    recipe = JournalBatchRecipe()
    client = FakeClient()
    rows = _rows()
    rows[1]["credit"] = "50"
    state = recipe.intake(
        connection_id="c1",
        filename="bad.csv",
        headers=list(rows[0].keys()),
        rows=rows,
    )
    state = recipe.map(state)
    state = recipe.dry_run(state, client)
    assert state.phase == "failed"
    assert any(e.code == "blocking" for e in state.errors)
