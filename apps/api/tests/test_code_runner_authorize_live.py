"""code_runner.ai.authorize refuses models/fields the live schema lacks (GND-GATE closed_choice)."""

from app.code_runner.ai import authorize
from app.code_runner.lint import lint

_FIELDS = {"res.partner": {"name": {}, "email": {}}}


def _lint(code: str) -> list:
    return lint(code, major=18, model_names={"res.partner"}, fields_of=lambda m: _FIELDS.get(m, {}))


def test_unknown_model_is_refused() -> None:
    out = authorize('odoo.execute_kw("x.invented", "search", [[]])', "", _lint)
    assert not out["ok"] and "x.invented" in out["reason"]


def test_unknown_field_is_refused() -> None:
    out = authorize('odoo.execute_kw("res.partner", "search", [[("x_made_up", "=", 1)]])', "", _lint)
    assert not out["ok"] and "x_made_up" in out["reason"]


def test_known_structure_passes() -> None:
    out = authorize('odoo.execute_kw("res.partner", "search", [[("email", "=", "a")]])', "", _lint)
    assert out["ok"]


def test_owner_existing_issue_is_not_blamed_on_the_ai() -> None:
    old = 'odoo.execute_kw("x.old", "search", [[]])'
    assert authorize(old + "\nlog(1)", old, _lint)["ok"]


def test_unreadable_schema_refuses_a_change() -> None:
    out = authorize("log(2)", "log(1)", _lint, schema_known=False)
    assert not out["ok"]
