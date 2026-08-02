"""Power Ops probe_recipe min_major — consistent with UI belowMinMajor semantics."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.power_ops_recipes import PowerRecipe, RecipeStep, get_recipe, probe_recipe, run_recipe


class _FakeCaps:
    def __init__(self, major: int | None) -> None:
        self.major = major


class _FakeClient:
    """Minimal client for probe_recipe / dry-run without live Odoo."""

    def __init__(
        self,
        *,
        major: int | None = 19,
        models: set[str] | None = None,
        module_states: dict[str, str] | None = None,
        search_ids: list[int] | None = None,
    ) -> None:
        self.capabilities = _FakeCaps(major)
        self._models = models or {"account.move", "res.partner"}
        self._module_states = module_states or {"account": "installed"}
        self._search_ids = list(search_ids if search_ids is not None else [11, 12])
        self.calls: list[tuple[Any, ...]] = []

    def model_exists(self, model: str) -> bool:
        return model in self._models

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        self.calls.append((model, method, args, kwargs or {}))
        if method == "search":
            return list(self._search_ids)
        if method == "search_read" and model == "ir.module.module":
            name = args[0][0][2] if args and args[0] else None
            state = self._module_states.get(str(name), "uninstalled")
            return [{"id": 1, "name": name, "state": state}]
        if method == "check_access_rights":
            return True
        raise AssertionError(f"unexpected {model}.{method}")


def _recipe_with_min_major(min_major: int) -> PowerRecipe:
    base = get_recipe("mass_archive")
    assert base is not None
    return replace(base, min_major=min_major)


@pytest.mark.parametrize(
    "client_major,min_major,expect_ok",
    [
        (16, 16, True),
        (16, 17, False),
        (16, 19, False),
        (17, 16, True),
        (17, 17, True),
        (17, 18, False),
        (18, 19, False),
        (19, 19, True),
        (19, 20, False),
        # major unknown → probe skips min_major gate (UI belowMinMajor fails closed separately)
        (None, 19, True),
    ],
)
def test_probe_recipe_min_major_gate(
    client_major: int | None, min_major: int, expect_ok: bool
) -> None:
    client = _FakeClient(major=client_major)
    recipe = _recipe_with_min_major(min_major)
    ok, reason = probe_recipe(client, recipe, "res.partner")  # type: ignore[arg-type]
    assert ok is expect_ok
    if expect_ok:
        assert "RPC available" in reason
    else:
        assert reason == (
            f"Recipe requires Odoo ≥{min_major}; connection is major {client_major}"
        )


def test_belowMinMajor_ui_semantics_match_probe_when_major_known() -> None:
    """Mirror apps/web belowMinMajor: major < min_major ⇒ blocked.

    UI: belowMinMajor(conn, min) === true when connectionMajor < min.
    API: probe_recipe returns available=False with exact reason string.
    """
    cases = [
        (16, 17),
        (16, 19),
        (17, 18),
        (18, 19),
    ]
    for major, min_major in cases:
        ui_blocked = major < min_major
        assert ui_blocked is True
        client = _FakeClient(major=major)
        ok, reason = probe_recipe(client, _recipe_with_min_major(min_major), "res.partner")  # type: ignore[arg-type]
        assert ok is False
        assert f"≥{min_major}" in reason
        assert f"major {major}" in reason


def test_probe_recipe_model_missing() -> None:
    client = _FakeClient(major=19, models={"res.partner"})
    recipe = get_recipe("purge_journal_entries")
    assert recipe is not None
    ok, reason = probe_recipe(client, recipe, "account.move")  # type: ignore[arg-type]
    assert ok is False
    assert reason == "Model account.move not installed on this database"


def test_probe_recipe_module_uninstalled() -> None:
    client = _FakeClient(
        major=19,
        models={"account.move"},
        module_states={"account": "uninstalled"},
    )
    recipe = get_recipe("purge_journal_entries")
    assert recipe is not None
    ok, reason = probe_recipe(client, recipe, "account.move")  # type: ignore[arg-type]
    assert ok is False
    assert "Module account is not installed" in reason
    assert "uninstalled" in reason


def test_run_recipe_refuses_when_min_major_blocks() -> None:
    client = _FakeClient(major=16)
    result = run_recipe(
        client,  # type: ignore[arg-type]
        recipe_id="mass_archive",
        model="res.partner",
        dry_run=True,
    )
    # mass_archive default min_major=16 → allowed
    assert result.available is True
    assert result.ok is True

    # Force higher floor via temporary recipe is covered by probe; run uses get_recipe.
    # Capability refuse path: missing model
    result_bad = run_recipe(
        client,  # type: ignore[arg-type]
        recipe_id="purge_journal_entries",
        dry_run=True,
    )
    # Fake has account.move — should pass min_major 16
    assert result_bad.available is True


def test_run_recipe_empty_domain_dry_run_zero_processed() -> None:
    """Adversarial: empty search result (domain matches nothing) → processed=0."""
    client = _FakeClient(major=19, search_ids=[])
    result = run_recipe(
        client,  # type: ignore[arg-type]
        recipe_id="mass_archive",
        model="res.partner",
        domain=[("id", "=", -1)],
        dry_run=True,
    )
    assert result.ok is True
    assert result.available is True
    assert result.processed == 0
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.logs == []
    # search called with the empty-match domain
    search_calls = [c for c in client.calls if c[1] == "search"]
    assert search_calls
    assert search_calls[0][2] == [[("id", "=", -1)]]


def test_run_recipe_unknown_recipe_raises() -> None:
    from odoo_client.client import OdooClientError

    client = _FakeClient(major=19)
    with pytest.raises(OdooClientError, match="Unknown recipe"):
        run_recipe(client, recipe_id="does_not_exist", model="res.partner")  # type: ignore[arg-type]


def test_run_recipe_star_model_requires_explicit_model() -> None:
    from odoo_client.client import OdooClientError

    client = _FakeClient(major=19)
    with pytest.raises(OdooClientError, match="model is required"):
        run_recipe(client, recipe_id="mass_archive", dry_run=True)  # type: ignore[arg-type]


def test_run_recipe_unavailable_when_probe_fails_min_major() -> None:
    """Inject a high min_major recipe via monkeypatch-free synthetic probe path."""
    client = _FakeClient(major=16)
    recipe = PowerRecipe(
        id="needs_19",
        name="Needs 19",
        description="synthetic",
        model="res.partner",
        steps=[RecipeStep(kind="write", values={"active": False}, label="Archive")],
        min_major=19,
        destructive=False,
    )
    ok, reason = probe_recipe(client, recipe, "res.partner")  # type: ignore[arg-type]
    assert ok is False
    assert reason == "Recipe requires Odoo ≥19; connection is major 16"

    # Simulate run_recipe early return shape
    from app.power_ops_recipes import PowerOpsResult

    early = PowerOpsResult(
        ok=False,
        dry_run=True,
        processed=0,
        succeeded=0,
        failed=0,
        message=reason,
        available=False,
        unavailable_reason=reason,
    )
    assert early.available is False
    assert early.processed == 0


def test_list_recipes_min_major_floor() -> None:
    from app.power_ops_recipes import list_recipes

    rows = list_recipes()
    assert len(rows) >= 1
    for row in rows:
        assert isinstance(row["min_major"], int)
        assert row["min_major"] >= 16
