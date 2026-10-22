import pytest
from unittest.mock import MagicMock
from app.power_ops_recipes import (LOCKED_RECIPES, RecipeLocked, list_recipes, recipe_lock_reason, run_recipe, _exec_step, RecipeStep)

LOCKED = ["purge_journal_entries", "mass_unlink", "cancel_account_moves", "reset_and_cancel_moves", "post_account_moves", "unreconcile_and_draft"]

@pytest.mark.parametrize("rid", LOCKED)
def test_locked_refused_before_odoo(rid):
    c = MagicMock()
    with pytest.raises(RecipeLocked, match="keep your books safe"):
        run_recipe(c, recipe_id=rid, model="res.partner", ids=[1], dry_run=True)
    c.execute_kw.assert_not_called()

def test_listed_as_locked():
    rows = {r["id"]: r for r in list_recipes()}
    assert all(rows[r]["locked"] for r in LOCKED) and not rows["mass_archive"]["locked"]

def test_any_recipe_on_money_model_locked():
    assert recipe_lock_reason("mass_archive", "account.move")
    assert recipe_lock_reason("mass_archive", "res.partner") is None

def test_exec_step_refuses_money_model():
    c = MagicMock(); c.edition = "community"
    with pytest.raises(RecipeLocked):
        _exec_step(c, "account.move.line", RecipeStep(kind="write", values={"name": "x"}), [1])
    c.execute_kw.assert_not_called()

def test_router_403():
    from fastapi import HTTPException
    from app.routers import power_ops
    body = MagicMock(recipe_id="post_account_moves", model=None, dry_run=True)
    with pytest.raises(HTTPException) as e:
        power_ops.run_power_ops("c1", body, db=MagicMock(), _=None)
    assert e.value.status_code == 403 and e.value.detail["code"] == "money_guard"
