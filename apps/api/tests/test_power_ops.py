"""Unit tests for Power Ops recipes (no live Odoo)."""

from __future__ import annotations

from app.power_ops_recipes import get_recipe, list_recipes, run_recipe


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._ids = [11, 12]

    def model_exists(self, model: str) -> bool:
        return model in {"account.move", "res.partner"}

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        self.calls.append((model, method, args, kwargs or {}))
        if method == "search":
            return list(self._ids)
        if method == "search_read":
            # probe_recipe checks ir.module.module state
            if model == "ir.module.module":
                return [{"id": 1, "name": "account", "state": "installed"}]
            return []
        if method == "check_access_rights":
            return True
        if method in {"button_draft", "unlink", "write", "button_cancel"}:
            return True
        raise AssertionError(f"unexpected {method}")

    def server_version(self) -> dict:
        return {"server_version": "19.0"}


def test_list_includes_journal_purge() -> None:
    ids = {r["id"] for r in list_recipes()}
    assert "purge_journal_entries" in ids
    recipe = get_recipe("purge_journal_entries")
    assert recipe is not None
    assert recipe.steps[0].method == "button_draft"
    assert recipe.steps[1].kind == "unlink"


def test_dry_run_journal_purge() -> None:
    client = _FakeClient()
    result = run_recipe(
        client,  # type: ignore[arg-type]
        recipe_id="purge_journal_entries",
        dry_run=True,
    )
    assert result.ok
    assert result.dry_run
    assert result.processed == 2
    assert not any(c[1] == "button_draft" for c in client.calls)


def test_execute_journal_purge() -> None:
    client = _FakeClient()
    result = run_recipe(
        client,  # type: ignore[arg-type]
        recipe_id="purge_journal_entries",
        dry_run=False,
        ids=[11],
    )
    assert result.succeeded == 1
    methods = [c[1] for c in client.calls]
    assert "button_draft" in methods
    assert "unlink" in methods
